# Lust Rentals LLC - Tax Reporting System

This project is designed to analyze and report income and expense data for Lust Rentals LLC for IRS tax reporting purposes.

## ✨ Recent Enhancements

**Phase 3 (In Progress):**
- 📋 **Per-Property Schedule E** - Individual tax worksheets for each rental property (NEW!)
- 📊 **Aggregated Schedule E** - Automatic consolidation across all properties for IRS filing (NEW!)
- 📄 **Enhanced PDF Reports** - Detailed breakdown with all properties in one comprehensive document (NEW!)

**Phase 1 (Completed):**
- 🔍 **Data Validation** - Pre-processing validation catches duplicates, date issues, and anomalies before processing
- 📋 **Audit Trail** - Complete compliance with timestamps, user attribution, and change history
- ⚡ **Bulk Operations** - Process 100+ overrides at once (10x faster workflow)
- 📥 **CSV Import/Export** - Excel-friendly workflow for bulk overrides
- 🤖 **Enhanced Categorization** - 80+ merchant database, confidence scoring (60-80% less manual review)

**Phase 2 (Completed):**
- 📊 **Multi-Year Reporting** - Trend analysis across multiple years with growth rates
- 🎯 **Data Quality Metrics** - Real-time quality scores and actionable recommendations
- 🔎 **Fuzzy Matching** - Handle typos and memo variations in deposit mapping (50-70% fewer unmapped)

**See `docs/ROADMAP.md` for full feature roadmap and `docs/PER_PROPERTY_SCHEDULE_E.md` for detailed per-property reporting guide.**

## Project Structure

```
lust-rentals-llc/
├── data/
│   ├── raw/           # Raw CSV/Excel files from accounting software
│   ├── processed/     # Cleaned and processed data
│   └── reports/       # Generated tax reports
├── src/
│   ├── data_processing/  # Data cleaning and transformation
│   ├── reporting/        # Report generation
│   └── utils/            # Utility functions
├── tests/                # Unit and integration tests
└── docs/                 # Documentation
```

## Setup

### Mac Users

**Automated Installation (Recommended):**
```bash
curl -fsSL https://raw.githubusercontent.com/rlust/lust-rentals-tax-reporting/main/install-mac.sh | bash
```
Or download and run locally:
```bash
git clone https://github.com/rlust/lust-rentals-tax-reporting.git
cd lust-rentals-tax-reporting
./install-mac.sh
```

**Manual Installation:** See the detailed [Mac Installation Guide](docs/MAC_INSTALLATION_GUIDE.md) for step-by-step instructions.

### Quick Setup

1. Create a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Quickstart: Run the API & Review Dashboard

1. Ensure your `LUST_DATA_DIR` points at a writable data directory (defaults to `./data`). For local usage you can leave the default or set it explicitly:

   ```bash
   export LUST_DATA_DIR="$(pwd)/data"
   ```

2. (Optional) Pre-create the standard subdirectories so the app can persist processed data and overrides:

   ```bash
   mkdir -p "$LUST_DATA_DIR"/raw "$LUST_DATA_DIR"/processed "$LUST_DATA_DIR"/overrides "$LUST_DATA_DIR"/reports
   ```

3. Start the FastAPI server with live reload:

   ```bash
   python -m uvicorn src.api.server:app --reload
   ```

4. In your browser, open `http://localhost:8000/review` to access the GUI. Use the Pipeline & Reports controls to process bank data, generate reports, and manage manual overrides. Changes persist to `data/processed/` CSVs and `data/overrides/overrides.db` for reuse after restarts.

## Usage

### 1. Prepare input data

1. Export the Park National Bank transaction report (`transaction_report-3.csv`) and copy it into `data/raw/`.
2. Maintain the deposit mapping file (`deposit_amount_map.csv`) with memo/amount to property attribution guidance. Place it in `data/raw/` (or leave in your Downloads folder; the pipeline auto-detects).

### 2. Process and classify transactions

Run the bank ingestion pipeline via the CLI to normalize data, classify income/expenses, and apply property mapping:

```bash
python -m src.cli.app process-bank --year 2025
```

Omit `--year` to process the full file or pass `--bank-file` to target an explicit export path.

Outputs written to `data/processed/`:

