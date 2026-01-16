"""
Demo script showing how to use the MeterDataSimulator (Borg pattern singleton)
"""
import logging
from venclient.simulation.meterdata_simulator import MeterDataSimulator, initialize_simulator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demo_basic_usage():
    """Demonstrate basic usage of the simulator"""
    logger.info("=== Basic Usage Demo ===\n")

    # Initialize the simulator - load a few VENs for demo
    # You can pass None to load all VENs, or a list of specific VEN IDs
    simulator = initialize_simulator(ven_list=["Herning", "Aalborg", "Lemvig"])

    # Get statistics
    stats = simulator.get_statistics()
    logger.info(f"Total VENs loaded: {stats['total_vens']}")
    logger.info(f"Total resources: {stats['total_resources']}")
    logger.info(f"Status distribution: {stats['total_by_status']}")

    # Show details for each VEN
    for ven_id, ven_stats in stats['by_ven'].items():
        logger.info(f"\nVEN '{ven_id}':")
        logger.info(f"  Pending: {ven_stats['pending']}")
        logger.info(f"  Approved: {ven_stats['approved']}")
        logger.info(f"  Suspended: {ven_stats['suspended']}")
        logger.info(f"  Total: {ven_stats['total']}")


def demo_borg_pattern():
    """Demonstrate that Borg pattern works - all instances share state"""
    logger.info("\n\n=== Borg Pattern Demo ===\n")

    # Create first instance
    sim1 = MeterDataSimulator()
    logger.info(f"sim1 is initialized: {sim1._initialized}")

    # Create second instance - should share same state
    sim2 = MeterDataSimulator()
    logger.info(f"sim2 is initialized: {sim2._initialized}")
    logger.info(f"sim1 and sim2 share state: {sim1 is not sim2 and sim1.__dict__ is sim2.__dict__}")

    # Get stats from both - should be identical
    stats1 = sim1.get_statistics()
    stats2 = sim2.get_statistics()
    logger.info(f"Both instances see same data: {stats1 == stats2}")


def demo_status_filtering():
    """Demonstrate filtering resources by status"""
    logger.info("\n\n=== Status Filtering Demo ===\n")

    simulator = MeterDataSimulator()

    # Pick a VEN to work with
    ven_id = "Herning"

    # Get all resources for this VEN
    all_resources = simulator.get_ven_resources(ven_id)
    logger.info(f"\nVEN '{ven_id}' has {len(all_resources)} total resources")

    # Get pending resources
    pending = simulator.get_ven_resources(ven_id, status='PENDING')
    logger.info(f"  - {len(pending)} PENDING resources")
    if pending:
        first_pending = list(pending.values())[0]
        logger.info(f"    Example: {first_pending.resourceName} ({first_pending.resourceID[:8]}...)")

    # Get approved resources
    approved = simulator.get_ven_resources(ven_id, status='APPROVED')
    logger.info(f"  - {len(approved)} APPROVED resources")

    # Get suspended resources
    suspended = simulator.get_ven_resources(ven_id, status='SUSPENDED')
    logger.info(f"  - {len(suspended)} SUSPENDED resources")


def demo_status_update():
    """Demonstrate updating resource status"""
    logger.info("\n\n=== Status Update Demo ===\n")

    simulator = MeterDataSimulator()
    ven_id = "Herning"

    # Get a pending resource
    pending = simulator.get_ven_resources(ven_id, status='PENDING')
    if not pending:
        logger.warning(f"No pending resources found for VEN '{ven_id}'")
        return

    # Pick the first pending resource
    resource_id = list(pending.keys())[0]
    resource = pending[resource_id]

    logger.info(f"Selected resource: {resource.resourceName}")
    logger.info(f"  Current status: {resource.registration_status}")

    # Update to APPROVED
    logger.info(f"  Updating to APPROVED...")
    simulator.update_resource_status(ven_id, resource_id, 'APPROVED')

    # Verify the change
    approved = simulator.get_ven_resources(ven_id, status='APPROVED')
    if resource_id in approved:
        logger.info(f"  ✓ Successfully moved to APPROVED")
        logger.info(f"  New status: {approved[resource_id].registration_status}")

    # Update back to PENDING for next demo run
    logger.info(f"  Reverting to PENDING...")
    simulator.update_resource_status(ven_id, resource_id, 'PENDING')


def demo_resource_iteration():
    """Demonstrate iterating through approved resources (for meter data assignment)"""
    logger.info("\n\n=== Resource Iteration Demo ===\n")
    logger.info("This shows how you would iterate through approved resources")
    logger.info("to assign simulated meter data in a later step.\n")

    simulator = MeterDataSimulator()

    # Iterate through all VENs
    for ven_id in simulator.get_ven_list():
        # Get only approved resources for this VEN
        approved = simulator.get_ven_resources(ven_id, status='APPROVED')

        if approved:
            logger.info(f"VEN '{ven_id}': {len(approved)} approved resources")
            # Show first few as examples
            for i, (resource_id, resource) in enumerate(list(approved.items())[:3]):
                logger.info(f"  {i+1}. {resource.resourceName}")
                logger.info(f"     - Type: {resource.resourceType}/{resource.resourceSubType}")
                logger.info(f"     - Meter: {resource.meterPointId}")
                logger.info(f"     - Location: {resource.location.get('latitude', 'N/A')}, "
                          f"{resource.location.get('longitude', 'N/A')}")

            if len(approved) > 3:
                logger.info(f"  ... and {len(approved) - 3} more")


if __name__ == "__main__":
    # Run all demos
    demo_basic_usage()
    demo_borg_pattern()
    demo_status_filtering()
    demo_status_update()
    demo_resource_iteration()

    logger.info("\n\n=== Demo Complete ===")
    logger.info("You can now use the MeterDataSimulator in your application!")

