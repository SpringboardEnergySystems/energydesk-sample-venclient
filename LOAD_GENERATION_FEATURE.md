# Load Generation Feature - Implementation Summary

## Overview
This document describes the implementation of the load generation feature that assigns H5 meter data to resources and creates individual load components for simulation purposes.

## Date: January 16, 2026

---

## Implementation Details

### 1. Database Schema Updates

#### Resources Table - Added Column
- **h5_meter_id** (TEXT): References the meter in the H5 file that will be used to simulate this resource's meter readings

#### New Loads Table
The `loads` table stores individual load components for each resource:

```sql
CREATE TABLE loads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    load_id TEXT UNIQUE NOT NULL,              -- UUID for the load
    resource_id TEXT NOT NULL,                  -- Reference to parent resource
    load_component TEXT NOT NULL,               -- Component name (load_0, load_1, etc.)
    load_name TEXT,                             -- Human-readable name
    h5_meter_id TEXT NOT NULL,                  -- H5 meter containing the data
    vtn_resource_id TEXT,                       -- VTN-assigned ID after registration
    registration_status TEXT DEFAULT 'PENDING', -- Registration status
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (resource_id) REFERENCES resources(resource_id)
)
```

**Indexes:**
- `idx_load_resource_id` - Query loads by resource
- `idx_load_h5_meter_id` - Query loads by H5 meter
- `idx_load_vtn_resource_id` - Query loads by VTN resource ID

### 2. Load Component Names

Each resource has 6 load components representing different types of electrical loads:

| Component | Name               | Description                    |
|-----------|--------------------|--------------------------------|
| load_0    | Base Load          | Baseline power consumption     |
| load_1    | Water Heater       | Water heating systems          |
| load_2    | HVAC               | Heating/cooling systems        |
| load_3    | Kitchen Appliances | Cooking and food storage       |
| load_4    | Lighting           | Lighting systems               |
| load_5    | Other Appliances   | Miscellaneous electrical loads |

### 3. Data Flow

```
H5 File (load_data.h5)
    └─> 153 unique meters, each with 6 load components
         └─> Randomly assigned to 19,402 resources
              └─> 116,412 individual load records created (19,402 × 6)
```

---

## Results

### Database Statistics

- **Total Resources**: 19,402
- **Resources with H5 meter assigned**: 19,402 (100%)
- **Total Loads**: 116,412
- **Unique H5 meters used**: 153 (all available meters)

### Loads by Component
Each component has exactly 19,402 records:
- load_0 (Base Load): 19,402
- load_1 (Water Heater): 19,402
- load_2 (HVAC): 19,402
- load_3 (Kitchen Appliances): 19,402
- load_4 (Lighting): 19,402
- load_5 (Other Appliances): 19,402

---

## Files Modified/Created

### 1. `resource_db.py`
**Modified** - Added database schema and methods:
- Added `loads` table creation
- Added `h5_meter_id` column to resources table
- New methods:
  - `update_resource_h5_meter()` - Assign H5 meter to resource
  - `insert_load()` - Insert single load
  - `bulk_insert_loads()` - Bulk insert loads
  - `get_loads_by_resource()` - Query loads for a resource
  - `get_loads_by_h5_meter()` - Query loads by H5 meter
  - `update_load_vtn_resource_id()` - Update after VTN registration
  - `clear_all_loads()` - Delete all loads
  - `get_load_statistics()` - Get load statistics

### 2. `prepare_load_samples.py`
**Rewritten** - Main script to generate loads:
- Reads all unique meters from `load_data.h5`
- Randomly assigns one H5 meter to each resource
- Creates 6 load records per resource (one for each load component)
- Uses bulk insert for performance (processed 19,402 resources in ~7 seconds)

### 3. `migrate_database.py`
**Created** - Database migration script:
- Drops and recreates `loads` table with correct schema
- Adds `h5_meter_id` column to `resources` table if missing
- Creates necessary indexes

### 4. Utility Scripts Created
- `check_database_status.py` - Check database state
- `run_load_setup.py` - Complete setup and verification
- `test_load_gen.py` - Test basic functionality

---

## Usage

### Generate Loads (First Time Setup)
```bash
python3 prepare_load_samples.py
```

### Migrate Existing Database
If you already have a database without the loads table:
```bash
python3 migrate_database.py
python3 prepare_load_samples.py
```

### Check Database Status
```bash
python3 check_database_status.py
```

---

## Example Usage in Code

### Get all loads for a resource
```python
from resource_db import ResourceDatabase

db = ResourceDatabase('./config/resources.db')
loads = db.get_loads_by_resource('resource-uuid-here')

for load in loads:
    print(f"{load['load_name']}: {load['load_component']}")
```

### Get resource with its H5 meter
```python
resource = db.get_resource('resource-uuid-here')
h5_meter_id = resource.h5_meter_id  # Use this to read from H5 file
```

### Access H5 meter data for simulation
```python
import h5py

with h5py.File('config/examplemeterdata/load_data.h5', 'r') as hf:
    meter = hf['meters'][h5_meter_id]
    load_component = meter['load_0']  # or load_1, load_2, etc.
    power_data = load_component['power'][:]  # Shape: (N, 2) [timestamp, power]
```

---

## Integration with VEN Client

### Registration Flow
1. Resources are registered with VTN server
2. Each load component should be registered as a separate resource
3. VTN assigns a `vtn_resource_id` to each load
4. Update loads table with VTN resource IDs using `update_load_vtn_resource_id()`

### Meter Data Reporting
1. Use the `h5_meter_id` from resources table to locate meter data in H5 file
2. Read specific `load_component` data from H5 file
3. Report meter values using the `vtn_resource_id` from loads table

---

## Next Steps

### For Simulation
1. **Implement meter data reader**: Create a function to read H5 data for a specific resource/load
2. **Time-series simulation**: Sample data from H5 file based on current time
3. **Data interpolation**: Handle missing timestamps or intervals

### For Registration
1. **Batch registration**: Register all loads for a VEN
2. **Status tracking**: Update registration_status for each load
3. **VTN resource ID mapping**: Store VTN-assigned IDs

### For Reporting
1. **Load-level reporting**: Report each load component separately
2. **Aggregated reporting**: Sum all loads for a resource
3. **Report generation**: Use load names and components in reports

---

## Performance Notes

- **Bulk insert**: 116,412 records inserted in ~0.3 seconds
- **Assignment speed**: ~2,800 resources/second during assignment
- **Database size**: Approximately 25 MB for 19,402 resources + 116,412 loads
- **Query performance**: Indexed queries are fast (< 1ms for typical queries)

---

## Troubleshooting

### If loads table is missing or has wrong schema
```bash
python3 migrate_database.py
```

### To regenerate all loads (WARNING: deletes existing data)
```python
from resource_db import ResourceDatabase
db = ResourceDatabase('./config/resources.db')
db.clear_all_loads()

# Then run prepare_load_samples.py again
```

### Check H5 file structure
```bash
python3 explore_h5.py
```

---

## Summary

The load generation feature is now complete and functional. The database contains:
- ✅ 19,402 resources, each with an assigned H5 meter
- ✅ 116,412 load components (6 per resource)
- ✅ Complete schema with indexes for efficient queries
- ✅ All 153 available H5 meters are in use

The system is ready for:
1. VTN registration of individual load components
2. Meter data simulation using H5 file data
3. Load-level reporting to VTN server
