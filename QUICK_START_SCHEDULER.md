# Quick Reference: Scheduler Pattern with ApplicationContext

## Problem Solved
How to pass VENManager and MeterDataSimulator objects to scheduled task functions.

## Solution
**ApplicationContext Singleton Pattern** - Store objects in a global registry that tasks can access.

## Implementation in 3 Steps

### Step 1: Register Objects (in main.py)
```python
from venclient.context import register_object

# After creating your objects
manager = VENManager(vtn_url, token)
simulator = MeterDataSimulator()

# Register them
register_object('ven_manager', manager)
register_object('simulator', simulator)
```

### Step 2: Access Objects (in scheduled_tasks.py)
```python
from venclient.context import get_ven_manager, get_simulator

def my_scheduled_task():
    """Task function - no parameters needed!"""
    # Retrieve objects from context
    manager = get_ven_manager()
    simulator = get_simulator()
    
    # Check they exist
    if not manager or not simulator:
        logger.error("Objects not found")
        return
    
    # Use them
    stats = simulator.get_statistics()
    logger.info(f"Processing {stats['total_vens']} VENs")
```

### Step 3: Schedule Tasks (in main.py)
```python
from venclient.scheduler import SchedulerConfig, get_scheduler
from venclient import scheduled_tasks

scheduler = get_scheduler()

scheduler.add_task(SchedulerConfig(
    name="my_task",
    func=scheduled_tasks.my_scheduled_task,  # No need to pass parameters!
    trigger_type='interval',
    seconds=30
))

scheduler.start()
```

## Complete Example

```python
# main.py
import asyncio
from venclient.client import VENManager
from venclient.simulation.meterdata_simulator import MeterDataSimulator
from venclient.context import register_object
from venclient.scheduler import SchedulerConfig, get_scheduler
from venclient import scheduled_tasks

async def initialize():
    # Create objects
    manager = VENManager(vtn_base_url="http://localhost:8444/openadr3", 
                        bearer_token="token")
    simulator = MeterDataSimulator()
    
    # Initialize them
    await manager.register_load_ven("MyVEN")
    simulator.initialize_resources(["MyVEN"])
    
    # Register in context (THIS IS THE KEY!)
    register_object('ven_manager', manager)
    register_object('simulator', simulator)
    
    return manager, simulator

# Main
manager, simulator = asyncio.run(initialize())

# Configure scheduler
scheduler = get_scheduler()
scheduler.add_task(SchedulerConfig(
    name="advance_time",
    func=scheduled_tasks.simulate_meterdata,
    trigger_type='interval',
    seconds=30
))
scheduler.add_task(SchedulerConfig(
    name="send_reports", 
    func=scheduled_tasks.generate_reports_task,
    trigger_type='interval',
    seconds=15
))

# Start
scheduler.start()

# Keep running
while True:
    time.sleep(1)
```

```python
# scheduled_tasks.py
from venclient.context import get_ven_manager, get_simulator

def simulate_meterdata():
    """Advance simulation time"""
    simulator = get_simulator()
    if simulator:
        new_index = simulator.increase_time()
        logger.info(f"Advanced to index {new_index}")

def generate_reports_task():
    """Send reports to VTN"""
    manager = get_ven_manager()
    if manager:
        # Handle async in scheduled context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(manager.generate_reports())
        finally:
            loop.close()
```

## Key Points

✅ **No Parameter Passing** - Tasks are simple: `def task():`
✅ **Thread-Safe** - Singleton is safe across scheduler threads
✅ **Easy Testing** - Register mock objects in tests
✅ **Clean Code** - No complex wiring needed

## Common Patterns

### Pattern 1: Simple Synchronous Task
```python
def my_task():
    obj = get_object('my_obj')
    if obj:
        obj.do_something()
```

### Pattern 2: Async Task in Scheduler
```python
def my_async_task():
    manager = get_ven_manager()
    if manager:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(manager.async_method())
        finally:
            loop.close()
```

### Pattern 3: Access Any Registered Object
```python
from venclient.context import get_object

def my_task():
    custom_obj = get_object('custom_name')
    if custom_obj:
        custom_obj.do_work()
```

## Statistics Dictionary

**IMPORTANT:** Use correct keys when accessing statistics:

```python
stats = simulator.get_statistics()

# ✅ CORRECT
approved_count = stats['total_by_status']['APPROVED']
pending_count = stats['total_by_status']['PENDING']
ven_count = stats['total_vens']
total_resources = stats['total_resources']

# ❌ WRONG - These don't exist!
approved = stats['total_approved']  # KeyError!
pending = stats['total_pending']    # KeyError!
```

## Scheduler Configuration

### Interval-Based (every N time units)
```python
SchedulerConfig(
    name="my_task",
    func=my_function,
    trigger_type='interval',
    seconds=30        # or minutes=5, hours=1, etc.
)
```

### Cron-Based (specific times)
```python
SchedulerConfig(
    name="business_hours",
    func=my_function,
    trigger_type='cron',
    day_of_week='mon-fri',
    hour='9-17',
    minute='*/15'     # Every 15 minutes
)
```

## Debugging

### Check What's Registered
```python
from venclient.context import get_context

ctx = get_context()
print(f"Registered: {ctx.list_registered()}")
# Output: ['ven_manager', 'simulator']
```

### Check Scheduled Jobs
```python
scheduler = get_scheduler()
for job in scheduler.get_jobs():
    print(f"{job.name}: next run at {job.next_run_time}")
```

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Common Issues

### "Event loop is closed" Error

**Problem:** When scheduled tasks run in a new event loop, aiohttp sessions created in the original loop become invalid.

**Solution:** The `generate_reports()` method automatically recreates sessions when needed:
```python
# In VENManager.generate_reports()
if ven.session is None or ven.session.closed:
    ven.session = aiohttp.ClientSession()
```

**Why it happens:**
1. VENs are initialized in main event loop during `initialize_ven_system()`
2. Scheduler runs `generate_reports_task()` in a background thread
3. Background thread creates new event loop
4. Old sessions are tied to the original event loop → error

**Fixed automatically in the updated code!** ✅

## Testing Your Tasks

```python
# test_my_tasks.py
from venclient.context import register_object
from venclient import scheduled_tasks

# Create mock objects
class MockManager:
    def do_something(self):
        print("Manager called!")

# Register mocks
register_object('ven_manager', MockManager())

# Test task
scheduled_tasks.my_task()  # Should work!
```

## Summary

1. **Initialize objects** in main.py
2. **Register them** with `register_object()`
3. **Retrieve them** in tasks with `get_ven_manager()` or `get_simulator()`
4. **No parameters needed** in task functions
5. **Use correct stats keys**: `stats['total_by_status']['APPROVED']`

That's it! Simple, clean, and effective.

