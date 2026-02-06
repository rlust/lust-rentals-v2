"""Configuration utilities for Lust Rentals processing and reporting."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class AppConfig:
    """Application configuration resolved from environment variables."""

    data_dir: Path
    log_level: str = "INFO"


def _normalize_data_dir(path_str: str) -> Path:
    """Ensure a data directory path is absolute and expanded."""

    raw_path = Path(path_str).expanduser()
    if raw_path.is_absolute():
        return raw_path
    return (Path.cwd() / raw_path).resolve()


def load_config(data_dir_override: Optional[str] = None) -> AppConfig:
    """Load application configuration, optionally overriding the data directory."""

    data_dir_env = data_dir_override or os.getenv("LUST_DATA_DIR", "data")
    log_level_env = os.getenv("LUST_LOG_LEVEL", "INFO").upper()

    return AppConfig(
        data_dir=_normalize_data_dir(data_dir_env),
        log_level=log_level_env,
    )


def configure_logging(level: str) -> None:
    """Configure root logging with a consistent format."""

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()

    if not root_logger.handlers:
        logging.basicConfig(
            level=numeric_level,
            format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        )
    else:
        root_logger.setLevel(numeric_level)


__all__ = ["AppConfig", "load_config", "configure_logging"]
