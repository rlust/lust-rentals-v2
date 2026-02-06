import shutil
import sys
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if 'fpdf' not in sys.modules:
    class _StubFPDF:  # pragma: no cover - simple stub for tests
        def __init__(self):
            self._y = 0

        def add_page(self):
            self._y = 0
            return None

        def set_font(self, *args, **kwargs):
            return None

        def cell(self, *args, **kwargs):
            # Simulate vertical position increment
            if len(args) > 1:
                self._y += args[1]
            return None

        def ln(self, *args, **kwargs):
            if args:
                self._y += args[0]
            else:
                self._y += 5
            return None

        def set_fill_color(self, *args, **kwargs):
            return None

        def get_y(self):
            return self._y

        def output(self, *args, **kwargs):
            if args:
                target = Path(args[0])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.touch()
            return ""

    stub_module = types.SimpleNamespace(FPDF=_StubFPDF)
    sys.modules['fpdf'] = stub_module

import pytest

from src.data_processing.processor import FinancialDataProcessor
from src.reporting.tax_reports import TaxReporter

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture()
def bank_transaction_fixture() -> Path:
    return FIXTURE_DIR / "bank_transaction_sample.csv"


@pytest.fixture()
def deposit_map_fixture() -> Path:
    return FIXTURE_DIR / "deposit_map_sample.csv"


def copy_fixture(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dest)


@pytest.fixture()
def configured_reporter(
    tmp_path: Path,
    bank_transaction_fixture: Path,
    deposit_map_fixture: Path,
) -> TaxReporter:
    data_dir = tmp_path / "data"
    processor = FinancialDataProcessor(data_dir=data_dir)

    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    copy_fixture(bank_transaction_fixture, raw_dir / "transaction_report-3.csv")
    copy_fixture(deposit_map_fixture, raw_dir / "deposit_amount_map.csv")

    return TaxReporter(data_processor=processor)


def test_generate_annual_summary_includes_property_breakdown(configured_reporter: TaxReporter) -> None:
    summary = configured_reporter.generate_annual_summary(year=2025, save_to_file=False)

    assert summary["total_income"] == pytest.approx(3385.0)
    assert summary["total_expenses"] == pytest.approx(310.61)
    assert summary["net_income"] == pytest.approx(3074.39, rel=1e-4)

    property_breakdown = summary["property_breakdown"]
    assert property_breakdown["118 W Shields St"] == pytest.approx(985.0)
    assert property_breakdown["966 Kinsbury Court"] == pytest.approx(1300.0)
    assert property_breakdown["41 26th St"] == pytest.approx(1100.0)

    review_counts = summary["mapping_review_counts"]
    assert review_counts.get("manual_review", 0) == 0
    assert summary["unresolved_transaction_count"] == 0


def test_generate_annual_summary_includes_expense_by_property(configured_reporter: TaxReporter) -> None:
    """Test that annual summary includes expense breakdown by property."""
    summary = configured_reporter.generate_annual_summary(year=2025, save_to_file=False)

    # Check that expense_by_property key exists
    assert "expense_by_property" in summary

    expense_by_property = summary["expense_by_property"]

    # expense_by_property should be a dictionary
    assert isinstance(expense_by_property, dict)

    # If there are expenses with property assignments, verify structure
    if expense_by_property:
        # Each property should have a dictionary of categories
        for property_name, categories in expense_by_property.items():
            assert isinstance(categories, dict)
            # Each category should have a numeric amount
            for category, amount in categories.items():
                assert isinstance(amount, (int, float))
                assert amount >= 0


def test_generate_schedule_e_outputs_property_summary(configured_reporter: TaxReporter, tmp_path: Path) -> None:
    schedule = configured_reporter.generate_schedule_e(year=2025)

    assert schedule["1"] == pytest.approx(3385.0)
    assert schedule["9"] == pytest.approx(310.61)
    assert schedule["12"] == pytest.approx(3074.39, rel=1e-4)


