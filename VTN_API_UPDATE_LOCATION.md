# VTN API Update: Longitude/Latitude in service_location

## Date: January 17, 2026

## Overview
The VTN API has been updated to require longitude and latitude values to be included in the `service_location` object rather than as separate attributes.

## API Documentation
See: http://localhost:8444/openadr3/docs#/default/create_resource_resources_post

---

## Changes Required

### Before (Old API)
```json
{
  "id": "2d62f4c5-b2ed-4e32-a484-ba92fd55cdd3",
  "resource_name": "The kindergarten - Base Load",
  "resource_type": "DSR",
  "ven_name": "Aabybro",
  "external_resource_id": "1bd5ca77-c963-45be-a0ee-c8dafaa51f08_load_0",
  "service_location": {
    "meter_point_id": "707057500504404881"
  },
  "attributes": [
    {
      "attribute_type": "longitude",
      "attribute_name": "longitude",
      "attribute_values": ["9.736535"]
    },
    {
      "attribute_type": "latitude",
      "attribute_name": "latitude",
      "attribute_values": ["57.158158"]
    }
  ]
}
```

### After (New API)
```json
{
  "id": "2d62f4c5-b2ed-4e32-a484-ba92fd55cdd3",
  "resource_name": "The kindergarten - Base Load",
  "resource_type": "DSR",
  "ven_name": "Aabybro",
  "external_resource_id": "1bd5ca77-c963-45be-a0ee-c8dafaa51f08_load_0",
  "service_location": {
    "meter_point_id": "707057500504404881",
    "longitude": 9.736535,
    "latitude": 57.158158
  },
  "attributes": [
    // longitude and latitude removed from here
  ]
}
```

---

## Code Changes

### 1. Updated `register_ven_resource()` Method Signature

**File:** `venclient/client.py`

**Before:**
```python
async def register_ven_resource(
    self, 
    resource_config: VENResource,
    external_resource_id: str = None,
    service_location: str = None  # ❌ Was a string
) -> Optional[str]:
```

**After:**
```python
async def register_ven_resource(
    self, 
    resource_config: VENResource,
    external_resource_id: str = None,
    service_location: dict = None  # ✅ Now a dict
) -> Optional[str]:
```

### 2. Updated `register_loads_parallel()` Method

**Changes:**
1. Extract longitude and latitude from location JSON
2. Remove longitude/latitude from attributes
3. Build service_location dict with all location data

**Before:**
```python
# Parse JSON fields
capacities = json.loads(capacities_json)
location = json.loads(location_json)

# Build attributes from resource data
attributes = []

# Add location (included longitude/latitude)
if location:
    for k, v in location.items():
        attributes.append({
            'attribute_type': camel_to_snake(k),
            'attribute_name': k,
            'attribute_values': [str(v)]
        })

# Service location was just meter_point_id
registration_data.append({
    'service_location': meter_point_id
})
```

**After:**
```python
# Parse JSON fields
capacities = json.loads(capacities_json)
location = json.loads(location_json)

# Extract longitude and latitude for service_location
longitude = location.get('longitude') if location else None
latitude = location.get('latitude') if location else None

# Build attributes (WITHOUT longitude/latitude)
attributes = []

# NOTE: longitude and latitude are now in service_location, not attributes

# Build service_location with meter_point_id, longitude, and latitude
service_location_dict = {
    "meter_point_id": meter_point_id
}
if longitude is not None:
    service_location_dict["longitude"] = float(longitude)
if latitude is not None:
    service_location_dict["latitude"] = float(latitude)

registration_data.append({
    'service_location': service_location_dict
})
```

---

## Key Differences

### 1. Data Type Change
- **Before:** longitude/latitude were strings in attributes
- **After:** longitude/latitude are floats in service_location

### 2. Location Change
- **Before:** longitude/latitude in attributes array
- **After:** longitude/latitude in service_location object

### 3. Structure Change
```python
# Before
attributes = [
    {"attribute_type": "longitude", "attribute_values": ["9.736535"]}  # String
]

# After
service_location = {
    "longitude": 9.736535  # Float
}
```

---

## Files Modified

1. ✅ **venclient/client.py**
   - Line ~133: Changed `service_location` parameter from `str` to `dict`
   - Line ~690: Extract longitude/latitude from location JSON
   - Line ~705: Remove location loop that added to attributes
   - Line ~740: Build service_location_dict with meter_point_id, longitude, latitude

2. ✅ **verify_fix.py**
   - Updated verification to check for new format

---

## Testing

### Run Verification Script
```bash
python3 verify_fix.py
```

Expected output:
```
✅ Fix is in place: service_location includes meter_point_id
✅ Fix is in place: longitude/latitude in service_location (not attributes)
✅ No premature return found - simulator will initialize
```

### Test Format
```bash
python3 test_location_update.py
```

This shows the before/after format comparison.

### Run Registration
```bash
python3 main.py
```

Expected:
- ✅ No validation errors
- ✅ Resources register successfully
- ✅ VTN returns 201 Created

---

## VTN Server Expected Response

With the correct format, VTN should accept registrations:

```
INFO: 127.0.0.1:51901 - "POST /openadr3/resources HTTP/1.1" 201 Created
```

Response body example:
```json
{
  "id": "vtn-assigned-uuid-here",
  "resource_name": "The kindergarten - Base Load",
  "service_location": {
    "meter_point_id": "707057500504404881",
    "longitude": 9.736535,
    "latitude": 57.158158
  }
}
```

---

## Database Impact

No database schema changes required. The loads table already has all necessary fields:
- `load_id` - Used as resource ID
- `resource_id` - Parent resource (contains location in JSON)
- `vtn_resource_id` - Updated after successful registration

The location data is already stored in the resources table as JSON:
```python
location = {"longitude": 9.736535, "latitude": 57.158158}
```

We simply extract these values and format them correctly for the VTN API.

---

## Backwards Compatibility

This is a **breaking change** in the VTN API. The old format will no longer work.

If you need to support both old and new API versions, you would need:
```python
# Detect API version
if api_version >= "3.1":
    # New format: longitude/latitude in service_location
    service_location = {
        "meter_point_id": meter_point_id,
        "longitude": longitude,
        "latitude": latitude
    }
else:
    # Old format: longitude/latitude in attributes
    service_location = {"meter_point_id": meter_point_id}
    attributes.append(longitude_attribute)
    attributes.append(latitude_attribute)
```

However, since your VTN has been updated, we only support the new format.

---

## Summary

✅ **Changes Complete:**
1. longitude/latitude moved from attributes to service_location
2. Values converted from strings to floats
3. service_location now properly structured with all location data
4. Code tested and verified

✅ **Ready to Use:**
- Run `python3 main.py` to register resources
- All loads will register with correct format
- VTN will accept registrations without validation errors

🎯 **Result:** Your VEN client now matches the updated VTN API specification!
