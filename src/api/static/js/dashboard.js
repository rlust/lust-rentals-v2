// JavaScript Dashboard Interaction Logic

// Chart instances
let expenseChartInstance = null;
let propertyExpenseChartInstance = null;

// Color palette for charts
const COLORS = [
    '#5B9BD5', '#70AD47', '#FFC000', '#C00000', '#8864C4',
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
    '#2F5496', '#7F7F7F'
];

/**
 * Format currency values
 */
function formatCurrency(value) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(value);
}

/**
 * Format percentage values
 */
function formatPercent(value) {
    return parseFloat(value).toFixed(1) + '%';
}

/**
 * Load dashboard summary
 */
async function loadDashboardSummary(year) {
    try {
        const response = await fetch(`/api/dashboard/summary/${year}`);
        const data = await response.json();
        
        document.getElementById('totalIncome').textContent = formatCurrency(data.total_income);
        document.getElementById('totalExpenses').textContent = formatCurrency(data.total_expenses);
        document.getElementById('netIncome').textContent = formatCurrency(data.net_income);
        document.getElementById('expenseRatio').textContent = formatPercent(data.expense_ratio);
    } catch (error) {
        console.error('Error loading summary:', error);
    }
}

/**
 * Load properties comparison
 */
async function loadPropertiesComparison(year) {
    try {
        const response = await fetch(`/api/dashboard/properties/${year}`);
        const data = await response.json();
        
        const tbody = document.querySelector('#propertiesTable tbody');
        tbody.innerHTML = '';
        
        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty">No properties found</td></tr>';
            return;
        }
        
        // Populate property selector
        const propertySelect = document.getElementById('propertySelect');
        propertySelect.innerHTML = '<option value="">-- Select a property --</option>';
        
        data.forEach(prop => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${prop.property_name}</td>
                <td class="number">${formatCurrency(prop.total_income)}</td>
                <td class="number">${formatCurrency(prop.total_expenses)}</td>
                <td class="number">${formatCurrency(prop.net_income)}</td>
                <td class="number">${formatPercent(prop.expense_ratio)}</td>
            `;
            row.addEventListener('click', () => {
                document.getElementById('propertySelect').value = prop.property_name;
                loadPropertyDetails(prop.property_name, year);
            });
            tbody.appendChild(row);
            
            const option = document.createElement('option');
            option.value = prop.property_name;
            option.textContent = prop.property_name;
            propertySelect.appendChild(option);
        });
    } catch (error) {
        console.error('Error loading properties:', error);
        document.querySelector('#propertiesTable tbody').innerHTML = '<tr><td colspan="5" class="error">Error loading data</td></tr>';
    }
}

/**
 * Load expense breakdown
 */
async function loadExpenseBreakdown(year) {
    try {
        const response = await fetch(`/api/dashboard/expenses/${year}`);
        const data = await response.json();
        
        if (!data || data.length === 0) {
            return;
        }
        
        const labels = data.map(d => d.category);
        const amounts = data.map(d => d.amount);
        const colors = COLORS.slice(0, data.length % COLORS.length + 1); // Recycle colors if needed
        
        // Create pie chart
        const ctx = document.getElementById('expenseChart').getContext('2d');
        
        if (expenseChartInstance) {
            expenseChartInstance.destroy();
        }
        
        expenseChartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: amounts,
                    backgroundColor: colors,
                    borderColor: '#fff',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false // Hide legend in chart, use custom list
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                let label = context.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                label += formatCurrency(context.parsed);
                                return label;
                            }
                        }
                    }
                }
            }
        });
        
        // Update category list
        const categoryList = document.getElementById('categoryList');
        categoryList.innerHTML = '';
        data.forEach((item, index) => {
            const div = document.createElement('div');
            div.className = 'category-item';
            div.innerHTML = `
                <div class="category-indicator" style="background-color: ${colors[index]}"></div>
                <span>${item.category}: ${formatCurrency(item.amount)}</span>
            `;
            categoryList.appendChild(div);
        });
    } catch (error) {
        console.error('Error loading expenses:', error);
    }
}

/**
 * Load property details
 */
async function loadPropertyDetails(propertyName, year) {
    try {
        const response = await fetch(`/api/dashboard/property/${encodeURIComponent(propertyName)}/${year}`);
        const data = await response.json();
        
        const detailsDiv = document.getElementById('propertyDetails');
        
        // Update property summary
        document.getElementById('propertyName').textContent = propertyName;
        document.getElementById('propIncome').textContent = formatCurrency(data.summary.total_income);
        document.getElementById('propExpenses').textContent = formatCurrency(data.summary.total_expenses);
        document.getElementById('propNet').textContent = formatCurrency(data.summary.net_income);
        
        // Load expense categories chart
        loadPropertyExpenseChart(data.expense_breakdown, propertyName);
        
        // Load transactions
        loadPropertyTransactions(data.income_transactions, data.expense_transactions);
        
        // Show details section
        detailsDiv.style.display = 'block';
        detailsDiv.scrollIntoView({ behavior: 'smooth' });
    } catch (error) {
        console.error('Error loading property details:', error);
    }
}

/**
 * Load property expense chart
 */
function loadPropertyExpenseChart(expenseBreakdown, propertyName) {
    if (!expenseBreakdown || expenseBreakdown.length === 0) {
        return;
    }
    
    // Sort by amount descending
    expenseBreakdown.sort((a, b) => b.amount - a.amount);
    
    const labels = expenseBreakdown.map(d => d.category);
    const amounts = expenseBreakdown.map(d => d.amount);
    
    const ctx = document.getElementById('propertyExpenseChart').getContext('2d');
    
    if (propertyExpenseChartInstance) {
        propertyExpenseChartInstance.destroy();
    }
    
    propertyExpenseChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Expenses',
                data: amounts,
                backgroundColor: '#5B9BD5',
                borderColor: '#2F5496',
                borderWidth: 1
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return formatCurrency(context.parsed.x);
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: {
                        callback: function(value) {
                            return formatCurrency(value);
                        }
                    }
                }
            }
        }
    });
}

/**
 * Load property transactions
 */
function loadPropertyTransactions(incomeTransactions, expenseTransactions) {
    // Income transactions
    const incomeTbody = document.getElementById('incomeTransactions');
    incomeTbody.innerHTML = '';
    
    if (!incomeTransactions || incomeTransactions.length === 0) {
        incomeTbody.innerHTML = '<tr><td colspan="3" class="empty">No transactions</td></tr>';
    } else {
        incomeTransactions.forEach(trans => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${trans.date}</td>
                <td>${trans.description}</td>
                <td class="number">${formatCurrency(trans.amount)}</td>
            `;
            incomeTbody.appendChild(row);
        });
    }
    
    // Expense transactions
    const expenseTbody = document.getElementById('expenseTransactions');
    expenseTbody.innerHTML = '';
    
    if (!expenseTransactions || expenseTransactions.length === 0) {
        expenseTbody.innerHTML = '<tr><td colspan="4" class="empty">No transactions</td></tr>';
    } else {
        expenseTransactions.forEach(trans => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${trans.date}</td>
                <td>${trans.description}</td>
                <td>${trans.category}</td>
                <td class="number">${formatCurrency(trans.amount)}</td>
            `;
            expenseTbody.appendChild(row);
        });
    }
}

/**
 * Load all dashboard data for a given year
 */
async function loadDashboardData(year) {
    await Promise.all([
        loadDashboardSummary(year),
        loadPropertiesComparison(year),
        loadExpenseBreakdown(year)
    ]);
}

/**
 * Initialize dashboard
 */
function initializeDashboard() {
    const currentYear = new Date().getFullYear();
    const yearSelect = document.getElementById('yearSelect');
    
    // Set default year to 2025 as per prompt
    yearSelect.value = "2025";
    
    // Load initial data
    loadDashboardData(parseInt(yearSelect.value));
    
    // Year selector change handler
    yearSelect.addEventListener('change', (e) => {
        loadDashboardData(parseInt(e.target.value));
    });
    
    // Property selector change handler
    document.getElementById('propertySelect').addEventListener('change', (e) => {
        if (e.target.value) {
            loadPropertyDetails(e.target.value, parseInt(yearSelect.value));
        }
    });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initializeDashboard);
