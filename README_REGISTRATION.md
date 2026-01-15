# VEN Registration from SQLite Database

## Overview

This guide explains how to use the `sample_registration` function to register VENs (Virtual End Nodes) and their resources from a SQLite database with a VTN (Virtual Top Node) server in the OpenADR 3.0.1 framework.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Registration Process                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Load VENs from SQLite                                   │
│     └─> Get distinct VEN identifiers (cities)               │
│                                                              │
│  2. For Each VEN:                                           │
│     a) Register VEN with VTN Server                         │
│        └─> POST /vens                                       │
│                                                              │
│     b) Load Resources for VEN from SQLite                   │
│        └─> Query resources WHERE ven = 'city_name'          │
│                                                              │
│     c) Register Resources with VTN Server                   │
│        └─> POST /resources (for each resource)              │
│                                                              │
│  3. Report Statistics                                       │
│     └─> VENs registered, Resources registered, Failures     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Database Structure

The SQLite database (`config/resources.db`) contains:

**VEN Grouping**: Resources are grouped by the `ven` field (city name)
- Example VENs: "Aalborg", "Aarhus", "Herning", etc.

**Resource Data**: Each resource contains:
- `resource_id`: Unique UUID
- `resource_name`: Display name (e.g., "Murphy's Pub")
- `resource_type`: DSR, EV, BATTERY, PV
- `resource_sub_type`: Bars, Hotels, Schools, etc.
- `meter_point_id`: Unique meter identifier
- `location`: Latitude, longitude
- `address`: Full address
- `capacities`: P_max_kw, P_min_kw, E_max_kwh, E_min_kwh
- `ven`: VEN identifier (city)

### 2. Registration Flow

```python
# Load all unique VENs
vens = load_vens_from_sqlite()  # Returns: ["Aalborg", "Aarhus", "Herning", ...]

# For each VEN
for ven_id in vens:
    # 1. Register the VEN
    await manager.register_load_ven(ven_id)
    
    # 2. Load resources for this VEN
    resources = load_ven_resources_from_sqlite(ven_id)
    
    # 3. Register all resources
    resource_map = {r.resourceID: r for r in resources}
    await manager.register_resources(ven_id, resource_map)
```

## Usage

### Command Line

#### Basic Usage (Register All VENs)
```bash
python test_registration.py
```

#### Register Limited Number of VENs (Testing)
```bash
# Register only first 3 VENs
python test_registration.py --limit 3
```

#### Custom VTN Server URL
```bash
python test_registration.py --vtn-url http://my-vtn-server.com:8080
```

#### Custom Database Path
```bash
python test_registration.py --db-path /path/to/custom/resources.db
```

#### Skip Authentication
```bash
python test_registration.py --no-auth
```

### Programmatic Usage

```python
import asyncio
from venclient.client import sample_registration

async def register_all():
    await sample_registration(
        vtn_url="http://localhost:8000",
        bearer_token="your_token_here",
        db_path="./config/resources.db",
        limit_vens=None  # None = all VENs, or set a number
    )

# Run the registration
asyncio.run(register_all())
```

### From Existing Code

```python
from venclient.client import sample_registration
from venclient.utils import get_access_token

# Get authentication token
bearer_token = get_access_token()

# Register VENs and resources
await sample_registration(
    vtn_url="http://localhost:8000",
    bearer_token=bearer_token,
    db_path="./config/resources.db",
    limit_vens=5  # Register first 5 VENs only
)
```

## Helper Functions

### load_vens_from_sqlite()

Loads all unique VEN identifiers from the database.

```python
def load_vens_from_sqlite(db_path: str = "./config/resources.db") -> List[str]:
    """
    Returns:
        List of unique VEN identifiers (city names)
        Example: ["Aalborg", "Aarhus", "Herning", "Randers", ...]
    """
```

### load_ven_resources_from_sqlite()

Loads all resources for a specific VEN.

```python
def load_ven_resources_from_sqlite(
    ven_id: str, 
    db_path: str = "./config/resources.db"
) -> List[Resource]:
    """
    Args:
        ven_id: VEN identifier (city name)
        
    Returns:
        List of Resource objects for the specified VEN
    """
```

## Output Example

