import importlib
import os
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def copy_fixture(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dest)


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    data_dir = tmp_path / "data"
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    copy_fixture(FIXTURE_DIR / "bank_transaction_sample.csv", raw_dir / "transaction_report-3.csv")
    copy_fixture(FIXTURE_DIR / "deposit_map_sample.csv", raw_dir / "deposit_amount_map.csv")

    monkeypatch.setenv("LUST_DATA_DIR", str(data_dir))

    module = importlib.import_module("src.api.server")
    module = importlib.reload(module)

    return TestClient(module.app)


def test_process_bank_endpoint(api_client: TestClient) -> None:
    response = api_client.post("/process/bank", json={"year": 2025})

    assert response.status_code == 200
    payload = response.json()

    assert payload["income_rows"] == 3
    assert payload["expense_rows"] == 2
    assert payload["unresolved_rows"] == 0


def test_generate_reports_endpoints(api_client: TestClient) -> None:
    summary_response = api_client.post(
        "/reports/annual",
        json={"year": 2025},
    )

    assert summary_response.status_code == 200
    summary = summary_response.json()

    assert summary["total_income"] == pytest.approx(3385.0)
    assert summary["net_income"] == pytest.approx(3074.39, rel=1e-4)
    assert summary["property_breakdown"]["966 Kinsbury Court"] == pytest.approx(1300.0)

    schedule_response = api_client.post(
        "/reports/schedule-e",
        json={"year": 2025},
    )

    assert schedule_response.status_code == 200
    schedule = schedule_response.json()

    assert schedule["1"] == pytest.approx(3385.0)
    assert schedule["11"] == pytest.approx(310.61)
    assert any(
        entry["property_name"] == "966 Kinsbury Court" for entry in schedule["property_summary"]
    )

    review_income = api_client.get("/review/income").json()
    review_expense = api_client.get("/review/expenses").json()

    assert review_income == []
    assert len(review_expense) == 2

    property_choices = ["118 W Shields St", "41 26th St", "966 Kinsbury Court"]

    for idx, item in enumerate(review_expense):
        response = api_client.post(
            f"/review/expenses/{item['transaction_id']}",
            json={
                "category": f"Manual-{idx}",
                "property_name": property_choices[idx % len(property_choices)],
            },
        )
        assert response.status_code == 200

    review_expense_after = api_client.get("/review/expenses").json()
    assert review_expense_after == []

    from src.review.manager import ReviewManager  # imported lazily to reuse env config

    manager = ReviewManager(Path(os.environ["LUST_DATA_DIR"]))
    overrides_df = manager.load_expense_overrides()
    assert len(overrides_df) == 2
    assert set(overrides_df["category"].tolist()) == {"Manual-0", "Manual-1"}
    assert set(overrides_df["property_name"].dropna().tolist()) <= set(property_choices)

    export_response = api_client.get("/export/income")
    assert export_response.status_code == 200
    assert export_response.headers["content-type"].startswith("text/csv")
    assert "processed_income.csv" in export_response.headers["content-disposition"]
    assert "transaction_id" in export_response.text

    status_response = api_client.get("/reports/status", params={"year": 2025})
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["year"] == 2025
    summary_meta = status_payload["artifacts"]["summary_pdf"]
    assert summary_meta["exists"] is True
    schedule_meta = status_payload["artifacts"]["schedule_csv"]
    assert schedule_meta["exists"] is True

    download_summary = api_client.get("/reports/download/summary_pdf", params={"year": 2025})
    assert download_summary.status_code == 200
    assert download_summary.headers["content-type"] == "application/pdf"
    assert "lust_rentals_tax_summary_2025.pdf" in download_summary.headers["content-disposition"]

    download_schedule = api_client.get("/reports/download/schedule_csv", params={"year": 2025})
    assert download_schedule.status_code == 200
    assert download_schedule.headers["content-type"].startswith("text/csv")
    assert "schedule_e_2025.csv" in download_schedule.headers["content-disposition"]


def test_excel_export_endpoint(api_client: TestClient) -> None:
    """Test the Excel export functionality."""
    # First, process bank transactions to have data
    process_response = api_client.post("/process/bank", json={"year": 2025})
    assert process_response.status_code == 200

    # Test Excel export
    excel_response = api_client.get("/export/excel/report", params={"year": 2025})
    assert excel_response.status_code == 200
    assert excel_response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "lust_rentals_report_2025.xlsx" in excel_response.headers["content-disposition"]

    # Verify the response contains binary data (Excel file)
    assert len(excel_response.content) > 0

    # Optionally verify it's a valid Excel file by checking the file signature
    # Excel files start with PK (ZIP signature)
    assert excel_response.content[:2] == b'PK'
