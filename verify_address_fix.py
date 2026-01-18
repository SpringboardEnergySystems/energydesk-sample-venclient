"""
Verify that address is being sent in service_location instead of attributes
"""
import asyncio
import logging
from venclient.client import VENManager, load_vens_from_sqlite
from energydeskapi.sdk.logging_utils import setup_service_logging
from venclient.utils import get_access_token
import environ
from energydeskapi.sdk.common_utils import get_environment_value

logger = logging.getLogger(__name__)

async def verify_address_in_service_location():
    """
    Verify that resources are registered with address in service_location
    """
    setup_service_logging("Address Fix Verification")

    # Load environment
    environ.Env.read_env()
    vtn_url = get_environment_value('VTN_SERVER_ADDRESS', None)
    bearer_token = get_access_token()

    if not vtn_url:
        logger.error("Missing VTN_SERVER_ADDRESS in environment")
        return

    logger.info("=" * 60)
    logger.info("Verifying Address Field Location Fix")
    logger.info("=" * 60)

    # Create manager
    manager = VENManager(vtn_base_url=vtn_url, bearer_token=bearer_token)

    # Load one VEN for testing
    vens = load_vens_from_sqlite("./config/resources.db")
    if not vens:
        logger.error("No VENs found in database")
        return

    test_ven = vens[0]  # Use first VEN
    logger.info(f"Testing with VEN: {test_ven}")

    # Register VEN
    logger.info("Registering VEN...")
    await manager.register_load_ven(test_ven)

    # Register resources (just first few for testing)
    logger.info("Registering resources (limited to first batch)...")
    stats = await manager.register_loads_parallel(
        test_ven,
        batch_size=5,  # Small batch for testing
        delay_between_batches=0.1
    )

    logger.info("=" * 60)
    logger.info("Registration Test Complete")
    logger.info(f"  Total loads: {stats['total_loads']}")
    logger.info(f"  Registered: {stats['registered']}")
    logger.info(f"  Failed: {stats['failed']}")
    logger.info("=" * 60)

    if stats['registered'] > 0:
        logger.info("✓ Success! Check VTN server logs/database to verify address is in service_location")
        logger.info("  Expected: service_location.address should contain the address")
        logger.info("  Expected: attributes should NOT contain address")
    else:
        logger.warning("⚠ No resources were registered. Check VTN server logs for details.")

    # Cleanup
    await manager.cleanup()

if __name__ == '__main__':
    asyncio.run(verify_address_in_service_location())
