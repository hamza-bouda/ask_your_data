"""Conversation Orchestrator — LangGraph pipeline.

Phase 01: skeleton with health/ready endpoints only.
Phase 07 will add the LangGraph decision graph:
classify → clarify? → retrieve → plan → generate_sql →
validate → execute → repair? → present.
"""

from contracts.service_factory import create_service_app

app = create_service_app(service_name="orchestrator")
