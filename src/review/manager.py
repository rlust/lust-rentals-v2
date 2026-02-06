"""Utilities for managing manual review overrides for income and expenses."""
from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import pandas as pd
from pandas import DataFrame

from src.utils.sqlite_migrations import Migration, apply_migrations


@dataclass
class ReviewManager:
    """Handle storage and application of manual overrides."""

    data_dir: Path
    overrides_dir: Path = field(init=False)
    overrides_db_path: Path = field(init=False)
    processed_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.overrides_dir = self.data_dir / "overrides"
        self.overrides_dir.mkdir(parents=True, exist_ok=True)
        self.overrides_db_path = self.overrides_dir / "overrides.db"
        self.processed_dir = self.data_dir / "processed"
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        apply_migrations(self.overrides_db_path, _OVERRIDE_MIGRATIONS)

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------
    def load_income_overrides(self) -> DataFrame:
        with sqlite3.connect(self.overrides_db_path) as conn:
            return pd.read_sql_query("SELECT * FROM income_overrides", conn)

    def load_expense_overrides(self) -> DataFrame:
        with sqlite3.connect(self.overrides_db_path) as conn:
            df = pd.read_sql_query("SELECT * FROM expense_overrides", conn)
        if "property_name" not in df.columns:
            df["property_name"] = pd.NA
        df["property_name"] = df["property_name"].astype("object")
        return df

    def _load_optional_csv(self, path: Path) -> DataFrame:
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    def load_income_review_items(self) -> DataFrame:
        return self._load_optional_csv(self.processed_dir / "income_mapping_review.csv")

    def load_expense_review_items(self) -> DataFrame:
        return self._load_optional_csv(self.processed_dir / "expense_category_review.csv")

    # ------------------------------------------------------------------
    # Application helpers
    # ------------------------------------------------------------------
    def apply_income_overrides(self, income_df: DataFrame) -> DataFrame:
        overrides = self.load_income_overrides()
        if overrides.empty or income_df.empty:
            return income_df

        merged = income_df.merge(overrides, on="transaction_id", how="left", suffixes=("", "_override"))

        override_mask = merged["property_name_override"].notna()

        merged.loc[override_mask, "property_name"] = merged.loc[override_mask, "property_name_override"]
        merged.loc[override_mask, "mapping_notes"] = merged.loc[override_mask, "mapping_notes_override"]
        merged.loc[override_mask, "mapping_status"] = "overridden"

        merged = merged.drop(columns=["property_name_override", "mapping_notes_override"])
        return merged

    def apply_expense_overrides(self, expense_df: DataFrame) -> DataFrame:
        overrides = self.load_expense_overrides()
        if overrides.empty or expense_df.empty:
            if "category_status" not in expense_df.columns:
                expense_df["category_status"] = "original"
            if "property_name" not in expense_df.columns:
                expense_df["property_name"] = pd.NA
            return expense_df

        merged = expense_df.merge(overrides, on="transaction_id", how="left", suffixes=("", "_override"))
        if "category_status" not in merged.columns:
            merged["category_status"] = "original"
        if "property_name" not in merged.columns:
            merged["property_name"] = pd.NA

        category_override_mask = merged["category_override"].notna()
        property_override_mask = merged["property_name_override"].notna()

        merged.loc[category_override_mask, "category"] = merged.loc[category_override_mask, "category_override"]
        merged.loc[property_override_mask, "property_name"] = merged.loc[property_override_mask, "property_name_override"]
        merged.loc[category_override_mask | property_override_mask, "category_status"] = "overridden"

        merged = merged.drop(columns=[col for col in ["category_override", "property_name_override"] if col in merged.columns])
        return merged

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _drop_review_entry(self, path: Path, transaction_id: str) -> None:
        if not path.exists():
            return
        df = pd.read_csv(path)
        df = df[df["transaction_id"] != transaction_id]
        if df.empty:
            path.unlink()
        else:
            df.to_csv(path, index=False)

    def _update_processed_income(self, transaction_id: str, property_name: str, mapping_notes: str | None) -> None:
        path = self.processed_dir / "processed_income.csv"
        if not path.exists():
            return
        df = pd.read_csv(path)
        mask = df["transaction_id"] == transaction_id
        if not mask.any():
            return
        df.loc[mask, "property_name"] = property_name
        df.loc[mask, "mapping_notes"] = mapping_notes
        df.loc[mask, "mapping_status"] = "overridden"
        df.to_csv(path, index=False)

    def _update_processed_expense(self, transaction_id: str, category: str, property_name: Optional[str]) -> None:
        path = self.processed_dir / "processed_expenses.csv"
        if not path.exists():
            return
        df = pd.read_csv(path)
        mask = df["transaction_id"] == transaction_id
        if not mask.any():
            return
        df.loc[mask, "category"] = category
        if "category_status" not in df.columns:
            df["category_status"] = "original"
        df.loc[mask, "category_status"] = "overridden"
        if "property_name" not in df.columns:
            df["property_name"] = pd.NA
        df["property_name"] = df["property_name"].astype("object")
        if property_name is not None:
            df.loc[mask, "property_name"] = property_name
        df.to_csv(path, index=False)

    def record_income_override(
        self,
        transaction_id: str,
        property_name: str,
        mapping_notes: str | None = None,
        modified_by: str = "web_user"
    ) -> None:
        """
        Record income property assignment override with audit trail.

        Args:
            transaction_id: Transaction identifier
            property_name: Property to assign
            mapping_notes: Optional notes about the mapping
            modified_by: User or system that made the change
        """
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.overrides_db_path) as conn:
            # Check if override exists
            cursor = conn.cursor()
            cursor.execute(
                "SELECT property_name, mapping_notes FROM income_overrides WHERE transaction_id = ?",
                (transaction_id,)
            )
            existing = cursor.fetchone()

            if existing:
                # Log history for changes
                old_property, old_notes = existing
                if old_property != property_name:
                    cursor.execute(
                        """
                        INSERT INTO override_history
                        (transaction_id, override_type, field_name, old_value, new_value, modified_by, modified_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (transaction_id, 'income', 'property_name', old_property, property_name, modified_by, now)
                    )
                if old_notes != mapping_notes:
                    cursor.execute(
                        """
                        INSERT INTO override_history
                        (transaction_id, override_type, field_name, old_value, new_value, modified_by, modified_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (transaction_id, 'income', 'mapping_notes', old_notes, mapping_notes, modified_by, now)
                    )

                # Update existing override
                cursor.execute(
                    """
                    UPDATE income_overrides
                    SET property_name = ?, mapping_notes = ?, updated_at = ?, modified_by = ?
                    WHERE transaction_id = ?
                    """,
                    (property_name, mapping_notes, now, modified_by, transaction_id)
                )
            else:
                # Insert new override
                cursor.execute(
                    """
                    INSERT INTO income_overrides
                    (transaction_id, property_name, mapping_notes, created_at, updated_at, modified_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (transaction_id, property_name, mapping_notes, now, now, modified_by)
                )

                # Log creation in history
                cursor.execute(
                    """
                    INSERT INTO override_history
                    (transaction_id, override_type, field_name, old_value, new_value, modified_by, modified_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (transaction_id, 'income', 'property_name', None, property_name, modified_by, now)
                )

            conn.commit()

        self._update_processed_income(transaction_id, property_name, mapping_notes)
        self._drop_review_entry(self.processed_dir / "income_mapping_review.csv", transaction_id)

    def record_expense_override(
        self,
        transaction_id: str,
        category: str,
        property_name: Optional[str],
        modified_by: str = "web_user"
    ) -> None:
        """
        Record expense category override with audit trail.

        Args:
            transaction_id: Transaction identifier
            category: Expense category to assign
            property_name: Optional property association
            modified_by: User or system that made the change
        """
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.overrides_db_path) as conn:
            # Check if override exists
            cursor = conn.cursor()
            cursor.execute(
                "SELECT category, property_name FROM expense_overrides WHERE transaction_id = ?",
                (transaction_id,)
            )
            existing = cursor.fetchone()

            if existing:
                # Log history for changes
                old_category, old_property = existing
                if old_category != category:
                    cursor.execute(
                        """
                        INSERT INTO override_history
                        (transaction_id, override_type, field_name, old_value, new_value, modified_by, modified_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (transaction_id, 'expense', 'category', old_category, category, modified_by, now)
                    )
                if old_property != property_name:
                    cursor.execute(
                        """
                        INSERT INTO override_history
                        (transaction_id, override_type, field_name, old_value, new_value, modified_by, modified_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (transaction_id, 'expense', 'property_name', old_property, property_name, modified_by, now)
                    )

                # Update existing override
                cursor.execute(
                    """
                    UPDATE expense_overrides
                    SET category = ?, property_name = ?, updated_at = ?, modified_by = ?
                    WHERE transaction_id = ?
                    """,
                    (category, property_name, now, modified_by, transaction_id)
                )
            else:
                # Insert new override
                cursor.execute(
                    """
                    INSERT INTO expense_overrides
                    (transaction_id, category, property_name, created_at, updated_at, modified_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (transaction_id, category, property_name, now, now, modified_by)
                )

                # Log creation in history
                cursor.execute(
                    """
                    INSERT INTO override_history
                    (transaction_id, override_type, field_name, old_value, new_value, modified_by, modified_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (transaction_id, 'expense', 'category', None, category, modified_by, now)
                )

            conn.commit()

        self._update_processed_expense(transaction_id, category, property_name)
        self._drop_review_entry(self.processed_dir / "expense_category_review.csv", transaction_id)

    # ------------------------------------------------------------------
    # Metadata helpers
    # ------------------------------------------------------------------
    def property_options(self) -> List[str]:
        path = self.processed_dir / "processed_income.csv"
        properties_set = {"Lust Rentals LLC"}  # Always include entity property

        if path.exists():
            df = pd.read_csv(path)
            if "property_name" in df.columns:
                existing_properties = (
                    df["property_name"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().unique()
                )
                properties_set.update(existing_properties.tolist())

        return sorted(properties_set)

    def expense_category_options(self) -> List[str]:
        processed_categories: List[str] = []
        path = self.processed_dir / "processed_expenses.csv"
        if path.exists():
            df = pd.read_csv(path)
            if "category" in df.columns:
                processed_categories = (
                    df["category"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist()
                )

        defaults = _load_default_expense_categories()
        combined = {str(category) for category in processed_categories}
        combined.update(defaults)

        return sorted(combined)


__all__ = ["ReviewManager"]


_OVERRIDE_MIGRATIONS: List[Migration] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS income_overrides (
            transaction_id TEXT PRIMARY KEY,
            property_name TEXT NOT NULL,
            mapping_notes TEXT
        );
        CREATE TABLE IF NOT EXISTS expense_overrides (
            transaction_id TEXT PRIMARY KEY,
            category TEXT NOT NULL
        );
        """,
    ),
    (
        2,
        """
        ALTER TABLE expense_overrides
            ADD COLUMN property_name TEXT;
        """,
    ),
    (
        3,
        """
        -- Add audit trail columns to income_overrides
        ALTER TABLE income_overrides ADD COLUMN created_at TEXT;
        ALTER TABLE income_overrides ADD COLUMN updated_at TEXT;
        ALTER TABLE income_overrides ADD COLUMN modified_by TEXT DEFAULT 'system';

        -- Add audit trail columns to expense_overrides
        ALTER TABLE expense_overrides ADD COLUMN created_at TEXT;
        ALTER TABLE expense_overrides ADD COLUMN updated_at TEXT;
        ALTER TABLE expense_overrides ADD COLUMN modified_by TEXT DEFAULT 'system';

        -- Create override history table for tracking all changes
        CREATE TABLE IF NOT EXISTS override_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT NOT NULL,
            override_type TEXT NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            modified_by TEXT NOT NULL,
            modified_at TEXT NOT NULL
        );

        -- Create indexes for efficient querying
        CREATE INDEX IF NOT EXISTS idx_override_history_transaction
            ON override_history(transaction_id);
        CREATE INDEX IF NOT EXISTS idx_override_history_modified_at
            ON override_history(modified_at DESC);
        """,
    ),
]


@lru_cache(maxsize=1)
def _load_default_expense_categories() -> List[str]:
    """Return distinct expense categories sourced from the expense code table."""

    categories: set[str] = set()
    tsv_path = Path(__file__).with_name("expense_code_categories.tsv")
    if not tsv_path.exists():
        return []

    with tsv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            value = row.get("Catagory") or row.get("Categorie") or row.get("category")
            if not value:
                continue
            normalized = value.strip()
            if normalized:
                categories.add(normalized)

    return sorted(categories)
