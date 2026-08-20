# ADR 001 — Monorepo structure

## Status
Accepted

## Date
2026-08-20

## Context
Ask Your Data is a Conversational BI product built as a set of microservices.
We need a repository structure that supports:
- Independent service development and deployment
- Shared contracts between services
- Local Docker Compose development
- A clear path toward CI/CD per service (Phase 12)

## Decision
We adopt a **monorepo** with the following top-level layout:

```
ask_your_data/
├── backend/services/       # One directory per microservice
├── frontend/               # Next.js frontend (Phase 09)
├── packages/contracts/     # Shared Pydantic models (pip-installable)
├── infra/compose/          # Docker Compose for local dev
├── tests/                  # Cross-service contract tests
├── docs/adr/               # Architecture Decision Records
└── roadmap/                # Project roadmap
```

### Services
Six services, each with its own `Dockerfile`, `requirements.txt`, and `app/` package:
- **gateway** (port 8000) — API Gateway / BFF
- **identity** (port 8001) — Identity & Tenant resolution
- **catalog** (port 8002) — Schema Catalog & Retrieval
- **query_execution** (port 8003) — SQL validation & execution
- **orchestrator** (port 8004) — LangGraph conversation pipeline
- **visualization** (port 8005) — Chart specification

### Shared Contracts
The `packages/contracts` package is installed as a local dependency in each
service's Docker image. It defines the 5 core Pydantic models:
`TenantContext`, `QueryRequest`, `RunEvent`, `ChartSpec`, `ApiError`.

### Why Monorepo
- **Atomic changes**: A contract change + service update is a single commit
- **Shared CI config**: Easier to enforce consistent linting, testing, typing
- **Simpler onboarding**: One `git clone`, one `docker compose up`
- **Independent deploy**: Each service has its own Dockerfile and can be
  built/deployed independently (Phase 12)

## Consequences
- All developers work in the same repository
- CI must be smart enough to detect which services changed (Phase 12)
- The `contracts` package version must be bumped when breaking changes occur
