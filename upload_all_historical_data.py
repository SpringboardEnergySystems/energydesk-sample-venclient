#!/usr/bin/env python3
"""
Upload historical meter data for ALL VENs and ALL loads.
This script processes all VENs in the database.
"""
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from venclient.client import VENManager
from resource_db import ResourceDatabase
from venclient.utils import get_access_token
import environ


async def upload_all_vens(vtn_url: str, bearer_token: str,
                         max_vens: int = None, chunk_size: int = 50000,
                         batch_size: int = 5000):
    """
    Upload historical data for all VENs and all their loads.

    Args:
        vtn_url: VTN server URL
        bearer_token: Authentication token
        max_vens: Optional limit on number of VENs to process (for testing)
        chunk_size: Points per upload chunk (default: 50000)
        batch_size: InfluxDB batch size (default: 5000)
    """
    print("=" * 80)
    print("BULK UPLOAD - ALL VENS AND ALL LOADS")
    print("=" * 80)
    print(f"VTN URL: {vtn_url}")
    print(f"Chunk size: {chunk_size}")
    print(f"Batch size: {batch_size}")
    if max_vens:
        print(f"Limiting to: {max_vens} VENs (testing mode)")
    print("=" * 80)

    # Initialize VEN manager
    manager = VENManager(vtn_base_url=vtn_url, bearer_token=bearer_token)

    # Get all VENs from database
    db = ResourceDatabase("./config/resources.db")
    all_vens = db.get_ven_list()

    if not all_vens:
        print("❌ No VENs found in database")
        return

    # Limit if requested
    vens_to_process = all_vens[:max_vens] if max_vens else all_vens

    print(f"\nFound {len(all_vens)} VENs in database")
    print(f"Processing {len(vens_to_process)} VENs")
    print("=" * 80)

    # Track overall statistics
    total_vens_processed = 0
    total_vens_successful = 0
    total_loads_uploaded = 0
    total_loads_failed = 0
    total_points_uploaded = 0

    # Process each VEN
    for idx, ven_id in enumerate(vens_to_process, 1):
        print(f"\n{'='*80}")
        print(f"VEN {idx}/{len(vens_to_process)}: {ven_id}")
        print(f"{'='*80}")

        try:
            # Register the VEN
            await manager.register_load_ven(ven_id)
            print(f"✓ VEN '{ven_id}' registered/verified")

            # Upload all loads for this VEN (no limit)
            print(f"Uploading historical data for ALL loads...")

            stats = await manager.bulk_upload_historical_meterdata(
                ven_id=ven_id,
                limit_loads=None,  # No limit - process all loads
                chunk_size=chunk_size,
                batch_size=batch_size
            )

            # Update totals
            total_vens_processed += 1
            if stats['successful'] > 0:
                total_vens_successful += 1
            total_loads_uploaded += stats['successful']
            total_loads_failed += stats['failed']
            total_points_uploaded += stats['total_points_uploaded']

            # Show VEN results
            print(f"\n✓ VEN '{ven_id}' complete:")
            print(f"  Loads: {stats['successful']}/{stats['total_loads']} uploaded")
            print(f"  Points: {stats['total_points_uploaded']:,}")

        except Exception as e:
            print(f"\n❌ Error processing VEN '{ven_id}': {e}")
            import traceback
            traceback.print_exc()
            continue

    # Final summary
    print("\n" + "=" * 80)
    print("FINAL SUMMARY - ALL VENS")
    print("=" * 80)
    print(f"VENs processed: {total_vens_processed}/{len(vens_to_process)}")
    print(f"VENs successful: {total_vens_successful}")
    print(f"Total loads uploaded: {total_loads_uploaded}")
    print(f"Total loads failed: {total_loads_failed}")
    print(f"Total data points uploaded: {total_points_uploaded:,}")

    if total_loads_uploaded > 0:
        print(f"\n✅ SUCCESS! Uploaded data for {total_loads_uploaded} loads across {total_vens_successful} VENs")
    else:
        print(f"\n❌ FAILED - No loads uploaded successfully")

    print("=" * 80)

    await manager.cleanup()


async def main():
    import argparse

    # Read environment variables
    env = environ.Env()
    environ.Env.read_env()

    default_vtn_url = env('VTN_SERVER_ADDRESS', default='http://127.0.0.1:8444/openadr3')

    parser = argparse.ArgumentParser(description='Upload historical data for ALL VENs and ALL loads')
    parser.add_argument('--vtn-url', type=str, default=default_vtn_url,
                       help='VTN server URL (default: from .env file)')
    parser.add_argument('--token', type=str, default=None,
                       help='Bearer token (default: obtained via OAuth from .env)')
    parser.add_argument('--max-vens', type=int, default=None,
                       help='Limit number of VENs to process (for testing)')
    parser.add_argument('--chunk-size', type=int, default=50000,
                       help='Points per chunk (default: 50000)')
    parser.add_argument('--batch-size', type=int, default=5000,
                       help='InfluxDB batch size (default: 5000)')

    args = parser.parse_args()

    # Get token - either from argument or via OAuth
    if args.token:
        bearer_token = args.token
        print("Using token from command line argument")
    else:
        try:
            print("Obtaining OAuth token from .env configuration...")
            bearer_token = get_access_token()
            print("✓ Successfully obtained OAuth token\n")
        except Exception as e:
            print(f"❌ Error obtaining OAuth token: {e}")
            print("\nPlease ensure these are set in .env file:")
            print("  - OAUTH_CLIENT_ID")
            print("  - OAUTH_CLIENT_SECRET")
            print("  - OAUTHCHECK_ACCESS_TOKEN_OBTAIN_URL")
            return

    await upload_all_vens(
        vtn_url=args.vtn_url,
        bearer_token=bearer_token,
        max_vens=args.max_vens,
        chunk_size=args.chunk_size,
        batch_size=args.batch_size
    )


if __name__ == "__main__":
    asyncio.run(main())
