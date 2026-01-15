"""
Verify resource_id uniqueness in SQLite database.
This script checks for duplicate resource_id values and reports statistics.
"""
import sqlite3
import logging
from resource_db import ResourceDatabase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_resource_id_uniqueness(db_path: str = "./config/resources.db"):
    """
    Check if resource_id values are unique in the database.

    Args:
        db_path: Path to the SQLite database
    """
    logger.info(f"Checking resource_id uniqueness in: {db_path}")
    logger.info("=" * 70)

    try:
        db = ResourceDatabase(db_path=db_path)

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Check total resources
            cursor.execute("SELECT COUNT(*) FROM resources")
            total_resources = cursor.fetchone()[0]
            logger.info(f"\nTotal resources in database: {total_resources}")

            # Check distinct resource_ids
            cursor.execute("SELECT COUNT(DISTINCT resource_id) FROM resources")
            distinct_resource_ids = cursor.fetchone()[0]
            logger.info(f"Distinct resource_ids: {distinct_resource_ids}")

            # Check for duplicates
            cursor.execute("""
                SELECT resource_id, COUNT(*) as count 
                FROM resources 
                GROUP BY resource_id 
                HAVING COUNT(*) > 1
            """)
            duplicates = cursor.fetchall()

            if duplicates:
                logger.error(f"\n❌ FOUND {len(duplicates)} DUPLICATE resource_id values!")
                logger.error("\nDuplicate resource_ids:")
                for resource_id, count in duplicates:
                    logger.error(f"  - {resource_id}: appears {count} times")

                    # Show details of duplicates
                    cursor.execute("""
                        SELECT id, resource_name, resource_type, resource_sub_type, ven 
                        FROM resources 
                        WHERE resource_id = ?
                    """, (resource_id,))
                    rows = cursor.fetchall()
                    for row in rows:
                        logger.error(f"    - ID: {row[0]}, Name: {row[1]}, Type: {row[2]}/{row[3]}, VEN: {row[4]}")
            else:
                logger.info(f"\n✅ ALL resource_id values are UNIQUE!")
                logger.info(f"   {total_resources} resources, {distinct_resource_ids} unique resource_ids")

            # Check for NULL resource_ids (should not exist due to NOT NULL constraint)
            cursor.execute("SELECT COUNT(*) FROM resources WHERE resource_id IS NULL")
            null_count = cursor.fetchone()[0]
            if null_count > 0:
                logger.error(f"\n❌ FOUND {null_count} NULL resource_id values!")
            else:
                logger.info(f"✅ No NULL resource_id values found")

            # Check resource_id format (should be UUIDs)
            cursor.execute("""
                SELECT resource_id 
                FROM resources 
                WHERE length(resource_id) != 36 
                   OR resource_id NOT LIKE '%-%-%-%-%'
                LIMIT 10
            """)
            invalid_formats = cursor.fetchall()
            if invalid_formats:
                logger.warning(f"\n⚠️  Found {len(invalid_formats)} resource_ids with non-UUID format:")
                for (resource_id,) in invalid_formats[:5]:
                    logger.warning(f"  - {resource_id}")
            else:
                logger.info(f"✅ All resource_ids appear to be valid UUIDs")

            # Show sample resource_ids
            cursor.execute("SELECT resource_id FROM resources LIMIT 5")
            samples = cursor.fetchall()
            logger.info("\nSample resource_ids:")
            for (resource_id,) in samples:
                logger.info(f"  - {resource_id}")

            # Check index existence
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='resources' AND name='idx_resource_id'
            """)
            index_exists = cursor.fetchone()
            if index_exists:
                logger.info(f"\n✅ Index 'idx_resource_id' exists for fast lookups")
            else:
                logger.warning(f"\n⚠️  Index 'idx_resource_id' not found")

            logger.info("\n" + "=" * 70)

            return len(duplicates) == 0 and null_count == 0

    except sqlite3.IntegrityError as e:
        logger.error(f"Integrity error: {e}")
        return False
    except Exception as e:
        logger.error(f"Error checking resource_id uniqueness: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    is_unique = check_resource_id_uniqueness()

    if is_unique:
        print("\n✅ Database integrity check PASSED - All resource_ids are unique!")
        exit(0)
    else:
        print("\n❌ Database integrity check FAILED - Found issues with resource_ids!")
        exit(1)

