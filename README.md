# Anupalan AI

### Agentic Regulatory Intelligence & Autonomous Compliance Platform for Indian Banking

> *"From RBI circular to closed compliance ticket — autonomously, in under 4 hours."*

**Built for the SuRaksha Cyber Hackathon 2.0, hosted by Canara Bank**

---

## Table of Contents

- [The Problem](#the-problem)
- [The Solution](#the-solution)
- [How It Works](#how-it-works)
- [The Five-Agent Architecture](#the-five-agent-architecture)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Running the System](#running-the-system)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Demo Walkthrough](#demo-walkthrough)
- [License](#license)

---

## The Problem

India's banking sector faces a **compliance crisis**. Every year, banks receive **300–500 regulatory circulars** from bodies like the RBI, SEBI, FIU-IND, and IRDAI. For a large bank like Canara Bank — operating across **9,500+ branches** — turning these dense legal documents into real, actionable steps is painfully slow and error-prone.

Three major pain points define this crisis:

| Pain Point | Description |
|---|---|
| **Density** | A single RBI Master Circular can be 80–120 pages of legal language, simultaneously affecting IT Security, Retail Credit, Treasury, HR, and Grievance Redressal — all in one undifferentiated PDF. |
| **Latency** | The manual compliance cycle — reading, interpreting, drafting action items, getting legal sign-off, and routing to departments — takes **10 to 21 business days**, dangerously close to regulatory deadlines. |
| **Accountability Gaps** | Once action items are routed, there is no autonomous tracking. Completion is self-reported. During an RBI inspection, the bank cannot prove *when* or *how* each requirement was addressed. Penalties range from **₹1 Cr to ₹5 Cr** per enforcement action. |

---

## The Solution

**Anupalan AI** is a multi-agent, agentic regulatory intelligence platform that automates the entire compliance lifecycle:

1. **Monitors** regulatory sources for new circulars
2. **Comprehends** directives by cross-referencing them against the bank's internal policy corpus using GraphRAG
3. **Generates** department-specific Measurable Action Points (MAPs)
4. **Routes** them to the correct departments via ServiceNow/Jira
5. **Validates** completion autonomously with verifiable evidence

All of this runs **100% on-premise** — no sensitive banking data ever leaves the network perimeter.

---

## How It Works

```
┌──────────────┐     ┌──────────────────┐     ┌───────────────┐     ┌───────────────────┐     ┌─────────────────┐
│  RBI / SEBI  │────▶│  Agent 1: Ingest │────▶│ Agent 2: LTA  │────▶│ Agent 3: MAP Gen  │────▶│  HITL Router    │
│  Circulars   │     │  (Parse & Hash)  │     │  (GraphRAG)   │     │  (Action Points)  │     │ (Risk >= 8.0?)  │
└──────────────┘     └──────────────────┘     └───────────────┘     └───────────────────┘     └────────┬────────┘
                                                                                                       │
                                                                     ┌─────────────────┐               │
                                                                     │  Agent 5: AVA   │◀──────────────┤
                                                                     │  (Validate &    │     Yes ──▶ CCO Review
                                                                     │   Generate PDF) │     No  ──▶ Route directly
                                                                     └────────┬────────┘
                                                                              │
                                                                     ┌────────▼────────┐
                                                                     │  Agent 4: ORA   │
                                                                     │  (ServiceNow    │
                                                                     │   Dispatch)     │
                                                                     └─────────────────┘
```

**In simple terms:**

1. A new RBI circular arrives → the system reads and understands it
2. It figures out which internal bank policies are affected
3. It breaks down the requirements into specific, measurable tasks (MAPs)
4. High-risk tasks get flagged for the Chief Compliance Officer's approval
5. Tasks are assigned to the right departments automatically
6. The system independently verifies that each task was completed, backed by evidence

---

## The Five-Agent Architecture

### Agent 1 — Regulatory Ingestion Agent (RIA)
**File:** `backend/agents/ria.py`

Fetches and parses regulatory PDFs from RBI, SEBI, FIU-IND, and IRDAI portals. Extracts text, computes a SHA-256 hash for deduplication (so the same circular is never processed twice), classifies the document type, and emits a structured `RegulatoryEvent` into the workflow.

### Agent 2 — Legal Translation Agent (LTA) via GraphRAG
**File:** `backend/agents/lta.py`

The core intelligence layer. Maintains a Knowledge Graph mapping Circulars → Policies → Departments with relationships like `SUPERSEDES`, `AMENDS`, and `IMPLEMENTS`. When a new circular arrives, it traverses this graph to find all intersecting internal policies, then runs a faithfulness-scored **Regulatory Delta Analysis** to identify what changed, what's new, and what was superseded.

### Agent 3 — MAP Generator Agent (MGA)
**File:** `backend/agents/mga.py`

Converts the delta analysis into atomic, unambiguous **Measurable Action Points**. Each MAP includes:
- **Department** owner and responsible role
- **Deadline** for compliance
- **Risk score** (0–10) based on penalty severity
- **Step-by-step instructions** for execution
- **Evidence requirements** that must be provided to prove completion

MAPs scoring 8.0+ are flagged for mandatory CCO review before dispatch.

### Agent 4 — Orchestration & Routing Agent (ORA)
**File:** `backend/agents/ora.py`

Authenticates with ServiceNow via OAuth 2.0 and creates incident tickets for each MAP. Uses a Department Routing Matrix to assign MAPs to the correct team (IT Security, Risk Management, HR, Compliance, etc.). Every routing action is recorded in a write-once audit log.

### Agent 5 — Autonomous Validation Agent (AVA)
**File:** `backend/agents/ava.py`

Verifies MAP completion **without relying on self-reporting**. Queries enterprise systems:
- **SIEM/CMDB** for IT configuration changes
- **Document Management System (DMS)** for policy updates
- **Learning Management System (LMS)** for training completions
- **Filing Portal** for regulatory submission confirmations

Upon successful validation, it auto-generates a **Compliance Evidence Package** — a timestamped PDF ready for RBI inspection — and closes the ServiceNow ticket.

---

## Key Features

### Human-in-the-Loop (HITL) Gate
Any MAP with a risk score of **8.0 or above**, or classified as **CRITICAL** priority, is automatically paused and routed to the Chief Compliance Officer's review queue. No critical MAP is dispatched without explicit CCO sign-off. This is built natively into the LangGraph workflow — not bolted on.

### 4-Layer Hallucination Defense
Ensures the AI never fabricates compliance requirements:

| Layer | Mechanism |
|---|---|
| **1. Grounded Prompting** | LLM can only use facts from the provided Context Bundle. Returns `INSUFFICIENT_CONTEXT` rather than guessing. |
| **2. Faithfulness Scoring** | Every LLM output is semantically compared against its source using sentence-transformers. Threshold: cosine similarity ≥ 0.82. |
| **3. Structured Enforcement** | All outputs validated against Pydantic v2 schemas. Three failures triggers human escalation. |
| **4. HITL Gate** | All CRITICAL and HIGH-risk MAPs require explicit CCO approval before dispatch. |

### Zero Data Leakage
All LLM inference runs on **locally-hosted models via Ollama**. No circular text or internal policy data is ever sent to an external API. The system is fully air-gappable.

### Immutable Audit Trail
Every agent action — ingestion, analysis, routing, validation — is recorded in a **write-once SQLite audit log** with timestamps, making the system inspection-ready from day one.

### Evidence-Based Closure
MAPs are never closed based on self-reporting. The Autonomous Validation Agent independently queries enterprise systems to verify that each required action was actually completed before closing the ticket.

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Agent Orchestration** | LangGraph (Python) | Stateful cyclic workflows, native HITL, persistent checkpointing |
| **AI Models** | Mistral / Llama3 via Ollama | On-premise, open-weight LLM ensuring zero data leakage |
| **Embeddings** | sentence-transformers (all-MiniLM-L6-v2) | Faithfulness scoring for hallucination defense |
| **GraphRAG (Data)** | Neo4j (mock) | Knowledge Graph for policy cross-referencing |
| **Vector Store** | ChromaDB | Semantic search (structured for easy Weaviate swap) |
| **PDF Parsing** | PyMuPDF + Unstructured.io | Circular text extraction, OCR, table parsing |
| **Backend API** | FastAPI (Python) | Async REST API with auto-generated OpenAPI docs |
| **Frontend** | Next.js 16 + Tailwind CSS + Recharts | Real-time compliance dashboard |
| **Workflow Routing** | Mock ServiceNow (OAuth2) | Simulates enterprise ITSM ticket creation |
| **Audit Log** | SQLite | Immutable, write-once compliance audit trail |
| **Evidence PDFs** | ReportLab | Auto-generated Compliance Evidence Packages |

---

## Project Structure

```
Anupalan AI/
│
├── start.sh                              # One-command startup for both servers
├── Ideation.md                           # Original hackathon ideation document
│
├── backend/                              # Python FastAPI backend
│   ├── main.py                           # FastAPI application & REST endpoints
│   ├── seed_data.py                      # Mock data seeder & system verification
│   ├── requirements.txt                  # Python dependencies
│   │
│   ├── core/
│   │   ├── state.py                      # LangGraph state schema & Pydantic models
│   │   └── graph.py                      # LangGraph workflow (8-node pipeline)
│   │
│   ├── agents/
│   │   ├── ria.py                        # Agent 1: Regulatory Ingestion Agent
│   │   ├── lta.py                        # Agent 2: Legal Translation Agent (GraphRAG)
│   │   ├── mga.py                        # Agent 3: MAP Generator Agent
│   │   ├── ora.py                        # Agent 4: Orchestration & Routing Agent
│   │   └── ava.py                        # Agent 5: Autonomous Validation Agent
│   │
│   ├── services/
│   │   ├── llm_service.py                # LLM client + 4-layer hallucination defense
│   │   └── audit_log.py                  # SQLite write-once audit log
│   │
│   ├── mocks/
│   │   ├── service_now.py                # Mock ServiceNow API (OAuth2 + tickets)
│   │   └── enterprise_systems.py         # Mock SIEM, DMS, LMS, Filing Portal, Neo4j
│   │
│   └── data/
│       ├── circulars/                    # Ingested regulatory PDFs/text files
│       ├── evidence/                     # Generated Compliance Evidence PDFs
│       └── audit_log.db                  # SQLite audit database
│
└── frontend/                             # Next.js 16 dashboard
    ├── src/app/
    │   ├── page.tsx                      # Main dashboard UI
    │   ├── layout.tsx                    # Root layout
    │   └── globals.css                   # Global styles
    ├── package.json                      # Node.js dependencies
    └── .env.local                        # Environment config (API URL)
```

---

## Prerequisites

| Requirement | Version | Purpose |
|---|---|---|
| **Python** | 3.10+ | Backend runtime |
| **Node.js** | 18+ | Frontend runtime |
| **npm** | 9+ | Frontend package manager |
| **Ollama** *(optional)* | Latest | Local LLM inference (system falls back to mock if unavailable) |

> **Note:** The system includes comprehensive mock fallbacks for all external services. Ollama is **not required** to run the demo — the system will use built-in mock LLM responses when Ollama is not running.

---

## Setup & Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd "Anupalan AI"
```

### 2. Set up the Python backend

```bash
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# Install dependencies


```

### 3. Set up the Next.js frontend

```bash
cd ../frontend

# Install dependencies
npm install
```

### 4. Seed mock data *(optional but recommended)*

```bash
cd ../backend
source venv/bin/activate
python seed_data.py
```

This creates a sample RBI Cybersecurity Master Circular and verifies all system components.

### 5. *(Optional)* Set up Ollama for real LLM inference

```bash
# Install Ollama from https://ollama.ai
ollama pull mistral
# The system will automatically use Ollama at http://localhost:11434
```

---

## Running the System

### Quick Start (Recommended)

```bash
./start.sh
```

This launches both servers simultaneously:
- **Backend API:** [http://localhost:8000](http://localhost:8000)
- **API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Frontend Dashboard:** [http://localhost:3000](http://localhost:3000)

### Manual Start

**Terminal 1 — Backend:**
```bash
cd backend
source venv/bin/activate
python main.py
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev -- -p 3000
```

---

## API Reference

The backend exposes the following REST endpoints. Full interactive documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `POST` | `/api/trigger_ingestion` | Trigger the full compliance pipeline |
| `GET` | `/api/pipeline/{run_id}/status` | Get pipeline run status and MAPs |
| `GET` | `/api/pipeline/{run_id}/stream` | SSE stream for real-time progress |
| `POST` | `/api/hitl/approve` | Approve HITL-gated MAPs (CCO sign-off) |
| `GET` | `/api/graph_state` | View the LangGraph workflow structure |
| `GET` | `/api/audit_logs` | Query the immutable audit log |
| `GET` | `/api/dashboard/summary` | High-level dashboard summary |

### Example: Trigger a Pipeline Run

```bash
curl -X POST http://localhost:8000/api/trigger_ingestion \
  -H "Content-Type: application/json" \
  -d '{"source": "RBI"}'
```

**Response:**
```json
{
  "pipeline_run_id": "a1b2c3d4e5f6",
  "status": "STARTED",
  "message": "Pipeline execution started."
}
```

### Example: Check Pipeline Status

```bash
curl http://localhost:8000/api/pipeline/a1b2c3d4e5f6/status
```

### Example: Approve HITL-Required MAPs

```bash
curl -X POST http://localhost:8000/api/hitl/approve \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline_run_id": "a1b2c3d4e5f6",
    "approved_by": "CCO",
    "approved_map_ids": ["MAP-2025-001", "MAP-2025-002"],
    "comments": "Approved for immediate execution"
  }'
```

---

## Configuration

### Backend

| Setting | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL for local LLM inference |
| `OLLAMA_MODEL` | `mistral` | Ollama model to use (or `llama3`) |
| `FAITHFULNESS_THRESHOLD` | `0.82` | Minimum cosine similarity for hallucination check |
| `MAX_RETRIES` | `3` | LLM retry attempts before human escalation |
| API Port | `8000` | FastAPI server port |

### Frontend

| Setting | Default | File |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | `frontend/.env.local` |
| Dev Port | `3000` | Passed via `npm run dev -- -p 3000` |

---

## Demo Walkthrough

When you open the dashboard at [http://localhost:3000](http://localhost:3000), the pipeline automatically runs a demonstration:

1. **Ingestion** — The system reads a mock RBI Master Circular on *"Cyber Security Framework for Banks — Enhanced Requirements"* (120+ pages equivalent, covering MFA, transaction monitoring, CSOC setup, and incident reporting).

2. **GraphRAG Analysis** — The Knowledge Graph identifies **5 intersecting internal policies** across **4 departments**: IT Security, Risk Management, HR, and Compliance.

3. **MAP Generation** — The system produces **5 Measurable Action Points**:

   | MAP ID | Department | Risk Score | Priority | HITL Required |
   |---|---|---|---|---|
   | MAP-2025-001 | IT Security | 9.0 | CRITICAL | Yes |
   | MAP-2025-002 | Risk Management | 8.5 | CRITICAL | Yes |
   | MAP-2025-003 | HR | 5.0 | MEDIUM | No |
   | MAP-2025-004 | IT Security | 8.0 | HIGH | Yes |
   | MAP-2025-005 | Compliance | 7.5 | HIGH | No |

4. **Routing** — Each MAP is dispatched as a ServiceNow ticket to the correct department.

5. **Validation** — The system queries mock enterprise systems (SIEM, DMS, LMS, Filing Portal) and generates **Compliance Evidence Package PDFs** in `backend/data/evidence/`.

6. **Audit Trail** — Every action is recorded in `backend/data/audit_log.db` with timestamps.

---

## Business Impact

| Metric | Before Anupalan AI | With Anupalan AI |
|---|---|---|
| Compliance turnaround time | 10–21 business days | Under 4 hours (40x faster) |
| Analyst hours per circular | ~120 person-hours | Under 8 person-hours (93% reduction) |
| MAP accountability | Self-reported, no verification | 100% evidence-backed closure |
| Regulatory penalty risk | High (₹1–5 Cr per action) | Near-zero with deadline automation |
| Estimated annual value | — | **₹2.8–3.1 Crores** (cost avoidance + efficiency) |

---

## License

This project is developed for the **SuRaksha Cyber Hackathon 2.0** hosted by Canara Bank.

```
MIT License

Copyright (c) 2025 Anupalan AI Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---
