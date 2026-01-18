# How to Upload Historical Data for All Loads

## Quick Commands

### Option 1: Upload ALL loads for ONE VEN
```bash
# Upload all loads for first VEN in database (no limit)
python3 test_bulk_upload.py

# Upload all loads for specific VEN
python3 test_bulk_upload.py --ven Aalborg
```

### Option 2: Upload ALL loads for ALL VENs
```bash
# Upload everything (all VENs, all loads)
python3 upload_all_historical_data.py
```

### Option 3: Test with Limited VENs First
```bash
# Upload all loads for first 5 VENs (testing)
python3 upload_all_historical_data.py --max-vens 5
```

## What Each Does

### test_bulk_upload.py

**Default behavior (no --limit):**
- Processes ONE VEN (first VEN or specified with --ven)
- Uploads ALL loads for that VEN
- Good for testing or processing one VEN at a time

**Examples:**
```bash
# All loads, first VEN
python3 test_bulk_upload.py

# All loads, specific VEN
python3 test_bulk_upload.py --ven Aabenraa

# Limited loads (testing)
python3 test_bulk_upload.py --limit 3
```

### upload_all_historical_data.py (NEW)

**Default behavior:**
- Processes ALL VENs in database
- Uploads ALL loads for each VEN
- Production use - complete upload

**Examples:**
```bash
# Upload everything
python3 upload_all_historical_data.py

# Test with first 5 VENs
python3 upload_all_historical_data.py --max-vens 5

# Custom chunk sizes
python3 upload_all_historical_data.py --chunk-size 100000 --batch-size 10000
```

## Performance Estimates

### Your Database
- **287 VENs** total
- **~46 loads per VEN** (average)
- **~8,700 points per load**
- **~116,412 total loads**
- **~1 billion total data points**

### Upload Time Estimates

**Per Load:**
- ~8,700 points @ 4,000 pts/sec = ~2-3 seconds

**Per VEN:**
- ~46 loads × 3 sec = ~2-3 minutes

**All VENs:**
- 287 VENs × 3 min = ~14-15 hours

**Faster with larger chunks:**
```bash
# Use larger chunks and batches
python3 upload_all_historical_data.py --chunk-size 100000 --batch-size 10000
# Estimated: ~8-10 hours
```

## Monitoring Progress

Both scripts show real-time progress:

```
[1/46] Uploading Hotel ABC - Base Load
  Loaded 8739 data points from H5 file
  Uploading chunk 1: 8739 points...
  ✓ Uploaded 8739/8739 points (4200 pts/sec)
  ✓ Complete: 8739 points uploaded

[2/46] Uploading Hotel ABC - Water Heater
  ...
```

## Final Summary

At the end, you'll see:

```
================================================================================
FINAL SUMMARY - ALL VENS
================================================================================
VENs processed: 287/287
VENs successful: 287
Total loads uploaded: 116,412
Total loads failed: 0
Total data points uploaded: 1,012,382,800

✅ SUCCESS! Uploaded data for 116,412 loads across 287 VENs
================================================================================
```

## Recommended Approach

### Phase 1: Test (DONE)
```bash
python3 test_bulk_upload.py --limit 3
```
✅ You confirmed this works!

### Phase 2: Test Full VEN
```bash
python3 test_bulk_upload.py --ven Aalborg
```
Upload all loads for one VEN to verify scale.

### Phase 3: Test Multiple VENs
```bash
python3 upload_all_historical_data.py --max-vens 5
```
Upload first 5 VENs to verify the loop works.

### Phase 4: Production Upload
```bash
python3 upload_all_historical_data.py
```
Upload everything - run overnight or in background.

## Running in Background

For long uploads, run in background:

```bash
# Run in background, save output to log
nohup python3 upload_all_historical_data.py > upload.log 2>&1 &

# Check progress
tail -f upload.log

# Check if still running
ps aux | grep upload_all_historical_data
```

## Stopping/Resuming

The scripts don't currently support resume. If interrupted:

1. Check VTN database to see what was uploaded
2. Re-run - existing data might cause errors or be skipped
3. Or filter out already-uploaded VENs manually

## Summary

**To upload ALL loads:**

| Command | What It Does |
|---------|--------------|
| `python3 test_bulk_upload.py` | All loads for 1 VEN (first or --ven) |
| `python3 test_bulk_upload.py --ven Aalborg` | All loads for Aalborg |
| `python3 upload_all_historical_data.py` | All loads for ALL VENs |
| `python3 upload_all_historical_data.py --max-vens 5` | All loads for first 5 VENs |

**Your next step:**
```bash
python3 test_bulk_upload.py --ven Aalborg
```
This will upload all loads for one VEN to verify it works at scale!
