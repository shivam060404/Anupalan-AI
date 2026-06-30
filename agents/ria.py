"""
Agent 1: Regulatory Ingestion Agent (RIA)
============================================
Fetches, parses, and deduplicates regulatory PDFs from RBI/SEBI/FIU-IND/IRDAI.
Emits a structured RegulatoryEvent into the LangGraph state.
"""

import hashlib
import logging
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional

from core.state import RegulatoryEvent, AnupalanState

logger = logging.getLogger(__name__)

CIRCULARS_DIR = Path(__file__).parent.parent / "data" / "circulars"


class RegulatoryIngestionAgent:
    """
    Agent 1 - Monitors regulatory portals and ingests circulars.
    
    In production: Uses Playwright to scrape RBI/SEBI portals on 4-hour schedule.
    In prototype: Reads from local data/circulars/ directory.
    """

    def __init__(self):
        CIRCULARS_DIR.mkdir(parents=True, exist_ok=True)
        # Track processed hashes for deduplication (instance-level, reset per run)
        self._processed_hashes: set[str] = set()

    def reset(self):
        """Reset deduplication state for a new pipeline run."""
        self._processed_hashes.clear()

    def run(self, state: AnupalanState) -> dict:
        """
        Execute the ingestion pipeline.
        
        Reads PDFs from the circulars directory, extracts text,
        computes SHA-256 hash, classifies the document, and emits
        a RegulatoryEvent to the LangGraph state.
        
        Args:
            state: Current LangGraph state
            
        Returns:
            dict with regulatory_event and updated state fields
        """
        logger.info("[RIA] Starting regulatory ingestion scan...")

        # Find unprocessed circulars
        circular_file = self._find_next_circular()
        if circular_file is None:
            logger.info("[RIA] No new circulars found. Using sample circular.")
            circular_file = self._create_sample_circular()

        # Extract text from PDF (or read mock text)
        raw_text = self._extract_text(circular_file)
        if not raw_text:
            return {
                "errors": state.get("errors", []) + ["RIA: Failed to extract text from circular"],
                "current_agent": "RIA",
                "final_status": "ERROR_INGESTION",
            }

        # Compute SHA-256 for deduplication
        doc_hash = hashlib.sha256(raw_text.encode()).hexdigest()
        if doc_hash in self._processed_hashes:
            logger.info("[RIA] Duplicate circular detected (hash: %s). Skipping.", doc_hash[:16])
            return {
                "errors": state.get("errors", []) + ["RIA: Duplicate circular"],
                "current_agent": "RIA",
                "final_status": "DUPLICATE_SKIPPED",
            }

        self._processed_hashes.add(doc_hash)

        # Classify document
        source = self._classify_source(circular_file.name, raw_text)
        doc_type = self._classify_doc_type(raw_text)

        # Create RegulatoryEvent
        circular_id = f"CIRC-{datetime.utcnow().strftime('%Y')}-{uuid.uuid4().hex[:6].upper()}"
        event = RegulatoryEvent(
            circular_id=circular_id,
            source=source,
            doc_type=doc_type,
            title=self._extract_title(raw_text),
            raw_text=raw_text,
            hash_sha256=doc_hash,
        )

        logger.info(
            "[RIA] Ingested circular %s from %s (type: %s, hash: %s...)",
            circular_id, source, doc_type, doc_hash[:16],
        )

        return {
            "regulatory_event": event,
            "current_agent": "RIA",
            "pipeline_run_id": state.get("pipeline_run_id", uuid.uuid4().hex[:12]),
            "started_at": state.get("started_at", datetime.utcnow().isoformat() + "Z"),
            "errors": [],
        }

    def _find_next_circular(self) -> Optional[Path]:
        """Find the next unprocessed circular in the data directory."""
        for f in sorted(CIRCULARS_DIR.glob("*")):
            if f.suffix.lower() in (".pdf", ".txt") and f.stat().st_size > 0:
                return f
        return None

    def _create_sample_circular(self) -> Path:
        """Create a sample RBI circular for demo purposes."""
        sample_path = CIRCULARS_DIR / "RBI_CyberSecurity_2025.txt"
        if not sample_path.exists():
            sample_text = self._get_sample_rbi_circular()
            sample_path.write_text(sample_text)
        return sample_path

    def _extract_text(self, file_path: Path) -> str:
        """Extract text from PDF or plain text file."""
        if file_path.suffix.lower() == ".pdf":
            return self._extract_pdf_text(file_path)
        elif file_path.suffix.lower() == ".txt":
            return file_path.read_text(encoding="utf-8")
        return ""

    def _extract_pdf_text(self, pdf_path: Path) -> str:
        """Extract text from PDF using PyMuPDF."""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(pdf_path))
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text
        except ImportError:
            logger.warning("[RIA] PyMuPDF not available. Cannot parse PDF.")
            return ""
        except Exception as e:
            logger.error("[RIA] PDF extraction failed: %s", e)
            return ""

    def _classify_source(self, filename: str, text: str) -> str:
        """Classify the regulatory source from filename or content."""
        text_lower = text.lower()
        name_lower = filename.lower()
        if "rbi" in name_lower or "reserve bank" in text_lower:
            return "RBI"
        elif "sebi" in name_lower or "securities" in text_lower:
            return "SEBI"
        elif "fiu" in name_lower or "financial intelligence" in text_lower:
            return "FIU-IND"
        elif "irdai" in name_lower or "insurance" in text_lower:
            return "IRDAI"
        return "RBI"  # Default

    def _classify_doc_type(self, text: str) -> str:
        """Classify document type from content."""
        text_lower = text.lower()
        if "master circular" in text_lower:
            return "Master Circular"
        elif "enforcement" in text_lower or "penalty" in text_lower:
            return "Enforcement Order"
        elif "notification" in text_lower:
            return "Notification"
        return "Circular"

    def _extract_title(self, text: str) -> str:
        """Extract document title from first few lines."""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines[:5]:
            if len(line) > 20 and len(line) < 200:
                return line
        return "Untitled Regulatory Circular"

    def _get_sample_rbi_circular(self) -> str:
        """Generate a realistic sample RBI circular for demonstration."""
        return """RESERVE BANK OF INDIA
Department of Supervision
Central Office, Mumbai - 400001

Ref: RBI/2025-26/DS/CyberSec/Master Direction No. 15/2025
Date: June 1, 2025

CIRCULAR

To: All Scheduled Commercial Banks (excluding Regional Rural Banks)
     All Primary (Urban) Co-operative Banks
     All Non-Banking Financial Companies

Subject: Cyber Security Framework for Banks - Enhanced Requirements for Digital Banking Security

Madam/Dear Sir,

1. INTRODUCTION

1.1 In exercise of the powers conferred under Section 35A of the Banking Regulation Act, 1949, 
and in supersession of the circular RBI/2023-24/DS/CyberSec/45 dated March 15, 2024, the 
Reserve Bank of India hereby issues this Master Direction on Cyber Security Framework for Banks.

1.2 This circular is issued in the context of the increasing frequency and sophistication of 
cyber attacks targeting the Indian banking sector, including but not limited to ransomware attacks, 
supply chain compromises, and advanced persistent threats (APTs).

2. MULTI-FACTOR AUTHENTICATION (MFA) REQUIREMENTS

2.1 All banks shall implement Multi-Factor Authentication (MFA) for ALL customer-facing digital 
banking channels, including but not limited to:
   (a) Internet Banking (Retail and Corporate)
   (b) Mobile Banking Applications
   (c) UPI-based payment interfaces
   (d) API Banking channels

2.2 MFA shall support at least two of the following factors:
   (a) Knowledge factor (OTP, PIN, Password)
   (b) Possession factor (Hardware token, Mobile device)
   (c) Inherence factor (Biometric - Fingerprint, Face Recognition, Iris)

2.3 The MFA implementation shall be completed within 60 days from the date of this circular.
Banks shall submit a compliance report to the Chief Compliance Officer of the respective 
Regional Office of RBI within 30 days of completion.

2.4 Penalty for non-compliance: Banks failing to implement MFA within the stipulated timeline 
shall be liable for penalty under Section 47A of the Banking Regulation Act, which may extend 
to ₹5 Crore per instance of non-compliance.

3. TRANSACTION MONITORING ENHANCEMENTS

3.1 All banks shall enhance their Anti-Money Laundering (AML) transaction monitoring systems 
to implement real-time screening for the following thresholds:
   (a) Individual transactions exceeding ₹2,00,000 (reduced from ₹10,00,000)
   (b) Aggregate daily transactions by a single customer exceeding ₹5,00,000
   (c) Cross-border transactions exceeding ₹50,000

3.2 Suspicious Transaction Reports (STRs) arising from the enhanced monitoring shall be filed 
with FIU-IND within 7 days of identification, as per the Prevention of Money Laundering 
(Maintenance of Records) Rules, 2005.

3.3 Banks shall conduct refresher training for all transaction monitoring analysts within 
90 days of implementing the new thresholds. Training completion records shall be maintained 
and made available for RBI inspection.

4. CYBER SECURITY OPERATIONS CENTRE (CSOC)

4.1 All banks with more than 5,000 branches shall establish a dedicated Cyber Security 
Operations Centre (CSOC) with 24x7x365 monitoring capability.

4.2 The CSOC shall be staffed with a minimum of:
   (a) 1 CSOC Manager (Grade: AGM or above)
   (b) 8 Security Analysts (minimum 3 per shift across 3 shifts)
   (c) 2 Threat Intelligence Analysts
   (d) 1 Incident Response Coordinator

4.3 The CSOC shall deploy a Security Information and Event Management (SIEM) solution capable of:
   (a) Real-time log aggregation from all critical systems
   (b) Automated threat correlation and alerting
   (c) Integration with RBI's Cyber Crime Reporting Portal
   (d) Minimum 365 days of log retention with 90 days of hot storage

4.4 Banks shall operationalize the CSOC within 120 days from the date of this circular.

5. INCIDENT RESPONSE AND REPORTING

5.1 All banks shall update their Incident Response Playbook to include the following 
mandatory reporting timelines:
   (a) Notification to RBI (Department of Supervision) within 6 hours of detecting a 
       significant cybersecurity incident
   (b) Detailed incident report within 24 hours
   (c) Root cause analysis report within 7 business days
   (d) Remediation action plan within 15 business days

5.2 A "significant cybersecurity incident" is defined as any incident that:
   (a) Affects more than 10,000 customer accounts
   (b) Results in unauthorized access to customer financial data
   (c) Disrupts critical banking services for more than 2 hours
   (d) Involves financial loss exceeding ₹1 Crore

5.3 Banks shall conduct at least two tabletop exercises per year simulating a major 
cybersecurity breach, with participation from the CISO, CTO, CCO, and at least one 
Executive Director.

6. DATA CLASSIFICATION AND VENDOR RISK

6.1 Banks shall implement a 4-tier data classification framework:
   (a) Tier 1 - Public Data
   (b) Tier 2 - Internal Data
   (c) Tier 3 - Confidential Data
   (d) Tier 4 - Restricted/Secret Data (Customer PII, Authentication Credentials)

6.2 Vendor risk assessments shall be conducted on a semi-annual basis (previously annual) 
for all vendors with access to Tier 3 and Tier 4 data.

6.3 Banks shall maintain a Vendor Risk Register and submit it to RBI along with the 
Annual Compliance Certificate.

7. COMPLIANCE AND PENALTIES

7.1 Non-compliance with any provision of this Master Direction shall attract penalties 
under Section 47A of the Banking Regulation Act, 1949, which may extend to:
   (a) ₹1 Crore for procedural non-compliance
   (b) ₹3 Crore for systemic failures
   (c) ₹5 Crore per instance for willful non-compliance or concealment

7.2 The Chief Compliance Officer (CCO) of the bank shall be personally accountable for 
ensuring timely compliance with all provisions of this circular.

8. EFFECTIVE DATE

8.1 This Master Direction shall come into effect from the date of issue. Banks are advised 
to initiate immediate action for compliance and submit an Action Taken Report (ATR) within 
the timelines specified for each provision.

Yours faithfully,

(Anil K. Sharma)
Chief General Manager-in-Charge
Department of Supervision
Reserve Bank of India
"""
