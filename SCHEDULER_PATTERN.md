# Scheduler Pattern and Object Reference Passing

## Overview

This document explains how to use the APScheduler-based task scheduler with proper object reference passing using the ApplicationContext singleton pattern.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                               │
│  1. Initialize VENManager & MeterDataSimulator              │
│  2. Register objects in ApplicationContext                   │
│  3. Configure TaskScheduler with tasks                       │
│  4. Start scheduler and run main loop                        │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              ApplicationContext (Singleton)                  │
│  Stores:                                                     │
│    - 'ven_manager': VENManager instance                     │
│    - 'simulator': MeterDataSimulator instance               │
│    - Any other shared objects                               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│           TaskScheduler (APScheduler wrapper)                │
│  Manages scheduled tasks:                                    │
│    - heartbeat_task (every 5 min)                           │
│    - simulate_meterdata (every 30 sec)                      │
│    - resource_status_checker (every 5 min)                  │
│    - generate_reports_task (every 15 sec)                   │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              scheduled_tasks.py                              │
│  Task functions that:                                        │
│    1. Retrieve objects from ApplicationContext              │
│    2. Perform their work                                    │
│    3. Handle errors gracefully                              │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. ApplicationContext (venclient/context.py)

**Purpose:** Singleton registry for sharing objects across scheduled tasks

**Key Features:**
- Thread-safe singleton pattern
- Simple get/set interface
- Convenience functions for common objects

**Usage:**
```python
from venclient.context import register_object, get_object, get_ven_manager, get_simulator

# Register objects (in main.py)
register_object('ven_manager', manager)
register_object('simulator', simulator)

# Retrieve objects (in scheduled tasks)
manager = get_ven_manager()
simulator = get_simulator()

# Or use generic access
manager = get_object('ven_manager')
```

### 2. TaskScheduler (venclient/scheduler.py)

**Purpose:** Wrapper around APScheduler's BackgroundScheduler

**Key Features:**
- Interval-based triggers (every N seconds/minutes/hours)
- Cron-based triggers (specific times/days)
- Job monitoring and error logging
- Pause/resume capabilities

**Configuration:**
```python
from venclient.scheduler import SchedulerConfig, get_scheduler

scheduler = get_scheduler()

# Interval-based task
scheduler.add_task(SchedulerConfig(
    name="my_task",
    func=my_function,
    trigger_type='interval',
    seconds=30  # Run every 30 seconds
))

# Cron-based task
scheduler.add_task(SchedulerConfig(
    name="business_hours_task",
    func=my_function,
    trigger_type='cron',
    day_of_week='mon-fri',
    hour='8-17',
    minute='*/15'  # Every 15 minutes during business hours
))
```

### 3. Scheduled Tasks (venclient/scheduled_tasks.py)

**Purpose:** Define the actual task functions

**Pattern:**
```python
def my_task():
    """Task that uses shared objects"""
    try:
        # 1. Retrieve objects from context
        manager = get_ven_manager()
        simulator = get_simulator()
        
        if not manager or not simulator:
            logger.error("Required objects not found in context")
            return
        
        # 2. Do your work
        stats = simulator.get_statistics()
        logger.info(f"Processing {stats['total_approved']} resources")
        
        # 3. Handle errors
    except Exception as e:
        logger.error(f"Task failed: {e}", exc_info=True)
```

## Implementation Pattern

### Step 1: Initialize Objects in main.py

```python
async def initialize_ven_system(vtn_url: str, bearer_token: str):
    """Setup VEN system and register in context"""
    from venclient.client import VENManager
    from venclient.simulation.meterdata_simulator import MeterDataSimulator
    from venclient.context import register_object
    
    # Create objects
    manager = VENManager(vtn_base_url=vtn_url, bearer_token=bearer_token)
    simulator = MeterDataSimulator()
    
    # Register VENs
    vens = load_vens_from_sqlite()
    for ven_id in vens:
        await manager.register_load_ven(ven_id)
    
    # Initialize simulator
    simulator.initialize_resources(vens)
    
    # Register in context (this is the key!)
    register_object('ven_manager', manager)
    register_object('simulator', simulator)
    
    return manager, simulator
```

### Step 2: Configure Scheduler

```python
def start_scheduler():
    """Configure scheduled tasks"""
    scheduler = get_scheduler()
    
    # Add tasks
    scheduler.add_task(SchedulerConfig(
        name="simulate_meterdata",
        func=scheduled_tasks.simulate_meterdata,
        trigger_type='interval',
        seconds=30
    ))
    
    scheduler.add_task(SchedulerConfig(
        name="generate_reports",
        func=scheduled_tasks.generate_reports_task,
        trigger_type='interval',
        seconds=15
    ))
    
    return scheduler
```

