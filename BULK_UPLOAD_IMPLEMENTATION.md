# Bulk Historical Meter Data Upload - Implementation Guide

## Date: January 18, 2026

## Overview

This guide explains how to bulk upload historical meter data from H5 files to the VTN server using the optimized bulk upload endpoint.

## Architecture

```
SQLite Database (resources.db)
    └─> Loads table (with vtn_resource_id)
         └─> References H5 meter data
              └─> H5 File (load_data.h5)
                   └─> Meter data grouped by meter_id and load_component
                        └─> Bulk upload to VTN
```

## Data Flow

1. **Query loads from database** - Get all loads with VTN resource IDs
2. **Load data from H5 file** - Read power data for each load component
3. **Format for API** - Convert to OpenADR bulk upload format
4. **Upload in chunks** - Send large datasets in manageable chunks
5. **Track progress** - Monitor upload statistics

## Implementation

### Function: `bulk_upload_historical_meterdata()`

**Location:** `venclient/client.py`

**Parameters:**
- `ven_id` (str): VEN identifier (city name)
- `db_path` (str): Path to SQLite database (default: "./config/resources.db")
- `h5_file_path` (str): Path to H5 file (default: "./config/examplemeterdata/load_data.h5")
- `chunk_size` (int): Points per chunk (default: 50000)
- `batch_size` (int): InfluxDB batch size (default: 5000)
- `limit_loads` (int): Optional limit for testing (default: None = all loads)

**Returns:**
```python
{
    "success": True,
    "ven_id": "Aalborg",
    "total_loads": 276,
    "successful": 276,
    "failed": 0,
    "total_points_uploaded": 2411964
}
```

### Data Format

**Input (H5 File):**
```
meters/
  └─ meter_707057500054535870/
       ├─ load_0/power: [[timestamp, power_w], ...]
       ├─ load_1/power: [[timestamp, power_w], ...]
       └─ ...
```

**Output (VTN API):**
```json
[
  {
    "interval_start": "2025-01-15T08:00:00Z",
    "interval_end": "2025-01-15T09:00:00Z",
    "value": 620.0,
    "quality_code": "GOOD"
  }
]
```

## Usage Examples

### Example 1: Test with Limited Loads

```bash
# Test with 3 loads only
python3 test_bulk_upload.py --token YOUR_TOKEN --limit 3
```

### Example 2: Upload All Loads for One VEN

```python
import asyncio
from venclient.client import VENManager

async def upload_ven_data():
    manager = VENManager(
        vtn_base_url="http://localhost:8000",
        bearer_token="your-token"
    )
    
    # Upload all loads for Aalborg
    stats = await manager.bulk_upload_historical_meterdata(
        ven_id="Aalborg",
        chunk_size=50000,  # 50k points per chunk
        batch_size=5000    # 5k points per InfluxDB batch
    )
    
    print(f"Uploaded {stats['total_points_uploaded']:,} points")
    await manager.cleanup()

asyncio.run(upload_ven_data())
```

### Example 3: Upload Multiple VENs

```python
async def upload_all_vens():
    from resource_db import ResourceDatabase
    
    manager = VENManager(
        vtn_base_url="http://localhost:8000",
        bearer_token="your-token"
    )
    
    db = ResourceDatabase("./config/resources.db")
    vens = db.get_ven_list()
    
    for ven_id in vens[:5]:  # First 5 VENs
        print(f"Uploading data for VEN: {ven_id}")
        
        await manager.register_load_ven(ven_id)
        stats = await manager.bulk_upload_historical_meterdata(ven_id)
        
        print(f"  ✓ {stats['successful']}/{stats['total_loads']} loads uploaded")
    
    await manager.cleanup()

asyncio.run(upload_all_vens())
```

### Example 4: Called from main.py

```python
# In main.py
for ven_id in vens_to_process:
    await manager.register_load_ven(ven_id)
    await manager.register_resources(ven_id)  # Register loads first
    await manager.bulk_upload_historical_meterdata(ven_id)  # Then upload data
```

## Performance

### Expected Throughput

Based on VTN bulk upload endpoint benchmarks:

| Data Points | Upload Time | Throughput |
|-------------|-------------|------------|
| 10,000 | ~2-3s | 3,000-5,000 pts/sec |
| 50,000 | ~10-15s | 3,000-5,000 pts/sec |
| 100,000 | ~20-30s | 3,000-5,000 pts/sec |

### For Our Dataset

- **Per load**: ~8,700 data points
- **Per VEN (avg)**: ~46 loads × 8,700 = ~400,000 points
- **Upload time per VEN**: ~2-3 minutes
- **All 287 VENs**: ~8-14 hours for complete upload

