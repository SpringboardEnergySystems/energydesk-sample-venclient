"""
Script to check resource_id uniqueness in the SQLite database
"""
import sqlite3
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_resource_id_uniqueness(db_path: str = "./config/resources.db"):
    """
    Check if resource_id is unique in the database.

    Args:
        db_path: Path to the SQLite database
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check for duplicates
    cursor.execute("""
        SELECT resource_id, COUNT(*) as count 
        FROM resources 
        GROUP BY resource_id 
        HAVING count > 1
    """)

    duplicates = cursor.fetchall()

    if duplicates:
        logger.error(f"Found {len(duplicates)} duplicate resource_id values:")
        for resource_id, count in duplicates:
            logger.error(f"  - {resource_id}: {count} occurrences")
        conn.close()
        return False
    else:
        # Get statistics
        cursor.execute("SELECT COUNT(*) as total FROM resources")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT resource_id) as unique_ids FROM resources")
        unique = cursor.fetchone()[0]

        logger.info(f"✓ All resource_ids are unique!")
        logger.info(f"  Total resources: {total}")
        logger.info(f"  Unique resource_ids: {unique}")

        # Show sample of resource_ids
        cursor.execute("SELECT resource_id, resource_name, ven FROM resources LIMIT 5")
        samples = cursor.fetchall()

        logger.info("\nSample resources:")
        for rid, name, ven in samples:
            logger.info(f"  - {rid[:8]}... | {name} | VEN: {ven}")

        conn.close()
        return True


if __name__ == "__main__":
    check_resource_id_uniqueness()

