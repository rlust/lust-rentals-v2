"""Review routes for manual categorization of income and expense transactions."""
from __future__ import annotations

import logging
import sqlite3
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from src.api.dependencies import get_config, get_review_manager

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================

class IncomeOverrideRequest(BaseModel):
    """Request to override income transaction mapping."""
    property_name: str
    mapping_notes: Optional[str] = None


class ExpenseOverrideRequest(BaseModel):
    """Request to override expense transaction category."""
    category: str
    property_name: Optional[str] = None


class IncomeOverrideItem(BaseModel):
    """Bulk override item for income transactions."""
    transaction_id: str
    property_name: str
    mapping_notes: Optional[str] = None


class ExpenseOverrideItem(BaseModel):
    """Bulk override item for expense transactions."""
    transaction_id: str
    category: str
    property_name: Optional[str] = None


class BulkIncomeOverrideRequest(BaseModel):
    """Request to bulk update income mappings."""
    updates: List[IncomeOverrideItem]


class BulkExpenseOverrideRequest(BaseModel):
    """Request to bulk update expense categories."""
    updates: List[ExpenseOverrideItem]


class ExpenseUpdateRequest(BaseModel):
    """Request to update a full expense transaction."""
    transaction_id: str
    date: str
    description: str
    amount: float
    category: str
    property_name: Optional[str] = None
    memo: Optional[str] = None


class IncomeUpdateRequest(BaseModel):
    """Request to update a full income transaction."""
    transaction_id: str
    date: str
    description: str
    amount: float
    property_name: str
    memo: Optional[str] = None


class PaginatedResponse(BaseModel):
    """Paginated response with metadata."""
    data: List[dict]
    page: int
    limit: int
    total_count: int
    has_more: bool


# ============================================================================
# Review Endpoints
# ============================================================================

