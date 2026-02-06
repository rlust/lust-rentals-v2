"""Processing routes for bank file upload and transaction processing."""
from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.encoders import jsonable_encoder
from pandas import DataFrame

from src.api.dependencies import get_config, get_processor
from src.api.models import BankProcessRequest, BankProcessResponse
from src.utils.validation import DataValidator

router = APIRouter()
CONFIG = get_config()


@router.post("/upload/bank-file")
async def upload_bank_file(request: Request, file: UploadFile = File(...)) -> dict:
    """Upload a bank transaction CSV file to the raw data directory."""

    # Validate filename
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    # Read file contents
    try:
        contents = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")

    # Validate file size (max 50MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE / 1024 / 1024}MB"
        )

    # Validate minimum file size (at least 10 bytes)
    if len(contents) < 10:
        raise HTTPException(status_code=400, detail="File is empty or too small")

    # Validate CSV structure before saving
    try:
        # Try to decode with common encodings
        try:
            content_str = contents.decode('utf-8-sig')
        except UnicodeDecodeError:
            try:
                content_str = contents.decode('latin-1')
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid file encoding. Please use UTF-8 or Latin-1 encoding"
                )

        # Validate CSV structure
        csv_reader = csv.reader(StringIO(content_str))
        headers = next(csv_reader, None)

        if not headers or len(headers) == 0:
            raise HTTPException(status_code=400, detail="CSV file has no headers")

        # Validate at least one data row exists
        first_row = next(csv_reader, None)
        if not first_row:
            raise HTTPException(status_code=400, detail="CSV file has no data rows")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")

    # Save to raw data directory
    raw_dir = CONFIG.data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    file_path = raw_dir / file.filename

    try:
        with open(file_path, 'wb') as f:
            f.write(contents)

        # Get file info and count rows
        file_size = file_path.stat().st_size
        row_count = content_str.count('\n') - 1  # Subtract header row

        return {
            "success": True,
            "filename": file.filename,
            "file_path": str(file_path),
            "file_size_bytes": file_size,
            "headers": headers,
            "row_count": max(0, row_count),
            "message": f"File uploaded successfully. Found {row_count} rows. Ready to process."
        }

    except Exception as e:
        # Clean up file if there was an error
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@router.post("/validate/bank")
def validate_bank_file(request: BankProcessRequest) -> dict:
    """
    Validate bank transaction file before processing.

    Performs comprehensive checks including:
    - Duplicate transaction detection
    - Date range validation
    - Amount anomaly detection
    - Required column verification
    - Format consistency checks

    Returns validation results with any issues found.
    Use this endpoint before calling /process/bank to catch data quality issues early.
    """
    validator = DataValidator()

    # Determine file path (same logic as process_bank)
    bank_path: Optional[Path] = None
    if request.bank_file_path is not None:
        bank_path = Path(request.bank_file_path)
    else:
        bank_path = CONFIG.data_dir / "raw" / "transaction_report-3.csv"

    if not bank_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Bank file not found: {bank_path}. Please ensure the file exists at the specified path."
        )

    # Determine year (same logic as processor)
    year = request.year or (datetime.now().year - 1)

    # Validate the file
    result = validator.validate_bank_file(bank_path, year)

    return jsonable_encoder(result.to_dict())


@router.post("/process/bank", response_model=BankProcessResponse)
def process_bank(http_request: Request, request: BankProcessRequest) -> BankProcessResponse:
    """Process Park National transactions and persist normalized outputs."""

    processor = get_processor()
    bank_path: Optional[Path] = None

    if request.bank_file_path is not None:
        bank_path = Path(request.bank_file_path)
        if not bank_path.exists():
            raise HTTPException(status_code=404, detail="Supplied bank_file_path does not exist.")

    try:
        results = processor.process_bank_transactions(file_path=bank_path, year=request.year)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:  # validation issues
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    unresolved_df = results.get("unresolved")
    unresolved_rows = int(unresolved_df.shape[0]) if isinstance(unresolved_df, DataFrame) else 0

    return BankProcessResponse(
        income_rows=int(results["income"].shape[0]),
        expense_rows=int(results["expenses"].shape[0]),
        unresolved_rows=unresolved_rows,
    )


@router.get("/files/latest-transaction")
def get_latest_transaction_file() -> dict:
    """
    Find the most recent transaction file in raw directory.

    Returns the path, filename, and modification time of the most recently
    modified transaction file matching known patterns.

    This endpoint replaces hardcoded path logic in client-side code,
    making the application portable across different systems.
    """
    raw_dir = CONFIG.data_dir / "raw"

    if not raw_dir.exists():
        raise HTTPException(
            status_code=404,
            detail="Raw data directory not found. Please upload a transaction file first."
        )

    # Search for transaction files with known patterns
    patterns = ["transaction_report-*.csv", "transaction_report.csv", "bank_transactions.csv"]
    candidates = []

    for pattern in patterns:
        candidates.extend(raw_dir.glob(pattern))

    if not candidates:
        raise HTTPException(
            status_code=404,
            detail="No transaction files found. Please upload a transaction file from the dashboard."
        )

    # Return most recent by modification time
    latest = max(candidates, key=lambda p: p.stat().st_mtime)

    return {
        "file_path": str(latest),
        "filename": latest.name,
        "modified_at": datetime.fromtimestamp(latest.stat().st_mtime).isoformat(),
        "size_bytes": latest.stat().st_size
    }


@router.get("/process/status")
def get_processing_status() -> dict:
    """
    Check if transaction processing is complete and data is ready.

    Returns status information about processed data files, indicating whether
    they have been recently updated (within last 10 seconds). Used by the
    review interface to poll for completion after triggering reprocessing.
    """
    processed_dir = CONFIG.data_dir / "processed"

    income_file = processed_dir / "processed_income.csv"
    expenses_file = processed_dir / "processed_expenses.csv"

    # Check if files exist and were recently modified (within last 10 seconds)
    now = datetime.now().timestamp()

    income_ready = income_file.exists() and (now - income_file.stat().st_mtime) < 10
    expenses_ready = expenses_file.exists() and (now - expenses_file.stat().st_mtime) < 10

    return {
        "ready": income_ready and expenses_ready,
        "income_ready": income_ready,
        "expenses_ready": expenses_ready,
        "timestamp": datetime.now().isoformat()
    }
