#!/usr/bin/env python3
"""Quick test to verify database and run load generation"""
import sys
import os
sys.path.insert(0, '/Users/steinar/PycharmProjects/energydesk-sample-venclient')

# Test 1: Check database
print("=" * 60)
print("TEST 1: Checking database status...")
print("=" * 60)

import sqlite3
conn = sqlite3.connect('/Users/steinar/PycharmProjects/energydesk-sample-venclient/config/resources.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print(f"Tables: {tables}")

cursor.execute('SELECT COUNT(*) FROM resources')
resource_count = cursor.fetchone()[0]
print(f"Resources: {resource_count}")

cursor.execute("PRAGMA table_info(resources)")
columns = [row[1] for row in cursor.fetchall()]
print(f"Has h5_meter_id column: {'h5_meter_id' in columns}")

if 'loads' in tables:
    cursor.execute('SELECT COUNT(*) FROM loads')
    load_count = cursor.fetchone()[0]
    print(f"Loads: {load_count}")
else:
    print("Loads table doesn't exist yet")

conn.close()

# Test 2: Check H5 file
print("\n" + "=" * 60)
print("TEST 2: Checking H5 file...")
print("=" * 60)

import h5py
h5_path = '/Users/steinar/PycharmProjects/energydesk-sample-venclient/config/examplemeterdata/load_data.h5'
with h5py.File(h5_path, 'r') as hf:
    meters = list(hf['meters'].keys())
    print(f"H5 meters available: {len(meters)}")
    first_meter = hf['meters'][meters[0]]
    loads = [k for k in first_meter.keys() if k.startswith('load_')]
    print(f"Load components per meter: {len(loads)}")

# Test 3: Run load generation if not already done
print("\n" + "=" * 60)
print("TEST 3: Running load generation...")
print("=" * 60)

if 'loads' not in tables or load_count == 0:
    print("Running load generation...")
    from prepare_load_samples import generate_resource_loads
    generate_resource_loads()
else:
    print(f"Loads already generated ({load_count} records)")

print("\n" + "=" * 60)
print("FINAL STATUS")
print("=" * 60)

conn = sqlite3.connect('/Users/steinar/PycharmProjects/energydesk-sample-venclient/config/resources.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM resources WHERE h5_meter_id IS NOT NULL')
print(f"Resources with H5 meter assigned: {cursor.fetchone()[0]}")
cursor.execute('SELECT COUNT(*) FROM loads')
print(f"Total loads: {cursor.fetchone()[0]}")
conn.close()

print("\nDONE!")
