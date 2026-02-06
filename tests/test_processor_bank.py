import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import pytest

from src.data_processing.processor import FinancialDataProcessor

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


def test_process_bank_transactions_with_mapping(
    tmp_path: Path,
    bank_transaction_fixture: Path,
    deposit_map_fixture: Path,
) -> None:
    data_dir = tmp_path / "data"
    processor = FinancialDataProcessor(data_dir=data_dir)

    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    copy_fixture(bank_transaction_fixture, raw_dir / "transaction_report-3.csv")
    copy_fixture(deposit_map_fixture, raw_dir / "deposit_amount_map.csv")

    results = processor.process_bank_transactions(year=2025)

    assert "income" in results and "expenses" in results

    income_df = results["income"].sort_values("amount").reset_index(drop=True)
    expense_df = results["expenses"].sort_values("amount").reset_index(drop=True)

    # Income amounts stay positive and mapped to properties when available
    assert income_df["amount"].tolist() == [985.0, 1100.0, 1300.0]
    assert income_df["mapping_status"].tolist() == ["mapped", "mapped", "mapped"]
    assert income_df["property_name"].tolist() == [
        "118 W Shields St",
        "41 26th St",
        "966 Kinsbury Court",
    ]
    assert income_df["transaction_id"].str.contains("income").all()

    # Expenses derived from debit transactions remain positive
    assert expense_df["amount"].tolist() == pytest.approx([60.61, 250.0])
    assert expense_df["transaction_id"].str.contains("expense").all()

    review_file = processor.processed_data_dir / "income_mapping_review.csv"
    assert not review_file.exists()

    expense_review_file = processor.processed_data_dir / "expense_category_review.csv"
    assert expense_review_file.exists()
    review_df = pd.read_csv(expense_review_file)
    assert sorted(review_df["transaction_id"].tolist()) == sorted(expense_df["transaction_id"].tolist())
    assert review_df["category"].str.lower().tolist().count("other") == 2

    # Normalized snapshot persisted for audit
    snapshot_file = processor.processed_data_dir / "bank_transactions_normalized.csv"
    assert snapshot_file.exists()

    processed_income = pd.read_csv(processor.processed_data_dir / "processed_income.csv")
    processed_expenses = pd.read_csv(processor.processed_data_dir / "processed_expenses.csv")
    assert "transaction_id" in processed_income.columns
    assert "transaction_id" in processed_expenses.columns
