"""
Test script for sample_registration function.
This demonstrates registering VENs and resources from SQLite database with VTN server.

Usage:
    python test_registration.py [--limit N] [--vtn-url URL]

Options:
    --limit N       Limit registration to first N VENs (useful for testing)
    --vtn-url URL   VTN server URL (default: http://localhost:8000)
"""
import asyncio
import argparse
import logging
import sys
import os

# Add parent directory to path to import venclient
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from venclient.client import sample_registration
from venclient.utils import get_access_token

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point for the registration test."""
    parser = argparse.ArgumentParser(
        description='Register VENs and resources from SQLite database with VTN server'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit registration to first N VENs (useful for testing)'
    )
    parser.add_argument(
        '--vtn-url',
        type=str,
        default='http://localhost:8000',
        help='VTN server URL (default: http://localhost:8000)'
    )
    parser.add_argument(
        '--db-path',
        type=str,
        default='./config/resources.db',
        help='Path to SQLite database (default: ./config/resources.db)'
    )
    parser.add_argument(
        '--no-auth',
        action='store_true',
        help='Skip authentication (use if VTN server does not require auth)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0.1,
        help='Delay in seconds between resource registrations (default: 0.1)'
    )

    args = parser.parse_args()

    # Get bearer token for authentication
    bearer_token = None
    if not args.no_auth:
        logger.info("Getting authentication token...")
        try:
            bearer_token = get_access_token()
            logger.info("Authentication token obtained successfully")
        except Exception as e:
            logger.warning(f"Failed to get authentication token: {e}")
            logger.warning("Proceeding without authentication...")

    # Check if database exists
    if not os.path.exists(args.db_path):
        logger.error(f"Database not found at: {args.db_path}")
        logger.error("Please run 'python prepare_samples.py' first to create the database.")
        sys.exit(1)

    # Run the registration
    logger.info("Starting registration process...")
    logger.info("-" * 60)

    try:
        await sample_registration(
            vtn_url=args.vtn_url,
            bearer_token=bearer_token,
            db_path=args.db_path,
            limit_vens=args.limit,
            delay_between_resources=args.delay
        )
        logger.info("Registration completed successfully!")
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())

