"""
Anupalan AI - FastAPI Backend
===============================
Exposes REST endpoints for the compliance pipeline, state management,
HITL approvals, and real-time pipeline status via SSE.
"""

import sys
import logging
import uuid
import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add backend root to path
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from core.state import AnupalanState, MeasurableActionPoint
from core.graph import run_pipeline, compile_graph
from services.audit_log import AuditLogService
from mocks.service_now import MockServiceNowAPI

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("anupalan_api")

# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Anupalan AI - Regulatory Compliance Platform",
    description="Autonomous multi-agent regulatory compliance system for Canara Bank",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared state
audit_log = AuditLogService()
service_now = MockServiceNowAPI()
_pipeline_states: dict[str, dict] = {}
_pipeline_events: dict[str, list[dict]] = {}


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------

class TriggerRequest(BaseModel):
    """Request to trigger a new pipeline run."""
    circular_text: Optional[str] = None
    source: Optional[str] = "RBI"


class HITLApprovalRequest(BaseModel):
    """Request to approve HITL-gated MAPs."""
    pipeline_run_id: str
    approved_by: str = "CCO"
    approved_map_ids: list[str] = []
    comments: str = ""


class PipelineStatusResponse(BaseModel):
    """Pipeline run status."""
    pipeline_run_id: str
    current_agent: str
    final_status: str
    total_maps: int
    validated_maps: int
    hitl_pending: bool
    errors: list[str]


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Anupalan AI",
        "version": "1.0.0",
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.post("/api/trigger_ingestion")
async def trigger_ingestion(request: TriggerRequest = None):
    """
    Trigger the full compliance pipeline starting from ingestion.
    Returns the pipeline_run_id for status tracking.
    """
    pipeline_run_id = uuid.uuid4().hex[:12]

    # Run pipeline in background
    asyncio.create_task(_run_pipeline_async(pipeline_run_id, request))

    return {
        "pipeline_run_id": pipeline_run_id,
        "status": "STARTED",
        "message": "Pipeline execution started. Use /api/pipeline/{run_id}/status to track progress.",
    }


async def _run_pipeline_async(pipeline_run_id: str, request: Optional[TriggerRequest] = None):
    """Run the pipeline asynchronously and track state."""
    _pipeline_events[pipeline_run_id] = []

    def emit_event(agent: str, status: str, details: dict = None):
        event = {
            "agent": agent,
            "status": status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "details": details or {},
        }
        _pipeline_events[pipeline_run_id].append(event)

    try:
        emit_event("PIPELINE", "STARTED", {"run_id": pipeline_run_id})

        initial_state = {"pipeline_run_id": pipeline_run_id}

        # Run the pipeline
        result = await asyncio.to_thread(run_pipeline, initial_state)

        # Store final state
        _pipeline_states[pipeline_run_id] = _serialize_state(result)

        emit_event("PIPELINE", "COMPLETED", {
            "final_status": result.get("final_status", "UNKNOWN"),
            "total_maps": len(result.get("maps", [])),
        })

    except Exception as e:
        logger.error("Pipeline %s failed: %s", pipeline_run_id, e)
        emit_event("PIPELINE", "ERROR", {"error": str(e)})
        _pipeline_states[pipeline_run_id] = {
            "pipeline_run_id": pipeline_run_id,
            "final_status": "ERROR",
            "errors": [str(e)],
        }


@app.get("/api/pipeline/{run_id}/status")
async def get_pipeline_status(run_id: str):
    """Get the current status of a pipeline run."""
    # Start with memory events
    mem_events = _pipeline_events.get(run_id, [])
    
    # Query database audit logs and map them to events
    db_logs = audit_log.get_logs(pipeline_run_id=run_id)
    db_events = []
    for log in db_logs:
        details_dict = {}
        if log.get("details"):
            try:
                details_dict = json.loads(log["details"]) if isinstance(log["details"], str) else log["details"]
            except Exception:
                pass
        
        timestamp = log["timestamp"]
        if not timestamp.endswith("Z"):
            timestamp += "Z"
            
        db_events.append({
            "agent": f"{log['agent']} ({log['action']})",
            "status": log["status"],
            "timestamp": timestamp,
            "details": details_dict,
        })
        
    events = list(mem_events) + db_events
    
    # Deduplicate
    seen_keys = set()
    deduped_events = []
    for e in events:
        key = (e["agent"], e["status"], e["timestamp"])
        if key not in seen_keys:
            seen_keys.add(key)
            deduped_events.append(e)
            
    deduped_events.sort(key=lambda x: x["timestamp"])

    state = _pipeline_states.get(run_id)

    if state:
        maps = state.get("maps", [])
        return {
            "pipeline_run_id": run_id,
            "current_agent": state.get("current_agent", "UNKNOWN"),
            "final_status": state.get("final_status", "IN_PROGRESS"),
            "total_maps": len(maps),
            "validated_maps": sum(
                1 for m in maps if m.get("status") == "VALIDATED"
            ),
            "maps": maps,
            "routing_logs": state.get("routing_logs", []),
            "validation_evidence": state.get("validation_evidence", []),
            "hitl_pending": len(state.get("hitl_required_maps", [])) > 0 and not state.get("hitl_approval", False),
            "errors": state.get("errors", []),
            "events": deduped_events,
        }

    # Still running or not found
    if run_id in _pipeline_events:
        return {
            "pipeline_run_id": run_id,
            "current_agent": deduped_events[-1]["agent"] if deduped_events else "UNKNOWN",
            "final_status": "IN_PROGRESS",
            "total_maps": 0,
            "validated_maps": 0,
            "maps": [],
            "routing_logs": [],
            "validation_evidence": [],
            "hitl_pending": False,
            "errors": [],
            "events": deduped_events,
        }

    raise HTTPException(status_code=404, detail=f"Pipeline run {run_id} not found")


