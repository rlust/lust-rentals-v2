"""
Fuzzy matching utilities for deposit mapping.

Handles typos, abbreviations, and memo variations when mapping
income deposits to properties.
"""

from typing import Optional, Tuple, List
import re
from difflib import SequenceMatcher


class FuzzyMatcher:
    """
    Fuzzy string matcher for deposit memo to property name matching.

    Uses multiple strategies:
    - Levenshtein-style similarity scoring
    - Partial substring matching
    - Address and unit number extraction
    - Common abbreviation handling
    """

    def __init__(self, similarity_threshold: float = 0.80):
        """
        Initialize fuzzy matcher.

        Args:
            similarity_threshold: Minimum similarity score (0.0-1.0) for a match
        """
        self.similarity_threshold = similarity_threshold

        # Common property-related abbreviations
        self.abbreviations = {
            'st': 'street',
            'str': 'street',
            'ave': 'avenue',
            'av': 'avenue',
            'blvd': 'boulevard',
            'dr': 'drive',
            'rd': 'road',
            'ln': 'lane',
            'ct': 'court',
            'cir': 'circle',
            'pl': 'place',
            'apt': 'apartment',
            'unit': 'unit',
            'bldg': 'building',
            'prop': 'property',
            '#': 'unit'
        }

    def match_property(
        self,
        memo: str,
        known_properties: List[str],
        threshold: Optional[float] = None
    ) -> Optional[Tuple[str, float]]:
        """
        Find the best matching property for a deposit memo.

        Args:
            memo: Transaction memo/description
            known_properties: List of known property names
            threshold: Override default similarity threshold

        Returns:
            Tuple of (property_name, confidence_score) or None if no good match
        """
        if not memo or not known_properties:
            return None

        threshold = threshold or self.similarity_threshold

        # Normalize memo
        memo_normalized = self._normalize_text(memo)

        best_match = None
        best_score = 0.0

        for property_name in known_properties:
            property_normalized = self._normalize_text(property_name)

            # Try multiple matching strategies
            scores = [
                self._exact_substring_score(memo_normalized, property_normalized),
                self._similarity_ratio(memo_normalized, property_normalized),
                self._word_overlap_score(memo_normalized, property_normalized),
                self._address_match_score(memo, property_name)
            ]

            # Take the highest score from all strategies
            score = max(scores)

            if score > best_score:
                best_score = score
                best_match = property_name

        if best_score >= threshold:
            return (best_match, best_score)

        return None

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison.

        - Lowercase
        - Expand abbreviations
        - Remove special characters
        - Collapse whitespace
        """
        text = text.lower().strip()

        # Expand common abbreviations
        words = text.split()
        expanded = []
        for word in words:
            # Remove punctuation from word
            clean_word = re.sub(r'[^\w\s]', '', word)
            expanded_word = self.abbreviations.get(clean_word, clean_word)
            expanded.append(expanded_word)

        text = ' '.join(expanded)

        # Remove all special characters except spaces
        text = re.sub(r'[^\w\s]', '', text)

        # Collapse multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def _exact_substring_score(self, memo: str, property_name: str) -> float:
        """Check if property name appears as substring in memo."""
        if property_name in memo:
            # Higher score if property name is significant portion of memo
            return 0.95 * (len(property_name) / len(memo))
        if memo in property_name:
            return 0.90 * (len(memo) / len(property_name))
        return 0.0

    def _similarity_ratio(self, memo: str, property_name: str) -> float:
        """Calculate Levenshtein-style similarity ratio."""
        return SequenceMatcher(None, memo, property_name).ratio()

    def _word_overlap_score(self, memo: str, property_name: str) -> float:
        """Calculate score based on overlapping words."""
        memo_words = set(memo.split())
        property_words = set(property_name.split())

        if not property_words:
            return 0.0

        # Intersection over property words (focus on property coverage)
        overlap = len(memo_words & property_words)
        score = overlap / len(property_words)

        return score

    def _address_match_score(self, memo: str, property_name: str) -> float:
        """
        Score based on address components (numbers, street names).

        Addresses are highly distinctive, so matching on address gives high confidence.
        """
        # Extract numbers (likely street numbers or unit numbers)
        memo_numbers = set(re.findall(r'\d+', memo))
        property_numbers = set(re.findall(r'\d+', property_name))

        if not property_numbers:
            return 0.0

        # If key numbers match, that's a strong signal
        number_overlap = len(memo_numbers & property_numbers) / len(property_numbers)

        if number_overlap >= 0.5:
            # Numbers match, now check street names
            memo_norm = self._normalize_text(memo)
            property_norm = self._normalize_text(property_name)

            # Remove numbers to compare street names
            memo_no_nums = re.sub(r'\d+', '', memo_norm).strip()
            property_no_nums = re.sub(r'\d+', '', property_norm).strip()

            if memo_no_nums and property_no_nums:
                word_score = self._word_overlap_score(memo_no_nums, property_no_nums)
                return 0.85 + (0.15 * word_score)  # High base score + word boost

        return 0.0

    def find_all_matches(
        self,
        memo: str,
        known_properties: List[str],
        top_n: int = 3
    ) -> List[Tuple[str, float]]:
        """
        Find top N matching properties with scores.

        Useful for showing user multiple options to choose from.

        Args:
            memo: Transaction memo
            known_properties: List of known property names
            top_n: Number of top matches to return

        Returns:
            List of (property_name, score) tuples, sorted by score descending
        """
        if not memo or not known_properties:
            return []

        memo_normalized = self._normalize_text(memo)

        scores = []
        for property_name in known_properties:
            property_normalized = self._normalize_text(property_name)

            # Calculate all strategy scores
            all_scores = [
                self._exact_substring_score(memo_normalized, property_normalized),
                self._similarity_ratio(memo_normalized, property_normalized),
                self._word_overlap_score(memo_normalized, property_normalized),
                self._address_match_score(memo, property_name)
            ]

            # Take max score
            score = max(all_scores)
            scores.append((property_name, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        # Return top N
        return scores[:top_n]

    def extract_unit_number(self, memo: str) -> Optional[str]:
        """
        Extract unit/apartment number from memo.

        Patterns like:
        - "Unit 5A"
        - "Apt 102"
        - "#204"
        - "Suite 3B"
        """
        patterns = [
            r'(?:unit|apt|apartment|suite|#)\s*([0-9]+[A-Za-z]?)',
            r'(?:unit|apt|apartment|suite|#)\s*([A-Za-z][0-9]+)',
        ]

        memo_lower = memo.lower()
        for pattern in patterns:
            match = re.search(pattern, memo_lower)
            if match:
                return match.group(1).upper()

        # Fallback: look for standalone numbers that might be unit numbers
        # (but only if they're not too large to be street addresses)
        numbers = re.findall(r'\b(\d{1,4}[A-Za-z]?)\b', memo)
        if numbers:
            # Return the first reasonable unit number
            for num in numbers:
                if len(num) <= 4:  # Reasonable unit number length
                    return num

        return None

    def extract_address(self, memo: str) -> Optional[str]:
        """
        Extract street address from memo.

        Patterns like:
        - "123 Main St"
        - "456 Oak Avenue"
        """
        # Look for number + street name + street type
        pattern = r'(\d+\s+[A-Za-z]+\s+(?:street|st|avenue|ave|road|rd|lane|ln|drive|dr|boulevard|blvd|court|ct|place|pl))'
        match = re.search(pattern, memo, re.IGNORECASE)
        if match:
            return match.group(1)

        return None
