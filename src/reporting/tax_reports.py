"""
Tax reporting module for Lust Rentals LLC.
Generates tax reports and schedules for IRS filing.
"""
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from fpdf import FPDF
from pandas import DataFrame

from src.categorization.category_utils import normalize_category, get_display_name
from src.data_processing.processor import FinancialDataProcessor


class TaxReporter:
    """Generates tax reports for Lust Rentals LLC."""

    def __init__(self, data_processor: Optional[FinancialDataProcessor] = None):
        """Initialize the tax reporter.

        Args:
            data_processor: Instance of FinancialDataProcessor. If None, creates a new one.
        """
        self.processor = data_processor or FinancialDataProcessor()
        self.reports_dir = self.processor.reports_dir
        self.current_year = datetime.now().year

    def generate_annual_summary(
        self, year: Optional[int] = None, save_to_file: bool = True
    ) -> Dict[str, float]:
        """Generate an annual summary of income and expenses.

        Args:
            year: The tax year. Defaults to the previous year.
            save_to_file: Whether to save the report to a file.

        Returns:
            Dictionary containing summary metrics
        """
        year = year or (self.current_year - 1)
        data = self._load_processed_data(year)

        income_df = data['income']
        expense_df = data['expenses']

        # Calculate totals
        total_income = income_df['amount'].sum()
        total_expenses = expense_df['amount'].sum()
        net_income = total_income - total_expenses

        property_breakdown = self._summarize_income_by_property(income_df)
        income_sources = (
            property_breakdown
            if property_breakdown
            else self._summarize_income_sources(income_df)
        )
        review_counts = self._summarize_mapping_status(income_df)
        unresolved_transactions = 0

        # Calculate expense breakdown with normalized categories
        if 'category' in expense_df.columns:
            # Normalize categories
            expense_df['category_normalized'] = expense_df['category'].apply(normalize_category)
            expense_df['category_display'] = expense_df['category_normalized'].apply(get_display_name)
            # Group by display name for the breakdown
            expense_breakdown = expense_df.groupby('category_display')['amount'].sum().to_dict()
        else:
            expense_breakdown = {'Uncategorized': total_expenses}

        # Calculate expense breakdown by property
        expense_by_property = self._summarize_expenses_by_property(expense_df)

        # Prepare summary
        summary = {
            'tax_year': year,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'net_income': net_income,
            'expense_breakdown': expense_breakdown,
            'expense_by_property': expense_by_property,
            'income_sources': income_sources,
            'property_breakdown': property_breakdown,
            'mapping_review_counts': review_counts,
            'unresolved_transaction_count': unresolved_transactions,
        }

        if save_to_file:
            self._save_summary_to_pdf(summary, year)

        return summary

    def _load_processed_data(self, year: int) -> Dict[str, DataFrame]:
        """Load processed income/expense data from the database."""
        return self.processor.load_processed_data(year)

    def _summarize_income_by_property(self, income_df: DataFrame) -> Dict[str, float]:
        """Summarize income by property using mapping metadata."""

        if 'property_name' not in income_df.columns or 'amount' not in income_df.columns:
            return {}

        decorated = income_df.copy()
        decorated['property_name'] = (
            decorated['property_name']
            .fillna('Unassigned')
            .replace('', 'Unassigned')
        )

        property_totals = (
            decorated.groupby('property_name')['amount']
            .sum()
            .sort_values(ascending=False)
        )

        return property_totals.round(2).to_dict()

    def _summarize_expenses_by_property(self, expense_df: DataFrame) -> Dict[str, Dict[str, float]]:
        """Summarize expenses by property and category.

        Args:
            expense_df: Expense DataFrame with property_name and category columns

        Returns:
            Nested dictionary: {property_name: {category: amount}}
        """
        if 'property_name' not in expense_df.columns or 'amount' not in expense_df.columns:
            return {}

        decorated = expense_df.copy()

        # Normalize categories
        if 'category' in decorated.columns:
            decorated['category_normalized'] = decorated['category'].apply(normalize_category)
            decorated['category_display'] = decorated['category_normalized'].apply(get_display_name)
        else:
            decorated['category_display'] = 'Uncategorized'

        # Fill missing property names
        decorated['property_name'] = (
            decorated['property_name']
            .fillna('Unassigned')
            .replace('', 'Unassigned')
        )

        # Group by property and category
        property_category_totals = (
            decorated.groupby(['property_name', 'category_display'])['amount']
            .sum()
        )

        # Convert to nested dictionary
        result = {}
        for (property_name, category), amount in property_category_totals.items():
            if property_name not in result:
                result[property_name] = {}
            result[property_name][category] = round(amount, 2)

        return result

    def _summarize_income_sources(self, income_df: DataFrame) -> Dict[str, float]:
        """Summarize income by source.

        Args:
            income_df: Processed income data

        Returns:
            Dictionary of income sources and amounts
        """
        if 'property_name' in income_df.columns:
            return self._summarize_income_by_property(income_df)
        if 'source' in income_df.columns:
            return income_df.groupby('source')['amount'].sum().to_dict()
        elif 'description' in income_df.columns:
            return {'Rental Income': income_df['amount'].sum()}
        else:
            return {'Income': income_df['amount'].sum()}

    def _summarize_mapping_status(self, income_df: DataFrame) -> Dict[str, int]:
        """Summarize mapping status counts for income rows."""

        if 'mapping_status' not in income_df.columns:
            return {}

        status_counts = (
            income_df['mapping_status']
            .fillna('mapping_missing')
            .value_counts()
            .to_dict()
        )

        return {status: int(count) for status, count in status_counts.items()}

    def _save_summary_to_pdf(self, summary: Dict, year: int) -> None:
        """Save the annual summary to a PDF file.

        Args:
            summary: Summary data
            year: Tax year
        """
        pdf = FPDF()
        pdf.add_page()
        
        # Title
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, f'Lust Rentals LLC - {year} Tax Year Summary', 0, 1, 'C')
        pdf.ln(10)
        
        # Summary section
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Financial Summary', 0, 1, 'L')
        pdf.set_font('Arial', '', 10)
        
        # Summary table
        col_width = 90
        row_height = 8
        
        # Table header
        pdf.set_fill_color(200, 220, 255)
        pdf.cell(col_width, row_height, 'Category', 1, 0, 'L', 1)
        pdf.cell(col_width, row_height, 'Amount ($)', 1, 1, 'R', 1)
        
        # Table rows
        pdf.set_fill_color(255, 255, 255)
        self._add_table_row(pdf, 'Total Income', summary['total_income'], col_width, row_height)

        property_breakdown = summary.get('property_breakdown') or {}
        if property_breakdown:
            pdf.ln(5)
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, 'Income by Property', 0, 1, 'L')
            pdf.set_font('Arial', '', 10)
            for property_name, amount in property_breakdown.items():
                self._add_table_row(pdf, f'  {property_name}', amount, col_width, row_height)

        # Expense breakdown by property
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Expense Breakdown by Property', 0, 1, 'L')
        pdf.set_font('Arial', '', 10)

        expense_by_property = summary.get('expense_by_property') or {}
        if expense_by_property:
            # Get sorted list of properties (same order as income breakdown if possible)
            if property_breakdown:
                # Use same order as income properties
                property_order = list(property_breakdown.keys())
                # Add any expense-only properties at the end
                for prop in expense_by_property.keys():
                    if prop not in property_order:
                        property_order.append(prop)
            else:
                # Sort by total expense amount descending
                property_totals = {
                    prop: sum(cats.values())
                    for prop, cats in expense_by_property.items()
                }
                property_order = sorted(
                    property_totals.keys(),
                    key=lambda x: property_totals[x],
                    reverse=True
                )

            for property_name in property_order:
                if property_name not in expense_by_property:
                    continue

                categories = expense_by_property[property_name]
                property_total = sum(categories.values())

                # Property header
                pdf.set_font('Arial', 'B', 10)
                self._add_table_row(pdf, f'  {property_name}', -property_total, col_width, row_height)

                # Category breakdown for this property
                pdf.set_font('Arial', '', 10)
                for category, amount in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                    self._add_table_row(pdf, f'    {category}', -amount, col_width, row_height)
        else:
            # Fallback to category-only breakdown if no property data
            for category, amount in summary['expense_breakdown'].items():
                self._add_table_row(pdf, f'  {category}', -amount, col_width, row_height)

        # Totals
        pdf.ln(2)
        pdf.set_font('Arial', 'B', 10)
        self._add_table_row(pdf, 'Total Expenses', -summary['total_expenses'], col_width, row_height)
        pdf.ln(5)
        
        # Net Income
        pdf.set_font('Arial', 'B', 12)
        net_income_text = 'Net Income' if summary['net_income'] >= 0 else 'Net Loss'
        self._add_table_row(pdf, net_income_text, summary['net_income'], col_width, row_height)

        review_counts = summary.get('mapping_review_counts') or {}
        unresolved_txns = int(summary.get('unresolved_transaction_count', 0))
        if review_counts or unresolved_txns:
            pdf.ln(5)
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, 'Data Quality Review', 0, 1, 'L')
            pdf.set_font('Arial', '', 10)
            for status, count in sorted(review_counts.items()):
                status_label = status.replace('_', ' ').title()
                pdf.cell(0, row_height, f'{status_label}: {int(count)}', 0, 1, 'L')
            pdf.cell(0, row_height, f'Unresolved bank transactions: {unresolved_txns}', 0, 1, 'L')
        
        # Save the PDF
        report_path = self.reports_dir / f'lust_rentals_tax_summary_{year}.pdf'
        pdf.output(str(report_path))
        
        # Generate and save charts
        self._generate_expense_chart(summary['expense_breakdown'], year)
    
    def _add_table_row(self, pdf, label: str, value: float, col_width: int, row_height: int) -> None:
        """Add a row to the PDF table.
        
        Args:
            pdf: FPDF instance
            label: Row label
            value: Numeric value
            col_width: Column width
            row_height: Row height
        """
        pdf.cell(col_width, row_height, label, 1, 0, 'L')
        pdf.cell(col_width, row_height, f'${abs(value):,.2f}', 1, 1, 'R')
    
    def _generate_expense_chart(self, expense_breakdown: Dict[str, float], year: int) -> None:
        """Generate a pie chart of expenses.

        Args:
            expense_breakdown: Dictionary of expense categories and amounts (already normalized)
            year: Tax year
        """
        if not expense_breakdown:
            return

        # Prepare data (labels are already display names from normalized categories)
        labels = list(expense_breakdown.keys())
        values = list(expense_breakdown.values())
        
        # Create pie chart
        plt.figure(figsize=(10, 6))
        plt.pie(values, labels=labels, autopct='%1.1f%%', startangle=90)
        plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        plt.title(f'Expense Breakdown - {year}')
        
        # Save the chart
        chart_path = self.reports_dir / f'expense_breakdown_{year}.png'
        plt.savefig(chart_path, bbox_inches='tight')
        plt.close()
    
    def generate_schedule_e(self, year: Optional[int] = None) -> Dict:
        """Generate IRS Schedule E (Supplemental Income and Loss) data.
        
        Args:
            year: Tax year. Defaults to previous year.
            
        Returns:
            Dictionary with Schedule E data
        """
        year = year or (self.current_year - 1)
        data = self._load_processed_data(year)
        
        income_df = data['income']
        expense_df = data['expenses']
        
        # Map expense categories to Schedule E line items
        schedule_e = {
            '1': income_df['amount'].sum(),  # Rental income
            '2': 0.0,  # Royalties
            '3': 0.0,  # Other income
            '4': 0.0,  # Insurance
            '5': 0.0,  # Mortgage interest
            '6': 0.0,  # Other interest
            '7': 0.0,  # Repairs
            '8': 0.0,  # Taxes
            '9': 0.0,  # Other expenses
            '10': 0.0, # Depreciation
            '11': 0.0, # Total expenses
            '12': 0.0  # Net income/loss
        }
        
        # Categorize expenses
        if 'category' in expense_df.columns:
            for _, row in expense_df.iterrows():
                category = row['category']
                amount = row['amount']
                
                if category == 'mortgage':
                    schedule_e['5'] += amount
                elif category == 'property_tax':
                    schedule_e['8'] += amount
                elif category == 'insurance':
                    schedule_e['4'] += amount
                elif category == 'maintenance':
                    schedule_e['7'] += amount
                else:
                    schedule_e['9'] += amount  # Other expenses
        else:
            # If no categories, put everything in 'Other expenses'
            schedule_e['9'] = expense_df['amount'].sum()
        
        # Calculate totals
        schedule_e['11'] = sum(schedule_e[str(i)] for i in range(4, 11))
        schedule_e['12'] = schedule_e['1'] - schedule_e['11']  # Net income/loss

        property_schedule = self._build_property_schedule(income_df)
        if not property_schedule.empty:
            property_schedule_path = self.reports_dir / f'schedule_e_property_summary_{year}.csv'
            property_schedule.to_csv(property_schedule_path, index=False)

        schedule_e['property_summary'] = property_schedule.to_dict('records')

        # Save to CSV
        schedule_df = pd.DataFrame(
            [{'Line': k, 'Description': self._get_schedule_e_description(k), 'Amount': v} 
             for k, v in schedule_e.items()]
        )
        
        schedule_path = self.reports_dir / f'schedule_e_{year}.csv'
        schedule_df.to_csv(schedule_path, index=False)
        
        return schedule_e

    def _build_property_schedule(self, income_df: DataFrame) -> DataFrame:
        """Construct property-level Schedule E summary."""

        if 'property_name' not in income_df.columns or income_df.empty:
            return pd.DataFrame()

        decorated = income_df.copy()
        decorated['property_name'] = (
            decorated['property_name']
            .fillna('Unassigned')
            .replace('', 'Unassigned')
        )

        income_totals = (
            decorated.groupby('property_name')['amount']
            .sum()
            .rename('rental_income')
        )

        transaction_counts = (
            decorated.groupby('property_name')['amount']
            .count()
            .rename('transaction_count')
        )

        mapping_status_counts = pd.DataFrame()
        if 'mapping_status' in decorated.columns:
            mapping_status_counts = (
                decorated.groupby(['property_name', 'mapping_status'])
                .size()
                .unstack(fill_value=0)
            )
        else:
            mapping_status_counts = pd.DataFrame(index=income_totals.index)

        merged = pd.concat([income_totals, transaction_counts, mapping_status_counts], axis=1).fillna(0)

        expected_statuses = ['mapped', 'manual_review', 'mapping_missing']
        for status in expected_statuses:
            if status not in merged.columns:
                merged[status] = 0

        merged = merged.reset_index()
        merged['rental_income'] = merged['rental_income'].round(2)
        merged = merged.sort_values('rental_income', ascending=False)

        return merged
    
    def _get_schedule_e_description(self, line_number: str) -> str:
        """Get description for Schedule E line items.

        Args:
            line_number: Schedule E line number as string

        Returns:
            Line item description
        """
        descriptions = {
            '1': 'Rental income',
            '2': 'Royalties',
            '3': 'Other income',
            '4': 'Insurance',
            '5': 'Mortgage interest',
            '6': 'Other interest',
            '7': 'Repairs',
            '8': 'Taxes',
            '9': 'Other expenses',
            '10': 'Depreciation',
            '11': 'Total expenses',
            '12': 'Net income/loss'
        }
        return descriptions.get(line_number, '')

    def generate_per_property_schedule_e(self, year: Optional[int] = None) -> Dict[str, Dict]:
        """Generate individual Schedule E forms for each property.

        Args:
            year: Tax year. Defaults to previous year.

        Returns:
            Dictionary mapping property names to their Schedule E data
        """
        year = year or (self.current_year - 1)
        data = self._load_processed_data(year)

        income_df = data['income']
        expense_df = data['expenses']

        # Get list of all properties
        properties = set()
        if 'property_name' in income_df.columns:
            properties.update(income_df['property_name'].dropna().unique())
        if 'property_name' in expense_df.columns:
            properties.update(expense_df['property_name'].dropna().unique())

        # Remove empty strings and 'Unassigned' from property list
        properties = {p for p in properties if p and str(p).strip() and str(p).lower() != 'unassigned'}

        per_property_schedules = {}

        for property_name in sorted(properties):
            schedule_e = self._generate_schedule_e_for_property(
                property_name, income_df, expense_df
            )
            per_property_schedules[property_name] = schedule_e

            # Save individual property Schedule E to CSV
            self._save_property_schedule_e_csv(property_name, schedule_e, year)

        return per_property_schedules

    def _generate_schedule_e_for_property(
        self, property_name: str, income_df: DataFrame, expense_df: DataFrame
    ) -> Dict:
        """Generate Schedule E data for a single property.

        Args:
            property_name: Name of the property
            income_df: Full income DataFrame
            expense_df: Full expense DataFrame

        Returns:
            Dictionary with Schedule E line items for the property
        """
        # Filter data for this property
        property_income = income_df[
            income_df.get('property_name', pd.Series(dtype=str)) == property_name
        ]
        property_expenses = expense_df[
            expense_df.get('property_name', pd.Series(dtype=str)) == property_name
        ]

        # Initialize Schedule E
        schedule_e = {
            'property_name': property_name,
            '1': property_income['amount'].sum() if not property_income.empty else 0.0,  # Rental income
            '2': 0.0,  # Royalties
            '3': 0.0,  # Other income
            '4': 0.0,  # Insurance
            '5': 0.0,  # Mortgage interest
            '6': 0.0,  # Other interest
            '7': 0.0,  # Repairs
            '8': 0.0,  # Taxes
            '9': 0.0,  # Other expenses
            '10': 0.0, # Depreciation
            '11': 0.0, # Total expenses
            '12': 0.0  # Net income/loss
        }

        # Categorize expenses by Schedule E line
        if not property_expenses.empty and 'category' in property_expenses.columns:
            for _, row in property_expenses.iterrows():
                category = row['category']
                amount = row['amount']

                if category == 'insurance':
                    schedule_e['4'] += amount
                elif category in ['mortgage', 'mortgage_interest']:
                    schedule_e['5'] += amount
                elif category in ['maintenance', 'repairs']:
                    schedule_e['7'] += amount
                elif category == 'property_tax':
                    schedule_e['8'] += amount
                else:
                    schedule_e['9'] += amount  # Other expenses

        # Calculate totals
        schedule_e['11'] = sum(schedule_e[str(i)] for i in range(4, 11))
        schedule_e['12'] = schedule_e['1'] - schedule_e['11']  # Net income/loss

        return schedule_e

    def _save_property_schedule_e_csv(
        self, property_name: str, schedule_e: Dict, year: int
    ) -> None:
        """Save a property's Schedule E to CSV file.

        Args:
            property_name: Name of the property
            schedule_e: Schedule E data dictionary
            year: Tax year
        """
        # Create a safe filename from property name
        safe_name = property_name.replace(' ', '_').replace('/', '_').replace('\\', '_')

        # Remove property_name from the data for CSV output
        csv_data = {k: v for k, v in schedule_e.items() if k != 'property_name'}

        schedule_df = pd.DataFrame([
            {
                'Line': k,
                'Description': self._get_schedule_e_description(k),
                'Amount': v
            }
            for k, v in csv_data.items()
        ])

        schedule_path = self.reports_dir / f'schedule_e_{year}_{safe_name}.csv'
        schedule_df.to_csv(schedule_path, index=False)

    def generate_aggregated_schedule_e(
        self, year: Optional[int] = None, save_to_file: bool = True
    ) -> Dict:
        """Generate aggregated Schedule E across all properties.

        This sums up all per-property Schedule E forms into a single consolidated report.

        Args:
            year: Tax year. Defaults to previous year.
            save_to_file: Whether to save to CSV file.

        Returns:
            Dictionary with aggregated Schedule E data
        """
        year = year or (self.current_year - 1)

        # Get per-property schedules
        per_property = self.generate_per_property_schedule_e(year)

        if not per_property:
            # No properties, return empty schedule
            return self.generate_schedule_e(year)

        # Aggregate across all properties
        aggregated = {
            '1': 0.0,  # Rental income
            '2': 0.0,  # Royalties
            '3': 0.0,  # Other income
            '4': 0.0,  # Insurance
            '5': 0.0,  # Mortgage interest
            '6': 0.0,  # Other interest
            '7': 0.0,  # Repairs
            '8': 0.0,  # Taxes
            '9': 0.0,  # Other expenses
            '10': 0.0, # Depreciation
            '11': 0.0, # Total expenses
            '12': 0.0  # Net income/loss
        }

        # Sum all properties
        for property_name, schedule in per_property.items():
            for line_num in aggregated.keys():
                aggregated[line_num] += schedule[line_num]

        # Add property breakdown for reference
        aggregated['properties'] = list(per_property.keys())
        aggregated['property_count'] = len(per_property)
        aggregated['per_property_details'] = per_property

        if save_to_file:
            # Save aggregated schedule
            schedule_df = pd.DataFrame([
                {
                    'Line': k,
                    'Description': self._get_schedule_e_description(k),
                    'Amount': v
                }
                for k, v in aggregated.items()
                if k in [str(i) for i in range(1, 13)]
            ])

            schedule_path = self.reports_dir / f'schedule_e_{year}_aggregate.csv'
            schedule_df.to_csv(schedule_path, index=False)

            # Also save a detailed breakdown with all properties
            self._save_detailed_schedule_e_pdf(per_property, aggregated, year)

        return aggregated

    def _save_detailed_schedule_e_pdf(
        self, per_property: Dict[str, Dict], aggregated: Dict, year: int
    ) -> None:
        """Save a detailed PDF with per-property and aggregated Schedule E.

        Args:
            per_property: Dictionary of per-property Schedule E data
            aggregated: Aggregated Schedule E data
            year: Tax year
        """
        pdf = FPDF()
        pdf.add_page()

        # Title
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, f'Schedule E (Form 1040) - {year}', 0, 1, 'C')
        pdf.cell(0, 10, 'Supplemental Income and Loss', 0, 1, 'C')
        pdf.ln(5)

        # Summary section
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, f'Aggregate Totals ({len(per_property)} Properties)', 0, 1, 'L')
        pdf.ln(2)

        # Aggregated table
        self._add_schedule_e_table(pdf, aggregated)

        # Add expense category breakdown
        data = self._load_processed_data(year)
        expense_df = data['expenses']
        if not expense_df.empty and 'category' in expense_df.columns:
            pdf.ln(5)
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, 'Detailed Expense Breakdown by Category', 0, 1, 'L')
            pdf.ln(2)
            self._add_expense_category_breakdown(pdf, expense_df)

        pdf.ln(10)

        # Per-property breakdown
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, 'Per-Property Breakdown', 0, 1, 'L')
        pdf.ln(5)

        for property_name in sorted(per_property.keys()):
            schedule = per_property[property_name]

            # Property header
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 8, property_name, 0, 1, 'L')
            pdf.ln(2)

            # Property schedule table
            self._add_schedule_e_table(pdf, schedule)

            # Add property-specific expense breakdown if available
            if not expense_df.empty and 'property_name' in expense_df.columns and 'category' in expense_df.columns:
                property_expenses = expense_df[expense_df['property_name'] == property_name]
                if not property_expenses.empty:
                    pdf.ln(3)
                    pdf.set_font('Arial', 'I', 10)
                    pdf.cell(0, 6, f'Expense Categories for {property_name}:', 0, 1, 'L')
                    pdf.ln(1)
                    self._add_expense_category_breakdown(pdf, property_expenses)

            pdf.ln(8)

            # Add new page if needed
            if pdf.get_y() > 240:
                pdf.add_page()

        # Save PDF
        pdf_path = self.reports_dir / f'schedule_e_{year}_detailed.pdf'
        pdf.output(str(pdf_path))

    def _add_expense_category_breakdown(self, pdf: FPDF, expense_df: DataFrame) -> None:
        """Add expense category breakdown table to PDF.

        Args:
            pdf: FPDF instance
            expense_df: Expense DataFrame with category column
        """
        # Normalize categories if not already done
        if 'category_display' not in expense_df.columns and 'category' in expense_df.columns:
            expense_df = expense_df.copy()
            expense_df['category_normalized'] = expense_df['category'].apply(normalize_category)
            expense_df['category_display'] = expense_df['category_normalized'].apply(get_display_name)

        # Calculate category totals using display names
        category_column = 'category_display' if 'category_display' in expense_df.columns else 'category'
        category_totals = expense_df.groupby(category_column)['amount'].agg(['sum', 'count']).sort_values('sum', ascending=False)

        col_widths = [100, 50, 40]
        row_height = 7

        # Table header
        pdf.set_font('Arial', 'B', 10)
        pdf.set_fill_color(255, 220, 180)
        pdf.cell(col_widths[0], row_height, 'Category', 1, 0, 'L', 1)
        pdf.cell(col_widths[1], row_height, 'Total Amount', 1, 0, 'R', 1)
        pdf.cell(col_widths[2], row_height, 'Count', 1, 1, 'C', 1)

        # Table rows
        pdf.set_font('Arial', '', 9)
        for category, row in category_totals.iterrows():
            category_name = category if category and str(category).strip() else 'Uncategorized'
            amount = abs(row['sum'])
            count = int(row['count'])

            pdf.cell(col_widths[0], row_height, category_name, 1, 0, 'L')
            pdf.cell(col_widths[1], row_height, f'${amount:,.2f}', 1, 0, 'R')
            pdf.cell(col_widths[2], row_height, str(count), 1, 1, 'C')

            # Add new page if needed
            if pdf.get_y() > 250:
                pdf.add_page()
                # Re-add header
                pdf.set_font('Arial', 'B', 10)
                pdf.set_fill_color(255, 220, 180)
                pdf.cell(col_widths[0], row_height, 'Category', 1, 0, 'L', 1)
                pdf.cell(col_widths[1], row_height, 'Total Amount', 1, 0, 'R', 1)
                pdf.cell(col_widths[2], row_height, 'Count', 1, 1, 'C', 1)
                pdf.set_font('Arial', '', 9)

        # Total row
        pdf.set_font('Arial', 'B', 9)
        total_amount = abs(expense_df['amount'].sum())
        total_count = len(expense_df)
        pdf.cell(col_widths[0], row_height, 'TOTAL', 1, 0, 'L')
        pdf.cell(col_widths[1], row_height, f'${total_amount:,.2f}', 1, 0, 'R')
        pdf.cell(col_widths[2], row_height, str(total_count), 1, 1, 'C')

    def _add_schedule_e_table(self, pdf: FPDF, schedule_e: Dict) -> None:
        """Add a Schedule E table to the PDF.

        Args:
            pdf: FPDF instance
            schedule_e: Schedule E data dictionary
        """
        col_widths = [20, 110, 50]
        row_height = 7

        # Table header
        pdf.set_font('Arial', 'B', 10)
        pdf.set_fill_color(200, 220, 255)
        pdf.cell(col_widths[0], row_height, 'Line', 1, 0, 'C', 1)
        pdf.cell(col_widths[1], row_height, 'Description', 1, 0, 'L', 1)
        pdf.cell(col_widths[2], row_height, 'Amount', 1, 1, 'R', 1)

        # Table rows
        pdf.set_font('Arial', '', 9)
        for line_num in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']:
            if line_num not in schedule_e:
                continue

            amount = schedule_e[line_num]
            description = self._get_schedule_e_description(line_num)

            # Highlight totals
            if line_num in ['11', '12']:
                pdf.set_font('Arial', 'B', 9)
            else:
                pdf.set_font('Arial', '', 9)

            pdf.cell(col_widths[0], row_height, line_num, 1, 0, 'C')
            pdf.cell(col_widths[1], row_height, description, 1, 0, 'L')
            pdf.cell(col_widths[2], row_height, f'${amount:,.2f}', 1, 1, 'R')


