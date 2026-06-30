"""
Agent 4: Orchestration & Routing Agent (ORA)
==============================================
Assigns MAPs to departments via ServiceNow/Jira.
Logs all routing actions to the audit trail.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from core.state import AnupalanState, MeasurableActionPoint, RoutingLog
from mocks.service_now import MockServiceNowAPI
from services.audit_log import AuditLogService

logger = logging.getLogger(__name__)


class OrchestrationRoutingAgent:
    """
    Agent 4 - Routes MAPs to the correct department via ServiceNow.
    
    1. Authenticates with MockServiceNow via OAuth2
    2. Creates an incident ticket for each MAP
    3. Logs all routing actions to SQLite audit log
    4. Updates MAP status to DISPATCHED
    """

    # Priority mapping from MAP priority to ServiceNow priority
    PRIORITY_MAP = {
        "CRITICAL": 1,
        "HIGH": 2,
        "MEDIUM": 3,
        "LOW": 4,
    }

    def __init__(
        self,
        service_now: Optional[MockServiceNowAPI] = None,
        audit_log: Optional[AuditLogService] = None,
    ):
        self.service_now = service_now or MockServiceNowAPI()
        self.audit_log = audit_log or AuditLogService()

    def run(self, state: AnupalanState) -> dict:
        """
        Route all MAPs to their respective departments.
        
        Args:
            state: LangGraph state with maps populated
            
        Returns:
            dict with routing_logs and updated map statuses
        """
        logger.info("[ORA] Starting MAP routing...")

        maps = state.get("maps", [])
        if not maps:
            return {
                "errors": state.get("errors", []) + ["ORA: No MAPs to route"],
                "current_agent": "ORA",
                "final_status": "ERROR_ORA_NO_MAPS",
            }

        # Authenticate with ServiceNow
        self._authenticate()

        routing_logs = []
        pipeline_run_id = state.get("pipeline_run_id", "unknown")

        for m in maps:
            try:
                log_entry = self._route_map(m, pipeline_run_id)
                routing_logs.append(log_entry)
                m.status = "DISPATCHED"
                logger.info(
                    "[ORA] Routed MAP %s to %s (Ticket: %s)",
                    m.map_id, m.department, log_entry.get("ticket_id", "N/A"),
                )
            except Exception as e:
                logger.error("[ORA] Failed to route MAP %s: %s", m.map_id, e)
                error_log = {
                    "map_id": m.map_id,
                    "department": m.department,
                    "ticket_id": "",
                    "action": "ROUTE_FAILED",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "status": "FAILED",
                    "error": str(e),
                }
                routing_logs.append(error_log)
                m.status = "FAILED"

                self.audit_log.log(
                    pipeline_run_id=pipeline_run_id,
                    agent="ORA",
                    action="ROUTE_FAILED",
                    map_id=m.map_id,
                    department=m.department,
                    details={"error": str(e)},
                    status="FAILED",
                )

        logger.info(
            "[ORA] Routing complete. %d/%d MAPs dispatched successfully.",
            sum(1 for l in routing_logs if l.get("status") != "FAILED"),
            len(maps),
        )

        return {
            "maps": maps,
            "routing_logs": routing_logs,
            "current_agent": "ORA",
        }

    def _authenticate(self):
        """Authenticate with ServiceNow via OAuth2."""
        try:
            self.service_now.authenticate(
                client_id="mock_client_id_anupalan",
                client_secret="mock_client_secret_anupalan",
            )
        except PermissionError as e:
            logger.error("[ORA] ServiceNow authentication failed: %s", e)
            raise

    def _route_map(self, m: MeasurableActionPoint, pipeline_run_id: str) -> dict:
        """
        Create a ServiceNow incident for a single MAP.
        
        Args:
            m: The MAP to route
            pipeline_run_id: Current pipeline run identifier
            
        Returns:
            dict with routing log entry
        """
        # Build incident description
        description = self._build_incident_description(m)

        # Create ServiceNow ticket
        ticket = self.service_now.create_incident(
            short_description=f"[COMPLIANCE] {m.map_id}: {m.department} - Risk Score {m.risk_score}",
            description=description,
            assignment_group=m.department,
            priority=self.PRIORITY_MAP.get(m.priority, 3),
            category="Regulatory Compliance",
        )

        ticket_id = ticket["number"]

        # Audit log
        self.audit_log.log(
            pipeline_run_id=pipeline_run_id,
            agent="ORA",
            action="MAP_ROUTED",
            map_id=m.map_id,
            department=m.department,
            ticket_id=ticket_id,
            details={
                "priority": m.priority,
                "risk_score": m.risk_score,
                "deadline": m.deadline,
                "owner_role": m.owner_role,
                "requires_hitl": m.requires_hitl,
                "service_now_url": ticket.get("url", ""),
            },
        )

        return {
            "map_id": m.map_id,
            "department": m.department,
            "ticket_id": ticket_id,
            "action": "MAP_ROUTED",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "DISPATCHED",
            "priority": m.priority,
            "risk_score": m.risk_score,
            "service_now_url": ticket.get("url", ""),
        }

    def _build_incident_description(self, m: MeasurableActionPoint) -> str:
        """Build a detailed ServiceNow incident description."""
        instructions = "\n".join(f"  {i+1}. {step}" for i, step in enumerate(m.instructions))
        evidence = "\n".join(f"  - {e}" for e in m.evidence_requirements)

        return f"""REGULATORY COMPLIANCE ACTION ITEM
=====================================
MAP ID: {m.map_id}
Source Circular: {m.circular_id}
Priority: {m.priority} | Risk Score: {m.risk_score}/10.0
Deadline: {m.deadline}

ASSIGNED TO:
  Department: {m.department}
  Owner Role: {m.owner_role}

ACTION INSTRUCTIONS:
{instructions}

EVIDENCE REQUIREMENTS (must be provided for validation):
{evidence}

HITL REVIEW: {"REQUIRED - CCO approval needed before execution" if m.requires_hitl else "Not required"}

Generated by Anupalan AI - Autonomous Compliance Platform
"""
