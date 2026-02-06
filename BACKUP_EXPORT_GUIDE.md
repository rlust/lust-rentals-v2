# Backup & Export Guide

## Overview

The Lust Rentals Tax Reporting application now includes comprehensive backup and export functionality to protect your data and create packages for external use (accountants, auditors, tax preparation).

## Features

### 1. **Full Data Backup**
- Creates a complete ZIP archive of all data
- Includes:
  - Raw transaction files
  - Processed database
  - Processed CSV exports
  - Generated reports (optional)
- Saved to: `data/backups/`
- Filename format: `lust_rentals_backup_YYYYMMDD_HHMMSS.zip`

### 2. **Database-Only Backup**
- Quick backup of just the processed database
- Smaller file size, faster creation
- Ideal for quick snapshots before major changes
- Filename format: `processed_db_backup_YYYYMMDD_HHMMSS.db`

### 3. **Accountant Export Package**
- Comprehensive package specifically formatted for accountants
- Year-specific data export
- Includes:
  - All income transactions (CSV)
  - All expense transactions (CSV)
  - Expenses broken down by property (one CSV per property)
  - Property summary report (income, expenses, net by property)
  - Database backup
  - All generated tax reports (PDF, Excel)
  - README.txt with file descriptions
- Automatically zipped and ready to email
- Filename format: `accountant_package_YYYY_YYYYMMDD_HHMMSS.zip`

### 4. **Database Table Export**
- Exports all database tables to CSV files
- Optional year filtering
- Creates separate directory with all exports
- Useful for custom analysis in Excel or other tools

## How to Use

### Via Dashboard (Recommended)

1. **Navigate to Dashboard**
   - Go to http://localhost:8002
   - Scroll to "💼 Backup & Export" section

2. **Select Export Year**
   - Set the year for year-specific exports (default: 2025)

3. **Choose Operation:**

   **Full Data Backup:**
   - Click "Create" next to "📦 Full Data Backup (ZIP)"
   - Wait for completion message
   - File saved to `data/backups/`

   **Database Only:**
   - Click "Create" next to "🗄️ Database Only Backup"
   - Quickest backup option

   **Accountant Package:**
   - Set desired year
   - Click "Create" next to "👔 Accountant Package"
   - Package will auto-download when ready
   - Also saved to `data/backups/`

   **Export Tables:**
   - Set desired year (or leave blank for all years)
   - Click "Export" next to "📋 Export Database Tables"
   - Creates directory with all CSV exports

### Via API

All backup operations are available via API endpoints:

```bash
# Full backup
curl -X POST "http://localhost:8002/backup/create?include_reports=true"

# Database only
curl -X POST "http://localhost:8002/backup/database"

# Accountant package
curl -X POST "http://localhost:8002/backup/export/accountant?year=2025"

# Export tables
curl -X POST "http://localhost:8002/backup/export/database?year=2025"

# List all backups
curl "http://localhost:8002/backup/list"

# Download specific backup
curl "http://localhost:8002/backup/download/backup_filename.zip" -O
```

## Accountant Package Contents

When you create an accountant package, it includes:

### Transaction Files
- **income_transactions_YYYY.csv**: All rental income for the year
  - Columns: date, amount, property_name, description, memo, mapping_status
  - Sorted by date and property

- **expense_transactions_YYYY.csv**: All expenses for the year
  - Columns: date, amount, property_name, category, description, confidence
  - Sorted by date, property, and category

### Property-Specific Files
- **expenses_PropertyName_YYYY.csv**: Expenses for each property
  - One file per property
  - Makes it easy for accountant to review property-by-property

### Summary Files
- **property_summary_YYYY.csv**: High-level overview
  - Shows total income, expenses, and net for each property
  - Perfect for quick property performance review

### Database & Reports
- **processed_database_YYYY.db**: Full SQLite database backup
  - Can be opened with SQLite tools for custom queries
  - Complete data integrity

- **All generated reports**: PDFs, Excel files, CSVs
  - Annual summary
  - Schedule E
  - Property reports
  - Expense breakdowns

### Documentation
- **README.txt**: Complete guide for your accountant
  - Explains each file
  - Describes data formats
  - Notes about categories and property types

## Best Practices

### Regular Backups
1. **Before Processing**: Create a backup before uploading new transaction files
2. **After Major Changes**: Backup after property assignments or categorization
3. **Monthly**: Create regular monthly backups for safety
4. **Year-End**: Full backup with reports before tax preparation

### For Accountants
1. **Create Package Early**: Generate package as soon as all transactions are reviewed
2. **Verify Data**: Review package contents before sending
3. **Include Notes**: Add any additional context in email or separate document
4. **Keep Copy**: Always keep a copy of what you send

### Storage
- Backups are stored in `data/backups/`
- Consider copying important backups to cloud storage (Dropbox, Google Drive)
- Keep at least 3 backup copies: local, external drive, cloud
- Backups are compressed (ZIP) to save space

## File Locations

```
data/
└── backups/
    ├── lust_rentals_backup_20251109_120000.zip          # Full backups
    ├── processed_db_backup_20251109_130000.db           # Database backups
    ├── accountant_package_2025_20251109_140000.zip      # Accountant packages
    └── exports_20251109_150000/                         # Table exports
        ├── processed_income_2025_*.csv
        ├── processed_expenses_2025_*.csv
        ├── properties_all_*.csv
        └── EXPORT_SUMMARY.txt
```

## Restore from Backup

### Manual Restore
1. Stop the server
2. Extract backup ZIP to `data/` directory
3. Verify directory structure matches
4. Restart server

### API Restore (Advanced)
```bash
curl -X POST "http://localhost:8002/backup/restore?backup_name=backup_filename.zip"
```

**⚠️ WARNING**: Restore operations overwrite existing data. A safety backup is created first.

## Troubleshooting

### Backup Creation Fails
- Check disk space (`data/backups/` directory)
- Verify database exists (`data/processed/processed.db`)
- Check server logs for detailed error messages

### Accountant Package Missing Data
- Ensure transactions are processed for the specified year
- Verify property assignments are saved
- Check that year parameter is correct

### Export Too Large
- Use database-only backup instead of full backup
- Export specific year instead of all years
- Compress files manually if needed

## Security Notes

- Backups contain sensitive financial data
- Do NOT store backups in public locations
- Use encrypted storage or password-protected ZIPs when sharing
- Delete old backups periodically (keep 3-6 months)
- When emailing to accountant, use secure file transfer if possible

## API Documentation

Full API documentation available at: http://localhost:8002/docs

Look for the "Backup & Export" section for:
- Request/response schemas
- Query parameters
- Error codes
- Example requests

## Support

For issues:
1. Check this guide first
2. Review server logs: Look for "ERROR" messages
3. Verify file permissions on `data/backups/` directory
4. Check API documentation for correct parameters

---

**Last Updated**: November 9, 2025
**Version**: 2.0
