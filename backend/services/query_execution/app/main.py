"""Query Execution Service — SQL validation and read-only execution.

Phase 01: skeleton with health/ready endpoints only.
Phase 06 will add SQLGlot parsing, allowlist validation, SQLAlchemy
execution with read-only account, timeout, max_rows, and audit.
"""

from contracts.service_factory import create_service_app
from observability import setup_logging, setup_tracing, setup_metrics


app = create_service_app(service_name="query-execution")

# Observability setup
setup_logging(service_name="query-execution")
setup_tracing(service_name="query-execution", app=app)
setup_metrics(app)

