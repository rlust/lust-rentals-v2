"""
Enhanced expense categorization with merchant database and rule engine.

This module provides intelligent categorization for expenses using:
- Merchant name database matching
- Regex pattern recognition
- Amount-based heuristics
- Confidence scoring
"""

import re
import logging
from typing import Tuple, Dict, List, Optional, Any
from dataclasses import dataclass

# Type alias for the rule evaluator function
# Should take a dict of transaction fields and return (category, property_name, rule_name)
# or (None, None, None)
RuleEvaluator = Any 

logger = logging.getLogger(__name__)


# Comprehensive merchant database mapping common vendors to categories
MERCHANT_DATABASE: Dict[str, str] = {
    # Home improvement & repairs
    "home depot": "repairs",
    "homedepot": "repairs",
    "lowes": "repairs",
    "lowe's": "repairs",
    "ace hardware": "repairs",
    "menards": "repairs",
    "true value": "repairs",

    # Insurance
    "state farm": "insurance",
    "allstate": "insurance",
    "geico": "insurance",
    "progressive": "insurance",
    "farmers insurance": "insurance",
    "liberty mutual": "insurance",
    "nationwide": "insurance",
    "usaa": "insurance",

    # Mortgage & financing
    "rocket mortgage": "mortgage_interest",
    "quicken loans": "mortgage_interest",
    "wells fargo mortgage": "mortgage_interest",
    "chase mortgage": "mortgage_interest",
    "bank of america mortgage": "mortgage_interest",
    "us bank mortgage": "mortgage_interest",

    # Utilities
    "electric": "utilities",
    "electricity": "utilities",
    "power company": "utilities",
    "gas company": "utilities",
    "natural gas": "utilities",
    "water": "utilities",
    "sewer": "utilities",
    "aep": "utilities",
    "duke energy": "utilities",
    "national grid": "utilities",
    "pg&e": "utilities",
    "pge": "utilities",

    # Repairs & maintenance
    "plumbing": "repairs",
    "plumber": "repairs",
    "hvac": "repairs",
    "heating": "repairs",
    "cooling": "repairs",
    "roto-rooter": "repairs",
    "roto rooter": "repairs",
    "mr handyman": "repairs",
    "handyman": "repairs",
    "appliance repair": "repairs",
    "locksmith": "repairs",

    # Legal & professional
    "attorney": "legal",
    "law office": "legal",
    "law firm": "legal",
    "legal services": "legal",

    # Property management
    "property management": "management_fees",
    "property manager": "management_fees",
    "pm company": "management_fees",

    # Cleaning & maintenance
    "maid": "cleaning",
    "cleaning service": "cleaning",
    "molly maid": "cleaning",
    "merry maids": "cleaning",
    "janitorial": "cleaning",

    # Landscaping & lawn care
    "landscape": "landscaping",
    "landscaping": "landscaping",
    "tree service": "landscaping",
    "lawn care": "landscaping",
    "trugreen": "landscaping",
    "scotts": "landscaping",

    # Pest control
    "pest control": "pest_control",
    "exterminator": "pest_control",
    "terminix": "pest_control",
    "orkin": "pest_control",

    # HOA
    "hoa": "hoa",
    "homeowners association": "hoa",
    "condo association": "hoa",

    # Taxes
    "tax": "taxes",
    "property tax": "taxes",
    "county treasurer": "taxes",
    "tax collector": "taxes",

    # Advertising
    "zillow": "advertising",
    "trulia": "advertising",
    "craigslist": "advertising",
    "apartments.com": "advertising",
    "facebook ads": "advertising",

    # Supplies
    "supply": "supplies",
    "supplies": "supplies",
    "hardware": "supplies",
}


# Regex patterns for complex matching
@dataclass
class CategoryPattern:
    """Pattern definition for category matching."""
    pattern: str
    category: str
    confidence: float
    description: str


