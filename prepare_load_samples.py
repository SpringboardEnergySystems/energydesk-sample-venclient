import logging
import os
import random
import uuid
import h5py
from resource_db import ResourceDatabase

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Load component names for better identification
LOAD_NAMES = {
    'load_0': 'Base Load',
    'load_1': 'Water Heater',
    'load_2': 'HVAC',
    'load_3': 'Kitchen Appliances',
    'load_4': 'Lighting',
    'load_5': 'Other Appliances',
}


def generate_resource_loads():
    """
    Generate load records from h5 meter data and assign to resources in SQLite database.

    Process:
    1. Read all unique meters from load_data.h5
    2. For each resource in resources.db, randomly assign one h5 meter
    3. For each load component in that meter, create a load record in the loads table
    """
    __location__ = os.path.realpath(
        os.path.join(os.getcwd(), os.path.dirname(__file__)))

    h5_file_path = os.path.join(__location__, 'config/examplemeterdata/load_data.h5')
    db_path = os.path.join(__location__, 'config/resources.db')

    # Initialize database
    db = ResourceDatabase(db_path)

    logger.info("Starting load generation process...")

    # Step 1: Read all unique meters from h5 file
    logger.info(f"Reading meters from {h5_file_path}")
    with h5py.File(h5_file_path, 'r') as hf:
        meters_group = hf['meters']
        available_meters = list(meters_group.keys())
        logger.info(f"Found {len(available_meters)} meters in h5 file")

        # Get load components from first meter as template
        first_meter = meters_group[available_meters[0]]
        load_components = sorted([k for k in first_meter.keys() if k.startswith('load_')])
        logger.info(f"Each meter has {len(load_components)} load components: {load_components}")

    # Step 2: Get all resources from database
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT resource_id FROM resources ORDER BY resource_id")
        all_resources = [row[0] for row in cursor.fetchall()]

    logger.info(f"Found {len(all_resources)} resources in database")

    # Step 3: Assign random h5 meter to each resource and create load records
    logger.info("Assigning h5 meters to resources and creating load records...")

    loads_to_insert = []
    resource_updates = []

    for i, resource_id in enumerate(all_resources):
        # Randomly pick an h5 meter for this resource
        assigned_meter = random.choice(available_meters)

        # Update resource with h5_meter_id
        db.update_resource_h5_meter(resource_id, assigned_meter)

        # Create load records for each load component in the assigned meter
        for load_component in load_components:
            load_id = str(uuid.uuid4())
            load_name = LOAD_NAMES.get(load_component, f"Load {load_component}")

            loads_to_insert.append((
                load_id,
                resource_id,
                load_component,
                load_name,
                assigned_meter,
                None  # vtn_resource_id - will be populated during registration
            ))

        # Log progress every 1000 resources
        if (i + 1) % 1000 == 0:
            logger.info(f"Processed {i + 1}/{len(all_resources)} resources...")

    # Step 4: Bulk insert all loads
    logger.info(f"Inserting {len(loads_to_insert)} load records into database...")
    db.bulk_insert_loads(loads_to_insert)

    # Step 5: Show statistics
    logger.info("Load generation complete!")

    # Get statistics
    load_stats = db.get_load_statistics()
    logger.info(f"Load Statistics:")
    logger.info(f"  Total loads: {load_stats['total_loads']}")
    logger.info(f"  By component: {load_stats['by_component']}")
    logger.info(f"  By status: {load_stats['by_status']}")

    # Verify some assignments
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(DISTINCT h5_meter_id) FROM resources WHERE h5_meter_id IS NOT NULL
        """)
        unique_assigned = cursor.fetchone()[0]
        logger.info(f"  Unique h5 meters assigned: {unique_assigned}")

        # Show a sample
        cursor.execute("""
            SELECT r.resource_id, r.h5_meter_id, COUNT(l.load_id) as load_count
            FROM resources r
            LEFT JOIN loads l ON r.resource_id = l.resource_id
            WHERE r.h5_meter_id IS NOT NULL
            GROUP BY r.resource_id
            LIMIT 5
        """)
        logger.info("Sample resource-load assignments:")
        for row in cursor.fetchall():
            logger.info(f"    Resource {row[0][:20]}... -> Meter {row[1]} -> {row[2]} loads")


if __name__ == '__main__':
    generate_resource_loads()