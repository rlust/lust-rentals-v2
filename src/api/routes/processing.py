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
    raw_dir = get_config().data_dir / "raw"
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
        bank_path = get_config().data_dir / "raw" / "transaction_report-3.csv"

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
    raw_dir = get_config().data_dir / "raw"

    if not raw_dir.exists():
        raise HTTPException(
            status_code=404,
            detail="Raw data directory not found. Please upload a transaction file first."
        )

    def normalize_header(header: str) -> str:
        return header.strip().lower().replace(" ", "_").replace("/", "_").replace("-", "_")

    def is_valid_bank_file(path: Path) -> bool:
        try:
            with open(path, "r", newline="") as handle:
                reader = csv.reader(handle)
                headers = next(reader, None)
            if not headers:
                return False
            normalized = {normalize_header(col) for col in headers}
            return {"date", "credit_amount", "debit_amount"}.issubset(normalized)
        except Exception:
            return False

    def infer_years(path: Path, sample_rows: int = 500) -> list[int]:
        try:
            with open(path, "r", newline="") as handle:
                reader = csv.reader(handle)
                headers = next(reader, None)
                if not headers:
                    return []
                normalized = [normalize_header(col) for col in headers]
                if "date" not in normalized:
                    return []
                date_index = normalized.index("date")

                years: set[int] = set()
                for idx, row in enumerate(reader):
                    if idx >= sample_rows:
                        break
                    if len(row) <= date_index:
                        continue
                    raw_value = row[date_index].strip()
                    if not raw_value:
                        continue
                    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
                        try:
                            parsed = datetime.strptime(raw_value, fmt)
                            years.add(parsed.year)
                            break
                        except ValueError:
                            continue
                return sorted(years)
        except Exception:
            return []

    # Search for transaction files with known patterns
    patterns = ["transaction_report-*.csv", "transaction_report.csv", "bank_transactions.csv"]
    pattern_candidates: list[Path] = []

    for pattern in patterns:
        pattern_candidates.extend(raw_dir.glob(pattern))

    # Consider all CSVs, then filter by required headers to avoid false positives
    all_csv = list(raw_dir.glob("*.csv"))
    candidates = list({*pattern_candidates, *all_csv})

    if not candidates:
        raise HTTPException(
            status_code=404,
            detail="No transaction files found. Please upload a transaction file from the dashboard."
        )

    # Filter to valid bank files based on required headers
    valid_candidates = [path for path in candidates if is_valid_bank_file(path)]
    if not valid_candidates:
        raise HTTPException(
            status_code=404,
            detail=(
                "No valid transaction files found. Expected headers include Date, Credit Amount, and Debit Amount. "
                "Please upload a valid bank transaction CSV."
            )
        )

    # Return most recent by modification time
    latest = max(valid_candidates, key=lambda p: p.stat().st_mtime)
    detected_years = infer_years(latest)
    recommended_year = max(detected_years) if detected_years else None

    return {
        "file_path": str(latest),
        "filename": latest.name,
        "modified_at": datetime.fromtimestamp(latest.stat().st_mtime).isoformat(),
        "size_bytes": latest.stat().st_size,
        "detected_years": detected_years,
        "recommended_year": recommended_year,
    }


@router.get("/process/status")
def get_processing_status() -> dict:
    """
    Check if transaction processing is complete and data is ready.

    Returns status information about processed data files, indicating whether
    they have been recently updated (within last 10 seconds). Used by the
    review interface to poll for completion after triggering reprocessing.
    """
    processed_dir = get_config().data_dir / "processed"

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
