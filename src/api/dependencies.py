"""Shared dependencies for API routes."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.data_processing.processor import FinancialDataProcessor
from src.reporting.tax_reports import TaxReporter
from src.reporting.property_reports import PropertyReportGenerator
from src.review.manager import ReviewManager
from src.utils.config import load_config

if TYPE_CHECKING:
    from src.utils.config import Config

# Global configuration
CONFIG: Config = load_config()

# Singleton instances
_PROCESSOR: FinancialDataProcessor | None = None
_REPORTER: TaxReporter | None = None
_PROPERTY_REPORTER: PropertyReportGenerator | None = None
_REVIEW_MANAGER: ReviewManager | None = None


def get_config() -> Config:
    """Get application configuration, reloading if the environment changed."""
    global CONFIG, _PROCESSOR, _REPORTER, _PROPERTY_REPORTER, _REVIEW_MANAGER
    latest = load_config()
    if latest != CONFIG:
        CONFIG = latest
        _PROCESSOR = None
        _REPORTER = None
        _PROPERTY_REPORTER = None
        _REVIEW_MANAGER = None
    return CONFIG


def get_processor() -> FinancialDataProcessor:
    """Get or create FinancialDataProcessor instance."""
    global _PROCESSOR
    config = get_config()
    if _PROCESSOR is None:
        _PROCESSOR = FinancialDataProcessor(data_dir=config.data_dir)
    return _PROCESSOR


def get_tax_reporter() -> TaxReporter:
    """Get or create TaxReporter instance."""
    global _REPORTER
    get_config()
    if _REPORTER is None:
        processor = get_processor()
        _REPORTER = TaxReporter(data_processor=processor)
    return _REPORTER


def get_property_reporter() -> PropertyReportGenerator:
    """Get or create PropertyReportGenerator instance."""
    global _PROPERTY_REPORTER
    config = get_config()
    if _PROPERTY_REPORTER is None:
        _PROPERTY_REPORTER = PropertyReportGenerator(data_dir=config.data_dir)
    return _PROPERTY_REPORTER


def get_review_manager() -> ReviewManager:
    """Get or create ReviewManager instance."""
    global _REVIEW_MANAGER
    config = get_config()
    if _REVIEW_MANAGER is None:
        _REVIEW_MANAGER = ReviewManager(data_dir=config.data_dir)
    return _REVIEW_MANAGER