- `processed_income.csv` – income rows with property metadata and mapping status
- `processed_expenses.csv` – expense rows with cleaned categories
- `bank_transactions_normalized.csv` – normalized snapshot of the raw bank feed
- `income_mapping_review.csv` – rows requiring manual review (e.g., `UNASSIGNED` or unmapped memos)
- `unresolved_bank_transactions.csv` – transactions where credit/debit signals were ambiguous

### 3. Generate reports

Produce the annual summary PDF and Schedule E CSV (defaults to the prior tax year) with:

```bash
python -m src.cli.app generate-reports --year 2025
```

Pass `--no-save` to preview metrics without writing PDF/CSV artifacts.

> **Deprecation Notice:** Legacy module entrypoints (`python -m src.reporting.tax_reports`) show deprecation warnings. Please use the CLI as the production interface.

### 4. Validate data quality (NEW in Phase 1)

Before processing, validate your bank file to catch issues early:

```bash
curl -X POST "http://localhost:8000/validate/bank?year=2025" \
  -H "Content-Type: application/json"
```

This checks for:
- Duplicate transactions
- Out-of-range dates
- Amount anomalies (outliers)
- Missing required fields
- Format consistency

### 5. Review & override in the GUI

1. Start the FastAPI app:

   ```bash
   python3 -m uvicorn src.api.server:app --reload
   ```

   > Running via Docker? The container command listed in the Deployment section exposes the same UI on port 8000.

2. Open `http://localhost:8000/review` in a browser. The **Pipeline & Reports** panel surfaces:

   - Pending income/expense counts
   - Processed CSV presence
   - Recent export audit rows
   - Controls to rerun the processor, trigger annual/Schedule E reports, and download processed datasets

3. Use the tables below the panel to assign properties/categories. Each row offers dropdowns populated from existing overrides along with inline notes.

4. Re-run the bank processor (via the GUI control or CLI) after finishing overrides to apply the decisions and regenerate downstream reports. The reports panel also surfaces download buttons for generated PDFs/CSVs via new API routes:

   - `GET /reports/status?year=2025` – availability metadata
   - `GET /reports/download/<artifact>?year=2025` – download `summary_pdf`, `schedule_csv`, `schedule_property_csv`, or `expense_chart`

### 6. Export processed datasets

Download processed income or expense data directly from the API (after running the pipeline):

```bash
curl -o processed_income.csv http://localhost:8000/export/income
curl -o processed_expenses.csv http://localhost:8000/export/expenses
```

Artifacts written to `data/reports/`:

- `lust_rentals_tax_summary_<YEAR>.pdf` – overview including property income, expense breakdowns, review counts
- `expense_breakdown_<YEAR>.png` – supporting chart for the PDF
- `schedule_e_<YEAR>.csv` – Schedule E line item export with totals
- `schedule_e_property_summary_<YEAR>.csv` – property-level rental income, transaction counts, and mapping-status counts used for Schedule E attachments

## New API Endpoints (Phases 1 & 2)

### Data Quality & Validation

**Validate bank file before processing:**
```bash
POST /validate/bank?year=2025
```
Returns validation results with errors/warnings and recommendations.

**Check data quality metrics:**
```bash
GET /metrics/quality?year=2025
```
Returns:
- Income mapping rate (% deposits mapped to properties)
- Expense categorization rate
- Confidence score distribution
- Overall quality score (0-100)
- Actionable recommendations

### Bulk Operations

**Bulk assign properties to income:**
```bash
POST /review/bulk/income
Body: {
  "overrides": [
    {"transaction_id": "txn_001", "property_name": "Property A", "mapping_notes": ""},
    {"transaction_id": "txn_002", "property_name": "Property A", "mapping_notes": ""}
  ]
}
```

**Bulk categorize expenses:**
```bash
POST /review/bulk/expenses
Body: {
  "overrides": [
    {"transaction_id": "txn_003", "category": "repairs", "property_name": "Property A"}
  ]
}
```

### CSV Import/Export

**Download override templates:**
```bash
GET /review/export/income-template    # Returns CSV template for income
GET /review/export/expense-template   # Returns CSV template for expenses
```

**Import completed overrides:**
```bash
POST /review/import/income
POST /review/import/expenses
# Upload CSV file with completed overrides
```

### Audit Trail

**Get audit log:**
```bash
GET /audit/log?transaction_id=txn_001&start_date=2025-01-01
```
Returns change history with timestamps, users, old/new values.

**Get audit summary:**
```bash
GET /audit/summary
```
Returns total overrides, user activity, recent changes.

### Multi-Year Reporting (NEW in Phase 2)

