from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

def setup_metrics(app: FastAPI):
    """
    Setup Prometheus metrics for a FastAPI application idempotently.
    Exposes /metrics endpoint and tracks HTTP requests (duration, counts, etc).
    """
    if getattr(app.state, "_metrics_initialized", False):
        return None
    try:
        instrumentator = Instrumentator(
            should_group_status_codes=False,
            should_ignore_untemplated=True,
            should_respect_env_var=False,
            should_instrument_requests_inprogress=False,
            excluded_handlers=["/metrics", "/health", "/ready"],
            env_var_name="ENABLE_METRICS",
        )
        instrumentator.instrument(app).expose(app, endpoint="/metrics")
        app.state._metrics_initialized = True
        return instrumentator
    except Exception:
        return None
