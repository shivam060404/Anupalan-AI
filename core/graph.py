"""
Anupalan AI - LangGraph Workflow
==================================
Orchestrates the 5-agent cyclic compliance pipeline:
ingest -> graphrag_translate -> map_generate -> hitl_router ->
  [cco_review | route] -> validate -> close
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from langgraph.graph import StateGraph, END

from core.state import AnupalanState
from agents.ria import RegulatoryIngestionAgent
from agents.lta import LegalTranslationAgent
from agents.mga import MAPGeneratorAgent
from agents.ora import OrchestrationRoutingAgent
from agents.ava import AutonomousValidationAgent
from services.audit_log import AuditLogService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent Node Functions
# ---------------------------------------------------------------------------

# Initialize agents (singletons)
_ria = RegulatoryIngestionAgent()
_lta = LegalTranslationAgent()
_mga = MAPGeneratorAgent()
_ora = OrchestrationRoutingAgent()
_ava = AutonomousValidationAgent()
_audit = AuditLogService()


def ingest_node(state: AnupalanState) -> dict:
    """
    Node 1: Regulatory Ingestion Agent
    Fetches, parses, and deduplicates regulatory circulars.
    """
    logger.info("=== NODE: ingest_node (Agent 1 - RIA) ===")
    result = _ria.run(state)

    _audit.log(
        pipeline_run_id=result.get("pipeline_run_id", state.get("pipeline_run_id", "unknown")),
        agent="RIA",
        action="INGESTION_COMPLETE",
        details={
            "circular_id": result.get("regulatory_event", {}).circular_id
            if result.get("regulatory_event") else "N/A",
            "source": result.get("regulatory_event", {}).source
            if result.get("regulatory_event") else "N/A",
        },
        status="SUCCESS" if result.get("regulatory_event") else "FAILED",
    )

    return result


def graphrag_translate_node(state: AnupalanState) -> dict:
    """
    Node 2: Legal Translation Agent (GraphRAG)
    Maps circular text to internal policies via Knowledge Graph.
    """
    logger.info("=== NODE: graphrag_translate_node (Agent 2 - LTA) ===")
    result = _lta.run(state)

    run_id = state.get("pipeline_run_id", "unknown")
    _audit.log(
        pipeline_run_id=run_id,
        agent="LTA",
        action="DELTA_ANALYSIS_COMPLETE",
        details={
            "intersecting_policies": len(result.get("policy_delta", {}).intersecting_policies)
            if result.get("policy_delta") else 0,
            "new_requirements": len(result.get("policy_delta", {}).new_requirements)
            if result.get("policy_delta") else 0,
            "risk_assessment": result.get("policy_delta", {}).risk_assessment
            if result.get("policy_delta") else "N/A",
        },
        status="SUCCESS" if result.get("policy_delta") else "FAILED",
    )

    return result


def map_generate_node(state: AnupalanState) -> dict:
    """
    Node 3: MAP Generator Agent
    Converts PolicyDelta into Measurable Action Points.
    """
    logger.info("=== NODE: map_generate_node (Agent 3 - MGA) ===")
    result = _mga.run(state)

    run_id = state.get("pipeline_run_id", "unknown")
    maps = result.get("maps", [])
    _audit.log(
        pipeline_run_id=run_id,
        agent="MGA",
        action="MAPS_GENERATED",
        details={
            "total_maps": len(maps),
            "hitl_required": len(result.get("hitl_required_maps", [])),
            "departments": list(set(m.department for m in maps)),
        },
    )

    return result


def hitl_router(state: AnupalanState) -> str:
    """
    Conditional Edge: Routes to CCO review if any MAP requires HITL approval.
    
    Returns:
        "cco_review" if HITL required
        "route" if no HITL needed
    """
    hitl_maps = state.get("hitl_required_maps", [])
    hitl_approved = state.get("hitl_approval", False)

    if hitl_maps and not hitl_approved:
        logger.info(
            "=== HITL ROUTER: %d MAPs require CCO approval. Routing to cco_review ===",
            len(hitl_maps),
        )
        return "cco_review"

    logger.info("=== HITL ROUTER: No HITL required or already approved. Proceeding to route ===")
    return "route"


def cco_review_node(state: AnupalanState) -> dict:
    """
    Human-in-the-Loop: CCO Review Node.
    
    In production: Uses LangGraph interrupt() to pause and wait for CCO approval.
    In prototype: Auto-approves after logging the review requirement.
    
    The /api/hitl/approve endpoint sets hitl_approval=True and resumes the graph.
    """
    logger.info("=== NODE: cco_review_node (HITL - CCO Review) ===")

    hitl_maps = state.get("hitl_required_maps", [])
    maps = state.get("maps", [])

    # Log HITL requirement
    logger.info(
        "CCO REVIEW REQUIRED for MAPs: %s",
        ", ".join(hitl_maps),
    )

    # For demo: show what CCO would see
    review_summary = []
    for m in maps:
        if m.map_id in hitl_maps:
            review_summary.append({
                "map_id": m.map_id,
                "department": m.department,
                "risk_score": m.risk_score,
                "priority": m.priority,
                "instructions_preview": m.instructions[:2] if m.instructions else [],
            })

    _audit.log(
        pipeline_run_id=state.get("pipeline_run_id", "unknown"),
        agent="HITL",
        action="CCO_REVIEW_REQUIRED",
        details={"maps_for_review": review_summary},
    )

    # In prototype mode, auto-approve
    # In production, this would use interrupt() and wait for /api/hitl/approve
    logger.info("CCO REVIEW: Auto-approving for prototype demo")
    return {"hitl_approval": True, "current_agent": "HITL"}


def route_node(state: AnupalanState) -> dict:
    """
    Node 4: Orchestration & Routing Agent
    Dispatches MAPs to departments via ServiceNow.
    """
    logger.info("=== NODE: route_node (Agent 4 - ORA) ===")
    return _ora.run(state)


def validate_node(state: AnupalanState) -> dict:
    """
    Node 5: Autonomous Validation Agent
    Verifies MAP completion via enterprise system queries.
    """
    logger.info("=== NODE: validate_node (Agent 5 - AVA) ===")
    return _ava.run(state)


def close_node(state: AnupalanState) -> dict:
    """
    Finalizer: Marks the pipeline as complete and generates final report.
    """
    logger.info("=== NODE: close_node (Pipeline Finalizer) ===")

    maps = state.get("maps", [])
    evidence = state.get("validation_evidence", [])

    validated = sum(1 for e in evidence if e.validation_status == "SUCCESS")
    pending = sum(1 for e in evidence if e.validation_status == "PENDING")
    failed = sum(1 for e in evidence if e.validation_status == "FAILED")

    final_status = "COMPLETED"
    if failed > 0:
        final_status = "COMPLETED_WITH_FAILURES"

    _audit.log(
        pipeline_run_id=state.get("pipeline_run_id", "unknown"),
        agent="PIPELINE",
        action="PIPELINE_COMPLETE",
        details={
            "total_maps": len(maps),
            "validated": validated,
            "pending": pending,
            "failed": failed,
            "final_status": final_status,
        },
    )

    logger.info(
        "Pipeline complete: %d MAPs processed, %d validated, %d pending, %d failed",
        len(maps), validated, pending, failed,
    )

    return {
        "final_status": final_status,
        "completed_at": datetime.utcnow().isoformat() + "Z",
        "current_agent": "CLOSED",
    }


def error_handler_node(state: AnupalanState) -> dict:
    """
    Error handler: Catches pipeline errors and routes to human escalation.
    """
    logger.error("=== NODE: error_handler_node (Human Escalation) ===")
    errors = state.get("errors", [])

    _audit.log(
        pipeline_run_id=state.get("pipeline_run_id", "unknown"),
        agent="PIPELINE",
        action="ESCALATED_TO_HUMAN",
        details={"errors": errors},
        status="ESCALATED",
    )

    return {
        "final_status": "ESCALATED_TO_HUMAN",
        "completed_at": datetime.utcnow().isoformat() + "Z",
        "current_agent": "ERROR_HANDLER",
    }


# ---------------------------------------------------------------------------
# Graph Construction
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """
    Construct the Anupalan AI LangGraph StateGraph.
    
    Flow:
        ingest -> graphrag_translate -> map_generate -> hitl_router
            -> [cco_review -> route | route]
        -> validate -> close -> END
        
    Error handling:
        Any node error -> error_handler -> END
    """
    workflow = StateGraph(AnupalanState)

    # Add nodes
    workflow.add_node("ingest", ingest_node)
    workflow.add_node("graphrag_translate", graphrag_translate_node)
    workflow.add_node("map_generate", map_generate_node)
    workflow.add_node("cco_review", cco_review_node)
    workflow.add_node("route", route_node)
    workflow.add_node("validate", validate_node)
    workflow.add_node("close", close_node)
    workflow.add_node("error_handler", error_handler_node)

    # Set entry point
    workflow.set_entry_point("ingest")

    # Linear flow
    workflow.add_edge("ingest", "graphrag_translate")
    workflow.add_edge("graphrag_translate", "map_generate")

    # Conditional HITL routing
    workflow.add_conditional_edges(
        "map_generate",
        hitl_router,
        {
            "cco_review": "cco_review",
            "route": "route",
        },
    )

    # After CCO review, proceed to routing
    workflow.add_edge("cco_review", "route")

    # Continue pipeline
    workflow.add_edge("route", "validate")
    workflow.add_edge("validate", "close")
    workflow.add_edge("close", END)
    workflow.add_edge("error_handler", END)

    return workflow


def compile_graph():
    """Compile the LangGraph workflow into an executable graph."""
    workflow = build_graph()
    return workflow.compile()


def run_pipeline(initial_state: Optional[dict] = None) -> AnupalanState:
    """
    Run the full Anupalan AI compliance pipeline.
    
    Args:
        initial_state: Optional partial state to initialize with
        
    Returns:
        Final AnupalanState after pipeline completion
    """
    graph = compile_graph()

    # Initialize state
    state = {
        "regulatory_event": None,
        "policy_delta": None,
        "maps": [],
        "routing_logs": [],
        "validation_evidence": [],
        "hitl_approval": False,
        "hitl_required_maps": [],
        "current_agent": "",
        "errors": [],
        "final_status": "",
        "pipeline_run_id": uuid.uuid4().hex[:12],
        "started_at": datetime.utcnow().isoformat() + "Z",
        "completed_at": "",
    }

    if initial_state:
        state.update(initial_state)

    logger.info("=" * 60)
    logger.info("ANUPALAN AI - Compliance Pipeline Starting")
    logger.info("Run ID: %s", state["pipeline_run_id"])
    logger.info("=" * 60)

    try:
        # Reset RIA dedup state so re-runs process the circular fresh
        _ria.reset()
        result = graph.invoke(state)
        return result
    except Exception as e:
        logger.error("Pipeline execution failed: %s", e)
        state["errors"].append(f"Pipeline error: {str(e)}")
        state["final_status"] = "PIPELINE_ERROR"
        return state
