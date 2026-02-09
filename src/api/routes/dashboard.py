"""Interactive dashboard for Lust Rentals."""
from __future__ import annotations

import logging
import sqlite3
from typing import Optional
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
import pandas as pd

from src.api.dependencies import get_config
from src.categorization.category_utils import normalize_category, get_display_name

router = APIRouter()
logger = logging.getLogger(__name__)


def get_dashboard_data(year: int):
    """Load dashboard data from database."""
    db_path = get_config().data_dir / "processed" / "processed.db"
    
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database not found")
    
    with sqlite3.connect(db_path) as conn:
        income_df = pd.read_sql_query("SELECT * FROM processed_income", conn)
        expenses_df = pd.read_sql_query("SELECT * FROM processed_expenses", conn)
    
    # Filter by year
    if 'date' in income_df.columns and not income_df.empty:
        income_df['date'] = pd.to_datetime(income_df['date'], errors='coerce')
        income_df = income_df[income_df['date'].dt.year == year]
    
    if 'date' in expenses_df.columns and not expenses_df.empty:
        expenses_df['date'] = pd.to_datetime(expenses_df['date'], errors='coerce')
        expenses_df = expenses_df[expenses_df['date'].dt.year == year]
    
    # Normalize categories
    if not expenses_df.empty and 'category' in expenses_df.columns:
        expenses_df['category_normalized'] = expenses_df['category'].apply(normalize_category)
        expenses_df['category_display'] = expenses_df['category_normalized'].apply(get_display_name)
    
    return income_df, expenses_df


@router.get("/api/dashboard/summary/{year}")
def get_summary(year: int) -> JSONResponse:
    """Get summary metrics."""
    try:
        income_df, expenses_df = get_dashboard_data(year)
        
        total_income = float(income_df['amount'].sum()) if not income_df.empty else 0
        total_expenses = float(abs(expenses_df['amount'].sum())) if not expenses_df.empty else 0
        net_income = total_income - total_expenses
        expense_ratio = (total_expenses / total_income * 100) if total_income > 0 else 0
        
        return JSONResponse({
            'total_income': round(total_income, 2),
            'total_expenses': round(total_expenses, 2),
            'net_income': round(net_income, 2),
            'expense_ratio': round(expense_ratio, 1)
        })
    except Exception as e:
        logger.error(f"Error getting summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/dashboard/properties/{year}")
def get_properties(year: int) -> JSONResponse:
    """Get property comparison data."""
    try:
        income_df, expenses_df = get_dashboard_data(year)
        
        properties = {}
        
        # Income by property
        if not income_df.empty and 'property_name' in income_df.columns:
            for prop, group in income_df.groupby('property_name'):
                if prop:
                    if prop not in properties:
                        properties[prop] = {'income': 0, 'expenses': 0}
                    properties[prop]['income'] = float(group['amount'].sum())
        
        # Expenses by property
        if not expenses_df.empty and 'property_name' in expenses_df.columns:
            for prop, group in expenses_df.groupby('property_name'):
                if prop:
                    if prop not in properties:
                        properties[prop] = {'income': 0, 'expenses': 0}
                    properties[prop]['expenses'] = float(abs(group['amount'].sum()))
        
        result = []
        for prop in sorted(properties.keys()):
            data = properties[prop]
            result.append({
                'property': prop,
                'income': round(data['income'], 2),
                'expenses': round(data['expenses'], 2),
                'net': round(data['income'] - data['expenses'], 2)
            })
        
        return JSONResponse(result)
    except Exception as e:
        logger.error(f"Error getting properties: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/dashboard/expenses-breakdown/{year}")
def get_expenses_breakdown(year: int) -> JSONResponse:
    """Get expense breakdown by category."""
    try:
        _, expenses_df = get_dashboard_data(year)
        
        if expenses_df.empty or 'category_display' not in expenses_df.columns:
            return JSONResponse({'labels': [], 'data': []})
        
        breakdown = expenses_df.groupby('category_display')['amount'].apply(lambda x: abs(x.sum()))
        breakdown = breakdown.sort_values(ascending=False)
        
        return JSONResponse({
            'labels': [str(cat) for cat in breakdown.index],
            'data': [round(float(val), 2) for val in breakdown.values]
        })
    except Exception as e:
        logger.error(f"Error getting expenses breakdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/dashboard/property-detail/{year}/{property_name}")
