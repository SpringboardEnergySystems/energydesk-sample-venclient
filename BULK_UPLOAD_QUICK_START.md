# Quick Start: Bulk Upload Testing

## Prerequisites

Ensure your `.env` file has these settings:

```env
VTN_SERVER_ADDRESS=http://127.0.0.1:8444/openadr3
OAUTH_CLIENT_ID=your-client-id
OAUTH_CLIENT_SECRET=your-client-secret
OAUTHCHECK_ACCESS_TOKEN_OBTAIN_URL=http://127.0.0.1:8001/o/token/
```

## Test Commands

### 1. Test Data Loading (No VTN connection needed)
```bash
python3 test_meter_data_loading.py --limit 3
```
Shows how data is loaded from H5 file.

### 2. Test Bulk Upload with 3 Loads
```bash
python3 test_bulk_upload.py --limit 3
```
Uploads 3 loads to VTN to verify the pipeline works.

### 3. Test Full VEN Upload
```bash
python3 test_bulk_upload.py --ven Aalborg
```
Uploads all loads for one VEN (e.g., Aalborg).

### 4. Production Upload (All VENs)
```bash
python3 main.py
```
Runs full system - registers and uploads all VENs.

## What Happens

The test script will:
1. ✅ Read `.env` configuration
2. ✅ Obtain OAuth token automatically
3. ✅ Query loads from SQLite database
4. ✅ Load meter data from H5 file
5. ✅ Format data for VTN bulk API
6. ✅ Upload to VTN in chunks
7. ✅ Show statistics and throughput

## Expected Output

```
================================================================================
BULK UPLOAD TEST
================================================================================
VTN URL: http://127.0.0.1:8444/openadr3
Testing with: 3 loads
================================================================================
Obtaining OAuth token from .env configuration...
✓ Successfully obtained OAuth token
Using VTN URL: http://127.0.0.1:8444/openadr3
Using token: eyJhbGciOiJIUzI1NiIs...

Starting bulk upload for VEN 'Aabenraa'...
--------------------------------------------------------------------------------
[1/3] Uploading Ljt Holiday Inn - Base Load
  Loaded 8739 data points from H5 file
  Uploading chunk 1: 8739 points...
  ✓ Uploaded 8739/8739 points (4200 pts/sec)
  ✓ Complete: 8739 points uploaded

[2/3] Uploading Ljt Holiday Inn - Water Heater
  ...

================================================================================
UPLOAD RESULTS
================================================================================
VEN: Aabenraa
Total loads processed: 3
Successful uploads: 3
Failed uploads: 0
Total data points uploaded: 26,217

✅ Test successful! 3/3 loads uploaded
================================================================================
```

## Troubleshooting

### Error: "No bearer token provided"
**Cause:** OAuth credentials not in `.env` file
**Fix:** Add OAuth settings to `.env` file

### Error: "No loads with VTN resource IDs found"
**Cause:** Loads not registered with VTN yet
**Fix:** Run `main.py` first to register loads

### Error: "H5 meter not found"
**Cause:** H5 file missing or incorrect path
**Fix:** Verify `config/examplemeterdata/load_data.h5` exists

### Error: "Connection refused"
**Cause:** VTN server not running
**Fix:** Start your VTN server first

## Manual Token Override

If you want to use a specific token instead of OAuth:

```bash
python3 test_bulk_upload.py --token YOUR_TOKEN_HERE --limit 3
```

## Options

```bash
python3 test_bulk_upload.py --help
```

Options:
- `--vtn-url URL` - Override VTN server URL
- `--token TOKEN` - Provide token directly (skips OAuth)
- `--ven VEN_ID` - Specific VEN to upload (default: first VEN)
- `--limit N` - Limit number of loads (default: 3)

---

**Ready to test?** Just run:
```bash
python3 test_bulk_upload.py --limit 3
```
