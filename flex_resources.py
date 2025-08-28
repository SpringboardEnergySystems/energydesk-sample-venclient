from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from enum import Enum

class ConnectionType(Enum):
    MODBUSTCP = "modbustcp"
    MQTT = "mqtt"
    FILEREADER = "filereader"
    # Add other types as needed

class ActorType(Enum):
    READER = "reader"
    WRITER = "writer"

class ResourceType(Enum):
    DSR = "Demand Response"
    BATTERY = "Battery"

@dataclass
class Connection:
    type: ConnectionType
    actortype: ActorType
    host:  Optional[str] = None
    port:  Optional[int] = None
    topic: Optional[str] = None
    file: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None

@dataclass
class Resource:
    resourceID: str
    resourceName: str
    resourceType: str
    meterPointId: str
    connection: Connection# Link to Connection, used locally to manage asset
    capacities: Dict[str, Any]
    location: Dict[str, Any]
    enabled: Optional[bool] = None
    reporting: Optional[Dict[str, Any]] = None


def load_flexible_resources(
    resources_path: str = './config/flex_resources.json'
) -> Dict[str, Resource]:
    resources={}
    sample_connection = Connection(type=ConnectionType.FILEREADER,
                                   actortype=ActorType.READER,
                                   host=None, port=None, topic=None,
                                   file="./data/elhub_smartmeter_707057500054134059.csv",
                                   username=None, password=None
                                   )
    r1=Resource(resourceID="HOUSEHOLD_1",
                resourceName="Household 1",
                resourceType=ResourceType.DSR.value,
                meterPointId="707057500054134059",
                connection=sample_connection,
                capacities={'P_max_kw':6.0, 'P_min_kw':-6.0, 'E_max_kwh':24.0, 'E_min_kwh':0.0},
                location={'address': 'Testveien 1, 1234 Teststed', 'latitude': 60.123456, 'longitude': 10.123456},
                enabled=True,)
    resources[r1.resourceID]=r1
    return resources