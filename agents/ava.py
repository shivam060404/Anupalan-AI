"""
Agent 5: Autonomous Validation Agent (AVA)
=============================================
Verifies MAP completion without self-reporting by querying
SIEM, DMS, LMS, and Filing Portal for evidence.
Generates Compliance Evidence Packages with timestamped PDFs.
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.state import AnupalanState, MeasurableActionPoint, ComplianceEvidencePackage
from mocks.enterprise_systems import MockSIEM, MockDMS, MockLMS, MockFilingPortal
from mocks.service_now import MockServiceNowAPI
from services.audit_log import AuditLogService

logger = logging.getLogger(__name__)

EVIDENCE_DIR = Path(__file__).parent.parent / "data" / "evidence"


class AutonomousValidationAgent:
    """
    Agent 5 - Autonomously validates MAP completion.
    
    Queries mock enterprise systems for evidence:
    - SIEM/CMDB: IT configuration changes
    - DMS: Policy document updates
    - LMS: Training completion records
    - Filing Portal: Regulatory submission confirmations
    
    Generates a ComplianceEvidencePackage and evidence PDF for each MAP.
    """

    # Mapping of evidence requirements to mock system queries
    EVIDENCE_SOURCE_MAP = {
        "siem": "SIEM",
        "cmdb": "SIEM",
        "configuration": "SIEM",
        "firewall": "SIEM",
        "mfa": "SIEM",
        "dms": "DMS",
        "policy": "DMS",
        "document": "DMS",
        "playbook": "DMS",
        "lms": "LMS",
        "training": "LMS",
        "completion": "LMS",
        "filing": "FILING",
        "submission": "FILING",
        "report": "FILING",
    }

    def __init__(
        self,
        siem: Optional[MockSIEM] = None,
        dms: Optional[MockDMS] = None,
        lms: Optional[MockLMS] = None,
        filing_portal: Optional[MockFilingPortal] = None,
        service_now: Optional[MockServiceNowAPI] = None,
        audit_log: Optional[AuditLogService] = None,
    ):
        self.siem = siem or MockSIEM()
        self.dms = dms or MockDMS()
        self.lms = lms or MockLMS()
        self.filing_portal = filing_portal or MockFilingPortal()
        self.service_now = service_now or MockServiceNowAPI()
        self.audit_log = audit_log or AuditLogService()
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    def run(self, state: AnupalanState) -> dict:
        """
        Validate all dispatched MAPs by querying enterprise systems.
        
        For each MAP:
        1. Parse evidence_requirements
        2. Query appropriate mock systems
        3. Assess evidence completeness
        4. Generate ComplianceEvidencePackage
        5. Generate evidence PDF
        6. Close ServiceNow ticket if validated
        
        Args:
            state: LangGraph state with maps and routing_logs
            
        Returns:
            dict with validation_evidence list updated
        """
        logger.info("[AVA] Starting autonomous validation...")

        maps = state.get("maps", [])
        dispatched_maps = [m for m in maps if m.status == "DISPATCHED"]

        if not dispatched_maps:
            # For demo: simulate all MAPs as dispatched and completed
            dispatched_maps = [m for m in maps if m.status != "VALIDATED"]
            for m in dispatched_maps:
                m.status = "DISPATCHED"

        if not dispatched_maps:
            return {
                "errors": state.get("errors", []) + ["AVA: No dispatched MAPs to validate"],
                "current_agent": "AVA",
                "final_status": "ERROR_AVA_NO_MAPS",
            }

        validation_evidence = []
        pipeline_run_id = state.get("pipeline_run_id", "unknown")

        for m in dispatched_maps:
            evidence_package = self._validate_map(m, pipeline_run_id)
            validation_evidence.append(evidence_package)

            # Update MAP status
            if evidence_package.validation_status == "SUCCESS":
                m.status = "VALIDATED"
                self._close_ticket(m)
            else:
                m.status = "COMPLETED"  # Completed but not fully validated

            logger.info(
                "[AVA] MAP %s: %s (sources: %d)",
                m.map_id,
                evidence_package.validation_status,
                len(evidence_package.evidence_sources),
            )

        success_count = sum(1 for e in validation_evidence if e.validation_status == "SUCCESS")
        logger.info(
            "[AVA] Validation complete. %d/%d MAPs validated successfully.",
            success_count, len(dispatched_maps),
        )

        return {
            "maps": maps,
            "validation_evidence": validation_evidence,
            "current_agent": "AVA",
        }

    def _validate_map(
        self, m: MeasurableActionPoint, pipeline_run_id: str
    ) -> ComplianceEvidencePackage:
        """Validate a single MAP by querying enterprise systems."""
        evidence_sources = []
        evidence_details = []

        for requirement in m.evidence_requirements:
            result = self._query_evidence(requirement, m.department)
            evidence_details.append(result)

            if result.get("found", False):
                source = result.get("source", "Unknown")
                if source not in evidence_sources:
                    evidence_sources.append(source)

        # Determine validation status
        total_requirements = len(m.evidence_requirements)
        found_evidence = sum(1 for d in evidence_details if d.get("found", False))

        if found_evidence == total_requirements:
            status = "SUCCESS"
        elif found_evidence > 0:
            status = "PENDING"
        else:
            status = "FAILED"

        # Generate evidence PDF
        pdf_path = self._generate_evidence_pdf(m, evidence_details, status)

        # Audit log
        self.audit_log.log(
            pipeline_run_id=pipeline_run_id,
            agent="AVA",
            action="MAP_VALIDATED",
            map_id=m.map_id,
            department=m.department,
            details={
                "validation_status": status,
                "evidence_found": found_evidence,
                "evidence_required": total_requirements,
                "evidence_sources": evidence_sources,
                "pdf_path": pdf_path,
            },
            status=status,
        )

        return ComplianceEvidencePackage(
            map_id=m.map_id,
            validation_status=status,
            evidence_sources=evidence_sources,
            evidence_details=evidence_details,
            evidence_pdf_path=pdf_path,
        )

    def _query_evidence(self, requirement: str, department: str) -> dict:
        """
        Route evidence query to the appropriate mock system.
        """
        req_lower = requirement.lower()

        # Determine which system to query
        for keyword, system in self.EVIDENCE_SOURCE_MAP.items():
            if keyword in req_lower:
                if system == "SIEM":
                    return self.siem.query_config_change(requirement)
                elif system == "DMS":
                    return self.dms.query_policy_update(requirement)
                elif system == "LMS":
                    return self.lms.query_training_completion(requirement)
                elif system == "FILING":
                    return self.filing_portal.query_filing_status(requirement)

        # Default: try all systems
        results = []
        results.append(self.siem.query_config_change(requirement))
        results.append(self.dms.query_policy_update(requirement))
        results.append(self.lms.query_training_completion(requirement))

        for r in results:
            if r.get("found", False):
                return r

        return {
            "source": "Multi-System Search",
            "found": False,
            "requirement": requirement,
        }

    def _generate_evidence_pdf(
        self,
        m: MeasurableActionPoint,
        evidence_details: list[dict],
        status: str,
    ) -> str:
        """Generate a Compliance Evidence Package PDF."""
        pdf_filename = f"evidence_{m.map_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = EVIDENCE_DIR / pdf_filename

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib import colors

            doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
            styles = getSampleStyleSheet()
            elements = []

            # Title
            elements.append(Paragraph("ANUPALAN AI - COMPLIANCE EVIDENCE PACKAGE", styles["Title"]))
            elements.append(Spacer(1, 12))

            # MAP Details
            elements.append(Paragraph(f"<b>MAP ID:</b> {m.map_id}", styles["Normal"]))
            elements.append(Paragraph(f"<b>Department:</b> {m.department}", styles["Normal"]))
            elements.append(Paragraph(f"<b>Risk Score:</b> {m.risk_score}/10.0", styles["Normal"]))
            elements.append(Paragraph(f"<b>Deadline:</b> {m.deadline}", styles["Normal"]))
            elements.append(Paragraph(f"<b>Validation Status:</b> {status}", styles["Normal"]))
            elements.append(Paragraph(
                f"<b>Generated:</b> {datetime.utcnow().isoformat()} UTC", styles["Normal"]
            ))
            elements.append(Spacer(1, 20))

            # Evidence Table
            elements.append(Paragraph("EVIDENCE RECORDS", styles["Heading2"]))
            elements.append(Spacer(1, 8))

            table_data = [["Requirement", "Source", "Status", "Details"]]
            for detail in evidence_details:
                found = "FOUND" if detail.get("found", False) else "NOT FOUND"
                source = detail.get("source", "N/A")
                req = detail.get("requirement", detail.get("description", "N/A"))[:50]
                detail_text = detail.get("title", detail.get("status", "N/A"))[:40]
                table_data.append([req, source, found, detail_text])

            if len(table_data) > 1:
                table = Table(table_data)
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a365d")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
                ]))
                elements.append(table)

            elements.append(Spacer(1, 20))

            # Instructions
            elements.append(Paragraph("ACTION INSTRUCTIONS COMPLETED", styles["Heading2"]))
            for i, instruction in enumerate(m.instructions, 1):
                elements.append(Paragraph(f"{i}. {instruction}", styles["Normal"]))

            elements.append(Spacer(1, 20))

            # Footer
            elements.append(Paragraph(
                "This document was auto-generated by Anupalan AI Autonomous Validation Agent. "
                "It serves as evidence of compliance completion and is suitable for RBI inspection.",
                styles["Italic"],
            ))
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(
                f"Document ID: EV-{uuid.uuid4().hex[:12].upper()} | "
                f"Generated: {datetime.utcnow().isoformat()}",
                styles["Normal"],
            ))

            doc.build(elements)
            logger.info("[AVA] Generated evidence PDF: %s", pdf_path)
            return str(pdf_path)

        except ImportError:
            # Fallback: create a simple text file
            txt_path = pdf_path.with_suffix(".txt")
            content = f"""ANUPALAN AI - COMPLIANCE EVIDENCE PACKAGE