### Optimization Tips

1. **Adjust chunk_size** based on network speed:
   - Fast network: 50,000 points
   - Medium network: 20,000 points
   - Slow network: 10,000 points

2. **Adjust batch_size** for InfluxDB:
   - Default: 5,000 (good balance)
   - High performance: 10,000
   - Low memory: 2,000

3. **Upload VENs in parallel** (if VTN can handle it):
   ```python
   from concurrent.futures import ThreadPoolExecutor
   
   with ThreadPoolExecutor(max_workers=3) as executor:
       futures = [executor.submit(upload_ven, ven_id) for ven_id in vens[:10]]
       for future in futures:
           future.result()
   ```

## Error Handling

### Common Issues

**1. Load not registered with VTN**
```
No loads with VTN resource IDs found
```
**Solution:** Register loads first using `register_loads_parallel()`

**2. H5 meter not found**
```
H5 meter 'meter_xxxxx' not found
```
**Solution:** Verify H5 file contains the referenced meter

**3. Timeout on large chunks**
```
Timeout after 300 seconds
```
**Solution:** Reduce chunk_size or increase timeout

**4. VTN server error**
```
Failed to upload chunk: 500 - Internal Server Error
```
**Solution:** Check VTN server logs, verify resource_id exists

## Monitoring Progress

The function logs progress for each load:

```
[1/276] Uploading Ljt Holiday Inn - Base Load
  Loaded 8739 data points from H5 file
  Uploading chunk 1: 8739 points...
  ✓ Uploaded 8739/8739 points (4200 pts/sec)
  ✓ Complete: 8739 points uploaded

[2/276] Uploading Ljt Holiday Inn - Water Heater
  ...
```

## Data Quality

### Checks Performed

1. ✅ **Meter exists** in H5 file
2. ✅ **Load component exists** in meter
3. ✅ **Power dataset exists** in load component
4. ✅ **Data is readable** from H5

### Quality Codes

All uploaded data uses `quality_code: "GOOD"` by default. To customize:

```python
# Modify the data_points list creation
data_points.append({
    "interval_start": timestamp.isoformat() + "Z",
    "interval_end": interval_end.isoformat() + "Z",
    "value": float(row['power_w']),
    "quality_code": "ESTIMATED" if row['power_w'] == 0 else "GOOD"
})
```

## Testing Strategy

### Phase 1: Test with Sample Data (DONE)
```bash
python3 test_meter_data_loading.py --limit 10
```
✅ Verified data loads correctly from H5 file

### Phase 2: Test Upload with 3 Loads
```bash
python3 test_bulk_upload.py --token YOUR_TOKEN --limit 3
```

### Phase 3: Test One Complete VEN
```bash
python3 test_bulk_upload.py --token YOUR_TOKEN --ven Aalborg
```

### Phase 4: Production Upload
```bash
# From main.py or custom script
# Upload all VENs
```

## Troubleshooting

### Issue: No loads uploaded

**Check:**
1. Are loads registered with VTN? (vtn_resource_id not NULL)
2. Does VEN exist in manager.vens?
3. Is bearer token valid?

**Debug:**
```python
# Check registered loads
db = ResourceDatabase("./config/resources.db")
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM loads 
        WHERE vtn_resource_id IS NOT NULL
    """)
    print(f"Registered loads: {cursor.fetchone()[0]}")
```

### Issue: Slow upload speed

**Check:**
1. Network latency to VTN server
2. VTN server InfluxDB performance
3. Chunk size too small/large

**Solutions:**
- Increase chunk_size for faster networks
- Increase batch_size if VTN allows
- Run during off-peak hours

### Issue: Partial uploads

**Check:**
1. VTN server timeout settings
2. Network stability
3. Data format errors

**Solutions:**
- Retry failed loads
- Reduce chunk_size
- Add retry logic for failed chunks

## Next Steps

1. ✅ **Test data loading** - Verified with test_meter_data_loading.py
2. ⏭️ **Test bulk upload** - Run test_bulk_upload.py with 3 loads
3. ⏭️ **Upload one VEN** - Test complete upload for one VEN
4. ⏭️ **Production upload** - Upload all VENs

## Summary

✅ **Implementation complete**
- Function: `bulk_upload_historical_meterdata()`
- Test script: `test_bulk_upload.py`
- Data loading verified
- OAuth token integration complete
- Ready for VTN integration testing

**Command to test (no token needed - uses OAuth from .env):**
```bash
python3 test_bulk_upload.py --limit 3
```

This will:
1. Read OAuth credentials from `.env` file
2. Obtain bearer token automatically
3. Upload historical data for 3 loads
4. Verify the complete pipeline works!
