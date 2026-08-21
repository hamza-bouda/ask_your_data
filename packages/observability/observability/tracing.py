import os
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.propagate import extract, inject

def setup_tracing(service_name: str, app: FastAPI = None):
    """Initialize OpenTelemetry tracing and optionally instrument a FastAPI app."""
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
    
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    
    # Use OTLP exporter
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    
    trace.set_tracer_provider(provider)
    
    if app:
        # Exclude endpoints that generate too much noise
        excluded_urls = "health,ready,metrics"
        FastAPIInstrumentor.instrument_app(app, excluded_urls=excluded_urls)

def get_tracer(module_name: str):
    """Get a tracer instance for manual instrumentation."""
    return trace.get_tracer(module_name)

def get_current_span():
    """Get the current active span."""
    return trace.get_current_span()

def inject_context(carrier: dict = None) -> dict:
    """Inject current tracing context into a dict (e.g., for Redis message headers)."""
    if carrier is None:
        carrier = {}
    inject(carrier)
    return carrier

def extract_context(carrier: dict):
    """Extract tracing context from a dict to resume a trace."""
    return extract(carrier)
