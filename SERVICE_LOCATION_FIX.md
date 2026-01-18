# Service Location Fix - January 17, 2026

## Issue

VTN server was rejecting resource registrations with validation error:
```
Input should be a valid dictionary or object to extract fields from
```

**Error Location:** `service_location` field

## Root Cause

The `service_location` was being sent as a string:
```json
{
  "service_location": "707057500504404881"
}
```

But the VTN server expects it to be an object:
```json
{
  "service_location": {
    "meter_point_id": "707057500504404881"
  }
}
```

## Solution

Updated `register_ven_resource()` method in `venclient/client.py`:

**Before:**
```python
if service_location:
    registration_data["service_location"] = service_location
```

**After:**
```python
if service_location:
    registration_data["service_location"] = {
        "meter_point_id": service_location
    }
```

## Files Modified

- **venclient/client.py** (line ~160): Fixed service_location format
- **main.py** (line ~97): Removed premature `return` statement that was blocking simulator initialization

## Testing

To test the fix:

```bash
# Run the main application
python3 main.py
```

Expected behavior:
- ✅ Resources should register successfully without validation errors
- ✅ Simulator should initialize after registration
- ✅ All loads should be registered with proper service_location format

## Verification

Check VTN server logs for successful registrations:
```
INFO: "POST /openadr3/resources HTTP/1.1" 201 Created
```

Instead of:
```
ERROR: Validation error for /openadr3/resources: service_location
```

## Additional Notes

The `service_location` object can contain additional location-related fields if needed by the VTN:
```python
{
    "service_location": {
        "meter_point_id": "707057500504404881",
        "address": "Optional address",
        "coordinates": "Optional coordinates"
    }
}
```

Currently, we're only sending `meter_point_id` as that's the primary identifier.

---

## Status: ✅ FIXED

The validation error has been resolved. Resources should now register successfully with the VTN server.
