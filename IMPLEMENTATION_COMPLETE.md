# Summary: Report Generation and Scheduler Pattern Implementation

## What Was Implemented

### 1. Report Generation with Simulated Meter Data

**New Method: `VENClient.report_meter_data()`**
- Sends individual meter readings to VTN server
- Formats data according to OpenADR 3.0 specification
- Handles multiple load components per resource
- Optional program_id for DR program-specific reports

**Updated Method: `VENManager.generate_reports()`**
- Collects simulated meter data from MeterDataSimulator
- Advances simulation time automatically
- Reports each load component separately (load_0 through load_5)
- Processes all VENs and their approved resources
- Comprehensive error handling and logging

**Report Structure (OpenADR 3.0):**
```json
{
  "report_name": "Resource_Name_timestamp",
  "resource_id": "uuid",
  "client_name": "Client_VEN",
  "report_type": "READING",
  "reading_type": "DIRECT_READ",
  "start": "ISO8601_timestamp",
  "duration": "PT0S",
  "intervals": [{"id": 0, "payloads": [{"type": "USAGE", "values": [kW]}]}],
  "resources": [{"resource_name": "Name"}],
  "load_component": "load_X",
  "program_id": "optional"
}
```

### 2. ApplicationContext Singleton Pattern

**New Module: `venclient/context.py`**
- Singleton registry for shared objects
- Thread-safe access to VENManager and MeterDataSimulator
- Simple get/set interface with convenience functions

**Key Functions:**
```python
register_object('ven_manager', manager)  # Register
manager = get_ven_manager()              # Retrieve
```

### 3. Updated Scheduled Tasks

**Updated Module: `venclient/scheduled_tasks.py`**

**Task 1: `heartbeat_task()`** (every 5 minutes)
- Health check
- Shows system is alive
- Lists registered objects

**Task 2: `simulate_meterdata()`** (every 30 seconds)
- Advances simulation time
- Logs statistics
- Prepares data for next report cycle

**Task 3: `resource_status_checker()`** (every 5 minutes)
- Monitors resource health
- Logs VEN and simulator statistics
- Shows current timestamp index

**Task 4: `generate_reports_task()`** (every 15 seconds)
- Collects meter data from simulator
- Sends reports to VTN server
- Handles async operation in scheduled context

### 4. Integrated Main Application

**Updated: `main.py`**

**Function: `initialize_ven_system()`**
- Creates VENManager and MeterDataSimulator
- Registers VENs with VTN server
- Initializes simulator with resources
- Registers objects in ApplicationContext
- Returns manager and simulator instances

**Function: `start_scheduler()`**
- Configures 4 scheduled tasks
- Sets appropriate intervals/cron schedules
- Returns configured scheduler

**Main Loop:**
1. Setup logging
2. Load environment variables
3. Get authentication token
4. Initialize VEN system (async)
5. Configure and start scheduler
6. Run main loop (sleep)
7. Handle cleanup on shutdown

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│              main.py Initialization                      │
│  - Create VENManager & MeterDataSimulator               │
│  - Register with VTN                                    │
│  - Store in ApplicationContext                          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│           Start APScheduler (4 tasks)                    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ├── Every 30s ──► simulate_meterdata()
                     │                  └─► Advance time
                     │
                     ├── Every 15s ──► generate_reports_task()
                     │                  ├─► Get manager from context
                     │                  ├─► Collect meter data
                     │                  └─► Send to VTN
                     │
                     ├── Every 5m ───► resource_status_checker()
                     │                  └─► Log statistics
                     │
                     └── Every 5m ───► heartbeat_task()
                                       └─► Health check
```

## Key Pattern: How Objects Are Passed

### Problem
- Scheduled tasks are simple functions: `def my_task():`
- APScheduler doesn't easily pass complex objects as parameters
- Need access to VENManager and MeterDataSimulator

### Solution: ApplicationContext Singleton
```python
# In main.py (initialization)
manager = VENManager(...)
simulator = MeterDataSimulator()
register_object('ven_manager', manager)
register_object('simulator', simulator)

# In scheduled_tasks.py (task functions)
def my_task():
    manager = get_ven_manager()      # Retrieve from context
    simulator = get_simulator()       # Retrieve from context
    # Use objects...
