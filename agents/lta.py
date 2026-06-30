"""
Agent 2: Legal Translation Agent (LTA) via GraphRAG
=====================================================
Maps circular text to internal bank policies using a Knowledge Graph.
Performs Regulatory Delta Analysis with faithfulness-scored LLM output.
"""

import json
import logging
from typing import Optional

from core.state import AnupalanState, PolicyDelta
from services.llm_service import LLMService
from mocks.enterprise_systems import MockNeo4jGraph

logger = logging.getLogger(__name__)


class LegalTranslationAgent:
    """
    Agent 2 - Traverses the Neo4j Knowledge Graph to find intersecting policies,
    then uses the local LLM to generate a Regulatory Delta Analysis (PolicyDelta).
    """

    def __init__(self, llm_service: Optional[LLMService] = None):
        self.llm_service = llm_service or LLMService()
        self.graph = MockNeo4jGraph()

    def run(self, state: AnupalanState) -> dict:
        """
        Execute the GraphRAG translation pipeline.
        
        1. Query the Knowledge Graph for policies affected by the circular
        2. Build a Context Bundle from graph traversal results + circular text
        3. Pass to LLM for Regulatory Delta Analysis
        4. Validate output against PolicyDelta schema
        
        Args:
            state: LangGraph state with regulatory_event populated
            
        Returns:
            dict with policy_delta field updated
        """
        logger.info("[LTA] Starting Legal Translation via GraphRAG...")

        event = state.get("regulatory_event")
        if event is None:
            logger.warning("[LTA] No regulatory_event in state. Using fallback delta.")
            return {
                "policy_delta": self._fallback_delta({"policies": [], "departments": []}),
                "current_agent": "LTA",
            }

        # Step 1: Traverse Knowledge Graph
        graph_results = self._traverse_graph(event.circular_id, event.raw_text)
        logger.info(
            "[LTA] Graph traversal found %d affected policies across %d departments",
            len(graph_results.get("policies", [])),
            len(graph_results.get("departments", [])),
        )

        # Step 2: Build Context Bundle
        context_bundle = self._build_context_bundle(event.raw_text, graph_results)

        # Step 3: LLM Analysis
        prompt = self._build_analysis_prompt(event)

        try:
            policy_delta = self.llm_service.generate_structured(
                prompt=prompt,
                context=context_bundle,
                output_schema=PolicyDelta,
                task_description="Regulatory Delta Analysis",
            )
            logger.info(
                "[LTA] Delta analysis complete. Risk: %s, Faithfulness: %.3f, "
                "New requirements: %d, Superseded: %d",
                policy_delta.risk_assessment,
                policy_delta.faithfulness_score,
                len(policy_delta.new_requirements),
                len(policy_delta.superseded_rules),
            )
            # Quality gate: if LLM output is practically empty, use fallback
            if not policy_delta.new_requirements and not policy_delta.intersecting_policies:
                logger.warning(
                    "[LTA] LLM delta is empty (0 requirements, 0 policies). Using fallback."
                )
                policy_delta = self._fallback_delta(graph_results)
        except ValueError as e:
            logger.error("[LTA] LLM analysis failed: %s", e)
            # Return a default PolicyDelta on failure
            policy_delta = self._fallback_delta(graph_results)

        return {
            "policy_delta": policy_delta,
            "current_agent": "LTA",
        }

    def _traverse_graph(self, circular_id: str, raw_text: str) -> dict:
        """
        Traverse the Knowledge Graph to find affected policies.
        Simulates Cypher: MATCH (c)-[r]->(p:Policy)-[o:OWNED_BY]->(d:Department)
        """
        # Try direct circular_id lookup
        result = self.graph.traverse_circular_impact(circular_id)

        # If no direct match, do text-based matching
        if not result.get("policies"):
            result = self._text_based_graph_search(raw_text)

        return result

    def _text_based_graph_search(self, raw_text: str) -> dict:
        """Search graph based on keywords in circular text."""
        text_lower = raw_text.lower()
        affected_policies = []
        departments = set()

        # Keyword-based matching to relevant policies
        keyword_policy_map = {
            "authentication": "POL-IT-SEC-3.2",
            "mfa": "POL-IT-SEC-3.2",
            "access control": "POL-IT-SEC-3.2",
            "money laundering": "POL-AML-5.0",
            "transaction monitoring": "POL-AML-5.0",
            "aml": "POL-AML-5.0",
            "data classification": "POL-DP-2.1",
            "data privacy": "POL-DP-2.1",
            "training": "POL-HR-TRN-1.0",
            "awareness": "POL-HR-TRN-1.0",
            "operational risk": "POL-RISK-OPS-4.0",
            "csoc": "POL-RISK-OPS-4.0",
            "security operations": "POL-RISK-OPS-4.0",
        }

        matched_policy_ids = set()
        for keyword, policy_id in keyword_policy_map.items():
            if keyword in text_lower:
                matched_policy_ids.add(policy_id)

        for policy_id in matched_policy_ids:
            # Simulate graph node lookup
            policy_info = {
                "policy_id": policy_id,
                "type": "Policy",
                "title": self._get_policy_title(policy_id),
                "relationship": "AMENDS",
                "detail": "Matched via keyword analysis",
            }
            affected_policies.append(policy_info)

            # Map to department
            dept = self._get_policy_department(policy_id)
            if dept:
                departments.add(dept)

        return {
            "policies": affected_policies,
            "departments": list(departments),
            "relationships": [],
        }

    def _get_policy_title(self, policy_id: str) -> str:
        """Get human-readable policy title."""
        titles = {
            "POL-IT-SEC-3.2": "IT Security Policy v3.2 - Access Control & Incident Response",
            "POL-AML-5.0": "KYC/AML Master Policy v5.0 - Transaction Monitoring",
            "POL-DP-2.1": "Data Privacy Policy v2.1 - Data Classification",
            "POL-HR-TRN-1.0": "Employee Training & Development Policy",
            "POL-RISK-OPS-4.0": "Operational Risk Framework v4.0",
        }
        return titles.get(policy_id, policy_id)

    def _get_policy_department(self, policy_id: str) -> Optional[str]:
        """Get owning department for a policy."""
        dept_map = {
            "POL-IT-SEC-3.2": "IT Security",
            "POL-AML-5.0": "Risk Management",
            "POL-DP-2.1": "IT Security",
            "POL-HR-TRN-1.0": "HR",
            "POL-RISK-OPS-4.0": "Risk Management",
        }
        return dept_map.get(policy_id)

    def _build_context_bundle(self, raw_text: str, graph_results: dict) -> str:
        """
        Build the Context Bundle for the LLM.
        Combines circular text with GraphRAG traversal results.
        """
        policies_text = "\n".join(
            f"- [{p.get('policy_id', 'N/A')}] {p.get('title', 'Unknown Policy')} "
            f"(Relationship: {p.get('relationship', 'N/A')}, Detail: {p.get('detail', 'N/A')})"
            for p in graph_results.get("policies", [])
        )

        departments_text = ", ".join(graph_results.get("departments", []))

        return f"""## CIRCULAR TEXT:
{raw_text[:3000]}

## AFFECTED INTERNAL POLICIES (from Knowledge Graph):
{policies_text or "No directly matching policies found."}

## AFFECTED DEPARTMENTS:
{departments_text or "To be determined based on analysis."}

## GRAPH RELATIONSHIPS:
{json.dumps(graph_results.get("relationships", []), indent=2)}
"""

    def _build_analysis_prompt(self, event) -> str:
        """Build the analysis prompt for the LLM."""
        return f"""Perform a Regulatory Delta Analysis for the following circular from {event.source}.

Circular ID: {event.circular_id}
Document Type: {event.doc_type}

Analyze the circular text against the provided Context Bundle and identify:
1. Which internal bank policies are affected (intersecting_policies)
2. Which existing rules are superseded or repealed (superseded_rules)
3. What new compliance requirements are introduced (new_requirements)
4. What existing requirements are amended (amended_requirements)
5. Overall risk assessment: LOW, MEDIUM, HIGH, or CRITICAL
6. A concise analysis summary

Be specific and cite section numbers where possible. Each requirement should be a clear, 
actionable statement that can be converted into a Measurable Action Point.

Return the output as a JSON object conforming to the PolicyDelta schema."""

    def _fallback_delta(self, graph_results: dict) -> PolicyDelta:
        """Generate a fallback PolicyDelta when LLM is unavailable."""
        policies = [
            p.get("title", p.get("policy_id", "Unknown"))
            for p in graph_results.get("policies", [])
        ]
        return PolicyDelta(
            intersecting_policies=policies or [
                "IT Security Policy v3.2",
                "KYC/AML Master Policy v5.0",
                "Data Privacy Policy v2.1",
            ],
            superseded_rules=["Previous cybersecurity requirements (pre-2025)"],
            new_requirements=[
                "Implement MFA for all digital banking channels",
                "Enhance transaction monitoring thresholds",
                "Establish CSOC with 24/7 monitoring",
                "Update incident response procedures",
            ],
            risk_assessment="HIGH",
            faithfulness_score=0.0,
            analysis_summary="Fallback analysis (LLM unavailable). Manual review recommended.",
        )