**Analyze multiple years:**
```bash
GET /reports/multi-year?start_year=2022&end_year=2025
```
Returns:
- Per-year income, expenses, net income
- Year-over-year growth rates
- Property breakdowns
- Category trends
- Average annual statistics

### Per-Property Schedule E (NEW in Phase 3)

**Generate individual Schedule E for each property:**
```bash
POST /reports/schedule-e/per-property
Body: {
  "year": 2025,
  "save_outputs": true
}
```
Returns per-property Schedule E data with all line items (1-12).
Generates individual CSV files for each property.

**Generate aggregated Schedule E across all properties:**
```bash
POST /reports/schedule-e/aggregate
Body: {
  "year": 2025,
  "save_outputs": true
}
```
Returns consolidated Schedule E for IRS filing.
Generates:
- Individual property CSV files
- Aggregated CSV (schedule_e_2025_aggregate.csv)
- Detailed PDF with all properties (schedule_e_2025_detailed.pdf)

**See `docs/PER_PROPERTY_SCHEDULE_E.md` for complete usage guide.**

## Data Requirements

- Income records (CSV/Excel)
- Expense records (CSV/Excel)
- Asset purchase records
- Depreciation schedules (if applicable)
- Previous year tax returns (for reference)

## Testing

Run the automated test suite (unit + integration):

```bash
pytest
```

## Deployment

### Production Deployment

For production deployments with SSL, automated backups, and monitoring, see:

- **[Production Deployment Guide](PRODUCTION_DEPLOYMENT.md)** - Complete production setup guide
- **[Quick Start Guide](PRODUCTION_QUICKSTART.md)** - 5-minute production deployment

The production setup includes:
- Docker Compose with app, Nginx reverse proxy, and backup services
- SSL/TLS configuration with Let's Encrypt support
- Automated daily backups with cloud storage support (S3, GCS, Azure)
- Security hardening (rate limiting, security headers, HTTPS)
- Health checks and logging
- Backup and restore scripts

**Quick production start:**
```bash
cp .env.production.example .env.production
# Edit .env.production with your settings
docker-compose -f docker-compose.production.yml up -d
```

### Development/Simple Deployment

For development or simple single-container deployment:

1. Build the production image:

   ```bash
   docker build -t lust-rentals-tax-reporting .
   ```

2. Run the API:

   ```bash
   docker run \
     -p 8000:8000 \
     -v $(pwd)/data:/app/data \
     -e LUST_LOG_LEVEL=INFO \
     lust-rentals-tax-reporting
   ```
   The FastAPI app is available at `http://localhost:8000` (GUI at `/review`).

### Continuous Integration

The GitHub Actions workflow (`.github/workflows/ci.yml`) installs dependencies, runs the pytest suite, and builds the Docker image on pushes/PRs to `main`.

### Data & Backups

**Development:**
- Processed datasets are stored both as CSVs under `data/processed/` and mirrored into `data/processed/processed.db` (SQLite) for reporting and external consumers.
- Manual overrides are persisted in `data/overrides/overrides.db`. Back up this file regularly (e.g., nightly copy to object storage) since it records review decisions.
- To rotate overrides, create a dated copy of `overrides.db` before running bulk imports, then vacuum the live database if it grows (`sqlite3 overrides.db 'VACUUM;'`).
- SQLite stores undergo lightweight migrations on startup via `src/utils/sqlite_migrations.py`; ensure deployments keep database files writable so migrations can run.

**Production:**
- Automated daily backups run at 2 AM UTC via the backup service
- Backups include databases, CSV files, and reports with integrity verification
- Cloud storage support for off-site backups (S3, Google Cloud Storage, Azure Blob)
- 90-day retention policy (configurable)
- Restore script available: `./scripts/restore.sh -l` to list, `./scripts/restore.sh -d latest` to restore

## Configuration

Runtime configuration is read from environment variables (loadable via `.env`):

- `LUST_DATA_DIR` – Base directory containing `raw/`, `processed/`, and `reports/` (defaults to `./data`).
- `LUST_LOG_LEVEL` – Logging verbosity (defaults to `INFO`).

The CLI accepts `--log-level` to temporarily override the configured log level per invocation.

Key coverage:

- Bank ingestion classification and mapping review queue (`tests/test_processor_bank.py`)
- Tax reporting summaries and Schedule E outputs (`tests/test_tax_reporter.py`)
