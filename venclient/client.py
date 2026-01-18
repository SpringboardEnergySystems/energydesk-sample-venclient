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
                f"{self.vtn_base_url}/resources",
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
            error_msg = str(e)
            # Add more context for event loop errors
            if "Event loop is closed" in error_msg or "attached to a different loop" in error_msg:
                logger.error(f"Event loop error reporting meter data for {resource_name}: {error_msg}")
                logger.debug(f"  Session state: closed={getattr(self.session, 'closed', 'unknown')}")
                logger.debug(f"  Try recreating the session in generate_reports()")
            else:
                logger.error(f"Error reporting meter data for {resource_name}: {error_msg}")
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

    async def bulk_upload_historical_meterdata(self, ven_id: str,
                                              db_path: str = "./config/resources.db",
                                              h5_file_path: str = "./config/examplemeterdata/load_data.h5",
                                              chunk_size: int = 50000,
                                              batch_size: int = 5000,
                                              limit_loads: int = None) -> Dict[str, any]:
        """
        Upload historical meter data from H5 files to VTN in bulk.

        Args:
            ven_id: VEN identifier (city name)
            db_path: Path to SQLite database
            h5_file_path: Path to H5 file with meter data
            chunk_size: Number of points to upload per chunk (default: 50000)
            batch_size: InfluxDB batch size for writes (default: 5000)
            limit_loads: Optional limit on number of loads to process (for testing)

        Returns:
            Dictionary with upload statistics
        """
        import h5py
        import pandas as pd

        logger.info(f"Starting bulk upload of historical meter data for VEN '{ven_id}'")

        # Initialize database
        db = ResourceDatabase(db_path=db_path)

        # Get the VEN instance
        ven = self.vens.get(ven_id)
        if not ven:
            logger.error(f"VEN '{ven_id}' not found in registered VENs")
            return {"success": False, "error": "VEN not found"}

        # Query loads with VTN resource IDs from database
        with db.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT 
                    l.load_id,
                    l.load_component,
                    l.load_name,
                    l.h5_meter_id,
                    l.vtn_resource_id,
                    r.resource_name
                FROM loads l
                JOIN resources r ON l.resource_id = r.resource_id
                WHERE r.ven = ? AND l.vtn_resource_id IS NOT NULL
                ORDER BY r.resource_id, l.load_component
            """
            if limit_loads:
                query += f" LIMIT {limit_loads}"

            cursor.execute(query, (ven_id,))
            load_records = cursor.fetchall()

        if not load_records:
            logger.warning(f"No loads with VTN resource IDs found for VEN '{ven_id}'")
            return {"success": True, "total_loads": 0, "uploaded": 0, "error": "No registered loads"}

        logger.info(f"Found {len(load_records)} loads to upload for VEN '{ven_id}'")

        # Track statistics
        total_loads = len(load_records)
        successful_uploads = 0
        failed_uploads = 0
        total_points_uploaded = 0

        # Open H5 file
        with h5py.File(h5_file_path, 'r') as hf:
            meters_group = hf['meters']

            # Process each load
            for idx, record in enumerate(load_records, 1):
                (load_id, load_component, load_name, h5_meter_id,
                 vtn_resource_id, resource_name) = record

                logger.info(f"[{idx}/{total_loads}] Uploading {resource_name} - {load_name}")

                try:
                    # Check if meter exists in H5 file
                    if h5_meter_id not in meters_group:
                        logger.error(f"  H5 meter '{h5_meter_id}' not found")
                        failed_uploads += 1
                        continue

                    # Get the meter and load component
                    meter = meters_group[h5_meter_id]
                    if load_component not in meter:
                        logger.error(f"  Load component '{load_component}' not found in meter")
                        failed_uploads += 1
                        continue

                    load_group = meter[load_component]
                    if 'power' not in load_group:
                        logger.error(f"  'power' dataset not found")
                        failed_uploads += 1
                        continue

                    # Load power data
                    power_data = load_group['power'][:]
                    df = pd.DataFrame(power_data, columns=['timestamp', 'power_w'])

                    logger.info(f"  Loaded {len(df)} data points from H5 file")

                    # Upload in chunks if dataset is large
                    total_points = len(df)
                    uploaded_points = 0

                    for chunk_start in range(0, total_points, chunk_size):
                        chunk_end = min(chunk_start + chunk_size, total_points)
                        chunk_df = df.iloc[chunk_start:chunk_end]

                        # Format data for bulk upload API
                        data_points = []
                        for _, row in chunk_df.iterrows():
                            timestamp = pd.to_datetime(row['timestamp'], unit='s')
                            interval_end = timestamp + pd.Timedelta(hours=1)  # 1-hour intervals

                            data_points.append({
                                "interval_start": timestamp.isoformat() + "Z",
                                "interval_end": interval_end.isoformat() + "Z",
                                "value": float(row['power_w']),
                                "quality_code": "GOOD"
                            })

                        # Upload chunk to VTN
                        logger.info(f"  Uploading chunk {chunk_start//chunk_size + 1}: {len(data_points)} points...")

                        response = await ven.session.post(
                            f"{self.vtn_base_url}/report_data/bulk",
                            params={
                                "resource_id": vtn_resource_id,
                                "batch_size": batch_size
                            },
                            headers={'Authorization': 'Bearer ' + self.bearer_token},
                            json=data_points,
                            timeout=aiohttp.ClientTimeout(total=300)  # 5 minute timeout
                        )

                        if response.status == 201:
                            result = await response.json()
                            uploaded_points += result.get('entries_created', 0)
                            throughput = result.get('throughput_points_per_second', 0)
                            logger.info(f"  ✓ Uploaded {uploaded_points}/{total_points} points ({throughput:.0f} pts/sec)")
                        else:
                            error_text = await response.text()
                            logger.error(f"  Failed to upload chunk: {response.status} - {error_text}")
                            break

                    if uploaded_points == total_points:
                        successful_uploads += 1
                        total_points_uploaded += uploaded_points
                        logger.info(f"  ✓ Complete: {uploaded_points} points uploaded")
                    else:
                        failed_uploads += 1
                        logger.warning(f"  Partial upload: {uploaded_points}/{total_points} points")

                except Exception as e:
                    logger.error(f"  Error uploading load: {e}")
                    import traceback
                    traceback.print_exc()
                    failed_uploads += 1

        # Return statistics
        stats = {
            "success": True,
            "ven_id": ven_id,
            "total_loads": total_loads,
            "successful": successful_uploads,
            "failed": failed_uploads,
            "total_points_uploaded": total_points_uploaded
        }

        logger.info(f"Bulk upload complete for VEN '{ven_id}': {successful_uploads}/{total_loads} loads uploaded")
        logger.info(f"Total data points uploaded: {total_points_uploaded:,}")

        return stats

    async def register_resources(self, ven_id) -> Dict[str, any]:
        """
        DEPRECATED: Use register_loads_parallel instead.
        This method is kept for backward compatibility.

        Returns:
            Dictionary with registration statistics (for compatibility)
        """
        logger.warning("register_resources is deprecated. Use register_loads_parallel for better performance.")
        stats = await self.register_loads_parallel(ven_id, batch_size=50, delay_between_batches=0.5)

        # Convert to old format for backward compatibility
        return {
            'success': stats.get('success', False),
            'registered': stats.get('registered', 0),
            'total': stats.get('total_loads', 0)
        }

    async def register_loads_parallel(self, ven_id: str, batch_size: int = 50,
                                     delay_between_batches: float = 0.5,
                                     db_path: str = "./config/resources.db") -> Dict[str, any]:
        """
        Register all loads for a VEN in parallel batches with the VTN server.

        Args:
            ven_id: VEN identifier (city name)
            batch_size: Number of resources to register in parallel per batch
            delay_between_batches: Delay between batches to avoid overwhelming server
            db_path: Path to SQLite database

        Returns:
            Dictionary with registration statistics
        """
        from dataclasses import fields

        # Get the VEN instance
        ven = self.vens.get(ven_id)
        if not ven:
            logger.error(f"VEN '{ven_id}' not found in registered VENs")
            return {"success": False, "error": "VEN not found"}

        logger.info(f"Registering loads for VEN '{ven_id}' in parallel batches of {batch_size}...")

        # Load resources and their loads from database
        db = ResourceDatabase(db_path=db_path)

        # Query to get all resources with their loads
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    r.resource_id,
                    r.resource_name,
                    r.resource_type,
                    r.resource_sub_type,
                    r.meter_point_id,
                    r.capacities,
                    r.location,
                    r.address,
                    r.enabled,
                    r.reporting,
                    l.load_id,
                    l.load_component,
                    l.load_name,
                    l.h5_meter_id
                FROM resources r
                JOIN loads l ON r.resource_id = l.resource_id
                WHERE r.ven = ?
                ORDER BY r.resource_id, l.load_component
            """, (ven_id,))

            resource_load_rows = cursor.fetchall()

        if not resource_load_rows:
            logger.warning(f"No resources/loads found for VEN '{ven_id}'")
            return {"success": True, "total_loads": 0, "registered": 0, "failed": 0}

        logger.info(f"Found {len(resource_load_rows)} load records for VEN '{ven_id}'")

        # Prepare registration tasks
        registration_data = []
        for row in resource_load_rows:
            (resource_id, resource_name, resource_type, resource_sub_type,
             meter_point_id, capacities_json, location_json, address, enabled, reporting_json,
             load_id, load_component, load_name, h5_meter_id) = row

            # Parse JSON fields
            capacities = json.loads(capacities_json)
            location = json.loads(location_json)
            reporting = json.loads(reporting_json) if reporting_json else None

            # Extract longitude and latitude for service_location
            longitude = location.get('longitude') if location else None
            latitude = location.get('latitude') if location else None

            # Build attributes from resource data (excluding longitude/latitude)
            attributes = []

            # Add resource sub type
            if resource_sub_type:
                attributes.append({
                    'attribute_type': 'resource_sub_type',
                    'attribute_name': 'resource_sub_type',
                    'attribute_values': [resource_sub_type]
                })

            # Add capacities
            if capacities:
                for k, v in capacities.items():
                    attributes.append({
                        'attribute_type': camel_to_snake(k),
                        'attribute_name': k,
                        'attribute_values': [str(v)]
                    })

            # NOTE: longitude and latitude are now in service_location, not attributes

            # Add address
            if address:
                attributes.append({
                    'attribute_type': 'address',
                    'attribute_name': 'address',
                    'attribute_values': [address]
                })

            # Add load-specific attributes
            attributes.append({
                'attribute_type': 'load_component',
                'attribute_name': 'load_component',
                'attribute_values': [load_component]
            })

            attributes.append({
                'attribute_type': 'load_name',
                'attribute_name': 'load_name',
                'attribute_values': [load_name]
            })

            attributes.append({
                'attribute_type': 'h5_meter_id',
                'attribute_name': 'h5_meter_id',
                'attribute_values': [h5_meter_id]
            })

            # Create resource config for this load
            load_resource_name = f"{resource_name} - {load_name}"
            external_resource_id = f"{resource_id}_{load_component}"

            res_config = VENResource(
                resource_id=load_id,  # Use load_id as the resource ID
                resource_name=load_resource_name,
                resource_type=resource_type,
                attributes=attributes
            )

            # Build service_location with meterpoint_id, longitude, and latitude
            service_location_dict = {
                "meterpoint_id": meter_point_id  # Note: all lowercase, no underscore
            }
            if longitude is not None:
                service_location_dict["longitude"] = float(longitude)
            if latitude is not None:
                service_location_dict["latitude"] = float(latitude)

            registration_data.append({
                'config': res_config,
                'external_resource_id': external_resource_id,
                'service_location': service_location_dict,
                'load_id': load_id
            })

        # Register in parallel batches
        total_loads = len(registration_data)
        registered_count = 0
        failed_count = 0
        vtn_resource_ids = {}  # Map load_id -> vtn_resource_id

        for batch_start in range(0, total_loads, batch_size):
            batch_end = min(batch_start + batch_size, total_loads)
            batch = registration_data[batch_start:batch_end]

            logger.info(f"Registering batch {batch_start//batch_size + 1}: loads {batch_start+1}-{batch_end}/{total_loads}")

            # Create parallel tasks for this batch
            tasks = []
            for item in batch:
                task = ven.register_ven_resource(
                    item['config'],
                    external_resource_id=item['external_resource_id'],
                    service_location=item['service_location']
                )
                tasks.append(task)

            # Execute batch in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for item, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.error(f"Error registering load {item['load_id']}: {result}")
                    failed_count += 1
                elif result:  # VTN resource ID returned
                    vtn_resource_ids[item['load_id']] = result
                    registered_count += 1
                else:
                    failed_count += 1

            # Delay between batches
            if batch_end < total_loads:
                await asyncio.sleep(delay_between_batches)

        # Update loads table with VTN resource IDs
        logger.info(f"Updating {len(vtn_resource_ids)} load records with VTN resource IDs...")
        for load_id, vtn_resource_id in vtn_resource_ids.items():
            try:
                db.update_load_vtn_resource_id(load_id, vtn_resource_id, 'APPROVED')
            except Exception as e:
                logger.error(f"Error updating load {load_id} with VTN ID: {e}")

        # Return statistics
        stats = {
            "success": True,
            "ven_id": ven_id,
            "total_loads": total_loads,
            "registered": registered_count,
            "failed": failed_count,
            "vtn_ids_mapped": len(vtn_resource_ids)
        }

        logger.info(f"Registration complete for VEN '{ven_id}': {registered_count}/{total_loads} loads registered")

        return stats


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
            # Always recreate session to ensure it's bound to current event loop
            # This is necessary because the scheduler runs tasks in a new event loop
            logger.debug(f"Recreating session for VEN {ven.config.ven_name} in current event loop")

            # Close old session if it exists (suppress all errors)
            if ven.session is not None:
                try:
                    await ven.session.close()
                except Exception:
                    pass

            # Create new session in current event loop
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


