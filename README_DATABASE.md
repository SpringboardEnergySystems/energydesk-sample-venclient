# Resource Database for VEN Client

## Overview

This project uses **SQLite** as a lightweight, file-based database for storing Resource and Connection objects in the VEN (Virtual End Node) client. SQLite is ideal for Raspberry Pi deployment due to its:

- **Zero configuration**: No server process required
- **Small footprint**: Perfect for embedded systems
- **ACID compliance**: Reliable data storage
- **Single file storage**: Easy backup and deployment
- **Built-in Python support**: No additional dependencies

## Database Architecture

### Storage Strategy

```
┌─────────────────────────────────────────────┐
│         Raspberry Pi VEN Client             │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────────┐      ┌────────────────┐  │
│  │   SQLite     │      │   InfluxDB     │  │
│  │   Database   │      │   (Time-Series)│  │
│  ├──────────────┤      ├────────────────┤  │
│  │ Resources    │      │ Meter Values   │  │
│  │ Connections  │      │ Measurements   │  │
│  │ Metadata     │      │ Historical     │  │
│  └──────────────┘      └────────────────┘  │
│        ↓                      ↓             │
│        └──────────┬───────────┘             │
│                   ↓                         │
│           ┌───────────────┐                 │
│           │  VTN Server   │                 │
│           │   Reporting   │                 │
│           └───────────────┘                 │
└─────────────────────────────────────────────┘
```

### Database Schema

#### `connections` table
Stores connection configuration for each resource (Modbus, MQTT, file reader, etc.)

```sql
CREATE TABLE connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,              -- MODBUSTCP, MQTT, FILEREADER
    actortype TEXT NOT NULL,         -- READER, WRITER
    host TEXT,
    port INTEGER,
    topic TEXT,
    file TEXT,
    username TEXT,
    password TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

#### `resources` table
Stores all resource metadata and configuration

```sql
CREATE TABLE resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id TEXT UNIQUE NOT NULL,      -- UUID
    resource_name TEXT NOT NULL,
    resource_type TEXT NOT NULL,           -- DSR, BATTERY, PV, EV
    resource_sub_type TEXT,                -- Hotels, Schools, etc.
    meter_point_id TEXT NOT NULL,          -- Meter point identifier
    connection_id INTEGER NOT NULL,        -- FK to connections
    capacities TEXT NOT NULL,              -- JSON: P_max_kw, P_min_kw, E_max_kwh, E_min_kwh
    location TEXT NOT NULL,                -- JSON: latitude, longitude
    address TEXT,
    ven TEXT,                              -- VEN identifier (city)
    enabled BOOLEAN DEFAULT 1,
    reporting TEXT,                        -- JSON: reporting configuration
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (connection_id) REFERENCES connections(id)
)
```

#### Indexes
For optimal query performance:
- `idx_resource_id` - Fast lookup by resource ID
- `idx_meter_point_id` - Fast lookup by meter point
- `idx_resource_type` - Filter by resource type
- `idx_ven` - Filter by VEN/city

## Usage

### 1. Generate Resources Database

Run the prepare script to convert CSV files into the database:

```bash
python prepare_samples.py
```

This will:
1. Read all CSV files from `config/exampleassets/`
2. Convert each row to a Resource object
3. Store in SQLite database at `config/resources.db`
4. Display statistics about stored resources

### 2. Query Resources

```python
from resource_db import ResourceDatabase

# Initialize database
db = ResourceDatabase(db_path="./config/resources.db")

# Get all resources
all_resources = db.get_all_resources()

# Get resources by type
dsr_resources = db.get_resources_by_type("DSR")
ev_resources = db.get_resources_by_type("EV")

# Get resources by VEN (city)
herning_resources = db.get_resources_by_ven("Herning")

# Get specific resource
resource = db.get_resource("5249eada-69af-432d-99a5-98f9c89f9aa6")

