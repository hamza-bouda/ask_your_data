import pytest
from backend.services.orchestrator.app.dashboards import sanitize_csv_cell

def test_csv_injection_prevention():
    assert sanitize_csv_cell("=1+1") == "'=1+1"
    assert sanitize_csv_cell("+SUM(A1:A10)") == "'+SUM(A1:A10)"
    assert sanitize_csv_cell("-1") == "'-1"
    assert sanitize_csv_cell("@cmd|' /C calc'!A0") == "'@cmd|' /C calc'!A0"
    
    # Safe values shouldn't be touched
    assert sanitize_csv_cell("1") == "1"
    assert sanitize_csv_cell("Total") == "Total"
    assert sanitize_csv_cell(None) == ""
