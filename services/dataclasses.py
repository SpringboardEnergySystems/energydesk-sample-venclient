# This file contains the dataclasses used in the coordinator module.
# They  sould contain properties matching the fields in file /config/mapping.json
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import json
import os
from enum import Enum
from podlogger import loginfo, logwarn
class ConnectionType(Enum):
    MODBUSTCP = "modbustcp"
    MQTT = "mqtt"
    FILEREADER = "filereader"
    # Add other types as needed

class ActorType(Enum):
    READER = "reader"
    WRITER = "writer"

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
class Mapping:
    resourceID: str
    connection: Connection
    resource: Optional['Resource'] = None  # Link to Resource

@dataclass
class Resource:
    resourceID: str
    resourceName: str
    resourceType: str
    meterPointId: str
    capacities: Dict[str, Any]
    location: Dict[str, Any]
    enabled: Optional[bool] = None
    reporting: Optional[Dict[str, Any]] = None

def load_mappings_and_resources(
    mapping_path: str = os.path.join(os.path.dirname(__file__), '../config/mapping.json'),
    resources_path: str = os.path.join(os.path.dirname(__file__), '../config/resources.json')
) -> Dict[str, Dict]:
    """
    Loads mappings and resources from configuration files and links them.
    Returns a list of Mapping objects with their Resource attached.
    """
    # Load resources
    with open(resources_path, 'r') as f:
        resources_data = json.load(f)
    resources = {r['resourceID']: Resource(
        resourceID=r['resourceID'],
        resourceName=r['resourceName'],
        resourceType=r['resourceType'],
        meterPointId=r['meterPointId'],
        capacities=r['capacities'],
        location=r['location'],
        enabled=r.get('enabled'),
        reporting=r.get('reporting')
    ) for r in resources_data}
    resource_map={}
    for resource in resources.values():
        #if resource.reporting is not None:
            #print(resource.reporting)
            #resource.reporting=json.loads(str(resource.reporting).replace("'", '"'))
            #print(resource.reporting)
        resource_map[resource.resourceID] = {'resource':resource}
    # Load mappings
    with open(mapping_path, 'r') as f:
        mappings_data = json.load(f)

    mapping_objs = []
    for m in mappings_data:
        conn_data = m['connection']
        conn_type = ConnectionType(conn_data['type'].lower())
        actor_type = ActorType(conn_data['actortype'].lower())
        loginfo(f"Creating connection for resource {m['resourceID']} with type {conn_type} and actor type {actor_type}")
        conn = Connection(
            type=conn_type,
            actortype=actor_type,
            host=conn_data.get('host'),
            port=conn_data.get('port'),
            topic=conn_data.get('topic'),
            file=conn_data.get('file'),
            username=conn_data.get('username'),
            password=conn_data.get('password')
        )
        resource = resources.get(m['resourceID'])
        mapping_objs.append(Mapping(resourceID=m['resourceID'], connection=conn, resource=resource))

    complete_map={}
    for m in mapping_objs:
        if m.resourceID in resource_map:
            m.resource = resource_map[m.resourceID]['resource']
            resource_map[m.resourceID]['mapping'] = m
            complete_map[m.resourceID] = resource_map[m.resourceID]

    return complete_map
