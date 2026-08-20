"""Configuration for the SQL Executor Service."""

import os

# Analytics Database (Target DB to run queries against)
ANALYTICS_DB_URL = os.getenv(
    "ANALYTICS_DB_URL", 
    "postgresql://postgres:postgres@postgres:5432/askyourdata"
)
