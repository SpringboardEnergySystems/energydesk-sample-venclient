import argparse
import json
import logging
from energydeskapi.sdk.logging_utils import setup_service_logging, create_logstash_from_environment
from cache import RpiCache
from venserver.server import mainapp as app
import sys
from venclient.scheduler import SchedulerConfig, get_scheduler
from venclient import scheduled_tasks
import environ
import uvicorn
logger = logging.getLogger(__name__)
environ.Env.read_env()
env = environ.Env()





# Module-level cache instance that persists across startup/shutdown
_ven_cache = None






def startup() -> None:
    global _ven_cache
    _ven_cache = RpiCache()
    _ven_cache.initialize()
    logger.info("✅ VEN cache initialized")

    scheduler = get_scheduler()
    scheduler.add_task(SchedulerConfig(
        name="ven_client_heartbeat",
        func=scheduled_tasks.heartbeat_task,
        trigger_type='interval',
        seconds=30
    ))

    scheduler.add_task(SchedulerConfig(
        name="ven_client_sync_vtn_programs",
        func=scheduled_tasks.sync_vtn_programs,   # fetch programs from VTN → local DB (hourly)
        trigger_type='cron',
        day_of_week='mon-sun',
        hour='*/1',
        minute='30'
    ))

    scheduler.add_task(SchedulerConfig(
        name="ven_client_enroll_vtn_programs",
        func=scheduled_tasks.entroll_vtn_programs,  # enroll pending resources into programs (daily)
        trigger_type='cron',
        day_of_week='mon-sun',
        hour='6',
        minute='0'
    ))

    scheduler.add_task(SchedulerConfig(
        name="ven_client_load_and_register_resources",
        func=scheduled_tasks.sync_resources,   # wrapper that calls load_and_register_resources(client)
        trigger_type='cron',
        day_of_week='mon-sun',
        hour='*/3',
        minute='15'
    ))

    scheduler.add_task(SchedulerConfig(
        name="ven_client_report_metervalues",
        func=scheduled_tasks.report_resource_metervalues,
        trigger_type='cron',
        day_of_week='mon-sun',
        hour='*',
        minute='*/1'
    ))

    # Start the scheduler
    scheduler.start()
    logger.info("Scheduler started with configured tasks")

def exit_gracefully():
    """Gracefully shutdown the server and clean up resources"""
    global _ven_cache

    logger.warning("Shutting down VEN server...")

    # Shutdown scheduler gracefully
    scheduler = get_scheduler()
    scheduler.shutdown(wait=True)
    logger.info(f"❌Scheduler shut down successfully")

    # Clean up portfolio cache if it exists
    if _ven_cache is not None:
        logger.info("Cleaning up VEN cache...")

    logger.info("✅ Shutdown complete")

def startvenserver(port) -> None:
    logger.info("Starting VEN OpsServer")
    app.add_event_handler('shutdown',exit_gracefully)
    #app.run(host='0.0.0.0',port=port, debug=True, use_reloader=False)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == '__main__':
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='VEN Ops Server')
    parser.add_argument('--port', '-p', type=int, default=8090,
                        help='Port number to run the server on (default: 8000)')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                        help='Host to bind the server to (default: 0.0.0.0)')
    args = parser.parse_args()

    logconf=create_logstash_from_environment()
    if logconf is None:
        setup_service_logging("VEN Client")
    else:
        setup_service_logging(logconf.appname,enable_logstash_conf=logconf)


    port = env.int("ALTERNATIVE_POD_PORT", default=args.port)

    startup()
    startvenserver(args.port)
