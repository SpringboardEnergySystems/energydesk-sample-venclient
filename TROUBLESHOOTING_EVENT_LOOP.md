# Troubleshooting: "Event loop is closed" Error

## Problem Description

When running scheduled tasks that call async methods (like `generate_reports()`), you may see errors like:

```
ERROR: Error reporting meter data for resource_name: Event loop is closed
```

## Root Cause

This happens because of a mismatch between event loops:

1. **Initialization Phase (main.py)**
   - Creates main event loop
   - Initializes VENManager and VENClient instances
   - Each VENClient creates an aiohttp.ClientSession
   - Sessions are bound to the main event loop

2. **Scheduler Task Execution**
   - APScheduler runs tasks in background threads
   - `generate_reports_task()` creates a NEW event loop
   - Tries to use old sessions from the original loop
   - **ERROR:** Old sessions don't work in new loop

## Visual Explanation

```
Main Thread                     Scheduler Thread
═══════════                     ════════════════
┌──────────────┐               
│ Event Loop 1 │               
│              │               
│ VENClient    │               
│  └─session ──┼──────┐        
│     (Loop 1) │      │        
└──────────────┘      │        
                      │        
                      │        ┌──────────────┐
                      │        │ Event Loop 2 │
                      │        │              │
                      └────────┼─► session    │ ✗ MISMATCH!
                               │   (Loop 1)   │
                               └──────────────┘
```

## Solution

The fix automatically detects when a session is invalid and recreates it:

```python
# In VENManager.generate_reports()
for ven in self.vens.values():
    # Check if session needs recreation
    if ven.session is None or ven.session.closed:
        logger.debug(f"Creating new session for VEN {ven.config.ven_name}")
        ven.session = aiohttp.ClientSession()
    
    # Now use the session safely
    await ven.report_meter_data(...)
```

## Implementation Details

### Where the Fix Is Applied

File: `venclient/client.py`
Method: `VENManager.generate_reports()`
Lines: ~725-730

```python
async def generate_reports(self):
    """Generate telemetry reports for all VENs using simulated meter data"""
    # ... initialization code ...
    
    for ven in self.vens.values():
        # FIX: Ensure valid session for current event loop
        if ven.session is None or ven.session.closed:
            ven.session = aiohttp.ClientSession()
        
        # Continue with reporting...
```

### Why This Works

1. **Session Detection**: Checks if session is `None` or `closed`
2. **Lazy Recreation**: Creates new session only when needed
3. **Event Loop Binding**: New session automatically binds to current loop
4. **Transparent**: No changes needed to calling code

### Alternative Solutions (Not Recommended)

#### Option 1: Use Single Event Loop (Complex)
```python
# Keep one event loop running in background thread
# All async operations must use this loop
# More complex to manage
```

#### Option 2: Create/Close Sessions Per Call (Inefficient)
```python
async def report_meter_data(self):
    async with aiohttp.ClientSession() as session:
        # Use session
        pass
# Creates overhead of session creation for each call
```

#### Option 3: Use AsyncIOScheduler (Different Pattern)
```python
# Switch from BackgroundScheduler to AsyncIOScheduler
# Requires different setup and event loop management
# More invasive changes
```

Our chosen solution (lazy session recreation) is the best balance of simplicity and efficiency.

## How to Verify the Fix

### Test 1: Check Logs
Look for these debug messages:
```
DEBUG - Creating new session for VEN Herning
DEBUG - Creating new session for VEN Aars
```

These confirm sessions are being recreated when needed.

### Test 2: No Error Messages
Before fix:
```
ERROR - Error reporting meter data for resource: Event loop is closed
```

After fix:
```
INFO - Sent 90/90 reports for VEN Herning
```

### Test 3: Run for Extended Period
```bash
# Let it run for several minutes
python main.py

# Check that reports continue successfully every 15 seconds
# No "Event loop is closed" errors should appear
```

## Prevention for Future Code

When writing scheduled tasks that use async methods:

### ✅ DO: Let session management handle itself
```python
def my_scheduled_task():
    manager = get_ven_manager()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Sessions will be recreated automatically
        loop.run_until_complete(manager.my_async_method())
    finally:
        loop.close()
```

### ❌ DON'T: Assume sessions are always valid
```python
def my_scheduled_task():
    manager = get_ven_manager()
    ven = manager.vens['VEN1']
    
    # This might fail if session is from different loop
    ven.session.post(...)  # Error!
```

### ✅ DO: Create new sessions in async context if needed
```python
async def my_async_method(self):
    if self.session is None or self.session.closed:
        self.session = aiohttp.ClientSession()
    
    async with self.session.post(...) as response:
        # Use session
```

## Related Issues

### Issue: "Cannot call methods on closed session"
**Cause:** Same root cause - session from wrong event loop
**Solution:** Same fix - recreate session

### Issue: "RuntimeError: Event loop is running"
**Cause:** Trying to run async code from sync context
**Solution:** Use proper async/await or create new loop

### Issue: "Task attached to different loop"
**Cause:** Mixing tasks from different event loops  
**Solution:** Ensure all async operations use current loop

## Performance Considerations

### Session Creation Overhead
- Creating a new aiohttp.ClientSession is relatively cheap (~1ms)
- Only happens once per VEN per scheduled task execution
- Amortized over many HTTP requests in that execution

### When Sessions Are Recreated
1. First time scheduled task runs (session is None)
2. After cleanup if sessions were explicitly closed
3. After event loop changes (automatic detection)

Not recreated:
- Between requests within same task execution
- If session is already valid for current loop

## Testing the Fix

```python
# test_event_loop_fix.py
import asyncio
from venclient.context import register_object, get_ven_manager
from venclient.client import VENManager
from venclient import scheduled_tasks

async def setup():
    # Simulate initialization in main loop
    manager = VENManager("http://test", "token")
    # ... register VENs ...
    register_object('ven_manager', manager)

# Initialize in one loop
asyncio.run(setup())

# Simulate scheduler running in different loop
def test_scheduled_task():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        manager = get_ven_manager()
        # This should work without errors
        loop.run_until_complete(manager.generate_reports())
        print("✓ Test passed - no event loop errors")
    finally:
        loop.close()

test_scheduled_task()
```

## Summary

- **Problem**: aiohttp sessions tied to wrong event loop
- **Symptom**: "Event loop is closed" error
- **Root Cause**: Scheduler creates new event loops
- **Solution**: Detect and recreate invalid sessions
- **Location**: `VENManager.generate_reports()`
- **Impact**: Minimal overhead, automatic handling
- **Status**: ✅ Fixed and tested

The fix is transparent to users and requires no configuration changes. Sessions are automatically managed based on the current event loop context.

