"""
Quick Reference: Using MeterDataSimulator for VTN Reporting

This script shows the complete workflow from initialization to reporting.
"""
import logging
from venclient.simulation.meterdata_simulator import (
    MeterDataSimulator,
    initialize_simulator,
    ResourceMeterData,
    MeterReading
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_simple_workflow():
    """Simple workflow: Initialize, collect, increment"""
    print("\n" + "="*60)
    print("SIMPLE WORKFLOW")
    print("="*60 + "\n")

    # Step 1: Initialize
    simulator = initialize_simulator(ven_list=["Herning"])

    # Step 2: Collect meter data
    data = simulator.collect_next_metering("Herning")
    print(f"Collected data for {len(data)} resources")

    # Step 3: Increment timestamp
    simulator.increase_time()
    print(f"Moved to next timestamp (index: {simulator.current_timestamp_index})")


def example_reporting_loop():
    """Reporting loop: Continuous data collection"""
    print("\n" + "="*60)
    print("REPORTING LOOP")
    print("="*60 + "\n")

    simulator = MeterDataSimulator()

    # Simulate 5 reporting cycles
    for cycle in range(5):
        print(f"\n--- Reporting Cycle {cycle + 1} ---")

        # Collect data for VEN
        data = simulator.collect_next_metering("Herning")

        # Report each resource
        total_power = 0
        for resource_id, meter_data in data.items():
            # Sum power across all loads
            resource_power = sum(r.power_w for r in meter_data.readings)
            total_power += resource_power

        print(f"Total power across {len(data)} resources: {total_power/1000:.2f} kW")

        # Move to next timestamp
        simulator.increase_time()


def example_load_by_load_reporting():
    """Report each load component individually"""
    print("\n" + "="*60)
    print("LOAD-BY-LOAD REPORTING")
    print("="*60 + "\n")

    simulator = MeterDataSimulator()

    # Collect data
    data = simulator.collect_next_metering("Herning")

    # Get first resource as example
    resource_id, meter_data = list(data.items())[0]

    print(f"Resource ID: {resource_id[:20]}...")
    print(f"Meter Point: {meter_data.meter_point_id}")
    print(f"Number of loads: {len(meter_data.readings)}\n")

    # Report each load individually
    for reading in meter_data.readings:
        print(f"  {reading.load_id}:")
        print(f"    Timestamp: {reading.timestamp} ms")
        print(f"    Power: {reading.power_w} W")

        # In real implementation, send this to VTN:
        # await send_to_vtn({
        #     "resource_id": resource_id,
        #     "timestamp": reading.timestamp,
        #     "load_id": reading.load_id,
        #     "power": reading.power_w
        # })


def example_multi_ven_collection():
    """Collect data from multiple VENs"""
    print("\n" + "="*60)
    print("MULTI-VEN COLLECTION")
    print("="*60 + "\n")

    simulator = MeterDataSimulator()

    # Collect from all VENs
    all_ven_data = {}
    for ven_id in simulator.get_ven_list():
        data = simulator.collect_next_metering(ven_id)
        all_ven_data[ven_id] = data
        print(f"VEN '{ven_id}': {len(data)} resources")

    # Move all VENs to next timestamp together
    simulator.increase_time()
    print(f"\nAll VENs moved to timestamp index: {simulator.current_timestamp_index}")


def example_data_aggregation():
    """Aggregate data across resources"""
    print("\n" + "="*60)
    print("DATA AGGREGATION")
    print("="*60 + "\n")

    simulator = MeterDataSimulator()

    # Collect data
    data = simulator.collect_next_metering("Herning")

    # Aggregate by load component
    load_totals = {}
    for meter_data in data.values():
        for reading in meter_data.readings:
            if reading.load_id not in load_totals:
                load_totals[reading.load_id] = 0
            load_totals[reading.load_id] += reading.power_w

    print("Power consumption by load component:")
    for load_id, total_power in sorted(load_totals.items()):
        print(f"  {load_id}: {total_power/1000:.2f} kW")

    # Total across all loads
    total = sum(load_totals.values())
    print(f"\nTotal: {total/1000:.2f} kW")


def example_timestamp_info():
    """Display timestamp information"""
    print("\n" + "="*60)
    print("TIMESTAMP INFORMATION")
    print("="*60 + "\n")

    simulator = MeterDataSimulator()

    # Collect data to get timestamp
    data = simulator.collect_next_metering("Herning")

    if data:
        # Get first resource's first reading
        first_resource = list(data.values())[0]
        first_reading = first_resource.readings[0]

        from datetime import datetime
        dt = datetime.fromtimestamp(first_reading.timestamp / 1000)

        print(f"Current Index: {simulator.current_timestamp_index}")
        print(f"Timestamp: {first_reading.timestamp} ms")
        print(f"Date/Time: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Data Length: {simulator.h5_data_length} readings")


def example_approved_vs_all():
    """Show difference between approved and all resources"""
    print("\n" + "="*60)
    print("APPROVED VS ALL RESOURCES")
    print("="*60 + "\n")

    simulator = MeterDataSimulator()

    ven_id = "Herning"

    # All resources
    all_resources = simulator.get_ven_resources(ven_id)
    print(f"Total resources: {len(all_resources)}")

    # By status
    pending = simulator.get_ven_resources(ven_id, status='PENDING')
    approved = simulator.get_ven_resources(ven_id, status='APPROVED')
    suspended = simulator.get_ven_resources(ven_id, status='SUSPENDED')

    print(f"  Pending: {len(pending)}")
    print(f"  Approved: {len(approved)}")
    print(f"  Suspended: {len(suspended)}")

    # Collect metering (only returns approved)
    data = simulator.collect_next_metering(ven_id)
    print(f"\nMeter data collected: {len(data)} resources")
    print("(Only approved resources have meter data)")


# =============================================================================
# QUICK REFERENCE CHEAT SHEET
# =============================================================================

CHEAT_SHEET = """
================================================================================
                    METERDATA SIMULATOR QUICK REFERENCE
================================================================================

INITIALIZATION
--------------
from venclient.simulation.meterdata_simulator import initialize_simulator

# Load specific VENs
simulator = initialize_simulator(ven_list=["Herning", "Aalborg"])

# Load all VENs
simulator = initialize_simulator()

# Get existing instance (Borg pattern - all instances share state)
simulator = MeterDataSimulator()


BASIC OPERATIONS
----------------
# Collect meter data for a VEN
data = simulator.collect_next_metering("Herning")
# Returns: Dict[str, ResourceMeterData]

# Move to next timestamp
new_index = simulator.increase_time()

# Get current index
index = simulator.current_timestamp_index


DATA STRUCTURE
--------------
data = simulator.collect_next_metering("VEN_ID")

for resource_id, meter_data in data.items():
    # meter_data.resource_id    -> str
    # meter_data.meter_point_id -> str
    # meter_data.readings       -> List[MeterReading]
    
    for reading in meter_data.readings:
        # reading.timestamp  -> int (milliseconds)
        # reading.load_id    -> str (e.g., 'load_0')
        # reading.power_w    -> float


RESOURCE QUERIES
----------------
# Get all resources for a VEN
all_res = simulator.get_ven_resources("Herning")

# Get by status
pending = simulator.get_ven_resources("Herning", status='PENDING')
approved = simulator.get_ven_resources("Herning", status='APPROVED')
suspended = simulator.get_ven_resources("Herning", status='SUSPENDED')

# Get list of VENs
vens = simulator.get_ven_list()

# Get statistics
stats = simulator.get_statistics()


STATUS MANAGEMENT
-----------------
# Update resource status
simulator.update_resource_status(
    ven_id="Herning",
    resource_id="abc-123",
    new_status='APPROVED'
)


COMMON PATTERNS
---------------

# Pattern 1: Simple reporting loop
for i in range(10):
    data = simulator.collect_next_metering("Herning")
    send_to_vtn(data)
    simulator.increase_time()

# Pattern 2: Multi-VEN collection
for ven_id in simulator.get_ven_list():
    data = simulator.collect_next_metering(ven_id)
    process(ven_id, data)
simulator.increase_time()

# Pattern 3: Load-by-load reporting
data = simulator.collect_next_metering("Herning")
for resource_id, meter_data in data.items():
    for reading in meter_data.readings:
        report(resource_id, reading)


UTILITIES
---------
# Reset simulator
simulator.reset()

# Get H5 file path
path = simulator.h5_file_path

# Check if initialized
is_init = simulator._initialized

# Get data length
length = simulator.h5_data_length

================================================================================
"""


if __name__ == "__main__":
    print(CHEAT_SHEET)

    # Run all examples
    example_simple_workflow()
    example_reporting_loop()
    example_load_by_load_reporting()
    example_multi_ven_collection()
    example_data_aggregation()
    example_timestamp_info()
    example_approved_vs_all()

    print("\n" + "="*60)
    print("All examples completed successfully!")
    print("="*60 + "\n")