@router.get("/income")
def get_income_for_review(http_request: Request) -> list:
    """Get all income transactions pending review.

    Returns income transactions that need property assignment, sorted by date.
    Only returns unmapped or manually reviewed items.
    """
    db_path = get_config().data_dir / "processed" / "processed.db"

    if not db_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Database not found. Please process transactions first."
        )

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get income items needing review
            cursor.execute("""
                SELECT *
                FROM processed_income
                WHERE mapping_status IN ('mapping_missing', 'manual_review')
                   OR property_name IS NULL
                   OR property_name = 'UNASSIGNED'
                ORDER BY date DESC
            """)

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    except sqlite3.Error as e:
        logger.error(f"Database error fetching income for review: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.get("/expenses")
def get_expenses_for_review(http_request: Request) -> list:
    """Get all expense transactions pending review.

    Returns expense transactions that need category assignment, sorted by date.
    Prioritizes low-confidence and uncategorized items.
    """
    db_path = get_config().data_dir / "processed" / "processed.db"

    if not db_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Database not found. Please process transactions first."
        )

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            review_manager = get_review_manager()
            cursor.execute(f"ATTACH DATABASE '{review_manager.overrides_db_path}' AS overrides_db")

            # Get expense items needing review (low confidence or uncategorized, excluding overrides)
            cursor.execute("""
                SELECT
                    pe.*,
                    COALESCE(eo.category, pe.category) as category,
                    COALESCE(eo.property_name, pe.property_name) as property_name,
                    CASE
                        WHEN eo.transaction_id IS NOT NULL THEN 'overridden'
                        ELSE pe.category_status
                    END as category_status
                FROM processed_expenses pe
                LEFT JOIN overrides_db.expense_overrides eo ON pe.transaction_id = eo.transaction_id
                WHERE eo.transaction_id IS NULL
                  AND (
                    pe.confidence < 0.6
                    OR pe.category = 'other'
                    OR pe.category IS NULL
                  )
                ORDER BY pe.confidence ASC, pe.date DESC
            """)

            rows = cursor.fetchall()
            cursor.execute("DETACH DATABASE overrides_db")
            return [dict(row) for row in rows]

    except sqlite3.Error as e:
        logger.error(f"Database error fetching expenses for review: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.post("/income/{transaction_id}")
def update_income_override(
    http_request: Request,
    transaction_id: str,
    override: IncomeOverrideRequest
) -> dict:
    """Update property mapping for a single income transaction."""
    review_manager = get_review_manager()

    try:
        with sqlite3.connect(review_manager.overrides_db_path) as conn:
            cursor = conn.cursor()

            # Insert or update override
            cursor.execute("""
                INSERT INTO income_overrides (
                    transaction_id, property_name, mapping_notes,
                    created_at, updated_at, modified_by
                )
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'web_user')
                ON CONFLICT(transaction_id) DO UPDATE SET
                    property_name = excluded.property_name,
                    mapping_notes = excluded.mapping_notes,
                    updated_at = CURRENT_TIMESTAMP,
                    modified_by = 'web_user'
            """, (transaction_id, override.property_name, override.mapping_notes))

            conn.commit()

        logger.info(f"Updated income override for {transaction_id}: {override.property_name}")
        return {"status": "success", "transaction_id": transaction_id}

    except sqlite3.Error as e:
        logger.error(f"Error updating income override: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.post("/expenses/{transaction_id}")
def update_expense_override(
    http_request: Request,
    transaction_id: str,
    override: ExpenseOverrideRequest
) -> dict:
    """Update category for a single expense transaction."""
    review_manager = get_review_manager()

    try:
        with sqlite3.connect(review_manager.overrides_db_path) as conn:
            cursor = conn.cursor()

            # Insert or update override
            cursor.execute("""
                INSERT INTO expense_overrides (
                    transaction_id, category, property_name,
                    created_at, updated_at, modified_by
                )
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'web_user')
                ON CONFLICT(transaction_id) DO UPDATE SET
                    category = excluded.category,
                    property_name = excluded.property_name,
                    updated_at = CURRENT_TIMESTAMP,
                    modified_by = 'web_user'
            """, (transaction_id, override.category, override.property_name))

            conn.commit()

        logger.info(f"Updated expense override for {transaction_id}: {override.category}")
        return {"status": "success", "transaction_id": transaction_id}

    except sqlite3.Error as e:
        logger.error(f"Error updating expense override: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.post("/bulk/income")
def bulk_update_income_overrides(
    http_request: Request,
    request: BulkIncomeOverrideRequest
) -> dict:
    """Bulk update property mappings for multiple income transactions."""
    review_manager = get_review_manager()

    try:
        with sqlite3.connect(review_manager.overrides_db_path) as conn:
            cursor = conn.cursor()

            for idx, override in enumerate(request.updates, 1):
                try:
                    # Validate required fields
                    if not override.transaction_id or str(override.transaction_id).strip() == '':
                        error_msg = f"Missing transaction_id for bulk income update (item {idx}/{len(request.updates)})"
                        logger.error(f"Validation error in bulk income update (item {idx}/{len(request.updates)}): {error_msg}")
                        raise HTTPException(status_code=400, detail=f"Validation error: {error_msg}")
                    if not override.property_name or override.property_name.strip() == '':
                        error_msg = f"Transaction {override.transaction_id}: property_name is required"
                        logger.error(f"Validation error in bulk income update (item {idx}/{len(request.updates)}): {error_msg}")
                        raise HTTPException(status_code=400, detail=f"Validation error: {error_msg}")

                    logger.debug(
                        f"Updating income override {idx}/{len(request.updates)}: "
                        f"transaction_id={override.transaction_id}, property_name={override.property_name}"
                    )

                    cursor.execute("""
                        INSERT INTO income_overrides (
                            transaction_id, property_name, mapping_notes,
                            created_at, updated_at, modified_by
                        )
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'web_user')
                        ON CONFLICT(transaction_id) DO UPDATE SET
                            property_name = excluded.property_name,
                            mapping_notes = excluded.mapping_notes,
                            updated_at = CURRENT_TIMESTAMP,
                            modified_by = 'web_user'
                    """, (override.transaction_id, override.property_name, override.mapping_notes))

                except sqlite3.IntegrityError as e:
                    error_msg = f"Database constraint violation for {override.transaction_id}: {e}"
                    logger.error(f"IntegrityError in bulk income update (item {idx}/{len(request.updates)}): {error_msg}")
                    raise HTTPException(status_code=400, detail=error_msg)
                except Exception as e:
                    error_msg = f"Error processing transaction {override.transaction_id}: {e}"
                    logger.error(f"Error in bulk income update (item {idx}/{len(request.updates)}): {error_msg}")
                    raise

            conn.commit()

        logger.info(f"Bulk updated {len(request.updates)} income overrides")
        return {
            "status": "success",
            "updated_count": len(request.updates)
        }

    except sqlite3.Error as e:
        logger.error(f"Error in bulk income update: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.post("/bulk/expenses")
def bulk_update_expense_overrides(
    http_request: Request,
    request: BulkExpenseOverrideRequest
) -> dict:
    """Bulk update categories for multiple expense transactions."""
    review_manager = get_review_manager()

    try:
        with sqlite3.connect(review_manager.overrides_db_path) as conn:
            cursor = conn.cursor()

            for idx, override in enumerate(request.updates, 1):
                try:
                    # Validate required fields before database operation
                    if not override.transaction_id or str(override.transaction_id).strip() == '':
                        error_msg = f"Missing transaction_id for bulk expense update (item {idx}/{len(request.updates)})"
                        logger.error(f"Validation error in bulk expense update (item {idx}/{len(request.updates)}): {error_msg}")
                        raise HTTPException(status_code=400, detail=f"Validation error: {error_msg}")
                    if not override.category or override.category.strip() == '':
                        error_msg = f"Transaction {override.transaction_id}: category is required but was empty"
                        logger.error(f"Validation error in bulk expense update (item {idx}/{len(request.updates)}): {error_msg}")
                        raise HTTPException(status_code=400, detail=f"Validation error: {error_msg}")

                    logger.debug(
                        f"Updating expense override {idx}/{len(request.updates)}: "
                        f"transaction_id={override.transaction_id}, category={override.category}, "
                        f"property_name={override.property_name}"
                    )

                    cursor.execute("""
                        INSERT INTO expense_overrides (
                            transaction_id, category, property_name,
                            created_at, updated_at, modified_by
                        )
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'web_user')
                        ON CONFLICT(transaction_id) DO UPDATE SET
                            category = excluded.category,
                            property_name = excluded.property_name,
                            updated_at = CURRENT_TIMESTAMP,
                            modified_by = 'web_user'
                    """, (override.transaction_id, override.category, override.property_name))

                except sqlite3.IntegrityError as e:
                    error_msg = (
                        f"Database constraint violation for transaction {override.transaction_id}: {e}. "
                        f"Data: category={override.category}, property_name={override.property_name}"
                    )
                    logger.error(f"IntegrityError in bulk expense update (item {idx}/{len(request.updates)}): {error_msg}")
                    raise HTTPException(status_code=400, detail=error_msg)
                except Exception as e:
                    error_msg = f"Error processing transaction {override.transaction_id}: {e}"
                    logger.error(f"Error in bulk expense update (item {idx}/{len(request.updates)}): {error_msg}")
                    raise

            conn.commit()

        logger.info(f"Bulk updated {len(request.updates)} expense overrides")
        return {
            "status": "success",
            "updated_count": len(request.updates)
        }

    except sqlite3.Error as e:
        logger.error(f"Error in bulk expense update: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.get("/properties")
def get_available_properties(http_request: Request) -> list:
    """Get list of available properties for assignment.

    Returns properties from the properties table if available,
    with business entity (LLC) listed first, followed by rental properties.
    Falls back to hardcoded defaults if properties table doesn't exist.
    """
    db_path = get_config().data_dir / "processed" / "processed.db"

    if not db_path.exists():
        # Return hardcoded defaults as fallback
        return [
            "Lust Rentals LLC",
            "118 W Shields St",
            "41 26th St",
            "966 Kinsbury Court"
        ]

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Try to get from properties table first
            try:
                cursor.execute("""
                    SELECT property_name
                    FROM properties
                    WHERE is_active = 1
                    ORDER BY
                        CASE WHEN property_type = 'business_entity' THEN 0 ELSE 1 END,
                        sort_order ASC,
                        property_name ASC
                """)
                properties = [row[0] for row in cursor.fetchall()]

                if properties:
                    return properties

            except sqlite3.OperationalError:
                # Properties table doesn't exist yet, fall through to legacy logic
                logger.warning("Properties table not found, using fallback logic")
                pass

            # Fallback: Try to get from property_mapping table
            try:
                cursor.execute("""
                    SELECT DISTINCT property_name
                    FROM property_mapping
                    WHERE property_name IS NOT NULL
                    ORDER BY property_name
                """)
                properties = [row[0] for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                properties = []

            # If no properties in mapping table, get from processed_income table
            if not properties:
                cursor.execute("""
                    SELECT DISTINCT property_name
                    FROM processed_income
                    WHERE property_name IS NOT NULL
                      AND property_name != 'UNASSIGNED'
                      AND property_name != ''
                    ORDER BY property_name
                """)
                properties = [row[0] for row in cursor.fetchall()]

            # If still no properties, return defaults
            if not properties:
                properties = [
                    "Lust Rentals LLC",
                    "118 W Shields St",
                    "41 26th St",
                    "966 Kinsbury Court"
                ]

            return properties

    except sqlite3.Error as e:
        logger.error(f"Error fetching properties: {e}")
        # Return default properties on error
        return [
            "Lust Rentals LLC",
            "118 W Shields St",
            "41 26th St",
            "966 Kinsbury Court"
        ]


@router.get("/categories")
def get_available_categories(http_request: Request) -> list:
    """Get list of available expense categories.

    Returns all expense categories used in the system, matching the
    canonical categories from category_utils.py.
    """
    return [
        "advertising",
        "cleaning",
        "hoa",
        "insurance",
        "landscaping",
        "legal",
        "maintenance",
        "management_fees",
        "mortgage_interest",
        "pest_control",
        "repairs",
        "supplies",
        "taxes",
        "travel",
        "utilities",
        "other"
    ]


@router.get("/income/all")
def get_all_income(
    http_request: Request,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(0, ge=0, le=1000, description="Items per page (0 = all)"),
    search: Optional[str] = Query(None, description="Search in description/property"),
    property_filter: Optional[str] = Query(None, alias="property", description="Filter by property name")
) -> PaginatedResponse:
    """Get ALL income transactions (assigned and unassigned) with pagination.

    Returns income transactions sorted by date, for viewing and editing.
    Applies any manual overrides that have been saved.

    Pagination: Use page and limit parameters. Set limit=0 for all records (backward compatible).
    Search: Filter by description or property name.
    """
    db_path = get_config().data_dir / "processed" / "processed.db"
    review_manager = get_review_manager()
    rules_db_path = get_config().data_dir / "overrides" / "rules.db"

    if not db_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Database not found. Please process transactions first."
        )

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Attach the overrides database to access override data
            cursor.execute(f"ATTACH DATABASE '{review_manager.overrides_db_path}' AS overrides_db")
            cursor.execute(f"ATTACH DATABASE '{rules_db_path}' AS rules_db")

            # Build WHERE clause for filters
            where_conditions = []
            params = []

            if search:
                where_conditions.append(
                    "(pi.description LIKE ? OR COALESCE(io.property_name, pi.property_name) LIKE ?)"
                )
                search_term = f"%{search}%"
                params.extend([search_term, search_term])

            if property_filter:
                where_conditions.append("COALESCE(io.property_name, pi.property_name) = ?")
                params.append(property_filter)

            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

            cursor.execute(
                """
                SELECT name FROM rules_db.sqlite_master
                WHERE type='table' AND name='categorization_rules'
                """
            )
            has_rules_table = cursor.fetchone() is not None
            rules_join = "LEFT JOIN rules_db.categorization_rules cr ON io.transaction_id = cr.id" if has_rules_table else ""
            rule_name_select = (
                "CASE WHEN cr.action_type IS NOT NULL then cr.name ELSE '' END as rule_name"
                if has_rules_table
                else "'' as rule_name"
            )

            # Get total count
            count_query = f"""
                SELECT COUNT(*)
                FROM processed_income pi
                LEFT JOIN overrides_db.income_overrides io ON pi.transaction_id = io.transaction_id
                {where_clause}
            """
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()[0]

            # Build main query with pagination
            base_query = f"""
                SELECT
                    pi.account_number,
                    pi.account_name,
                    pi.date,
                    pi.credit_amount,
                    pi.debit_amount,
                    pi.code,
                    pi.description,
                    pi.reference,
                    pi.memo,
                    pi.transaction_type,
                    pi.amount,
                    pi.transaction_id,
                    COALESCE(io.property_name, pi.property_name) as property_name,
                    io.mapping_notes as mapping_notes,
                    {rule_name_select},
                    pi.created_at,
                    pi.updated_at,
                    pi.modified_by
                FROM processed_income pi
                LEFT JOIN overrides_db.income_overrides io ON pi.transaction_id = io.transaction_id
                {rules_join}
                {where_clause}
                ORDER BY pi.date DESC
            """

            # Apply pagination only if limit > 0
            if limit > 0:
                offset = (page - 1) * limit
                base_query += f" LIMIT {limit} OFFSET {offset}"

            cursor.execute(base_query, params)
            rows = cursor.fetchall()

            # Detach the overrides database
            cursor.execute("DETACH DATABASE overrides_db")
            cursor.execute("DETACH DATABASE rules_db")

            data = [dict(row) for row in rows]
            actual_limit = limit if limit > 0 else total_count
            has_more = (page * actual_limit) < total_count if limit > 0 else False

            return PaginatedResponse(
                data=data,
                page=page,
                limit=actual_limit,
                total_count=total_count,
                has_more=has_more
            )

    except sqlite3.Error as e:
        logger.error(f"Database error fetching all income: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.get("/expenses/all")
def get_all_expenses(
    http_request: Request,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(0, ge=0, le=1000, description="Items per page (0 = all)"),
    search: Optional[str] = Query(None, description="Search in description/category"),
    category_filter: Optional[str] = Query(None, alias="category", description="Filter by category"),
    property_filter: Optional[str] = Query(None, alias="property", description="Filter by property name")
) -> PaginatedResponse:
    """Get ALL expense transactions (assigned and unassigned) with pagination.

    Returns expense transactions sorted by date, for viewing and editing.
    Applies any manual overrides that have been saved.

    Pagination: Use page and limit parameters. Set limit=0 for all records (backward compatible).
    Search: Filter by description, category, or property name.
    """
    db_path = get_config().data_dir / "processed" / "processed.db"
    review_manager = get_review_manager()

    if not db_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Database not found. Please process transactions first."
        )

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Attach the overrides database to access override data
            cursor.execute(f"ATTACH DATABASE '{review_manager.overrides_db_path}' AS overrides_db")

            # Build WHERE clause for filters
            where_conditions = []
            params = []

            if search:
                where_conditions.append(
                    "(pe.description LIKE ? OR COALESCE(eo.category, pe.category) LIKE ? OR COALESCE(eo.property_name, pe.property_name) LIKE ?)"
                )
                search_term = f"%{search}%"
                params.extend([search_term, search_term, search_term])

            if category_filter:
                where_conditions.append("COALESCE(eo.category, pe.category) = ?")
                params.append(category_filter)

            if property_filter:
                where_conditions.append("COALESCE(eo.property_name, pe.property_name) = ?")
                params.append(property_filter)

            where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

            # Get total count
            count_query = f"""
                SELECT COUNT(*)
                FROM processed_expenses pe
                LEFT JOIN overrides_db.expense_overrides eo ON pe.transaction_id = eo.transaction_id
                {where_clause}
            """
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()[0]

            # Build main query with pagination
            base_query = f"""
                SELECT
                    pe.account_number,
                    pe.account_name,
                    pe.date,
                    pe.credit_amount,
                    pe.debit_amount,
                    pe.code,
                    pe.description,
                    pe.reference,
                    pe.memo,
                    pe.transaction_type,
                    pe.amount,
                    pe.transaction_id,
                    COALESCE(eo.category, pe.category) as category,
                    pe.confidence,
                    pe.match_reason,
                    COALESCE(eo.property_name, pe.property_name) as property_name,
                    pe.created_at,
                    pe.updated_at,
                    pe.modified_by,
                    CASE
                        WHEN eo.transaction_id IS NOT NULL THEN 'overridden'
                        ELSE pe.category_status
                    END as category_status
                FROM processed_expenses pe
                LEFT JOIN overrides_db.expense_overrides eo ON pe.transaction_id = eo.transaction_id
                {where_clause}
                ORDER BY pe.date DESC
            """

            # Apply pagination only if limit > 0
            if limit > 0:
                offset = (page - 1) * limit
                base_query += f" LIMIT {limit} OFFSET {offset}"

            cursor.execute(base_query, params)
            rows = cursor.fetchall()

            # Detach the overrides database
            cursor.execute("DETACH DATABASE overrides_db")

            data = [dict(row) for row in rows]
            actual_limit = limit if limit > 0 else total_count
            has_more = (page * actual_limit) < total_count if limit > 0 else False

            return PaginatedResponse(
                data=data,
                page=page,
                limit=actual_limit,
                total_count=total_count,
                has_more=has_more
            )

    except sqlite3.Error as e:
        logger.error(f"Database error fetching all expenses: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.delete("/expense/{transaction_id}")
def delete_expense(transaction_id: str, http_request: Request) -> dict:
    """Delete an expense transaction."""
    db_path = get_config().data_dir / "processed" / "processed.db"
    review_manager = get_review_manager()

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM processed_expenses WHERE transaction_id = ?", (transaction_id,))
            conn.commit()

        # Also delete from overrides if exists
        with sqlite3.connect(review_manager.overrides_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM expense_overrides WHERE transaction_id = ?", (transaction_id,))
            conn.commit()

        logger.info(f"Deleted expense transaction: {transaction_id}")
        return {"status": "success", "transaction_id": transaction_id}

    except sqlite3.Error as e:
        logger.error(f"Error deleting expense {transaction_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.delete("/income/{transaction_id}")
def delete_income(transaction_id: str, http_request: Request) -> dict:
    """Delete an income transaction."""
    db_path = get_config().data_dir / "processed" / "processed.db"
    review_manager = get_review_manager()

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM processed_income WHERE transaction_id = ?", (transaction_id,))
            conn.commit()

        # Also delete from overrides if exists
        with sqlite3.connect(review_manager.overrides_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM income_overrides WHERE transaction_id = ?", (transaction_id,))
            conn.commit()

        logger.info(f"Deleted income transaction: {transaction_id}")
        return {"status": "success", "transaction_id": transaction_id}

    except sqlite3.Error as e:
        logger.error(f"Error deleting income {transaction_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.put("/expense/{transaction_id}")
def update_expense(
    transaction_id: str,
    request: ExpenseUpdateRequest,
    http_request: Request
) -> dict:
    """Update a full expense transaction."""
    db_path = get_config().data_dir / "processed" / "processed.db"
    review_manager = get_review_manager()

    # Validate required fields
    if not request.category or request.category.strip() == '':
        raise HTTPException(status_code=400, detail="Category is required for expenses")

    try:
        # Update the main transaction table
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE processed_expenses
                SET date = ?,
                    description = ?,
                    amount = ?,
                    memo = ?
                WHERE transaction_id = ?
            """, (request.date, request.description, request.amount, request.memo, transaction_id))
            conn.commit()

        # Update or create override for category and property
        with sqlite3.connect(review_manager.overrides_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO expense_overrides (
                    transaction_id, category, property_name,
                    created_at, updated_at, modified_by
                )
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'web_user')
                ON CONFLICT(transaction_id) DO UPDATE SET
                    category = excluded.category,
                    property_name = excluded.property_name,
                    updated_at = CURRENT_TIMESTAMP,
                    modified_by = 'web_user'
            """, (transaction_id, request.category, request.property_name))
            conn.commit()

        logger.info(f"Updated expense transaction: {transaction_id}")
        return {"status": "success", "transaction_id": transaction_id}

    except sqlite3.Error as e:
        logger.error(f"Error updating expense {transaction_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.put("/income/{transaction_id}")
def update_income(
    transaction_id: str,
    request: IncomeUpdateRequest,
    http_request: Request
) -> dict:
    """Update a full income transaction."""
    db_path = get_config().data_dir / "processed" / "processed.db"
    review_manager = get_review_manager()

    # Validate required fields
    if not request.property_name or request.property_name.strip() == '':
        raise HTTPException(status_code=400, detail="Property is required for income")

    try:
        # Update the main transaction table
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE processed_income
                SET date = ?,
                    description = ?,
                    amount = ?,
                    memo = ?
                WHERE transaction_id = ?
            """, (request.date, request.description, request.amount, request.memo, transaction_id))
            conn.commit()

        # Update or create override for property
        with sqlite3.connect(review_manager.overrides_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO income_overrides (
                    transaction_id, property_name, mapping_notes,
                    created_at, updated_at, modified_by
                )
                VALUES (?, ?, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'web_user')
                ON CONFLICT(transaction_id) DO UPDATE SET
                    property_name = excluded.property_name,
                    updated_at = CURRENT_TIMESTAMP,
                    modified_by = 'web_user'
            """, (transaction_id, request.property_name))
            conn.commit()

        logger.info(f"Updated income transaction: {transaction_id}")
        return {"status": "success", "transaction_id": transaction_id}

    except sqlite3.Error as e:
        logger.error(f"Error updating income {transaction_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
