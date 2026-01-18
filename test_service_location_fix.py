#!/usr/bin/env python3
"""
Quick test of the service_location fix
"""
import json

# Old format (caused error)
old_format = {
    "service_location": "707057500504404881"
}

# New format (should work)
new_format = {
    "service_location": {
        "meter_point_id": "707057500504404881"
    }
}

print("=" * 70)
print("SERVICE LOCATION FORMAT FIX")
print("=" * 70)

print("\n❌ Old format (caused validation error):")
print(json.dumps(old_format, indent=2))

print("\n✅ New format (should work):")
print(json.dumps(new_format, indent=2))

print("\n" + "=" * 70)
print("The service_location is now properly formatted as an object")
print("with a meter_point_id field, as expected by the VTN server.")
print("=" * 70)
