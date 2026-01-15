"""
Example usage of the Resource Database.
Demonstrates how to query and retrieve resources from the SQLite database.
"""
import logging
from resource_db import ResourceDatabase
from flex_resources import ResourceType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def demo_database_usage():
    """Demonstrate various database operations."""

    # Initialize database connection
    db = ResourceDatabase(db_path="./config/resources.db")

    # Get statistics
    print("\n" + "="*70)
    print("DATABASE STATISTICS")
    print("="*70)
    stats = db.get_statistics()
    print(f"\nTotal Resources: {stats['total_resources']}")

    print("\nResources by Type:")
    for rtype, count in stats['by_type'].items():
        print(f"  {rtype}: {count}")

    print("\nResources by Sub-Type:")
    for subtype, count in stats['by_subtype'].items():
        print(f"  {subtype}: {count}")

    print("\nTop 10 VENs (Cities):")
    for ven, count in stats['top_10_vens'].items():
        print(f"  {ven}: {count}")

    # Get all DSR resources
    print("\n" + "="*70)
    print("DSR RESOURCES (first 5)")
    print("="*70)
    dsr_resources = db.get_resources_by_type(ResourceType.DSR.name)
    for resource in dsr_resources[:5]:
        print(f"\nResource: {resource.resourceName}")
        print(f"  ID: {resource.resourceID}")
        print(f"  Type: {resource.resourceType} - {resource.resourceSubType}")
        print(f"  Meter Point: {resource.meterPointId}")
        print(f"  Location: {resource.location}")
        print(f"  Capacities: {resource.capacities}")
        print(f"  Connection Type: {resource.connection.type.value}")

    # Get resources for a specific VEN (city)
    print("\n" + "="*70)
    print("RESOURCES FOR SPECIFIC VEN")
    print("="*70)
    # Get the first VEN from statistics
    if stats['top_10_vens']:
        first_ven = list(stats['top_10_vens'].keys())[0]
        ven_resources = db.get_resources_by_ven(first_ven)
        print(f"\nFound {len(ven_resources)} resources for VEN: {first_ven}")

        # Show first 3 resources for this VEN
        for resource in ven_resources[:3]:
            print(f"\n  - {resource.resourceName}")
            print(f"    Type: {resource.resourceSubType}")
            print(f"    Address: {resource.address}")
            print(f"    Meter Point: {resource.meterPointId}")

    # Get a specific resource by ID
    print("\n" + "="*70)
    print("RETRIEVE SPECIFIC RESOURCE")
    print("="*70)
    all_resources = db.get_all_resources()
    if all_resources:
        first_resource = all_resources[0]
        retrieved = db.get_resource(first_resource.resourceID)
        if retrieved:
            print(f"\nSuccessfully retrieved: {retrieved.resourceName}")
            print(f"  Resource ID: {retrieved.resourceID}")
            print(f"  Type: {retrieved.resourceType}")
            print(f"  Sub-Type: {retrieved.resourceSubType}")
            print(f"  Meter Point: {retrieved.meterPointId}")
            print(f"  Enabled: {retrieved.enabled}")
            print(f"  Address: {retrieved.address}")
            print(f"  Location: lat={retrieved.location['latitude']}, lon={retrieved.location['longitude']}")
            print(f"  Capacities:")
            for key, value in retrieved.capacities.items():
                print(f"    {key}: {value}")

    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    demo_database_usage()

