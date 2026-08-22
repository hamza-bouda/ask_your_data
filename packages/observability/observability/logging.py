import logging
import os
import structlog
from opentelemetry import trace

import re

SENSITIVE_KEYS = {"password", "token", "secret", "connection_string", "api_key", "sql_error", "openai_api_key"}

# Matches JWTs and other common Bearer tokens
BEARER_TOKEN_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*", re.IGNORECASE)

def _redact_sensitive_data(logger, log_method, event_dict):
    """Redact sensitive keys from log event."""
    for key in list(event_dict.keys()):
        if any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS):
            event_dict[key] = "***REDACTED***"
            
        # Also check values if they are strings and look like connection strings
        val = event_dict[key]
        if isinstance(val, str):
            if "://" in val and "@" in val and ":" in val: # Simple heuristic for postgres://user:pass@...
                event_dict[key] = "***REDACTED_CONN_STR***"
            elif BEARER_TOKEN_PATTERN.search(val):
                event_dict[key] = BEARER_TOKEN_PATTERN.sub("Bearer ***REDACTED_TOKEN***", val)
                
    return event_dict

def _add_opentelemetry_trace_info(logger, log_method, event_dict):
    """Add trace_id and span_id from OpenTelemetry to logs."""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        ctx = span.get_span_context()
        event_dict["trace_id"] = f"{ctx.trace_id:032x}"
        event_dict["span_id"] = f"{ctx.span_id:016x}"
    return event_dict

def setup_logging(service_name: str, log_level: str = "INFO"):
    """Initialize structured logging for a service."""
    # Ensure standard library logging is configured
    logging.basicConfig(
        format="%(message)s",
        stream=os.sys.stdout,
        level=logging.getLevelName(log_level.upper()),
    )

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        _add_opentelemetry_trace_info,
        _redact_sensitive_data,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    # Use JSON in production, ConsoleRenderer in dev if preferred, but requirement asks for standard JSON logs in all services.
    processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Optional: Bind service name globally
    structlog.contextvars.bind_contextvars(service=service_name)
