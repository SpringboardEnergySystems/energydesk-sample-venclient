import logging

from fastapi import FastAPI
import os, json, asyncio
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from nats.aio.client import Client as NATS
from nats.js.api import ConsumerConfig
from common.schemas import Command, ResultEvent, TelemetryEvent, HeartbeatEvent, utcnow
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
SITE = os.getenv("SITE", "NO1")
VEN_INSTANCE = os.getenv("VEN_INSTANCE", "ven-1")

app = FastAPI(title="VEN Ops",    description="VEN Services.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc")

nc = NATS()
js = None

# Simple in-memory state for ops dashboard
state: Dict[str, Any] = {
    "workers": {},   # worker_id -> heartbeat dict
    "devices": {},   # (site, device) -> last telemetry/result
    "commands": {},  # command_id -> last result/status
}

# For SSE subscribers
sse_subscribers: List[asyncio.Queue] = []

def push_sse(event: str, data: dict):
    msg = f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
    for q in list(sse_subscribers):
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass

@app.on_event("startup")
async def startup():
    global js
    await nc.connect(servers=[NATS_URL], name=VEN_INSTANCE)
    js = nc.jetstream()

    # Subscribe to worker events
    await nc.subscribe("evt.modus.result.>", cb=_on_result)
    await nc.subscribe("evt.modus.telemetry.>", cb=_on_telemetry)
    await nc.subscribe("evt.modus.heartbeat.>", cb=_on_heartbeat)

@app.on_event("shutdown")
async def shutdown():
    await nc.drain()

async def _on_result(msg):
    try:
        evt = ResultEvent.model_validate_json(msg.data)
    except Exception as e:
        return

    state["commands"][evt.command_id] = evt.model_dump()
    dev_key = f"{evt.site}:{evt.device}"
    state["devices"].setdefault(dev_key, {})
    state["devices"][dev_key]["last_result"] = evt.model_dump()
    state["devices"][dev_key]["ts"] = evt.ts.isoformat()
    push_sse("result", evt.model_dump())

async def _on_telemetry(msg):
    try:
        tel = TelemetryEvent.model_validate_json(msg.data)
    except Exception:
        return

    dev_key = f"{tel.site}:{tel.device}"
    state["devices"].setdefault(dev_key, {})
    state["devices"][dev_key]["last_telemetry"] = tel.model_dump()
    state["devices"][dev_key]["ts"] = tel.ts.isoformat()
    push_sse("telemetry", tel.model_dump())

async def _on_heartbeat(msg):
    try:
        hb = HeartbeatEvent.model_validate_json(msg.data)
    except Exception:
        return

    state["workers"][hb.worker_id] = hb.model_dump()
    push_sse("heartbeat", hb.model_dump())

    # If heartbeat carries a device_id, update the matching resource in DB
    if hb.device_id:
        try:
            from venserver.datamodel.database import SessionLocal
            from venserver.datamodel.models import FlexibleResource
            db = SessionLocal()
            try:
                resource = db.query(FlexibleResource).filter(
                    FlexibleResource.resource_external_id == hb.device_id
                ).first()
                if resource:
                    resource.last_heartbeat_at = datetime.now(timezone.utc)
                    resource.last_heartbeat_worker = hb.worker_id
                    db.commit()
                    push_sse("resource_heartbeat", {
                        "device_id": hb.device_id,
                        "worker_id": hb.worker_id,
                        "ts": hb.ts.isoformat(),
                    })
            finally:
                db.close()
        except Exception as e:
            logger.warning("Failed to persist heartbeat for device %s: %s", hb.device_id, e)

@app.get("/ops/status")
async def ops_status():
    return {
        "site": SITE,
        "now": utcnow().isoformat(),
        "workers": state["workers"],
        "devices": state["devices"],
    }

@app.post("/ops/command")
async def ops_command(body: Dict[str, Any]):
    """
    body example:
    {
      "type":"setpoint",
      "device":"battery_1",
      "payload":{"p_kw": 10.0}
    }
    """
    cmd_type = body.get("type")
    device = body.get("device")
    payload = body.get("payload", {})

    if cmd_type not in ("setpoint", "read"):
        raise HTTPException(400, "type must be setpoint or read")
    if not device:
        raise HTTPException(400, "device is required")

    cmd = Command(type=cmd_type, site=SITE, device=device, payload=payload)

    subject = f"cmd.modus.{cmd.type}.{cmd.site}.{cmd.device}"
    await nc.publish(subject, cmd.model_dump_json().encode("utf-8"))
    state["commands"][cmd.command_id] = {
        "status": "pending",
        "command": cmd.model_dump(),
        "published_subject": subject,
        "published_at": utcnow().isoformat(),
    }
    push_sse("command", state["commands"][cmd.command_id])

    return {"command_id": cmd.command_id, "subject": subject}

@app.get("/ops/commands/{command_id}")
async def get_command(command_id: str):
    if command_id not in state["commands"]:
        raise HTTPException(404, "unknown command_id")
    return state["commands"][command_id]

@app.get("/ops/stream")
async def ops_stream():
    """
    Server-Sent Events stream for live updates.
    """
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    sse_subscribers.append(q)

    async def gen():
        # initial hello
        yield f"event: hello\ndata: {json.dumps({'ven': VEN_INSTANCE, 'site': SITE})}\n\n"
        try:
            while True:
                msg = await q.get()
                yield msg
        finally:
            if q in sse_subscribers:
                sse_subscribers.remove(q)

    return StreamingResponse(gen(), media_type="text/event-stream")
