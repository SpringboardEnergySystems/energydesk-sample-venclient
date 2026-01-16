"""
Meter Data Simulator - Manages VEN resources and simulated meter data
Uses Borg pattern for singleton behavior
"""
import logging
import random
import sys
import os
import h5py
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

import environ

logger = logging.getLogger(__name__)
# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from resource_db import ResourceDatabase
from flex_resources import Resource
from venclient.simulation.h5data import list_meters, locating_h5file

logger = logging.getLogger(__name__)


@dataclass
class MeterReading:
    """Represents a single meter reading from a load component"""
    timestamp: int  # Unix timestamp in milliseconds
    load_id: str  # e.g., 'load_0', 'load_1', etc.
    power_w: float  # Power reading in watts


@dataclass
class ResourceMeterData:
    """Represents meter data for a resource with multiple load components"""
    resource_id: str
    meter_point_id: str
    readings: List[MeterReading]  # One or more readings per load component


class MeterDataSimulator:
    """
    Borg pattern singleton for managing VEN resources and simulated meter data.
    All instances share the same state.
    """

    # Shared state for all instances (Borg pattern)
    _shared_state = {}

    def __init__(self, db_path: str = "./config/resources.db"):
        """
        Initialize the simulator. All instances share the same state.

        Args:
            db_path: Path to the SQLite database containing resources
        """
        # Implement Borg pattern - all instances share the same state
        self.__dict__ = self._shared_state

        # Initialize shared state only once
        if not hasattr(self, '_initialized'):
            self._initialized = False
            self.db_path = db_path
            self.db = ResourceDatabase(db_path)

            # Dictionaries to store VEN resources by VEN ID
            self.vens: Dict[str, List[Resource]] = {}

            # Dictionaries to store resources by status for each VEN
            self.pending_resources: Dict[str, Dict[str, Resource]] = {}
            self.approved_resources: Dict[str, Dict[str, Resource]] = {}
            self.suspended_resources: Dict[str, Dict[str, Resource]] = {}

            # Available meters from H5 data
            self.available_meters: List[str] = []

            # H5 file path
            self.h5_file_path: str = locating_h5file()

            # Current timestamp index for each meter (tracks position in H5 data)
            self.current_timestamp_index: int = 0

            # Cache of H5 data length (to know when to wrap around)
            self.h5_data_length: Optional[int] = None

            logger.debug("MeterDataSimulator initialized (Borg pattern)")

    def initialize_resources(self, ven_list: Optional[List[str]] = None):
        """
        Load resources from the database for specified VENs or all VENs.
        Resources are organized by registration status.

        Args:
            ven_list: List of VEN identifiers to load. If None, loads all VENs.
        """
        if self._initialized:
            logger.warning("Resources already initialized. Call reset() first to reload.")
            return

        # Get list of VENs to load
        if ven_list is None:
            ven_list = self.db.get_ven_list()
            logger.debug(f"Loading resources for all VENs: {len(ven_list)} VENs found")

        # Load resources for each VEN
        for ven_id in ven_list[:10]:
            logger.debug(f"Loading resources for VEN: {ven_id}")

            # Get all resources for this VEN
            all_resources = self.db.get_resources_by_ven(ven_id)
            self.vens[ven_id] = all_resources

            # Initialize status dictionaries for this VEN
            self.pending_resources[ven_id] = {}
            self.approved_resources[ven_id] = {}
            self.suspended_resources[ven_id] = {}

            # Organize resources by status
            for resource in all_resources:
                status = resource.registration_status or 'PENDING'
                if random.random() < 0.1:
                    status="APPROVED"

                if status == 'PENDING':
                    self.pending_resources[ven_id][resource.resourceID] = resource
                elif status == 'APPROVED':
                    self.approved_resources[ven_id][resource.resourceID] = resource
                elif status == 'SUSPENDED':
                    self.suspended_resources[ven_id][resource.resourceID] = resource
                else:
                    logger.warning(f"Unknown status '{status}' for resource {resource.resourceID}")
                    self.pending_resources[ven_id][resource.resourceID] = resource

            logger.info(f"  VEN '{ven_id}': "
                       f"{len(self.pending_resources[ven_id])} pending, "
                       f"{len(self.approved_resources[ven_id])} approved, "
                       f"{len(self.suspended_resources[ven_id])} suspended")

        # Load available meters from H5 data
        try:
            self.available_meters = list_meters()
            logger.info(f"Loaded {len(self.available_meters)} available meters from H5 data")
        except Exception as e:
            logger.warning(f"Could not load meters from H5 data: {e}")

        # Assign random meters to approved resources for simulation
        if self.available_meters:
            total_assigned = 0
            for ven_id in self.approved_resources.keys():
                approved = self.approved_resources[ven_id]
                for resource_id, resource in approved.items():
                    # Randomly select a meter from available meters
                    random_meter = random.choice(self.available_meters)
                    # Assign the meter ID to the resource
                    resource.meterPointId = random_meter
                    total_assigned += 1

            if total_assigned > 0:
                logger.info(f"Assigned random meters to {total_assigned} approved resources")
        else:
            logger.warning("No available meters to assign to approved resources")

        self._initialized = True
        logger.info(f"Resource initialization complete for {len(ven_list)} VENs")

    def get_ven_resources(self, ven_id: str, status: Optional[str] = None) -> Dict[str, Resource]:
        """
        Get resources for a specific VEN, optionally filtered by status.

        Args:
            ven_id: VEN identifier
            status: Optional status filter ('PENDING', 'APPROVED', 'SUSPENDED')

        Returns:
            Dictionary of resources keyed by resource_id
        """
        if not self._initialized:
            raise RuntimeError("Resources not initialized. Call initialize_resources() first.")

        if ven_id not in self.vens:
            logger.warning(f"VEN '{ven_id}' not found")
            return {}

        if status is None:
            # Return all resources as a dict
            return {r.resourceID: r for r in self.vens[ven_id]}
        elif status == 'PENDING':
            return self.pending_resources.get(ven_id, {})
        elif status == 'APPROVED':
            return self.approved_resources.get(ven_id, {})
        elif status == 'SUSPENDED':
            return self.suspended_resources.get(ven_id, {})
        else:
            logger.error(f"Invalid status filter: {status}")
            return {}

    def update_resource_status(self, ven_id: str, resource_id: str, new_status: str):
        """
        Update the registration status of a resource and move it to the appropriate dictionary.

        Args:
            ven_id: VEN identifier
            resource_id: Resource identifier
            new_status: New status ('PENDING', 'APPROVED', 'SUSPENDED')
        """
        if not self._initialized:
            raise RuntimeError("Resources not initialized. Call initialize_resources() first.")

        if ven_id not in self.vens:
            logger.error(f"VEN '{ven_id}' not found")
            return

        # Find the resource in current status dictionaries
        resource = None
        old_status = None

        for status_dict, status_name in [
            (self.pending_resources[ven_id], 'PENDING'),
            (self.approved_resources[ven_id], 'APPROVED'),
            (self.suspended_resources[ven_id], 'SUSPENDED')
        ]:
            if resource_id in status_dict:
                resource = status_dict[resource_id]
                old_status = status_name
                del status_dict[resource_id]
                break

        if resource is None:
            logger.error(f"Resource '{resource_id}' not found in VEN '{ven_id}'")
            return

        # Update resource status
        resource.registration_status = new_status

        # Add to new status dictionary
        if new_status == 'PENDING':
            self.pending_resources[ven_id][resource_id] = resource
        elif new_status == 'APPROVED':
            self.approved_resources[ven_id][resource_id] = resource
        elif new_status == 'SUSPENDED':
            self.suspended_resources[ven_id][resource_id] = resource
        else:
            logger.error(f"Invalid status: {new_status}")
            return

        # Update in database
        self.db.update_resource_status(resource_id, new_status)

        logger.info(f"Updated resource '{resource_id}' status from {old_status} to {new_status}")

    def get_statistics(self) -> Dict:
        """
        Get statistics about loaded resources.

        Returns:
            Dictionary with statistics
        """
        if not self._initialized:
            return {"error": "Not initialized"}

        stats = {
            'total_vens': len(self.vens),
            'total_resources': sum(len(resources) for resources in self.vens.values()),
            'by_ven': {},
            'total_by_status': {
                'PENDING': 0,
                'APPROVED': 0,
                'SUSPENDED': 0
            }
        }

        for ven_id in self.vens.keys():
            pending = len(self.pending_resources.get(ven_id, {}))
            approved = len(self.approved_resources.get(ven_id, {}))
            suspended = len(self.suspended_resources.get(ven_id, {}))

            stats['by_ven'][ven_id] = {
                'pending': pending,
                'approved': approved,
                'suspended': suspended,
                'total': pending + approved + suspended
            }

            stats['total_by_status']['PENDING'] += pending
            stats['total_by_status']['APPROVED'] += approved
            stats['total_by_status']['SUSPENDED'] += suspended

        return stats

    def increase_time(self) -> int:
        """
        Increment the timestamp index by 1 to move to the next reading in the H5 data.

        Returns:
            The new timestamp index
        """
        if not self._initialized:
            raise RuntimeError("Resources not initialized. Call initialize_resources() first.")

        # Get the H5 data length if not cached
        if self.h5_data_length is None:
            try:
                with h5py.File(self.h5_file_path, 'r') as hf:
                    # Get length from first available meter's first load
                    first_meter_key = list(hf['meters'].keys())[0]
                    first_meter = hf['meters'][first_meter_key]
                    load_0_power = first_meter['load_0']['power']
                    self.h5_data_length = len(load_0_power)
                    logger.debug(f"H5 data length: {self.h5_data_length}")
            except Exception as e:
                logger.error(f"Error reading H5 data length: {e}")
                raise

        # Increment timestamp index
        self.current_timestamp_index += 1

        # Wrap around if we reach the end
        if self.current_timestamp_index >= self.h5_data_length:
            self.current_timestamp_index = 0
            logger.info("Timestamp index wrapped around to 0")

        logger.debug(f"Timestamp index increased to {self.current_timestamp_index}")
        return self.current_timestamp_index

    def collect_next_metering(self, ven_id: str) -> Dict[str, ResourceMeterData]:
        """
        Collect the next meter readings for all approved resources of a VEN.
        Each resource may have multiple load components.

        Args:
            ven_id: VEN identifier

        Returns:
            Dictionary mapping resource_id to ResourceMeterData with list of readings
        """
        if not self._initialized:
            raise RuntimeError("Resources not initialized. Call initialize_resources() first.")

        if ven_id not in self.vens:
            logger.warning(f"VEN '{ven_id}' not found")
            return {}

        # Get approved resources for this VEN
        approved = self.approved_resources.get(ven_id, {})

        if not approved:
            logger.debug(f"No approved resources for VEN '{ven_id}'")
            return {}

        result: Dict[str, ResourceMeterData] = {}

        try:
            with h5py.File(self.h5_file_path, 'r') as hf:
                meters_group = hf['meters']

                for resource_id, resource in approved.items():
                    meter_point_id = resource.meterPointId

                    # Find the meter in H5 file
                    meter_key = f"meter_{meter_point_id}"

                    if meter_key not in meters_group:
                        logger.warning(f"Meter {meter_key} not found in H5 file for resource {resource_id}")
                        continue

                    meter_group = meters_group[meter_key]
                    readings: List[MeterReading] = []

                    # Read all load components (load_0 through load_5)
                    num_loads = meter_group.attrs.get('num_load_components', 6)

                    for load_idx in range(num_loads):
                        load_key = f'load_{load_idx}'

                        if load_key not in meter_group:
                            continue

                        load_group = meter_group[load_key]
                        power_data = load_group['power']

                        # Get the reading at current timestamp index
                        if self.current_timestamp_index < len(power_data):
                            timestamp_ms = int(power_data[self.current_timestamp_index][0] * 1000)  # Convert to milliseconds
                            power_w = float(power_data[self.current_timestamp_index][1])

                            reading = MeterReading(
                                timestamp=timestamp_ms,
                                load_id=load_key,
                                power_w=power_w
                            )
                            readings.append(reading)

                    # Create ResourceMeterData with all readings for this resource
                    if readings:
                        resource_meter_data = ResourceMeterData(
                            resource_id=resource_id,
                            meter_point_id=meter_point_id,
                            readings=readings
                        )
                        result[resource_id] = resource_meter_data

                logger.info(f"Collected meter data for {len(result)} resources in VEN '{ven_id}' at index {self.current_timestamp_index}")

        except Exception as e:
            logger.error(f"Error collecting meter data for VEN '{ven_id}': {e}")
            raise

        return result

    def reset(self):
        """
        Reset the simulator state. Useful for testing or reloading data.
        """
        self._initialized = False
        self.vens.clear()
        self.pending_resources.clear()
        self.approved_resources.clear()
        self.suspended_resources.clear()
        self.available_meters.clear()
        self.current_timestamp_index = 0
        self.h5_data_length = None
        logger.info("MeterDataSimulator reset")

    def get_ven_list(self) -> List[str]:
        """
        Get list of all loaded VEN identifiers.

        Returns:
            List of VEN identifiers
        """
        return list(self.vens.keys())


# Convenience function for initialization
def initialize_simulator(ven_list: Optional[List[str]] = None,
                        db_path: str = "./config/resources.db") -> MeterDataSimulator:
    """
    Initialize and return the MeterDataSimulator singleton.

    Args:
        ven_list: List of VEN identifiers to load. If None, loads all VENs.
        db_path: Path to the SQLite database

    Returns:
        MeterDataSimulator instance
    """
    simulator = MeterDataSimulator(db_path)
    if not simulator._initialized:
        simulator.initialize_resources(ven_list)
    return simulator
