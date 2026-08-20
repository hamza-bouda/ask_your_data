"""Configuration for the API Gateway."""

import os

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
IDENTITY_URL = os.getenv("IDENTITY_URL", "http://identity:8001")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8004")

RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
