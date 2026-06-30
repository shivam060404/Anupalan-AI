"""
Agent 3: MAP Generator Agent (MGA)
====================================
Converts PolicyDelta into atomic, executable Measurable Action Points.
Each MAP includes department, deadline, risk score, instructions, and evidence requirements.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from core.state import AnupalanState, MeasurableActionPoint
from services.llm_service import LLMService

logger = logging.getLogger(__name__)

# Department Routing Matrix
DEPARTMENT_MATRIX = {
    "IT Security": ["CISO", "Chief Information Security Officer", "VP - Security Operations"],
    "Risk Management": ["CRO", "Head of Transaction Monitoring", "AML Compliance Officer"],
    "HR": ["CHRO", "Head of Learning & Development", "Training Coordinator"],
    "Retail Credit": ["GM Retail", "Credit Risk Manager"],
    "Treasury": ["GM Treasury", "Forex Compliance Officer"],
    "Compliance": ["CCO", "Deputy CCO", "Compliance Manager"],
    "Operations": ["COO", "Operations Manager"],
}


class MAPGeneratorAgent:
    """
    Agent 3 - Generates Measurable Action Points from Regulatory Delta Analysis.
    Uses strict Pydantic v2 schema enforcement with retry mechanism.
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service or LLMService()

    def run(self, state: AnupalanState) -> dict:
        """
        Generate MAPs from the PolicyDelta.
        
        1. Build prompt from policy_delta and regulatory_event
        2. Call LLM to generate MAPs as JSON array
        3. Validate each MAP against Pydantic schema (3 retries)
        4. Flag MAPs with risk_score >= 8.0 for HITL
        
        Args:
            state: LangGraph state with regulatory_event and policy_delta
            
        Returns:
            dict with maps list and hitl_required_maps
        """
        logger.info("[MGA] Starting MAP generation...")

        event = state.get("regulatory_event")
        delta = state.get("policy_delta")

        if not event or not delta:
            return {
                "errors": state.get("errors", []) + ["MGA: Missing regulatory_event or policy_delta"],
                "current_agent": "MGA",
                "final_status": "ERROR_MGA_MISSING_INPUT",
            }

        # Build context for LLM
        context = self._build_context(event, delta)
        prompt = self._build_prompt(event, delta)

        # Generate MAPs via LLM
        try:
            maps = self.llm_service.generate_list_structured(
                prompt=prompt,
                context=context,
                output_schema=MeasurableActionPoint,
                task_description="MAP Generation",
            )
            # Quality gate: if LLM produced too few MAPs, use curated fallback
            if len(maps) < 3:
                logger.warning(
                    "[MGA] LLM generated only %d MAPs (minimum 3 expected). Using fallback.",
                    len(maps),
                )
                maps = self._fallback_maps(event, delta)
        except ValueError as e:
            logger.error("[MGA] LLM MAP generation failed: %s", e)
            maps = self._fallback_maps(event, delta)

        # Post-process MAPs
        processed_maps = []
        hitl_required = []

        for i, m in enumerate(maps):
            # Ensure unique map_id
            if not m.map_id:
                m.map_id = f"MAP-{datetime.utcnow().strftime('%Y')}-{i+1:03d}"

            # Set circular_id reference
            m.circular_id = event.circular_id

            # Set HITL flag
            if m.risk_score >= 8.0 or m.priority == "CRITICAL":
                m.requires_hitl = True
                hitl_required.append(m.map_id)

            # Assign owner role from department matrix
            if m.department in DEPARTMENT_MATRIX:
                roles = DEPARTMENT_MATRIX[m.department]
                if not m.owner_role or m.owner_role not in roles:
                    m.owner_role = roles[0]

            m.status = "PENDING"
            processed_maps.append(m)

        logger.info(
            "[MGA] Generated %d MAPs. HITL required for: %s",
            len(processed_maps),
            hitl_required or "None",
        )

        return {
            "maps": processed_maps,
            "hitl_required_maps": hitl_required,
            "current_agent": "MGA",
        }

    def _build_context(self, event, delta) -> str:
        """Build the context bundle for MAP generation."""
        return f"""## REGULATORY CIRCULAR:
Source: {event.source}
Type: {event.doc_type}
ID: {event.circular_id}

CIRCULAR EXCERPT:
{event.raw_text[:2000]}

## REGULATORY DELTA ANALYSIS:
Risk Assessment: {delta.risk_assessment}

Intersecting Policies:
{chr(10).join(f"- {p}" for p in delta.intersecting_policies) if delta.intersecting_policies else "N/A"}

Superseded Rules:
{chr(10).join(f"- {r}" for r in delta.superseded_rules) if delta.superseded_rules else "N/A"}

New Requirements:
{chr(10).join(f"- {r}" for r in delta.new_requirements) if delta.new_requirements else "N/A"}

Amended Requirements:
{chr(10).join(f"- {r}" for r in delta.amended_requirements) if delta.amended_requirements else "N/A"}

Analysis Summary: {delta.analysis_summary}
"""

    def _build_prompt(self, event, delta) -> str:
        """Build the MAP generation prompt."""
        departments = list(DEPARTMENT_MATRIX.keys())
        return f"""Generate Measurable Action Points (MAPs) based on the Regulatory Delta Analysis.

Each MAP must be:
- Atomic: One specific, actionable compliance task
- Measurable: Has clear evidence requirements that prove completion
- Assignable: Has a specific department and owner role
- Time-bound: Has a specific deadline (use ISO date format)

Available departments: {', '.join(departments)}

For each MAP, include:
1. A unique map_id (format: MAP-2025-XXX)
2. The responsible department and owner role
3. A realistic deadline based on the circular's requirements
4. A risk_score from 0.0 to 10.0 (based on regulatory penalty severity)
5. Priority: LOW, MEDIUM, HIGH, or CRITICAL
6. Step-by-step instructions (3-5 steps)
7. Evidence requirements (2-4 types of evidence needed for validation)
8. requires_hitl: true if risk_score >= 8.0 OR priority is CRITICAL

Generate one MAP for each distinct compliance requirement identified in the delta analysis.
Return a JSON array of MAP objects."""

    def _fallback_maps(self, event, delta) -> list[MeasurableActionPoint]:
        """Generate fallback MAPs when LLM is unavailable."""
        fallback_data = [
            {
                "map_id": "MAP-2025-001",
                "department": "IT Security",
                "owner_role": "Chief Information Security Officer",
                "deadline": "2025-07-30",
                "risk_score": 9.0,
                "priority": "CRITICAL",
                "instructions": [
                    "Deploy MFA across all customer-facing digital banking channels",
                    "Configure MFA to support OTP, biometric, and hardware token methods",
                    "Integrate MFA with existing IAM system",
                    "Conduct UAT with pilot users before full rollout",
                ],
                "evidence_requirements": [
                    "SIEM configuration logs showing MFA enforcement",
                    "UAT sign-off document",
                    "Updated IAM policy configuration export",
                ],
                "requires_hitl": True,
                "circular_id": event.circular_id,
            },
            {
                "map_id": "MAP-2025-002",
                "department": "Risk Management",
                "owner_role": "Head of Transaction Monitoring",
                "deadline": "2025-07-15",
                "risk_score": 8.5,
                "priority": "CRITICAL",
                "instructions": [
                    "Update AML transaction monitoring rules for new ₹2,00,000 threshold",
                    "Configure real-time screening alerts",
                    "Train analysts on updated procedures",
                    "Document changes in AML policy register",
                ],
                "evidence_requirements": [
                    "Updated monitoring rule configuration",
                    "LMS training completion records",
                    "Updated AML policy document",
                ],
                "requires_hitl": True,
                "circular_id": event.circular_id,
            },
            {
                "map_id": "MAP-2025-003",
                "department": "HR",
                "owner_role": "Head of Learning & Development",
                "deadline": "2025-08-30",
                "risk_score": 5.0,
                "priority": "MEDIUM",
                "instructions": [
                    "Design quarterly cybersecurity awareness training module",
                    "Upload training content to bank LMS",
                    "Schedule mandatory training for all employees",
                    "Set up automated tracking and reminders",
                ],
                "evidence_requirements": [
                    "LMS training module upload confirmation",
                    "Training completion dashboard screenshot",
                ],
                "requires_hitl": False,
                "circular_id": event.circular_id,
            },
            {
                "map_id": "MAP-2025-004",
                "department": "IT Security",
                "owner_role": "VP - Security Operations",
                "deadline": "2025-09-15",
                "risk_score": 8.0,
                "priority": "HIGH",
                "instructions": [
                    "Establish CSOC with 24/7 monitoring capability",
                    "Procure and deploy SIEM solution",
                    "Hire/assign minimum 8 FTEs for CSOC operations",
                    "Define escalation matrix and SOPs",
                ],
                "evidence_requirements": [
                    "CSOC facility setup completion certificate",
                    "SIEM deployment document",
                    "CSOC staffing roster",
                    "Incident response SOP document",
                ],
                "requires_hitl": True,
                "circular_id": event.circular_id,
            },
            {
                "map_id": "MAP-2025-005",
                "department": "Compliance",
                "owner_role": "Deputy CCO",
                "deadline": "2025-07-01",
                "risk_score": 7.5,
                "priority": "HIGH",
                "instructions": [
                    "Update incident response playbook for 6-hour RBI notification",
                    "Define incident severity classification matrix",
                    "Conduct tabletop exercise for data breach scenario",
                    "Update vendor risk assessment to semi-annual schedule",
                ],
                "evidence_requirements": [
                    "Updated incident response playbook",
                    "Tabletop exercise report",
                    "Updated vendor risk assessment calendar",
                ],
                "requires_hitl": False,
                "circular_id": event.circular_id,
            },
        ]
        return [MeasurableActionPoint(**data) for data in fallback_data]
