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
