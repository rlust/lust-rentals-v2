# Property Management System - Feature Documentation

## Overview

The Lust Rentals Tax Reporting application now includes a comprehensive property management system that allows you to centrally manage rental properties and business entities (like Lust Rentals LLC) for better organization and tax reporting.

## ✨ New Features

### 1. **Centralized Property Management**
- **Location**: Dashboard → 🏢 Manage Properties button
- **Features**:
  - Add, edit, and deactivate properties through a modern UI
  - Two property types supported:
    - 🏠 **Rental Property**: Individual rental properties
    - 🏢 **Business Entity**: Company/LLC for business-level expenses
  - Custom sort ordering
  - Address and notes fields for each property
  - Soft deletion (deactivate instead of delete to preserve historical data)

### 2. **Lust Rentals LLC Entity**
- **Pre-configured** business entity for company-level expenses
- Appears **first** in all property selection dropdowns
- Automatically included in all reports with proper categorization
- Ideal for expenses like:
  - Legal fees
  - Insurance (general business)
  - Professional services
  - Office expenses
  - Other business-level costs

### 3. **Enhanced Property Selection**
- Property dropdowns now pull from centralized properties table
- LLC entity always appears at the top
- Rental properties sorted alphabetically
- Only active properties shown in selection dropdowns
- Inactive properties preserved in historical reports

## 📋 How to Use

### Managing Properties

1. **Navigate to Property Management**
   - Go to Dashboard (http://localhost:8002)
   - Click the "🏢 Manage Properties" button in Quick Actions

2. **View Existing Properties**
   - Default properties are automatically created:
     - Lust Rentals LLC (Business Entity)
     - 118 W Shields St (Rental)
     - 41 26th St (Rental)
     - 966 Kinsbury Court (Rental)

3. **Add a New Property**
   - Click "+ Add Property" button
   - Fill in the form:
     - **Property Name**: Full name or address
     - **Property Type**: Choose Rental or Business Entity
     - **Address**: Physical address (optional)
     - **Notes**: Any additional information
     - **Sort Order**: Number for custom ordering
   - Click "Save Property"

4. **Edit a Property**
   - Click "Edit" button next to any property
   - Modify details as needed
   - Click "Save Property"

5. **Deactivate a Property**
   - Click "Deactivate" button next to any property
   - Confirm the action
   - Property will no longer appear in dropdowns but historical data is preserved

### Assigning Transactions to Properties

1. **Go to Review Page**
   - Click "🔍 Review Transactions" from Dashboard
   - Or navigate to http://localhost:8002/review

2. **Assign Income to Properties**
   - Select "Unassigned Income" or "All Income" tab
   - For each transaction, select a property from the dropdown
   - **Lust Rentals LLC** will appear first for business-level income
   - Rental properties appear below

3. **Assign Expenses to Properties**
   - Select "Unassigned Expenses" or "All Expenses" tab
   - Select category AND property for each expense
   - Use **Lust Rentals LLC** for business expenses (legal, insurance, etc.)
   - Use rental property names for property-specific expenses

4. **Save Changes**
   - Option 1: Click "💾 Save Changes" to save without reprocessing
   - Option 2: Click "💾🔄 Save & Re-Process" to save and automatically update reports

## 📊 How Properties Appear in Reports

### Property Reports (PDF & Excel)
- Each property gets its own section showing:
  - Total income
  - Total expenses
  - Net income
  - Detailed expense breakdown by type
  - Income entries by date
  - Expense entries by date and type

### Lust Rentals LLC in Reports
- Appears as a separate property with its own section
- Business expenses are clearly categorized
- Helps separate property-level vs business-level costs

### Schedule E Reports
- Rental properties appear on Schedule E (rental real estate)
- Business entity expenses should be reported on Schedule C (business income)
- System automatically organizes data by property type

## 🎯 Best Practices

### When to Use Lust Rentals LLC
✅ **DO** assign to LLC:
- Legal and professional fees (general business)
- Business insurance (not property-specific)
- Office supplies and equipment
- General administrative costs
- Company-level marketing expenses

❌ **DON'T** assign to LLC:
- Property-specific repairs
- Property-specific utilities
- Property-specific insurance
- Property management fees for specific properties

### When to Use Rental Properties
✅ **DO** assign to specific rental properties:
- Rent deposits and payments
- Property-specific repairs and maintenance
- Property-specific utilities
- Property taxes for that specific property
- Property-specific insurance

## 🔧 Technical Details

### Database Structure
- New `properties` table in `processed.db`
- Fields: id, property_name, property_type, address, is_active, sort_order, notes, timestamps
- Migration automatically runs on first database access
- Foreign key relationships preserved for data integrity

### API Endpoints
- `GET /properties/` - List all properties
- `GET /properties/{id}` - Get single property
- `POST /properties/` - Create new property
- `PUT /properties/{id}` - Update property
- `DELETE /properties/{id}` - Soft delete (deactivate) property
- `POST /properties/initialize` - Initialize default properties
- `GET /review/properties` - Get properties for dropdown selection

### Files Modified
1. **src/data_processing/processor.py** - Added properties table migration
2. **src/api/routes/properties.py** - NEW: Property CRUD API
3. **src/api/routes/review.py** - Updated to use properties table
4. **src/api/server_new.py** - Registered properties router and UI route
5. **src/api/templates/properties.html** - NEW: Property management UI
6. **src/api/templates/dashboard_v2.html** - Added Manage Properties button

## 🚀 Getting Started

The property management system is already set up and running! Here's what's ready to use:

1. ✅ **Database**: Properties table created with 4 default properties
2. ✅ **API**: All CRUD endpoints working on port 8002
3. ✅ **UI**: Property management page accessible from dashboard
4. ✅ **LLC Entity**: "Lust Rentals LLC" ready to use for business expenses

### Quick Start
1. Go to http://localhost:8002
2. Click "🏢 Manage Properties" to view/edit properties
3. Go to Review page to assign transactions
4. Generate reports to see property breakdowns

## 📈 What's Next (Future Enhancements)

Planned improvements for future releases:
- **Bulk Operations**: Select multiple transactions and assign to property at once
- **Property Grouping**: Group properties by location or type
- **Advanced Filtering**: Filter transactions by property, date range, amount
- **Property Analytics**: Dashboard showing performance by property
- **Import/Export**: CSV import for bulk property setup

## ❓ Troubleshooting

### Properties Not Showing in Dropdown
- Check if properties are active in Property Management page
- Ensure database migration completed (restart server if needed)
- Clear browser cache and reload page

### Can't Delete Property
- Properties can only be deactivated (soft delete) to preserve historical data
- Use "Deactivate" button instead of delete
- Deactivated properties won't appear in new transactions but remain in reports

### LLC Not Appearing First
- LLC should automatically appear first due to property_type = 'business_entity'
- Check Property Management page to verify type is set correctly
- If issue persists, check sort_order (should be 0 for LLC)

## 📞 Support

For issues or questions:
- Check this documentation first
- Review API docs at http://localhost:8002/docs
- Check server logs for error messages
- Report issues via GitHub

---

**Version**: 2.0
**Last Updated**: November 9, 2025
**Feature Status**: ✅ Production Ready
