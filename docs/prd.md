# Lust Rentals LLC Tax Reporting System PRD

## 1. Executive Summary

Lust Rentals LLC requires a repeatable process to consolidate rental property income and expenses, transform source spreadsheets into standardized datasets, and generate IRS-ready summaries. This system must ingest deposits, expenses, and supplemental mapping files, normalize them, and produce Schedule E-aligned outputs alongside audit-ready artifacts.

## 2. Goals & Non-Goals

### Goals

1. Centralize source financial data (bank feeds, manual logs) in a structured repository.
2. Normalize and clean income/expense data for consistent downstream analysis.
3. Provide categorization and property attribution logic to map deposits to properties.
4. Generate annual summaries, expense breakdowns, and supporting schedules for IRS reporting.
5. Maintain traceability from processed figures back to raw inputs.

### Non-Goals

1. Replace accounting systems (e.g., QuickBooks) or perform bookkeeping reconciliation.
2. Automate direct IRS filing or e-file submission.
3. Provide real-time dashboards beyond annual/periodic reporting needs.

## 3. Stakeholders

1. **Primary:** Owner/operators of Lust Rentals LLC (financial reporting, compliance).
2. **Secondary:** Tax preparers or CPAs validating figures prior to filing.

## 4. Data Sources & Inputs

| Source | Location | Format | Key Fields |
| --- | --- | --- | --- |
| Bank transaction feed | `downloads/transaction_report-3.csv` | CSV | `Account Number`, `Account Name`, `Date`, `Credit Amount`, `Debit Amount`, `Code`, `Description`, `Memo` |
| Income deposit mapping | `downloads/deposit_amount_map.csv` | CSV | `memo`, `credit_amount`, `prop_name`, `notes` |
| Income transactions | `data/raw/income.*` | CSV/XLSX | Must contain `date`, `amount`, `description`, optional `property` |
| Expense transactions | `data/raw/expense.*` | CSV/XLSX | Must contain `date`, `amount`, `description`, optional `category`, `property` |
| Supplemental mapping | `docs/*.csv` | CSV | Property metadata, category overrides (future) |

### 4.1 Deposit Mapping Structure

Sample rows of `deposit_amount_map.csv` demonstrate memo-level mapping between bank deposits and properties with guidance for manual classification. Each row contains:

1. **memo:** Free-text bank memo used to identify recurring payments.
2. **credit_amount:** Transaction amount to match with bank deposits.
3. **prop_name:** Target property label (e.g., street address). `UNASSIGNED` indicates manual review required.
4. **notes:** Analyst instructions for ambiguous cases (e.g., split payments, housing authority deposits).

This mapping file guides the categorization logic when assigning income records to properties and flags records needing manual intervention.

### 4.2 Park National Bank Transaction Feed Structure

`transaction_report-3.csv` is the baseline export from Park National Bank and will serve as the raw unified feed for both income and expense events. Key characteristics:

1. **Account metadata:** `Account Number` and `Account Name` identify the originating bank account (e.g., Park National DDA ending 2755).
2. **Transaction dates:** `Date` is authoritative for tax-year filtering and must be parsed as timezone-naïve dates.
3. **Financial amounts:** `Credit Amount` denotes inflows (income), while `Debit Amount` captures outflows (expenses). Exactly one of the two columns is non-zero per row.
4. **Context fields:** `Code`, `Description`, and `Memo` capture bank classifications and narratives that feed categorization and property mapping, including housing authority payments and ACH details.

The processor must normalize column headers to snake_case and persist original narrative fields for audit trails.

## 5. Data Processing Pipeline

Processing is orchestrated by `FinancialDataProcessor` and includes:

1. **Load raw files** from `data/raw` directories, resolving `income.*` and `expense.*` sources automatically.@src/data_processing/processor.py#31-83
2. **Clean & standardize datasets** by normalizing column names, parsing dates, forcing numeric amounts, and dropping incomplete rows.@src/data_processing/processor.py#85-140
3. **Expense categorization** using keyword-based heuristics when categories are absent, preparing Schedule E aligned buckets.@src/data_processing/processor.py#141-179
4. **Year filtering & persistence:** Optionally filter transactions to a specific tax year and persist processed CSVs to `data/processed/` for traceability.@src/data_processing/processor.py#181-216

Future enhancements will extend step (3) to leverage deposit mapping for precise property attribution and to surface manual review queues based on `UNASSIGNED` rows.

### 5.1 Preliminary Parsing Rules for Bank Feed

1. **Income vs. Expense:** Treat rows with non-zero `credit_amount` as income entries and those with non-zero `debit_amount` as expenses. Amount sign should be normalized to positive values per class.
2. **Memo/property linkage:** Join `memo` text to `deposit_amount_map.csv` for property attribution; default to `UNASSIGNED` when no match is found and flag for manual review.
3. **Categorization hints:** Use `description` prefixes (e.g., "ACH Payment", "Signature Point of Sale") and merchant strings to seed expense category heuristics before falling back to existing keyword rules.
4. **Reference preservation:** Retain original `code`, `description`, and `reference` fields in processed output for reconciliation and audit support.
5. **Deduplication:** Identify potential duplicates via `(date, credit_amount, debit_amount, memo)` tuple comparison to prevent double counting.

## 6. Reporting Requirements

Annual reporting is handled by `TaxReporter`:

1. **Annual summary** computing total income, total expenses, net income, and category breakdowns for the selected tax year.@src/reporting/tax_reports.py#31-68
2. **Supporting artifacts** saved as PDFs in `data/reports/`, leveraging processed data to create audit-ready summaries.@src/reporting/tax_reports.py#69-72

Reports must surface:

1. Year, totals, and net income (Schedule E lines 3-21 alignment).
2. Expense breakdown by category/property, highlighting items requiring manual review.
3. Income source summaries (e.g., rent vs. subsidies) using memo/property metadata.

## 7. Functional Requirements

1. **Data ingestion:** Ability to ingest multiple raw files (CSV/XLSX) per period.
2. **Mapping application:** Apply memo/property match logic and flag transactions without definitive mapping.
3. **Validation:** Log missing required columns or malformed rows prior to processing.
4. **Reporting:** Generate PDF/CSV outputs for each tax year with breakdown tables and charts.
5. **Configuration:** Allow environment-driven configuration of data directories via `.env`.

## 8. Non-Functional Requirements

1. **Maintainability:** Keep modules under 300 lines and favor functional utilities where possible.
2. **Traceability:** Persist intermediate datasets so manual audits can reconcile outputs.
3. **Reliability:** Tests for processing and reporting modules covering major use cases.
4. **Security:** Handle local files only; no external network dependence without explicit approval.

## 9. Testing & QA

1. Unit tests for data cleaning, categorization, and annual summary calculations.
2. Integration tests covering end-to-end processing from raw sample files to report generation.
3. Fixture datasets should include edge cases: partial data, UNASSIGNED mappings, split payments.

## 10. Milestones

1. **M1 – Data Mapping Integration:** Implement deposit/property attribution using `deposit_amount_map.csv`; flag manual review items.
2. **M2 – Processing Enhancements:** Extend cleaning logic for multi-property datasets, add validation logging.
3. **M3 – Reporting Expansion:** Enhance PDF outputs with property-level summaries and manual review appendices.
4. **M4 – API/Automation (Optional):** Expose processing/reporting via FastAPI endpoints for automated workflows.
