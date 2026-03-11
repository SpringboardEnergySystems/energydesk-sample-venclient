"""
Example Scheduled Tasks
Define your scheduled tasks here
"""
import asyncio
import logging
from datetime import datetime
import pendulum
from cache import RpiCache
from venclient.client import load_and_register_resources, report_metervalues, retrieve_vtn_programs, enroll_vtn_programs

logger = logging.getLogger(__name__)


def heartbeat_task():
    """Example: Simple heartbeat task that runs periodically if needing to send to other services"""
    logger.debug(f"[HEARTBEAT] Service is alive at {datetime.now()}")


def sync_resources():
    """Example: Sync data from external sources"""
    try:
        logger.info("[RESOURCE_SYNC] Check resources to be synchronized...")
        # Add your data sync logic here
        # Example: sync cleared contracts, update positions, etc.
        ven_cache = RpiCache()
        asyncio.run(load_and_register_resources(ven_cache.ven_client))
        logger.info("[RESOURCE_SYNC] Resources Synchronized")
    except Exception as e:
        logger.error(f"[RESOURCE_SYNC] Failed: {e}", exc_info=True)


def sync_vtn_programs():
    """Fetch programs from the VTN and upsert them into the local DB."""
    try:
        logger.info("[PROGRAM_SYNC] Fetching VTN programs...")
        ven_cache = RpiCache()
        asyncio.run(retrieve_vtn_programs(ven_cache.ven_client))
        logger.info("[PROGRAM_SYNC] Done")
    except Exception as e:
        logger.error(f"[PROGRAM_SYNC] Failed: {e}", exc_info=True)

def entroll_vtn_programs():
    """Example: Sync data from external sources"""
    try:
        logger.info("[RESOURCE_SYNC] Check resources to be enrolled...")

        ven_cache = RpiCache()
        asyncio.run(enroll_vtn_programs(ven_cache.ven_client))
        logger.info("[RESOURCE_SYNC] Resources enrolled")
    except Exception as e:
        logger.error(f"[RESOURCE_SYNC] Failed: {e}", exc_info=True)

def report_resource_metervalues():
    """Example: Report meter values to VEN server"""
    try:
        logger.info("[REPORT_VALUES] Starting reporting from InfluxDB...")
        ven_cache = RpiCache()
        report_metervalues(ven_cache.ven_client)
        logger.info("[REPORT_VALUES] Starting reporting from InfluxDB")
    except Exception as e:
        logger.error(f"[REPORT_VALUES] Failed: {e}", exc_info=True)

