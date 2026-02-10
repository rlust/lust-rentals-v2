"""Data processing module for Lust Rentals LLC financial data."""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
from pandas import DataFrame

from src.review.manager import ReviewManager
from src.review.rules_manager import RulesManager
from src.utils.config import AppConfig, configure_logging, load_config
from src.utils.sqlite_migrations import Migration, apply_migrations
from src.utils.properties import normalize_property_column
from src.categorization.categorizer import EnhancedCategorizer


class FinancialDataProcessor:
    """Process financial data for Lust Rentals LLC."""

    def __init__(
        self,
        data_dir: Union[str, Path, None] = None,
        config: Optional[AppConfig] = None,
    ) -> None:
        """Initialize the processor with configuration-aware data directory paths."""

        self._config = config or load_config(str(data_dir) if data_dir is not None else None)
        configure_logging(self._config.log_level)
        self.logger = logging.getLogger(__name__)

        self.data_dir = self._config.data_dir
        self.raw_data_dir = self.data_dir / "raw"
        self.processed_data_dir = self.data_dir / "processed"
        self.reports_dir = self.data_dir / "reports"
        self.processed_db_path = self.processed_data_dir / "processed.db"

        # Create directories if they don't exist
        for directory in [self.raw_data_dir, self.processed_data_dir, self.reports_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        self.logger.info("Initialized FinancialDataProcessor", extra={"data_dir": str(self.data_dir)})
        apply_migrations(self.processed_db_path, _PROCESSED_MIGRATIONS)

        # Initialize rules manager
        self.rules_manager = RulesManager(self.data_dir / "overrides" / "rules.db")

        # Initialize enhanced categorizer with rules
        self.categorizer = EnhancedCategorizer(rule_evaluator=self.rules_manager)
        self.logger.info(f"Initialized categorizer with {self.categorizer.get_statistics()}")

    def load_income_data(self, file_path: Optional[Union[str, Path]] = None) -> DataFrame:
        """Load income data from a CSV or Excel file.

        Args:
            file_path: Path to the income data file. If None, looks in raw_data_dir.

        Returns:
            DataFrame containing income data
        """
        if file_path is None:
            # Look for common income file names
            for ext in ["xlsx", "xls", "csv"]:
                for prefix in ["income", "revenue", "sales"]:
                    path = self.raw_data_dir / f"{prefix}.{ext}"
                    if path.exists():
                        file_path = path
                        break

        if file_path is None or not Path(file_path).exists():
            raise FileNotFoundError(
                "Income file not found. Please provide a valid file path or place it in the raw data directory."
            )

        if str(file_path).endswith(('.xlsx', '.xls')):
            return pd.read_excel(file_path)
        return pd.read_csv(file_path)

    def load_expense_data(self, file_path: Optional[Union[str, Path]] = None) -> DataFrame:
        """Load expense data from a CSV or Excel file.

        Args:
            file_path: Path to the expense data file. If None, looks in raw_data_dir.

        Returns:
            DataFrame containing expense data
        """
        if file_path is None:
            # Look for common expense file names
            for ext in ["xlsx", "xls", "csv"]:
                for prefix in ["expense", "expenses", "costs"]:
                    path = self.raw_data_dir / f"{prefix}.{ext}"
                    if path.exists():
                        file_path = path
                        break

        if file_path is None or not Path(file_path).exists():
            raise FileNotFoundError(
                "Expense file not found. Please provide a valid file path or place it in the raw data directory."
            )

        if str(file_path).endswith(('.xlsx', '.xls')):
            return pd.read_excel(file_path)
        return pd.read_csv(file_path)

    def load_bank_transactions(self, file_path: Optional[Union[str, Path]] = None) -> DataFrame:
        """Load Park National Bank transaction export.

        Args:
            file_path: Optional explicit path to the transaction report. If None,
                searches common locations including raw data directory and ~/Downloads.

        Returns:
            Raw DataFrame of bank transactions.
        """

        candidate_paths: List[Path] = []

        if file_path is not None:
            candidate_paths.append(Path(file_path))
        else:
            # Prioritize curated raw data copies inside the project structure.
            for ext in ["csv", "xlsx", "xls"]:
                for prefix in ["transaction_report", "bank_transactions", "transaction_report-3"]:
                    candidate_paths.append(self.raw_data_dir / f"{prefix}.{ext}")

            # Fall back to the user's Downloads directory for freshly exported files.
            downloads_dir = Path.home() / "Downloads"
            candidate_paths.append(downloads_dir / "transaction_report-3.csv")

        target = next((path for path in candidate_paths if path.exists()), None)

        if target is None:
            raise FileNotFoundError(
                "Bank transaction report not found. Place the export in data/raw or provide an explicit path."
            )

        if target.suffix.lower() in {".xlsx", ".xls"}:
            return pd.read_excel(target)
        self.logger.debug("Loaded bank transactions", extra={"path": str(target)})
        return pd.read_csv(target)

    def load_deposit_mapping(self, file_path: Optional[Union[str, Path]] = None) -> DataFrame:
        """Load memo-to-property deposit mapping file."""

        candidate_paths: List[Path] = []

        if file_path is not None:
            candidate_paths.append(Path(file_path))
        else:
            candidate_paths.extend(
                [
                    self.raw_data_dir / "deposit_amount_map.csv",
                    self.raw_data_dir / "deposit_mapping.csv",
                    self.data_dir / "docs" / "deposit_amount_map.csv",
                ]
            )
            downloads_dir = Path.home() / "Downloads"
            candidate_paths.append(downloads_dir / "deposit_amount_map.csv")

        target = next((path for path in candidate_paths if path.exists()), None)

        if target is None:
            raise FileNotFoundError(
                "Deposit mapping file not found. Place deposit_amount_map.csv in data/raw, docs, or provide path."
            )

        if target.suffix.lower() in {".xlsx", ".xls"}:
            mapping_df = pd.read_excel(target)
        else:
            mapping_df = pd.read_csv(target)

        mapping_df = mapping_df.copy()
        mapping_df.columns = mapping_df.columns.str.strip().str.lower().str.replace(" ", "_")

        required_columns = {"memo", "credit_amount", "prop_name"}
        missing = required_columns.difference(mapping_df.columns)
        if missing:
            raise ValueError(
                "Deposit mapping missing required columns: " + ", ".join(sorted(missing))
            )

        mapping_df["credit_amount"] = (
            pd.to_numeric(mapping_df["credit_amount"], errors="coerce").fillna(0).astype(float)
        )

        if "notes" not in mapping_df.columns:
            mapping_df["notes"] = pd.NA

        return mapping_df

    def clean_income_data(self, df: DataFrame) -> DataFrame:
        """Clean and standardize income data."""
        # Make a copy to avoid SettingWithCopyWarning
        df = df.copy()

        # Standardize column names (case insensitive)
        df.columns = df.columns.str.lower().str.replace(" ", "_")

        # Convert date columns to datetime
        date_columns = [col for col in df.columns if 'date' in col]
        for col in date_columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

        # Ensure amount is numeric
        if 'amount' in df.columns:
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce')

        # Drop rows with no amount
        df = df.dropna(subset=['amount'])

        # Ensure property_name column exists
        if 'property_name' not in df.columns:
            df['property_name'] = pd.NA
        df['property_name'] = df['property_name'].astype('object')

        if 'mapping_notes' not in df.columns:
            df['mapping_notes'] = pd.NA

        # Apply Automation Rules (Property Assignment)
        if self.rules_manager:
            for idx, row in df.iterrows():
                # Skip if already assigned (e.g. via deposit mapping)
                if pd.notna(row.get('property_name')) and row.get('property_name') != 'UNASSIGNED':
                    continue

                tx_data = {
                    "description": row.get('description', ''),
                    "memo": row.get('memo', ''),
                    "amount": str(row.get('amount', 0.0)),
                    "payee": row.get('payee', '')
                }
                actions, rule_name = self.rules_manager.evaluate_transaction(tx_data)
                applied = False

                for action in actions:
                    action_type = action.get("type")
                    action_value = action.get("value")
                    if action_type == "set_property" and action_value:
                        df.at[idx, 'property_name'] = action_value
                        applied = True
                    elif action_type == "set_category" and action_value and 'category' in df.columns:
                        df.at[idx, 'category'] = action_value
                        applied = True

                if applied:
                    # Initialize mapping_status if missing
                    if 'mapping_status' not in df.columns:
                        df['mapping_status'] = 'mapping_missing'
                    df.at[idx, 'mapping_status'] = 'rule_applied'
                    df.at[idx, 'mapping_notes'] = f"Rule: {rule_name}"

        return df

    def clean_expense_data(self, df: DataFrame) -> DataFrame:
        """Clean and standardize expense data.

        Args:
            df: Raw expense data

        Returns:
            Cleaned expense data
        """
        # Make a copy to avoid SettingWithCopyWarning
        df = df.copy()

        # Standardize column names (case insensitive)
        df.columns = df.columns.str.lower().str.replace(" ", "_")

        # Convert date columns to datetime
        date_columns = [col for col in df.columns if 'date' in col]
        for col in date_columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

        # Ensure amount is numeric and positive (expenses are typically positive in raw data)
        if 'amount' in df.columns:
            df['amount'] = abs(pd.to_numeric(df['amount'], errors='coerce'))

        # Drop rows with no amount
        df = df.dropna(subset=['amount'])

        # Categorize expenses using enhanced categorization
        if 'category' not in df.columns and 'description' in df.columns:
            # Use enhanced categorization with confidence scoring
            categorization_results = df.apply(
                lambda row: self._categorize_expense(
                    description=row.get('description', ''),
                    amount=row.get('amount', 0.0),
                    payee=row.get('payee', ''),
                    memo=row.get('memo', '')
                ),
                axis=1
            )

            # Extract category, confidence, and match_reason from results
            df[['category', 'confidence', 'match_reason']] = pd.DataFrame(
                categorization_results.tolist(),
                index=df.index
            )

        # Add confidence columns if they don't exist (for already categorized data)
        if 'confidence' not in df.columns:
            df['confidence'] = 1.0  # Assume high confidence for pre-categorized data
        if 'match_reason' not in df.columns:
            df['match_reason'] = 'Pre-categorized'

        if 'property_name' not in df.columns:
            df['property_name'] = pd.NA
        df['property_name'] = df['property_name'].astype('object')

        # Apply Automation Rules (Property Assignment)
        if self.rules_manager:
            for idx, row in df.iterrows():
                if pd.notna(row.get('property_name')) and row.get('property_name') != 'UNASSIGNED':
                    continue

                tx_data = {
                    "description": row.get('description', ''),
                    "memo": row.get('memo', ''),
                    "amount": str(row.get('amount', 0.0)),
                    "payee": row.get('payee', '')
                }
                actions, _ = self.rules_manager.evaluate_transaction(tx_data)
                for action in actions:
                    action_type = action.get("type")
                    action_value = action.get("value")
                    if action_type == "set_property" and action_value:
                        df.at[idx, 'property_name'] = action_value
                    elif action_type == "set_category" and action_value and 'category' in df.columns:
                        df.at[idx, 'category'] = action_value

        return df

    def _categorize_expense(
        self,
        description: str,
        amount: float = 0.0,
        payee: str = "",
        memo: str = ""
    ) -> Tuple[str, float, str]:
        """
        Categorize an expense using enhanced categorization engine.

        Args:
            description: Transaction description
            amount: Transaction amount (optional)
            payee: Payee name (optional)
            memo: Transaction memo (optional)

        Returns:
            Tuple of (category, confidence, match_reason)
        """
        return self.categorizer.categorize(description, amount, payee, memo)

    @staticmethod
    def _normalize_column_name(column: str) -> str:
        """Normalize column names to snake_case alphanumeric tokens."""

        return (
            column.strip()
            .lower()
            .replace(" ", "_")
            .replace("/", "_")
            .replace("-", "_")
        )

    @staticmethod
    def _classify_transaction(row: pd.Series) -> str:
        """Determine whether a transaction represents income or expense."""

        credit = row.get("credit_amount", 0) or 0
        debit = row.get("debit_amount", 0) or 0

        if credit > 0 and debit == 0:
            return "income"
        if debit > 0 and credit == 0:
            return "expense"
        if credit == 0 and debit == 0:
            return "neutral"
        return "mixed"

    @staticmethod
    def _derive_amount(row: pd.Series) -> float:
        """Extract a positive amount value aligned with the transaction classification."""

        transaction_type = row.get("transaction_type")
        credit = row.get("credit_amount", 0) or 0
        debit = row.get("debit_amount", 0) or 0

        if transaction_type == "income":
            return abs(float(credit))
        if transaction_type == "expense":
            return abs(float(debit))
        return 0.0

    @staticmethod
    def _normalize_memo(value: Union[str, float, int, None]) -> str:
        """Produce a comparison-friendly memo key."""

        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        return str(value).strip().lower()

    def _prepare_bank_dataframe(self, df: DataFrame) -> DataFrame:
        """Normalize Park National Bank transactions for downstream processing."""

        normalized = df.copy()
        normalized.columns = [self._normalize_column_name(col) for col in normalized.columns]

        required_columns = {"date", "credit_amount", "debit_amount"}
        missing = required_columns.difference(normalized.columns)
        if missing:
            raise ValueError(f"Bank report missing required columns: {', '.join(sorted(missing))}")

        # Ensure schema completeness by adding missing optional columns
        optional_columns = ["account_number", "account_name", "code", "reference", "memo", "description"]
        for col in optional_columns:
            if col not in normalized.columns:
                normalized[col] = pd.NA

        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
        normalized = normalized.dropna(subset=["date"])

        normalized = normalized.reset_index(drop=True)

        for amount_column in ["credit_amount", "debit_amount"]:
            normalized[amount_column] = (
                pd.to_numeric(normalized[amount_column], errors="coerce")
                .fillna(0)
                .astype(float)
            )

        normalized["credit_amount"] = normalized["credit_amount"].abs()
        normalized["debit_amount"] = normalized["debit_amount"].abs()

        normalized["transaction_type"] = normalized.apply(self._classify_transaction, axis=1)
        normalized["amount"] = normalized.apply(self._derive_amount, axis=1)
        normalized["transaction_id"] = normalized.apply(
            lambda row: f"{row['date'].strftime('%Y%m%d')}_{row.name:05d}_{row['transaction_type']}",
            axis=1,
        )

        return normalized

    def _apply_deposit_mapping(
        self, income_df: DataFrame, mapping_df: DataFrame
    ) -> Tuple[DataFrame, DataFrame]:
        """Attach property metadata to income entries using deposit mapping."""

        if "memo" not in income_df.columns:
            raise ValueError("Income data missing 'memo' column required for mapping.")

        income = income_df.copy()
        income["memo_key"] = income["memo"].apply(self._normalize_memo)
        income["amount_rounded"] = income["amount"].round(2)

        mapping = mapping_df.copy()
        mapping["memo_key"] = mapping["memo"].apply(self._normalize_memo)
        mapping["credit_amount_rounded"] = mapping["credit_amount"].round(2)

        merged = income.merge(
            mapping[["memo_key", "credit_amount_rounded", "prop_name", "notes"]],
            how="left",
            left_on=["memo_key", "amount_rounded"],
            right_on=["memo_key", "credit_amount_rounded"],
        )

        merged["property_name"] = merged["prop_name"]
        merged["mapping_notes"] = merged["notes"]
        merged["mapping_status"] = "mapped"

        no_match_mask = merged["property_name"].isna()
        merged.loc[no_match_mask, "mapping_status"] = "mapping_missing"

        manual_mask = merged["property_name"].fillna("").str.strip().str.upper() == "UNASSIGNED"
        merged.loc[manual_mask, "mapping_status"] = "manual_review"

        review_df = merged[merged["mapping_status"] != "mapped"].copy()

        merged = merged.drop(
            columns=[
                "memo_key",
                "amount_rounded",
                "credit_amount_rounded",
                "prop_name",
                "notes",
            ]
        )

        return merged, review_df

    def _split_bank_transactions(self, df: DataFrame) -> Tuple[DataFrame, DataFrame, DataFrame]:
        """Segment normalized bank transactions into income, expenses, and unresolved buckets."""

        income_df = df[df["transaction_type"] == "income"].copy()
        expense_df = df[df["transaction_type"] == "expense"].copy()
        unresolved_df = df[df["transaction_type"].isin(["mixed", "neutral"])].copy()

        return income_df, expense_df, unresolved_df

    def process_bank_transactions(
        self,
        file_path: Optional[Union[str, Path]] = None,
        year: Optional[int] = None,
    ) -> Dict[str, DataFrame]:
        """Process bank feed into cleaned income and expense datasets."""

        raw_df = self.load_bank_transactions(file_path)
        normalized_df = self._prepare_bank_dataframe(raw_df)

        if year is not None:
            normalized_df = normalized_df[normalized_df["date"].dt.year == year]
            self.logger.debug("Filtered bank transactions by year", extra={"year": year, "rows": len(normalized_df)})

        # Persist normalized snapshot for traceability
        normalized_df.to_csv(self.processed_data_dir / "bank_transactions_normalized.csv", index=False)
        self.logger.info(
            "Persisted normalized bank transactions",
            extra={"rows": len(normalized_df), "path": str(self.processed_data_dir / "bank_transactions_normalized.csv")},
        )

        income_df, expense_df, unresolved_df = self._split_bank_transactions(normalized_df)

        mapping_df: Optional[DataFrame] = None
        try:
            mapping_df = self.load_deposit_mapping()
        except FileNotFoundError:
            mapping_df = None

        mapped_income = income_df
        review_df: Optional[DataFrame] = None

        if mapping_df is not None and not income_df.empty:
            mapped_income, review_df = self._apply_deposit_mapping(income_df, mapping_df)
            if review_df is not None and not review_df.empty:
                review_path = self.processed_data_dir / "income_mapping_review.csv"
                review_df.to_csv(review_path, index=False)
                self.logger.warning(
                    "Income mapping review required",
                    extra={"rows": len(review_df), "path": str(review_path)},
                )
            else:
                self.logger.info("All income transactions mapped to properties")

        results: Dict[str, DataFrame] = {}

        if not unresolved_df.empty:
            unresolved_path = self.processed_data_dir / "unresolved_bank_transactions.csv"
            unresolved_df.to_csv(unresolved_path, index=False)
            results["unresolved"] = unresolved_df
            self.logger.warning(
                "Unresolved bank transactions detected",
                extra={"rows": len(unresolved_df), "path": str(unresolved_path)},
            )

        review_manager = ReviewManager(self.data_dir)

        cleaned_income = self.clean_income_data(mapped_income)
        cleaned_expenses = self.clean_expense_data(expense_df)

        cleaned_income = review_manager.apply_income_overrides(cleaned_income)
        cleaned_expenses = review_manager.apply_expense_overrides(cleaned_expenses)

        cleaned_income.to_csv(self.processed_data_dir / "processed_income.csv", index=False)
        cleaned_expenses.to_csv(self.processed_data_dir / "processed_expenses.csv", index=False)

        # Fix for potential missing column if no overrides/mappings applied
        if "mapping_status" not in cleaned_income.columns:
            cleaned_income["mapping_status"] = "mapping_missing"

        income_review_df = cleaned_income[~cleaned_income["mapping_status"].isin(["mapped", "overridden"])].copy()
        if not income_review_df.empty:
            income_review_path = self.processed_data_dir / "income_mapping_review.csv"
            income_review_df.to_csv(income_review_path, index=False)
            results["income_review"] = income_review_df
        elif (self.processed_data_dir / "income_mapping_review.csv").exists():
            (self.processed_data_dir / "income_mapping_review.csv").unlink()

        expense_review_df = cleaned_expenses[
            cleaned_expenses["category"].fillna("").str.lower().isin(["", "other", "uncategorized"])
            & (cleaned_expenses.get("category_status", "original") != "overridden")
        ].copy()
        if not expense_review_df.empty:
            expense_review_path = self.processed_data_dir / "expense_category_review.csv"
            expense_review_df.to_csv(expense_review_path, index=False)
            results["expense_review"] = expense_review_df
        elif (self.processed_data_dir / "expense_category_review.csv").exists():
            (self.processed_data_dir / "expense_category_review.csv").unlink()

        results.update({"income": cleaned_income, "expenses": cleaned_expenses})
        self.logger.info(
            "Processed financial datasets",
            extra={
                "income_rows": len(cleaned_income),
                "expense_rows": len(cleaned_expenses),
                "year": year,
            },
        )

        self._persist_processed_tables(cleaned_income, cleaned_expenses)
        return results

    def _persist_processed_tables(self, income_df: DataFrame, expense_df: DataFrame) -> None:
        """Persist processed datasets into the local SQLite warehouse."""

        if income_df.empty and expense_df.empty:
            return

        # Add metadata columns required by the API
        from datetime import datetime
        now = datetime.utcnow().isoformat()
        
        for df in [income_df, expense_df]:
            if not df.empty:
                # Add columns if they don't exist
                for col in ['created_at', 'updated_at']:
                    if col not in df.columns:
                        df[col] = now
                if 'modified_by' not in df.columns:
                    df['modified_by'] = 'system'

        with sqlite3.connect(self.processed_db_path) as conn:
            income_df.to_sql("processed_income", conn, if_exists="replace", index=False)
            expense_df.to_sql("processed_expenses", conn, if_exists="replace", index=False)

            # Create indexes for efficient joins and filtering
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_income_transaction_id ON processed_income(transaction_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_income_date ON processed_income(date DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_income_property ON processed_income(property_name)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_expenses_transaction_id ON processed_expenses(transaction_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_expenses_date ON processed_expenses(date DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_expenses_category ON processed_expenses(category)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_expenses_property ON processed_expenses(property_name)"
            )

            conn.execute(
                "DELETE FROM export_audit WHERE table_name IN (?, ?)",
                ("processed_income", "processed_expenses"),
            )
            conn.executemany(
                "INSERT INTO export_audit (table_name, row_count) VALUES (?, ?)",
                [
                    ("processed_income", len(income_df)),
                    ("processed_expenses", len(expense_df)),
                ],
            )
        self.logger.debug(
            "Persisted processed datasets to SQLite",
            extra={"database": str(self.processed_db_path)},
        )

    def process_financials(
        self,
        year: Optional[int] = None,
        bank_file_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, DataFrame]:
        """Process financial data, preferring the Park National bank feed when available."""

        try:
            return self.process_bank_transactions(file_path=bank_file_path, year=year)
        except FileNotFoundError as bank_missing:
            # Fallback to legacy separate income/expense files if bank report not present
            try:
                income_df = self.load_income_data()
                expense_df = self.load_expense_data()

                income_df = self.clean_income_data(income_df)
                expense_df = self.clean_expense_data(expense_df)

                if year is not None:
                    income_date_col = next((col for col in income_df.columns if "date" in col), None)
                    expense_date_col = next((col for col in expense_df.columns if "date" in col), None)

                    if income_date_col:
                        income_df = income_df[income_df[income_date_col].dt.year == year]
                    if expense_date_col:
                        expense_df = expense_df[expense_df[expense_date_col].dt.year == year]

                income_df.to_csv(self.processed_data_dir / "processed_income.csv", index=False)
                expense_df.to_csv(self.processed_data_dir / "processed_expenses.csv", index=False)

                return {"income": income_df, "expenses": expense_df}
            except FileNotFoundError:
                raise bank_missing

    def load_processed_data(self, year: Optional[int] = None) -> Dict[str, DataFrame]:
        """Load processed income and expense data from SQLite, with manual overrides applied."""
        if not self.processed_db_path.exists():
            raise FileNotFoundError("Processed database not found.")

        from src.data_processing.review_manager import ReviewManager

        review_manager = ReviewManager()

        try:
            with sqlite3.connect(self.processed_db_path) as conn:
                income_df = pd.read_sql_query("SELECT * FROM processed_income", conn)
                expense_df = pd.read_sql_query("SELECT * FROM processed_expenses", conn)
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc):
                raise FileNotFoundError("Processed database missing required tables.") from exc
            raise

        income_df = review_manager.apply_income_overrides(income_df)
        expense_df = review_manager.apply_expense_overrides(expense_df)

        if not income_df.empty:
            income_df['amount'] = pd.to_numeric(income_df['amount'], errors='coerce').fillna(0.0)
        if not expense_df.empty:
            expense_df['amount'] = pd.to_numeric(expense_df['amount'], errors='coerce').fillna(0.0)

        income_df = normalize_property_column(income_df)
        expense_df = normalize_property_column(expense_df)

        if year is not None:
            income_df = self._filter_dataframe_by_year(income_df, year)
            expense_df = self._filter_dataframe_by_year(expense_df, year)

        if income_df.empty and expense_df.empty:
            raise FileNotFoundError("No processed data found in database.")

        return {"income": income_df, "expenses": expense_df}

    def _filter_dataframe_by_year(self, df: DataFrame, year: int) -> DataFrame:
        """Filter a DataFrame to a specific year using the first date-like column."""
        date_col = next((col for col in df.columns if "date" in col.lower()), None)
        if not date_col:
            return df

        filtered = df.copy()
        filtered[date_col] = pd.to_datetime(filtered[date_col], errors="coerce")
        return filtered[filtered[date_col].dt.year == year]
_PROCESSED_MIGRATIONS: List[Migration] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS export_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            exported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """,
    ),
    (
        2,
        """
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_name TEXT NOT NULL UNIQUE,
            property_type TEXT NOT NULL DEFAULT 'rental',
            address TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT DEFAULT 'system'
        );

        CREATE INDEX IF NOT EXISTS idx_properties_active
            ON properties(is_active);

        CREATE INDEX IF NOT EXISTS idx_properties_type
            ON properties(property_type);

        -- Insert default properties including Lust Rentals LLC
        INSERT INTO properties (property_name, property_type, address, sort_order)
        VALUES
            ('Lust Rentals LLC', 'business_entity', NULL, 0),
            ('118 W Shields St', 'rental', '118 W Shields St', 1),
            ('41 26th St', 'rental', '41 26th St', 2),
            ('966 Kinsbury Court', 'rental', '966 Kinsbury Court', 3)
        ON CONFLICT(property_name) DO NOTHING;
        """,
    ),
]
