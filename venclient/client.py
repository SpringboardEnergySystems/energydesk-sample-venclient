"""
OpenADR 3.0.1 VEN Client Application
Creates multiple VEN instances and manages their interactions with the VTN server
"""
import traceback

import schedule
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
from resource_db import ResourceDatabase
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

    def __init__(self, config: VENConfig, vtn_base_url: str = "http://localhost:8000", bearer_token:str=None):
        self.config = config
        self.bearer_token=bearer_token
        self.vtn_base_url = vtn_base_url
        self.credentials: Optional[VENCredentials] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.active_events: Dict[str, EventData] = {}
        self.reports: List[Dict] = []
        self.resources: Dict[str, VENResource] = {}
        logger.info(f"Initializing VEN client for {self.config.ven_name} with VTN at {self.vtn_base_url} and bearer token: {self.bearer_token}")

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API calls"""
        if not self.credentials:
            raise ValueError("VEN not registered. Call register() first.")
        return {
            "Authorization": f"Bearer {self.credentials.auth_token}",
            "Content-Type": "application/json"
        }

    async def register_ven_resource(self, resource_config:VENResource) -> bool:
        """Register this VEN with the VTN server"""
        try:
            registration_data = {
                "id": resource_config.resource_id,
                "resource_name": resource_config.resource_name,
                "resource_type": resource_config.resource_type,
                "ven_name": self.config.ven_name,
                "attributes": resource_config.attributes
            }
            headers={'Authorization': 'Bearer '+self.bearer_token}
            async with self.session.post(
                f"{self.vtn_base_url}/resources",
                json=registration_data,
                headers=headers
            ) as response:
                if response.status == 201:
                    data = await response.json()
                    logger.info(f"Successfully registered VEN Resource: {json.dumps(data, indent=2)}")
                    logger.info(f"Successfully registered VEN: {resource_config.resource_name}")
                    return True
                elif response.status == 409:
                    logger.warning(f"VEN Resource {resource_config.resource_name} already exists")
                    return False
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to register VEN  Resource{resource_config.resource_name}: {error_text}")
                    return False

        except Exception as e:
            logger.error(f"Error registering Resource {resource_config.resource_name}: {str(e)}")
            return False

    async def register_ven(self) -> bool:
        """Register this VEN with the VTN server"""
        try:
            registration_data = {
                "ven_name": self.config.ven_name,
                "client_name": self.config.client_name
            }
            print(registration_data, self.bearer_token)
            headers = {'Authorization': 'Bearer ' + self.bearer_token}
            async with self.session.post(
                f"{self.vtn_base_url}/vens",
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
            logger.info(f"Polling for events for {self.vtn_base_url}/events")
            async with self.session.get(
                f"{self.vtn_base_url}/events",
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
            response_data = {
                "event_id": event_id,
                "response_type": response_type.value
            }

            async with self.session.post(
                f"{self.vtn_base_url}/events/{event_id}/responses",
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
            report_data = {
                "report_name": f"{self.config.ven_name}_{report_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "program_id": program_id,
                "ven_id": self.credentials.ven_id,
                "report_type": report_type.value,
                "reading_type": reading_type.value,
                "interval_period": "PT15M"  # 15-minute intervals
            }

            async with self.session.post(
                f"{self.vtn_base_url}/reports",
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
            # Convert timestamp from milliseconds to ISO format
            timestamp_dt = datetime.fromtimestamp(timestamp / 1000)
            timestamp_iso = timestamp_dt.isoformat()

            # Build report data according to OpenADR 3.0 specification
            report_data = {
                "report_name": f"{resource_name}_{timestamp}",
                "resource_id": resource_id,
                "client_name": self.config.client_name,
                "report_type": "READING",
                "reading_type": "DIRECT_READ",
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
                f"{self.vtn_base_url}/reports",
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
            logger.error(f"Error reporting meter data for {resource_name}: {str(e)}")
            return False

    def get_smart_response(self, event: EventData) -> ResponseType:
        """Generate intelligent response based on VEN characteristics"""
        # Simulate intelligent decision making based on VEN type and capacity
        if self.config.device_type == "battery_storage":
            # Battery storage systems are more likely to participate
            return random.choices(
                [ResponseType.OPT_IN, ResponseType.OPT_OUT, ResponseType.NOT_PARTICIPATING],
                weights=[70, 20, 10]
            )[0]
        elif self.config.device_type == "solar_panel":
            # Solar panels may opt out during peak generation hours
            return random.choices(
                [ResponseType.OPT_IN, ResponseType.OPT_OUT, ResponseType.NOT_PARTICIPATING],
                weights=[50, 40, 10]
            )[0]
        elif self.config.device_type == "hvac_system":
            # HVAC systems can be flexible
            return random.choices(
                [ResponseType.OPT_IN, ResponseType.OPT_OUT, ResponseType.NOT_PARTICIPATING],
                weights=[60, 30, 10]
            )[0]
        else:
            # Default behavior for other devices
            return random.choices(
                [ResponseType.OPT_IN, ResponseType.OPT_OUT, ResponseType.NOT_PARTICIPATING],
                weights=[50, 35, 15]
            )[0]




class VENManager:
    """Manages multiple VEN clients"""

    def __init__(self, vtn_base_url: str = "http://localhost:8000", bearer_token:str=None):
        self.vtn_base_url = vtn_base_url
        self.bearer_token=bearer_token
        self.vens: Dict[str, VENClient] = {}
        self.program_id: Optional[str] = None
        self._stop_polling = threading.Event()  # Flag to signal thread termination
        self.poll_thread: Optional[threading.Thread] = None

    def load_ven_resources(self):
        data=json.loads(open('config/resources.json').read())

        return data
    def generate_ven_configs(self, count: int = 10) -> List[VENConfig]:
        """Generate diverse VEN configurations"""
        device_types = ["battery_storage", "solar_panel", "hvac_system", "water_heater", "ev_charger"]
        locations = ["Building_A", "Building_B", "Building_C", "Residential_Zone_1", "Residential_Zone_2",
                     "Industrial_Complex", "Shopping_Mall", "Office_Tower", "Hospital", "School"]

        configs = []
        for i in range(count):
            config = VENConfig(
                ven_name=f"VEN_{i + 1:02d}",
                client_name=f"Client_{i + 1:02d}"
            )
            configs.append(config)

        return configs


    async def load_resources_from_vtn(self, ven_id) -> List:
        try:
            ven=self.vens[ven_id]
            print("Loading resources for ven: {}".format(f"{self.vtn_base_url}/resources"))
            print("Authenticating with token:",ven._get_auth_headers())
            async with ven.session.get(
                f"{self.vtn_base_url}/resources",
                headers=ven._get_auth_headers()
            ) as response:
                logger.info("Loading programs for ven: {}".format(ven_id))
                if response.status == 200:
                    resource_data = await response.json()
                    logger.info("Got resources {} ".format(resource_data))
                    programs = []
                    for pr_data in resource_data:
                        logger.info("Loading resource {}".format(json.dumps(pr_data, indent=4)))
                        continue
                        prog = VTNProgram(
                            id=pr_data["id"],
                            event_name=pr_data["event_name"],
                            program_id=pr_data["program_id"],
                            start_date=pr_data["start_date"],
                            end_date=pr_data["end_date"],
                            status=pr_data["status"],
                            modification_number=pr_data["modification_number"]
                        )
                        programs.append(prog)
                    return programs
                else:
                    logger.error(f"Failed to poll events for {ven.config.ven_name}: {response.status}")
                    return []
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Error polling reosurces: {str(e)}")
            return []


    async def load_programs(self, ven_id) -> List[VTNProgram]:
        try:
            ven=self.vens[ven_id]
            async with ven.session.get(
                f"{self.vtn_base_url}/programs",
                headers=ven._get_auth_headers()
            ) as response:
                logger.info("Loading programs for ven: {}".format(ven_id))
                if response.status == 200:
                    program_data = await response.json()
                    logger.info("Got program {} ".format(program_data))
                    programs = []
                    for pr_data in program_data:
                        logger.info("Loading program {}".format(json.dumps(pr_data, indent=4)))
                        continue
                        prog = VTNProgram(
                            id=pr_data["id"],
                            event_name=pr_data["event_name"],
                            program_id=pr_data["program_id"],
                            start_date=pr_data["start_date"],
                            end_date=pr_data["end_date"],
                            status=pr_data["status"],
                            modification_number=pr_data["modification_number"]
                        )
                        programs.append(prog)
                    return programs
                else:
                    logger.error(f"Failed to poll events for {ven.config.ven_name}: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error polling events for {ven.config.ven_name}: {str(e)}")
            return []

    async def setup_test_program(self) -> str:
        """Create a test program for VENs to subscribe to"""
        program_data = {
            "program_name": "Peak_Shaving_Program_2025",
            "program_long_name": "Summer Peak Shaving Demand Response Program 2025",
            "retailer_name": "Grid_Operator_ABC",
            "retailer_long_name": "ABC Grid Operations Company",
            "program_type": "EMERGENCY_DR",
            "country": "USA",
            "principal_subdivision": "CA",
            "timezone": "America/Los_Angeles",
            "interval_period": "PT1H"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.vtn_base_url}/programs",
                json=program_data
            ) as response:
                if response.status == 201:
                    program_info = await response.json()
                    self.program_id = program_info["id"]
                    logger.info(f"Created test program: {program_info['program_name']}")
                    return self.program_id
                elif response.status == 409:
                    logger.info("Test program already exists")
                    # For simplicity, we'll assume the existing program ID
                    # In production, you'd query for existing programs
                    return "existing-program-id"
                else:
                    error_text = await response.text()
                    raise Exception(f"Failed to create test program: {error_text}")
    def process_dict(self, value):
        """Process a dictionary to convert keys to snake_case"""
        if isinstance(value, dict):
            return {camel_to_snake(k): self.process_dict(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.process_dict(item) for item in value]
        else:
            return value

    async def register_load_ven(self, ven_id):
        logger.info("Starting VEN {} registration process...".format(ven_id))

        # Generate VEN configurations
        #configs = self.generate_ven_configs(1)
        config = VENConfig(
            ven_name=ven_id,
            client_name=f"Client_{ven_id}"
        )
        # Create VEN clients
        # For simpliocity, we'll create a single VEN instance here
        # In production, you might create multiple VENs
        ven=VENClient(config, self.vtn_base_url, self.bearer_token)
        #print(self.vtn_base_url, ven.config.ven_name, self.bearer_token)
        await ven.__aenter__()
        self.vens[ven_id]=ven

        """Register all VEN instances"""
        ven=self.vens[ven_id]

        # Register all VENs concurrently
        registration_tasks = []
        registration_tasks.append(ven.register_ven())
        results = await asyncio.gather(*registration_tasks, return_exceptions=True)

        successful_registrations = sum(1 for result in results if result is True)
        logger.info(f"Successfully registered {successful_registrations}/{len(self.vens.values())} VENs")

        return ven

    async def register_resources(self, ven_id, ressource_map, delay_between_resources: float = 0.1) -> bool:

        from dataclasses import fields

        # Get the VEN instance
        ven = self.vens.get(ven_id)
        if not ven:
            logger.error(f"VEN '{ven_id}' not found in registered VENs")
            return False

        successful_registrations = 0
        total_resources = len(ressource_map)

        logger.info(f"Registering {total_resources} resources sequentially for VEN '{ven_id}' (delay: {delay_between_resources}s between calls)...")

        for idx, resource in enumerate(ressource_map.values(), 1):
            attributes=[]
            for field in fields(resource):
                if field.name=="resourceID" or field.name=="resourceName" or field.name=="resourceType":
                    continue
                else:
                    attribute_value = getattr(resource, field.name)
                    logger.debug(f"Processing field {field.name} with value {attribute_value} and converting to snake_case")
                    atrval=self.process_dict(attribute_value)
                    if type(atrval) is dict:
                        for k,v in atrval.items():
                            attr={'attribute_type':camel_to_snake(k),'attribute_name':k,'attribute_values':[str(v)]}
                            attributes.append(attr)
                    else:
                        attr={'attribute_type':camel_to_snake(field.name),'attribute_name':camel_to_snake(field.name),'attribute_values':[str(atrval)]}
                        attributes.append(attr)

            # Log progress every 50 resources or for the first/last resource
            if idx == 1 or idx == total_resources or idx % 50 == 0:
                logger.info(f"  Progress: {idx}/{total_resources} resources ({(idx/total_resources)*100:.1f}%)")

            logger.debug(f"[{idx}/{total_resources}] Registering resource: {resource.resourceName}")
            res_config=VENResource(resource_id=resource.resourceID,resource_name=resource.resourceName,resource_type=resource.resourceType, attributes=attributes)

            # Register resource synchronously (one at a time)
            try:
                result = await ven.register_ven_resource(res_config)
                if result:
                    successful_registrations += 1
                    ven.resources[res_config.resource_id] = res_config

                # Add delay between registrations to avoid overwhelming the server
                if idx < total_resources:  # Don't delay after the last one
                    await asyncio.sleep(delay_between_resources)

            except Exception as e:
                logger.error(f"Error registering resource {resource.resourceName}: {str(e)}")
                continue

        logger.info(f"Successfully registered {successful_registrations}/{total_resources} VEN Resources for VEN '{ven_id}'")

        return successful_registrations > 0

    async def create_test_event(self) -> str:
        """Create a test demand response event"""
        if not self.program_id:
            raise ValueError("No program available. Create a program first.")

        # Pick a random VEN to target (in practice, you might target multiple VENs)
        target_ven = random.choice([ven for ven in self.vens.values() if ven.credentials])

        event_data = {
            "event_name": f"Emergency_DR_Event_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "program_id": self.program_id,
            "ven_id": target_ven.credentials.ven_id,
            "start_date": (datetime.now() + timedelta(minutes=15)).isoformat(),
            "end_date": (datetime.now() + timedelta(hours=2)).isoformat(),
            "notification_period": 10,
            "priority": 1,
            "event_targets": [
                {
                    "type": "power_reduction",
                    "values": ["25"]  # 25% power reduction
                }
            ]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.vtn_base_url}/events",
                json=event_data
            ) as response:
                if response.status == 201:
                    event_info = await response.json()
                    logger.info(f"Created test event: {event_info['event_name']} for VEN: {target_ven.config.ven_name}")
                    return event_info["id"]
                else:
                    error_text = await response.text()
                    raise Exception(f"Failed to create test event: {error_text}")


    async def run_event_polling_loop(self, polling_seconds_frequency: int = 15):
        """Run continuous event polling for all VENs"""
        logger.info(f"Starting event polling loop for every {polling_seconds_frequency} seconds...")

        while not self._stop_polling.is_set():
            # Poll events for all VENs
            polling_tasks = []
            for ven in self.vens.values():
                if ven.credentials:
                    polling_tasks.append(ven.poll_events())
            if polling_tasks:
                results = await asyncio.gather(*polling_tasks, return_exceptions=True)
                # Process events and generate responses
                response_tasks = []
                for i, events in enumerate(results):
                    if isinstance(events, list) and events:
                        ven = list(self.vens.values())[i]  # Fix the indexing issue
                        for event in events:
                            # Generate intelligent response
                            response_type = ven.get_smart_response(event)
                            response_tasks.append(ven.respond_to_event(event.id, response_type))

                # Execute all responses
                if response_tasks:
                    await asyncio.gather(*response_tasks, return_exceptions=True)

            # Check if we should stop before waiting
            if self._stop_polling.is_set():
                break

            # Wait before next poll with periodic check for stop signal
            for _ in range(polling_seconds_frequency):
                if self._stop_polling.is_set():
                    break
                await asyncio.sleep(1)

        logger.info("Event polling loop terminated gracefully")

    async def generate_reports(self):
        """Generate telemetry reports for all VENs using simulated meter data"""
        logger.info("Generating telemetry reports from simulated meter data...")

        from venclient.simulation.meterdata_simulator import MeterDataSimulator

        # Initialize simulator and advance time
        ms = MeterDataSimulator()
        ms.increase_time()
        logger.info("Increased timestamp")

        total_reports_sent = 0
        total_resources_processed = 0

        for ven in self.vens.values():
            #if not ven.credentials:
            #    logger.info(f"Skipping VEN {ven.config.ven_name} - not registered")
            #    continue

            # Ensure VEN has a valid session in current event loop
            if ven.session is None or ven.session.closed:
                logger.debug(f"Creating new session for VEN {ven.config.ven_name}")
                ven.session = aiohttp.ClientSession()

            logger.info(f"Collecting meter data for VEN: {ven.config.ven_name}")

            # Collect meter data for this VEN's resources
            resources_meterdata = ms.collect_next_metering(ven.config.ven_name)


            if not resources_meterdata:
                logger.info(f"No meter data available for VEN {ven.config.ven_name}")
                continue

            logger.info(f"Processing {len(resources_meterdata)} resources for VEN {ven.config.ven_name}")
            total_resources_processed += len(resources_meterdata)

            # Report data for each resource
            report_tasks = []
            for resource_id, meter_data in resources_meterdata.items():
                # Get resource info if available
                resource_info = ven.resources.get(resource_id)
                resource_name = resource_info.resource_name if resource_info else resource_id[:16]

                # Report each load component's reading
                for reading in meter_data.readings:
                    task = ven.report_meter_data(
                        resource_id=resource_id,
                        resource_name=resource_name,
                        timestamp=reading.timestamp,
                        power_w=reading.power_w,
                        load_id=reading.load_id,
                        program_id=self.program_id if self.program_id else None
                    )
                    report_tasks.append(task)

            # Send all reports for this VEN
            if report_tasks:
                results = await asyncio.gather(*report_tasks, return_exceptions=True)
                successful = sum(1 for r in results if r is True)
                total_reports_sent += successful
                logger.info(f"Sent {successful}/{len(report_tasks)} reports for VEN {ven.config.ven_name}")

        logger.info(f"Report generation complete: {total_reports_sent} reports sent for {total_resources_processed} resources across {len(self.vens)} VENs")

    async def cleanup(self):
        """Clean up all VEN sessions"""
        cleanup_tasks = []
        for ven in self.vens.values():
            if ven.session:
                cleanup_tasks.append(ven.__aexit__(None, None, None))

        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)

    def print_summary(self):
        """Print summary of all VEN operations"""
        print("\n" + "=" * 80)
        print("VEN CLIENT SUMMARY")
        print("=" * 80)

        registered_vens = [ven for ven in self.vens if ven.credentials]
        print(f"Total VENs Created: {len(self.vens)}")
        print(f"Successfully Registered: {len(registered_vens)}")
        print(f"Program ID: {self.program_id}")

        print(f"\nVEN Details:")
        for ven in registered_vens:
            print(
                f"  {ven.config.ven_name}: {ven.config.device_type} ({ven.config.capacity_kw:.1f}kW) - {ven.config.location}")
            print(f"    Events Received: {len(ven.active_events)}")
            print(f"    Reports Created: {len(ven.reports)}")

        print("\n" + "=" * 80)

    # Start thread for async polling against VTN server
    def run_async_polling(self):
        def poll_worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # Re-create VENs in this loop
            for ven in self.vens.values():
                loop.run_until_complete(ven.__aenter__())
            try:
                loop.run_until_complete(self.run_event_polling_loop(polling_seconds_frequency=15))
            finally:
                loop.run_until_complete(self.cleanup())
                loop.close()

        self.poll_thread = threading.Thread(target=poll_worker, daemon=True)
        self.poll_thread.start()
        logger.info("Started async polling thread")

    def stop_polling(self):
        """Signal the polling thread to stop gracefully"""
        logger.info("Signaling polling thread to stop...")
        self._stop_polling.set()

    def wait_for_polling_to_stop(self, timeout: Optional[float] = 30.0):
        """Wait for the polling thread to stop gracefully"""
        if self.poll_thread and self.poll_thread.is_alive():
            logger.info("Waiting for polling thread to stop...")
            self.poll_thread.join(timeout=timeout)
            if self.poll_thread.is_alive():
                logger.warning("Polling thread did not stop within timeout period")
                return False
            else:
                logger.info("Polling thread stopped successfully")
                return True
        return True

    def is_polling_active(self) -> bool:
        """Check if polling is currently active"""
        return self.poll_thread is not None and self.poll_thread.is_alive() and not self._stop_polling.is_set()


    async def ven_report_usage(self):
        """
        Report usage data for all VENs using simulated meter data.
        This method is called by the scheduler to periodically report meter data to the VTN.
        """
        try:
            logger.info("Scheduled report generation triggered...")
            await self.generate_reports()
        except Exception as e:
            logger.error(f"Error in ven_report_usage: {str(e)}")
            import traceback
            traceback.print_exc()


def init_scheduler(manager):
    """
    Initialize the scheduler for periodic meter data reporting.
    Since schedule library doesn't support async functions, we wrap the async call.
    """
    def run_report_job():
        """Synchronous wrapper for async report generation"""
        try:
            logger.info("Scheduled report generation triggered...")
            # Run the async function in the existing event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, create a task
                asyncio.create_task(manager.ven_report_usage())
            else:
                # Otherwise run it directly
                loop.run_until_complete(manager.ven_report_usage())
        except Exception as e:
            logger.error(f"Error in scheduled report job: {str(e)}")
            import traceback
            traceback.print_exc()

    schedule.every(3).seconds.do(run_report_job)
    logger.info("Scheduler initialized: reports will be generated every 10 seconds")


from flex_resources import Resource

def load_vens_from_sqlite(db_path: str = "./config/resources.db") -> List[str]:
    """
    Load unique VEN identifiers from SQLite database.

    Args:
        db_path: Path to the SQLite database

    Returns:
        List of unique VEN identifiers (cities)
    """
    try:
        db = ResourceDatabase(db_path=db_path)
        stats = db.get_statistics()

        # Get all unique VEN names
        vens = list(stats['top_10_vens'].keys()) if stats['top_10_vens'] else []

        # If you want ALL VENs (not just top 10), query directly
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT ven FROM resources WHERE ven IS NOT NULL ORDER BY ven")
            all_vens = [row[0] for row in cursor.fetchall()]

        logger.info(f"Loaded {len(all_vens)} VENs from SQLite database")
        return all_vens

    except Exception as e:
        logger.error(f"Error loading VENs from SQLite: {str(e)}")
        return []


def load_ven_resources_from_sqlite(ven_id: str, db_path: str = "./config/resources.db") -> List[Resource]:
    """
    Load all resources for a specific VEN from SQLite database.

    Args:
        ven_id: The VEN identifier (city name)
        db_path: Path to the SQLite database

    Returns:
        List of Resource objects for the specified VEN
    """
    try:
        db = ResourceDatabase(db_path=db_path)
        resources = db.get_resources_by_ven(ven_id)

        logger.info(f"Loaded {len(resources)} resources for VEN '{ven_id}' from SQLite database")
        return resources

    except Exception as e:
        logger.error(f"Error loading resources for VEN '{ven_id}' from SQLite: {str(e)}")
        return []


async def sample_registration(vtn_url="http://localhost:8000", bearer_token:str=None, db_path: str = "./config/resources.db", limit_vens: int = None, delay_between_resources: float = 0.1):
    """
    Register VENs and their resources from SQLite database with VTN server.

    Args:
        vtn_url: Base URL of the VTN server
        bearer_token: Authentication token for VTN API
        db_path: Path to the SQLite database containing resources
        limit_vens: Optional limit on number of VENs to register (for testing)
        delay_between_resources: Delay in seconds between resource registrations (default: 0.1)
    """
    logger.info("EnergyDesk OpenADR 3.0.1 VEN Client - Sample Registration")
    logger.info("="*60)
    logger.info(f"VTN URL: {vtn_url}")
    logger.info(f"Database: {db_path}")

    # Initialize VEN manager
    manager = VENManager(vtn_base_url=vtn_url, bearer_token=bearer_token)

    # Load all VENs from SQLite database
    logger.info("\nStep 1: Loading VENs from SQLite database...")
    vens = load_vens_from_sqlite(db_path)

    if not vens:
        logger.error("No VENs found in database. Please run prepare_samples.py first.")
        return

    logger.info(f"Found {len(vens)} VENs in database")

    # Limit VENs if requested (useful for testing)
    if limit_vens and limit_vens > 0:
        vens = vens[:limit_vens]
        logger.info(f"Limited to first {len(vens)} VENs for testing")

    # Track statistics
    total_vens_registered = 0
    total_resources_registered = 0
    failed_vens = []

    try:
        # Register each VEN and its resources
        logger.info(f"\nStep 2: Registering {len(vens)} VENs and their resources...")
        logger.info("-"*60)

        for idx, ven_id in enumerate(vens, 1):
            try:
                logger.info(f"\n[{idx}/{len(vens)}] Processing VEN: {ven_id}")

                # Load resources for this VEN
                resources_of_ven = load_ven_resources_from_sqlite(ven_id, db_path)

                if not resources_of_ven:
                    logger.warning(f"  No resources found for VEN '{ven_id}', skipping...")
                    continue

                logger.info(f"  Found {len(resources_of_ven)} resources for VEN '{ven_id}'")

                # Register the VEN
                logger.info(f"  Registering VEN '{ven_id}'...")
                await manager.register_load_ven(ven_id)
                total_vens_registered += 1

                # Convert resources to dictionary
                resource_map: Dict[str, Resource] = {}
                for resource in resources_of_ven:
                    resource_map[resource.resourceID] = resource

                # Register resources for this VEN
                logger.info(f"  Registering {len(resource_map)} resources for VEN '{ven_id}'...")
                success = await manager.register_resources(ven_id, resource_map, delay_between_resources)

                if success:
                    total_resources_registered += len(resource_map)
                    logger.info(f"  ✓ Successfully registered VEN '{ven_id}' with {len(resource_map)} resources")
                else:
                    logger.warning(f"  ⚠ VEN '{ven_id}' registered but some resources may have failed")

            except Exception as e:
                logger.error(f"  ✗ Error processing VEN '{ven_id}': {str(e)}")
                failed_vens.append((ven_id, str(e)))
                continue

        # Print summary
        logger.info("\n" + "="*60)
        logger.info("REGISTRATION SUMMARY")
        logger.info("="*60)
        logger.info(f"Total VENs processed:          {len(vens)}")
        logger.info(f"VENs successfully registered:  {total_vens_registered}")
        logger.info(f"Resources registered:          {total_resources_registered}")
        logger.info(f"Failed VENs:                   {len(failed_vens)}")

        if failed_vens:
            logger.info("\nFailed VENs:")
            for ven_id, error in failed_vens:
                logger.info(f"  - {ven_id}: {error}")

        logger.info("="*60 + "\n")

    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        await manager.cleanup()
        logger.info("Registration process completed.\n")


from venclient.simulation.meterdata_simulator import MeterDataSimulator
async def startup(vtn_url="http://localhost:8000", bearer_token:str=None,db_path: str = "./config/resources.db"):
    """Main application entry point"""
    logger.info("EnergyDesk OpenADR 3.0.1 VEN Client")
    logger.info("====================================")

    # Initialize VEN manager
    manager = VENManager(vtn_base_url=vtn_url, bearer_token=bearer_token)

    # Load all VENs from SQLite database
    logger.info("\nStep 1: Loading VENs from SQLite database...")
    vens = load_vens_from_sqlite(db_path)
    for ven_id in vens[:10]:
        await manager.register_load_ven(ven_id)
    ms=MeterDataSimulator()
    ms.initialize_resources(vens)
    #init_scheduler(manager)
    try:


        #manager.run_async_polling()  # Start polling VTN in a separate thread

        while True:
            #schedule.run_pending()  # This scheduler checks status on Resources and generates reports to VTN
            time.sleep(1)
        # Step 6: Generate final reports
        #   print("\n6. Generating final reports...")
        #await manager.generate_reports()

        # Step 7: Print summary
        #manager.print_summary()

    except Exception as e:
        logger.error(f"Application error: {str(e)}")
    finally:
        # Cleanup
        await manager.cleanup()
        print("\nApplication completed.")


if __name__ == "__main__":
    asyncio.run(startup())