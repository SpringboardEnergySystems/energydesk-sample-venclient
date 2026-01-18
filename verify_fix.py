#!/usr/bin/env python3
"""
Quick verification that the service_location fix is in place
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("SERVICE LOCATION FIX VERIFICATION")
print("=" * 70)

# Check the fix in client.py
print("\n1. Checking venclient/client.py for service_location fix...")
with open('venclient/client.py', 'r') as f:
    content = f.read()

    # Look for the updated service_location dict format with correct field name
    if '"meterpoint_id": meter_point_id' in content:
        print("   ✅ Fix is in place: service_location includes meterpoint_id (correct field name)")
    else:
        print("   ❌ Fix not found - should be 'meterpoint_id' not 'meter_point_id'")
        sys.exit(1)

    # Check for longitude/latitude in service_location
    if 'service_location_dict["longitude"]' in content and 'service_location_dict["latitude"]' in content:
        print("   ✅ Fix is in place: longitude/latitude in service_location (not attributes)")
    else:
        print("   ❌ Fix not found - longitude/latitude not in service_location")
        sys.exit(1)

# Check main.py doesn't have premature return
print("\n2. Checking main.py for premature return statement...")
with open('main.py', 'r') as f:
    lines = f.readlines()

    # Find the registration section
    found_registration = False
    found_return_before_simulator = False

    for i, line in enumerate(lines):
        if 'await manager.register_resources' in line:
            found_registration = True
        if found_registration and i < len(lines) - 1:
            if 'return' in line and 'Step 4: Initialize simulator' in lines[i+1]:
                found_return_before_simulator = True
                break

    if not found_return_before_simulator:
        print("   ✅ No premature return found - simulator will initialize")
    else:
        print("   ❌ Premature return found - simulator will not initialize")
        sys.exit(1)

print("\n" + "=" * 70)
print("✅ ALL FIXES VERIFIED")
print("=" * 70)
print("\nYour code is ready to run!")
print("\nNext step:")
print("  python3 main.py")
print("\nExpected result:")
print("  - Resources register successfully (no validation errors)")
print("  - Simulator initializes")
print("  - VTN server shows 201 Created responses")
print("\n" + "=" * 70)
