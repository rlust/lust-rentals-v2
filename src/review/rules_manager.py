"""Manager for persistent automation rules."""
from __future__ import annotations

import sqlite3
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from src.utils.sqlite_migrations import Migration, apply_migrations
from src.api.models import RuleCreate, RuleUpdate, RuleResponse

_RULES_MIGRATIONS: List[Migration] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS categorization_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            criteria_field TEXT NOT NULL,
            criteria_match_type TEXT NOT NULL,
            criteria_value TEXT NOT NULL,
            action_type TEXT NOT NULL,
            action_value TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            priority INTEGER DEFAULT 10,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_rules_priority ON categorization_rules(priority DESC);
        """,
    )
]

@dataclass
class RulesManager:
    """Manages storage and retrieval of automation rules."""

    db_path: Path

    def __post_init__(self) -> None:
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        apply_migrations(self.db_path, _RULES_MIGRATIONS)

    def get_all_rules(self, active_only: bool = False) -> List[RuleResponse]:
        """Retrieve all rules, optionally filtering by active status."""
        query = "SELECT * FROM categorization_rules"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY priority DESC, id ASC"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query).fetchall()
            return [self._row_to_rule(row) for row in rows]

    def add_rule(self, rule: RuleCreate) -> RuleResponse:
        """Create a new rule."""
        query = """
            INSERT INTO categorization_rules 
            (name, criteria_field, criteria_match_type, criteria_value, action_type, action_value, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, (
                rule.name, rule.criteria_field, rule.criteria_match_type, 
                rule.criteria_value, rule.action_type, rule.action_value, rule.priority
            ))
            rule_id = cursor.lastrowid
            conn.commit()
            
            # Fetch back to return complete object
            row = conn.execute("SELECT * FROM categorization_rules WHERE id = ?", (rule_id,)).fetchone()
            # Since we used a fresh cursor for fetch, we need to set row_factory if we want dict access, 
            # or just construct manually. Let's rely on _row_to_rule which expects dict-like access.
            # Re-opening with row_factory for simplicity in this method context
            pass

        # Cleaner fetch
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM categorization_rules WHERE id = ?", (rule_id,)).fetchone()
            return self._row_to_rule(row)

    def update_rule(self, rule_id: int, update: RuleUpdate) -> Optional[RuleResponse]:
        """Update an existing rule."""
        # Build dynamic update query
        fields = update.dict(exclude_unset=True)
        if not fields:
            return self.get_rule(rule_id)

        set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
        values = list(fields.values())
        values.append(rule_id)

        query = f"UPDATE categorization_rules SET {set_clause} WHERE id = ?"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, values)
            conn.commit()
            if cursor.rowcount == 0:
                return None
            
        return self.get_rule(rule_id)

    def delete_rule(self, rule_id: int) -> bool:
        """Delete a rule."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM categorization_rules WHERE id = ?", (rule_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_rule(self, rule_id: int) -> Optional[RuleResponse]:
        """Get a single rule by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM categorization_rules WHERE id = ?", (rule_id,)).fetchone()
            if row:
                return self._row_to_rule(row)
        return None

    def evaluate_transaction(self, transaction: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Evaluate a transaction against all active rules.
        
        Returns:
            Tuple of (category, property_name, matched_rule_name)
        """
        rules = self.get_all_rules(active_only=True)
        
        for rule in rules:
            field_value = str(transaction.get(rule.criteria_field, "") or "").lower()
            criteria_value = rule.criteria_value.lower()
            match = False

            if rule.criteria_match_type == "contains":
                match = criteria_value in field_value
            elif rule.criteria_match_type == "starts_with":
                match = field_value.startswith(criteria_value)
            elif rule.criteria_match_type == "equals":
                match = field_value == criteria_value
            elif rule.criteria_match_type == "regex":
                try:
                    match = bool(re.search(rule.criteria_value, field_value, re.IGNORECASE))
                except re.error:
                    continue  # Skip invalid regex

            if match:
                if rule.action_type == "set_category":
                    return (rule.action_value, None, rule.name)
                elif rule.action_type == "set_property":
                    return (None, rule.action_value, rule.name)
        
        return (None, None, None)

    def _row_to_rule(self, row: sqlite3.Row) -> RuleResponse:
        return RuleResponse(
            id=row["id"],
            name=row["name"],
            criteria_field=row["criteria_field"],
            criteria_match_type=row["criteria_match_type"],
            criteria_value=row["criteria_value"],
            action_type=row["action_type"],
            action_value=row["action_value"],
            is_active=bool(row["is_active"]),
            priority=row["priority"]
        )
