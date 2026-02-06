# Per-Property Schedule E Worksheets

## Overview

The per-property Schedule E feature generates individual tax worksheets for each rental property and automatically aggregates them into a consolidated report for IRS filing. This makes tax preparation easier by providing both detailed property-level breakdowns and the combined totals needed for Schedule E (Form 1040).

## Features

### 1. Individual Property Schedule E Forms
- Generates a complete Schedule E for each property
- Includes all standard Schedule E lines (1-12):
  - Line 1: Rental income
  - Line 4: Insurance
  - Line 5: Mortgage interest
  - Line 7: Repairs and maintenance
  - Line 8: Property taxes
  - Line 9: Other expenses
  - Line 11: Total expenses
  - Line 12: Net income/loss

### 2. Aggregated Schedule E
- Automatically sums all property Schedule E forms
- Provides consolidated totals for IRS filing
- Includes property count and breakdown reference
- Generates both CSV and PDF formats

### 3. File Outputs

#### Per-Property CSV Files
Individual CSV files for each property:
```
data/reports/schedule_e_2025_118_W_Shields_St.csv
data/reports/schedule_e_2025_966_Kinsbury_Court.csv
data/reports/schedule_e_2025_41_26th_St.csv
```

#### Aggregated Files
```
data/reports/schedule_e_2025_aggregate.csv      # Summary CSV for IRS filing
data/reports/schedule_e_2025_detailed.pdf        # Comprehensive PDF with all properties
```

## Usage

### CLI Usage

Generate per-property Schedule E forms:
```bash
python -c "
from src.reporting.tax_reports import TaxReporter
reporter = TaxReporter()

# Generate individual property schedules
per_property = reporter.generate_per_property_schedule_e(year=2025)
print(f'Generated {len(per_property)} property schedules')
"
```

Generate aggregated Schedule E:
```bash
python -c "
from src.reporting.tax_reports import TaxReporter
reporter = TaxReporter()

# Generate aggregated schedule across all properties
aggregated = reporter.generate_aggregated_schedule_e(year=2025)
print(f'Total income: \${aggregated[\"1\"]:.2f}')
print(f'Total expenses: \${aggregated[\"11\"]:.2f}')
print(f'Net income: \${aggregated[\"12\"]:.2f}')
"
```

### API Usage

#### Generate Per-Property Schedule E

**Endpoint:** `POST /reports/schedule-e/per-property`

**Request Body:**
```json
{
  "year": 2025,
  "save_outputs": true
}
```

**Response:**
```json
{
  "118 W Shields St": {
    "property_name": "118 W Shields St",
    "1": 985.0,
    "4": 50.0,
    "5": 200.0,
    "7": 100.0,
    "8": 150.0,
    "9": 25.0,
    "11": 525.0,
    "12": 460.0
  },
  "966 Kinsbury Court": {
    "property_name": "966 Kinsbury Court",
    "1": 1300.0,
    ...
  }
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/reports/schedule-e/per-property" \
  -H "Content-Type: application/json" \
  -d '{"year": 2025, "save_outputs": true}'
```

#### Generate Aggregated Schedule E

**Endpoint:** `POST /reports/schedule-e/aggregate`

**Request Body:**
```json
{
  "year": 2025,
  "save_outputs": true
}
```

**Response:**
```json
{
  "1": 3385.0,
  "4": 150.0,
  "5": 600.0,
  "7": 300.0,
  "8": 450.0,
  "9": 75.0,
  "11": 1575.0,
  "12": 1810.0,
  "property_count": 3,
  "properties": ["118 W Shields St", "966 Kinsbury Court", "41 26th St"],
  "per_property_details": {...}
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/reports/schedule-e/aggregate" \
  -H "Content-Type: application/json" \
  -d '{"year": 2025, "save_outputs": true}'
```

### Web Dashboard Usage

1. Navigate to `http://localhost:8000/review`
2. In the "Generate reports" section, enter the tax year
3. Click one of the new buttons:
   - **📋 Per-Property Schedule E**: Generates individual property worksheets
   - **📊 Aggregated Schedule E**: Generates consolidated report + individual worksheets

The dashboard will display a success message with:
- Number of properties processed
- Total net income (for aggregated report)

## File Format Examples

### Per-Property CSV Format
```csv
Line,Description,Amount
1,Rental income,985.0
2,Royalties,0.0
3,Other income,0.0
4,Insurance,50.0
5,Mortgage interest,200.0
6,Other interest,0.0
7,Repairs,100.0
8,Taxes,150.0
9,Other expenses,25.0
10,Depreciation,0.0
11,Total expenses,525.0
12,Net income/loss,460.0
```

