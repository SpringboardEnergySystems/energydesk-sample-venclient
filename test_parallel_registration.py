#!/usr/bin/env python3
"""
Test script for the new parallel load registration
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from venclient.client import sample_registration

async def main():
    """Test the parallel load registration with a limited number of VENs"""

    vtn_url = "http://localhost:8444/openadr3"
    bearer_token = "your-bearer-token-here"  # Replace with actual token
    db_path = "./config/resources.db"

    print("=" * 70)
    print("Testing Parallel Load Registration")
    print("=" * 70)
    print(f"VTN URL: {vtn_url}")
    print(f"Database: {db_path}")
    print(f"Testing with: 2 VENs (limited for testing)")
    print("=" * 70)

    # Test with only 2 VENs
    await sample_registration(
        vtn_url=vtn_url,
        bearer_token=bearer_token,
        db_path=db_path,
        limit_vens=2,  # Test with just 2 VENs
        batch_size=20,  # Smaller batch size for testing
        delay_between_batches=0.5
    )

    print("\n" + "=" * 70)
    print("Test completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