# Get statistics
stats = db.get_statistics()
print(f"Total resources: {stats['total_resources']}")
print(f"By type: {stats['by_type']}")
print(f"Top VENs: {stats['top_10_vens']}")
```

### 3. Demo Script

Run the demo to see various query examples:

```bash
python demo_db_usage.py
```

## API Reference

### ResourceDatabase Class

#### `__init__(db_path: str = "./config/resources.db")`
Initialize database connection and create tables if needed.

#### `insert_connection(connection: Connection) -> int`
Insert a connection record and return its ID.

#### `insert_resource(resource: Resource, connection_id: int, ven: str = None)`
Insert a resource record linked to a connection.

#### `get_resource(resource_id: str) -> Optional[Resource]`
Retrieve a single resource by its ID.

#### `get_resources_by_type(resource_type: str) -> List[Resource]`
Get all resources of a specific type (DSR, EV, BATTERY, PV).

#### `get_resources_by_ven(ven: str) -> List[Resource]`
Get all resources for a specific VEN/city.

#### `get_all_resources() -> List[Resource]`
Retrieve all resources from the database.

#### `get_statistics() -> Dict`
Get database statistics including counts by type, sub-type, and VEN.

#### `clear_all_resources()`
Delete all resources and connections. **Use with caution!**

## Data Flow

### Preparation Phase (One-time)
```
CSV Files → pandas DataFrame → Resource Objects → SQLite Database
```

### Runtime Phase (Continuous)
```
SQLite Database → Load Resources → Connect to Meters → Read Values → InfluxDB → Report to VTN
```

## File Structure

```
config/
├── resources.db              # SQLite database (auto-created)
├── exampleassets/            # Source CSV files
│   ├── bars-in-denmark.csv
│   ├── hotels-in-denmark.csv
│   ├── schools-in-denmark.csv
│   └── ...
└── examplemeterdata/         # (Future) Generated meter data files

venclient/
├── client.py                 # VEN client implementation
└── utils.py                  # Utility functions

resource_db.py                # Database module (this implementation)
prepare_samples.py            # Data preparation script
demo_db_usage.py              # Example queries and usage
flex_resources.py             # Resource and Connection dataclasses
```

## Performance Considerations

### For Raspberry Pi Deployment

1. **WAL Mode**: SQLite Write-Ahead Logging for better concurrency
   ```python
   # Enable in production
   conn.execute("PRAGMA journal_mode=WAL")
   ```

2. **Memory Settings**: Adjust cache size for Raspberry Pi
   ```python
   conn.execute("PRAGMA cache_size=-8000")  # 8MB cache
   ```

3. **Read-Heavy Optimization**: Most operations will be reads
   - Indexes are already configured
   - Connection pooling not needed (single client)

4. **Backup Strategy**: Simple file copy
   ```bash
   cp config/resources.db config/resources.db.backup
   ```

## Integration with InfluxDB

### Separation of Concerns

- **SQLite**: Static resource metadata
  - Resource definitions
  - Connection configurations
  - Capacities and constraints
  - Location data

- **InfluxDB**: Dynamic time-series data
  - Meter readings (kW, kWh)
  - Timestamps
  - Measurement intervals
  - Historical trends

### Example Integration

```python
from resource_db import ResourceDatabase
from influxdb_client import InfluxDBClient

# Load resource from SQLite
db = ResourceDatabase()
resource = db.get_resource(resource_id)

# Read meter value (via connection in resource)
meter_value = read_meter(resource.connection, resource.meterPointId)

# Store in InfluxDB
influx_client = InfluxDBClient(url="http://localhost:8086", token="...")
point = Point("meter_reading") \
    .tag("resource_id", resource.resourceID) \
    .tag("meter_point_id", resource.meterPointId) \
    .field("power_kw", meter_value) \
    .time(datetime.utcnow())
write_api.write(bucket="meter_data", record=point)
```

## Future Enhancements

1. **Resource Updates**: Add `update_resource()` method for runtime changes
2. **Reporting Config**: Store reporting schedules and status in database
3. **Migration Scripts**: Version control for schema changes
4. **Bulk Operations**: Optimize for mass updates
5. **Query Builder**: Higher-level query interface

## Troubleshooting

### Database locked error
If you get "database is locked", ensure only one process writes at a time.

### Check database integrity
```bash
sqlite3 config/resources.db "PRAGMA integrity_check;"
```

### View database contents
```bash
sqlite3 config/resources.db
.tables
.schema resources
SELECT COUNT(*) FROM resources;
```

### Reset database
```python
from resource_db import ResourceDatabase
db = ResourceDatabase()
db.clear_all_resources()
```

## License

This is a sample implementation for VEN client demonstration purposes.

