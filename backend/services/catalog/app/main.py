"""Schema Catalog & Retrieval Service — schema introspection and search.

Phase 01: skeleton with health/ready endpoints only.
Phase 04 will add PostgreSQL connector, schema introspection,
versioned snapshots, and catalog document creation.
Phase 05 will add BGE-M3 embeddings and hybrid retrieval.
"""

from contracts.service_factory import create_service_app

app = create_service_app(service_name="catalog")
