"""
Simplified Property Income and Expense Reports

This module provides simplified reporting functionality that shows only
Income and Expense by each property, available in both PDF and Excel formats.
"""

import os
import logging
from typing import Dict, List, Tuple
from datetime import datetime
from fpdf import FPDF as FPDF2
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows

from pathlib import Path

from src.data_processing.processor import FinancialDataProcessor
from src.utils.config import load_config
from src.utils.date_helpers import safe_format_date

# Use FPDF2 (fpdf2 package) for PDF generation
FPDF = FPDF2

logger = logging.getLogger(__name__)


class PropertyReportGenerator:
    """Generates simplified income and expense reports by property."""

    def __init__(self, data_dir: Path = None):
        """
        Initialize the property report generator.

        Args:
            data_dir: Base directory for data files
        """
        config = load_config()
        self.data_dir = data_dir or config.data_dir
        self.processor = FinancialDataProcessor(data_dir=self.data_dir)
        self.reports_dir = os.path.join(self.data_dir, "reports")
        os.makedirs(self.reports_dir, exist_ok=True)

    def get_property_summary(self, year: int) -> Dict:
        """
        Get income and expense summary by property.

        Args:
            year: Tax year to generate report for

        Returns:
            Dictionary containing property summaries with detailed expense types and income entries
        """
        logger.info(f"Generating property summary for year {year}")

        # Process financial data
        result = self.processor.process_financials(year)
        income_df = result["income"]
        expenses_df = result["expenses"]

        # Calculate income by property
        income_by_property = {}
        if not income_df.empty and 'property_name' in income_df.columns:
            income_summary = income_df.groupby('property_name')['amount'].sum()
            income_by_property = income_summary.to_dict()

        # Calculate expenses by property and expense type
        expenses_by_property = {}
        expenses_by_property_and_type = {}
        if not expenses_df.empty and 'property_name' in expenses_df.columns:
            # Total expenses by property
            expense_summary = expenses_df.groupby('property_name')['amount'].sum()
            expenses_by_property = expense_summary.to_dict()

            # Expenses grouped by property and category (expense type)
            if 'category' in expenses_df.columns:
                expense_detail = expenses_df.groupby(['property_name', 'category'])['amount'].sum()
                for (prop, category), amount in expense_detail.items():
                    if prop not in expenses_by_property_and_type:
                        expenses_by_property_and_type[prop] = []
                    expenses_by_property_and_type[prop].append({
                        'type': category,
                        'amount': amount
                    })
                # Sort expense types by amount (descending) for each property
                for prop in expenses_by_property_and_type:
                    expenses_by_property_and_type[prop].sort(key=lambda x: x['amount'], reverse=True)

        # Get income entries by property with dates
        income_entries_by_property = {}
        if not income_df.empty and 'property_name' in income_df.columns:
            # Ensure we have date column
            date_col = None
            for col in income_df.columns:
                if 'date' in col.lower():
                    date_col = col
                    break

            if date_col:
                income_with_dates = income_df[[date_col, 'property_name', 'amount']].copy()
                # Sort by date
                income_with_dates = income_with_dates.sort_values(date_col)

                for prop in income_with_dates['property_name'].unique():
                    prop_income = income_with_dates[income_with_dates['property_name'] == prop]
                    income_entries_by_property[prop] = [
                        {
                            'date': row[date_col],
                            'amount': row['amount']
                        }
                        for _, row in prop_income.iterrows()
                    ]

        # Get expense entries by property with dates and types
        expense_entries_by_property = {}
        if not expenses_df.empty and 'property_name' in expenses_df.columns:
            # Ensure we have date column
            date_col = None
            for col in expenses_df.columns:
                if 'date' in col.lower():
                    date_col = col
                    break

            if date_col and 'category' in expenses_df.columns:
                expenses_with_dates = expenses_df[[date_col, 'property_name', 'category', 'amount']].copy()
                # Sort by date
                expenses_with_dates = expenses_with_dates.sort_values(date_col)

                for prop in expenses_with_dates['property_name'].unique():
                    prop_expenses = expenses_with_dates[expenses_with_dates['property_name'] == prop]
                    expense_entries_by_property[prop] = [
                        {
                            'date': row[date_col],
                            'type': row['category'],
                            'amount': row['amount']
                        }
                        for _, row in prop_expenses.iterrows()
                    ]

        # Get all unique properties
        all_properties = set(list(income_by_property.keys()) + list(expenses_by_property.keys()))

        # Build property summaries
        property_data = []
        total_income = 0
        total_expenses = 0

        for property_name in sorted(all_properties):
            income = income_by_property.get(property_name, 0)
            expenses = expenses_by_property.get(property_name, 0)
            net = income - expenses

            property_data.append({
                'property': property_name,
                'income': income,
                'expenses': expenses,
                'net': net,
                'expense_types': expenses_by_property_and_type.get(property_name, []),
                'income_entries': income_entries_by_property.get(property_name, []),
                'expense_entries': expense_entries_by_property.get(property_name, [])
            })

            total_income += income
            total_expenses += expenses

        return {
            'year': year,
            'properties': property_data,
            'total_income': total_income,
            'total_expenses': total_expenses,
            'total_net': total_income - total_expenses
        }

    def generate_pdf_report(self, year: int, save_to_file: bool = True) -> Tuple[str, Dict]:
        """
        Generate a PDF report showing detailed expenses by type and income by date for each property.

        Args:
            year: Tax year to generate report for
            save_to_file: Whether to save the PDF to a file

        Returns:
            Tuple of (file_path, summary_data)
        """
        logger.info(f"Generating property PDF report for year {year}")

        # Get property summary data
        summary = self.get_property_summary(year)

        # Create PDF
        pdf = FPDF()
        pdf.add_page()

        # Title
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, 'Lust Rentals', 0, 1, 'C')
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 10, f'Property Income & Expense Report - {year}', 0, 1, 'C')
        pdf.ln(5)

        # Expenses by Property and Type Section
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'EXPENSES BY PROPERTY AND TYPE', 0, 1, 'L')

        # Table header for expenses
        pdf.set_font('Arial', 'B', 10)
        pdf.set_fill_color(37, 99, 235)  # Blue header
        pdf.set_text_color(255, 255, 255)  # White text
        pdf.cell(65, 8, 'Prop Name', 1, 0, 'L', True)
        pdf.cell(70, 8, 'Expense Type', 1, 0, 'L', True)
        pdf.cell(55, 8, 'Debit Amount (Sum)', 1, 1, 'R', True)
        pdf.set_text_color(0, 0, 0)  # Reset to black

        # Property expense details
        pdf.set_font('Arial', '', 9)
        grand_total_expenses = 0
        for prop in summary['properties']:
            if not prop['expense_types']:
                continue

            # First expense type row includes property name
            first_expense = prop['expense_types'][0]
            pdf.cell(65, 7, prop['property'][:30], 1, 0, 'L')
            pdf.cell(70, 7, first_expense['type'][:35], 1, 0, 'L')
            pdf.cell(55, 7, f"${first_expense['amount']:,.2f}", 1, 1, 'R')

            # Remaining expense types (property name blank)
            for expense in prop['expense_types'][1:]:
                pdf.cell(65, 7, '', 1, 0, 'L')
                pdf.cell(70, 7, expense['type'][:35], 1, 0, 'L')
                pdf.cell(55, 7, f"${expense['amount']:,.2f}", 1, 1, 'R')

            # Property total row
            pdf.set_font('Arial', 'B', 9)
            pdf.set_fill_color(229, 231, 235)  # Light gray
            pdf.cell(65, 7, f"{prop['property'][:25]} Total", 1, 0, 'L', True)
            pdf.cell(70, 7, '', 1, 0, 'L', True)
            pdf.cell(55, 7, f"${prop['expenses']:,.2f}", 1, 1, 'R', True)
            pdf.set_font('Arial', '', 9)
            grand_total_expenses += prop['expenses']

        # Grand total for expenses
        pdf.set_font('Arial', 'B', 10)
        pdf.set_fill_color(209, 213, 219)  # Darker gray
        pdf.cell(65, 8, 'GRAND TOTAL', 1, 0, 'L', True)
        pdf.cell(70, 8, '', 1, 0, 'L', True)
        pdf.cell(55, 8, f"${grand_total_expenses:,.2f}", 1, 1, 'R', True)
        pdf.ln(5)

        # Check if we need a new page
        if pdf.get_y() > 200:
            pdf.add_page()

        # Income by Property and Date Section
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'INCOME BY PROPERTY AND DATE', 0, 1, 'L')

        # Table header for income
        pdf.set_font('Arial', 'B', 10)
        pdf.set_fill_color(37, 99, 235)  # Blue header
        pdf.set_text_color(255, 255, 255)  # White text
        pdf.cell(65, 8, 'Prop Name', 1, 0, 'L', True)
        pdf.cell(70, 8, 'Deposit Date', 1, 0, 'L', True)
        pdf.cell(55, 8, 'Credit Amount', 1, 1, 'R', True)
        pdf.set_text_color(0, 0, 0)  # Reset to black

        # Property income details
        pdf.set_font('Arial', '', 9)
        grand_total_income = 0
        for prop in summary['properties']:
            if not prop['income_entries']:
                continue

            # Check if we need a new page
            if pdf.get_y() > 250:
                pdf.add_page()
                # Reprint header
                pdf.set_font('Arial', 'B', 10)
                pdf.set_fill_color(37, 99, 235)
                pdf.set_text_color(255, 255, 255)
                pdf.cell(65, 8, 'Prop Name', 1, 0, 'L', True)
                pdf.cell(70, 8, 'Deposit Date', 1, 0, 'L', True)
                pdf.cell(55, 8, 'Credit Amount', 1, 1, 'R', True)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font('Arial', '', 9)

            # First income entry includes property name
            first_income = prop['income_entries'][0]
            date_str = safe_format_date(first_income['date'])
            pdf.cell(65, 7, prop['property'][:30], 1, 0, 'L')
            pdf.cell(70, 7, date_str, 1, 0, 'L')
            pdf.cell(55, 7, f"${first_income['amount']:,.2f}", 1, 1, 'R')

            # Remaining income entries (property name blank)
            for income in prop['income_entries'][1:]:
                if pdf.get_y() > 260:
                    pdf.add_page()
                    # Reprint header
                    pdf.set_font('Arial', 'B', 10)
                    pdf.set_fill_color(37, 99, 235)
                    pdf.set_text_color(255, 255, 255)
                    pdf.cell(65, 8, 'Prop Name', 1, 0, 'L', True)
                    pdf.cell(70, 8, 'Deposit Date', 1, 0, 'L', True)
                    pdf.cell(55, 8, 'Credit Amount', 1, 1, 'R', True)
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font('Arial', '', 9)

                date_str = safe_format_date(income['date'])
                pdf.cell(65, 7, '', 1, 0, 'L')
                pdf.cell(70, 7, date_str, 1, 0, 'L')
                pdf.cell(55, 7, f"${income['amount']:,.2f}", 1, 1, 'R')

            # Property total row
            pdf.set_font('Arial', 'B', 9)
            pdf.set_fill_color(229, 231, 235)  # Light gray
            pdf.cell(65, 7, f"{prop['property'][:25]} Total", 1, 0, 'L', True)
            pdf.cell(70, 7, '', 1, 0, 'L', True)
            pdf.cell(55, 7, f"${prop['income']:,.2f}", 1, 1, 'R', True)
            pdf.set_font('Arial', '', 9)
            grand_total_income += prop['income']

        # Grand total for income
        pdf.set_font('Arial', 'B', 10)
        pdf.set_fill_color(209, 213, 219)  # Darker gray
        pdf.cell(65, 8, 'GRAND TOTAL', 1, 0, 'L', True)
        pdf.cell(70, 8, '', 1, 0, 'L', True)
        pdf.cell(55, 8, f"${grand_total_income:,.2f}", 1, 1, 'R', True)
        pdf.ln(10)

        # ========== NEW SECTION: Expenses by Property, Date and Type ==========
        pdf.add_page()
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'EXPENSES BY PROPERTY, DATE AND TYPE', 0, 1, 'L')

        # Table header for expense entries
        pdf.set_font('Arial', 'B', 10)
        pdf.set_fill_color(37, 99, 235)  # Blue header
        pdf.set_text_color(255, 255, 255)  # White text
        pdf.cell(50, 8, 'Prop Name', 1, 0, 'L', True)
        pdf.cell(45, 8, 'Expense Date', 1, 0, 'L', True)
        pdf.cell(50, 8, 'Expense Type', 1, 0, 'L', True)
        pdf.cell(45, 8, 'Debit Amount', 1, 1, 'R', True)
        pdf.set_text_color(0, 0, 0)  # Reset to black

        # Property expense entry details
        pdf.set_font('Arial', '', 9)
        grand_total_expenses_detailed = 0
        for prop in summary['properties']:
            if not prop['expense_entries']:
                continue

            # Check if we need a new page
            if pdf.get_y() > 250:
                pdf.add_page()
                # Reprint header
                pdf.set_font('Arial', 'B', 10)
                pdf.set_fill_color(37, 99, 235)
                pdf.set_text_color(255, 255, 255)
                pdf.cell(50, 8, 'Prop Name', 1, 0, 'L', True)
                pdf.cell(45, 8, 'Expense Date', 1, 0, 'L', True)
                pdf.cell(50, 8, 'Expense Type', 1, 0, 'L', True)
                pdf.cell(45, 8, 'Debit Amount', 1, 1, 'R', True)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font('Arial', '', 9)

            # First expense entry row includes property name
            first_expense = prop['expense_entries'][0]
            date_str = safe_format_date(first_expense['date'])
            pdf.cell(50, 7, prop['property'][:25], 1, 0, 'L')
            pdf.cell(45, 7, date_str, 1, 0, 'L')
            pdf.cell(50, 7, first_expense['type'][:25], 1, 0, 'L')
            pdf.cell(45, 7, f"${first_expense['amount']:,.2f}", 1, 1, 'R')

            # Remaining expense entries (property name blank)
            for expense in prop['expense_entries'][1:]:
                if pdf.get_y() > 260:
                    pdf.add_page()
                    # Reprint header
                    pdf.set_font('Arial', 'B', 10)
                    pdf.set_fill_color(37, 99, 235)
                    pdf.set_text_color(255, 255, 255)
                    pdf.cell(50, 8, 'Prop Name', 1, 0, 'L', True)
                    pdf.cell(45, 8, 'Expense Date', 1, 0, 'L', True)
                    pdf.cell(50, 8, 'Expense Type', 1, 0, 'L', True)
                    pdf.cell(45, 8, 'Debit Amount', 1, 1, 'R', True)
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font('Arial', '', 9)

                date_str = safe_format_date(expense['date'])
                pdf.cell(50, 7, '', 1, 0, 'L')
                pdf.cell(45, 7, date_str, 1, 0, 'L')
                pdf.cell(50, 7, expense['type'][:25], 1, 0, 'L')
                pdf.cell(45, 7, f"${expense['amount']:,.2f}", 1, 1, 'R')

            # Property total row
            pdf.set_font('Arial', 'B', 9)
            pdf.set_fill_color(229, 231, 235)  # Light gray
            pdf.cell(50, 7, f"{prop['property'][:20]} Total", 1, 0, 'L', True)
            pdf.cell(45, 7, '', 1, 0, 'L', True)
            pdf.cell(50, 7, '', 1, 0, 'L', True)
            pdf.cell(45, 7, f"${prop['expenses']:,.2f}", 1, 1, 'R', True)
            pdf.set_font('Arial', '', 9)
            grand_total_expenses_detailed += prop['expenses']

        # Grand total for expenses
        pdf.set_font('Arial', 'B', 10)
        pdf.set_fill_color(209, 213, 219)  # Darker gray
        pdf.cell(50, 8, 'GRAND TOTAL', 1, 0, 'L', True)
        pdf.cell(45, 8, '', 1, 0, 'L', True)
        pdf.cell(50, 8, '', 1, 0, 'L', True)
        pdf.cell(45, 8, f"${grand_total_expenses_detailed:,.2f}", 1, 1, 'R', True)
        pdf.ln(10)

        # Overall Summary
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'OVERALL SUMMARY', 0, 1, 'L')
        pdf.set_font('Arial', '', 10)

        pdf.cell(80, 8, 'Total Income:', 0, 0)
        pdf.cell(0, 8, f"${summary['total_income']:,.2f}", 0, 1)

        pdf.cell(80, 8, 'Total Expenses:', 0, 0)
        pdf.cell(0, 8, f"${summary['total_expenses']:,.2f}", 0, 1)

        pdf.cell(80, 8, 'Net Income:', 0, 0)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, f"${summary['total_net']:,.2f}", 0, 1)

        # Footer
        pdf.ln(10)
        pdf.set_font('Arial', 'I', 8)
        pdf.cell(0, 5, f'Report generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1, 'C')

        # Save file
        file_path = None
        if save_to_file:
            file_path = os.path.join(self.reports_dir, f'property_report_{year}.pdf')
            pdf.output(file_path)
            logger.info(f"Property PDF report saved to: {file_path}")

        return file_path, summary

    def generate_excel_report(self, year: int, save_to_file: bool = True) -> Tuple[str, Dict]:
        """
        Generate an Excel report showing detailed expenses by type and income by date for each property.

        Args:
            year: Tax year to generate report for
            save_to_file: Whether to save the Excel file

        Returns:
            Tuple of (file_path, summary_data)
        """
        logger.info(f"Generating property Excel report for year {year}")

        # Get property summary data
        summary = self.get_property_summary(year)

        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = f"Property Report {year}"

        # Define styles
        header_font = Font(name='Arial', size=14, bold=True)
        title_font = Font(name='Arial', size=11, bold=True)
        section_font = Font(name='Arial', size=10, bold=True)
        header_fill = PatternFill(start_color='2563EB', end_color='2563EB', fill_type='solid')
        total_fill = PatternFill(start_color='E5E7EB', end_color='E5E7EB', fill_type='solid')
        white_font = Font(name='Arial', size=10, bold=True, color='FFFFFF')
        bold_font = Font(name='Arial', size=10, bold=True)
        currency_format = '_($* #,##0.00_);_($* (#,##0.00);_($* "-"??_);_(@_)'
        date_format = 'mm/dd/yyyy'
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

        # Title
        ws['A1'] = 'Lust Rentals'
        ws['A1'].font = header_font
        ws['A2'] = f'Property Income & Expense Report - {year}'
        ws['A2'].font = Font(name='Arial', size=11)

        row = 4

        # Expenses by Property and Type Section
        ws[f'A{row}'] = 'EXPENSES BY PROPERTY AND TYPE'
        ws[f'A{row}'].font = title_font
        ws.merge_cells(f'A{row}:C{row}')
        row += 1

        # Table headers for expenses
        headers = ['Prop Name', 'Expense Type', 'Debit Amount (Sum)']
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = white_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = thin_border
        row += 1

        # Property expense details
        grand_total_expenses = 0
        for prop in summary['properties']:
            if not prop['expense_types']:
                continue

            # First expense type row includes property name
            first_expense = prop['expense_types'][0]
            ws.cell(row=row, column=1, value=prop['property'])
            ws.cell(row=row, column=2, value=first_expense['type'])
            ws.cell(row=row, column=3, value=first_expense['amount'])

            # Apply formatting
            for col in range(1, 4):
                cell = ws.cell(row=row, column=col)
                cell.border = thin_border
                if col == 3:
                    cell.number_format = currency_format
            row += 1

            # Remaining expense types (property name blank)
            for expense in prop['expense_types'][1:]:
                ws.cell(row=row, column=1, value='')
                ws.cell(row=row, column=2, value=expense['type'])
                ws.cell(row=row, column=3, value=expense['amount'])

                for col in range(1, 4):
                    cell = ws.cell(row=row, column=col)
                    cell.border = thin_border
                    if col == 3:
                        cell.number_format = currency_format
                row += 1

            # Property total row
            ws.cell(row=row, column=1, value=f"{prop['property']} Total")
            ws.cell(row=row, column=2, value='')
            ws.cell(row=row, column=3, value=prop['expenses'])

            for col in range(1, 4):
                cell = ws.cell(row=row, column=col)
                cell.font = bold_font
                cell.fill = total_fill
                cell.border = thin_border
                if col == 3:
                    cell.number_format = currency_format
            row += 1
            grand_total_expenses += prop['expenses']

        # Grand total for expenses
        ws.cell(row=row, column=1, value='GRAND TOTAL')
        ws.cell(row=row, column=2, value='')
        ws.cell(row=row, column=3, value=grand_total_expenses)
        for col in range(1, 4):
            cell = ws.cell(row=row, column=col)
            cell.font = Font(name='Arial', size=10, bold=True)
            cell.fill = PatternFill(start_color='D1D5DB', end_color='D1D5DB', fill_type='solid')
            cell.border = thin_border
            if col == 3:
                cell.number_format = currency_format
        row += 2

        # Income by Property and Date Section
        ws[f'A{row}'] = 'INCOME BY PROPERTY AND DATE'
        ws[f'A{row}'].font = title_font
        ws.merge_cells(f'A{row}:C{row}')
        row += 1

        # Table headers for income
        headers = ['Prop Name', 'Deposit Date', 'Credit Amount']
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = white_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = thin_border
        row += 1

        # Property income details
        grand_total_income = 0
        for prop in summary['properties']:
            if not prop['income_entries']:
                continue

            # First income entry includes property name
            first_income = prop['income_entries'][0]
            ws.cell(row=row, column=1, value=prop['property'])
            ws.cell(row=row, column=2, value=first_income['date'])
            ws.cell(row=row, column=3, value=first_income['amount'])

            # Apply formatting
            for col in range(1, 4):
                cell = ws.cell(row=row, column=col)
                cell.border = thin_border
                if col == 2:
                    cell.number_format = date_format
                elif col == 3:
                    cell.number_format = currency_format
            row += 1

            # Remaining income entries (property name blank)
            for income in prop['income_entries'][1:]:
                ws.cell(row=row, column=1, value='')
                ws.cell(row=row, column=2, value=income['date'])
                ws.cell(row=row, column=3, value=income['amount'])

                for col in range(1, 4):
                    cell = ws.cell(row=row, column=col)
                    cell.border = thin_border
                    if col == 2:
                        cell.number_format = date_format
                    elif col == 3:
                        cell.number_format = currency_format
                row += 1

            # Property total row
            ws.cell(row=row, column=1, value=f"{prop['property']} Total")
            ws.cell(row=row, column=2, value='')
            ws.cell(row=row, column=3, value=prop['income'])

            for col in range(1, 4):
                cell = ws.cell(row=row, column=col)
                cell.font = bold_font
                cell.fill = total_fill
                cell.border = thin_border
                if col == 3:
                    cell.number_format = currency_format
            row += 1
            grand_total_income += prop['income']

        # Grand total for income
        ws.cell(row=row, column=1, value='GRAND TOTAL')
        ws.cell(row=row, column=2, value='')
        ws.cell(row=row, column=3, value=grand_total_income)
        for col in range(1, 4):
            cell = ws.cell(row=row, column=col)
            cell.font = Font(name='Arial', size=10, bold=True)
            cell.fill = PatternFill(start_color='D1D5DB', end_color='D1D5DB', fill_type='solid')
            cell.border = thin_border
            if col == 3:
                cell.number_format = currency_format
        row += 2

        # ========== NEW SECTION: Expenses by Property, Date and Type ==========
        ws[f'A{row}'] = 'EXPENSES BY PROPERTY, DATE AND TYPE'
        ws[f'A{row}'].font = title_font
        row += 1

        # Table header for expense entries
        headers = ['Prop Name', 'Expense Date', 'Expense Type', 'Debit Amount']
        for col, header in enumerate(headers, start=1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = Font(name='Arial', size=10, bold=True, color='FFFFFF')
            cell.fill = PatternFill(start_color='2563EB', end_color='2563EB', fill_type='solid')
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center' if col < 4 else 'right')
        row += 1

        # Property expense entry details
        grand_total_expenses_detailed = 0
        for prop in summary['properties']:
            if not prop['expense_entries']:
                continue

            # First expense entry row includes property name
            first_expense = prop['expense_entries'][0]
            date_str = safe_format_date(first_expense['date'])

            ws.cell(row=row, column=1, value=prop['property'][:25])
            ws.cell(row=row, column=2, value=date_str)
            ws.cell(row=row, column=3, value=first_expense['type'][:25])
            ws.cell(row=row, column=4, value=first_expense['amount'])

            for col in range(1, 5):
                cell = ws.cell(row=row, column=col)
                cell.border = thin_border
                cell.font = Font(name='Arial', size=9)
                if col == 4:
                    cell.number_format = currency_format
                    cell.alignment = Alignment(horizontal='right')
            row += 1

            # Remaining expense entries (property name blank)
            for expense in prop['expense_entries'][1:]:
                date_str = safe_format_date(expense['date'])

                ws.cell(row=row, column=1, value='')
                ws.cell(row=row, column=2, value=date_str)
                ws.cell(row=row, column=3, value=expense['type'][:25])
                ws.cell(row=row, column=4, value=expense['amount'])

                for col in range(1, 5):
                    cell = ws.cell(row=row, column=col)
                    cell.border = thin_border
                    cell.font = Font(name='Arial', size=9)
                    if col == 4:
                        cell.number_format = currency_format
                        cell.alignment = Alignment(horizontal='right')
                row += 1

            # Property total row
            ws.cell(row=row, column=1, value=f"{prop['property'][:20]} Total")
            ws.cell(row=row, column=2, value='')
            ws.cell(row=row, column=3, value='')
            ws.cell(row=row, column=4, value=prop['expenses'])

            for col in range(1, 5):
                cell = ws.cell(row=row, column=col)
                cell.font = Font(name='Arial', size=9, bold=True)
                cell.fill = PatternFill(start_color='E5E7EB', end_color='E5E7EB', fill_type='solid')
                cell.border = thin_border
                if col == 4:
                    cell.number_format = currency_format
                    cell.alignment = Alignment(horizontal='right')
            row += 1
            grand_total_expenses_detailed += prop['expenses']

        # Grand total for expenses
        ws.cell(row=row, column=1, value='GRAND TOTAL')
        ws.cell(row=row, column=2, value='')
        ws.cell(row=row, column=3, value='')
        ws.cell(row=row, column=4, value=grand_total_expenses_detailed)

        for col in range(1, 5):
            cell = ws.cell(row=row, column=col)
            cell.font = Font(name='Arial', size=10, bold=True)
            cell.fill = PatternFill(start_color='D1D5DB', end_color='D1D5DB', fill_type='solid')
            cell.border = thin_border
            if col == 4:
                cell.number_format = currency_format
                cell.alignment = Alignment(horizontal='right')
        row += 2

        # Overall Summary section
        ws[f'A{row}'] = 'OVERALL SUMMARY'
        ws[f'A{row}'].font = title_font
        row += 1

        ws[f'A{row}'] = 'Total Income'
        ws[f'B{row}'] = summary['total_income']
        ws[f'B{row}'].number_format = currency_format
        ws[f'B{row}'].font = bold_font
        row += 1

        ws[f'A{row}'] = 'Total Expenses'
        ws[f'B{row}'] = summary['total_expenses']
        ws[f'B{row}'].number_format = currency_format
        ws[f'B{row}'].font = bold_font
        row += 1

        ws[f'A{row}'] = 'Net Income'
        ws[f'B{row}'] = summary['total_net']
        ws[f'B{row}'].number_format = currency_format
        ws[f'B{row}'].font = Font(name='Arial', size=10, bold=True, color='10B981' if summary['total_net'] >= 0 else 'EF4444')

        # Column widths
        ws.column_dimensions['A'].width = 30
        ws.column_dimensions['B'].width = 20
        ws.column_dimensions['C'].width = 20

        # Footer
        row += 2
        ws[f'A{row}'] = f'Report generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
        ws[f'A{row}'].font = Font(name='Arial', size=8, italic=True)

        # Save file
        file_path = None
        if save_to_file:
            file_path = os.path.join(self.reports_dir, f'property_report_{year}.xlsx')
            wb.save(file_path)
            logger.info(f"Property Excel report saved to: {file_path}")

        return file_path, summary


def main():
    """Test the property report generator."""
    import sys

    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2025

    generator = PropertyReportGenerator()

    print(f"\nGenerating property reports for {year}...")

    # Generate PDF
    pdf_path, pdf_summary = generator.generate_pdf_report(year)
    print(f"✓ PDF report generated: {pdf_path}")

    # Generate Excel
    excel_path, excel_summary = generator.generate_excel_report(year)
    print(f"✓ Excel report generated: {excel_path}")

    print(f"\nSummary:")
    print(f"  Total Income: ${pdf_summary['total_income']:,.2f}")
    print(f"  Total Expenses: ${pdf_summary['total_expenses']:,.2f}")
    print(f"  Net Income: ${pdf_summary['total_net']:,.2f}")
    print(f"  Properties: {len(pdf_summary['properties'])}")


if __name__ == '__main__':
    main()