@app.get("/api/pipeline/{run_id}/stream")
async def stream_pipeline(run_id: str):
    """SSE endpoint for real-time pipeline progress."""
    async def event_generator():
        sent_keys = set()
        while True:
            mem_events = _pipeline_events.get(run_id, [])
            
            db_logs = audit_log.get_logs(pipeline_run_id=run_id)
            db_events = []
            for log in db_logs:
                details_dict = {}
                if log.get("details"):
                    try:
                        details_dict = json.loads(log["details"]) if isinstance(log["details"], str) else log["details"]
                    except Exception:
                        pass
                
                timestamp = log["timestamp"]
                if not timestamp.endswith("Z"):
                    timestamp += "Z"
                    
                db_events.append({
                    "agent": f"{log['agent']} ({log['action']})",
                    "status": log["status"],
                    "timestamp": timestamp,
                    "details": details_dict,
                })
                
            all_events = list(mem_events) + db_events
            
            # Deduplicate
            seen_keys = set()
            deduped_events = []
            for e in all_events:
                key = (e["agent"], e["status"], e["timestamp"])
                if key not in seen_keys:
                    seen_keys.add(key)
                    deduped_events.append(e)
                    
            deduped_events.sort(key=lambda x: x["timestamp"])
            
            for event in deduped_events:
                event_key = f"{event['agent']}_{event['status']}_{event['timestamp']}"
                if event_key not in sent_keys:
                    yield {"event": "pipeline_update", "data": json.dumps(event)}
                    sent_keys.add(event_key)

            # Check if pipeline is complete
            state = _pipeline_states.get(run_id)
            if state and state.get("final_status"):
                yield {"event": "complete", "data": json.dumps({"final_status": state["final_status"]})}
                break

            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())


@app.post("/api/hitl/approve")
async def approve_hitl(request: HITLApprovalRequest):
    """
    Approve HITL-gated MAPs (CCO sign-off).
    Resumes the pipeline after CCO review.
    """
    audit_log.log(
        pipeline_run_id=request.pipeline_run_id,
        agent="HITL",
        action="CCO_APPROVAL_GRANTED",
        details={
            "approved_by": request.approved_by,
            "approved_maps": request.approved_map_ids,
            "comments": request.comments,
        },
    )

    # Update pipeline state
    state = _pipeline_states.get(request.pipeline_run_id)
    if state:
        state["hitl_approval"] = True

    return {
        "status": "APPROVED",
        "pipeline_run_id": request.pipeline_run_id,
        "approved_by": request.approved_by,
        "message": "CCO approval recorded. Pipeline will resume.",
    }


@app.get("/api/graph_state")
async def get_graph_state():
    """Get the LangGraph workflow structure."""
    return {
        "nodes": [
            {"id": "ingest", "agent": "RIA", "description": "Regulatory Ingestion - Fetch & parse circulars"},
            {"id": "graphrag_translate", "agent": "LTA", "description": "Legal Translation via GraphRAG"},
            {"id": "map_generate", "agent": "MGA", "description": "Generate Measurable Action Points"},
            {"id": "hitl_router", "agent": "ROUTER", "description": "Conditional HITL routing"},
            {"id": "cco_review", "agent": "HITL", "description": "CCO Review (Human-in-the-Loop)"},
            {"id": "route", "agent": "ORA", "description": "Route MAPs to departments via ServiceNow"},
            {"id": "validate", "agent": "AVA", "description": "Autonomous validation of MAP completion"},
            {"id": "close", "agent": "FINALIZER", "description": "Pipeline finalization & reporting"},
        ],
        "edges": [
            {"from": "ingest", "to": "graphrag_translate"},
            {"from": "graphrag_translate", "to": "map_generate"},
            {"from": "map_generate", "to": "hitl_router", "conditional": True},
            {"from": "hitl_router", "to": "cco_review", "condition": "risk_score >= 8.0"},
            {"from": "hitl_router", "to": "route", "condition": "no HITL required"},
            {"from": "cco_review", "to": "route"},
            {"from": "route", "to": "validate"},
            {"from": "validate", "to": "close"},
        ],
    }


@app.get("/api/audit_logs")
async def get_audit_logs(pipeline_run_id: Optional[str] = None, limit: int = 50):
    """Query the immutable audit log."""
    logs = audit_log.get_logs(pipeline_run_id=pipeline_run_id)
    return {"logs": logs[:limit], "total": len(logs)}


@app.get("/api/dashboard/summary")
async def dashboard_summary():
    """Get high-level dashboard summary."""
    all_logs = audit_log.get_logs()
    total_runs = len(set(l.get("pipeline_run_id", "") for l in all_logs))

    completed_runs = [
        s for s in _pipeline_states.values()
        if s.get("final_status") in ("COMPLETED", "COMPLETED_WITH_FAILURES")
    ]

    total_maps = sum(len(s.get("maps", [])) for s in completed_runs)
    validated_maps = sum(
        sum(1 for m in s.get("maps", []) if m.get("status") == "VALIDATED")
        for s in completed_runs
    )

    return {
        "total_pipeline_runs": total_runs,
        "completed_runs": len(completed_runs),
        "total_maps_generated": total_maps,
        "total_maps_validated": validated_maps,
        "recent_runs": list(_pipeline_states.keys())[-5:],
        "system_status": "operational",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_state(state: dict) -> dict:
    """Serialize state for JSON response."""
    serialized = {}
    for key, value in state.items():
        if hasattr(value, "model_dump"):
            serialized[key] = value.model_dump()
        elif isinstance(value, list) and value and hasattr(value[0], "model_dump"):
            serialized[key] = [v.model_dump() for v in value]
        else:
            serialized[key] = value
    return serialized


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
