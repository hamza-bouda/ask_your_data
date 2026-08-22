from app.generator import generate_sql


def test_mock_generator_creates_safe_count_query(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    draft = generate_sql(
        query="How many rows are in orders?",
        semantic_plan={"source_tables": ["orders"]},
        schema={"tables": [{"name": "orders"}]},
    )
    assert draft.sql_query == 'SELECT COUNT(*) AS row_count FROM "orders"'
    assert draft.metric == "row_count"


def test_mock_generator_rejects_unsafe_table_identifier(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    try:
        generate_sql("count", {"source_tables": ["orders; DROP TABLE users"]}, {})
    except RuntimeError as error:
        assert "safe source table" in str(error)
    else:
        raise AssertionError("Unsafe table identifier was accepted")