### Step 3: Run Main Loop

```python
if __name__ == '__main__':
    # Initialize system
    manager, simulator = asyncio.run(initialize_ven_system(vtn_url, token))
    
    # Start scheduler
    scheduler = start_scheduler()
    scheduler.start()
    
    # Keep running
    while True:
        time.sleep(1)
```

### Step 4: Define Scheduled Tasks

```python
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
        # APScheduler runs in thread, so create event loop for async
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(manager.generate_reports())
        finally:
            loop.close()
```

## Handling Async Tasks

APScheduler runs tasks in background threads, not in an event loop. For async functions:

### Pattern 1: Wrap in Synchronous Function

```python
def my_scheduled_task():
    """Synchronous wrapper for async work"""
    manager = get_ven_manager()
    
    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(manager.async_method())
    finally:
        loop.close()
```

### Pattern 2: Use AsyncIOScheduler (Alternative)

If you prefer native async support, you can switch to AsyncIOScheduler:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

class TaskScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
    
    # Now you can schedule async functions directly
    scheduler.add_job(
        async_function,
        trigger=IntervalTrigger(seconds=30)
    )
```

## Why This Pattern?

### ✅ Advantages

1. **No Parameter Passing**: Task functions don't need parameters
2. **Clean Function Signatures**: `def my_task():` not `def my_task(manager, simulator, ...)`
3. **Thread-Safe**: Singleton pattern is thread-safe
4. **Easy Testing**: Can register mock objects in tests
5. **Flexibility**: Easy to add new shared objects
6. **Decoupling**: Scheduled tasks don't depend on main.py structure

### ⚠️ Considerations

1. **Global State**: Objects are globally accessible (acceptable for singletons)
2. **Initialization Order**: Must register objects before scheduler starts
3. **Error Handling**: Tasks must handle missing objects gracefully

## Alternative Pattern: Functools Partial

If you prefer to pass objects as parameters, you can use `functools.partial`:

```python
from functools import partial

def my_task(manager, simulator):
    """Task that receives objects as parameters"""
    stats = simulator.get_statistics()
    logger.info(f"Got {stats['total_approved']} resources")

# In main.py
scheduler.add_task(SchedulerConfig(
    name="my_task",
    func=partial(my_task, manager, simulator),  # Bind parameters
    trigger_type='interval',
    seconds=30
))
```

**When to use:**
- Prefer explicit dependencies
- Testing with different instances
- Avoiding global state

**When NOT to use:**
- Objects are true singletons (VENManager, Simulator)
- Many tasks need same objects (lots of duplication)
- Complex parameter lists

## Complete Example

See `/Users/steinar/PycharmProjects/energydesk-sample-venclient/main.py` for the complete working example.

### Task Schedule

```
┌──────────────────────────────────────────────────────────────┐
│ Task                      │ Frequency        │ Purpose        │
├──────────────────────────────────────────────────────────────┤
│ heartbeat_task           │ Every 5 min      │ Health check   │
│ simulate_meterdata       │ Every 30 sec     │ Advance time   │
│ resource_status_checker  │ Every 5 min      │ Log statistics │
│ generate_reports_task    │ Every 15 sec     │ Send to VTN    │
└──────────────────────────────────────────────────────────────┘
```

## Testing

Test scheduled tasks independently:

```python
# test_scheduled_tasks.py
import asyncio
from venclient.context import register_object
from venclient.client import VENManager
from venclient.simulation.meterdata_simulator import MeterDataSimulator
from venclient import scheduled_tasks

async def test_tasks():
    # Setup context
    manager = VENManager(vtn_base_url="http://test", bearer_token="test")
    simulator = MeterDataSimulator()
    simulator.initialize_resources(["TestVEN"])
    
    register_object('ven_manager', manager)
    register_object('simulator', simulator)
    
    # Test tasks
    scheduled_tasks.simulate_meterdata()
    scheduled_tasks.resource_status_checker()
    scheduled_tasks.generate_reports_task()

asyncio.run(test_tasks())
```

## Debugging

Enable debug logging to see task execution:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Will show:
# - When tasks execute
# - What objects they retrieve
# - Any errors or warnings
```

Check registered objects:

```python
from venclient.context import get_context

ctx = get_context()
print(f"Registered: {ctx.list_registered()}")
```

## Summary

The **ApplicationContext singleton pattern** is recommended for this use case because:

1. VENManager and MeterDataSimulator are already singletons (Borg pattern)
2. Multiple scheduled tasks need access to the same instances
3. Tasks are simple functions without complex dependencies
4. The pattern is clean, testable, and maintainable

This approach follows the same pattern used by the MeterDataSimulator itself (Borg pattern) and provides a consistent way to share state across scheduled tasks.

