"""
Demo script to test increase_time() and collect_next_metering() functionality
"""
import logging
from venclient.simulation.meterdata_simulator import MeterDataSimulator, initialize_simulator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def demo_meter_data_collection():
    """Demonstrate collecting meter data at different timestamps"""
    logger.info("=== Meter Data Collection Demo ===\n")

    # Initialize the simulator
    simulator = initialize_simulator(ven_list=["Herning"])

    # Get statistics
    stats = simulator.get_statistics()
    logger.info(f"VEN 'Herning' has {stats['by_ven']['Herning']['approved']} approved resources\n")

    # Collect meter data at different timestamps
    for iteration in range(5):
        logger.info(f"\n--- Iteration {iteration + 1} ---")
        logger.info(f"Current timestamp index: {simulator.current_timestamp_index}")

        # Collect meter data for all approved resources
        resources_meter_data = simulator.collect_next_metering("Herning")

        logger.info(f"Collected data for {len(resources_meter_data)} resources")

        # Show details for first 2 resources
        for i, (resource_id, meter_data) in enumerate(list(resources_meter_data.items())[:2]):
            logger.info(f"\n  Resource {i+1}: {resource_id[:16]}...")
            logger.info(f"    Meter Point: {meter_data.meter_point_id}")
            logger.info(f"    Number of loads: {len(meter_data.readings)}")

            # Show first 3 load readings
            for reading in meter_data.readings[:3]:
                timestamp_str = f"{reading.timestamp / 1000:.0f}"  # Convert back to seconds for display
                logger.info(f"      {reading.load_id}: {reading.power_w:.2f} W at {timestamp_str}")

            if len(meter_data.readings) > 3:
                logger.info(f"      ... and {len(meter_data.readings) - 3} more loads")

        # Increase time to next reading
        new_index = simulator.increase_time()
        logger.info(f"\n  Time increased to index: {new_index}")


def demo_all_vens():
    """Demonstrate collecting meter data for all VENs"""
    logger.info("\n\n=== All VENs Meter Data Collection ===\n")

    simulator = MeterDataSimulator()

    # Collect data for each VEN
    for ven_id in simulator.get_ven_list():
        logger.info(f"\nVEN: {ven_id}")

        resources_meter_data = simulator.collect_next_metering(ven_id)
        logger.info(f"  Collected data for {len(resources_meter_data)} approved resources")

        # Calculate total power across all resources
        total_power = 0
        total_loads = 0

        for meter_data in resources_meter_data.values():
            for reading in meter_data.readings:
                total_power += reading.power_w
                total_loads += 1

        logger.info(f"  Total loads: {total_loads}")
        logger.info(f"  Total power: {total_power:.2f} W ({total_power/1000:.2f} kW)")


def demo_timestamp_progression():
    """Show how timestamps progress through the data"""
    logger.info("\n\n=== Timestamp Progression Demo ===\n")

    simulator = MeterDataSimulator()

    # Get one resource to track
    herning_approved = simulator.get_ven_resources("Herning", status='APPROVED')
    if not herning_approved:
        logger.warning("No approved resources found")
        return

    # Pick first resource
    resource_id = list(herning_approved.keys())[0]
    resource = herning_approved[resource_id]

    logger.info(f"Tracking resource: {resource.resourceName}")
    logger.info(f"Meter point: {resource.meterPointId}\n")

    # Collect readings at 10 different timestamps
    logger.info("First 10 readings:")
    for i in range(10):
        resources_meter_data = simulator.collect_next_metering("Herning")

        if resource_id in resources_meter_data:
            meter_data = resources_meter_data[resource_id]

            # Show first load component
            if meter_data.readings:
                reading = meter_data.readings[0]
                from datetime import datetime
                dt = datetime.fromtimestamp(reading.timestamp / 1000)
                logger.info(f"  {i+1}. Index {simulator.current_timestamp_index}: "
                          f"{dt.strftime('%Y-%m-%d %H:%M:%S')} - "
                          f"{reading.power_w:.2f} W")

        simulator.increase_time()


def demo_data_structure():
    """Show the structure of collected data"""
    logger.info("\n\n=== Data Structure Demo ===\n")

    simulator = MeterDataSimulator()

    # Collect data
    resources_meter_data = simulator.collect_next_metering("Herning")

    if resources_meter_data:
        # Get first resource
        resource_id, meter_data = list(resources_meter_data.items())[0]

        logger.info("Structure of ResourceMeterData:")
        logger.info(f"  resource_id: {meter_data.resource_id[:20]}...")
        logger.info(f"  meter_point_id: {meter_data.meter_point_id}")
        logger.info(f"  readings: List[MeterReading] with {len(meter_data.readings)} items")

        if meter_data.readings:
            logger.info(f"\nStructure of MeterReading:")
            reading = meter_data.readings[0]
            logger.info(f"  timestamp: {reading.timestamp} (milliseconds)")
            logger.info(f"  load_id: {reading.load_id}")
            logger.info(f"  power_w: {reading.power_w}")


if __name__ == "__main__":
    # Run all demos
    demo_meter_data_collection()
    demo_all_vens()
    demo_timestamp_progression()
    demo_data_structure()

    logger.info("\n\n=== Demo Complete ===")

