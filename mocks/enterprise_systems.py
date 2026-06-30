"""
Mock Enterprise Systems for Autonomous Validation
==================================================
Simulates SIEM, DMS, LMS, and Filing Portal for evidence collection.
Used by Agent 5 (Autonomous Validation Agent).
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class MockSIEM:
    """
    Simulates SIEM/CMDB queries for IT configuration changes.
    Validates evidence like firewall rule changes, MFA deployment, etc.
    """

    def __init__(self):
        # Pre-seeded evidence records
        self._records = {
            "MFA_DEPLOYMENT": {
                "event_type": "CONFIG_CHANGE",
                "system": "IAM Portal",
                "description": "MFA enforcement enabled for all digital banking channels",
                "changed_by": "admin@cboi.internal",
                "timestamp": (datetime.utcnow() - timedelta(days=2)).isoformat(),
                "status": "COMPLETED",
                "config_hash": "sha256:abc123def456",
            },
            "FIREWALL_UPDATE": {
                "event_type": "CONFIG_CHANGE",
                "system": "Palo Alto Firewall Cluster",
                "description": "Updated firewall rules for CSOC network segment",
                "changed_by": "netops@cboi.internal",
                "timestamp": (datetime.utcnow() - timedelta(days=1)).isoformat(),
                "status": "COMPLETED",
                "config_hash": "sha256:789xyz012",
            },
            "SIEM_DEPLOYMENT": {
                "event_type": "DEPLOYMENT",
                "system": "Splunk Enterprise SIEM",
                "description": "SIEM deployed with 24/7 monitoring dashboards active",
                "changed_by": "soc-team@cboi.internal",
                "timestamp": (datetime.utcnow() - timedelta(hours=12)).isoformat(),
                "status": "COMPLETED",
                "config_hash": "sha256:siem456def",
            },
            "TX_MONITORING_UPDATE": {
                "event_type": "CONFIG_CHANGE",
                "system": "AML Transaction Monitoring Engine",
                "description": "Threshold updated to ₹2,00,000 for real-time flagging",
                "changed_by": "aml-admin@cboi.internal",
                "timestamp": (datetime.utcnow() - timedelta(days=3)).isoformat(),
                "status": "COMPLETED",
                "config_hash": "sha256:aml789ghi",
            },
        }

    def query_config_change(self, change_type: str) -> Optional[dict]:
        """Query SIEM for a specific configuration change."""
        key = change_type.upper().replace(" ", "_")
        record = self._records.get(key)
        if record:
            logger.info("SIEM: Found evidence for %s", change_type)
            return {"source": "SIEM/CMDB", "found": True, **record}
        logger.info("SIEM: No evidence found for %s", change_type)
        return {"source": "SIEM/CMDB", "found": False, "change_type": change_type}

    def query_system_status(self, system_name: str) -> dict:
        """Query CMDB for system operational status."""
        return {
            "source": "CMDB",
            "system": system_name,
            "status": "OPERATIONAL",
            "last_checked": datetime.utcnow().isoformat(),
        }


class MockDMS:
    """
    Simulates Document Management System for policy update verification.
    """

    def __init__(self):
        self._documents = {
            "IT_SECURITY_POLICY_V3.3": {
                "doc_id": "DOC-2025-0451",
                "title": "IT Security Policy v3.3 (Updated for MFA Requirements)",
                "version": "3.3",
                "uploaded_by": "ciso-office@cboi.internal",
                "uploaded_at": (datetime.utcnow() - timedelta(days=1)).isoformat(),
                "status": "APPROVED",
                "approver": "Chief Information Security Officer",
            },
            "AML_POLICY_V5.1": {
                "doc_id": "DOC-2025-0452",
                "title": "KYC/AML Master Policy v5.1 (Updated Transaction Thresholds)",
                "version": "5.1",
                "uploaded_by": "compliance@cboi.internal",
                "uploaded_at": (datetime.utcnow() - timedelta(days=2)).isoformat(),
                "status": "APPROVED",
                "approver": "Chief Compliance Officer",
            },
            "INCIDENT_RESPONSE_PLAYBOOK_V2.0": {
                "doc_id": "DOC-2025-0453",
                "title": "Incident Response Playbook v2.0 (6-hour RBI Notification)",
                "version": "2.0",
                "uploaded_by": "ir-team@cboi.internal",
                "uploaded_at": (datetime.utcnow() - timedelta(hours=8)).isoformat(),
                "status": "APPROVED",
                "approver": "Deputy CCO",
            },
            "DATA_PRIVACY_POLICY_V2.2": {
                "doc_id": "DOC-2025-0454",
                "title": "Data Privacy Policy v2.2 (4-tier Classification)",
                "version": "2.2",
                "uploaded_by": "dpo@cboi.internal",
                "uploaded_at": (datetime.utcnow() - timedelta(hours=4)).isoformat(),
                "status": "APPROVED",
                "approver": "Data Protection Officer",
            },
        }

    def query_policy_update(self, policy_name: str) -> Optional[dict]:
        """Check if a policy document has been updated."""
        key = policy_name.upper().replace(" ", "_").replace("-", "_")
        # Try partial match
        for doc_key, doc in self._documents.items():
            if key in doc_key or any(
                word.lower() in doc["title"].lower()
                for word in policy_name.split()
                if len(word) > 3
            ):
                logger.info("DMS: Found policy update for %s", policy_name)
                return {"source": "DMS", "found": True, **doc}

        logger.info("DMS: No update found for policy %s", policy_name)
        return {"source": "DMS", "found": False, "policy_name": policy_name}

    def list_recent_documents(self, days: int = 7) -> list[dict]:
        """List documents uploaded in the last N days."""
        return list(self._documents.values())


class MockLMS:
    """
    Simulates Learning Management System for training completion verification.
    """

    def __init__(self):
        self._training_records = {
            "CYBER_AWARENESS_Q1": {
                "course_id": "TRN-2025-001",
                "title": "Cybersecurity Awareness Training - Q1 2025",
                "total_enrolled": 85234,
                "total_completed": 82156,
                "completion_rate": 96.4,
                "deadline": "2025-03-31",
                "completed_at": (datetime.utcnow() - timedelta(days=5)).isoformat(),
                "status": "COMPLETED",
            },
            "AML_REFRESHER": {
                "course_id": "TRN-2025-002",
                "title": "AML Transaction Monitoring - Updated Thresholds Training",
                "total_enrolled": 12450,
                "total_completed": 11890,
                "completion_rate": 95.5,
                "deadline": "2025-07-15",
                "completed_at": (datetime.utcnow() - timedelta(days=1)).isoformat(),
                "status": "COMPLETED",
            },
            "CSOC_OPERATIONS": {
                "course_id": "TRN-2025-003",
                "title": "CSOC Operations & Incident Handling Procedures",
                "total_enrolled": 48,
                "total_completed": 48,
                "completion_rate": 100.0,
                "deadline": "2025-08-01",
                "completed_at": (datetime.utcnow() - timedelta(hours=6)).isoformat(),
                "status": "COMPLETED",
            },
        }

    def query_training_completion(self, course_name: str) -> Optional[dict]:
        """Check if a specific training has been completed."""
        key = course_name.upper().replace(" ", "_").replace("-", "_")
        for rec_key, record in self._training_records.items():
            if key in rec_key or any(
                word.lower() in record["title"].lower()
                for word in course_name.split()
                if len(word) > 3
            ):
                logger.info("LMS: Found training record for %s", course_name)
                return {"source": "LMS", "found": True, **record}

        logger.info("LMS: No training record found for %s", course_name)
        return {"source": "LMS", "found": False, "course_name": course_name}

    def get_completion_summary(self) -> dict:
        """Get overall training completion summary."""
        return {
            "source": "LMS",
            "total_courses": len(self._training_records),
            "records": list(self._training_records.values()),
        }


class MockFilingPortal:
    """
    Simulates regulatory filing portal for submission verification.
    """

    def __init__(self):
        self._filings = {
            "RBI_CYBER_REPORT_Q1": {
                "filing_id": "FIL-2025-RBI-001",
                "regulator": "RBI",
                "title": "Quarterly Cybersecurity Compliance Report - Q1 2025",
                "submitted_by": "compliance@cboi.internal",
                "submitted_at": (datetime.utcnow() - timedelta(days=7)).isoformat(),
                "status": "ACKNOWLEDGED",
                "acknowledgement_number": "RBI/CYB/2025/Q1/ACK-4521",
            },
            "FIU_SUSPECT_TX_REPORT": {
                "filing_id": "FIL-2025-FIU-001",
                "regulator": "FIU-IND",
                "title": "Suspicious Transaction Report - Monthly",
                "submitted_by": "aml-team@cboi.internal",
                "submitted_at": (datetime.utcnow() - timedelta(days=3)).isoformat(),
                "status": "ACKNOWLEDGED",
                "acknowledgement_number": "FIU/STR/2025/06/ACK-8834",
            },
        }

    def query_filing_status(self, filing_type: str) -> Optional[dict]:
        """Check if a regulatory filing has been submitted."""
        key = filing_type.upper().replace(" ", "_").replace("-", "_")
        for fil_key, filing in self._filings.items():
            if key in fil_key or any(
                word.lower() in filing["title"].lower()
                for word in filing_type.split()
                if len(word) > 3
            ):
                logger.info("FilingPortal: Found filing for %s", filing_type)
                return {"source": "Filing Portal", "found": True, **filing}

        return {"source": "Filing Portal", "found": False, "filing_type": filing_type}


class MockNeo4jGraph:
    """
    Simulates Neo4j Knowledge Graph for GraphRAG queries.
    Stores circulars, policies, departments, and their relationships.
    """

    def __init__(self):
        self._nodes = {
            "circulars": {
                "RBI/CYBSEC/2025/001": {
                    "type": "Circular",
                    "title": "Cyber Security Framework for Banks - Enhanced Requirements",
                    "source": "RBI",
                    "date": "2025-06-01",
                    "sections": ["MFA Requirements", "Transaction Monitoring", "CSOC Setup", "Incident Reporting"],
                },
            },
            "policies": {
                "POL-IT-SEC-3.2": {
                    "type": "Policy",
                    "title": "IT Security Policy v3.2",
                    "department": "IT Security",
                    "sections": {"4.1": "Access Control", "4.3": "Encryption Standards", "5.0": "Incident Response"},
                },
                "POL-AML-5.0": {
                    "type": "Policy",
                    "title": "KYC/AML Master Policy v5.0",
                    "department": "Risk Management",
                    "sections": {"2.0": "Customer Due Diligence", "3.1": "Transaction Monitoring"},
                },
                "POL-DP-2.1": {
                    "type": "Policy",
                    "title": "Data Privacy Policy v2.1",
                    "department": "IT Security",
                    "sections": {"3.0": "Data Classification", "4.0": "Data Retention"},
                },
                "POL-HR-TRN-1.0": {
                    "type": "Policy",
                    "title": "Employee Training & Development Policy",
                    "department": "HR",
                    "sections": {"2.0": "Mandatory Training", "3.0": "Cybersecurity Awareness"},
                },
                "POL-RISK-OPS-4.0": {
                    "type": "Policy",
                    "title": "Operational Risk Framework v4.0",
                    "department": "Risk Management",
                    "sections": {"1.0": "Risk Assessment", "2.0": "Control Framework"},
                },
            },
            "departments": {
                "IT Security": {"head": "CISO", "staff_count": 120},
                "Risk Management": {"head": "CRO", "staff_count": 85},
                "HR": {"head": "CHRO", "staff_count": 200},
                "Retail Credit": {"head": "GM Retail", "staff_count": 450},
                "Treasury": {"head": "GM Treasury", "staff_count": 60},
                "Compliance": {"head": "CCO", "staff_count": 95},
                "Operations": {"head": "COO", "staff_count": 300},
            },
        }

        self._relationships = [
            {"from": "RBI/CYBSEC/2025/001", "to": "POL-IT-SEC-3.2", "type": "AMENDS", "detail": "Sections 4.1, 5.0"},
            {"from": "RBI/CYBSEC/2025/001", "to": "POL-AML-5.0", "type": "AMENDS", "detail": "Section 3.1 thresholds"},
            {"from": "RBI/CYBSEC/2025/001", "to": "POL-DP-2.1", "type": "AMENDS", "detail": "Section 3.0 classification"},
            {"from": "RBI/CYBSEC/2025/001", "to": "POL-HR-TRN-1.0", "type": "IMPLEMENTS", "detail": "Mandatory cyber training"},
            {"from": "RBI/CYBSEC/2025/001", "to": "POL-RISK-OPS-4.0", "type": "IMPLEMENTS", "detail": "CSOC operational risk"},
            {"from": "POL-IT-SEC-3.2", "to": "IT Security", "type": "OWNED_BY", "detail": ""},
            {"from": "POL-AML-5.0", "to": "Risk Management", "type": "OWNED_BY", "detail": ""},
            {"from": "POL-DP-2.1", "to": "IT Security", "type": "OWNED_BY", "detail": ""},
            {"from": "POL-HR-TRN-1.0", "to": "HR", "type": "OWNED_BY", "detail": ""},
            {"from": "POL-RISK-OPS-4.0", "to": "Risk Management", "type": "OWNED_BY", "detail": ""},
        ]

    def traverse_circular_impact(self, circular_id: str) -> dict:
        """
        Simulate Cypher query: MATCH (c:Circular {id: $cid})-[r]->(p:Policy)-[o:OWNED_BY]->(d:Department)
        Returns all affected policies and departments.
        """
        if circular_id not in self._nodes["circulars"]:
            return {"policies": [], "departments": [], "relationships": []}

        affected_policies = []
        affected_departments = set()
        relevant_relationships = []

        for rel in self._relationships:
            if rel["from"] == circular_id and rel["type"] in ("AMENDS", "IMPLEMENTS", "SUPERSEDES"):
                policy_id = rel["to"]
                if policy_id in self._nodes["policies"]:
                    policy = self._nodes["policies"][policy_id]
                    affected_policies.append({
                        "policy_id": policy_id,
                        **policy,
                        "relationship": rel["type"],
                        "detail": rel["detail"],
                    })
                    relevant_relationships.append(rel)

                    # Find owning department
                    for dept_rel in self._relationships:
                        if dept_rel["from"] == policy_id and dept_rel["type"] == "OWNED_BY":
                            dept = dept_rel["to"]
                            affected_departments.add(dept)

        return {
            "circular": self._nodes["circulars"][circular_id],
            "policies": affected_policies,
            "departments": list(affected_departments),
            "relationships": relevant_relationships,
        }

    def get_superseded_rules(self, circular_id: str) -> list[str]:
        """Find rules superseded by this circular."""
        superseded = []
        for rel in self._relationships:
            if rel["from"] == circular_id and rel["type"] == "SUPERSEDES":
                superseded.append(rel["to"])
        return superseded

    def get_department_info(self, department: str) -> Optional[dict]:
        """Get department metadata."""
        return self._nodes["departments"].get(department)
