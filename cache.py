import asyncio
import logging
from energydeskapi.sdk.common_utils import  get_environment_value
import json
from podlogger import loginfo
from energydeskapi.sdk.api_connection import ApiConnection
from energydeskapi.sdk.common_utils import get_environment_value
import environ
from influxdb_client import InfluxDBClient
logger = logging.getLogger(__name__)
from venclient.utils import get_access_token
from venclient.client import VENClient, VENConfig


from functools import cache
@cache
class RpiCache(object):


    def __init_influxdb(self):
        """
        Initializes the InfluxDB connection.
        """
        # This method can be used to initialize InfluxDB connection if needed
        environ.Env.read_env()
        INFLUXDB_URL = get_environment_value('INFLUXDB_URL', 'http://localhost:8086')
        INFLUXDB_TOKEN = get_environment_value('INFLUXDB_TOKEN', 'mytoken')
        INFLUXDB_ORG = get_environment_value('INFLUXDB_ORG', 'myorg')
        INFLUXDB_BUCKET = get_environment_value('INFLUXDB_BUCKET', 'mybucket')

        # Only create client if URL is properly configured
        if INFLUXDB_URL and INFLUXDB_URL != 'http://localhost:8086':
            try:
                self.influxdb_client = InfluxDBClient(
                    url=INFLUXDB_URL,
                    token=INFLUXDB_TOKEN,
                    org=INFLUXDB_ORG
                )
                self.influxdb_bucket = INFLUXDB_BUCKET
                self.influxdb_org = INFLUXDB_ORG
                loginfo(f"Initialized InfluxDB client with URL: {INFLUXDB_URL}")
            except Exception as e:
                logger.error(f"Failed to initialize InfluxDB client: {e}")
                self.influxdb_client = None
        else:
            logger.warning("InfluxDB URL not configured, skipping InfluxDB initialization")
            self.influxdb_client = None

    def initialize(self):
        VTN_SERVER_ADDRESS = get_environment_value('VTN_SERVER_ADDRESS', "")
        VTN_API_PREFIX = get_environment_value('VTN_API_PREFIX', '/openadr3')
        print(f"Using URL: {VTN_SERVER_ADDRESS}, API prefix: {VTN_API_PREFIX}")
        VEN_LOCAL_ID = get_environment_value('VEN_LOCAL_ID', "")
        bearer_token = get_access_token()
        if not bearer_token:
            logger.warning("No bearer token obtained — VTN requests will be unauthorised. Check OAuth config.")
        config: VENConfig = VENConfig(ven_name=VEN_LOCAL_ID, client_name="rpi-ven-001")
        self.ven_client = VENClient(config, VTN_SERVER_ADDRESS, bearer_token=bearer_token,
                                    vtn_api_prefix=VTN_API_PREFIX)
        asyncio.run(self.ven_client.register_ven())  # Upsert itself
        self.__init_influxdb()
        self.polling_freq_seconds = int(get_environment_value('POLLING_FREQUENCY_SECONDS', "10"))

    def get_all_data(self):
        """
        Returns all cache data for monitoring purposes.
        """
        return {
            'polling_frequency_seconds': self.polling_freq_seconds,
            'influxdb_connected': hasattr(self, 'influxdb_client') and self.influxdb_client is not None,
        }
