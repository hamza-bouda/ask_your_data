"""Global test configuration and fixtures for Ask Your Data."""

import os
import sys
import pytest

# Ensure all service paths are in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
service_dirs = [
    os.path.join(BASE_DIR, "backend", "services", "gateway"),
    os.path.join(BASE_DIR, "backend", "services", "identity"),
    os.path.join(BASE_DIR, "backend", "services", "catalog"),
    os.path.join(BASE_DIR, "backend", "services", "orchestrator"),
    os.path.join(BASE_DIR, "backend", "services", "visualization"),
    os.path.join(BASE_DIR, "backend", "services", "sql_executor"),
    os.path.join(BASE_DIR, "backend", "services", "sql_generator"),
    os.path.join(BASE_DIR, "backend", "services", "semantic_router"),
    os.path.join(BASE_DIR, "packages", "contracts"),
    os.path.join(BASE_DIR, "packages", "observability"),
]
for p in service_dirs:
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ["FERNET_KEY"] = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("APP_ENV", "test")
os.environ["JWT_SECRET_KEY"] = "dev-secret-change-in-production"
os.environ["JWT_SECRET"] = "dev-secret-change-in-production"
