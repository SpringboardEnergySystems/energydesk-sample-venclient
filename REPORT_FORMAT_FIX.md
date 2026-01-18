# Report Format Fix - 422 Validation Errors

## Problem
VTN server was rejecting reports with 422 status code and validation errors:
```
{"detail":[
  {"type":"missing","loc":["body","ven_id"],"msg":"Field required"},
  {"type":"enum","loc":["body","report_type"],"msg":"Input should be 'usage', 'demand', 'baseline' or 'deviation'","input":"READING"},
  {"type":"enum","loc":["body","reading_type"],"msg":"Input should be 'energy', 'power', 'state_of_charge', 'voltage' or 'frequency'","input":"DIRECT_READ"}
]}
```

## Root Cause
The report payload format didn't match the VTN server's API expectations:

### Issues Found
1. **Missing `ven_id`** - Required field was not included
2. **Wrong `report_type`** - Used `"READING"` instead of enum values
3. **Wrong `reading_type`** - Used `"DIRECT_READ"` instead of enum values

## Solution

### Updated Report Format

**Before (Incorrect):**
```python
report_data = {
    "report_name": f"{resource_name}_{timestamp}",
    "resource_id": resource_id,
    "client_name": self.config.client_name,
    "report_type": "READING",           # ❌ Invalid
    "reading_type": "DIRECT_READ",      # ❌ Invalid
    # Missing ven_id                    # ❌ Required field missing
    ...
}
```

**After (Correct):**
```python
report_data = {
    "report_name": f"{resource_name}_{timestamp}",
    "ven_id": self.credentials.ven_id,   # ✅ Required field added
    "resource_id": resource_id,
    "client_name": self.config.client_name,
    "report_type": "usage",              # ✅ Valid enum value
    "reading_type": "power",             # ✅ Valid enum value
    ...
}
```

## Valid Enum Values

### report_type
Must be one of:
- `"usage"` - Energy usage report
- `"demand"` - Demand report
- `"baseline"` - Baseline measurement
- `"deviation"` - Deviation from baseline

**We use**: `"usage"` (most appropriate for meter readings)

### reading_type
Must be one of:
- `"energy"` - Energy measurement (kWh)
- `"power"` - Power measurement (kW) ← **We use this**
- `"state_of_charge"` - Battery state
- `"voltage"` - Voltage measurement
- `"frequency"` - Frequency measurement

**We use**: `"power"` (matches our power readings in watts)

## Implementation

### File Changed
`venclient/client.py` - Method: `VENClient.report_meter_data()`

### Code Update
```python
async def report_meter_data(self, resource_id: str, resource_name: str, 
                           timestamp: int, power_w: float, 
                           load_id: str = None, program_id: str = None) -> bool:
    # ... timestamp conversion ...
    
    # Build report data according to VTN server's expected format
    report_data = {
        "report_name": f"{resource_name}_{timestamp}",
        "ven_id": self.credentials.ven_id if self.credentials else "unknown",  # ✅ Added
        "resource_id": resource_id,
        "client_name": self.config.client_name,
        "report_type": "usage",      # ✅ Fixed enum
        "reading_type": "power",     # ✅ Fixed enum
        "start": timestamp_iso,
        "duration": "PT0S",
        "intervals": [{
            "id": 0,
            "payloads": [{
                "type": "USAGE",
                "values": [power_w / 1000]  # kW
            }]
        }],
        "resources": [{
            "resource_name": resource_name
        }]
    }
    
    # Optional fields
    if program_id:
        report_data["program_id"] = program_id
    if load_id:
        report_data["load_component"] = load_id
    
    # Send to VTN
    async with self.session.post(f"{self.vtn_base_url}/reports", 
                                 json=report_data, headers=headers) as response:
        # Handle response...
```

## Complete Valid Report Example

```json
{
  "report_name": "Murphy's Pub_1737036000000",
  "ven_id": "ven-e4f2a1b3-5c6d-7e8f-9a0b-1c2d3e4f5a6b",
  "resource_id": "5249eada-69af-432d-99a5-98f9c89f9aa6",
  "client_name": "Client_Herning",
  "report_type": "usage",
  "reading_type": "power",
  "start": "2026-01-16T10:00:00",
  "duration": "PT0S",
  "intervals": [{
    "id": 0,
    "payloads": [{
      "type": "USAGE",
      "values": [1.234]
    }]
  }],
  "resources": [{
    "resource_name": "Murphy's Pub"
  }],
  "load_component": "load_0"
}
```

## Testing

### Before Fix
```
ERROR - Failed to report meter data for resource: 422 - {"detail":[...validation errors...]}
```

### After Fix
```
INFO  - Successfully reported meter data for Murphy's Pub (load_0): 1234.56W
INFO  - Sent 720/720 reports for VEN Herning
```

## How to Verify VTN API Requirements

If you encounter similar validation errors:

1. **Check VTN API Documentation**
   ```
   http://localhost:8444/openadr3/docs
   ```

2. **Look at Pydantic Error URLs**
   The error includes: `"url":"https://errors.pydantic.dev/2.12/v/missing"`
   This tells you it's a Pydantic validation error

3. **Check Error Details**
   ```json
   "loc":["body","ven_id"]  // Location of error
   "msg":"Field required"    // What's wrong
   ```

4. **Check Enum Values**
   ```json
   "ctx":{"expected":"'usage', 'demand', 'baseline' or 'deviation'"}
   ```

## Common Validation Errors

### Missing Required Field
```json
{"type":"missing","loc":["body","field_name"],"msg":"Field required"}
```
**Solution**: Add the required field to payload

### Invalid Enum Value
```json
{"type":"enum","loc":["body","field_name"],"msg":"Input should be 'a', 'b' or 'c'","input":"WRONG"}
```
**Solution**: Use one of the valid enum values

### Wrong Data Type
```json
{"type":"string_type","loc":["body","field_name"],"msg":"Input should be a valid string"}
```
**Solution**: Convert to correct type

### Invalid Format
```json
{"type":"datetime_parsing","loc":["body","start"],"msg":"Input should be a valid datetime"}
```
**Solution**: Use correct ISO format

## Prevention

To avoid future API mismatch issues:

1. **Generate API Client from OpenAPI Spec**
   ```python
   # Use openapi-generator or similar
   ```

2. **Use Type Hints and Validation**
   ```python
   from pydantic import BaseModel
   
   class ReportRequest(BaseModel):
       ven_id: str
       report_type: Literal["usage", "demand", "baseline", "deviation"]
       reading_type: Literal["energy", "power", "state_of_charge", "voltage", "frequency"]
   ```

3. **Test Against Real API**
   - Don't assume format
   - Check API docs
   - Test with curl first

4. **Log Full Requests**
   ```python
   logger.debug(f"Sending report: {json.dumps(report_data, indent=2)}")
   ```

## Summary

**Problem**: 422 validation errors due to incorrect report format
**Missing**: `ven_id` field
**Wrong Values**: `report_type="READING"`, `reading_type="DIRECT_READ"`
**Solution**: Added `ven_id`, changed to valid enum values (`"usage"`, `"power"`)
**Status**: ✅ **FIXED**

Reports should now be accepted by the VTN server!