CATEGORY_PATTERNS: List[CategoryPattern] = [
    # Mortgage patterns
    CategoryPattern(
        pattern=r"mortgage.*\d{4,}",
        category="mortgage_interest",
        confidence=0.90,
        description="Mortgage with account number"
    ),
    CategoryPattern(
        pattern=r"\bpayment\s*\d+\s*of\s*\d+",
        category="mortgage_interest",
        confidence=0.85,
        description="Payment X of Y pattern"
    ),
    CategoryPattern(
        pattern=r"loan.*payment",
        category="mortgage_interest",
        confidence=0.80,
        description="Loan payment mention"
    ),

    # Insurance patterns
    CategoryPattern(
        pattern=r"insurance.*policy",
        category="insurance",
        confidence=0.90,
        description="Insurance policy reference"
    ),
    CategoryPattern(
        pattern=r"policy\s*#?\s*\d+",
        category="insurance",
        confidence=0.85,
        description="Policy number pattern"
    ),

    # Repair patterns
    CategoryPattern(
        pattern=r"repair.*invoice",
        category="repairs",
        confidence=0.85,
        description="Repair invoice"
    ),
    CategoryPattern(
        pattern=r"service.*call",
        category="repairs",
        confidence=0.70,
        description="Service call"
    ),
    CategoryPattern(
        pattern=r"emergency.*repair",
        category="repairs",
        confidence=0.90,
        description="Emergency repair"
    ),

    # Tax patterns
    CategoryPattern(
        pattern=r"property\s*tax",
        category="taxes",
        confidence=0.95,
        description="Property tax explicit"
    ),
    CategoryPattern(
        pattern=r"real\s*estate\s*tax",
        category="taxes",
        confidence=0.95,
        description="Real estate tax"
    ),

    # Utility patterns
    CategoryPattern(
        pattern=r"electric.*bill",
        category="utilities",
        confidence=0.90,
        description="Electric bill"
    ),
    CategoryPattern(
        pattern=r"water.*bill",
        category="utilities",
        confidence=0.90,
        description="Water bill"
    ),
    CategoryPattern(
        pattern=r"gas.*bill",
        category="utilities",
        confidence=0.90,
        description="Gas bill"
    ),

    # HOA patterns
    CategoryPattern(
        pattern=r"hoa.*dues",
        category="hoa",
        confidence=0.95,
        description="HOA dues"
    ),
    CategoryPattern(
        pattern=r"association.*fee",
        category="hoa",
        confidence=0.85,
        description="Association fee"
    ),
]


# Simple keyword-based fallback matching
KEYWORD_CATEGORIES: Dict[str, float] = {
    "insurance": 0.70,
    "mortgage": 0.70,
    "repair": 0.65,
    "fix": 0.60,
    "utility": 0.65,
    "utilities": 0.70,
    "tax": 0.75,
    "taxes": 0.75,
    "cleaning": 0.75,
    "landscape": 0.70,
    "pest": 0.75,
    "hoa": 0.80,
    "management": 0.70,
    "legal": 0.75,
    "advertising": 0.75,
}


