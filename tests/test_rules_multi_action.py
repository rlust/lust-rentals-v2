import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.api.models import RuleCreate
from src.data_processing.processor import FinancialDataProcessor


def test_multi_action_rule_sets_category_and_property(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    processor = FinancialDataProcessor(data_dir=data_dir)

    rule = RuleCreate(
        name="Coventry HOA",
        criteria_field="memo",
        criteria_match_type="contains",
        criteria_value="coventry",
        action_type="multi",
        action_value=[
            {"type": "set_property", "value": "966 Kinsbury Court"},
            {"type": "set_category", "value": "hoa"},
        ],
        priority=50,
    )
    processor.rules_manager.add_rule(rule)

    raw_df = pd.DataFrame(
        [
            {
                "description": "HOA payment",
                "memo": "coventry HOA fee",
                "amount": 145.67,
                "payee": "Coventry HOA",
            }
        ]
    )

    cleaned = processor.clean_expense_data(raw_df)

    assert cleaned.loc[0, "category"] == "hoa"
    assert cleaned.loc[0, "property_name"] == "966 Kinsbury Court"
