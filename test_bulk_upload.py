#!/usr/bin/env python3
"""
Test bulk upload of historical meter data to VTN.
This script tests the bulk upload functionality with a small number of loads.
"""
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from venclient.client import VENManager


async def test_bulk_upload(vtn_url: str, bearer_token: str,
                           ven_id: str = None, limit_loads: int = 3):
    """
    Test bulk upload with a limited number of loads.

    Args:
        vtn_url: VTN server URL
        bearer_token: Authentication token
        ven_id: VEN identifier (default: first VEN)
        limit_loads: Number of loads to test (default: 3)
    """
    print("=" * 80)
    print("BULK UPLOAD TEST")
    print("=" * 80)
    print(f"VTN URL: {vtn_url}")
    print(f"Testing with: {limit_loads} loads")
    print("=" * 80)

    # Initialize VEN manager
    manager = VENManager(vtn_base_url=vtn_url, bearer_token=bearer_token)

    # Get VEN if not specified
    if not ven_id:
        from resource_db import ResourceDatabase
        db = ResourceDatabase("./config/resources.db")
        vens = db.get_ven_list()
        if not vens:
            print("❌ No VENs found in database")
            return
        ven_id = vens[0]
        print(f"Using first VEN: {ven_id}")

    # Register the VEN (if not already)
    try:
        await manager.register_load_ven(ven_id)
        print(f"✓ VEN '{ven_id}' registered/verified")
    except Exception as e:
        print(f"⚠️  VEN registration issue: {e}")

    # Test bulk upload
    print(f"\nStarting bulk upload for VEN '{ven_id}'...")
    print("-" * 80)

    try:
        stats = await manager.bulk_upload_historical_meterdata(
            ven_id=ven_id,
            limit_loads=limit_loads,
            chunk_size=10000,  # Smaller chunks for testing
            batch_size=2000
        )

        print("\n" + "=" * 80)
        print("UPLOAD RESULTS")
        print("=" * 80)
        print(f"VEN: {stats['ven_id']}")
        print(f"Total loads processed: {stats['total_loads']}")
        print(f"Successful uploads: {stats['successful']}")
        print(f"Failed uploads: {stats['failed']}")
        print(f"Total data points uploaded: {stats['total_points_uploaded']:,}")

        if stats['successful'] > 0:
            print(f"\n✅ Test successful! {stats['successful']}/{stats['total_loads']} loads uploaded")
        else:
            print(f"\n❌ Test failed - no loads uploaded successfully")

        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error during bulk upload: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await manager.cleanup()


async def main():
    import argparse
    import environ
    from venclient.utils import get_access_token

    # Read environment variables
    env = environ.Env()
    environ.Env.read_env()

    default_vtn_url = env('VTN_SERVER_ADDRESS', default='http://127.0.0.1:8444/openadr3')

    parser = argparse.ArgumentParser(description='Test bulk upload of historical meter data')
    parser.add_argument('--vtn-url', type=str, default=default_vtn_url,
                       help=f'VTN server URL (default: from .env file)')
    parser.add_argument('--token', type=str, default=None,
                       help='Bearer token for authentication (default: obtained via OAuth from .env)')
    parser.add_argument('--ven', type=str,
                       help='VEN identifier (default: first VEN in database)')
    parser.add_argument('--limit', type=int, default=3,
                       help='Number of loads to test (default: 3)')

    args = parser.parse_args()

    # Get token - either from argument or via OAuth
    if args.token:
        bearer_token = args.token
        print(f"Using token from command line argument")
    else:
        try:
            print("Obtaining OAuth token from .env configuration...")
            bearer_token = get_access_token()
            print("✓ Successfully obtained OAuth token")
        except Exception as e:
            print(f"❌ Error obtaining OAuth token: {e}")
            print("\nPlease ensure these are set in .env file:")
            print("  - OAUTH_CLIENT_ID")
            print("  - OAUTH_CLIENT_SECRET")
            print("  - OAUTHCHECK_ACCESS_TOKEN_OBTAIN_URL")
            print("\nOr provide token directly: --token YOUR_TOKEN")
            return

    print(f"Using VTN URL: {args.vtn_url}")
    print(f"Using token: {bearer_token[:20]}..." if len(bearer_token) > 20 else f"Using token: {bearer_token}")

    await test_bulk_upload(
        vtn_url=args.vtn_url,
        bearer_token=bearer_token,
        ven_id=args.ven,
        limit_loads=args.limit
    )


if __name__ == "__main__":
    asyncio.run(main())
