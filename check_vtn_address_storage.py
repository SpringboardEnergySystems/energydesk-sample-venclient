"""
Check VTN database to verify address is stored in service_location and not in attributes
"""
import asyncio
import logging
from venclient.utils import get_access_token
import environ
from energydeskapi.sdk.common_utils import get_environment_value
from energydeskapi.sdk.logging_utils import setup_service_logging
import aiohttp
import json

logger = logging.getLogger(__name__)

async def check_vtn_resources():
    """
    Check VTN resources to verify address field location
    """
    setup_service_logging("VTN Address Check")

    # Load environment
    environ.Env.read_env()
    vtn_url = get_environment_value('VTN_SERVER_ADDRESS', None)
    bearer_token = get_access_token()

    if not vtn_url:
        logger.error("Missing VTN_SERVER_ADDRESS in environment")
        return

    logger.info("=" * 60)
    logger.info("Checking VTN Resource Address Storage")
    logger.info("=" * 60)

    # Get resources from VTN
    headers = {'Authorization': f'Bearer {bearer_token}'}

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{vtn_url}/resources",
            headers=headers
        ) as response:
            if response.status != 200:
                logger.error(f"Failed to fetch resources: {response.status}")
                return

            resources = await response.json()

            if not resources:
                logger.warning("No resources found in VTN")
                return

            logger.info(f"Found {len(resources)} resources in VTN")

            # Check first few resources
            sample_count = min(5, len(resources))
            logger.info(f"\nChecking first {sample_count} resources:")

            address_in_service_location = 0
            address_in_attributes = 0
            no_address = 0

            for i, resource in enumerate(resources[:sample_count], 1):
                resource_name = resource.get('resource_name', 'Unknown')
                service_location = resource.get('service_location', {})
                attributes = resource.get('attributes', [])

                logger.info(f"\n[{i}] {resource_name}")
                logger.info(f"  Resource ID: {resource.get('id', 'N/A')}")

                # Check service_location for address
                if service_location and 'address' in service_location:
                    address_in_service_location += 1
                    logger.info(f"  ✓ Address in service_location: {service_location['address'][:50]}...")
                    logger.info(f"    service_location keys: {list(service_location.keys())}")
                else:
                    logger.warning(f"  ✗ No address in service_location")
                    if service_location:
                        logger.info(f"    service_location keys: {list(service_location.keys())}")

                # Check attributes for address
                address_attrs = [a for a in attributes if a.get('attribute_type') == 'address' or a.get('attribute_name') == 'address']
                if address_attrs:
                    address_in_attributes += 1
                    logger.warning(f"  ✗ Address found in attributes (should not be here!)")
                    logger.info(f"    {json.dumps(address_attrs, indent=6)}")
                else:
                    logger.info(f"  ✓ No address in attributes (correct!)")

                if not service_location or 'address' not in service_location:
                    if not address_attrs:
                        no_address += 1
                        logger.error(f"  ⚠ No address found anywhere!")

            # Summary
            logger.info("\n" + "=" * 60)
            logger.info("Summary:")
            logger.info(f"  Resources checked: {sample_count}")
            logger.info(f"  Address in service_location: {address_in_service_location} ✓")
            logger.info(f"  Address in attributes (bad): {address_in_attributes}")
            logger.info(f"  No address found: {no_address}")
            logger.info("=" * 60)

            if address_in_service_location == sample_count and address_in_attributes == 0:
                logger.info("✓ SUCCESS! All addresses are correctly stored in service_location")
            elif address_in_attributes > 0:
                logger.warning("⚠ Some addresses found in attributes (old format)")
            else:
                logger.warning("⚠ Some addresses missing")

if __name__ == '__main__':
    asyncio.run(check_vtn_resources())
