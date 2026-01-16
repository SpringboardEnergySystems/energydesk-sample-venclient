"""
Example Scheduled Tasks
Define your scheduled tasks here

These tasks access shared objects via ApplicationContext singleton.
"""
import logging
import asyncio
from datetime import datetime
from venclient.context import get_ven_manager, get_simulator, get_context

logger = logging.getLogger(__name__)


def heartbeat_task():
    """Example: Simple heartbeat task that runs periodically"""
    logger.info(f"[HEARTBEAT] Service is alive at {datetime.now()}")

    # Show registered objects
    ctx = get_context()
    registered = ctx.list_registered()
    logger.debug(f"[HEARTBEAT] Registered objects: {registered}")


def simulate_meterdata():
    """
    Advance the simulation time and collect meter data.
    This prepares data for the next report cycle.
    """
    try:
        logger.info("[SIMULATE_METERDATA] Starting data simulation...")

        # Get simulator from context
        simulator = get_simulator()
        if not simulator:
            logger.error("[SIMULATE_METERDATA] Simulator not found in context")
            return

        # Advance time in simulation
        new_index = simulator.increase_time()
        logger.info(f"[SIMULATE_METERDATA] Advanced simulation to timestamp index {new_index}")

        # Get statistics
        stats = simulator.get_statistics()
        logger.info(f"[SIMULATE_METERDATA] Simulator has {stats['total_by_status']['APPROVED']} approved resources across {stats['total_vens']} VENs")

        logger.info("[SIMULATE_METERDATA] Data simulation completed")
    except Exception as e:
        logger.error(f"[SIMULATE_METERDATA] Failed: {e}", exc_info=True)


def resource_status_checker():
    """
    Check resource status and log statistics.
    Can be used to monitor resource health, registration status, etc.
    """
    try:
        logger.info("[RESOURCE_STATUS_CHECKER] Starting status check...")

        # Get objects from context
        manager = get_ven_manager()
        simulator = get_simulator()

        if not manager:
            logger.error("[RESOURCE_STATUS_CHECKER] VENManager not found in context")
            return

        if not simulator:
            logger.error("[RESOURCE_STATUS_CHECKER] Simulator not found in context")
            return

        # Check VEN status
        logger.info(f"[RESOURCE_STATUS_CHECKER] Active VENs: {len(manager.vens)}")

        for ven_id, ven in list(manager.vens.items())[:5]:  # Show first 5
            logger.info(f"[RESOURCE_STATUS_CHECKER]   VEN '{ven_id}': {len(ven.resources)} resources registered")

        # Check simulator status
        stats = simulator.get_statistics()
        logger.info(f"[RESOURCE_STATUS_CHECKER] Simulator status:")
        logger.info(f"[RESOURCE_STATUS_CHECKER]   Current timestamp index: {simulator.current_timestamp_index}")
        logger.info(f"[RESOURCE_STATUS_CHECKER]   Total approved resources: {stats['total_by_status']['APPROVED']}")
        logger.info(f"[RESOURCE_STATUS_CHECKER]   Total pending resources: {stats['total_by_status']['PENDING']}")

        logger.info("[RESOURCE_STATUS_CHECKER] Status check completed")
    except Exception as e:
        logger.error(f"[RESOURCE_STATUS_CHECKER] Failed: {e}", exc_info=True)


def generate_reports_task():
    """
    Generate and send meter data reports to VTN.
    This is an async task that needs special handling.
    """
    try:
        logger.info("[GENERATE_REPORTS] Starting report generation...")

        # Get manager from context
        manager = get_ven_manager()
        if not manager:
            logger.error("[GENERATE_REPORTS] VENManager not found in context")
            return

        # Run the async generate_reports method
        # APScheduler runs in a thread, so we need to handle the async call properly
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(manager.generate_reports())
            logger.info("[GENERATE_REPORTS] Report generation completed")
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"[GENERATE_REPORTS] Failed: {e}", exc_info=True)



