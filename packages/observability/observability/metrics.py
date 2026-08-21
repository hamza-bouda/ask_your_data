from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

def setup_metrics(app: FastAPI):
    """
    Setup Prometheus metrics for a FastAPI application.
    Exposes /metrics endpoint and tracks HTTP requests (duration, counts, etc).
    """
    # Instrumentator adds middleware and endpoint
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics", "/health", "/ready"],
        env_var_name="ENABLE_METRICS",
        inprogress_name="inprogress",
        inprogress_labels=True,
    )
    
    # We use custom metrics directly from prometheus_client in specific services 
    # instead of adding generic high-cardinality labels here.
    
    instrumentator.instrument(app).expose(app, endpoint="/metrics")
    return instrumentator