def main():
    """
    Main function to generate tax reports.

    DEPRECATED: This module entrypoint is deprecated.
    Please use the CLI instead:
        python -m src.cli.app generate-reports --year 2025

    This entrypoint will be removed in a future version.
    """
    import warnings
    warnings.warn(
        "Running tax_reports.py as a module is deprecated. "
        "Please use: python -m src.cli.app generate-reports --year YYYY",
        DeprecationWarning,
        stacklevel=2
    )

    try:
        reporter = TaxReporter()

        # Generate reports for the previous year
        year = datetime.now().year - 1

        print(f"\n⚠️  DEPRECATION WARNING ⚠️")
        print(f"This entrypoint is deprecated. Use the CLI instead:")
        print(f"    python -m src.cli.app generate-reports --year {year}\n")

        print(f"Generating tax reports for {year}...")

        # Generate summary report
        summary = reporter.generate_annual_summary(year)
        print(f"Generated annual summary: {reporter.reports_dir}/lust_rentals_tax_summary_{year}.pdf")

        # Generate Schedule E
        schedule_e = reporter.generate_schedule_e(year)
        print(f"Generated Schedule E: {reporter.reports_dir}/schedule_e_{year}.csv")

        print("\nTax preparation complete!")
        print(f"Net income/loss for {year}: ${summary['net_income']:,.2f}")

    except Exception as e:
        print(f"Error generating tax reports: {str(e)}")


if __name__ == "__main__":
    main()
