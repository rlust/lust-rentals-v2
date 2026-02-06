"""Pydantic models for API request/response schemas."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel


class BankProcessRequest(BaseModel):
    """Request payload for triggering bank transaction processing."""

    bank_file_path: Optional[str] = None
    year: Optional[int] = None


class BankProcessResponse(BaseModel):
    """Response summarizing processed bank feed statistics."""

    income_rows: int
    expense_rows: int
    unresolved_rows: int = 0


class ReportRequest(BaseModel):
    """Request payload controlling report generation."""

    year: Optional[int] = None
    save_outputs: bool = True


class IncomeOverrideRequest(BaseModel):
    """Request for updating income transaction property mapping."""

    property_name: str
    mapping_notes: Optional[str] = None


class ExpenseOverrideRequest(BaseModel):
    """Request for updating expense transaction categorization."""

    category: str
    property_name: Optional[str] = None


class BulkIncomeOverrideRequest(BaseModel):
    """Request for bulk income override operations."""

    overrides: List[Dict[str, Optional[str]]]  # [{"transaction_id": "...", "property_name": "...", "mapping_notes": "..."}]


class BulkExpenseOverrideRequest(BaseModel):
    """Request for bulk expense override operations."""

    overrides: List[Dict[str, Optional[str]]]  # [{"transaction_id": "...", "category": "...", "property_name": "..."}]


class RuleCreate(BaseModel):
    """Request to create a new automation rule."""
    name: str
    criteria_field: str  # 'description', 'memo', 'amount'
    criteria_match_type: str  # 'contains', 'starts_with', 'equals', 'regex'
    criteria_value: str
    action_type: str  # 'set_category', 'set_property'
    action_value: str
    priority: int = 10


class RuleUpdate(BaseModel):
    """Request to update an existing rule."""
    name: Optional[str] = None
    criteria_field: Optional[str] = None
    criteria_match_type: Optional[str] = None
    criteria_value: Optional[str] = None
    action_type: Optional[str] = None
    action_value: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


class RuleResponse(RuleCreate):
    """Response model for a rule."""
    id: int
    is_active: bool