class EnhancedCategorizer:
    """
    Intelligent expense categorization engine.

    Uses multiple strategies with confidence scoring:
    1. Merchant database matching (highest confidence)
    2. Regex pattern matching (medium-high confidence)
    3. Keyword matching (lower confidence)
    4. Amount-based heuristics (contextual)
    """

    def __init__(self, merchant_db: Optional[Dict[str, str]] = None, rule_evaluator: Optional[RuleEvaluator] = None):
        """
        Initialize the categorizer.

        Args:
            merchant_db: Optional custom merchant database (uses default if None)
            rule_evaluator: Optional object/function with evaluate_transaction method
        """
        self.merchant_db = merchant_db or MERCHANT_DATABASE
        self.patterns = CATEGORY_PATTERNS
        self.keywords = KEYWORD_CATEGORIES
        self.rule_evaluator = rule_evaluator
        self.logger = logging.getLogger(self.__class__.__name__)

        self.logger.info(f"Initialized with {len(self.merchant_db)} merchants, "
                        f"{len(self.patterns)} patterns, {len(self.keywords)} keywords")

    def categorize(
        self,
        description: str,
        amount: float = 0.0,
        payee: str = "",
        memo: str = ""
    ) -> Tuple[str, float, str]:
        """
        Categorize an expense with confidence scoring.

        Args:
            description: Transaction description
            amount: Transaction amount (optional, for amount-based rules)
            payee: Payee name (optional)
            memo: Transaction memo (optional)

        Returns:
            Tuple of (category, confidence, match_reason)
            - category: Assigned category name
            - confidence: Score from 0.0 to 1.0 (1.0 = certain)
            - match_reason: Explanation of why this category was chosen
        """
        # Normalize inputs
        desc_lower = str(description).lower().strip()
        payee_lower = str(payee).lower().strip()
        memo_lower = str(memo).lower().strip()

        # Combine all text fields for searching
        combined_text = f"{desc_lower} {payee_lower} {memo_lower}"

        # Strategy 0: User-defined Rules (Highest priority)
        if self.rule_evaluator:
            # Construct transaction dict for rule evaluation
            tx_data = {
                "description": description,
                "memo": memo,
                "amount": str(amount),
                "payee": payee
            }
            actions, rule_name = self.rule_evaluator.evaluate_transaction(tx_data)

            for action in actions:
                if action.get("type") == "set_category":
                    return (action.get("value", ""), 1.0, f"Matched rule: {rule_name}")
            # Note: Property assignment from rules is handled separately in the processor.

        # Strategy 1: Merchant database (highest confidence)
        result = self._match_merchant(combined_text)
        if result:
            return result

        # Strategy 2: Regex patterns (medium-high confidence)
        result = self._match_patterns(combined_text)
        if result:
            return result

        # Strategy 3: Keyword matching (lower confidence)
        result = self._match_keywords(combined_text)
        if result:
            return result

        # Strategy 4: Amount-based heuristics (contextual)
        if amount > 0:
            result = self._match_by_amount(amount, combined_text)
            if result:
                return result

        # Default: uncategorized
        return ("other", 0.0, "No matching rule found")

    def _match_merchant(self, text: str) -> Optional[Tuple[str, float, str]]:
        """Match against merchant database."""
        for merchant, category in self.merchant_db.items():
            if merchant in text:
                confidence = 0.95  # High confidence for exact merchant match
                reason = f"Matched merchant: '{merchant}'"
                self.logger.debug(f"Merchant match: {merchant} -> {category} (confidence: {confidence})")
                return (category, confidence, reason)
        return None

    def _match_patterns(self, text: str) -> Optional[Tuple[str, float, str]]:
        """Match against regex patterns."""
        for pattern_obj in self.patterns:
            if re.search(pattern_obj.pattern, text, re.IGNORECASE):
                self.logger.debug(f"Pattern match: {pattern_obj.description} -> "
                                f"{pattern_obj.category} (confidence: {pattern_obj.confidence})")
                return (
                    pattern_obj.category,
                    pattern_obj.confidence,
                    f"Matched pattern: {pattern_obj.description}"
                )
        return None

    def _match_keywords(self, text: str) -> Optional[Tuple[str, float, str]]:
        """Match against simple keywords."""
        for keyword, confidence in self.keywords.items():
            if keyword in text:
                # Determine category from keyword
                category = self._keyword_to_category(keyword)
                reason = f"Matched keyword: '{keyword}'"
                self.logger.debug(f"Keyword match: {keyword} -> {category} (confidence: {confidence})")
                return (category, confidence, reason)
        return None

    def _match_by_amount(self, amount: float, text: str) -> Optional[Tuple[str, float, str]]:
        """
        Use amount-based heuristics for categorization.

        This is contextual and lower confidence, but can help with recurring expenses.
        """
        # Example: Large regular amounts might be mortgage
        if amount > 1000 and ("pmt" in text or "payment" in text):
            return ("mortgage_interest", 0.60, "Large regular payment heuristic")

        # Small regular amounts might be utilities
        if 50 < amount < 500:
            if "monthly" in text or "bill" in text:
                return ("utilities", 0.55, "Monthly bill amount heuristic")

        return None

    def _keyword_to_category(self, keyword: str) -> str:
        """Map keyword to category name."""
        keyword_map = {
            "insurance": "insurance",
            "mortgage": "mortgage_interest",
            "repair": "repairs",
            "fix": "repairs",
            "utility": "utilities",
            "utilities": "utilities",
            "tax": "taxes",
            "taxes": "taxes",
            "cleaning": "cleaning",
            "landscape": "landscaping",
            "pest": "pest_control",
            "hoa": "hoa",
            "management": "management_fees",
            "legal": "legal",
            "advertising": "advertising",
        }
        return keyword_map.get(keyword, "other")

    def add_merchant(self, merchant_name: str, category: str) -> None:
        """
        Add a new merchant to the database.

        Args:
            merchant_name: Merchant name or pattern (case-insensitive)
            category: Category to assign
        """
        self.merchant_db[merchant_name.lower()] = category
        self.logger.info(f"Added merchant: {merchant_name} -> {category}")

    def add_pattern(
        self,
        pattern: str,
        category: str,
        confidence: float = 0.80,
        description: str = "Custom pattern"
    ) -> None:
        """
        Add a new regex pattern.

        Args:
            pattern: Regex pattern
            category: Category to assign
            confidence: Confidence score (0.0-1.0)
            description: Description of what the pattern matches
        """
        pattern_obj = CategoryPattern(
            pattern=pattern,
            category=category,
            confidence=confidence,
            description=description
        )
        self.patterns.append(pattern_obj)
        self.logger.info(f"Added pattern: {description} -> {category}")

    def get_statistics(self) -> Dict[str, int]:
        """Get statistics about the categorization engine."""
        return {
            "merchants": len(self.merchant_db),
            "patterns": len(self.patterns),
            "keywords": len(self.keywords),
            "categories": len(set(self.merchant_db.values()))
        }
