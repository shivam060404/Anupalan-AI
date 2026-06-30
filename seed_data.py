"""
Seed Data Script
=================
Populates mock data for the Anupalan AI prototype:
1. Drops a mock RBI Master Circular into the ingestion folder
2. Sets up the Knowledge Graph with mock Canara Bank policies
3. Creates sample audit log entries
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agents.ria import RegulatoryIngestionAgent, CIRCULARS_DIR
from mocks.enterprise_systems import MockNeo4jGraph
from services.audit_log import AuditLogService


def seed_circular():
    """Drop a mock RBI circular into the ingestion directory."""
    print("[SEED] Creating sample RBI circular...")
    ria = RegulatoryIngestionAgent()
    sample_path = ria._create_sample_circular()
    print(f"  -> Created: {sample_path}")
    print(f"  -> Size: {sample_path.stat().st_size} bytes")
    return sample_path


def seed_knowledge_graph():
    """Initialize the mock knowledge graph with Canara Bank policies."""
    print("[SEED] Initializing Knowledge Graph...")
    graph = MockNeo4jGraph()

    # Verify graph data
    impact = graph.traverse_circular_impact("RBI/CYBSEC/2025/001")
    print(f"  -> Circulars: {len(graph._nodes['circulars'])}")
    print(f"  -> Policies: {len(graph._nodes['policies'])}")
    print(f"  -> Departments: {len(graph._nodes['departments'])}")
    print(f"  -> Relationships: {len(graph._relationships)}")
    print(f"  -> Impact traversal found {len(impact['policies'])} affected policies")

    return graph


def seed_audit_log():
    """Create sample audit log entries."""
    print("[SEED] Seeding audit log...")
    audit = AuditLogService()

    # Add sample entries
    audit.log(
        pipeline_run_id="SEED-001",
        agent="SEED",
        action="DATA_SEEDED",
        details={"circular": "RBI_CyberSecurity_2025.txt", "policies": 5, "departments": 7},
    )
    print("  -> Audit log seeded")
    return audit


def verify_system():
    """Run a quick system verification."""
    print("\n[VERIFY] System verification...")

    # Check imports
    try:
        from core.state import AnupalanState, RegulatoryEvent, PolicyDelta, MeasurableActionPoint
        print("  -> State schemas: OK")
    except Exception as e:
        print(f"  -> State schemas: FAILED ({e})")

    try:
        from services.llm_service import LLMService, LocalLLMClient, FaithfulnessScorer
        print("  -> LLM Service: OK")
    except Exception as e:
        print(f"  -> LLM Service: FAILED ({e})")

    try:
        from core.graph import build_graph, compile_graph
        print("  -> LangGraph workflow: OK")
    except Exception as e:
        print(f"  -> LangGraph workflow: FAILED ({e})")

    try:
        from fastapi import FastAPI
        print("  -> FastAPI: OK")
    except Exception as e:
        print(f"  -> FastAPI: FAILED ({e})")

    try:
        import langgraph
        try:
            version = langgraph.__version__
        except AttributeError:
            import importlib.metadata
            try:
                version = importlib.metadata.version("langgraph")
            except Exception:
                version = "installed (version unknown)"
        print(f"  -> LangGraph version: {version}")
    except Exception as e:
        print(f"  -> LangGraph: FAILED ({e})")

    print("\n[VERIFY] System verification complete.")


if __name__ == "__main__":
    print("=" * 60)
    print("ANUPALAN AI - Seed Data & Verification")
    print("=" * 60)

    seed_circular()
    seed_knowledge_graph()
    seed_audit_log()
    verify_system()

    print("\n[DONE] System is ready. Run the backend with:")
    print("  cd backend && source venv/bin/activate && python main.py")
    print("\nAnd the frontend with:")
    print("  cd frontend && npm run dev")