==========================================
MAP ID: {m.map_id}
Department: {m.department}
Risk Score: {m.risk_score}/10.0
Validation Status: {status}
Generated: {datetime.utcnow().isoformat()} UTC

EVIDENCE RECORDS:
"""
            for detail in evidence_details:
                found = "FOUND" if detail.get("found", False) else "NOT FOUND"
                content += f"  - [{found}] {detail.get('source', 'N/A')}: {detail.get('description', detail.get('requirement', 'N/A'))}\n"

            txt_path.write_text(content)
            return str(txt_path)

        except Exception as e:
            logger.error("[AVA] PDF generation failed: %s", e)
            return ""

    def _close_ticket(self, m: MeasurableActionPoint):
        """Close the ServiceNow ticket after successful validation."""
        try:
            # Find the ticket for this MAP from routing logs
            incidents = self.service_now.list_incidents()
            for inc in incidents:
                if m.map_id in inc.get("description", ""):
                    self.service_now.close_incident(
                        inc["number"],
                        resolution=f"Validated by Anupalan AI - All evidence requirements met",
                    )
                    logger.info("[AVA] Closed ticket %s for MAP %s", inc["number"], m.map_id)
                    return
        except Exception as e:
            logger.warning("[AVA] Could not close ticket for MAP %s: %s", m.map_id, e)
