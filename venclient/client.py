"""
OpenADR 3.0.1 VEN Client Application
Creates multiple VEN instances and manages their interactions with the VTN server
"""
import traceback

import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import random
import time
import threading
import environ
import os
from .utils import get_environment_value, camel_to_snake, get_access_token
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

import re



# Enums for OpenADR 3.0.1
class EventStatus(str, Enum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ResponseType(str, Enum):
    OPT_IN = "optIn"
    OPT_OUT = "optOut"
    NOT_PARTICIPATING = "notParticipating"

class ReportType(str, Enum):
    USAGE = "usage"
    DEMAND = "demand"
    BASELINE = "baseline"
    DEVIATION = "deviation"

class ResourceType(str, Enum):
    ENERGY = "energy"
    POWER = "power"
    STATE_OF_CHARGE = "state_of_charge"  # Added type
    VOLTAGE = "voltage"  # Added type
    FREQUENCY = "frequency"  # Added type



@dataclass
class VENConfig:
    ven_name: str
    client_name: str

@dataclass
class VENResource:
    resource_id: str
    resource_name: str
    resource_type: str
    attributes: List[Dict]

@dataclass
class VENCredentials:
    ven_id: str
    ven_name: str
    auth_token: str


@dataclass
class EventData:
    id: str
    event_name: str
    program_id: str
    start_date: str
    end_date: str
    status: str
    modification_number: int

@dataclass
class VTNProgram:
    id: str
    event_name: str
    program_id: str
    start_date: str
    end_date: str
    status: str
    modification_number: int

class VENClient:
    """Individual VEN client that manages a single VEN instance"""

    def __init__(self, config: VENConfig, vtn_base_url: str = "http://localhost:8000",
                 bearer_token: str = None, vtn_api_prefix: str = None):
        self.config = config
        self.bearer_token = bearer_token
        self.vtn_base_url = vtn_base_url.rstrip("/")

        # API prefix: argument > env var > default "/openadr3"
        if vtn_api_prefix is None:
            vtn_api_prefix = os.environ.get("VTN_API_PREFIX", "/openadr3")
        self.vtn_api_prefix = "/" + vtn_api_prefix.strip("/")  # normalise slashes

        # All API calls use this as their base
        self.vtn_api_url = self.vtn_base_url + self.vtn_api_prefix

        self.credentials: Optional[VENCredentials] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.active_events: Dict[str, EventData] = {}
        self.reports: List[Dict] = []
        self.resources: Dict[str, VENResource] = {}
        logger.info(
            f"Initializing VEN client for {self.config.ven_name} "
            f"with VTN at {self.vtn_api_url} and bearer token: {self.bearer_token}"
        )

    async def close_session(self):
        """Close the aiohttp session if open. Call before asyncio.run() returns."""
        if self.session and not self.session.closed:
            await self.session.close()
        self.session = None

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            self.session = None

    async def _ensure_session(self):
        """Create a fresh aiohttp session bound to the current event loop.

        asyncio.run() closes the loop after each call, so any session created
        in a previous run is unusable.  We detect that and replace it.
        """
        loop = asyncio.get_event_loop()
        needs_new = (
            self.session is None
            or self.session.closed
            or getattr(self.session, "_loop", loop) is not loop
        )
        if needs_new:
            if self.session and not self.session.closed:
                await self.session.close()
            self.session = aiohttp.ClientSession()

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API calls"""
        if not self.credentials:
            raise ValueError("VEN not registered. Call register() first.")
        return {
            "Authorization": f"Bearer {self.credentials.auth_token}",
            "Content-Type": "application/json"
        }


    async def register_ven_resource(self, resource_config: VENResource, external_resource_id: str = None,
                                   service_location: dict = None) -> Optional[str]:
        """
        Register a VEN resource with the VTN server.

        Args:
            resource_config: Resource configuration
            external_resource_id: External resource identifier (resource_id + load_component)
            service_location: Service location dict with meter_point_id, longitude, latitude

        Returns:
            VTN-assigned resource ID if successful, None otherwise
        """
        try:
            await self._ensure_session()
            registration_data = {
                "id": resource_config.resource_id,
                "resource_name": resource_config.resource_name,
                "resource_type": resource_config.resource_type,
                "ven_name": self.config.ven_name,
                "attributes": resource_config.attributes
            }

            # Add external_resource_id if provided
            if external_resource_id:
                registration_data["external_resource_id"] = external_resource_id

            # Add service_location if provided
            if service_location:
                registration_data["service_location"] = service_location

            headers = {'Authorization': 'Bearer ' + self.bearer_token}
            async with self.session.post(
                f"{self.vtn_api_url}/resources",
                json=registration_data,
                headers=headers
            ) as response:
                if response.status == 201:
                    data = await response.json()
                    vtn_resource_id = data.get("id")
                    logger.info(f"Successfully registered VEN Resource: {resource_config.resource_name} -> VTN ID: {vtn_resource_id}")
                    return vtn_resource_id
                elif response.status == 409:
                    logger.warning(f"VEN Resource {resource_config.resource_name} already exists (409)")
                    # Try to get existing resource ID from response
                    try:
                        data = await response.json()
                        return data.get("id")
                    except:
                        return None
                elif response.status == 500:
                    # Workaround: VTN server may return 500 when finding existing resource
                    error_text = await response.text()
                    if "existing resource" in error_text.lower() or external_resource_id:
                        logger.warning(f"VEN Resource {resource_config.resource_name} likely already exists (500 error - VTN bug)")
                        # Try to fetch the resource by external_resource_id to get its VTN ID
                        # For now, log and return None - resource exists but we can't get its ID
                        logger.info(f"Skipping - external_resource_id: {external_resource_id}")
                        return None  # Treat as "already registered"
                    else:
                        logger.error(f"Failed to register VEN Resource {resource_config.resource_name}: {error_text}")
                        return None
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to register VEN Resource {resource_config.resource_name}: {error_text}")
                    return None

        except Exception as e:
            logger.error(f"Error registering Resource {resource_config.resource_name}: {str(e)}")
            return None

    async def register_ven(self) -> bool:
        """Register this VEN with the VTN server"""
        try:
            await self._ensure_session()
            registration_data = {
                "ven_name": self.config.ven_name,
                "client_name": self.config.client_name
            }
            print(registration_data, self.bearer_token)
            headers = {'Authorization': 'Bearer ' + self.bearer_token}
            async with self.session.post(
                f"{self.vtn_api_url}/vens",
                json=registration_data,
                headers=headers
            ) as response:
                if response.status == 201:
                    data = await response.json()
                    self.credentials = VENCredentials(
                        ven_id=data["id"],
                        ven_name=data["ven_name"],
                        auth_token=data["auth_token"]
                    )
                    logger.info(f"Successfully registered VEN: {self.config.ven_name}")
                    return True
                elif response.status == 409:
                    logger.warning(f"VEN {self.config.ven_name} already exists")

                    return False
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to register VEN {self.config.ven_name}: {error_text}")
                    return False

        except Exception as e:
            logger.error(f"Error registering VEN {self.config.ven_name}: {str(e)}")
            return False



    async def poll_events(self) -> List[EventData]:
        """Poll for new events from the VTN"""
        try:
            await self._ensure_session()
            logger.info(f"Polling for events for {self.vtn_api_url}/events")
            async with self.session.get(
                f"{self.vtn_api_url}/events",
                headers=self._get_auth_headers()
            ) as response:
                print(response.status)
                if response.status == 200:
                    events_data = await response.json()
                    events = []
                    for event_data in events_data:
                        event = EventData(
                            id=event_data["id"],
                            event_name=event_data["event_name"],
                            program_id=event_data["program_id"],
                            start_date=event_data["start_date"],
                            end_date=event_data["end_date"],
                            status=event_data["status"],
                            modification_number=event_data["modification_number"]
                        )
                        events.append(event)

                        # Update active events tracking
                        if event.id not in self.active_events:
                            self.active_events[event.id] = event
                            logger.info(f"New event received by {self.config.ven_name}: {event.event_name}")

                    return events
                else:
                    logger.error(f"Failed to poll events for {self.config.ven_name}: {response.status}")
                    return []

        except Exception as e:
            print(e)
            logger.error(f"Error polling events for {self.config.ven_name}: {str(e)}")
            return []

    async def respond_to_event(self, event_id: str, response_type: ResponseType) -> bool:
        """Respond to a demand response event"""
        try:
            await self._ensure_session()
            response_data = {
                "event_id": event_id,
                "response_type": response_type.value
            }

            async with self.session.post(
                f"{self.vtn_api_url}/events/{event_id}/responses",
                json=response_data,
                headers=self._get_auth_headers()
            ) as response:
                if response.status == 201:
                    logger.info(f"{self.config.ven_name} responded to event {event_id} with {response_type.value}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to respond to event {event_id} for {self.config.ven_name}: {error_text}")
                    return False

        except Exception as e:
            logger.error(f"Error responding to event {event_id} for {self.config.ven_name}: {str(e)}")
            return False

    async def create_report(self, program_id: str, report_type: ReportType, reading_type: ResourceType) -> bool:
        """Create a telemetry report"""
        try:
            await self._ensure_session()
            report_data = {
                "report_name": f"{self.config.ven_name}_{report_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "program_id": program_id,
                "ven_id": self.credentials.ven_id,
                "report_type": report_type.value,
                "reading_type": reading_type.value,
                "interval_period": "PT15M"  # 15-minute intervals
            }

            async with self.session.post(
                f"{self.vtn_api_url}/reports",
                json=report_data,
                headers=self._get_auth_headers()
            ) as response:
                if response.status == 201:
                    report_info = await response.json()
                    self.reports.append(report_info)
                    logger.info(f"{self.config.ven_name} created {report_type.value} report")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to create report for {self.config.ven_name}: {error_text}")
                    return False

        except Exception as e:
            logger.error(f"Error creating report for {self.config.ven_name}: {str(e)}")
            return False

    async def list_programs(self) -> List[Dict]:
        """
        Fetch all OpenADR programs available on the VTN.

        Returns:
            List of program dicts (matching ProgramResponse schema) or [] on error.
        """
        try:
            await self._ensure_session()
            headers = {"Authorization": f"Bearer {self.bearer_token}"}
            async with self.session.get(
                f"{self.vtn_api_url}/programs",
                headers=headers,
            ) as response:
                if response.status == 200:
                    programs = await response.json()
                    logger.info(f"Fetched {len(programs)} program(s) from VTN")
                    return programs
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to list VTN programs: {response.status} - {error_text}")
                    return []
        except Exception as e:
            logger.error(f"Error listing VTN programs: {str(e)}")
            return []

    async def enroll_resource(self, vtn_program_id: str, vtn_resource_id: str) -> bool:
        """
        Enroll a resource (by its VTN resource ID) into a program on the VTN.

        Calls:  POST /programs/{vtn_program_id}/resources?resource_id={vtn_resource_id}

        Returns True if enrolled (201) or already enrolled (409), False on error.
        """
        try:
            await self._ensure_session()
            headers = {"Authorization": f"Bearer {self.bearer_token}"}
            url = f"{self.vtn_api_url}/programs/{vtn_program_id}/resources"
            params = {"resource_id": vtn_resource_id}
            async with self.session.post(url, params=params, headers=headers) as response:
                if response.status == 201:
                    logger.info(
                        f"Enrolled resource {vtn_resource_id} in program {vtn_program_id}"
                    )
                    return True
                elif response.status == 409:
                    logger.info(
                        f"Resource {vtn_resource_id} already enrolled in program {vtn_program_id} (409)"
                    )
                    return True  # Treat as success – idempotent
                else:
                    error_text = await response.text()
                    logger.error(
                        f"Failed to enroll resource {vtn_resource_id} in program "
                        f"{vtn_program_id}: {response.status} - {error_text}"
                    )
                    return False
        except Exception as e:
            logger.error(f"Error enrolling resource {vtn_resource_id}: {str(e)}")
            return False

    async def report_meter_data(self, resource_id: str, resource_name: str, timestamp: int,
                               power_w: float, load_id: str = None, program_id: str = None) -> bool:
        """
        Report meter data for a specific resource to the VTN server.

        Args:
            resource_id: Unique identifier for the resource
            resource_name: Human-readable name of the resource
            timestamp: Unix timestamp in milliseconds
            power_w: Power reading in watts
            load_id: Optional load component identifier (e.g., 'load_0')
            program_id: Optional program identifier (not required for general meter readings)

        Returns:
            True if report was successfully sent, False otherwise
        """
        try:
            await self._ensure_session()
            # Convert timestamp from milliseconds to ISO format
            timestamp_dt = datetime.fromtimestamp(timestamp / 1000)
            timestamp_iso = timestamp_dt.isoformat()

            # Build report data according to VTN server's expected format
            report_data = {
                "report_name": f"{resource_name}_{timestamp}",
                "ven_id": self.credentials.ven_id if self.credentials else "unknown",  # Required field
                "resource_id": resource_id,
                "client_name": self.config.client_name,
                "report_type": "usage",  # Must be: 'usage', 'demand', 'baseline' or 'deviation'
                "reading_type": "power",  # Must be: 'energy', 'power', 'state_of_charge', 'voltage' or 'frequency'
                "start": timestamp_iso,
                "duration": "PT0S",  # Instantaneous reading
                "intervals": [{
                    "id": 0,
                    "payloads": [{
                        "type": "USAGE",
                        "values": [power_w / 1000]  # Convert watts to kilowatts
                    }]
                }],
                "resources": [{
                    "resource_name": resource_name
                }]
            }

            # Add program_id only if provided
            if program_id:
                report_data["program_id"] = program_id

            # Add load component information if provided
            if load_id:
                report_data["load_component"] = load_id

            headers = {'Authorization': f'Bearer {self.bearer_token}', 'Content-Type': 'application/json'}

            async with self.session.post(
                f"{self.vtn_api_url}/reports",
                json=report_data,
                headers=headers
            ) as response:
                if response.status in [200, 201]:
                    logger.debug(f"Successfully reported meter data for {resource_name} ({load_id or 'aggregate'}): {power_w:.2f}W")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to report meter data for {resource_name}: {response.status} - {error_text}")
                    return False

        except Exception as e:
            error_msg = str(e)
            # Add more context for event loop errors
            if "Event loop is closed" in error_msg or "attached to a different loop" in error_msg:
                logger.error(f"Event loop error reporting meter data for {resource_name}: {error_msg}")
                logger.debug(f"  Session state: closed={getattr(self.session, 'closed', 'unknown')}")
                logger.debug(f"  Try recreating the session in generate_reports()")
            else:
                logger.error(f"Error reporting meter data for {resource_name}: {error_msg}")
            return False




async def load_and_register_resources(client: VENClient):
    """
    Load FlexibleResources (with their MeterConnections) from the local DB
    and register each one with the VTN via register_ven_resource().

    - Builds a VENResource with attributes mirroring resource_sample.json.
    - If vtn_resource_id is already set the VTN has seen this resource before;
      pass it as external_resource_id so the VTN avoids creating a duplicate.
    - Passes longitude/latitude as an explicit service_location dict.
    """
    if client is None:
        raise ValueError("VENClient cannot be None")

    # Import here to avoid circular imports at module level
    from venserver.datamodel.database import SessionLocal
    from venserver.datamodel.models import FlexibleResource, VTNRegistrationStatus

    db = SessionLocal()
    try:
        resources = (
            db.query(FlexibleResource)
            .filter(FlexibleResource.is_active == True)
            .all()
        )
        logger.info(f"Found {len(resources)} active FlexibleResource(s) in local DB")

        for res in resources:
            mc = res.meter_connection  # joined via relationship

            # ── Build attribute list matching resource_sample.json structure ──
            resource_id_str = str(res.id)
            attributes = []

            # meter_point_id (from MeterConnection)
            if mc and mc.meterpoint_id:
                attributes.append({
                    "resource_id": resource_id_str,
                    "attribute_name": "meter_point_id",
                    "attribute_type": "meter_point_id",
                    "attribute_values": [mc.meterpoint_id],
                })

            # connection type – always modbus for RPI deployments
            attributes.append({
                "resource_id": resource_id_str,
                "attribute_name": "connection",
                "attribute_type": "connection",
                "attribute_values": ["modbus"],
            })

            # power limits
            if res.max_power_kw is not None:
                attributes.append({
                    "resource_id": resource_id_str,
                    "attribute_name": "p_max_kw",
                    "attribute_type": "p_max_kw",
                    "attribute_values": [str(res.max_power_kw)],
                })
            if res.min_power_kw is not None:
                attributes.append({
                    "resource_id": resource_id_str,
                    "attribute_name": "p_min_kw",
                    "attribute_type": "p_min_kw",
                    "attribute_values": [str(res.min_power_kw)],
                })

            # energy capacity (batteries / storage)
            if res.energy_capacity_kwh is not None:
                attributes.append({
                    "resource_id": resource_id_str,
                    "attribute_name": "e_max_kwh",
                    "attribute_type": "e_max_kwh",
                    "attribute_values": [str(res.energy_capacity_kwh)],
                })
                attributes.append({
                    "resource_id": resource_id_str,
                    "attribute_name": "e_min_kwh",
                    "attribute_type": "e_min_kwh",
                    "attribute_values": ["0.0"],
                })

            # address (from MeterConnection)
            if mc and mc.full_address:
                attributes.append({
                    "resource_id": resource_id_str,
                    "attribute_name": "address",
                    "attribute_type": "address",
                    "attribute_values": [mc.full_address],
                })

            # latitude / longitude (from MeterConnection)
            if mc and mc.location_latitude is not None:
                attributes.append({
                    "resource_id": resource_id_str,
                    "attribute_name": "latitude",
                    "attribute_type": "latitude",
                    "attribute_values": [str(mc.location_latitude)],
                })
            if mc and mc.location_longitude is not None:
                attributes.append({
                    "resource_id": resource_id_str,
                    "attribute_name": "longitude",
                    "attribute_type": "longitude",
                    "attribute_values": [str(mc.location_longitude)],
                })

            # enabled / status
            attributes.append({
                "resource_id": resource_id_str,
                "attribute_name": "enabled",
                "attribute_type": "enabled",
                "attribute_values": [str(res.is_active)],
            })
            attributes.append({
                "resource_id": resource_id_str,
                "attribute_name": "status",
                "attribute_type": "prequalification",
                "attribute_values": [res.vtn_registration_status.value.upper()],
            })

            # ── Build VENResource dataclass ────────────────────────────────
            ven_resource = VENResource(
                resource_id=res.resource_external_id,
                resource_name=res.description or res.resource_external_id,
                resource_type=res.resource_type.value,
                attributes=attributes,
            )

            # ── external_resource_id: use vtn_resource_id if already known ──
            external_resource_id = res.vtn_resource_id if res.vtn_resource_id else None

            # ── service_location: explicit lat/lon + meterpoint_id ──────────
            service_location = None
            if mc and mc.meterpoint_id:
                service_location = {
                    "meterpoint_id": mc.meterpoint_id,
                    "latitude": mc.location_latitude,
                    "longitude": mc.location_longitude,
                    "address": mc.full_address if hasattr(mc, 'full_address') else None,
                }

            logger.info(
                f"Registering resource '{ven_resource.resource_name}' "
                f"(external_id={external_resource_id or 'new'}) with VTN..."
            )
            vtn_id = await client.register_ven_resource(
                ven_resource,
                external_resource_id=external_resource_id,
                service_location=service_location,
            )

            # ── Persist the VTN-assigned ID back to local DB if we got one ──
            if vtn_id and vtn_id != res.vtn_resource_id:
                res.vtn_resource_id = vtn_id
                res.vtn_registration_status = VTNRegistrationStatus.REGISTERED
                res.vtn_last_sync = datetime.utcnow()
                db.commit()
                logger.info(f"  ✓ VTN ID '{vtn_id}' saved for resource '{ven_resource.resource_name}'")
            elif vtn_id is None and res.vtn_resource_id is None:
                # Registration failed for a brand-new resource
                res.vtn_registration_status = VTNRegistrationStatus.FAILED
                db.commit()
                logger.warning(f"  ✗ Registration failed for '{ven_resource.resource_name}'")

    except Exception:
        logger.exception("Error in load_and_register_resources")
        db.rollback()
    finally:
        db.close()
        # Close the HTTP session so asyncio.run() can cleanly shut down the loop.
        # A fresh session will be created on the next asyncio.run() call.
        await client.close_session()

async def retrieve_vtn_programs(client: VENClient):
    """
    Fetch all programs from the VTN and upsert them into the local ``vtn_programs`` table.
    New programs are inserted; existing ones (matched by vtn_id) are updated.
    """
    if client is None:
        raise ValueError("VENClient cannot be None")

    from venserver.datamodel.database import SessionLocal
    from venserver.datamodel.models import VTNProgram

    programs_data = await client.list_programs()
    if not programs_data:
        logger.info("[PROGRAM_SYNC] No programs returned from VTN (or error)")
        await client.close_session()
        return

    db = SessionLocal()
    try:
        import json as _json
        added = 0
        updated = 0
        for p in programs_data:
            vtn_id = p.get("id")
            if not vtn_id:
                continue

            def _dt(val):
                if not val:
                    return None
                from datetime import datetime as _dtcls
                try:
                    return _dtcls.fromisoformat(val.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    return None

            existing = db.query(VTNProgram).filter(VTNProgram.vtn_id == vtn_id).first()
            if existing:
                obj = existing
                updated += 1
            else:
                obj = VTNProgram(vtn_id=vtn_id)
                db.add(obj)
                added += 1

            obj.program_id             = p.get("program_id")
            obj.program_name           = p.get("program_name", "")
            obj.program_long_name      = p.get("program_long_name")
            obj.program_type           = p.get("program_type")
            obj.program_priority       = p.get("program_priority", 0)
            obj.state                  = p.get("state", "PENDING")
            obj.program_issuer         = p.get("program_issuer")
            obj.retailer_name          = p.get("retailer_name")
            obj.retailer_long_name     = p.get("retailer_long_name")
            obj.effective_start_date   = _dt(p.get("effective_start_date"))
            obj.effective_end_date     = _dt(p.get("effective_end_date"))
            obj.program_period_start   = _dt(p.get("program_period_start"))
            obj.program_period_end     = _dt(p.get("program_period_end"))
            obj.enrollment_period_start = _dt(p.get("enrollment_period_start"))
            obj.enrollment_period_end  = _dt(p.get("enrollment_period_end"))
            obj.created_date           = _dt(p.get("created_date"))
            obj.modification_date_time = _dt(p.get("modification_date_time"))
            obj.country                = p.get("country")
            obj.principal_subdivision  = p.get("principal_subdivision")
            obj.timezone               = p.get("timezone", "UTC")
            obj.market_context         = p.get("market_context")
            obj.participation_type     = p.get("participation_type")
            obj.notification_time      = p.get("notification_time")
            obj.call_heads_up_time     = p.get("call_heads_up_time")
            obj.interval_period        = p.get("interval_period", "PT1H")
            obj.interval_period_duration = p.get("interval_period_duration")
            obj.interruptible          = bool(p.get("interruptible", False))
            obj.raw_json               = _json.dumps(p)
            obj.last_synced_at         = datetime.utcnow()

        db.commit()
        logger.info(f"[PROGRAM_SYNC] Done – {added} added, {updated} updated")
    except Exception:
        logger.exception("Error in retrieve_vtn_programs")
        db.rollback()
    finally:
        db.close()
        await client.close_session()




async def enroll_vtn_programs(client: VENClient):
    """
    For every VTNProgramEnrollment row whose status is PENDING, call the VTN
    POST /programs/{vtn_program_id}/resources?resource_id={vtn_resource_id}
    endpoint and update the local status to ENROLLED or FAILED.

    Only resources that already have a vtn_resource_id (i.e. registered with the
    VTN) can be enrolled — others are skipped with a warning.
    """
    if client is None:
        raise ValueError("VENClient cannot be None")

    from venserver.datamodel.database import SessionLocal
    from venserver.datamodel.models import (
        VTNProgram,
        VTNProgramEnrollment,
        VTNProgramEnrollmentStatus,
        FlexibleResource,
    )

    db = SessionLocal()
    try:
        # Fetch all enrollments the user has requested but not yet confirmed
        pending = (
            db.query(VTNProgramEnrollment)
            .filter(VTNProgramEnrollment.status == VTNProgramEnrollmentStatus.PENDING.value)
            .all()
        )

        if not pending:
            logger.info("[ENROLL_SYNC] No pending program enrollments to process")
            return

        logger.info(f"[ENROLL_SYNC] Processing {len(pending)} pending enrollment(s)")

        for enrollment in pending:
            # Resolve the VTN program UUID
            program = db.query(VTNProgram).filter(VTNProgram.id == enrollment.program_id).first()
            if not program or not program.vtn_id:
                logger.warning(
                    f"[ENROLL_SYNC] Program {enrollment.program_id} has no vtn_id – skipping"
                )
                continue

            # Resolve the local resource and its VTN resource ID
            resource = db.query(FlexibleResource).filter(
                FlexibleResource.id == enrollment.resource_id
            ).first()
            if not resource:
                logger.warning(
                    f"[ENROLL_SYNC] Resource {enrollment.resource_id} not found – skipping"
                )
                continue

            if not resource.vtn_resource_id:
                logger.warning(
                    f"[ENROLL_SYNC] Resource '{resource.description or resource.resource_external_id}' "
                    f"has no vtn_resource_id yet – cannot enroll until it is registered with the VTN"
                )
                continue

            logger.info(
                f"[ENROLL_SYNC] Enrolling resource '{resource.description or resource.resource_external_id}' "
                f"(VTN ID: {resource.vtn_resource_id}) into program '{program.program_name}' "
                f"(VTN ID: {program.vtn_id})"
            )

            success = await client.enroll_resource(
                vtn_program_id=program.vtn_id,
                vtn_resource_id=resource.vtn_resource_id,
            )

            if success:
                enrollment.status = VTNProgramEnrollmentStatus.ENROLLED.value
                enrollment.enrolled_at = datetime.utcnow()
                logger.info(
                    f"[ENROLL_SYNC]  ✓ Enrolled '{resource.description or resource.resource_external_id}' "
                    f"in '{program.program_name}'"
                )
            else:
                enrollment.status = VTNProgramEnrollmentStatus.FAILED.value
                logger.warning(
                    f"[ENROLL_SYNC]  ✗ Enrollment failed for "
                    f"'{resource.description or resource.resource_external_id}' "
                    f"in '{program.program_name}'"
                )

        db.commit()
        logger.info("[ENROLL_SYNC] Done")

    except Exception:
        logger.exception("Error in enroll_vtn_programs")
        db.rollback()
    finally:
        db.close()


def report_metervalues(client: VENClient, lookback_days: int = 500):
    """
    For every FlexibleResource that has been registered with the VTN
    (vtn_registration_status == REGISTERED and vtn_resource_id is set),
    query InfluxDB for the last ``lookback_days`` of hourly p_kw telemetry
    and forward each reading to the VTN via client.report_meter_data().

    The InfluxDB query filters on:
        measurement = "telemetry"
        device      = resource.resource_external_id   (e.g. "BATT-STE")

    Each InfluxDB record returns:
        record["time"]  – ISO-8601 string (UTC)
        record["value"] – p_kw (float)
    which is converted to watts (×1000) before calling report_meter_data.
    """
    if client is None:
        raise ValueError("VENClient cannot be None")

    import os
    from venserver.datamodel.database import SessionLocal
    from venserver.datamodel.models import FlexibleResource, VTNRegistrationStatus
    from influxdb_client import InfluxDBClient

    # ── resolve InfluxDB settings from environment ─────────────────────────
    influx_url    = os.getenv("INFLUXDB_URL",    "http://localhost:8086")
    influx_token  = os.getenv("INFLUXDB_TOKEN",  "mytoken")
    influx_org    = os.getenv("INFLUXDB_ORG",    "myorg")
    influx_bucket = os.getenv("INFLUXDB_BUCKET", "mybucket")

    db = SessionLocal()
    try:
        # Only process resources that the VTN has confirmed
        approved = (
            db.query(FlexibleResource)
            .filter(
                FlexibleResource.vtn_registration_status == VTNRegistrationStatus.REGISTERED,
                FlexibleResource.vtn_resource_id.isnot(None),
                FlexibleResource.is_active == True,
            )
            .all()
        )

        if not approved:
            logger.info("[REPORT_VALUES] No VTN-approved resources found – nothing to report")
            return

        logger.info(f"[REPORT_VALUES] Found {len(approved)} approved resource(s) to report")

        influx_client = InfluxDBClient(
            url=influx_url, token=influx_token, org=influx_org
        )

        for res in approved:
            device_id = res.resource_external_id   # e.g. "BATT-STE"
            logger.info(
                f"[REPORT_VALUES] Querying InfluxDB for device='{device_id}' "
                f"(last {lookback_days} days) …"
            )

            # Build Flux query – 1-hour aggregation windows, filter by device tag
            flux = (
                f'from(bucket: "{influx_bucket}")\n'
                f'  |> range(start: -{lookback_days}d)\n'
                f'  |> filter(fn: (r) => r["_measurement"] == "telemetry")\n'
                f'  |> filter(fn: (r) => r["device"] == "{device_id}")\n'
                f'  |> filter(fn: (r) => r["_field"] == "p_kw")\n'
                f'  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)\n'
                f'  |> yield(name: "mean")'
            )

            try:
                tables = influx_client.query_api().query(flux, org=influx_org)
            except Exception as e:
                logger.error(f"[REPORT_VALUES] InfluxDB query failed for '{device_id}': {e}")
                continue

            records = [
                (record.get_time(), record.get_value())
                for table in tables
                for record in table.records
                if record.get_value() is not None
            ]

            if not records:
                logger.warning(
                    f"[REPORT_VALUES] No InfluxDB data found for device='{device_id}' "
                    f"in the last {lookback_days} days"
                )
                continue

            logger.info(
                f"[REPORT_VALUES] Reporting {len(records)} readings for "
                f"'{device_id}' (VTN resource id: {res.vtn_resource_id})"
            )

            async def _send_all(resource=res, device=device_id, rows=records):
                reported = 0
                failed   = 0
                for ts, p_kw in rows:
                    ts_ms  = int(ts.timestamp() * 1000)
                    p_watt = p_kw * 1000.0
                    ok = await client.report_meter_data(
                        resource_id   = resource.vtn_resource_id,
                        resource_name = resource.description or device,
                        timestamp     = ts_ms,
                        power_w       = p_watt,
                        load_id       = None,
                        program_id    = resource.vtn_program_id,
                    )
                    if ok:
                        reported += 1
                    else:
                        failed += 1
                # Close the session so asyncio.run() can cleanly exit;
                # _ensure_session() will open a fresh one on the next call.
                await client.close_session()
                return reported, failed

            reported, failed = asyncio.run(_send_all())
            logger.info(
                f"[REPORT_VALUES] '{device_id}': {reported} reported, {failed} failed"
            )

        influx_client.close()

    except Exception:
        logger.exception("[REPORT_VALUES] Unexpected error in report_metervalues")
    finally:
        db.close()

