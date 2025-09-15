"""
OpenADR 3.0.1 VEN Client Application
Creates multiple VEN instances and manages their interactions with the VTN server
"""
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

    async def register_ven_and_resources(self, ven_id, ressource_map) -> bool:
        """Register all VEN instances"""
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
        await ven.__aenter__()
        self.vens[ven_id]=ven

        # Register all VENs concurrently
        registration_tasks = []
        registration_tasks.append(ven.register_ven())
        results = await asyncio.gather(*registration_tasks, return_exceptions=True)

        successful_registrations = sum(1 for result in results if result is True)
        logger.info(f"Successfully registered {successful_registrations}/{len(self.vens.values())} VENs")
        from dataclasses import dataclass, fields
        registration_tasks = []
        resource_configs=[]
        for resource in ressource_map.values():
            attributes=[]
            for field in fields(resource):
                if field.name=="resourceID" or field.name=="resourceName" or field.name=="resourceType":
                    continue
                else:
                    attribute_value = getattr(resource, field.name)
                    print(f"Processing field {field.name} with value {attribute_value} and converting to snake_case")
                    atrval=self.process_dict(attribute_value)
                    if type(atrval) is dict:
                        for k,v in atrval.items():
                            attr={'attribute_type':camel_to_snake(k),'attribute_name':k,'attribute_values':[str(v)]}
                            attributes.append(attr)
                    else:
                        attr={'attribute_type':camel_to_snake(field.name),'attribute_name':camel_to_snake(field.name),'attribute_values':[str(atrval)]}
                        attributes.append(attr)
            print(f"Registering resource {resource.resourceName} with attributes {attributes}")
            res_config=VENResource(resource_id=resource.resourceID,resource_name=resource.resourceName,resource_type=resource.resourceType, attributes=attributes)
            resource_configs.append(res_config)
            registration_tasks.append(ven.register_ven_resource(res_config))
        results = await asyncio.gather(*registration_tasks, return_exceptions=True)
        for r in resource_configs:
            ven.resources[r.resource_id] = r
        successful_registrations = sum(1 for result in results if result is True)
        logger.info(f"Successfully registered {successful_registrations}/{len(self.vens)} VEN Resources")

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
        """Generate telemetry reports for all VENs"""
        if not self.program_id:
            logger.warning("No program available for reporting")
            return

        logger.info("Generating telemetry reports...")

        report_tasks = []
        report_types = [ReportType.USAGE, ReportType.DEMAND]
        resource_types = [ResourceType.ENERGY, ResourceType.POWER]

        for ven in self.vens.values():
            if ven.credentials:
                report_type = random.choice(report_types)
                resource_type = random.choice(resource_types)
                report_tasks.append(ven.create_report(self.program_id, report_type, resource_type))

        if report_tasks:
            results = await asyncio.gather(*report_tasks, return_exceptions=True)
            successful_reports = sum(1 for result in results if result is True)
            logger.info(f"Successfully created {successful_reports}/{len(report_tasks)} reports")

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


    def ven_report_usage(self) -> bool:
        """
        Placeholder for the VEN update logic.
        This method should be implemented to perform the actual update.
        """
        report_tasks = []
        report_types = [ReportType.USAGE]
        resource_types = [ResourceType.POWER]
        report_type=report_types[0]
        resource_type=resource_types[0]
        logger.info("Generating reports for all VENs...")
        fields=['power', 'energy', 'state_of_charge', 'voltage', 'frequency']
        for ven in self.vens.values():
            logger.info("Reporting usage for VEN: {}".format(ven.config.ven_name))
            for resource in ven.resources.values():
                # Here you would typically fetch the latest data and generate a report
                # For demonstration, we will just print the resource details
                logger.info(f"Resource ID: {resource.resource_id}, Name: {resource.resource_name}, Type: {resource.resource_type}")
                records = []#read_influxdb("mybucket", "sensordata", fields=fields, tags={'resource_id': resource.resource_id}, start_time="-100y")
                for r in records:
                    logger.debug("Sensor data to report {}".format(r))
                report_tasks.append(ven.create_report(self.program_id, report_type, resource_type))



        #records=read_influxdb("mybucket","sensordata", {'resource_id': 'shop-001'}, start_time="-100y")

        #asyncio.run(self.generate_reports())
        # Implement the actual VEN update logic here
        # For example, fetching data from a VTN server and updating local state
        # This is just a placeholder for demonstration purposes
        pass


async def init_scheduler(manager):
    VEN_UPDATE_INTERVAL_MINUTES = get_environment_value('VEN_UPDATE_INTERVAL_MINUTES', None)
    print("Initializing schedule", VEN_UPDATE_INTERVAL_MINUTES)
    if VEN_UPDATE_INTERVAL_MINUTES is not None:
        mins=int(VEN_UPDATE_INTERVAL_MINUTES)
        schedule.every(10).seconds.do(manager.ven_report_usage)

async def startup(ven_id="testven",vtn_url="http://localhost:8000", bearer_token:str=None,resource_map:dict={}):
    """Main application entry point"""
    logger.info("EnergyDesk OpenADR 3.0.1 VEN Client")
    logger.info("====================================")

    # Initialize VEN manager
    manager = VENManager(vtn_base_url=vtn_url, bearer_token=bearer_token)
    await init_scheduler(manager)
    try:


        # Step 1: Register all VENs
        print("\n1. Login as VEN and register Resource (Asset) instances...")
        await manager.register_ven_and_resources(ven_id, resource_map)
        return
        print("\n2. Loading programs for ven:", ven_id)
        await manager.load_programs(ven_id)
        print("\n3. Starting event polling and response loop...")

        manager.run_async_polling()  # Start polling VTN in a separate thread

        while manager.poll_thread.is_alive():
            schedule.run_pending()  # This scheduler checks status on Resources and generates reports to VTN
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