def get_property_detail(year: int, property_name: str) -> JSONResponse:
    """Get all transactions for a property."""
    try:
        income_df, expenses_df = get_dashboard_data(year)
        
        transactions = []
        
        # Add income transactions
        if not income_df.empty and 'property_name' in income_df.columns:
            prop_income = income_df[income_df['property_name'] == property_name]
            for _, row in prop_income.iterrows():
                transactions.append({
                    'date': str(row['date'])[:10] if pd.notna(row['date']) else 'N/A',
                    'description': str(row.get('description', 'Income')),
                    'category': 'Income',
                    'amount': round(float(row['amount']), 2)
                })
        
        # Add expense transactions
        if not expenses_df.empty and 'property_name' in expenses_df.columns:
            prop_exp = expenses_df[expenses_df['property_name'] == property_name]
            for _, row in prop_exp.iterrows():
                transactions.append({
                    'date': str(row['date'])[:10] if pd.notna(row['date']) else 'N/A',
                    'description': str(row.get('description', 'Expense')),
                    'category': str(row.get('category_display', 'Uncategorized')),
                    'amount': round(float(row['amount']), 2)
                })
        
        # Sort by date descending
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        return JSONResponse({'transactions': transactions})
    except Exception as e:
        logger.error(f"Error getting property detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard")
