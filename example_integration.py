"""
Example: Integration of MeterDataSimulator with VEN Client Registration

This script demonstrates how to:
1. Load resources from the database using MeterDataSimulator
2. Register resources with the VTN server
3. Update resource status based on VTN approval
4. Prepare approved resources for meter data reporting
"""
import asyncio
import logging
from typing import Dict, List
from venclient.simulation.meterdata_simulator import MeterDataSimulator, initialize_simulator
from venclient.client import VENClient, VENConfig, VENResource

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def register_ven_resources(
    ven_id: str,
    vtn_base_url: str,
    bearer_token: str
) -> Dict[str, bool]:
    """
    Register all pending resources for a VEN with the VTN server.

    Args:
        ven_id: VEN identifier
        vtn_base_url: VTN server base URL
        bearer_token: Authentication token

    Returns:
        Dictionary mapping resource_id to registration success status
    """
    # Get simulator instance (Borg pattern - shared state)
    simulator = MeterDataSimulator()

    # Get pending resources for this VEN
    pending = simulator.get_ven_resources(ven_id, status='PENDING')

    if not pending:
        logger.info(f"No pending resources for VEN '{ven_id}'")
        return {}

    logger.info(f"Registering {len(pending)} resources for VEN '{ven_id}'")

    # Create VEN client
    ven_config = VENConfig(ven_name=ven_id, client_name=f"{ven_id}_client")

    results = {}

    async with VENClient(ven_config, vtn_base_url, bearer_token) as client:
        # First register the VEN itself
        await client.register_ven()

        # Register each pending resource
        for resource_id, resource in pending.items():
            # Convert Resource to VENResource format
            ven_resource = VENResource(
                resource_id=resource.resourceID,
                resource_name=resource.resourceName,
                resource_type=resource.resourceType,
                attributes=[
                    {
                        "type": "capacity",
                        "values": resource.capacities
                    },
                    {
                        "type": "location",
                        "values": resource.location
                    },
                    {
                        "type": "meter_point",
                        "values": {"meter_point_id": resource.meterPointId}
                    }
                ]
            )

            # Register with VTN
            success = await client.register_ven_resource(ven_resource)
            results[resource_id] = success

            # Update status if registration successful
            if success:
                simulator.update_resource_status(ven_id, resource_id, 'APPROVED')
                logger.info(f"✓ Registered and approved: {resource.resourceName}")
            else:
                logger.warning(f"✗ Failed to register: {resource.resourceName}")

    return results


async def sample_registration_workflow():
    """
    Example workflow for registering resources from SQLite database.
    This demonstrates the complete flow from database to VTN registration.
    """
    # Configuration
    VTN_BASE_URL = "http://localhost:8000"
    BEARER_TOKEN = "your-auth-token-here"

    logger.info("=== Resource Registration Workflow ===\n")

    # Step 1: Initialize simulator with specific VENs
    logger.info("Step 1: Initializing MeterDataSimulator...")
    simulator = initialize_simulator(ven_list=["Herning", "Aalborg", "Lemvig"])

    # Show initial statistics
    stats = simulator.get_statistics()
    logger.info(f"Loaded {stats['total_resources']} resources from {stats['total_vens']} VENs")
    logger.info(f"Status: {stats['total_by_status']}\n")

    # Step 2: Register resources for each VEN
    logger.info("Step 2: Registering resources with VTN server...\n")

    for ven_id in simulator.get_ven_list():
        logger.info(f"Processing VEN: {ven_id}")

        # In production, you would actually call the registration function
        # results = await register_ven_resources(ven_id, VTN_BASE_URL, BEARER_TOKEN)

        # For demo purposes, let's simulate approving some resources
        pending = simulator.get_ven_resources(ven_id, status='PENDING')

        # Approve first 5 resources as example
        for i, (resource_id, resource) in enumerate(list(pending.items())[:5]):
            simulator.update_resource_status(ven_id, resource_id, 'APPROVED')
            logger.info(f"  ✓ Approved: {resource.resourceName}")

        logger.info("")

    # Step 3: Show updated statistics
    logger.info("Step 3: Updated statistics after registration\n")
    stats = simulator.get_statistics()

    for ven_id, ven_stats in stats['by_ven'].items():
        logger.info(f"VEN '{ven_id}':")
        logger.info(f"  Pending: {ven_stats['pending']}")
        logger.info(f"  Approved: {ven_stats['approved']}")
        logger.info(f"  Total: {ven_stats['total']}\n")

    # Step 4: Prepare approved resources for meter data reporting
    logger.info("Step 4: Preparing approved resources for meter data reporting\n")

    total_approved = 0
    for ven_id in simulator.get_ven_list():
        approved = simulator.get_ven_resources(ven_id, status='APPROVED')
        total_approved += len(approved)

        if approved:
            logger.info(f"VEN '{ven_id}': {len(approved)} resources ready for reporting")

            # Show first 3 as examples
            for i, (resource_id, resource) in enumerate(list(approved.items())[:3]):
                logger.info(f"  - {resource.resourceName}")
                logger.info(f"    Meter: {resource.meterPointId}")
                logger.info(f"    Type: {resource.resourceType}/{resource.resourceSubType}")

    logger.info(f"\n✓ Total {total_approved} resources ready for meter data reporting")

    logger.info("\n=== Workflow Complete ===")


def show_usage_patterns():
    """
    Show common usage patterns for the MeterDataSimulator.
    """
    logger.info("\n=== Common Usage Patterns ===\n")

    # Pattern 1: Get all VENs
    logger.info("Pattern 1: Get list of all VENs")
    simulator = MeterDataSimulator()
    vens = simulator.get_ven_list()
    logger.info(f"VENs: {vens}\n")

    # Pattern 2: Get resources by status
    logger.info("Pattern 2: Get resources filtered by status")
    ven_id = vens[0] if vens else "Herning"
    approved = simulator.get_ven_resources(ven_id, status='APPROVED')
    logger.info(f"Approved resources for '{ven_id}': {len(approved)}\n")

    # Pattern 3: Iterate through approved resources for reporting
    logger.info("Pattern 3: Prepare approved resources for meter data reporting")
    for resource_id, resource in list(approved.items())[:2]:
        logger.info(f"Resource: {resource.resourceName}")
        logger.info(f"  - Would assign meter data from: {resource.meterPointId}")
        logger.info(f"  - Connection type: {resource.connection.type.value}")
        logger.info(f"  - Location: {resource.location}")

    logger.info("")

    # Pattern 4: Statistics
    logger.info("Pattern 4: Get comprehensive statistics")
    stats = simulator.get_statistics()
    logger.info(f"Statistics: {stats}\n")


if __name__ == "__main__":
    # Run the workflow
    asyncio.run(sample_registration_workflow())

    # Show usage patterns
    show_usage_patterns()

