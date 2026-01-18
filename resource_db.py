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
                    registration_status TEXT DEFAULT 'PENDING',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (connection_id) REFERENCES connections(id)
                )
            """)

            # Add registration_status column if it doesn't exist (for existing databases)
            try:
                cursor.execute("""
                    ALTER TABLE resources 
                    ADD COLUMN registration_status TEXT DEFAULT 'PENDING'
                """)
                logger.info("Added registration_status column to existing database")
            except sqlite3.OperationalError:
                # Column already exists
                pass

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

            # Add h5_meter_id column to resources table if it doesn't exist
            try:
                cursor.execute("""
                    ALTER TABLE resources 
                    ADD COLUMN h5_meter_id TEXT
                """)
                logger.info("Added h5_meter_id column to resources table")
            except sqlite3.OperationalError:
                # Column already exists
                pass

            # Loads table - stores individual load components for each resource
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS loads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    load_id TEXT UNIQUE NOT NULL,
                    resource_id TEXT NOT NULL,
                    load_component TEXT NOT NULL,
                    load_name TEXT,
                    h5_meter_id TEXT NOT NULL,
                    vtn_resource_id TEXT,
                    registration_status TEXT DEFAULT 'PENDING',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (resource_id) REFERENCES resources(resource_id)
                )
            """)

            # Create indexes for loads table
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_load_resource_id 
                ON loads(resource_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_load_h5_meter_id 
                ON loads(h5_meter_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_load_vtn_resource_id 
                ON loads(vtn_resource_id)
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

    def get_resources_by_ven_and_status(self, ven: str, status: str) -> List[Resource]:
        """
        Retrieve resources for a specific VEN filtered by registration status.

        Args:
            ven: The VEN identifier (city/location)
            status: Registration status ('PENDING', 'APPROVED', 'SUSPENDED')

        Returns:
            List of Resource objects
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.*, c.*
                FROM resources r
                JOIN connections c ON r.connection_id = c.id
                WHERE r.ven = ? AND r.registration_status = ?
            """, (ven, status))

            return [self._row_to_resource(row) for row in cursor.fetchall()]

    def update_resource_status(self, resource_id: str, status: str):
        """
        Update the registration status of a resource.

        Args:
            resource_id: The resource ID to update
            status: New registration status ('PENDING', 'APPROVED', 'SUSPENDED')
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE resources 
                SET registration_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE resource_id = ?
            """, (status, resource_id))
            logger.info(f"Updated resource {resource_id} status to {status}")

    def get_ven_list(self) -> List[str]:
        """
        Get list of all unique VEN identifiers.

        Returns:
            List of VEN identifiers
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT ven FROM resources WHERE ven IS NOT NULL ORDER BY ven")
            return [row[0] for row in cursor.fetchall()]

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
        # Convert row to dict to safely check for registration_status field
        row_dict = dict(row)

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
            reporting=json.loads(row['reporting']) if row['reporting'] else None,
            registration_status=row_dict.get('registration_status', 'PENDING')
        )

        return resource

    def clear_all_resources(self):
        """Delete all resources and connections. Use with caution!"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM resources")
            cursor.execute("DELETE FROM connections")
            logger.warning("All resources and connections deleted from database")

    def update_resource_h5_meter(self, resource_id: str, h5_meter_id: str):
        """
        Update the h5_meter_id for a resource.

        Args:
            resource_id: The resource ID to update
            h5_meter_id: The h5 meter ID to assign
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE resources 
                SET h5_meter_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE resource_id = ?
            """, (h5_meter_id, resource_id))
            logger.debug(f"Assigned h5_meter_id {h5_meter_id} to resource {resource_id}")

    def insert_load(self, load_id: str, resource_id: str, load_component: str,
                   load_name: str, h5_meter_id: str, vtn_resource_id: str = None):
        """
        Insert a load component.

        Args:
            load_id: Unique load identifier
            resource_id: The resource ID this load belongs to
            load_component: Load component name (e.g., 'load_0', 'load_1')
            load_name: Human-readable load name
            h5_meter_id: The h5 meter ID containing the load data
            vtn_resource_id: VTN resource ID (if registered)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO loads 
                (load_id, resource_id, load_component, load_name, h5_meter_id, vtn_resource_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (load_id, resource_id, load_component, load_name, h5_meter_id, vtn_resource_id))
            logger.debug(f"Inserted load: {load_id} for resource {resource_id}")

    def bulk_insert_loads(self, loads: List[tuple]):
        """
        Bulk insert loads for better performance.

        Args:
            loads: List of tuples containing (load_id, resource_id, load_component,
                   load_name, h5_meter_id, vtn_resource_id)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR REPLACE INTO loads 
                (load_id, resource_id, load_component, load_name, h5_meter_id, vtn_resource_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, loads)
            logger.info(f"Bulk inserted {len(loads)} loads")

    def get_loads_by_resource(self, resource_id: str) -> List[Dict]:
        """
        Get all loads for a specific resource.

        Args:
            resource_id: The resource ID

        Returns:
            List of load dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM loads WHERE resource_id = ?
            """, (resource_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_loads_by_h5_meter(self, h5_meter_id: str) -> List[Dict]:
        """
        Get all loads using a specific h5 meter.

        Args:
            h5_meter_id: The h5 meter ID

        Returns:
            List of load dictionaries
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM loads WHERE h5_meter_id = ?
            """, (h5_meter_id,))
            return [dict(row) for row in cursor.fetchall()]

    def update_load_vtn_resource_id(self, load_id: str, vtn_resource_id: str, status: str = 'APPROVED'):
        """
        Update the VTN resource ID for a load after registration.

        Args:
            load_id: The load ID to update
            vtn_resource_id: The VTN-assigned resource ID
            status: Registration status
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE loads 
                SET vtn_resource_id = ?, registration_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE load_id = ?
            """, (vtn_resource_id, status, load_id))
            logger.info(f"Updated load {load_id} with VTN resource ID {vtn_resource_id}")

    def clear_all_loads(self):
        """Delete all loads. Use with caution!"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM loads")
            logger.warning("All loads deleted from database")

    def get_load_statistics(self) -> Dict:
        """
        Get load statistics.

        Returns:
            Dictionary with statistics
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total loads
            cursor.execute("SELECT COUNT(*) FROM loads")
            total_loads = cursor.fetchone()[0]

            # Loads by component
            cursor.execute("""
                SELECT load_component, COUNT(*) as count
                FROM loads
                GROUP BY load_component
            """)
            by_component = {row[0]: row[1] for row in cursor.fetchall()}

            # Loads by status
            cursor.execute("""
                SELECT registration_status, COUNT(*) as count
                FROM loads
                GROUP BY registration_status
            """)
            by_status = {row[0]: row[1] for row in cursor.fetchall()}

            return {
                'total_loads': total_loads,
                'by_component': by_component,
                'by_status': by_status
            }