```

### Why This Pattern?
✅ No parameter passing needed
✅ Clean function signatures
✅ Thread-safe (singleton)
✅ Easy to test (can register mocks)
✅ Consistent with existing Borg pattern in simulator

## Usage

### Start the Application
```bash
python main.py
```

### Environment Variables Required
```bash
VTN_SERVER_ADDRESS=http://localhost:8444/openadr3
# Optional: VEN_LOCAL_ID (not currently used)
```

### What Happens
1. System initializes VENs and simulator
2. Scheduler starts running 4 tasks
3. Every 30 seconds: Simulation time advances
4. Every 15 seconds: Meter data reports sent to VTN
5. Every 5 minutes: Status check and heartbeat

### Monitoring
Watch the logs to see:
- VEN registration progress
- Simulator initialization
- Scheduled task execution
- Report generation statistics
- Any errors or warnings

## Testing

### Test Offline (No VTN Server)
```bash
python test_scheduler_pattern.py
# Select option 2 for offline testing
```

### Test Report Structure
```bash
python test_report_generation.py
# Select option 2 to see report format without sending
```

### Test With VTN Server
```bash
python test_report_generation.py
# Select option 1 and configure VTN URL and token
```

## Files Modified/Created

### Modified
- `venclient/client.py` - Added `report_meter_data()`, updated `generate_reports()`
- `venclient/scheduled_tasks.py` - Updated all tasks to use ApplicationContext
- `main.py` - Complete rewrite with new initialization pattern

### Created
- `venclient/context.py` - ApplicationContext singleton
- `REPORT_GENERATION_FEATURE.md` - Report generation documentation
- `SCHEDULER_PATTERN.md` - Scheduler pattern documentation
- `test_scheduler_pattern.py` - Pattern testing
- `test_report_generation.py` - Report generation testing

## Statistics Dictionary Structure

**Important:** The `get_statistics()` method returns:
```python
{
    'total_vens': 10,
    'total_resources': 1200,
    'total_by_status': {
        'APPROVED': 276,
        'PENDING': 924,
        'SUSPENDED': 0
    },
    'by_ven': {
        'Herning': {
            'approved': 28,
            'pending': 92,
            'suspended': 0,
            'total': 120
        },
        # ... more VENs
    }
}
```

**Access approved count:** `stats['total_by_status']['APPROVED']`
**NOT:** ~~`stats['total_approved']`~~ ❌

## Troubleshooting

### Error: 'total_approved' not found
**Solution:** Use `stats['total_by_status']['APPROVED']` instead
**Fixed in:** main.py, scheduled_tasks.py, test_scheduler_pattern.py

### No reports being sent
**Check:**
1. VEN registration successful?
2. Simulator initialized with approved resources?
3. Bearer token valid?
4. VTN server running at correct URL?

### Scheduler not running
**Check:**
1. `scheduler.start()` called?
2. Main loop running (not exiting)?
3. Check for exceptions in logs

### Tasks not executing
**Check:**
1. Objects registered in ApplicationContext?
2. Task function names correct in scheduler config?
3. Check scheduler job list: `scheduler.get_jobs()`

## Performance

### Current Load
- 10 VENs
- ~120 resources per VEN (1200 total)
- ~276 approved resources
- 6 load components per resource = ~1656 reports every 15 seconds

### Optimization Tips
1. Adjust report frequency in `start_scheduler()`
2. Limit number of VENs: `vens[:N]` in `initialize_ven_system()`
3. Add rate limiting if VTN server has limits
4. Consider batching reports if API supports it

## Next Steps

### Potential Enhancements
1. **InfluxDB Integration:** Cache meter data locally before reporting
2. **Retry Logic:** Queue failed reports for retry
3. **Selective Reporting:** Only report specific load components
4. **Aggregation:** Sum loads before reporting
5. **Configuration File:** Make intervals configurable
6. **Metrics:** Track reports sent, success rate, latency

### Production Readiness
- ✅ Error handling
- ✅ Logging
- ✅ Graceful shutdown
- ✅ Thread-safe singletons
- ⚠️ Need retry logic
- ⚠️ Need rate limiting
- ⚠️ Need metrics/monitoring

## Support

For questions or issues:
1. Check logs for detailed error messages
2. Review documentation files (*.md)
3. Run test scripts to isolate issues
4. Verify environment variables and configuration

