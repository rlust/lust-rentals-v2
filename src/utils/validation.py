"""
Data validation utilities for pre-processing checks.

This module provides comprehensive validation for bank transaction files
before processing, catching issues early to prevent bad data ingestion.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """Represents a single validation issue found during data checks."""

    severity: str  # 'error' | 'warning' | 'info'
    category: str  # 'duplicate' | 'date' | 'amount' | 'format' | 'missing'
    message: str
    transaction_id: Optional[str] = None
    row_number: Optional[int] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "transaction_id": self.transaction_id,
            "row_number": self.row_number,
            "details": self.details or {}
        }


@dataclass
class ValidationResult:
    """Results from validating a data file."""

    valid: bool
    error_count: int
    warning_count: int
    info_count: int
    issues: List[ValidationIssue]
    file_stats: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "valid": self.valid,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "issues": [issue.to_dict() for issue in self.issues],
            "file_stats": self.file_stats,
            "recommendation": self._get_recommendation()
        }

    def _get_recommendation(self) -> str:
        """Get user-friendly recommendation based on validation results."""
        if self.error_count > 0:
            return f"Fix {self.error_count} error(s) before processing. Data ingestion will likely fail."
        elif self.warning_count > 10:
            return f"Found {self.warning_count} warnings. Review issues before processing to ensure data quality."
        elif self.warning_count > 0:
            return f"Found {self.warning_count} warning(s). Consider reviewing before processing."
        else:
            return "Validation passed! Safe to process."


class DataValidator:
    """
    Validates financial data files before processing.

    Performs comprehensive checks including:
    - Duplicate transaction detection
    - Date range validation
    - Amount anomaly detection
    - Required column verification
    - Format consistency checks
    """

    def __init__(self):
        """Initialize the validator."""
        self.logger = logging.getLogger(self.__class__.__name__)

    def validate_bank_file(
        self,
        file_path: Path,
        year: int,
        duplicate_threshold: float = 1.0
    ) -> ValidationResult:
        """
        Validate bank transaction file before processing.

        Args:
            file_path: Path to the bank transaction file (CSV or Excel)
            year: Expected year for transactions
            duplicate_threshold: Days within which same amount+memo is considered duplicate

        Returns:
            ValidationResult with all issues found
        """
        issues: List[ValidationIssue] = []

        try:
            # Load data
            if file_path.suffix.lower() in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path)
            else:
                df = pd.read_csv(file_path)

            self.logger.info(f"Loaded {len(df)} rows from {file_path}")

            # Collect file statistics
            file_stats = {
                "total_rows": len(df),
                "columns": list(df.columns),
                "file_size_bytes": file_path.stat().st_size,
                "file_type": file_path.suffix
            }

            # Check 1: Required columns
            issues.extend(self._check_required_columns(df))

            # If critical columns are missing, stop further validation
            error_count = sum(1 for i in issues if i.severity == 'error')
            if error_count > 0:
                return ValidationResult(
                    valid=False,
                    error_count=error_count,
                    warning_count=0,
                    info_count=0,
                    issues=issues,
                    file_stats=file_stats
                )

            # Normalize column names for consistent checking
            df = self._normalize_columns(df)

            # Check 2: Duplicate transactions
            issues.extend(self._check_duplicates(df, duplicate_threshold))

            # Check 3: Date range validation
            issues.extend(self._check_date_range(df, year))

            # Check 4: Amount anomalies
            issues.extend(self._check_amount_anomalies(df))

            # Check 5: Missing critical data
            issues.extend(self._check_missing_data(df))

            # Check 6: Format consistency
            issues.extend(self._check_format_consistency(df))

            # Update file stats with processed info
            file_stats.update({
                "date_range": self._get_date_range(df),
                "amount_range": self._get_amount_range(df),
                "transaction_count": len(df)
            })

        except Exception as e:
            self.logger.exception("Error during validation")
            issues.append(ValidationIssue(
                severity='error',
                category='format',
                message=f"Failed to read or parse file: {str(e)}",
                details={"exception": str(e)}
            ))
            file_stats = {"error": str(e)}

        # Summarize results
        error_count = sum(1 for i in issues if i.severity == 'error')
        warning_count = sum(1 for i in issues if i.severity == 'warning')
        info_count = sum(1 for i in issues if i.severity == 'info')

        return ValidationResult(
            valid=(error_count == 0),
            error_count=error_count,
            warning_count=warning_count,
            info_count=info_count,
            issues=issues,
            file_stats=file_stats
        )

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names to snake_case."""
        df.columns = [
            col.lower().replace(' ', '_').replace('-', '_')
            for col in df.columns
        ]
        return df

    def _check_required_columns(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Check for required columns in the dataframe."""
        issues = []

        # Possible column name variations
        required_fields = {
            'date': ['date', 'transaction_date', 'post_date', 'posted_date'],
            'amount': ['amount', 'transaction_amount', 'value', 'debit', 'credit'],
            'description': ['description', 'memo', 'details', 'transaction_details']
        }

        df_cols_lower = [col.lower().replace(' ', '_').replace('-', '_') for col in df.columns]

        for field, variations in required_fields.items():
            found = any(var in df_cols_lower for var in variations)
            if not found:
                issues.append(ValidationIssue(
                    severity='error',
                    category='format',
                    message=f"Missing required field: '{field}'. Expected one of: {', '.join(variations)}",
                    details={"expected_variations": variations, "found_columns": list(df.columns)}
                ))

        return issues

    def _check_duplicates(self, df: pd.DataFrame, threshold_days: float) -> List[ValidationIssue]:
        """Check for duplicate transactions."""
        issues = []

        # Try to identify date and amount columns
        date_col = self._find_column(df, ['date', 'transaction_date', 'post_date'])
        amount_col = self._find_column(df, ['amount', 'transaction_amount', 'value'])
        memo_col = self._find_column(df, ['description', 'memo', 'details'])

        if not date_col or not amount_col:
            return issues

        # Parse dates
        df_check = df.copy()
        try:
            df_check[date_col] = pd.to_datetime(df_check[date_col])
        except Exception as e:
            self.logger.warning(f"Could not parse dates for duplicate check: {e}")
            return issues

        # Check for exact duplicates (same date, amount, memo)
        if memo_col:
            dup_cols = [date_col, amount_col, memo_col]
        else:
            dup_cols = [date_col, amount_col]

        duplicates = df_check[df_check.duplicated(subset=dup_cols, keep=False)]

        if len(duplicates) > 0:
            # Group duplicates
            for _, group in duplicates.groupby(dup_cols):
                if len(group) > 1:
                    row = group.iloc[0]
                    issues.append(ValidationIssue(
                        severity='warning',
                        category='duplicate',
                        message=f"Potential duplicate transaction: {row[date_col].strftime('%Y-%m-%d')} - ${row[amount_col]:.2f}",
                        row_number=group.index[0] + 2,  # +2 for header and 0-index
                        details={
                            "date": str(row[date_col]),
                            "amount": float(row[amount_col]),
                            "memo": str(row[memo_col]) if memo_col else None,
                            "duplicate_count": len(group),
                            "rows": [int(idx) + 2 for idx in group.index]
                        }
                    ))

        return issues

    def _check_date_range(self, df: pd.DataFrame, year: int) -> List[ValidationIssue]:
        """Check if dates are within expected year."""
        issues = []

        date_col = self._find_column(df, ['date', 'transaction_date', 'post_date'])
        if not date_col:
            return issues

        try:
            df_check = df.copy()
            df_check[date_col] = pd.to_datetime(df_check[date_col])

            # Check for dates outside target year
            out_of_range = df_check[df_check[date_col].dt.year != year]

            if len(out_of_range) > 0:
                # Summarize by year
                year_counts = out_of_range[date_col].dt.year.value_counts()

                for wrong_year, count in year_counts.items():
                    issues.append(ValidationIssue(
                        severity='error' if count > len(df) * 0.1 else 'warning',
                        category='date',
                        message=f"Found {count} transaction(s) dated in {wrong_year} (expected {year})",
                        details={
                            "expected_year": year,
                            "found_year": int(wrong_year),
                            "count": int(count)
                        }
                    ))

            # Check for future dates
            future_dates = df_check[df_check[date_col] > pd.Timestamp.now()]
            if len(future_dates) > 0:
                issues.append(ValidationIssue(
                    severity='warning',
                    category='date',
                    message=f"Found {len(future_dates)} transaction(s) with future dates",
                    details={"count": len(future_dates)}
                ))

        except Exception as e:
            issues.append(ValidationIssue(
                severity='warning',
                category='date',
                message=f"Could not validate date range: {str(e)}"
            ))

        return issues

    def _check_amount_anomalies(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Check for unusual amounts (outliers)."""
        issues = []

        amount_col = self._find_column(df, ['amount', 'transaction_amount', 'value'])
        if not amount_col:
            return issues

        try:
            amounts = df[amount_col].abs()

            # Remove zero amounts for statistics
            non_zero = amounts[amounts > 0]

            if len(non_zero) == 0:
                issues.append(ValidationIssue(
                    severity='error',
                    category='amount',
                    message="All transaction amounts are zero",
                ))
                return issues

            # Calculate statistics
            mean = non_zero.mean()
            std = non_zero.std()
            median = non_zero.median()

            # Find outliers (>3 standard deviations from mean)
            if std > 0:
                outliers = df[amounts > (mean + 3 * std)]

                if len(outliers) > 0:
                    for idx, row in outliers.head(5).iterrows():  # Report first 5
                        issues.append(ValidationIssue(
                            severity='warning',
                            category='amount',
                            message=f"Unusually large amount: ${abs(row[amount_col]):.2f} (>3 std dev from mean of ${mean:.2f})",
                            row_number=int(idx) + 2,
                            details={
                                "amount": float(abs(row[amount_col])),
                                "mean": float(mean),
                                "std": float(std),
                                "median": float(median)
                            }
                        ))

                    if len(outliers) > 5:
                        issues.append(ValidationIssue(
                            severity='info',
                            category='amount',
                            message=f"Total of {len(outliers)} outlier amounts found (showing first 5)",
                            details={"total_outliers": len(outliers)}
                        ))

            # Check for negative income or positive expenses (if we can determine direction)
            credit_col = self._find_column(df, ['credit'])
            debit_col = self._find_column(df, ['debit'])

            if credit_col and debit_col:
                # Negative credits (income) are suspicious
                neg_credits = df[(df[credit_col].notna()) & (df[credit_col] < 0)]
                if len(neg_credits) > 0:
                    issues.append(ValidationIssue(
                        severity='warning',
                        category='amount',
                        message=f"Found {len(neg_credits)} transaction(s) with negative credit amounts",
                        details={"count": len(neg_credits)}
                    ))

                # Negative debits (expenses) are suspicious
                neg_debits = df[(df[debit_col].notna()) & (df[debit_col] < 0)]
                if len(neg_debits) > 0:
                    issues.append(ValidationIssue(
                        severity='warning',
                        category='amount',
                        message=f"Found {len(neg_debits)} transaction(s) with negative debit amounts",
                        details={"count": len(neg_debits)}
                    ))

        except Exception as e:
            self.logger.warning(f"Could not check amount anomalies: {e}")

        return issues

    def _check_missing_data(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Check for missing critical data."""
        issues = []

        # Check for missing dates
        date_col = self._find_column(df, ['date', 'transaction_date', 'post_date'])
        if date_col:
            missing_dates = df[df[date_col].isna()]
            if len(missing_dates) > 0:
                issues.append(ValidationIssue(
                    severity='error',
                    category='missing',
                    message=f"Found {len(missing_dates)} transaction(s) with missing dates",
                    details={"count": len(missing_dates), "rows": [int(idx) + 2 for idx in missing_dates.index[:10]]}
                ))

        # Check for missing amounts
        amount_col = self._find_column(df, ['amount', 'transaction_amount', 'value'])
        if amount_col:
            missing_amounts = df[df[amount_col].isna()]
            if len(missing_amounts) > 0:
                issues.append(ValidationIssue(
                    severity='error',
                    category='missing',
                    message=f"Found {len(missing_amounts)} transaction(s) with missing amounts",
                    details={"count": len(missing_amounts), "rows": [int(idx) + 2 for idx in missing_amounts.index[:10]]}
                ))

        # Check for missing descriptions (warning only)
        memo_col = self._find_column(df, ['description', 'memo', 'details'])
        if memo_col:
            missing_memos = df[df[memo_col].isna() | (df[memo_col].str.strip() == '')]
            if len(missing_memos) > len(df) * 0.1:  # >10% missing
                issues.append(ValidationIssue(
                    severity='warning',
                    category='missing',
                    message=f"Found {len(missing_memos)} transaction(s) with missing or empty descriptions",
                    details={"count": len(missing_memos)}
                ))

        return issues

    def _check_format_consistency(self, df: pd.DataFrame) -> List[ValidationIssue]:
        """Check for format consistency issues."""
        issues = []

        # Check date format consistency
        date_col = self._find_column(df, ['date', 'transaction_date', 'post_date'])
        if date_col:
            try:
                parsed = pd.to_datetime(df[date_col], errors='coerce')
                unparseable = df[parsed.isna() & df[date_col].notna()]

                if len(unparseable) > 0:
                    issues.append(ValidationIssue(
                        severity='error',
                        category='format',
                        message=f"Found {len(unparseable)} transaction(s) with unparseable dates",
                        details={
                            "count": len(unparseable),
                            "examples": [str(val) for val in unparseable[date_col].head(3).tolist()]
                        }
                    ))
            except Exception as e:
                self.logger.warning(f"Could not check date format: {e}")

        return issues

    def _find_column(self, df: pd.DataFrame, possible_names: List[str]) -> Optional[str]:
        """Find a column by checking multiple possible names."""
        df_cols_lower = [col.lower() for col in df.columns]

        for name in possible_names:
            if name.lower() in df_cols_lower:
                idx = df_cols_lower.index(name.lower())
                return df.columns[idx]

        return None

    def _get_date_range(self, df: pd.DataFrame) -> Optional[Dict[str, str]]:
        """Get the date range from the dataframe."""
        date_col = self._find_column(df, ['date', 'transaction_date', 'post_date'])
        if not date_col:
            return None

        try:
            dates = pd.to_datetime(df[date_col], errors='coerce')
            valid_dates = dates.dropna()

            if len(valid_dates) > 0:
                return {
                    "min": valid_dates.min().strftime('%Y-%m-%d'),
                    "max": valid_dates.max().strftime('%Y-%m-%d')
                }
        except Exception:
            pass

        return None

    def _get_amount_range(self, df: pd.DataFrame) -> Optional[Dict[str, float]]:
        """Get the amount range from the dataframe."""
        amount_col = self._find_column(df, ['amount', 'transaction_amount', 'value'])
        if not amount_col:
            return None

        try:
            amounts = df[amount_col].abs()
            valid_amounts = amounts.dropna()

            if len(valid_amounts) > 0:
                return {
                    "min": float(valid_amounts.min()),
                    "max": float(valid_amounts.max()),
                    "mean": float(valid_amounts.mean()),
                    "median": float(valid_amounts.median())
                }
        except Exception:
            pass

        return None