async def sample_registration(vtn_url="http://localhost:8000", bearer_token: str = None,
                             db_path: str = "./config/resources.db", limit_vens: int = None,
                             batch_size: int = 50, delay_between_batches: float = 0.5):
    """
    Register VENs and their load resources from SQLite database with VTN server.

    This function:
    1. Loads VENs from the database
    2. For each VEN, loads all resources and their associated loads
    3. Registers each load as a separate resource with the VTN
    4. Uses parallel registration for better performance
    5. Updates the loads table with VTN-assigned resource IDs

    Args:
        vtn_url: Base URL of the VTN server
        bearer_token: Authentication token for VTN API
        db_path: Path to the SQLite database containing resources
        limit_vens: Optional limit on number of VENs to register (for testing)
        batch_size: Number of loads to register in parallel per batch (default: 50)
        delay_between_batches: Delay between batches to avoid overwhelming server (default: 0.5s)
    """
    logger.info("EnergyDesk OpenADR 3.0.1 VEN Client - Load Registration (Parallel)")
    logger.info("=" * 60)
    logger.info(f"VTN URL: {vtn_url}")
    logger.info(f"Database: {db_path}")
    logger.info(f"Batch size: {batch_size}")
    logger.info(f"Delay between batches: {delay_between_batches}s")

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
    total_loads_registered = 0
    total_loads_failed = 0
    failed_vens = []

    try:
        # Register each VEN and its load resources in parallel
        logger.info(f"\nStep 2: Registering {len(vens)} VENs and their loads...")
        logger.info("-" * 60)

        for idx, ven_id in enumerate(vens, 1):
            try:
                logger.info(f"\n[{idx}/{len(vens)}] Processing VEN: {ven_id}")

                # Register the VEN
                logger.info(f"  Registering VEN '{ven_id}'...")
                await manager.register_load_ven(ven_id)
                total_vens_registered += 1

                # Register loads for this VEN in parallel batches
                logger.info(f"  Registering loads for VEN '{ven_id}' in parallel...")
                stats = await manager.register_loads_parallel(
                    ven_id=ven_id,
                    batch_size=batch_size,
                    delay_between_batches=delay_between_batches,
                    db_path=db_path
                )

                if stats['success']:
                    total_loads_registered += stats['registered']
                    total_loads_failed += stats['failed']
                    logger.info(f"  ✓ Successfully registered {stats['registered']}/{stats['total_loads']} loads for VEN '{ven_id}'")
                    if stats['failed'] > 0:
                        logger.warning(f"  ⚠ {stats['failed']} loads failed to register")
                else:
                    logger.error(f"  ✗ Failed to register loads for VEN '{ven_id}': {stats.get('error', 'Unknown error')}")
                    failed_vens.append((ven_id, stats.get('error', 'Unknown error')))

            except Exception as e:
                logger.error(f"  ✗ Error processing VEN '{ven_id}': {str(e)}")
                import traceback
                traceback.print_exc()
                failed_vens.append((ven_id, str(e)))
                continue

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("REGISTRATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total VENs processed:          {len(vens)}")
        logger.info(f"VENs successfully registered:  {total_vens_registered}")
        logger.info(f"Total loads registered:        {total_loads_registered}")
        logger.info(f"Total loads failed:            {total_loads_failed}")
        logger.info(f"Failed VENs:                   {len(failed_vens)}")

        if failed_vens:
            logger.info("\nFailed VENs:")
            for ven_id, error in failed_vens:
                logger.info(f"  - {ven_id}: {error}")

        logger.info("=" * 60 + "\n")

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