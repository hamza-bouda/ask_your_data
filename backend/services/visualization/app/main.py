"""Visualization Service — deterministic chart specification.

Phase 01: skeleton with health/ready endpoints only.
Phase 09 will add ChartSpec generation from ResultSet + SemanticPlan,
deterministic chart type selection, and Plotly-compatible output.
"""

from contracts.service_factory import create_service_app

app = create_service_app(service_name="visualization")
