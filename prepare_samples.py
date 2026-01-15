import logging
import os
from random import randint
from flex_resources import ResourceType, Resource, ConnectionType, Connection, ActorType
from resource_db import ResourceDatabase
import environ
import pandas as pd

import uuid

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def random_with_N_digits(n):
    range_start = 10**(n-1)
    range_end = (10**n)-1
    return randint(range_start, range_end)

def convert_to_resources(df_resources)->list[Resource]:
    """
    Convert a DataFrame of resources to a list of Resource objects.

    Args:
        df_resources: DataFrame with columns: title, address, longitude, latitude,
                      resource_type, resource_sub_type, meterpoint_id, ven, resource_id

    Returns:
        List of Resource objects
    """
    res_list = []

    # Create a default connection for file-based reading
    # In production, this would be specific to each resource type
    sample_connection = Connection(
        type=ConnectionType.FILEREADER,
        actortype=ActorType.READER,
        host=None,
        port=None,
        topic=None,
        file="",  # Will be populated when actual meter data files are created
        username=None,
        password=None
    )

    # Loop through dataframe and create resource objects
    for _, row in df_resources.iterrows():
        # Determine default capacities based on resource type
        if row['resource_type'] == ResourceType.EV.name:
            # Electric Vehicle - typical charging station capacity
            capacities = {
                'P_max_kw': 22.0,  # Typical EV charger
                'P_min_kw': 0.0,
                'E_max_kwh': 100.0,  # Typical EV battery
                'E_min_kwh': 0.0
            }
        else:
            # DSR resources - varying by sub-type
            subtype = row['resource_sub_type'].lower()
            if 'hotel' in subtype or 'swimmingpool' in subtype:
                capacities = {
                    'P_max_kw': 50.0,
                    'P_min_kw': -20.0,
                    'E_max_kwh': 200.0,
                    'E_min_kwh': 0.0
                }
            elif 'industry' in subtype or 'school' in subtype:
                capacities = {
                    'P_max_kw': 100.0,
                    'P_min_kw': -40.0,
                    'E_max_kwh': 400.0,
                    'E_min_kwh': 0.0
                }
            else:  # bars, restaurants, bakeries, etc.
                capacities = {
                    'P_max_kw': 25.0,
                    'P_min_kw': -10.0,
                    'E_max_kwh': 100.0,
                    'E_min_kwh': 0.0
                }

        # Create location dictionary
        location = {
            'latitude': float(row['latitude']),
            'longitude': float(row['longitude'])
        }

        # Create Resource object
        resource = Resource(
            resourceID=row['resource_id'],
            resourceName=row['title'],
            resourceType=row['resource_type'],
            resourceSubType=row['resource_sub_type'],
            meterPointId=row['meterpoint_id'],
            connection=sample_connection,
            capacities=capacities,
            location=location,
            address=row['address'],
            enabled=True,
            reporting=None  # Will be configured later when reporting starts
        )

        res_list.append((resource, row['ven']))

    logger.info(f"Converted {len(res_list)} resources from DataFrame")
    return res_list

def generate_resources():
    """
    Generate resources from CSV files and store them in SQLite database.
    """
    __location__ = os.path.realpath(
        os.path.join(os.getcwd(), os.path.dirname(__file__)))
    dirname = os.path.join(__location__, "./config/exampleassets")

    # Initialize database
    db = ResourceDatabase(db_path=os.path.join(__location__, "./config/resources.db"))
    logger.info(f"Database initialized at {db.db_path}")

    # Optional: Clear existing data (comment out if you want to keep existing data)
    # db.clear_all_resources()

    total_resources_processed = 0

    for fil in os.listdir(dirname):
        if fil == ".DS_Store":
            continue

        filepath = os.path.join(dirname, fil)
        logger.info(f"Processing file: {filepath}")

        # Extract asset type from filename
        assettype = fil.split("-")
        asset_type_name = assettype[0].capitalize()

        # Read CSV and prepare data
        df = pd.read_csv(filepath)
        df2 = df[['title', 'address', 'longitude', 'latitude']]

        # Set resource type based on file name
        df2['resource_type'] = ResourceType.DSR.name if "chargingstations" not in fil else ResourceType.EV.name
        df2['resource_sub_type'] = asset_type_name

        # Generate unique meter point IDs
        def specify_mpid(row):
            return "707057500" + str(random_with_N_digits(9))
        df2['meterpoint_id'] = df2.apply(specify_mpid, axis=1)

        # Extract VEN (city) from address
        def specify_ven(row):
            add = str(row['address']).split(",")
            city = add[len(add)-2].strip()
            city2 = city.split(" ")
            if len(city2) > 1:
                return city2[1]
            return city2[0] if city2 else "Unknown"
        df2['ven'] = df2.apply(specify_ven, axis=1)

        # Generate unique resource IDs for each row
        df2['resource_id'] = [str(uuid.uuid4()) for _ in range(len(df2))]

        # Drop rows with missing data
        df2 = df2.dropna()

        # Convert to Resource objects
        resource_list = convert_to_resources(df2)

        # Store in database
        for resource, ven in resource_list:
            # Insert connection first
            connection_id = db.insert_connection(resource.connection)
            # Then insert resource with connection reference
            db.insert_resource(resource, connection_id, ven)

        total_resources_processed += len(resource_list)
        logger.info(f"Stored {len(resource_list)} resources from {fil}")

    # Print statistics
    logger.info(f"\n{'='*60}")
    logger.info(f"Total resources processed: {total_resources_processed}")
    logger.info(f"{'='*60}")

    stats = db.get_statistics()
    logger.info(f"\nDatabase Statistics:")
    logger.info(f"  Total resources: {stats['total_resources']}")
    logger.info(f"\n  By Type:")
    for rtype, count in stats['by_type'].items():
        logger.info(f"    {rtype}: {count}")
    logger.info(f"\n  By Sub-Type:")
    for subtype, count in stats['by_subtype'].items():
        logger.info(f"    {subtype}: {count}")
    logger.info(f"\n  Top 10 VENs (Cities):")
    for ven, count in stats['top_10_vens'].items():
        logger.info(f"    {ven}: {count}")
    logger.info(f"{'='*60}\n")

    return db

if __name__ == '__main__':
    environ.Env.read_env()
    generate_resources()