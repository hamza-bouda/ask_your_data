# Observability Guide

Ask Your Data implements comprehensive observability including distributed tracing, structured logging, and metrics.

## Local Observability Stack

The `docker-compose.yml` includes the following observability tools:
- **Prometheus** (`http://localhost:9090`): Scrapes metrics from all services via their `/metrics` endpoints.
- **Grafana** (`http://localhost:3000`): Visualizes metrics. Dashboards are pre-provisioned.
- **Jaeger** (`http://localhost:16686`): Receives and visualizes distributed OpenTelemetry traces.

## Tracing

Every request entering the API Gateway starts a trace. The `traceparent` context is propagated via HTTP headers and Redis Stream payloads, allowing you to follow a user's prompt through the Semantic Router, SQL Generator, Worker, and SQL Executor.

**No sensitive data** (like full SQL queries, DB connection strings, or full LLM prompts) is included in trace attributes.

## Logging

Logs are formatted as structured JSON using `structlog`.
All logs automatically include `correlation_id` and `trace_id`.

**Secret Redaction**: A custom structlog processor redacts passwords, connection strings, and tokens before they are emitted.

## Troubleshooting

- **Blocked Runs / DLQ**: Check the `Worker DLQ Messages` stat on the Grafana dashboard. If it's increasing, tasks are failing repeatedly (max 3 retries). Use Redis CLI to inspect `stream:dlq:runs`.
- **Secret redaction**: Structured logging redacts sensitive fields before output. The E2E suite verifies that datasource metadata returned through the public API never contains a connection string.
- **Worker health**: The worker publishes Prometheus metrics on its internal port `8000`; Docker marks it healthy only when `/metrics` responds. If it is unhealthy, inspect `docker compose logs worker` before retrying runs.
- **Deterministic E2E**: Run `docker compose -f tests/e2e/docker-compose.e2e.yml up -d --build --wait`, then `pytest tests/e2e/test_end_to_end.py`. This stack provisions and allowlists its own source and exercises catalogue discovery, SSE, SQL and chart selection without a provider key.
