import json
import logging
import os
import time
import traceback
import asyncio
import aiohttp
import schedule
import environ
from energydeskapi.sdk.common_utils import get_environment_value
from energydeskapi.sdk.logging_utils import setup_service_logging
from venclient.client import startup
from flex_resources import load_flexible_resources
from venclient.utils import get_access_token
logger = logging.getLogger(__name__)


if __name__ == '__main__':
    environ.Env.read_env()
    vtn_url = get_environment_value('VTN_SERVER_ADDRESS', None)
    ven_id = get_environment_value('VEN_LOCAL_ID', None)

    if not vtn_url or not ven_id:
        logger.error("Missing required environment variables: VTN_SERVER_ADDRESS and/or VEN_LOCAL_ID")
        exit(1)

    setup_service_logging("VEN client")
    logger.info(f"Starting VEN client with ID {ven_id}, connecting to {vtn_url}")

    try:
        resource_map=load_flexible_resources()
        bearer_token=get_access_token()
        logger.info(f"Bearer token: {bearer_token}")
        asyncio.run(startup(ven_id, vtn_url, bearer_token, resource_map))
        while True:
            logger.info("Sleeping for 5 seconds")
            schedule.run_pending()
            time.sleep(1)
    except Exception as e:
        logger.error(f"Error in VEN client: {e}")
        logger.error(traceback.format_exc())
        exit(1)

