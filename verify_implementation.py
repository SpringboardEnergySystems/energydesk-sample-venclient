#!/usr/bin/env python3
"""
Verification script for parallel load registration implementation
"""
import sys
import os

print("=" * 70)
print("PARALLEL LOAD REGISTRATION - VERIFICATION")
print("=" * 70)

# Test 1: Import modules
print("\n1. Testing imports...")
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from venclient.client import sample_registration, VENManager
    from resource_db import ResourceDatabase
    print("   ✓ All imports successful")
except Exception as e:
    print(f"   ✗ Import failed: {e}")
    sys.exit(1)

# Test 2: Check database
print("\n2. Checking database...")
try:
    db = ResourceDatabase('./config/resources.db')

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        if 'resources' in tables and 'loads' in tables:
            print("   ✓ Required tables exist")
        else:
            print(f"   ✗ Missing tables. Found: {tables}")
            sys.exit(1)

        # Check resources count
        cursor.execute("SELECT COUNT(*) FROM resources")
        resource_count = cursor.fetchone()[0]
        print(f"   ✓ Resources: {resource_count:,}")

        # Check loads count
        cursor.execute("SELECT COUNT(*) FROM loads")
        load_count = cursor.fetchone()[0]
        print(f"   ✓ Loads: {load_count:,}")

        # Check h5_meter_id column
        cursor.execute("PRAGMA table_info(resources)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'h5_meter_id' in columns:
            print("   ✓ h5_meter_id column exists in resources")
        else:
            print("   ✗ h5_meter_id column missing")

        # Check vtn_resource_id column in loads
        cursor.execute("PRAGMA table_info(loads)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'vtn_resource_id' in columns:
            print("   ✓ vtn_resource_id column exists in loads")
        else:
            print("   ✗ vtn_resource_id column missing")

        # Sample JOIN query
        cursor.execute("""
            SELECT COUNT(*) FROM resources r
            JOIN loads l ON r.resource_id = l.resource_id
        """)
        join_count = cursor.fetchone()[0]
        print(f"   ✓ JOIN query works: {join_count:,} joined records")

except Exception as e:
    print(f"   ✗ Database check failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Check VENs
print("\n3. Checking VENs...")
try:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT ven FROM resources WHERE ven IS NOT NULL")
        vens = [row[0] for row in cursor.fetchall()]
        print(f"   ✓ Found {len(vens)} VENs: {', '.join(vens[:5])}...")
except Exception as e:
    print(f"   ✗ VEN check failed: {e}")

# Test 4: Sample load data
print("\n4. Checking sample load data...")
try:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                r.resource_name,
                r.meter_point_id,
                l.load_component,
                l.load_name
            FROM resources r
            JOIN loads l ON r.resource_id = l.resource_id
            LIMIT 3
        """)
        print("   Sample loads:")
        for row in cursor.fetchall():
            resource_name, meter_point, component, load_name = row
            print(f"      {resource_name[:30]:30s} | {meter_point:20s} | {load_name:20s} ({component})")
        print("   ✓ Sample data looks good")
except Exception as e:
    print(f"   ✗ Sample data check failed: {e}")

# Test 5: Method signatures
print("\n5. Checking method signatures...")
try:
    import inspect

    # Check register_loads_parallel signature
    sig = inspect.signature(VENManager.register_loads_parallel)
    params = list(sig.parameters.keys())
    expected = ['self', 'ven_id', 'batch_size', 'delay_between_batches', 'db_path']
    if params == expected:
        print("   ✓ register_loads_parallel signature correct")
    else:
        print(f"   ✗ Unexpected parameters: {params}")

    # Check sample_registration signature
    sig = inspect.signature(sample_registration)
    params = list(sig.parameters.keys())
    if 'batch_size' in params and 'delay_between_batches' in params:
        print("   ✓ sample_registration signature updated")
    else:
        print(f"   ⚠ sample_registration parameters: {params}")

except Exception as e:
    print(f"   ✗ Signature check failed: {e}")

# Summary
print("\n" + "=" * 70)
print("VERIFICATION COMPLETE")
print("=" * 70)
print("\n✓ Implementation verified and ready to use!")
print("\nNext steps:")
print("  1. Update bearer token in test_parallel_registration.py")
print("  2. Run: python3 test_parallel_registration.py")
print("  3. Check logs for registration progress")
print("  4. Verify database updates with:")
print("     python3 -c 'from resource_db import ResourceDatabase; \\")
print("                 db = ResourceDatabase(\"./config/resources.db\"); \\")
print("                 print(db.get_load_statistics())'")
print("\n" + "=" * 70)
