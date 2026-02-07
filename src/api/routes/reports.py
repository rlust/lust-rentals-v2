"""Report generation routes for tax reports and property reports."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
import pandas as pd

from src.api.dependencies import get_config, get_tax_reporter, get_property_reporter
from src.api.models import ReportRequest

router = APIRouter()
logger = logging.getLogger(__name__)

# Report artifacts metadata
REPORT_ARTIFACTS = {
    "summary_pdf": {
        "filename": "lust_rentals_tax_summary_{year}.pdf",
        "content_type": "application/pdf",
        "display_name": "Annual summary (PDF)",
    },
    "schedule_csv": {
        "filename": "schedule_e_{year}.csv",
        "content_type": "text/csv",
        "display_name": "Schedule E (CSV)",
    },
    "schedule_property_csv": {
        "filename": "schedule_e_property_summary_{year}.csv",
        "content_type": "text/csv",
        "display_name": "Schedule E property summary",
    },
    "expense_chart": {
        "filename": "expense_breakdown_{year}.png",
        "content_type": "image/png",
        "display_name": "Expense breakdown chart",
    },
    "property_report_pdf": {
        "filename": "property_report_{year}.pdf",
        "content_type": "application/pdf",
        "display_name": "Property Income & Expense Report (PDF)",
    },
    "property_report_excel": {
        "filename": "Yearly Income & Expense Lust Rentals LLC.xlsx",
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "display_name": "Property Income & Expense Report (Excel)",
    },
}


def resolve_report_year(year: Optional[int]) -> int:
    """Resolve the report year, defaulting to previous year if not specified."""
    reporter = get_tax_reporter()
    return year or (reporter.current_year - 1)


def get_report_status_data(year: Optional[int] = None) -> Dict[str, object]:
    """Get report artifact availability for the requested tax year."""
    resolved_year = resolve_report_year(year)
    reporter = get_tax_reporter()
    reports_dir = reporter.reports_dir

    artifacts: Dict[str, Dict[str, object]] = {}
    for key, meta in REPORT_ARTIFACTS.items():
        path = reports_dir / meta["filename"].format(year=resolved_year)
        exists = path.exists()

        artifacts[key] = {
            "display_name": meta["display_name"],
            "exists": exists,
            "size_bytes": path.stat().st_size if exists else 0,
            "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat() if exists else None,
            "path": str(path),
        }

    return {"year": resolved_year, "artifacts": artifacts}


def _get_table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def _resolve_date_column(columns: list[str]) -> Optional[str]:
    if "date" in columns:
        return "date"
    return next((col for col in columns if "date" in col.lower()), None)


def _year_filter_clause(date_col: Optional[str]) -> str:
    if not date_col:
        return ""
    return f"WHERE strftime('%Y', {date_col}) = ?"


def _fetch_summary(
    conn: sqlite3.Connection,
    table_name: str,
    date_col: Optional[str],
    year: int,
) -> tuple[float, int]:
    clause = _year_filter_clause(date_col)
    params = [str(year)] if clause else []
    query = f"SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM {table_name} {clause}"
    total, count = conn.execute(query, params).fetchone()
    return float(total or 0), int(count or 0)


def _fetch_grouped_totals(
    conn: sqlite3.Connection,
    table_name: str,
    group_col: str,
    date_col: Optional[str],
    year: int,
) -> Dict[str, float]:
    clause = _year_filter_clause(date_col)
    params = [str(year)] if clause else []
    query = (
        f"SELECT {group_col}, SUM(amount) "
        f"FROM {table_name} {clause} GROUP BY {group_col}"
    )
    rows = conn.execute(query, params).fetchall()
    return {
        str(key): float(total)
        for key, total in rows
        if key is not None and str(key).strip()
    }


def _load_table_for_year(
    conn: sqlite3.Connection,
    table_name: str,
    date_col: Optional[str],
    year: int,
) -> pd.DataFrame:
    clause = _year_filter_clause(date_col)
    params = [str(year)] if clause else []
    query = f"SELECT * FROM {table_name} {clause}"
    return pd.read_sql_query(query, conn, params=params)


@router.post("/annual")
def generate_annual_report(http_request: Request, request: ReportRequest) -> dict:
    """Generate annual summary metrics and optionally persist artifacts."""

    reporter = get_tax_reporter()
    try:
        summary = reporter.generate_annual_summary(year=request.year, save_to_file=request.save_outputs)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=(
                "Source data not found. Please process your bank transactions first using "
                "the 'Run processor' button. Error: " + str(e)
            ),
        ) from e

    return jsonable_encoder(summary)


@router.post("/schedule-e")
def generate_schedule_e_report(http_request: Request, request: ReportRequest) -> dict:
    """Generate Schedule E data for the requested tax year."""

    reporter = get_tax_reporter()

    try:
        schedule = reporter.generate_schedule_e(year=request.year)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Source data not found. Please process your bank transactions first using the 'Run processor' button. Error: {str(e)}"
        ) from e

    if not request.save_outputs:
        # When skipping persistence we still want the CSV omitted, so delete if created.
        schedule.pop("property_summary", None)

    return jsonable_encoder(schedule)


@router.post("/schedule-e/per-property")
def generate_per_property_schedule_e_report(http_request: Request, request: ReportRequest) -> dict:
    """Generate individual Schedule E forms for each property.

    Returns a dictionary mapping property names to their Schedule E data.
    Each property gets income and expenses broken down by Schedule E line items.
    CSV files are saved for each property if save_outputs=True.

    Example response:
    {
        "118 W Shields St": {"1": 985.0, "4": 50.0, ..., "12": 935.0},
        "966 Kinsbury Court": {"1": 1300.0, "4": 75.0, ..., "12": 1225.0},
        ...
    }
    """
    reporter = get_tax_reporter()

    try:
        per_property_schedules = reporter.generate_per_property_schedule_e(year=request.year)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Source data not found. Please process your bank transactions first using the 'Run processor' button. Error: {str(e)}"
        ) from e

    return jsonable_encoder(per_property_schedules)


@router.post("/schedule-e/aggregate")
def generate_aggregated_schedule_e_report(http_request: Request, request: ReportRequest) -> dict:
    """Generate aggregated Schedule E across all properties.

    Sums up all per-property Schedule E forms into a single consolidated report.
    Includes property breakdown for reference.

    This generates:
    - Individual CSV files for each property (schedule_e_2025_Property_Name.csv)
    - Aggregated CSV (schedule_e_2025_aggregate.csv)
    - Detailed PDF with all properties (schedule_e_2025_detailed.pdf)

    Returns aggregated Schedule E with property details included.
    """
    reporter = get_tax_reporter()

    try:
        aggregated = reporter.generate_aggregated_schedule_e(
            year=request.year,
            save_to_file=request.save_outputs
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Source data not found. Please process your bank transactions first using the 'Run processor' button. Error: {str(e)}"
        ) from e

    return jsonable_encoder(aggregated)


@router.post("/property/pdf")
def generate_property_pdf_report(http_request: Request, request: ReportRequest) -> dict:
    """Generate a simplified PDF report showing income and expenses by property.

    This endpoint creates a streamlined report that displays:
    - Total income and expenses across all properties
    - Net income for the year
    - Property-by-property breakdown with income, expenses, and net

    Returns summary data including file path if save_outputs=True.
    """
    try:
        property_reporter = get_property_reporter()
        file_path, summary = property_reporter.generate_pdf_report(
            year=request.year or (datetime.now().year - 1),
            save_to_file=request.save_outputs
        )

        response = {
            **summary,
            "file_path": file_path,
            "report_type": "property_pdf"
        }

        return jsonable_encoder(response)

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Source data not found. Please process your bank transactions first using the 'Run processor' button. Error: {str(e)}"
        ) from e
    except Exception as e:
        logger.error(f"Error generating property PDF report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}") from e


@router.post("/property/excel")
def generate_property_excel_report(http_request: Request, request: ReportRequest) -> dict:
    """Generate the yearly Excel report with summary, income, expenses, and property breakdown sheets."""
    try:
        property_reporter = get_property_reporter()
        resolved_year = resolve_report_year(request.year)
        file_path, summary = property_reporter.generate_excel_report(
            year=resolved_year,
            save_to_file=request.save_outputs
        )

        response = {
            **summary,
            "file_path": file_path,
            "report_type": "property_excel"
        }

        return jsonable_encoder(response)

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Source data not found. Please process your bank transactions first using the 'Run processor' button. Error: {str(e)}"
        ) from e
    except Exception as e:
        logger.error(f"Error generating property Excel report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}") from e


@router.get("/status")
def reports_status(year: Optional[int] = None) -> dict:
    """Report artifact availability for the requested tax year."""

    status = get_report_status_data(year)
    return jsonable_encoder(status)


@router.get("/download/{artifact}")
def download_report_artifact(artifact: str, year: Optional[int] = None) -> FileResponse:
    """Download a generated report artifact."""
    reporter = get_tax_reporter()
    resolved_year = resolve_report_year(year)
    meta = REPORT_ARTIFACTS.get(artifact)
    if meta is None:
        raise HTTPException(status_code=404, detail="Unknown report artifact.")

    file_path = reporter.reports_dir / meta["filename"].format(year=resolved_year)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found. Generate reports first.")

    return FileResponse(
        path=file_path,
        media_type=meta["content_type"],
        filename=file_path.name,
    )


@router.get("/multi-year")
def get_multi_year_report(start_year: int, end_year: int) -> dict:
    """
    Generate multi-year summary for trend analysis.

    Aggregates income, expenses, and net income across multiple years.
    Useful for year-over-year comparisons and identifying trends.

    Args:
        start_year: Beginning year (inclusive)
        end_year: Ending year (inclusive)

    Returns:
        Dictionary with per-year data and aggregate statistics

    Example:
        GET /reports/multi-year?start_year=2022&end_year=2025
    """
    if end_year < start_year:
        raise HTTPException(status_code=400, detail="end_year must be >= start_year")

    if (end_year - start_year) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 years per request")

    years_data = []
    years_with_data = []
    db_path = get_config().data_dir / "processed" / "processed.db"

    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Processed database not found. Run processing first.")

    try:
        with sqlite3.connect(db_path) as conn:
            income_columns = _get_table_columns(conn, "processed_income")
            expense_columns = _get_table_columns(conn, "processed_expenses")

            if not income_columns and not expense_columns:
                raise HTTPException(
                    status_code=404,
                    detail="No processed data found. Please process your bank transactions first using the 'Run processor' button.",
                )

            income_date_col = _resolve_date_column(income_columns)
            expense_date_col = _resolve_date_column(expense_columns)

            for year in range(start_year, end_year + 1):
                total_income, income_count = _fetch_summary(
                    conn, "processed_income", income_date_col, year
                ) if income_columns else (0.0, 0)
                total_expenses, expense_count = _fetch_summary(
                    conn, "processed_expenses", expense_date_col, year
                ) if expense_columns else (0.0, 0)

                net_income = total_income - total_expenses

                properties = (
                    _fetch_grouped_totals(
                        conn, "processed_income", "property_name", income_date_col, year
                    )
                    if income_columns and "property_name" in income_columns
                    else {}
                )
                categories = (
                    _fetch_grouped_totals(
                        conn, "processed_expenses", "category", expense_date_col, year
                    )
                    if expense_columns and "category" in expense_columns
                    else {}
                )

                has_data = (income_count + expense_count) > 0
                if has_data:
                    years_with_data.append(year)

                years_data.append({
                    "year": year,
                    "total_income": total_income,
                    "total_expenses": total_expenses,
                    "net_income": net_income,
                    "transaction_count": income_count + expense_count,
                    "properties": properties,
                    "expense_categories": categories,
                    "has_data": has_data,
                    "error": None if has_data else "No processed data found"
                })
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}") from e

    # Calculate aggregate statistics
    if years_with_data:
        valid_years = [y for y in years_data if y.get("has_data")]

        total_income_all = sum(y["total_income"] for y in valid_years)
        total_expenses_all = sum(y["total_expenses"] for y in valid_years)
        avg_annual_income = total_income_all / len(valid_years) if valid_years else 0
        avg_annual_expenses = total_expenses_all / len(valid_years) if valid_years else 0

        # Year-over-year growth rates
        growth_rates = []
        for i in range(1, len(valid_years)):
            prev_income = valid_years[i-1]["total_income"]
            curr_income = valid_years[i]["total_income"]
            if prev_income > 0:
                growth_rate = ((curr_income - prev_income) / prev_income) * 100
                growth_rates.append({
                    "from_year": valid_years[i-1]["year"],
                    "to_year": valid_years[i]["year"],
                    "income_growth_pct": round(growth_rate, 2)
                })

        summary = {
            "years_analyzed": len(valid_years),
            "total_income_all_years": total_income_all,
            "total_expenses_all_years": total_expenses_all,
            "total_net_income_all_years": total_income_all - total_expenses_all,
            "average_annual_income": avg_annual_income,
            "average_annual_expenses": avg_annual_expenses,
            "average_annual_net": avg_annual_income - avg_annual_expenses,
            "growth_rates": growth_rates
        }
    else:
        summary = {
            "years_analyzed": 0,
            "error": "No data found for any year in range"
        }

    return {
        "start_year": start_year,
        "end_year": end_year,
        "years": years_data,
        "summary": summary
    }


@router.get("/quality")
def get_data_quality_metrics(year: Optional[int] = None) -> dict:
    """
    Calculate data quality metrics for the specified year.

    Returns statistics about:
    - Income mapping rate (% of deposits mapped to properties)
    - Expense categorization rate (% of expenses with categories)
    - Auto-categorization confidence distribution
    - Unmapped/uncategorized transaction counts
    - Override activity

    Args:
        year: Year to analyze (defaults to current year)

    Returns:
        Dictionary with quality metrics and recommendations
    """
    resolved_year = year or datetime.now().year
    db_path = get_config().data_dir / "processed" / "processed.db"

    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Processed database not found. Run processing first.")

    metrics = {
        "year": resolved_year,
        "data_available": False,
        "income_metrics": {},
        "expense_metrics": {},
        "overall_quality_score": 0.0,
        "recommendations": []
    }

    try:
        with sqlite3.connect(db_path) as conn:
            income_columns = _get_table_columns(conn, "processed_income")
            expense_columns = _get_table_columns(conn, "processed_expenses")

            income_date_col = _resolve_date_column(income_columns) if income_columns else None
            expense_date_col = _resolve_date_column(expense_columns) if expense_columns else None

            income_df = (
                _load_table_for_year(conn, "processed_income", income_date_col, resolved_year)
                if income_columns
                else pd.DataFrame()
            )
            expense_df = (
                _load_table_for_year(conn, "processed_expenses", expense_date_col, resolved_year)
                if expense_columns
                else pd.DataFrame()
            )
    except sqlite3.Error as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    # Analyze income data
    if not income_df.empty:
        try:
            total_income = len(income_df)

            # Count mapped vs unmapped
            if 'mapping_status' in income_df.columns:
                mapped = len(income_df[income_df['mapping_status'].isin(['mapped', 'overridden'])])
                unmapped = total_income - mapped
                mapping_rate = (mapped / total_income * 100) if total_income > 0 else 0
                pending_review = len(
                    income_df[~income_df['mapping_status'].isin(['mapped', 'overridden'])]
                )
            else:
                # Fallback: check if property_name is set
                mapped = len(income_df[income_df['property_name'].notna()])
                unmapped = total_income - mapped
                mapping_rate = (mapped / total_income * 100) if total_income > 0 else 0
                pending_review = unmapped

            metrics["income_metrics"] = {
                "total_transactions": total_income,
                "mapped_count": mapped,
                "unmapped_count": unmapped,
                "mapping_rate_pct": round(mapping_rate, 2),
                "total_amount": float(income_df['amount'].sum()) if 'amount' in income_df.columns else 0.0,
                "pending_review_count": int(pending_review),
            }

            metrics["data_available"] = True

            # Add recommendation if mapping rate is low
            if mapping_rate < 80:
                metrics["recommendations"].append({
                    "severity": "warning",
                    "category": "income_mapping",
                    "message": f"Income mapping rate is {mapping_rate:.1f}%. Consider reviewing unmapped deposits.",
                    "action": "Visit /review to assign properties to unmapped income"
                })

        except Exception as e:
            logger.exception("Error analyzing income metrics")
            metrics["income_metrics"] = {"error": str(e)}

    # Analyze expense data
    if not expense_df.empty:
        try:
            total_expenses = len(expense_df)

            # Count categorized vs other
            if 'category' in expense_df.columns:
                categorized = len(expense_df[expense_df['category'] != 'other'])
                uncategorized = total_expenses - categorized
                categorization_rate = (categorized / total_expenses * 100) if total_expenses > 0 else 0
            else:
                categorized = 0
                uncategorized = total_expenses
                categorization_rate = 0

            # Analyze confidence scores if available
            confidence_stats = {}
            if 'confidence' in expense_df.columns:
                confidence_stats = {
                    "high_confidence_count": len(expense_df[expense_df['confidence'] >= 0.85]),
                    "medium_confidence_count": len(
                        expense_df[(expense_df['confidence'] >= 0.60) & (expense_df['confidence'] < 0.85)]
                    ),
                    "low_confidence_count": len(expense_df[expense_df['confidence'] < 0.60]),
                    "average_confidence": round(float(expense_df['confidence'].mean()), 3)
                }

            pending_review = 0
            if 'category' in expense_df.columns:
                pending_mask = expense_df['category'].fillna("").str.lower().isin(
                    ["", "other", "uncategorized"]
                )
                if 'category_status' in expense_df.columns:
                    pending_mask &= expense_df['category_status'].fillna("original") != "overridden"
                pending_review = int(pending_mask.sum())

            metrics["expense_metrics"] = {
                "total_transactions": total_expenses,
                "categorized_count": categorized,
                "uncategorized_count": uncategorized,
                "categorization_rate_pct": round(categorization_rate, 2),
                "total_amount": float(expense_df['amount'].sum()) if 'amount' in expense_df.columns else 0.0,
                "pending_review_count": pending_review,
                **confidence_stats
            }

            metrics["data_available"] = True

            # Add recommendations
            if categorization_rate < 80:
                metrics["recommendations"].append({
                    "severity": "warning",
                    "category": "expense_categorization",
                    "message": f"Expense categorization rate is {categorization_rate:.1f}%. Many expenses need manual review.",
                    "action": "Visit /review to categorize uncategorized expenses"
                })

            if confidence_stats and confidence_stats.get("low_confidence_count", 0) > 0:
                low_count = confidence_stats["low_confidence_count"]
                metrics["recommendations"].append({
                    "severity": "info",
                    "category": "low_confidence",
                    "message": f"{low_count} expenses have low confidence scores (<60%). Consider reviewing.",
                    "action": "Filter by low confidence in the review dashboard"
                })

        except Exception as e:
            logger.exception("Error analyzing expense metrics")
            metrics["expense_metrics"] = {"error": str(e)}

    # Calculate overall quality score
    if metrics["data_available"]:
        income_score = metrics["income_metrics"].get("mapping_rate_pct", 0) / 100
        expense_score = metrics["expense_metrics"].get("categorization_rate_pct", 0) / 100
        overall_score = (income_score + expense_score) / 2 * 100
        metrics["overall_quality_score"] = round(overall_score, 2)

        # Add overall recommendation
        if overall_score >= 90:
            metrics["recommendations"].append({
                "severity": "success",
                "category": "quality",
                "message": "Excellent data quality! Most transactions are properly categorized.",
                "action": None
            })
        elif overall_score >= 70:
            metrics["recommendations"].append({
                "severity": "info",
                "category": "quality",
                "message": "Good data quality, but some manual review recommended.",
                "action": "Review pending items in /review dashboard"
            })
        else:
            metrics["recommendations"].append({
                "severity": "warning",
                "category": "quality",
                "message": "Data quality needs improvement. Significant manual review required.",
                "action": "Prioritize reviewing unmapped income and uncategorized expenses"
            })

    return metrics
