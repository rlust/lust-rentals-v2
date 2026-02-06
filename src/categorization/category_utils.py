"""
Utility functions for expense category normalization and formatting.

This module provides functions to ensure consistent category naming and
display formatting across all reports.
"""

from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


# Canonical category name mappings (normalized to lowercase with underscores)
CATEGORY_NORMALIZATION: Dict[str, str] = {
    # Repairs variations
    "repairs": "repairs",
    "repair": "repairs",
    "REPAIRS": "repairs",
    "Repairs": "repairs",
    "REPAIR": "repairs",

    # Maintenance variations
    "maintenance": "maintenance",
    "maintance": "maintenance",  # Common typo
    "MAINTANCE": "maintenance",
    "MAINTENANCE": "maintenance",
    "Maintenance": "maintenance",

    # Mortgage variations
    "mortgage": "mortgage_interest",
    "mortgage_interest": "mortgage_interest",
    "MORTGAGE": "mortgage_interest",
    "Mortgage": "mortgage_interest",
    "MORTGAGE INTEREST": "mortgage_interest",
    "Mortgage Interest": "mortgage_interest",

    # Insurance variations
    "insurance": "insurance",
    "INSURANCE": "insurance",
    "Insurance": "insurance",

    # Utilities variations
    "utilities": "utilities",
    "utility": "utilities",
    "UTILITIES": "utilities",
    "UTILITY": "utilities",
    "Utilities": "utilities",

    # Taxes variations
    "taxes": "taxes",
    "tax": "taxes",
    "TAXES": "taxes",
    "TAX": "taxes",
    "Taxes": "taxes",
    "property_tax": "taxes",
    "PROPERTY TAX": "taxes",
    "Property Tax": "taxes",

    # HOA/Condo fee variations
    "hoa": "hoa",
    "HOA": "hoa",
    "condo_fee": "hoa",
    "condo fee": "hoa",
    "CONDO FEE": "hoa",
    "Condo Fee": "hoa",
    "association_fee": "hoa",
    "ASSOCIATION FEE": "hoa",

    # Cleaning variations
    "cleaning": "cleaning",
    "CLEANING": "cleaning",
    "Cleaning": "cleaning",

    # Landscaping variations
    "landscaping": "landscaping",
    "LANDSCAPING": "landscaping",
    "Landscaping": "landscaping",
    "lawn_care": "landscaping",
    "LAWN CARE": "landscaping",

    # Legal variations
    "legal": "legal",
    "LEGAL": "legal",
    "Legal": "legal",

    # Management fees variations
    "management_fees": "management_fees",
    "MANAGEMENT FEES": "management_fees",
    "Management Fees": "management_fees",
    "management": "management_fees",
    "MANAGEMENT": "management_fees",

    # Pest control variations
    "pest_control": "pest_control",
    "PEST CONTROL": "pest_control",
    "Pest Control": "pest_control",

    # Advertising variations
    "advertising": "advertising",
    "ADVERTISING": "advertising",
    "Advertising": "advertising",

    # Supplies variations
    "supplies": "supplies",
    "SUPPLIES": "supplies",
    "Supplies": "supplies",
    "supply": "supplies",
    "SUPPLY": "supplies",

    # Travel variations (IRS mileage reimbursement)
    "travel": "travel",
    "TRAVEL": "travel",
    "Travel": "travel",
    "mileage": "travel",
    "MILEAGE": "travel",
    "Mileage": "travel",
    "auto": "travel",
    "AUTO": "travel",
    "Auto": "travel",
    "vehicle": "travel",
    "VEHICLE": "travel",
    "Vehicle": "travel",

    # Other variations
    "other": "other",
    "OTHER": "other",
    "Other": "other",
    "miscellaneous": "other",
    "MISCELLANEOUS": "other",
}


# Display names for categories (formatted for reports)
CATEGORY_DISPLAY_NAMES: Dict[str, str] = {
    "repairs": "Repairs",
    "maintenance": "Maintenance",
    "mortgage_interest": "Mortgage Interest",
    "insurance": "Insurance",
    "utilities": "Utilities",
    "taxes": "Taxes",
    "hoa": "HOA/Condo Fee",
    "cleaning": "Cleaning",
    "landscaping": "Landscaping",
    "legal": "Legal",
    "management_fees": "Management Fees",
    "pest_control": "Pest Control",
    "advertising": "Advertising",
    "supplies": "Supplies",
    "travel": "Travel/Mileage",
    "other": "Other",
}


def normalize_category(category: Optional[str]) -> str:
    """
    Normalize a category name to its canonical form.

    This function handles:
    - Case variations (REPAIRS, Repairs, repairs -> repairs)
    - Common typos (maintance -> maintenance)
    - Alternative names (condo fee -> hoa)
    - Whitespace normalization

    Args:
        category: The category name to normalize

    Returns:
        Normalized category name in lowercase with underscores
        Returns "other" for unknown categories or None
    """
    if not category or not str(category).strip():
        return "other"

    # Clean up the input
    category_clean = str(category).strip()

    # Try direct lookup first
    if category_clean in CATEGORY_NORMALIZATION:
        return CATEGORY_NORMALIZATION[category_clean]

    # Try case-insensitive lookup
    category_lower = category_clean.lower()
    if category_lower in CATEGORY_NORMALIZATION:
        return CATEGORY_NORMALIZATION[category_lower]

    # Try with underscores converted to spaces
    category_with_spaces = category_clean.replace("_", " ")
    if category_with_spaces in CATEGORY_NORMALIZATION:
        return CATEGORY_NORMALIZATION[category_with_spaces]

    # Try with spaces converted to underscores
    category_with_underscores = category_clean.replace(" ", "_").lower()
    if category_with_underscores in CATEGORY_NORMALIZATION:
        return CATEGORY_NORMALIZATION[category_with_underscores]

    # If no match found, return as lowercase with underscores (new category)
    normalized = category_lower.replace(" ", "_")
    logger.warning(f"Unknown category '{category}' normalized to '{normalized}'")
    return normalized


def get_display_name(category: Optional[str]) -> str:
    """
    Get the display-friendly name for a category.

    Args:
        category: The normalized category name

    Returns:
        Formatted display name suitable for reports
    """
    if not category or not str(category).strip():
        return "Other"

    # Normalize first to ensure consistency
    normalized = normalize_category(category)

    # Look up display name
    if normalized in CATEGORY_DISPLAY_NAMES:
        return CATEGORY_DISPLAY_NAMES[normalized]

    # Fallback: convert underscores to spaces and title case
    return normalized.replace("_", " ").title()


def normalize_category_dict(data: Dict[str, float]) -> Dict[str, float]:
    """
    Normalize all keys in a dictionary of category->amount mappings.

    This consolidates entries with different capitalizations or spellings
    into a single canonical entry.

    Args:
        data: Dictionary mapping category names to amounts

    Returns:
        New dictionary with normalized category names
    """
    normalized = {}

    for category, amount in data.items():
        norm_category = normalize_category(category)

        # Sum amounts for categories that normalize to the same value
        if norm_category in normalized:
            normalized[norm_category] += amount
        else:
            normalized[norm_category] = amount

    return normalized
