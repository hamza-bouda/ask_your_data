import pytest
from fastapi.testclient import TestClient
from backend.services.visualization.app.main import app

client = TestClient(app)

def test_visualization_metric():
    # 1 row, 1 numeric column -> metric
    payload = {
        "results": [{"total_sales": 10500.5}],
        "semantic_plan": {},
        "question": "What are the total sales?"
    }
    response = client.post("/internal/chart-spec", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["chart_type"] == "metric"
    assert data["y_field"] == "total_sales"

def test_visualization_line():
    # date/time + numeric -> line
    payload = {
        "results": [
            {"date": "2023-01-01", "sales": 100},
            {"date": "2023-01-02", "sales": 150}
        ]
    }
    response = client.post("/internal/chart-spec", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["chart_type"] == "line"
    assert data["x_field"] == "date"
    assert data["y_field"] == "sales"

def test_visualization_pie():
    # categorical + numeric, <= 6 categories -> pie
    payload = {
        "results": [
            {"category": "A", "count": 10},
            {"category": "B", "count": 20},
            {"category": "C", "count": 30}
        ]
    }
    response = client.post("/internal/chart-spec", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["chart_type"] == "pie"
    assert data["x_field"] == "category"
    assert data["y_field"] == "count"

def test_visualization_bar():
    # categorical + numeric, > 6 categories -> bar
    payload = {
        "results": [{"category": f"C{i}", "value": i} for i in range(10)]
    }
    response = client.post("/internal/chart-spec", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["chart_type"] == "bar"
    assert data["x_field"] == "category"
    assert data["y_field"] == "value"

def test_visualization_fallback_table_too_many_rows():
    # > 50 rows -> table
    payload = {
        "results": [{"category": f"C{i}", "value": i} for i in range(55)]
    }
    response = client.post("/internal/chart-spec", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["chart_type"] == "table"
    assert len(data["warnings"]) > 0
    assert "50 lignes" in data["warnings"][0]

def test_visualization_fallback_table_no_chart_pattern():
    # multiple strings, no numeric -> table
    payload = {
        "results": [
            {"name": "Alice", "city": "Paris"},
            {"name": "Bob", "city": "London"}
        ]
    }
    response = client.post("/internal/chart-spec", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["chart_type"] == "table"


@pytest.mark.parametrize(
    ("question", "results", "expected"),
    [
        ("montre un graphique en aire", [{"date": "2024-01-01", "value": 2}, {"date": "2024-01-02", "value": 4}], "area"),
        ("barres horizontales", [{"category": "A", "value": 2}, {"category": "B", "value": 4}], "horizontal_bar"),
        ("un donut", [{"category": "A", "value": 2}, {"category": "B", "value": 4}], "donut"),
        ("un radar", [{"category": "A", "value": 2}, {"category": "B", "value": 4}], "radar"),
        ("un nuage de points", [{"x": 2, "y": 4}, {"x": 3, "y": 8}], "scatter"),
        ("affiche le tableau", [{"category": "A", "value": 2}, {"category": "B", "value": 4}], "table"),
    ],
)
def test_visualization_honors_explicit_supported_type(question, results, expected):
    response = client.post("/internal/chart-spec", json={"results": results, "question": question})
    assert response.status_code == 200
    assert response.json()["chart_type"] == expected
