# Field Name Fix: meterpoint_id (not meter_point_id)

## Date: January 17, 2026 - 20:15

## Issue
VTN server was rejecting registrations with validation error:
```
Field required: ('body', 'service_location', 'meterpoint_id')
Input: {'meter_point_id': '707057500504404881', ...}
```

## Root Cause
We were using `meter_point_id` (with underscore) but the VTN API expects `meterpoint_id` (all lowercase, no underscore).

## Fix Applied

**File:** `venclient/client.py` (line ~740)

**Before:**
```python
service_location_dict = {
    "meter_point_id": meter_point_id  # ❌ Wrong field name
}
```

**After:**
```python
service_location_dict = {
    "meterpoint_id": meter_point_id  # ✅ Correct field name
}
```

## Correct Format

```json
{
  "service_location": {
    "meterpoint_id": "707057500504404881",
    "longitude": 9.736535,
    "latitude": 57.158158
  }
}
```

## Key Points

1. ✅ Field name: `meterpoint_id` (all lowercase, no underscore)
2. ✅ Not: `meter_point_id`, `meterPoint_id`, or `MeterPointId`
3. ✅ Longitude and latitude as floats in service_location
4. ✅ All three fields in same object

## Verification

Run:
```bash
python3 verify_fix.py
```

Expected:
```
✅ Fix is in place: service_location includes meterpoint_id (correct field name)
✅ Fix is in place: longitude/latitude in service_location (not attributes)
```

## Status: ✅ FIXED

Your resources should now register successfully with the VTN server.

Run `python3 main.py` to test!