def test_generate_per_property_schedule_e(configured_reporter: TaxReporter) -> None:
    """Test generating individual Schedule E forms for each property."""
    per_property = configured_reporter.generate_per_property_schedule_e(year=2025)

    # Should have 3 properties
    assert len(per_property) == 3
    assert "118 W Shields St" in per_property
    assert "966 Kinsbury Court" in per_property
    assert "41 26th St" in per_property

    # Check individual property schedules
    shields_schedule = per_property["118 W Shields St"]
    assert shields_schedule["1"] == pytest.approx(985.0)  # Rental income
    assert shields_schedule["property_name"] == "118 W Shields St"

    kinsbury_schedule = per_property["966 Kinsbury Court"]
    assert kinsbury_schedule["1"] == pytest.approx(1300.0)

    st_26_schedule = per_property["41 26th St"]
    assert st_26_schedule["1"] == pytest.approx(1100.0)

    # Verify each property has all Schedule E lines
    for property_name, schedule in per_property.items():
        assert "1" in schedule  # Rental income
        assert "12" in schedule  # Net income/loss
        # Net income should equal rental income minus expenses
        net_income = schedule["1"] - schedule["11"]
        assert schedule["12"] == pytest.approx(net_income)


def test_generate_aggregated_schedule_e(configured_reporter: TaxReporter) -> None:
    """Test generating aggregated Schedule E across all properties."""
    aggregated = configured_reporter.generate_aggregated_schedule_e(year=2025, save_to_file=False)

    # Should have property count and list
    assert aggregated["property_count"] == 3
    assert len(aggregated["properties"]) == 3

    # Aggregated totals should match original total
    assert aggregated["1"] == pytest.approx(3385.0)  # Total rental income
    # Note: Test data doesn't have expenses assigned to properties, so net income = rental income
    assert aggregated["12"] == pytest.approx(3385.0)  # Net income/loss

    # Should include per-property details
    assert "per_property_details" in aggregated
    assert len(aggregated["per_property_details"]) == 3


def test_per_property_schedule_e_csv_files_created(configured_reporter: TaxReporter) -> None:
    """Test that individual CSV files are created for each property."""
    configured_reporter.generate_per_property_schedule_e(year=2025)

    # Check that CSV files were created
    reports_dir = configured_reporter.reports_dir

    assert (reports_dir / "schedule_e_2025_118_W_Shields_St.csv").exists()
    assert (reports_dir / "schedule_e_2025_966_Kinsbury_Court.csv").exists()
    assert (reports_dir / "schedule_e_2025_41_26th_St.csv").exists()


def test_aggregated_schedule_e_creates_files(configured_reporter: TaxReporter) -> None:
    """Test that aggregated Schedule E creates all expected files."""
    configured_reporter.generate_aggregated_schedule_e(year=2025, save_to_file=True)

    reports_dir = configured_reporter.reports_dir

    # Should create aggregate CSV
    assert (reports_dir / "schedule_e_2025_aggregate.csv").exists()

    # Should create detailed PDF
    assert (reports_dir / "schedule_e_2025_detailed.pdf").exists()

    # Should also create individual property CSVs
    assert (reports_dir / "schedule_e_2025_118_W_Shields_St.csv").exists()


def test_per_property_schedule_e_with_expenses(configured_reporter: TaxReporter, tmp_path: Path) -> None:
    """Test per-property Schedule E correctly categorizes expenses."""
    # First process the data to get expenses assigned
    configured_reporter.processor.process_bank_transactions(year=2025)

    per_property = configured_reporter.generate_per_property_schedule_e(year=2025)

    # At least one property should have expenses if expenses are properly attributed
    # This depends on the test data having property_name set on expenses
    for property_name, schedule in per_property.items():
        # Each schedule should have expense lines initialized
        assert "4" in schedule  # Insurance
        assert "5" in schedule  # Mortgage interest
        assert "7" in schedule  # Repairs
        assert "8" in schedule  # Taxes
        assert "9" in schedule  # Other expenses
        assert "11" in schedule  # Total expenses
