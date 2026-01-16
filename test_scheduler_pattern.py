"""
Test script for verifying the ApplicationContext and scheduler pattern
"""
import logging
import time
import asyncio
from venclient.context import register_object, get_ven_manager, get_simulator, get_context
from venclient.scheduler import SchedulerConfig, get_scheduler
from venclient import scheduled_tasks

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MockVENManager:
    """Mock VENManager for testing"""
    def __init__(self):
        self.vens = {"TestVEN": "mock"}
        self.report_count = 0

    async def generate_reports(self):
        """Mock report generation"""
        self.report_count += 1
        logger.info(f"[MOCK] Generated report #{self.report_count}")
        await asyncio.sleep(0.1)  # Simulate async work


class MockSimulator:
    """Mock MeterDataSimulator for testing"""
    def __init__(self):
        self.current_index = 0

    def increase_time(self):
        """Mock time advancement"""
        self.current_index += 1
        logger.info(f"[MOCK] Advanced time to index {self.current_index}")
        return self.current_index

    def get_statistics(self):
        """Mock statistics"""
        return {
            'total_vens': 1,
            'total_resources': 15,
            'total_by_status': {
                'APPROVED': 10,
                'PENDING': 5,
                'SUSPENDED': 0
            },
            'by_ven': {
                'TestVEN': {
                    'approved': 10,
                    'pending': 5,
                    'suspended': 0,
                    'total': 15
                }
            }
        }


def test_context_pattern():
    """Test the ApplicationContext pattern"""
    logger.info("="*60)
    logger.info("Testing ApplicationContext Pattern")
    logger.info("="*60)

    # Create mock objects
    logger.info("\n1. Creating mock objects...")
    manager = MockVENManager()
    simulator = MockSimulator()

    # Register in context
    logger.info("2. Registering objects in ApplicationContext...")
    register_object('ven_manager', manager)
    register_object('simulator', simulator)

    # Verify registration
    ctx = get_context()
    registered = ctx.list_registered()
    logger.info(f"   Registered objects: {registered}")
    assert 'ven_manager' in registered
    assert 'simulator' in registered

    # Retrieve objects
    logger.info("\n3. Retrieving objects from context...")
    retrieved_manager = get_ven_manager()
    retrieved_simulator = get_simulator()

    assert retrieved_manager is manager, "Manager not retrieved correctly"
    assert retrieved_simulator is simulator, "Simulator not retrieved correctly"
    logger.info("   ✓ Objects retrieved successfully")

    # Test from scheduled tasks
    logger.info("\n4. Testing access from scheduled_tasks functions...")

    # Test simulate_meterdata
    logger.info("\n   Running simulate_meterdata()...")
    scheduled_tasks.simulate_meterdata()
    assert simulator.current_index == 1, "Simulator time not advanced"

    # Test resource_status_checker
    logger.info("\n   Running resource_status_checker()...")
    scheduled_tasks.resource_status_checker()

    # Test generate_reports_task
    logger.info("\n   Running generate_reports_task()...")
    scheduled_tasks.generate_reports_task()
    assert manager.report_count == 1, "Reports not generated"

    logger.info("\n" + "="*60)
    logger.info("✓ All ApplicationContext tests passed!")
    logger.info("="*60)


def test_scheduler_integration():
    """Test the scheduler with ApplicationContext"""
    logger.info("\n" + "="*60)
    logger.info("Testing Scheduler Integration")
    logger.info("="*60)

    # Create mock objects
    logger.info("\n1. Creating and registering mock objects...")
    manager = MockVENManager()
    simulator = MockSimulator()
    register_object('ven_manager', manager)
    register_object('simulator', simulator)

    # Setup scheduler
    logger.info("\n2. Configuring scheduler...")
    scheduler = get_scheduler()

    # Add tasks with short intervals for testing
    scheduler.add_task(SchedulerConfig(
        name="test_simulate",
        func=scheduled_tasks.simulate_meterdata,
        trigger_type='interval',
        seconds=2
    ))

    scheduler.add_task(SchedulerConfig(
        name="test_reports",
        func=scheduled_tasks.generate_reports_task,
        trigger_type='interval',
        seconds=3
    ))

    logger.info("   Added 2 test tasks")

    # Start scheduler
    logger.info("\n3. Starting scheduler...")
    scheduler.start()

    # Show scheduled jobs
    jobs = scheduler.get_jobs()
    logger.info(f"   Scheduled jobs: {len(jobs)}")
    for job in jobs:
        logger.info(f"      - {job.name}: next run at {job.next_run_time}")

    # Run for a few seconds
    logger.info("\n4. Running scheduler for 10 seconds...")
    logger.info("   (Watch for task executions)")

    try:
        for i in range(10):
            time.sleep(1)
            if (i + 1) % 3 == 0:
                logger.info(f"   ... {i+1} seconds elapsed")
    finally:
        # Stop scheduler
        logger.info("\n5. Stopping scheduler...")
        scheduler.shutdown(wait=True)
        logger.info("   Scheduler stopped")

    # Verify tasks executed
    logger.info("\n6. Verifying task execution...")
    logger.info(f"   Simulator time index: {simulator.current_index}")
    logger.info(f"   Report count: {manager.report_count}")

    assert simulator.current_index > 0, "Simulate task didn't run"
    assert manager.report_count > 0, "Report task didn't run"

    logger.info("\n" + "="*60)
    logger.info("✓ All Scheduler Integration tests passed!")
    logger.info("="*60)


def test_async_handling():
    """Test async function handling in scheduled tasks"""
    logger.info("\n" + "="*60)
    logger.info("Testing Async Function Handling")
    logger.info("="*60)

    # Register mock manager
    manager = MockVENManager()
    register_object('ven_manager', manager)

    logger.info("\n1. Testing async method call from sync context...")
    initial_count = manager.report_count

    # Call the scheduled task (which handles async internally)
    scheduled_tasks.generate_reports_task()

    logger.info(f"   Reports before: {initial_count}")
    logger.info(f"   Reports after: {manager.report_count}")

    assert manager.report_count > initial_count, "Async method not called"

    logger.info("\n" + "="*60)
    logger.info("✓ Async handling test passed!")
    logger.info("="*60)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("ApplicationContext and Scheduler Pattern Test Suite")
    print("="*60)

    try:
        # Test 1: Context pattern
        test_context_pattern()

        # Test 2: Async handling
        test_async_handling()

        # Test 3: Scheduler integration (this one actually runs tasks)
        print("\n\nWARNING: The next test will run for 10 seconds")
        response = input("Continue with scheduler integration test? (y/n): ").strip().lower()
        if response == 'y':
            test_scheduler_integration()
        else:
            print("Skipped scheduler integration test")

        print("\n" + "="*60)
        print("✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("="*60)
        print("\nThe ApplicationContext and Scheduler pattern is working correctly!")
        print("You can now use this pattern in your application.")

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

