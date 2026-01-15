"""
SQLite database module for storing Resource and Connection objects.
This lightweight database is suitable for Raspberry Pi deployment.
"""
import sqlite3
import json
import logging
from typing import List, Optional, Dict
from contextlib import contextmanager
from flex_resources import Resource, Connection, ConnectionType, ActorType

logger = logging.getLogger(__name__)


class ResourceDatabase:
    """SQLite database manager for Resource and Connection objects."""

    def __init__(self, db_path: str = "./config/resources.db"):
        """
        Initialize the database.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.init_database()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def init_database(self):
        """Create database tables if they don't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Connections table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS connections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    actortype TEXT NOT NULL,
                    host TEXT,
                    port INTEGER,
                    topic TEXT,
                    file TEXT,
                    username TEXT,
                    password TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Resources table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS resources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resource_id TEXT UNIQUE NOT NULL,
                    resource_name TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_sub_type TEXT,
                    meter_point_id TEXT NOT NULL,
                    connection_id INTEGER NOT NULL,
                    capacities TEXT NOT NULL,
                    location TEXT NOT NULL,
                    address TEXT,
                    ven TEXT,
                    enabled BOOLEAN DEFAULT 1,
                    reporting TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (connection_id) REFERENCES connections(id)
                )
            """)

            # Create indexes for better query performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_resource_id 
                ON resources(resource_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_meter_point_id 
                ON resources(meter_point_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_resource_type 
                ON resources(resource_type)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_ven 
                ON resources(ven)
            """)

            logger.info(f"Database initialized at {self.db_path}")

    def insert_connection(self, connection: Connection) -> int:
        """
        Insert a connection and return its ID.

        Args:
            connection: Connection object to insert

        Returns:
            ID of the inserted connection
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO connections 
                (type, actortype, host, port, topic, file, username, password)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                connection.type.value,
                connection.actortype.value,
                connection.host,
                connection.port,
                connection.topic,
                connection.file,
                connection.username,
                connection.password
            ))
            return cursor.lastrowid

    def insert_resource(self, resource: Resource, connection_id: int, ven: str = None):
        """
        Insert a resource into the database.

        Args:
            resource: Resource object to insert
            connection_id: ID of the associated connection
            ven: VEN identifier (city/location)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO resources 
                (resource_id, resource_name, resource_type, resource_sub_type,
                 meter_point_id, connection_id, capacities, location, address,
                 ven, enabled, reporting)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                resource.resourceID,
                resource.resourceName,
                resource.resourceType,
                resource.resourceSubType,
                resource.meterPointId,
                connection_id,
                json.dumps(resource.capacities),
                json.dumps(resource.location),
                resource.address,
                ven,
                resource.enabled if resource.enabled is not None else True,
                json.dumps(resource.reporting) if resource.reporting else None
            ))
            logger.debug(f"Inserted resource: {resource.resourceID}")

    def bulk_insert_resources(self, resources: List[tuple]):
        """
        Bulk insert resources for better performance.

        Args:
            resources: List of tuples containing resource data
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # First, insert a default connection for all resources
            cursor.execute("""
                INSERT INTO connections 
                (type, actortype, host, port, topic, file, username, password)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ConnectionType.FILEREADER.value,
                ActorType.READER.value,
                None, None, None, "", None, None
            ))
            connection_id = cursor.lastrowid

            # Prepare resource data with the connection_id
            resource_data = []
            for r in resources:
                resource_data.append(r + (connection_id,))

            cursor.executemany("""
                INSERT OR REPLACE INTO resources 
                (resource_id, resource_name, resource_type, resource_sub_type,
                 meter_point_id, capacities, location, address, ven, enabled, connection_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, resource_data)

            logger.info(f"Bulk inserted {len(resources)} resources")

    def get_resource(self, resource_id: str) -> Optional[Resource]:
        """
        Retrieve a resource by ID.

        Args:
            resource_id: The resource ID to retrieve

        Returns:
            Resource object or None if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.*, c.*
                FROM resources r
                JOIN connections c ON r.connection_id = c.id
                WHERE r.resource_id = ?
            """, (resource_id,))
            row = cursor.fetchone()

            if row:
                return self._row_to_resource(row)
            return None

    def get_resources_by_type(self, resource_type: str) -> List[Resource]:
        """
        Retrieve all resources of a specific type.

        Args:
            resource_type: The resource type to filter by

        Returns:
            List of Resource objects
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.*, c.*
                FROM resources r
                JOIN connections c ON r.connection_id = c.id
                WHERE r.resource_type = ?
            """, (resource_type,))

            return [self._row_to_resource(row) for row in cursor.fetchall()]

    def get_resources_by_ven(self, ven: str) -> List[Resource]:
        """
        Retrieve all resources for a specific VEN.

        Args:
            ven: The VEN identifier (city/location)

        Returns:
            List of Resource objects
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.*, c.*
                FROM resources r
                JOIN connections c ON r.connection_id = c.id
                WHERE r.ven = ?
            """, (ven,))

            return [self._row_to_resource(row) for row in cursor.fetchall()]

    def get_all_resources(self) -> List[Resource]:
        """
        Retrieve all resources.

        Returns:
            List of all Resource objects
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.*, c.*
                FROM resources r
                JOIN connections c ON r.connection_id = c.id
            """)

            return [self._row_to_resource(row) for row in cursor.fetchall()]

    def get_statistics(self) -> Dict:
        """
        Get database statistics.

        Returns:
            Dictionary with statistics
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total resources
            cursor.execute("SELECT COUNT(*) FROM resources")
            total_resources = cursor.fetchone()[0]

            # Resources by type
            cursor.execute("""
                SELECT resource_type, COUNT(*) as count
                FROM resources
                GROUP BY resource_type
            """)
            by_type = {row[0]: row[1] for row in cursor.fetchall()}

            # Resources by sub-type
            cursor.execute("""
                SELECT resource_sub_type, COUNT(*) as count
                FROM resources
                GROUP BY resource_sub_type
            """)
            by_subtype = {row[0]: row[1] for row in cursor.fetchall()}

            # Resources by VEN
            cursor.execute("""
                SELECT ven, COUNT(*) as count
                FROM resources
                GROUP BY ven
                ORDER BY count DESC
                LIMIT 10
            """)
            by_ven = {row[0]: row[1] for row in cursor.fetchall()}

            return {
                'total_resources': total_resources,
                'by_type': by_type,
                'by_subtype': by_subtype,
                'top_10_vens': by_ven
            }

    def _row_to_resource(self, row: sqlite3.Row) -> Resource:
        """
        Convert a database row to a Resource object.

        Args:
            row: SQLite row object

        Returns:
            Resource object
        """
        # Create Connection object from row
        connection = Connection(
            type=ConnectionType(row['type']),
            actortype=ActorType(row['actortype']),
            host=row['host'],
            port=row['port'],
            topic=row['topic'],
            file=row['file'],
            username=row['username'],
            password=row['password']
        )

        # Create Resource object from row
        resource = Resource(
            resourceID=row['resource_id'],
            resourceName=row['resource_name'],
            resourceType=row['resource_type'],
            resourceSubType=row['resource_sub_type'],
            meterPointId=row['meter_point_id'],
            connection=connection,
            capacities=json.loads(row['capacities']),
            location=json.loads(row['location']),
            address=row['address'],
            enabled=bool(row['enabled']),
            reporting=json.loads(row['reporting']) if row['reporting'] else None
        )

        return resource

    def clear_all_resources(self):
        """Delete all resources and connections. Use with caution!"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM resources")
            cursor.execute("DELETE FROM connections")
            logger.warning("All resources and connections deleted from database")

