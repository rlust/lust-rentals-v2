"""
Phase 2: Dashboard API Routes for Lust Rentals
Provides JSON endpoints for the interactive dashboard
"""

import logging
from flask import Blueprint, jsonify, request
from datetime import datetime

from src.data_processing.processor import FinancialDataProcessor
from src.categorization.category_utils import normalize_category, get_display_name

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')


class DashboardService:
    """Service for dashboard data aggregation."""
    
    def __init__(self):
        self.processor = FinancialDataProcessor()
    
    def get_summary(self, year):
        """Get consolidated summary metrics."""
        try:
            result = self.processor.load_processed_data(year)
            income_df = result.get("income", pd.DataFrame())
            expenses_df = result.get("expenses", pd.DataFrame())
            
            total_income = float(income_df['amount'].sum()) if not income_df.empty else 0.0
            total_expenses = float(expenses_df['amount'].sum()) if not expenses_df.empty else 0.0
            net_income = total_income - total_expenses
            expense_ratio = (total_expenses / total_income * 100) if total_income > 0 else 0.0
            
            return {
                'year': year,
                'total_income': round(total_income, 2),
                'total_expenses': round(total_expenses, 2),
                'net_income': round(net_income, 2),
                'expense_ratio': round(expense_ratio, 1),
                'currency': 'USD'
            }
        except Exception as e:
            logger.error(f"Error getting summary for {year}: {str(e)}")
            raise
    
    def get_properties_comparison(self, year):
        """Get property comparison data."""
        try:
            result = self.processor.load_processed_data(year)
            income_df = result.get("income", pd.DataFrame())
            expenses_df = result.get("expenses", pd.DataFrame())
            
            properties = []
            
            all_props = set()
            if not income_df.empty:
                all_props.update(income_df['property_name'].unique())
            if not expenses_df.empty:
                all_props.update(expenses_df['property_name'].unique())
            
            for prop in sorted(all_props):
                prop_income = float(income_df[income_df['property_name'] == prop]['amount'].sum()) if not income_df.empty else 0.0
                prop_expenses = float(expenses_df[expenses_df['property_name'] == prop]['amount'].sum()) if not expenses_df.empty else 0.0
                prop_net = prop_income - prop_expenses
                
                properties.append({
                    'name': prop,
                    'income': round(prop_income, 2),
                    'expenses': round(prop_expenses, 2),
                    'net_income': round(prop_net, 2),
                    'profit_margin': round((prop_net / prop_income * 100), 1) if prop_income > 0 else 0.0,
                    'transaction_count': len(income_df[income_df['property_name'] == prop]) + 
                                        len(expenses_df[expenses_df['property_name'] == prop])
                })
            
            return {'year': year, 'properties': properties}
        except Exception as e:
            logger.error(f"Error getting property comparison for {year}: {str(e)}")
            raise
    
    def get_expenses_breakdown(self, year):
        """Get expense breakdown by category."""
        try:
            result = self.processor.load_processed_data(year)
            expenses_df = result.get("expenses", pd.DataFrame())
            
            if expenses_df.empty:
                return {'year': year, 'categories': []}
            
            # Normalize categories
            expenses_df['category_display'] = expenses_df['category'].apply(
                lambda x: get_display_name(normalize_category(x))
            )
            
            categories = []
            for cat, amount in expenses_df.groupby('category_display')['amount'].sum().sort_values(ascending=False).items():
                categories.append({
                    'name': cat,
                    'amount': round(float(amount), 2),
                    'percentage': round(float(amount) / expenses_df['amount'].sum() * 100, 1)
                })
            
            return {'year': year, 'categories': categories}
        except Exception as e:
            logger.error(f"Error getting expense breakdown for {year}: {str(e)}")
            raise
    
    def get_property_detail(self, property_name, year):
        """Get detailed data for a specific property."""
        try:
            result = self.processor.load_processed_data(year)
            income_df = result.get("income", pd.DataFrame())
            expenses_df = result.get("expenses", pd.DataFrame())
            
            prop_income_df = income_df[income_df['property_name'] == property_name]
            prop_expenses_df = expenses_df[expenses_df['property_name'] == property_name]
            
            total_income = float(prop_income_df['amount'].sum()) if not prop_income_df.empty else 0.0
            total_expenses = float(prop_expenses_df['amount'].sum()) if not prop_expenses_df.empty else 0.0
            
            # Normalize expense categories
            if not prop_expenses_df.empty and 'category' in prop_expenses_df.columns:
                prop_expenses_df['category_display'] = prop_expenses_df['category'].apply(
                    lambda x: get_display_name(normalize_category(x))
                )
            
            return {
                'property_name': property_name,
                'year': year,
                'summary': {
                    'total_income': round(total_income, 2),
                    'total_expenses': round(total_expenses, 2),
                    'net_income': round(total_income - total_expenses, 2)
                },
                'income_transactions': [
                    {
                        'date': str(row.get('transaction_date', '')),
                        'amount': round(float(row['amount']), 2),
                        'description': str(row.get('description', ''))
                    }
                    for _, row in prop_income_df.iterrows()
                ] if not prop_income_df.empty else [],
                'expense_transactions': [
                    {
                        'date': str(row.get('transaction_date', '')),
                        'category': str(row.get('category_display', '')),
                        'amount': round(float(row['amount']), 2),
                        'description': str(row.get('description', ''))
                    }
                    for _, row in prop_expenses_df.iterrows()
                ] if not prop_expenses_df.empty else [],
                'expense_by_category': [
                    {
                        'category': cat,
                        'amount': round(float(amount), 2)
                    }
                    for cat, amount in prop_expenses_df.groupby('category_display')['amount'].sum().items()
                ] if not prop_expenses_df.empty else []
            }
        except Exception as e:
            logger.error(f"Error getting property detail for {property_name}/{year}: {str(e)}")
            raise


# Initialize service
dashboard_service = DashboardService()


# Routes
@dashboard_bp.route('/summary/<int:year>', methods=['GET'])
def get_summary(year):
    """Get consolidated summary metrics."""
    try:
        data = dashboard_service.get_summary(year)
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Error in get_summary: {str(e)}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/properties/<int:year>', methods=['GET'])
def get_properties(year):
    """Get property comparison data."""
    try:
        data = dashboard_service.get_properties_comparison(year)
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Error in get_properties: {str(e)}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/expenses/<int:year>', methods=['GET'])
def get_expenses(year):
    """Get expense breakdown by category."""
    try:
        data = dashboard_service.get_expenses_breakdown(year)
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Error in get_expenses: {str(e)}")
        return jsonify({'error': str(e)}), 500


@dashboard_bp.route('/property/<property_name>/<int:year>', methods=['GET'])
def get_property(property_name, year):
    """Get detailed property data."""
    try:
        data = dashboard_service.get_property_detail(property_name, year)
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Error in get_property: {str(e)}")
        return jsonify({'error': str(e)}), 500


# Missing import
import pandas as pd