def dashboard_page(year: Optional[int] = None) -> HTMLResponse:
    """Serve the interactive dashboard."""
    from src.api.dependencies import get_tax_reporter
    
    reporter = get_tax_reporter()
    resolved_year = year or (reporter.current_year - 1)
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lust Rentals Dashboard - {resolved_year}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0"></script>
    <style>
        * {{ 
            margin: 0; 
            padding: 0; 
            box-sizing: border-box; 
        }}
        
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .header {{
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        
        .header h1 {{
            font-size: 2.5em;
            color: #667eea;
            margin-bottom: 10px;
        }}
        
        .header .year-selector {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 15px;
        }}
        
        .year-selector select {{
            padding: 10px 20px;
            font-size: 1em;
            border: 2px solid #667eea;
            border-radius: 8px;
            background: white;
            color: #667eea;
            cursor: pointer;
            font-weight: 600;
        }}
        
        .year-selector label {{
            font-weight: 600;
            color: #555;
        }}
        
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .card {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        
        .card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
        }}
        
        .card-title {{
            font-size: 0.9em;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
            font-weight: 600;
        }}
        
        .card-value {{
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .card-income .card-value {{ color: #10b981; }}
        .card-expenses .card-value {{ color: #ef4444; }}
        .card-net .card-value {{ color: #667eea; }}
        .card-ratio .card-value {{ color: #f59e0b; }}
        
        .main-content {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }}
        
        .table-section {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        
        .section-title {{
            font-size: 1.5em;
            color: #667eea;
            margin-bottom: 20px;
            font-weight: 600;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        thead {{
            background: #f8f9fa;
        }}
        
        th {{
            padding: 12px;
            text-align: left;
            font-weight: 600;
            color: #555;
            border-bottom: 2px solid #e5e7eb;
        }}
        
        th.right, td.right {{
            text-align: right;
        }}
        
        tbody tr {{
            border-bottom: 1px solid #e5e7eb;
            cursor: pointer;
            transition: background-color 0.2s;
        }}
        
        tbody tr:hover {{
            background-color: #f8f9fa;
        }}
        
        td {{
            padding: 12px;
            color: #333;
        }}
        
        .positive {{ color: #10b981; font-weight: 600; }}
        .negative {{ color: #ef4444; font-weight: 600; }}
        
        .chart-section {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        
        .chart-container {{
            position: relative;
            height: 400px;
            margin-top: 20px;
        }}
        
        /* Modal */
        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            animation: fadeIn 0.3s;
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}
        
        .modal-content {{
            background-color: white;
            margin: 5% auto;
            padding: 0;
            border-radius: 12px;
            width: 90%;
            max-width: 900px;
            max-height: 80vh;
            overflow: hidden;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
            animation: slideIn 0.3s;
        }}
        
        @keyframes slideIn {{
            from {{ 
                transform: translateY(-50px);
                opacity: 0;
            }}
            to {{ 
                transform: translateY(0);
                opacity: 1;
            }}
        }}
        
        .modal-header {{
            padding: 25px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .modal-header h2 {{
            font-size: 1.8em;
            margin: 0;
        }}
        
        .close {{
            color: white;
            font-size: 2em;
            font-weight: bold;
            cursor: pointer;
            background: none;
            border: none;
            padding: 0;
            line-height: 1;
            transition: transform 0.2s;
        }}
        
        .close:hover {{
            transform: scale(1.2);
        }}
        
        .modal-body {{
            padding: 25px;
            max-height: calc(80vh - 200px);
            overflow-y: auto;
        }}
        
        .transaction-summary {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-bottom: 25px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
        }}
        
        .transaction-summary-item {{
            text-align: center;
        }}
        
        .transaction-summary-label {{
            font-size: 0.85em;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 5px;
        }}
        
        .transaction-summary-value {{
            font-size: 1.5em;
            font-weight: bold;
        }}
        
        .transaction-table {{
            margin-top: 20px;
        }}
        
        .loading {{
            text-align: center;
            padding: 40px;
            color: #888;
            font-size: 1.2em;
        }}
        
        .loading:after {{
            content: '.';
            animation: dots 1.5s steps(3, end) infinite;
        }}
        
        @keyframes dots {{
            0%, 20% {{ content: '.'; }}
            40% {{ content: '..'; }}
            60%, 100% {{ content: '...'; }}
        }}
        
        .error {{
            color: #ef4444;
            background: #fee;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
        }}
        
        @media (max-width: 1024px) {{
            .main-content {{
                grid-template-columns: 1fr;
            }}
            
            .summary-cards {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
        
        @media (max-width: 640px) {{
            .header h1 {{
                font-size: 1.8em;
            }}
            
            .summary-cards {{
                grid-template-columns: 1fr;
            }}
            
            .card-value {{
                font-size: 2em;
            }}
            
            .modal-content {{
                width: 95%;
                margin: 10% auto;
            }}
            
            .transaction-summary {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏠 Lust Rentals Dashboard</h1>
            <div class="year-selector">
                <label for="year-select">Tax Year:</label>
                <select id="year-select" onchange="changeYear(this.value)">
                    <option value="2023" {('selected' if resolved_year == 2023 else '')}>2023</option>
                    <option value="2024" {('selected' if resolved_year == 2024 else '')}>2024</option>
                    <option value="2025" {('selected' if resolved_year == 2025 else '')}>2025</option>
                </select>
            </div>
        </div>
        
        <div class="summary-cards" id="summary-cards">
            <div class="card card-income">
                <div class="card-title">Total Income</div>
                <div class="card-value" id="total-income">$0.00</div>
            </div>
            <div class="card card-expenses">
                <div class="card-title">Total Expenses</div>
                <div class="card-value" id="total-expenses">$0.00</div>
            </div>
            <div class="card card-net">
                <div class="card-title">Net Income</div>
                <div class="card-value" id="net-income">$0.00</div>
            </div>
            <div class="card card-ratio">
                <div class="card-title">Expense Ratio</div>
                <div class="card-value" id="expense-ratio">0%</div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="table-section">
                <h2 class="section-title">Property Performance</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Property</th>
                            <th class="right">Income</th>
                            <th class="right">Expenses</th>
                            <th class="right">Net</th>
                        </tr>
                    </thead>
                    <tbody id="properties-table">
                        <tr><td colspan="4" class="loading">Loading</td></tr>
                    </tbody>
                </table>
            </div>
            
            <div class="chart-section">
                <h2 class="section-title">Expense Breakdown</h2>
                <div class="chart-container">
                    <canvas id="expenses-chart"></canvas>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Property Detail Modal -->
    <div id="property-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 id="modal-property-name">Property Details</h2>
                <button class="close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="transaction-summary" id="modal-summary">
                    <!-- Summary will be populated here -->
                </div>
                <div class="transaction-table">
                    <table>
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Description</th>
                                <th>Category</th>
                                <th class="right">Amount</th>
                            </tr>
                        </thead>
                        <tbody id="modal-transactions">
                            <tr><td colspan="4" class="loading">Loading</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        const currentYear = {resolved_year};
        let expensesChart = null;
        
        // Format currency
        function formatCurrency(amount) {{
            return new Intl.NumberFormat('en-US', {{
                style: 'currency',
                currency: 'USD'
            }}).format(amount);
        }}
        
        // Change year
        function changeYear(year) {{
            window.location.href = `/dashboard?year=${{year}}`;
        }}
        
        // Load summary data
        async function loadSummary() {{
            try {{
                const response = await fetch(`/api/dashboard/summary/${{currentYear}}`);
                const data = await response.json();
                
                document.getElementById('total-income').textContent = formatCurrency(data.total_income);
                document.getElementById('total-expenses').textContent = formatCurrency(data.total_expenses);
                document.getElementById('net-income').textContent = formatCurrency(data.net_income);
                document.getElementById('expense-ratio').textContent = data.expense_ratio + '%';
            }} catch (error) {{
                console.error('Error loading summary:', error);
                document.getElementById('summary-cards').innerHTML = '<div class="error">Failed to load summary data</div>';
            }}
        }}
        
        // Load properties table
        async function loadProperties() {{
            try {{
                const response = await fetch(`/api/dashboard/properties/${{currentYear}}`);
                const properties = await response.json();
                
                const tbody = document.getElementById('properties-table');
                
                if (properties.length === 0) {{
                    tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #888;">No properties found for ' + currentYear + '</td></tr>';
                    return;
                }}
                
                tbody.innerHTML = '';
                properties.forEach(property => {{
                    const row = document.createElement('tr');
                    row.onclick = () => openPropertyDetail(property.property);
                    
                    const netClass = property.net >= 0 ? 'positive' : 'negative';
                    
                    row.innerHTML = `
                        <td>${{property.property}}</td>
                        <td class="right positive">${{formatCurrency(property.income)}}</td>
                        <td class="right negative">${{formatCurrency(property.expenses)}}</td>
                        <td class="right ${{netClass}}">${{formatCurrency(property.net)}}</td>
                    `;
                    
                    tbody.appendChild(row);
                }});
            }} catch (error) {{
                console.error('Error loading properties:', error);
                document.getElementById('properties-table').innerHTML = '<tr><td colspan="4" class="error">Failed to load properties</td></tr>';
            }}
        }}
        
        // Load expense breakdown chart
        async function loadExpensesChart() {{
            try {{
                const response = await fetch(`/api/dashboard/expenses-breakdown/${{currentYear}}`);
                const data = await response.json();
                
                const ctx = document.getElementById('expenses-chart').getContext('2d');
                
                // Destroy existing chart if it exists
                if (expensesChart) {{
                    expensesChart.destroy();
                }}
                
                if (data.labels.length === 0) {{
                    ctx.canvas.parentElement.innerHTML = '<p style="text-align: center; color: #888; padding: 40px;">No expense data available for ' + currentYear + '</p>';
                    return;
                }}
                
                // Generate colors
                const colors = [
                    '#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6',
                    '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1'
                ];
                
                expensesChart = new Chart(ctx, {{
                    type: 'pie',
                    data: {{
                        labels: data.labels,
                        datasets: [{{
                            data: data.data,
                            backgroundColor: colors.slice(0, data.labels.length),
                            borderWidth: 2,
                            borderColor: '#fff'
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                position: 'right',
                                labels: {{
                                    padding: 15,
                                    font: {{
                                        size: 12
                                    }},
                                    generateLabels: function(chart) {{
                                        const data = chart.data;
                                        if (data.labels.length && data.datasets.length) {{
                                            return data.labels.map((label, i) => {{
                                                const value = data.datasets[0].data[i];
                                                return {{
                                                    text: `${{label}}: ${{formatCurrency(value)}}`,
                                                    fillStyle: data.datasets[0].backgroundColor[i],
                                                    hidden: false,
                                                    index: i
                                                }};
                                            }});
                                        }}
                                        return [];
                                    }}
                                }}
                            }},
                            tooltip: {{
                                callbacks: {{
                                    label: function(context) {{
                                        const label = context.label || '';
                                        const value = context.parsed || 0;
                                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                        const percentage = ((value / total) * 100).toFixed(1);
                                        return `${{label}}: ${{formatCurrency(value)}} (${{percentage}}%)`;
                                    }}
                                }}
                            }}
                        }}
                    }}
                }});
            }} catch (error) {{
                console.error('Error loading expenses chart:', error);
                document.getElementById('expenses-chart').parentElement.innerHTML = '<div class="error">Failed to load expenses breakdown</div>';
            }}
        }}
        
        // Open property detail modal
        async function openPropertyDetail(propertyName) {{
            const modal = document.getElementById('property-modal');
            const modalBody = document.getElementById('modal-transactions');
            const modalTitle = document.getElementById('modal-property-name');
            const modalSummary = document.getElementById('modal-summary');
            
            modalTitle.textContent = propertyName;
            modalBody.innerHTML = '<tr><td colspan="4" class="loading">Loading transactions</td></tr>';
            modalSummary.innerHTML = '';
            modal.style.display = 'block';
            
            try {{
                const response = await fetch(`/api/dashboard/property-detail/${{currentYear}}/${{encodeURIComponent(propertyName)}}`);
                const data = await response.json();
                
                if (data.transactions.length === 0) {{
                    modalBody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #888;">No transactions found</td></tr>';
                    return;
                }}
                
                // Calculate summary
                let totalIncome = 0;
                let totalExpenses = 0;
                data.transactions.forEach(t => {{
                    if (t.amount > 0) totalIncome += t.amount;
                    else totalExpenses += Math.abs(t.amount);
                }});
                const net = totalIncome - totalExpenses;
                
                // Display summary
                modalSummary.innerHTML = `
                    <div class="transaction-summary-item">
                        <div class="transaction-summary-label">Income</div>
                        <div class="transaction-summary-value positive">${{formatCurrency(totalIncome)}}</div>
                    </div>
                    <div class="transaction-summary-item">
                        <div class="transaction-summary-label">Expenses</div>
                        <div class="transaction-summary-value negative">${{formatCurrency(totalExpenses)}}</div>
                    </div>
                    <div class="transaction-summary-item">
                        <div class="transaction-summary-label">Net</div>
                        <div class="transaction-summary-value ${{net >= 0 ? 'positive' : 'negative'}}">${{formatCurrency(net)}}</div>
                    </div>
                `;
                
                // Display transactions
                modalBody.innerHTML = '';
                data.transactions.forEach(transaction => {{
                    const row = document.createElement('tr');
                    const amountClass = transaction.amount >= 0 ? 'positive' : 'negative';
                    
                    row.innerHTML = `
                        <td>${{transaction.date}}</td>
                        <td>${{transaction.description}}</td>
                        <td>${{transaction.category}}</td>
                        <td class="right ${{amountClass}}">${{formatCurrency(transaction.amount)}}</td>
                    `;
                    
                    modalBody.appendChild(row);
                }});
            }} catch (error) {{
                console.error('Error loading property detail:', error);
                modalBody.innerHTML = '<tr><td colspan="4" class="error">Failed to load transactions</td></tr>';
            }}
        }}
        
        // Close modal
        function closeModal() {{
            document.getElementById('property-modal').style.display = 'none';
        }}
        
        // Close modal when clicking outside
        window.onclick = function(event) {{
            const modal = document.getElementById('property-modal');
            if (event.target === modal) {{
                closeModal();
            }}
        }}
        
        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {{
            loadSummary();
            loadProperties();
            loadExpensesChart();
        }});
    </script>
</body>
</html>
    """
    
    return HTMLResponse(content=html)