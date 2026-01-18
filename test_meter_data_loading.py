#!/usr/bin/env python3
"""
Test function to load and display meter data from H5 files based on loads in SQLite database.
This will help verify the data structure before uploading to VTN.
"""
import h5py
import os
import pandas as pd
from datetime import datetime
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from resource_db import ResourceDatabase


def test_load_meter_data_for_resources(ven_id: str = None, limit: int = 10,
                                       db_path: str = "./config/resources.db",
                                       h5_file_path: str = "./config/examplemeterdata/load_data.h5"):
    """
    Test function to load meter data from H5 file for the first N loads.

    Args:
        ven_id: VEN identifier (city name). If None, uses first VEN in database.
        limit: Number of loads to test (default: 10)
        db_path: Path to SQLite database
        h5_file_path: Path to H5 file with meter data
    """
    print("=" * 80)
    print("METER DATA LOADING TEST")
    print("=" * 80)

    # Initialize database
    db = ResourceDatabase(db_path=db_path)

    # Get VEN if not specified
    if not ven_id:
        vens = db.get_ven_list()
        if not vens:
            print("❌ No VENs found in database")
            return
        ven_id = vens[0]
        print(f"Using first VEN: {ven_id}")

    print(f"\nVEN: {ven_id}")
    print(f"Database: {db_path}")
    print(f"H5 File: {h5_file_path}")
    print(f"Loading first {limit} loads...")
    print("=" * 80)

    # Query loads from database
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                r.resource_id,
                r.resource_name,
                r.meter_point_id,
                l.load_id,
                l.load_component,
                l.load_name,
                l.h5_meter_id,
                l.vtn_resource_id
            FROM resources r
            JOIN loads l ON r.resource_id = l.resource_id
            WHERE r.ven = ?
            ORDER BY r.resource_id, l.load_component
            LIMIT ?
        """, (ven_id, limit))

        load_records = cursor.fetchall()

    if not load_records:
        print(f"❌ No loads found for VEN '{ven_id}'")
        return

    print(f"\n✓ Found {len(load_records)} loads to test\n")

    # Open H5 file
    with h5py.File(h5_file_path, 'r') as hf:
        meters_group = hf['meters']

        # Process each load
        for idx, record in enumerate(load_records, 1):
            (resource_id, resource_name, meter_point_id, load_id,
             load_component, load_name, h5_meter_id, vtn_resource_id) = record

            print(f"\n{'='*80}")
            print(f"LOAD {idx}/{len(load_records)}")
            print(f"{'='*80}")
            print(f"Resource: {resource_name}")
            print(f"Load: {load_name} ({load_component})")
            print(f"Meter Point ID: {meter_point_id}")
            print(f"H5 Meter ID: {h5_meter_id}")
            print(f"VTN Resource ID: {vtn_resource_id or 'Not registered yet'}")
            print(f"{'-'*80}")

            # Check if meter exists in H5 file
            if h5_meter_id not in meters_group:
                print(f"❌ ERROR: H5 meter '{h5_meter_id}' not found in H5 file")
                continue

            # Get the meter from H5
            meter = meters_group[h5_meter_id]

            # Check if load component exists
            if load_component not in meter:
                print(f"❌ ERROR: Load component '{load_component}' not found in meter '{h5_meter_id}'")
                print(f"   Available components: {list(meter.keys())}")
                continue

            # Get the load data
            load_group = meter[load_component]

            # Check if 'power' dataset exists
            if 'power' not in load_group:
                print(f"❌ ERROR: 'power' dataset not found in {load_component}")
                print(f"   Available datasets: {list(load_group.keys())}")
                continue

            # Load power data
            power_data = load_group['power'][:]

            # Create DataFrame
            df = pd.DataFrame(power_data, columns=['timestamp', 'power_w'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df['datetime'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')

            print(f"\n✓ Successfully loaded {len(df)} data points")
            print(f"\nTime Range:")
            print(f"  Start: {df['datetime'].iloc[0]}")
            print(f"  End:   {df['datetime'].iloc[-1]}")
            print(f"\nPower Statistics:")
            print(f"  Min:    {df['power_w'].min():.2f} W")
            print(f"  Max:    {df['power_w'].max():.2f} W")
            print(f"  Mean:   {df['power_w'].mean():.2f} W")
            print(f"  Median: {df['power_w'].median():.2f} W")

            print(f"\nFirst 5 data points:")
            print(df[['datetime', 'power_w']].head().to_string(index=False))

            print(f"\nLast 5 data points:")
            print(df[['datetime', 'power_w']].tail().to_string(index=False))

            # Check for data quality issues
            null_count = df['power_w'].isnull().sum()
            zero_count = (df['power_w'] == 0).sum()
            negative_count = (df['power_w'] < 0).sum()

            if null_count > 0 or negative_count > 0:
                print(f"\n⚠️  Data Quality Issues:")
                if null_count > 0:
                    print(f"  - {null_count} null values")
                if negative_count > 0:
                    print(f"  - {negative_count} negative values")

            if zero_count > 0:
                print(f"\nℹ️  {zero_count} zero values ({zero_count/len(df)*100:.1f}%)")

    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print(f"\n✓ Successfully loaded and displayed meter data for {len(load_records)} loads")
    print("\nNext steps:")
    print("  1. Verify the data looks correct")
    print("  2. Check time ranges and power values")
    print("  3. If everything looks good, proceed with bulk upload to VTN")
    print("=" * 80)


def test_h5_structure():
    """Quick test to show H5 file structure"""
    h5_file_path = "./config/examplemeterdata/load_data.h5"

    print("=" * 80)
    print("H5 FILE STRUCTURE")
    print("=" * 80)

    with h5py.File(h5_file_path, 'r') as hf:
        meters_group = hf['meters']
        meter_list = list(meters_group.keys())

        print(f"\nTotal meters in H5 file: {len(meter_list)}")
        print(f"First 5 meters: {meter_list[:5]}")

        # Show structure of first meter
        first_meter = meters_group[meter_list[0]]
        print(f"\nStructure of meter '{meter_list[0]}':")
        print(f"  Attributes: {dict(first_meter.attrs)}")
        print(f"  Load components: {list(first_meter.keys())}")

        # Show structure of first load component
        first_load = first_meter['load_0']
        print(f"\nStructure of 'load_0':")
        print(f"  Datasets: {list(first_load.keys())}")

        power_data = first_load['power']
        print(f"\n'power' dataset:")
        print(f"  Shape: {power_data.shape}")
        print(f"  Dtype: {power_data.dtype}")
        print(f"  First 3 rows: {power_data[:3]}")

    print("=" * 80)


if __name__ == "__main__":
    import argparse
    import environ

    # Show .env configuration
    try:
        env = environ.Env()
        environ.Env.read_env()
        vtn_url = env('VTN_SERVER_ADDRESS', default='Not set')
        token = env('ENERGYDESK_TOKEN', default='Not set')

        print("=" * 80)
        print("CONFIGURATION FROM .env FILE")
        print("=" * 80)
        print(f"VTN_SERVER_ADDRESS: {vtn_url}")
        print(f"ENERGYDESK_TOKEN: {'Set (' + token[:20] + '...)' if token != 'Not set' else 'Not set'}")
        print("=" * 80)
        print()
    except:
        pass

    parser = argparse.ArgumentParser(description='Test meter data loading from H5 file')
    parser.add_argument('--ven', type=str, help='VEN identifier (default: first VEN)')
    parser.add_argument('--limit', type=int, default=10, help='Number of loads to test (default: 10)')
    parser.add_argument('--structure', action='store_true', help='Show H5 file structure only')

    args = parser.parse_args()

    if args.structure:
        test_h5_structure()
    else:
        test_load_meter_data_for_resources(ven_id=args.ven, limit=args.limit)