### Aggregated PDF Structure
```
Schedule E (Form 1040) - 2025
Supplemental Income and Loss

Aggregate Totals (3 Properties)
┌──────┬────────────────────┬────────────┐
│ Line │ Description        │ Amount     │
├──────┼────────────────────┼────────────┤
│ 1    │ Rental income      │ $3,385.00  │
│ 4    │ Insurance          │ $150.00    │
│ 5    │ Mortgage interest  │ $600.00    │
│ 7    │ Repairs            │ $300.00    │
│ 8    │ Taxes              │ $450.00    │
│ 9    │ Other expenses     │ $75.00     │
│ 11   │ Total expenses     │ $1,575.00  │
│ 12   │ Net income/loss    │ $1,810.00  │
└──────┴────────────────────┴────────────┘

Per-Property Breakdown

118 W Shields St
┌──────┬────────────────────┬────────────┐
│ Line │ Description        │ Amount     │
├──────┼────────────────────┼────────────┤
│ 1    │ Rental income      │ $985.00    │
│ ...  │ ...                │ ...        │
└──────┴────────────────────┴────────────┘

[Additional properties follow]
```

## Data Requirements

### Income Data
- Must have `property_name` field populated for each transaction
- Income is automatically grouped by property

### Expense Data
- Should have `property_name` field to allocate expenses to specific properties
- Without property assignment, expenses appear as $0 in per-property schedules
- Use the review dashboard to assign expenses to properties

### Assigning Expenses to Properties

To ensure expenses appear in per-property schedules:

1. **Via Review Dashboard:**
   - Navigate to the expense review table
   - Select the property from the dropdown for each expense
   - Save changes

2. **Via Bulk Import:**
   - Export the expense template
   - Add `property_name` column values in Excel
   - Re-import the CSV

## Best Practices

1. **Always Generate Both Reports:**
   - Per-property schedules for internal tracking
   - Aggregated schedule for IRS filing

2. **Verify Property Names:**
   - Ensure consistent property naming across income and expenses
   - Use the same name format for all transactions (e.g., "118 W Shields St" not "118 Shields")

3. **Review Unassigned Expenses:**
   - Check for expenses with no property assignment
   - These won't appear in per-property schedules

4. **Annual Workflow:**
   ```bash
   # 1. Process bank transactions
   python -m src.cli.app process-bank --year 2025

   # 2. Review and assign properties via dashboard
   # Visit http://localhost:8000/review

   # 3. Generate per-property schedules
   # Click "Per-Property Schedule E" button

   # 4. Generate aggregated schedule for filing
   # Click "Aggregated Schedule E" button

   # 5. Download reports for CPA
   # CSV files in data/reports/ directory
   ```

## Testing

Run the test suite:
```bash
pytest tests/test_tax_reporter.py::test_generate_per_property_schedule_e
pytest tests/test_tax_reporter.py::test_generate_aggregated_schedule_e
pytest tests/test_tax_reporter.py::test_per_property_schedule_e_csv_files_created
pytest tests/test_tax_reporter.py::test_aggregated_schedule_e_creates_files
```

## Technical Details

### Implementation Files
- `src/reporting/tax_reports.py`: Core reporting logic
  - `generate_per_property_schedule_e()`: Per-property generation
  - `generate_aggregated_schedule_e()`: Aggregation logic
  - `_generate_schedule_e_for_property()`: Single property Schedule E
  - `_save_detailed_schedule_e_pdf()`: PDF generation

- `src/api/server.py`: API endpoints
  - `POST /reports/schedule-e/per-property`
  - `POST /reports/schedule-e/aggregate`

- `src/api/templates/review.html`: Web UI
  - JavaScript functions: `triggerPerPropertyScheduleE()`, `triggerAggregatedScheduleE()`

### Expense Categorization Mapping

The system automatically maps expense categories to Schedule E lines:

| Category          | Schedule E Line | Description        |
|-------------------|----------------|--------------------|
| insurance         | 4              | Insurance          |
| mortgage          | 5              | Mortgage interest  |
| mortgage_interest | 5              | Mortgage interest  |
| maintenance       | 7              | Repairs            |
| repairs           | 7              | Repairs            |
| property_tax      | 8              | Taxes              |
| (all others)      | 9              | Other expenses     |

## Roadmap

Future enhancements planned:

- **Phase 3.1 (Next):**
  - Depreciation support (Schedule E Line 10)
  - Additional Schedule E lines (HOA fees, legal fees, supplies, travel)
  - Form 4562 generation (Depreciation and Amortization)

- **Phase 3.2:**
  - Multi-year property comparison
  - Year-over-year trend analysis
  - Property performance metrics

## Support

For issues or questions:
- GitHub Issues: https://github.com/rlust/lust-rentals-tax-reporting/issues
- Documentation: See `docs/ROADMAP.md` for full feature roadmap
