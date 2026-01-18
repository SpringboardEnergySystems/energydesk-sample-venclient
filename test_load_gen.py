import logging
import os
import h5py
from resource_db import ResourceDatabase

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

print("Starting test script...")

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
h5_file_path = os.path.join(__location__, 'config/examplemeterdata/load_data.h5')
db_path = os.path.join(__location__, 'config/resources.db')

print(f"H5 file path: {h5_file_path}")
print(f"DB path: {db_path}")

# Initialize database
print("Initializing database...")
db = ResourceDatabase(db_path)
print("Database initialized!")

# Read meters from h5
print("Reading h5 file...")
with h5py.File(h5_file_path, 'r') as hf:
    meters_group = hf['meters']
    available_meters = list(meters_group.keys())
    print(f"Found {len(available_meters)} meters in h5 file")

    first_meter = meters_group[available_meters[0]]
    load_components = sorted([k for k in first_meter.keys() if k.startswith('load_')])
    print(f"Each meter has {len(load_components)} load components: {load_components}")

print("Script completed successfully!")
