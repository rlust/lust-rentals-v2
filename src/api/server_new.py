"""FastAPI application exposing Lust Rentals processing and reporting workflows.

This is the refactored version using modular routers for better organization.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from src.api.dependencies import get_config, CONFIG
from src.api.routes import processing, reports, exports, review, properties, backup, rules
from src.utils.config import configure_logging

logger = logging.getLogger(__name__)

# Configure logging
configure_logging(CONFIG.log_level)

# Initialize FastAPI app
app = FastAPI(title="Lust Rentals Tax Reporting API", version="0.1.0")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

# Setup rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Register routers
# Processing routes handle: /upload/bank-file, /validate/bank, /process/bank
app.include_router(processing.router, tags=["Processing & Validation"])

# Report routes handle: /reports/* and /metrics/quality (note: /metrics/quality is in reports.router)
app.include_router(reports.router, prefix="/reports", tags=["Reports"])

# Export routes handle: /export/{dataset} and /export/excel/report
app.include_router(exports.router, prefix="/export", tags=["Exports"])

# Review routes handle: /review/income, /review/expenses, /review/income/{id}, etc.
app.include_router(review.router, prefix="/review", tags=["Review & Categorization"])

# Property management routes handle: /properties (CRUD operations)
app.include_router(properties.router, prefix="/properties", tags=["Property Management"])

# Automation Rules routes handle: /rules (CRUD operations)
app.include_router(rules.router, prefix="/rules", tags=["Automation Rules"])

# Backup and export routes handle: /backup/* (backup, export, restore)
app.include_router(backup.router, prefix="/backup", tags=["Backup & Export"])

# NOTE: The following routers still need to be extracted from the old server.py:
# - Review routes (/review/*) - ~12 endpoints
# - Audit routes (/audit/*) - 2 endpoints
# - System management routes (/system/*) - 4 endpoints
#
# For now, these are still in the old server.py. To complete the refactoring:
# 1. Create src/api/routes/review.py
# 2. Create src/api/routes/audit.py
# 3. Create src/api/routes/system.py
# 4. Register them here with app.include_router()
# 5. Remove the old server.py


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    """Render the modern V2 dashboard UI."""
    return templates.TemplateResponse("dashboard_v2.html", {"request": request})


@app.get("/review", response_class=HTMLResponse)
def review_dashboard(request: Request):
    """Render the modern review UI for transaction categorization."""
    return templates.TemplateResponse("review_v2.html", {"request": request})


@app.get("/properties-ui", response_class=HTMLResponse)
def properties_management(request: Request):
    """Render the property management UI."""
    return templates.TemplateResponse("properties.html", {"request": request})


@app.get("/rules-ui", response_class=HTMLResponse)
def rules_management(request: Request):
    """Render the automation rules management UI."""
    return templates.TemplateResponse("rules.html", {"request": request})


@app.get("/review-enhanced", response_class=HTMLResponse)
def review_enhanced(request: Request):
    """Render the enhanced review UI with bulk operations and modern UX."""
    return templates.TemplateResponse("review_v3.html", {"request": request})


@app.get("/health")
def healthcheck() -> dict[str, str]:
    """Service liveness probe."""
    return {"status": "ok"}


@app.get("/database/status")
def get_database_status() -> dict:
    """Get detailed database status including table information and row counts."""
    config = get_config()
    db_path = config.data_dir / "processed" / "processed.db"

    status: Dict[str, object] = {
        "database_path": str(db_path),
        "exists": db_path.exists(),
        "tables": {},
        "is_empty": True,
        "message": "",
    }

    if not db_path.exists():
        status["message"] = "Database does not exist yet. Process transactions to create it."
        return status

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = cursor.fetchall()

            # Whitelist of allowed tables to prevent SQL injection
            ALLOWED_TABLES = {
                "processed_income", "processed_expenses", "export_audit",
                "property_mapping", "review_overrides", "sqlite_sequence"
            }

            has_data = False
            for (table_name,) in tables:
                # Skip tables not in whitelist
                if table_name not in ALLOWED_TABLES:
                    continue

                # Get row count - using parameterized queries not possible with table names,
                # but validated against whitelist above
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]

                # Get column info
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()

                status["tables"][table_name] = {
                    "row_count": row_count,
                    "columns": [{"name": col[1], "type": col[2]} for col in columns],
                    "column_count": len(columns)
                }

                if table_name in ["processed_income", "processed_expenses"] and row_count > 0:
                    has_data = True

            status["is_empty"] = not has_data
            status["ready_for_reports"] = has_data

            if has_data:
                status["message"] = "Database is ready. You can generate reports."
            else:
                status["message"] = "Database tables exist but contain no data. Please process transactions."

    except sqlite3.Error as e:
        status["error"] = str(e)
        status["message"] = f"Database error: {e}"

    return status


def get_processed_status() -> Dict[str, object]:
    """Get status of processed data files and database."""
    config = get_config()
    processed_dir = config.data_dir / "processed"
    db_path = processed_dir / "processed.db"

    status: Dict[str, object] = {
        "income_csv": (processed_dir / "processed_income.csv").exists(),
        "expenses_csv": (processed_dir / "processed_expenses.csv").exists(),
        "db_exists": db_path.exists(),
        "export_audit": [],
    }

    if db_path.exists():
        try:
            with sqlite3.connect(db_path) as conn:
                rows = conn.execute(
                    "SELECT table_name, row_count, exported_at FROM export_audit ORDER BY exported_at DESC"
                ).fetchall()
        except sqlite3.OperationalError:
            rows = []
        status["export_audit"] = [
            {
                "table_name": row[0],
                "row_count": row[1],
                "exported_at": row[2],
            }
            for row in rows
        ]

    return status


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
