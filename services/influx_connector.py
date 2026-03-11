import json
import logging
import os
import time
import traceback
import asyncio
import aiohttp
import environ
from energydeskapi.sdk.common_utils import get_environment_value
from energydeskapi.sdk.logging_utils import setup_service_logging
from services.dataclasses import Resource
from influxdb_client import InfluxDBClient
from cache import RpiCache
from podlogger import loginfo, logwarn
# Configuration for InfluxDB 1.x

logger = logging.getLogger(__name__)


def create_cobnnection():
    """
    Initializes the InfluxDB connection.
    """
    # This method can be used to initialize InfluxDB connection if needed
    environ.Env.read_env()
    INFLUXDB_HOST = get_environment_value('INFLUXDB_HOST', None)
    INFLUXDB_PORT = get_environment_value('INFLUXDB_PORT', None)
    INFLUXDB_USER = get_environment_value('INFLUXDB_PORT', None)
    INFLUXDB_PASSWORD = get_environment_value('INFLUXDB_PORT', None)
    INFLUXDB_DATABASE = get_environment_value('INFLUXDB_PORT', None)
    INFLUXDB_URL = get_environment_value('INFLUXDB_URL', None)
    INFLUXDB_TOKEN = get_environment_value('INFLUXDB_TOKEN', None)
    bucket = "mybucket"
    org = "myorg"
    # Create an InfluxDB client
    influxdb_client = InfluxDBClient(
        url=INFLUXDB_URL,
        username=INFLUXDB_USER,
        # password=INFLUXDB_PASSWORD,
        token=INFLUXDB_TOKEN,
        org=org
    )
    loginfo("Initialized InfluxDB client with URL: " + INFLUXDB_URL)
    return influxdb_client

def  update_influxdb( bucket:str, measurement:str, resource:Resource,fields:dict, tags:dict, override_timestamp:int=None):
    """
    Updates InfluxDB with the given resource data.

    Should store metedata from the resource with the data

    Parameters:
        resource (InfluxDBResource): InfluxDB resource
        data (dict): InfluxDB data

    Returns:
        boolean: give the status of the update operation
    """
    cache = RpiCache()
    try:
        cli=cache.influxdb_client
        if cli is None:
            logger.warning("InfluxDB client not initialized, skipping write")
            return False

        #cli=create_cobnnection()
        write_api = cli.write_api()
        timestamp = time.time_ns() if override_timestamp is None else override_timestamp
        print("TIMERSTAMP: ", timestamp, "override_timestamp: ", override_timestamp)
        # Prepare the data point
        point = {
            "measurement": measurement,
            "tags": tags,
            "fields": fields,
            "time": timestamp
        }
        loginfo(f"Writing to InfluxDB: {point}")
        # Write the data point to InfluxDB
        write_api.write(bucket=bucket, record=point)
        logger.info(f"Data written to InfluxDB: {point}")

        write_api.close()
        return True

    except Exception as e:
        logger.error(f"Error writing to InfluxDB: {e}")
        return False

def  read_influxdb( bucket:str, measurement:str,fields: list = None, tags:dict=None, start_time:str=None, end_time:str=None):
    cache = RpiCache()
    try:
        client:InfluxDBClient = cache.influxdb_client
        if client is None:
            logger.warning("InfluxDB client not initialized, returning empty records")
            return []

        # Build the Flux query
        query = f'from(bucket: "{bucket}")\n'
        query += f'  |> range(start: {start_time if start_time else "-100d"}, stop: {end_time if end_time else "now()"})\n'
        #query += f'  |> filter(fn: (r) => r["_field"] == "power")\n'
        if fields:
            field_filter = " or ".join([f'r["_field"] == "{field}"' for field in fields])
            query += f'  |> filter(fn: (r) => {field_filter})\n'

        query += f'  |> filter(fn: (r) => r["_measurement"] == "{measurement}")\n'
        if tags:
            for k, v in tags.items():
                query += f'  |> filter(fn: (r) => r["{k}"] == "{v}")\n'
        query += '  |> aggregateWindow(every: 15m, fn: mean, createEmpty: false)\n'
        query += '  |> yield(name: "mean")'
        loginfo(f"InfluxDB query: {query}")
        result = client.query_api().query(query)
        records = []
        for table in result:
            for record in table.records:
                records.append({
                    "time": record.get_time().isoformat(),
                    "field": record.get_field(),
                    "value": record.get_value(),
                    "tags": record.values
                })
        return records
    except Exception as e:
        logger.error(f"Error reading from InfluxDB: {e}")
        return []

if __name__ == '__main__':
    environ.Env.read_env()
    INFLUXDB_HOST = get_environment_value('INFLUXDB_HOST', None)
    INFLUXDB_PORT = get_environment_value('INFLUXDB_PORT', None)
    INFLUXDB_USER = get_environment_value('INFLUXDB_PORT', None)
    INFLUXDB_PASSWORD = get_environment_value('INFLUXDB_PORT', None)
    INFLUXDB_DATABASE = get_environment_value('INFLUXDB_PORT', None)
    INFLUXDB_URL= get_environment_value('INFLUXDB_URL', None)
    INFLUXDB_TOKEN= get_environment_value('INFLUXDB_TOKEN', None)
    bucket = "mybucket"
    org="myorg"
    # Create an InfluxDB client
    client = InfluxDBClient(
        url=INFLUXDB_URL,
        username=INFLUXDB_USER,
        #password=INFLUXDB_PASSWORD,
        token=INFLUXDB_TOKEN,
        org=org
    )
    query_api = client.query_api()
    # To list measurements (tables) in a specific bucket
    query = f'import "influxdata/influxdb/schema"\nschema.measurements(bucket: "{bucket}")'
    tables = query_api.query(query, org=org)

    print(f"Measurements in bucket '{bucket}':")
    for table in tables:
        for record in table.records:
            print(f"- {record.get_value()}")

    query = 'SHOW TAG KEYS FROM mqtt_consumer'

    # To show all tag keys in the database (may be slower for large databases)
    # query = 'SHOW TAG KEYS'

    #tables = query_api.query(query, org=org)
    #print("Tag keys in the database:",tables)

    query = 'from(bucket:"mybucket")\
    |> range(start: -30d)\
    |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)'

    #result = query_api.query(org=org, query=query)
    tables = query_api.query(query, org=org)
    for table in tables:
        for record in table.records:
            print(f"Time: {record.get_time()},Field: {record.get_field()}, Value: {record.get_value()}")
            #print(f"Measurement: {record}")
            print(f"Topic: {record['topic']}")
