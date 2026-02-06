"""Data backup and export utilities for Lust Rentals Tax Reporting."""
from __future__ import annotations

import logging
import shutil
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class DataBackupManager:
    """Manages data backups and exports for the tax reporting system."""

    def __init__(self, data_dir: Path):
        """
        Initialize the backup manager.

        Args:
            data_dir: Base data directory containing raw, processed, and reports folders
        """
        self.data_dir = Path(data_dir)
        self.backup_dir = self.data_dir / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self.raw_dir = self.data_dir / "raw"
        self.processed_dir = self.data_dir / "processed"
        self.reports_dir = self.data_dir / "reports"

        logger.info(f"Initialized DataBackupManager with data_dir: {self.data_dir}")

    def create_full_backup(self, include_reports: bool = True) -> Dict[str, str]:
        """
        Create a complete backup of all data including database, CSVs, and optionally reports.

        Args:
            include_reports: Whether to include generated reports in the backup

        Returns:
            Dictionary with backup information including file path and timestamp
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"lust_rentals_backup_{timestamp}.zip"
        backup_path = self.backup_dir / backup_name

        logger.info(f"Creating full backup: {backup_name}")

        try:
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Backup raw data files
                if self.raw_dir.exists():
                    for file in self.raw_dir.rglob('*'):
                        if file.is_file():
                            arcname = file.relative_to(self.data_dir)
                            zipf.write(file, arcname)
                            logger.debug(f"Added to backup: {arcname}")

                # Backup processed data
                if self.processed_dir.exists():
                    for file in self.processed_dir.rglob('*'):
                        if file.is_file():
                            arcname = file.relative_to(self.data_dir)
                            zipf.write(file, arcname)
                            logger.debug(f"Added to backup: {arcname}")

                # Backup reports if requested
                if include_reports and self.reports_dir.exists():
                    for file in self.reports_dir.rglob('*'):
                        if file.is_file():
                            arcname = file.relative_to(self.data_dir)
                            zipf.write(file, arcname)
                            logger.debug(f"Added to backup: {arcname}")

                # Create backup manifest
                manifest = self._create_backup_manifest(timestamp, include_reports)
                zipf.writestr("BACKUP_MANIFEST.txt", manifest)

            backup_size = backup_path.stat().st_size
            logger.info(f"Backup created successfully: {backup_path} ({backup_size / 1024 / 1024:.2f} MB)")

            return {
                "status": "success",
                "backup_file": str(backup_path),
                "backup_name": backup_name,
                "timestamp": timestamp,
                "size_mb": round(backup_size / 1024 / 1024, 2),
                "include_reports": include_reports
            }

        except Exception as e:
            logger.error(f"Error creating backup: {e}", exc_info=True)
            raise

    def export_database_tables(self, year: Optional[int] = None) -> Dict[str, str]:
        """
        Export all database tables to CSV files for external analysis.

        Args:
            year: Optional year to filter data (if None, exports all data)

        Returns:
            Dictionary with paths to exported files
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_subdir = self.backup_dir / f"exports_{timestamp}"
        export_subdir.mkdir(parents=True, exist_ok=True)

        db_path = self.processed_dir / "processed.db"

        if not db_path.exists():
            raise FileNotFoundError(f"Database not found at {db_path}")

        logger.info(f"Exporting database tables to {export_subdir}")

        exported_files = {}

        try:
            with sqlite3.connect(db_path) as conn:
                # Get all tables
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                tables = [row[0] for row in cursor.fetchall()]

                logger.info(f"Found {len(tables)} tables to export")

                for table in tables:
                    try:
                        # Read table into DataFrame
                        query = f"SELECT * FROM {table}"

                        # Add year filter for date-based tables
                        if year and table in ['processed_income', 'processed_expenses']:
                            query += f" WHERE strftime('%Y', date) = '{year}'"

                        df = pd.read_sql_query(query, conn)

                        if df.empty:
                            logger.warning(f"Table {table} is empty, skipping export")
                            continue

                        # Export to CSV
                        csv_filename = f"{table}_{year if year else 'all'}_{timestamp}.csv"
                        csv_path = export_subdir / csv_filename
                        df.to_csv(csv_path, index=False)

                        exported_files[table] = str(csv_path)
                        logger.info(f"Exported {table}: {len(df)} rows -> {csv_filename}")

                    except Exception as e:
                        logger.error(f"Error exporting table {table}: {e}")
                        continue

            # Create export summary
            summary_path = export_subdir / "EXPORT_SUMMARY.txt"
            summary = self._create_export_summary(exported_files, year)
            summary_path.write_text(summary)

            logger.info(f"Database export complete: {len(exported_files)} tables exported")

            return {
                "status": "success",
                "export_dir": str(export_subdir),
                "timestamp": timestamp,
                "year": year,
                "tables_exported": len(exported_files),
                "files": exported_files
            }

        except Exception as e:
            logger.error(f"Error exporting database: {e}", exc_info=True)
            raise

    def backup_database_only(self) -> Dict[str, str]:
        """
        Create a backup of just the processed database file.

        Returns:
            Dictionary with backup information
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_path = self.processed_dir / "processed.db"

        if not db_path.exists():
            raise FileNotFoundError(f"Database not found at {db_path}")

        backup_name = f"processed_db_backup_{timestamp}.db"
        backup_path = self.backup_dir / backup_name

        logger.info(f"Creating database backup: {backup_name}")

        try:
            shutil.copy2(db_path, backup_path)
            backup_size = backup_path.stat().st_size

            logger.info(f"Database backup created: {backup_path} ({backup_size / 1024 / 1024:.2f} MB)")

            return {
                "status": "success",
                "backup_file": str(backup_path),
                "backup_name": backup_name,
                "timestamp": timestamp,
                "size_mb": round(backup_size / 1024 / 1024, 2)
            }

        except Exception as e:
            logger.error(f"Error backing up database: {e}", exc_info=True)
            raise

    def export_for_accountant(self, year: int) -> Dict[str, str]:
        """
        Create a comprehensive export package for your accountant.

        Includes:
        - All income transactions
        - All expense transactions grouped by property
        - Property summary report
        - Database backup
        - Generated tax reports

        Args:
            year: Tax year to export

        Returns:
            Dictionary with export package information
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        package_name = f"accountant_package_{year}_{timestamp}"
        package_dir = self.backup_dir / package_name
        package_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Creating accountant export package for {year}")

        try:
            db_path = self.processed_dir / "processed.db"

            if not db_path.exists():
                raise FileNotFoundError(f"Database not found at {db_path}")

            exported_items = []

            with sqlite3.connect(db_path) as conn:
                # Export income transactions
                income_df = pd.read_sql_query(
                    f"SELECT * FROM processed_income WHERE strftime('%Y', date) = '{year}' ORDER BY date, property_name",
                    conn
                )
                if not income_df.empty:
                    income_path = package_dir / f"income_transactions_{year}.csv"
                    income_df.to_csv(income_path, index=False)
                    exported_items.append(("Income Transactions", str(income_path), len(income_df)))

                # Export expenses transactions
                expenses_df = pd.read_sql_query(
                    f"SELECT * FROM processed_expenses WHERE strftime('%Y', date) = '{year}' ORDER BY date, property_name, category",
                    conn
                )
                if not expenses_df.empty:
                    expenses_path = package_dir / f"expense_transactions_{year}.csv"
                    expenses_df.to_csv(expenses_path, index=False)
                    exported_items.append(("Expense Transactions", str(expenses_path), len(expenses_df)))

                # Export expenses grouped by property
                if not expenses_df.empty and 'property_name' in expenses_df.columns:
                    for prop in expenses_df['property_name'].unique():
                        if prop is None or pd.isna(prop):
                            continue
                        prop_expenses = expenses_df[expenses_df['property_name'] == prop]
                        safe_prop_name = str(prop).replace(' ', '_').replace('/', '_')
                        prop_path = package_dir / f"expenses_{safe_prop_name}_{year}.csv"
                        prop_expenses.to_csv(prop_path, index=False)
                        exported_items.append((f"Expenses - {prop}", str(prop_path), len(prop_expenses)))

                # Create property summary
                summary_data = []
                for prop in income_df['property_name'].unique() if not income_df.empty else []:
                    prop_income = income_df[income_df['property_name'] == prop]['amount'].sum()
                    prop_expenses = expenses_df[expenses_df['property_name'] == prop]['amount'].sum() if not expenses_df.empty else 0
                    summary_data.append({
                        'Property': prop,
                        'Total Income': prop_income,
                        'Total Expenses': prop_expenses,
                        'Net Income': prop_income - prop_expenses
                    })

                if summary_data:
                    summary_df = pd.DataFrame(summary_data)
                    summary_path = package_dir / f"property_summary_{year}.csv"
                    summary_df.to_csv(summary_path, index=False)
                    exported_items.append(("Property Summary", str(summary_path), len(summary_df)))

            # Copy database backup
            db_backup_path = package_dir / f"processed_database_{year}.db"
            shutil.copy2(db_path, db_backup_path)
            db_size = db_backup_path.stat().st_size
            exported_items.append(("Database Backup", str(db_backup_path), f"{db_size / 1024 / 1024:.2f} MB"))

            # Copy generated reports if they exist
            if self.reports_dir.exists():
                for report_file in self.reports_dir.glob(f"*{year}*"):
                    if report_file.is_file():
                        dest_path = package_dir / report_file.name
                        shutil.copy2(report_file, dest_path)
                        exported_items.append(("Report", str(dest_path), report_file.stat().st_size))

            # Create README for accountant
            readme = self._create_accountant_readme(year, exported_items)
            readme_path = package_dir / "README.txt"
            readme_path.write_text(readme)

            # Create ZIP archive
            zip_name = f"{package_name}.zip"
            zip_path = self.backup_dir / zip_name

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file in package_dir.rglob('*'):
                    if file.is_file():
                        arcname = file.relative_to(package_dir)
                        zipf.write(file, arcname)

            # Clean up unzipped directory
            shutil.rmtree(package_dir)

            zip_size = zip_path.stat().st_size

            logger.info(f"Accountant package created: {zip_path} ({zip_size / 1024 / 1024:.2f} MB)")

            return {
                "status": "success",
                "package_file": str(zip_path),
                "package_name": zip_name,
                "year": year,
                "timestamp": timestamp,
                "size_mb": round(zip_size / 1024 / 1024, 2),
                "items_exported": len(exported_items)
            }

        except Exception as e:
            logger.error(f"Error creating accountant package: {e}", exc_info=True)
            raise

    def list_backups(self) -> List[Dict]:
        """
        List all available backups.

        Returns:
            List of backup information dictionaries
        """
        backups = []

        if not self.backup_dir.exists():
            return backups

        for backup_file in sorted(self.backup_dir.glob("*.zip"), reverse=True):
            backups.append({
                "name": backup_file.name,
                "path": str(backup_file),
                "size_mb": round(backup_file.stat().st_size / 1024 / 1024, 2),
                "created": datetime.fromtimestamp(backup_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })

        for db_file in sorted(self.backup_dir.glob("*.db"), reverse=True):
            backups.append({
                "name": db_file.name,
                "path": str(db_file),
                "size_mb": round(db_file.stat().st_size / 1024 / 1024, 2),
                "created": datetime.fromtimestamp(db_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })

        return backups

    def restore_backup(self, backup_path: str) -> Dict[str, str]:
        """
        Restore data from a backup file.

        Args:
            backup_path: Path to the backup ZIP file

        Returns:
            Dictionary with restore information
        """
        backup_file = Path(backup_path)

        if not backup_file.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        logger.info(f"Restoring backup from: {backup_file}")

        # Create a safety backup before restoring
        safety_backup = self.create_full_backup(include_reports=True)
        logger.info(f"Created safety backup: {safety_backup['backup_file']}")

        try:
            with zipfile.ZipFile(backup_file, 'r') as zipf:
                # Extract to data directory
                zipf.extractall(self.data_dir)

            logger.info("Backup restored successfully")

            return {
                "status": "success",
                "restored_from": str(backup_file),
                "safety_backup": safety_backup['backup_file']
            }

        except Exception as e:
            logger.error(f"Error restoring backup: {e}", exc_info=True)
            raise

    def _create_backup_manifest(self, timestamp: str, include_reports: bool) -> str:
        """Create a manifest file for the backup."""
        manifest_lines = [
            "LUST RENTALS TAX REPORTING - BACKUP MANIFEST",
            "=" * 50,
            f"Backup Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Timestamp: {timestamp}",
            f"Include Reports: {include_reports}",
            "",
            "CONTENTS:",
            "- Raw transaction data files",
            "- Processed database (processed.db)",
            "- Processed CSV files",
        ]

        if include_reports:
            manifest_lines.append("- Generated tax reports")

        manifest_lines.extend([
            "",
            "RESTORE INSTRUCTIONS:",
            "1. Extract this ZIP file to your data directory",
            "2. Ensure the directory structure is preserved",
            "3. Restart the application",
            "",
            "For assistance, see documentation or contact support."
        ])

        return "\n".join(manifest_lines)

    def _create_export_summary(self, exported_files: Dict[str, str], year: Optional[int]) -> str:
        """Create a summary file for database exports."""
        summary_lines = [
            "DATABASE EXPORT SUMMARY",
            "=" * 50,
            f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Year Filter: {year if year else 'All Years'}",
            f"Tables Exported: {len(exported_files)}",
            "",
            "EXPORTED FILES:",
        ]

        for table, filepath in exported_files.items():
            filename = Path(filepath).name
            summary_lines.append(f"  - {table}: {filename}")

        return "\n".join(summary_lines)

    def _create_accountant_readme(self, year: int, exported_items: List) -> str:
        """Create README file for accountant package."""
        readme_lines = [
            f"LUST RENTALS TAX REPORTING - ACCOUNTANT PACKAGE {year}",
            "=" * 60,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "CONTENTS:",
            ""
        ]

        for item_type, filepath, info in exported_items:
            filename = Path(filepath).name
            if isinstance(info, int):
                readme_lines.append(f"  {item_type}: {filename} ({info} records)")
            else:
                readme_lines.append(f"  {item_type}: {filename} ({info})")

        readme_lines.extend([
            "",
            "FILE DESCRIPTIONS:",
            "",
            "income_transactions_*.csv:",
            "  - All rental income transactions for the year",
            "  - Grouped by property",
            "  - Includes dates, amounts, and property assignments",
            "",
            "expense_transactions_*.csv:",
            "  - All expense transactions for the year",
            "  - Includes categories (repairs, maintenance, utilities, etc.)",
            "  - Property assignments included",
            "",
            "expenses_*_*.csv:",
            "  - Expenses broken down by individual property",
            "  - One file per property for easy review",
            "",
            "property_summary_*.csv:",
            "  - High-level summary showing income, expenses, and net for each property",
            "  - Use for quick overview of property performance",
            "",
            "processed_database_*.db:",
            "  - Complete SQLite database backup",
            "  - Can be opened with SQLite tools for custom queries",
            "",
            "NOTES:",
            "- All amounts are in USD",
            "- Dates are in YYYY-MM-DD format",
            "- Categories match IRS Schedule E line items",
            "- 'Lust Rentals LLC' entries are business-level expenses (Schedule C)",
            "",
            "For questions about this data, please contact Randy Lust."
        ])

        return "\n".join(readme_lines)


def create_backup(data_dir: Path, include_reports: bool = True) -> Dict[str, str]:
    """
    Convenience function to create a full backup.

    Args:
        data_dir: Data directory path
        include_reports: Whether to include generated reports

    Returns:
        Backup information dictionary
    """
    manager = DataBackupManager(data_dir)
    return manager.create_full_backup(include_reports)


def export_for_accountant(data_dir: Path, year: int) -> Dict[str, str]:
    """
    Convenience function to create accountant export package.

    Args:
        data_dir: Data directory path
        year: Tax year to export

    Returns:
        Export package information dictionary
    """
    manager = DataBackupManager(data_dir)
    return manager.export_for_accountant(year)
