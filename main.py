import logging
import time
import traceback
import asyncio
import environ
from energydeskapi.sdk.common_utils import get_environment_value
from energydeskapi.sdk.logging_utils import setup_service_logging
from venclient.utils import get_access_token
from venclient.scheduler import SchedulerConfig, get_scheduler
from venclient import scheduled_tasks
from venclient.context import register_object, get_context

logger = logging.getLogger(__name__)

def start_scheduler():
    """Initialize and configure the task scheduler"""
    scheduler = get_scheduler()

    # Task 1: Heartbeat - runs every minute to show system is alive
    scheduler.add_task(SchedulerConfig(
         name="heartbeat",
         func=scheduled_tasks.heartbeat_task,
         trigger_type='interval',
         minutes=5
    ))

    # Task 2: Simulate meter data - advances simulation time
    # Runs every 10 seconds during business hours on weekdays
    scheduler.add_task(SchedulerConfig(
        name="simulate_meterdata",
        func=scheduled_tasks.simulate_meterdata,
        trigger_type='cron',
        day_of_week='mon-sun',  # Every day
        hour='0-23',  # All hours
        second='*/30'  # Every 30 seconds
    ))

    # Task 3: Resource status checker - monitors resource health
    # Runs every minute
    scheduler.add_task(SchedulerConfig(
        name="resource_status_checker",
        func=scheduled_tasks.resource_status_checker,
        trigger_type='interval',
        minutes=5
    ))

    # Task 4: Generate reports - sends meter data to VTN
    # Runs every 15 seconds
    scheduler.add_task(SchedulerConfig(
        name="generate_reports",
        func=scheduled_tasks.generate_reports_task,
        trigger_type='interval',
        seconds=15
    ))

    logger.info("Scheduler configured with 4 tasks")
    return scheduler


async def initialize_ven_system(vtn_url: str, bearer_token: str, db_path: str = "./config/resources.db"):
    """
    Initialize the VEN system: register VENs, setup simulator, and register in context.

    Args:
        vtn_url: VTN server URL
        bearer_token: Authentication token
        db_path: Path to SQLite database with resources

    Returns:
        Tuple of (VENManager, MeterDataSimulator)
    """
    from venclient.client import VENManager, load_vens_from_sqlite
    from venclient.simulation.meterdata_simulator import MeterDataSimulator

    logger.info("="*60)
    logger.info("Initializing VEN System")
    logger.info("="*60)

    # Step 1: Create VEN Manager
    logger.info("Step 1: Creating VEN Manager...")
    manager = VENManager(vtn_base_url=vtn_url, bearer_token=bearer_token)

    # Step 2: Load VENs from database
    logger.info("Step 2: Loading VENs from SQLite database...")
    vens = load_vens_from_sqlite(db_path)
    logger.info(f"Found {len(vens)} VENs in database")

    # Step 3: Register VENs with VTN (limit for testing)
    logger.info("Step 3: Registering VENs with VTN server...")
    vens_to_register = vens # Limit to first 10 for testing
    for idx, ven_id in enumerate(vens_to_register, 1):
        logger.info(f"  [{idx}/{len(vens_to_register)}] Registering VEN: {ven_id}")
        try:
            await manager.register_load_ven(ven_id)
            await manager.register_resources(ven_id)
            #await manager.bulk_upload_historical_meterdata(ven_id)
        except Exception as e:
            logger.error(f"  Failed to register VEN {ven_id}: {e}")

    # Step 4: Initialize simulator
    logger.info("Step 4: Initializing Meter Data Simulator...")
    simulator = MeterDataSimulator(db_path=db_path)
    simulator.initialize_resources(vens_to_register)

    stats = simulator.get_statistics()
    logger.info(f"Simulator initialized with:")
    logger.info(f"  - {stats['total_vens']} VENs")
    logger.info(f"  - {stats['total_resources']} total resources")
    logger.info(f"  - {stats['total_by_status']['APPROVED']} approved resources")
    logger.info(f"  - {stats['total_by_status']['PENDING']} pending resources")
    logger.info(f"  - {stats['total_by_status']['SUSPENDED']} suspended resources")

    # Step 5: Register in application context
    logger.info("Step 5: Registering objects in ApplicationContext...")
    register_object('ven_manager', manager)
    register_object('simulator', simulator)

    ctx = get_context()
    logger.info(f"Registered objects: {ctx.list_registered()}")

    logger.info("="*60)
    logger.info("VEN System Initialization Complete")
    logger.info("="*60)

    return manager, simulator


if __name__ == '__main__':
    # Setup logging first
    setup_service_logging("VEN client")

    # Load environment variables
    environ.Env.read_env()
    vtn_url = get_environment_value('VTN_SERVER_ADDRESS', None)
    ven_id = get_environment_value('VEN_LOCAL_ID', None)

    if not vtn_url:
        logger.error("Missing required environment variable: VTN_SERVER_ADDRESS")
        exit(1)

    logger.info(f"Starting VEN client, connecting to {vtn_url}")

    try:
        # Get authentication token
        bearer_token = get_access_token()
        logger.info(f"Authenticated with VTN server")

        # Initialize VEN system (async)
        logger.info("Initializing VEN system...")
        manager, simulator = asyncio.run(initialize_ven_system(vtn_url, bearer_token))

        # Configure and start scheduler
        logger.info("Starting task scheduler...")
        scheduler = start_scheduler()
        #scheduler.start()
        logger.info("Scheduler started successfully")

        # Main loop - keep application running
        logger.info("VEN client is now running. Press Ctrl+C to stop.")
        logger.info("Scheduled tasks:")
        for job in scheduler.get_jobs():
            logger.info(f"  - {job.name}: next run at {job.next_run_time}")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Error in VEN client: {e}")
        logger.error(traceback.format_exc())
        exit(1)
    finally:
        # Cleanup
        logger.info("Shutting down...")
        scheduler = get_scheduler()
        scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")

        # Cleanup VEN manager
        ctx = get_context()
        manager = ctx.get('ven_manager')
        if manager:
            asyncio.run(manager.cleanup())

        logger.info("VEN client stopped")

