"""Compatibility shim for legacy imports.

Historically the ReviewManager lived under ``src.data_processing``. When it was
moved to :mod:`src.review.manager`, older modules (and the test suite) still
imported ``src.data_processing.review_manager`` and instantiated ``ReviewManager``
without arguments.  This shim preserves that behavior by defaulting the
``data_dir`` to ``$LUST_DATA_DIR`` (or ``./data`` as a fallback) before
delegating to the real implementation.
"""
from __future__ import annotations

import os
from pathlib import Path

from src.review.manager import ReviewManager as _ReviewManager


def _resolve_data_dir(data_dir: Path | str | None) -> Path:
    if data_dir is not None:
        return Path(data_dir)

    env_dir = os.environ.get("LUST_DATA_DIR")
    if env_dir:
        return Path(env_dir)

    # Tests that import this shim without configuring a data dir still expect a
    # writable location.  Default to ./data to mirror the original behavior.
    return Path.cwd() / "data"


class ReviewManager(_ReviewManager):
    def __init__(self, data_dir: Path | str | None = None) -> None:
        super().__init__(data_dir=_resolve_data_dir(data_dir))


__all__ = ["ReviewManager"]
