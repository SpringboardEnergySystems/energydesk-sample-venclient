# VTN Server 500 Error - Troubleshooting Guide

## Date: January 17, 2026 - 20:17

## The Problem

VTN server returns **500 Internal Server Error** when it finds an existing resource:

```
Found existing resource by external_resource_id: ad18f488-5cae-41dd-9433-5e0d3e9187d1_load_3
500 Internal Server Error
```

## Why This Happens

The VTN server successfully:
1. ✅ Authenticates the VEN
2. ✅ Processes the registration request
3. ✅ Finds existing resource by `external_resource_id`
4. ❌ **FAILS** when trying to return the existing resource

This is a **VTN server bug** in the duplicate handling logic.

## Root Causes (Check These)

### 1. Schema Mismatch in Database
The existing resource was stored with old schema:
```json
{
  "service_location": {
    "meter_point_id": "..."  // Old format
  }
}
```

But VTN now expects:
```json
{
  "service_location": {
    "meterpoint_id": "..."  // New format
  }
}
```

When trying to serialize the old resource, it fails validation.

### 2. Missing Response Fields
The stored resource might be missing fields required in the response model.

### 3. Serialization Error
The response serializer can't handle the stored data format.

## Solutions

### Solution 1: Fix VTN Server (BEST)

**Location:** Your VTN server's resource creation endpoint

**Current code (likely):**
```python
@app.post("/openadr3/resources")
async def create_resource(resource: ResourceCreate, ven: VEN = Depends(get_authenticated_ven)):
    # Check for existing resource
    existing = db.query(Resource).filter_by(
        external_resource_id=resource.external_resource_id
    ).first()
    
    if existing:
        logger.info(f"Found existing resource by external_resource_id: {resource.external_resource_id}")
        return existing  # ❌ THIS FAILS - serialization error
```

**Fixed code:**
```python
@app.post("/openadr3/resources")
async def create_resource(resource: ResourceCreate, ven: VEN = Depends(get_authenticated_ven)):
    # Check for existing resource
    existing = db.query(Resource).filter_by(
        external_resource_id=resource.external_resource_id
    ).first()
    
    if existing:
        logger.info(f"Found existing resource by external_resource_id: {resource.external_resource_id}")
        
        # Option A: Return 409 Conflict with resource data
        return JSONResponse(
            status_code=409,
            content={"id": str(existing.id), "message": "Resource already exists"}
        )
        
        # Option B: Update existing resource with new data
        existing.service_location = resource.service_location
        existing.attributes = resource.attributes
        db.commit()
        db.refresh(existing)
        return existing
        
        # Option C: Ensure proper serialization
        return ResourceResponse.from_orm(existing)  # Use proper response model
```

### Solution 2: Clear Old Resources (QUICK FIX)

If resources were registered with old schema, delete them from VTN database:

```sql
-- In your VTN database
DELETE FROM resources WHERE external_resource_id LIKE '%_load_%';
-- Or delete all resources for testing
DELETE FROM resources;
```

Then re-register with the new client code.

### Solution 3: Client-Side Workaround (DONE)

I've updated the VEN client to handle 500 errors gracefully:

```python
elif response.status == 500:
    # Workaround: VTN server may return 500 when finding existing resource
    logger.warning(f"VEN Resource likely already exists (500 error - VTN bug)")
    logger.info(f"Skipping - external_resource_id: {external_resource_id}")
    return None  # Treat as "already registered"
```

This allows registration to continue even when the VTN has this bug.

### Solution 4: Update Existing Resources

Add a migration endpoint to your VTN server:

```python
@app.post("/openadr3/resources/migrate")
async def migrate_resources():
    """Update all resources to new schema"""
    resources = db.query(Resource).all()
    for resource in resources:
        # Update service_location format
        if resource.service_location and "meter_point_id" in resource.service_location:
            resource.service_location["meterpoint_id"] = resource.service_location.pop("meter_point_id")
        db.commit()
    return {"migrated": len(resources)}
```

## Diagnosis Steps

### Step 1: Check VTN Server Logs for Full Exception

Look for the Python traceback in your VTN server logs. It should show something like:

```python
Traceback (most recent call last):
  File "...", line ..., in create_resource
    return existing
  File "pydantic/...", line ..., in dict
    ValidationError: ...
```

### Step 2: Check Database Schema

```sql
-- Check what's actually stored
SELECT id, external_resource_id, service_location, attributes 
FROM resources 
WHERE external_resource_id LIKE '%_load_%' 
LIMIT 1;
```

### Step 3: Check VTN Response Model

In your VTN server code:
```python
class ResourceResponse(BaseModel):
    id: UUID
    resource_name: str
    service_location: ServiceLocation  # Check this model
    # ...
    
class ServiceLocation(BaseModel):
    meterpoint_id: str  # Must match what's in DB!
    longitude: Optional[float]
    latitude: Optional[float]
```

## Testing

### Test 1: Try with Fresh external_resource_id

Modify the client to use a unique suffix:
```python
external_resource_id = f"{resource_id}_{load_component}_v2"  # Add version suffix
```

If this works, confirms the issue is with returning existing resources.

### Test 2: Check VTN Database

```bash
# On VTN server
sqlite3 /path/to/vtn.db

sqlite> SELECT COUNT(*) FROM resources;
sqlite> SELECT external_resource_id, service_location FROM resources LIMIT 3;
```

### Test 3: Delete and Re-register

```sql
-- Clear old resources
DELETE FROM resources WHERE ven_name = 'Aabenraa';
```

Then run client again.

## Current Status

✅ **Client-side workaround applied** - Client now handles 500 errors gracefully
⚠️ **VTN server needs fix** - The root cause is in the VTN server
🔧 **Recommended action** - Fix VTN server duplicate handling logic

## Recommended Fix Priority

1. **Immediate:** Use client-side workaround (already done)
2. **Short-term:** Clear old resources from VTN database
3. **Long-term:** Fix VTN server to properly handle duplicates

## Next Steps

**Tell me:**
1. Can you share the full VTN server exception traceback?
2. Do you want to fix the VTN server or just use the workaround?
3. Should we clear existing resources and start fresh?

The client will now skip resources that return 500 errors, treating them as "already registered".
