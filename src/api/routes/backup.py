"""Backup and export API routes."""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.api.dependencies import get_config
from src.utils.backup import DataBackupManager

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================

class BackupResponse(BaseModel):
    """Response from backup operations."""
    status: str
    backup_file: str
    backup_name: str
    timestamp: str
    size_mb: float
    include_reports: Optional[bool] = None


class ExportResponse(BaseModel):
    """Response from export operations."""
    status: str
    export_dir: Optional[str] = None
    package_file: Optional[str] = None
    timestamp: str
    year: Optional[int] = None
    tables_exported: Optional[int] = None
    items_exported: Optional[int] = None
    size_mb: Optional[float] = None


class BackupInfo(BaseModel):
    """Information about a backup file."""
    name: str
    path: str
    size_mb: float
    created: str


# ============================================================================
# Backup Endpoints
# ============================================================================

@router.post("/create", response_model=BackupResponse)
def create_full_backup(
    http_request: Request,
    include_reports: bool = True
) -> BackupResponse:
    """
    Create a complete backup of all data.

    Args:
        include_reports: Whether to include generated reports in the backup

    Returns:
        Backup information including file path and size
    """
    logger.info(f"Creating full backup (include_reports={include_reports})")

    try:
        manager = DataBackupManager(get_config().data_dir)
        result = manager.create_full_backup(include_reports=include_reports)

        return BackupResponse(**result)

    except Exception as e:
        logger.error(f"Error creating backup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")


@router.post("/database", response_model=BackupResponse)
def backup_database_only(http_request: Request) -> BackupResponse:
    """
    Create a backup of just the processed database.

    Returns:
        Backup information including file path and size
    """
    logger.info("Creating database-only backup")

    try:
        manager = DataBackupManager(get_config().data_dir)
        result = manager.backup_database_only()

        return BackupResponse(**result)

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error backing up database: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database backup failed: {str(e)}")


@router.get("/list", response_model=List[BackupInfo])
def list_backups(http_request: Request) -> List[BackupInfo]:
    """
    List all available backups.

    Returns:
        List of backup files with metadata
    """
    logger.info("Listing backups")

    try:
        manager = DataBackupManager(get_config().data_dir)
        backups = manager.list_backups()

        return [BackupInfo(**backup) for backup in backups]

    except Exception as e:
        logger.error(f"Error listing backups: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list backups: {str(e)}")


@router.get("/download/{backup_name}")
def download_backup(http_request: Request, backup_name: str):
    """
    Download a specific backup file.

    Args:
        backup_name: Name of the backup file to download

    Returns:
        File download response
    """
    logger.info(f"Download requested for backup: {backup_name}")

    try:
        manager = DataBackupManager(get_config().data_dir)
        backup_path = manager.backup_dir / backup_name

        if not backup_path.exists():
            raise HTTPException(status_code=404, detail=f"Backup file not found: {backup_name}")

        # Security check: ensure the file is actually in the backups directory
        if not backup_path.resolve().is_relative_to(manager.backup_dir.resolve()):
            raise HTTPException(status_code=403, detail="Invalid backup file path")

        return FileResponse(
            path=backup_path,
            filename=backup_name,
            media_type='application/zip' if backup_name.endswith('.zip') else 'application/octet-stream'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading backup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


# ============================================================================
# Export Endpoints
# ============================================================================

@router.post("/export/database", response_model=ExportResponse)
def export_database_tables(
    http_request: Request,
    year: Optional[int] = None
) -> ExportResponse:
    """
    Export all database tables to CSV files.

    Args:
        year: Optional year to filter data (exports all data if not specified)

    Returns:
        Export information including directory path and file count
    """
    logger.info(f"Exporting database tables (year={year})")

    try:
        manager = DataBackupManager(get_config().data_dir)
        result = manager.export_database_tables(year=year)

        return ExportResponse(**result)

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting database: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.post("/export/accountant", response_model=ExportResponse)
def export_for_accountant(
    http_request: Request,
    year: int
) -> ExportResponse:
    """
    Create a comprehensive export package for your accountant.

    Includes:
    - All income transactions
    - All expense transactions grouped by property
    - Property summary report
    - Database backup
    - Generated tax reports
    - README with file descriptions

    Args:
        year: Tax year to export

    Returns:
        Export package information including file path and size
    """
    logger.info(f"Creating accountant export package for year {year}")

    try:
        manager = DataBackupManager(get_config().data_dir)
        result = manager.export_for_accountant(year)

        return ExportResponse(**result)

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating accountant package: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Accountant export failed: {str(e)}")


@router.get("/export/download/{package_name}")
def download_export_package(http_request: Request, package_name: str):
    """
    Download a specific export package.

    Args:
        package_name: Name of the export package to download

    Returns:
        File download response
    """
    logger.info(f"Download requested for export package: {package_name}")

    try:
        manager = DataBackupManager(get_config().data_dir)
        package_path = manager.backup_dir / package_name

        if not package_path.exists():
            raise HTTPException(status_code=404, detail=f"Export package not found: {package_name}")

        # Security check: ensure the file is actually in the backups directory
        if not package_path.resolve().is_relative_to(manager.backup_dir.resolve()):
            raise HTTPException(status_code=403, detail="Invalid package file path")

        return FileResponse(
            path=package_path,
            filename=package_name,
            media_type='application/zip'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading export package: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


# ============================================================================
# Restore Endpoints
# ============================================================================

@router.post("/restore")
def restore_backup(
    http_request: Request,
    backup_name: str
) -> dict:
    """
    Restore data from a backup file.

    CAUTION: This will overwrite existing data. A safety backup is created first.

    Args:
        backup_name: Name of the backup file to restore

    Returns:
        Restore information including safety backup path
    """
    logger.warning(f"Restore requested for backup: {backup_name}")

    try:
        manager = DataBackupManager(get_config().data_dir)
        backup_path = manager.backup_dir / backup_name

        if not backup_path.exists():
            raise HTTPException(status_code=404, detail=f"Backup file not found: {backup_name}")

        result = manager.restore_backup(str(backup_path))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restoring backup: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Restore failed: {str(e)}")