```
2026-01-14 10:00:00,000 - venclient.client - INFO - EnergyDesk OpenADR 3.0.1 VEN Client - Sample Registration
2026-01-14 10:00:00,001 - venclient.client - INFO - ============================================================
2026-01-14 10:00:00,001 - venclient.client - INFO - VTN URL: http://localhost:8000
2026-01-14 10:00:00,001 - venclient.client - INFO - Database: ./config/resources.db

2026-01-14 10:00:00,010 - venclient.client - INFO - Step 1: Loading VENs from SQLite database...
2026-01-14 10:00:00,015 - venclient.client - INFO - Loaded 158 VENs from SQLite database
2026-01-14 10:00:00,015 - venclient.client - INFO - Found 158 VENs in database
2026-01-14 10:00:00,015 - venclient.client - INFO - Limited to first 3 VENs for testing

2026-01-14 10:00:00,015 - venclient.client - INFO - Step 2: Registering 3 VENs and their resources...
2026-01-14 10:00:00,015 - venclient.client - INFO - ------------------------------------------------------------

2026-01-14 10:00:00,016 - venclient.client - INFO - [1/3] Processing VEN: Aalborg
2026-01-14 10:00:00,020 - venclient.client - INFO -   Found 627 resources for VEN 'Aalborg'
2026-01-14 10:00:00,021 - venclient.client - INFO -   Registering VEN 'Aalborg'...
2026-01-14 10:00:00,150 - venclient.client - INFO - Successfully registered VEN: Aalborg
2026-01-14 10:00:00,151 - venclient.client - INFO -   Registering 627 resources for VEN 'Aalborg'...
2026-01-14 10:00:05,234 - venclient.client - INFO -   ✓ Successfully registered VEN 'Aalborg' with 627 resources

2026-01-14 10:00:05,235 - venclient.client - INFO - [2/3] Processing VEN: Aarhus
2026-01-14 10:00:05,240 - venclient.client - INFO -   Found 557 resources for VEN 'Aarhus'
2026-01-14 10:00:05,241 - venclient.client - INFO -   Registering VEN 'Aarhus'...
2026-01-14 10:00:05,350 - venclient.client - INFO - Successfully registered VEN: Aarhus
2026-01-14 10:00:05,351 - venclient.client - INFO -   Registering 557 resources for VEN 'Aarhus'...
2026-01-14 10:00:09,876 - venclient.client - INFO -   ✓ Successfully registered VEN 'Aarhus' with 557 resources

2026-01-14 10:00:09,877 - venclient.client - INFO - [3/3] Processing VEN: Herning
2026-01-14 10:00:09,882 - venclient.client - INFO -   Found 507 resources for VEN 'Herning'
2026-01-14 10:00:09,883 - venclient.client - INFO -   Registering VEN 'Herning'...
2026-01-14 10:00:10,012 - venclient.client - INFO - Successfully registered VEN: Herning
2026-01-14 10:00:10,013 - venclient.client - INFO -   Registering 507 resources for VEN 'Herning'...
2026-01-14 10:00:14,234 - venclient.client - INFO -   ✓ Successfully registered VEN 'Herning' with 507 resources

2026-01-14 10:00:14,235 - venclient.client - INFO - 
============================================================
2026-01-14 10:00:14,235 - venclient.client - INFO - REGISTRATION SUMMARY
2026-01-14 10:00:14,235 - venclient.client - INFO - ============================================================
2026-01-14 10:00:14,235 - venclient.client - INFO - Total VENs processed:          3
2026-01-14 10:00:14,235 - venclient.client - INFO - VENs successfully registered:  3
2026-01-14 10:00:14,235 - venclient.client - INFO - Resources registered:          1691
2026-01-14 10:00:14,235 - venclient.client - INFO - Failed VENs:                   0
2026-01-14 10:00:14,235 - venclient.client - INFO - ============================================================

2026-01-14 10:00:14,236 - venclient.client - INFO - Registration process completed.
```

## Database Statistics

You can check the database before registration:

```bash
python demo_db_usage.py
```

This shows:
- Total resources in database
- Resources by type (DSR, EV, etc.)
- Resources by sub-type (Hotels, Schools, etc.)
- Top VENs by resource count

## Error Handling

The registration function handles various error scenarios:

### VEN Registration Failures
- If a VEN fails to register, it's logged and the process continues with the next VEN
- Failed VENs are tracked and reported in the summary

### Resource Registration Failures
- If some resources fail to register, the process continues
- Successful registrations are counted and reported

### Database Issues
- If database is not found, an error is logged
- If a VEN has no resources, it's skipped with a warning

### Network Issues
- Connection failures to VTN server are caught and logged
- The cleanup process ensures connections are properly closed

## Best Practices

### Testing
1. Start with a small number of VENs using `--limit`
2. Verify VTN server is running and accessible
3. Check authentication token is valid

### Production
1. Register all VENs without limit
2. Monitor logs for any failures
3. Re-run registration for failed VENs if needed

### Performance
- Registration is done asynchronously for better performance
- Multiple resources are registered concurrently
- Database queries are optimized with indexes

## Troubleshooting

### Database not found
```bash
# Create the database first
python prepare_samples.py
```

### Authentication failed
```bash
# Check your credentials in environment variables or .env file
# Or run without authentication for testing
python test_registration.py --no-auth
```

### VTN server not responding
```bash
# Verify VTN server is running
curl http://localhost:8000/health

# Or use custom URL
python test_registration.py --vtn-url http://your-vtn-server:8000
```

### Some resources fail to register
- Check VTN server logs for errors
- Verify resource data format is correct
- Check if resources already exist (409 Conflict)

## Integration Example

### Complete Workflow

```python
import asyncio
from prepare_samples import generate_resources
from venclient.client import sample_registration
from venclient.utils import get_access_token

async def complete_setup():
    # Step 1: Generate resources database from CSV files
    print("Step 1: Generating resources database...")
    db = generate_resources()
    
    # Step 2: Get authentication
    print("Step 2: Getting authentication token...")
    token = get_access_token()
    
    # Step 3: Register VENs and resources
    print("Step 3: Registering VENs and resources...")
    await sample_registration(
        vtn_url="http://localhost:8000",
        bearer_token=token,
        db_path="./config/resources.db"
    )
    
    print("Setup complete!")

if __name__ == '__main__':
    asyncio.run(complete_setup())
```

## Next Steps

After registration:
1. **Poll for Events**: VENs can start polling for DR events from VTN
2. **Report Meter Values**: Read meter data and report to VTN
3. **Respond to Events**: Implement event response logic
4. **Monitor Status**: Track VEN and resource status

See `venclient/client.py` for additional functions:
- `startup()`: Complete VEN client lifecycle
- `poll_events()`: Poll for DR events
- `respond_to_event()`: Respond to events
- `create_report()`: Send telemetry reports

## Related Files

- `resource_db.py` - SQLite database interface
- `prepare_samples.py` - Generate database from CSV files
- `venclient/client.py` - VEN client implementation
- `test_registration.py` - Registration test script
- `demo_db_usage.py` - Database query examples
- `README_DATABASE.md` - Database documentation

