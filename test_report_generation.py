"""
Test script for verifying the report generation functionality with simulated meter data.
This script tests the integration between MeterDataSimulator and the VENClient reporting.
"""
import asyncio
import logging
from venclient.client import VENManager
from venclient.simulation.meterdata_simulator import MeterDataSimulator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_report_generation():
    """Test the report generation with simulated meter data"""
    logger.info("=" * 80)
    logger.info("Testing Report Generation with Simulated Meter Data")
    logger.info("=" * 80)

    # Configuration
    vtn_url = "http://localhost:8444/openadr3"
    bearer_token = "your-bearer-token-here"  # Replace with actual token
    db_path = "./config/resources.db"

    # Initialize VEN manager
    logger.info("\n1. Initializing VEN Manager...")
    manager = VENManager(vtn_base_url=vtn_url, bearer_token=bearer_token)

    # Initialize simulator with a limited set of VENs for testing
    logger.info("\n2. Initializing Meter Data Simulator...")
    ms = MeterDataSimulator(db_path=db_path)
    test_vens = ["Herning"]  # Start with just one VEN for testing
    ms.initialize_resources(ven_list=test_vens)

    # Register the test VEN
    logger.info("\n3. Registering test VEN...")
    try:
        for ven_id in test_vens:
            await manager.register_load_ven(ven_id)
            logger.info(f"VEN '{ven_id}' registered successfully")
    except Exception as e:
        logger.error(f"Error registering VEN: {e}")
        return

    # Get statistics
    stats = ms.get_statistics()
    logger.info(f"\n4. Simulator Statistics:")
    logger.info(f"   Total VENs: {stats['total_vens']}")
    logger.info(f"   Total Approved Resources: {stats['total_approved']}")

    for ven_id in test_vens:
        ven_stats = stats['by_ven'].get(ven_id, {})
        logger.info(f"\n   VEN '{ven_id}':")
        logger.info(f"      Approved resources: {ven_stats.get('approved', 0)}")
        logger.info(f"      Total resources: {ven_stats.get('total', 0)}")

    # Test report generation
    logger.info("\n5. Testing Report Generation...")
    try:
        # Generate one round of reports
        await manager.generate_reports()
        logger.info("✓ Report generation completed successfully")

    except Exception as e:
        logger.error(f"✗ Error during report generation: {e}")
        import traceback
        traceback.print_exc()

    # Test multiple iterations
    logger.info("\n6. Testing Multiple Report Cycles...")
    for i in range(3):
        logger.info(f"\n   Cycle {i+1}/3:")
        ms.increase_time()
        await manager.generate_reports()
        await asyncio.sleep(1)  # Brief pause between cycles

    logger.info("\n" + "=" * 80)
    logger.info("Test completed successfully!")
    logger.info("=" * 80)

    # Cleanup
    await manager.cleanup()


async def test_report_structure():
    """Test the report data structure without sending to VTN"""
    logger.info("\n" + "=" * 80)
    logger.info("Testing Report Data Structure")
    logger.info("=" * 80)

    # Initialize simulator
    ms = MeterDataSimulator()
    ms.initialize_resources(ven_list=["Herning"])

    # Collect meter data
    logger.info("\n1. Collecting meter data...")
    resources_meterdata = ms.collect_next_metering("Herning")

    logger.info(f"   Collected data for {len(resources_meterdata)} resources")

    # Show sample report structure
    if resources_meterdata:
        resource_id, meter_data = list(resources_meterdata.items())[0]

        logger.info(f"\n2. Sample Resource Data:")
        logger.info(f"   Resource ID: {resource_id[:40]}...")
        logger.info(f"   Meter Point: {meter_data.meter_point_id}")
        logger.info(f"   Number of loads: {len(meter_data.readings)}")

        logger.info(f"\n3. Sample Report Structure:")
        for reading in meter_data.readings[:3]:
            from datetime import datetime
            timestamp_dt = datetime.fromtimestamp(reading.timestamp / 1000)

            # Show what would be sent in the report
            logger.info(f"\n   Load: {reading.load_id}")
            logger.info(f"      Timestamp: {timestamp_dt.isoformat()}")
            logger.info(f"      Power: {reading.power_w:.2f} W ({reading.power_w/1000:.3f} kW)")
            logger.info(f"      Report payload would contain:")
            logger.info(f"         - resource_id: {resource_id[:20]}...")
            logger.info(f"         - timestamp: {timestamp_dt.isoformat()}")
            logger.info(f"         - power_kw: {reading.power_w/1000:.3f}")
            logger.info(f"         - load_component: {reading.load_id}")


if __name__ == "__main__":
    import sys

    print("\nMeter Data Report Generation Test")
    print("=" * 80)
    print("\nThis script tests the integration between the MeterDataSimulator")
    print("and the VENClient report generation functionality.")
    print("\nOptions:")
    print("  1. Test report generation (requires VTN server)")
    print("  2. Test report structure (offline)")
    print()

    choice = input("Enter choice (1 or 2, default=2): ").strip() or "2"

    if choice == "1":
        # Test with actual VTN server
        print("\nNote: This requires a running VTN server and valid bearer token.")
        print("Edit the script to set the correct vtn_url and bearer_token.")
        confirm = input("Continue? (y/n): ").strip().lower()
        if confirm == 'y':
            asyncio.run(test_report_generation())
        else:
            print("Test cancelled.")
    else:
        # Test structure only (offline)
        asyncio.run(test_report_structure())

