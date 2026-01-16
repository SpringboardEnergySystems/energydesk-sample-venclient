"""
Quick test to verify random meter assignment to approved resources
"""
import logging
from venclient.simulation.meterdata_simulator import initialize_simulator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize simulator
simulator = initialize_simulator(ven_list=["Herning"])

# Get approved resources
approved = simulator.get_ven_resources("Herning", status='APPROVED')

logger.info(f"\n=== Meter Assignment Verification ===")
logger.info(f"Total approved resources: {len(approved)}")

# Show first 10 approved resources with their assigned meters
logger.info("\nFirst 10 approved resources with assigned meters:")
for i, (resource_id, resource) in enumerate(list(approved.items())[:10]):
    logger.info(f"{i+1}. {resource.resourceName}")
    logger.info(f"   Resource ID: {resource_id[:20]}...")
    logger.info(f"   Assigned Meter: {resource.meterPointId}")
    logger.info(f"   Location: {resource.location.get('latitude')}, {resource.location.get('longitude')}")

# Verify meters are from the available pool
available_meters = simulator.available_meters
logger.info(f"\nTotal available meters in pool: {len(available_meters)}")

# Check if all assigned meters are from the available pool
all_valid = True
for resource_id, resource in approved.items():
    if resource.meterPointId not in available_meters:
        logger.error(f"ERROR: Resource {resource_id} has invalid meter: {resource.meterPointId}")
        all_valid = False

if all_valid:
    logger.info("✓ All approved resources have valid meters from the available pool!")
else:
    logger.error("✗ Some resources have invalid meters!")

