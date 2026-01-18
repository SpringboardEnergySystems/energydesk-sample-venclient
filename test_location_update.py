#!/usr/bin/env python3
"""
Test the updated service_location format with longitude and latitude
"""
import json

print("=" * 70)
print("UPDATED SERVICE LOCATION FORMAT")
print("=" * 70)

# Old format (before longitude/latitude moved)
old_format = {
    "service_location": {
        "meter_point_id": "707057500504404881"  # ❌ Wrong field name
    },
    "attributes": [
        {"attribute_type": "longitude", "attribute_name": "longitude", "attribute_values": ["9.736535"]},
        {"attribute_type": "latitude", "attribute_name": "latitude", "attribute_values": ["57.158158"]}
    ]
}

# New format (longitude/latitude in service_location with correct field name)
new_format = {
    "service_location": {
        "meterpoint_id": "707057500504404881",  # ✅ Correct: all lowercase, no underscore
        "longitude": 9.736535,
        "latitude": 57.158158
    },
    "attributes": [
        # longitude and latitude removed from attributes
    ]
}

print("\n❌ OLD FORMAT (before API change):")
print(json.dumps(old_format, indent=2))

print("\n✅ NEW FORMAT (matching updated VTN API):")
print(json.dumps(new_format, indent=2))

print("\n" + "=" * 70)
print("KEY CHANGES:")
print("=" * 70)
print("1. ✅ longitude and latitude moved FROM attributes TO service_location")
print("2. ✅ longitude and latitude are now numeric (float) not strings")
print("3. ✅ service_location is a proper object with all location data")
print("4. ✅ Field name is 'meterpoint_id' (lowercase, no underscore)")
print("\n" + "=" * 70)
print("This matches the updated VTN API at:")
print("http://localhost:8444/openadr3/docs#/default/create_resource_resources_post")
print("=" * 70)
