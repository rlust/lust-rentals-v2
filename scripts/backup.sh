#!/bin/bash
#
# Lust Rentals Tax Reporting - Automated Backup Script
#
# This script creates backups of:
# - SQLite databases (overrides.db, processed.db)
# - Processed CSV files
# - Configuration files
#
# Optionally uploads to cloud storage (S3, GCS, Azure)
#

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

BACKUP_ROOT="${BACKUP_ROOT:-/app/backups}"
DATA_DIR="${LUST_DATA_DIR:-/app/data}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-90}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DATE=$(date +%Y-%m-%d)
BACKUP_DIR="${BACKUP_ROOT}/${BACKUP_DATE}"

# Cloud backup destination (optional)
BACKUP_DESTINATION="${BACKUP_DESTINATION:-}"

# =============================================================================
# Logging
# =============================================================================

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
}

# =============================================================================
# Validation
# =============================================================================

if [ ! -d "$DATA_DIR" ]; then
    error "Data directory not found: $DATA_DIR"
    exit 1
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"
log "Starting backup to: $BACKUP_DIR"

# =============================================================================
# Backup Databases
# =============================================================================

backup_database() {
    local db_path="$1"
    local db_name=$(basename "$db_path")

    if [ -f "$db_path" ]; then
        log "Backing up database: $db_name"

        # Use sqlite3 to create a proper backup (handles locks)
        if command -v sqlite3 &> /dev/null; then
            sqlite3 "$db_path" ".backup '${BACKUP_DIR}/${db_name}.backup'"

            # Also create a SQL dump for portability
            sqlite3 "$db_path" .dump | gzip > "${BACKUP_DIR}/${db_name}.sql.gz"

            # Verify backup
            if sqlite3 "${BACKUP_DIR}/${db_name}.backup" "PRAGMA integrity_check;" | grep -q "ok"; then
                log "✓ Database backup verified: $db_name"
            else
                error "Database backup verification failed: $db_name"
                return 1
            fi
        else
            # Fallback: simple copy (not ideal if database is in use)
            cp "$db_path" "${BACKUP_DIR}/${db_name}.backup"
            log "⚠ Warning: sqlite3 not available, using simple copy"
        fi
    else
        log "⚠ Database not found, skipping: $db_path"
    fi
}

# Backup override database
OVERRIDES_DB="${DATA_DIR}/overrides/overrides.db"
backup_database "$OVERRIDES_DB"

# Backup processed data database
PROCESSED_DB="${DATA_DIR}/processed/processed.db"
backup_database "$PROCESSED_DB"

# =============================================================================
# Backup CSV Files
# =============================================================================

log "Backing up processed CSV files..."
if [ -d "${DATA_DIR}/processed" ]; then
    tar -czf "${BACKUP_DIR}/processed_csv_${TIMESTAMP}.tar.gz" \
        -C "${DATA_DIR}" \
        processed/*.csv 2>/dev/null || log "⚠ No CSV files found or backup failed"

    if [ -f "${BACKUP_DIR}/processed_csv_${TIMESTAMP}.tar.gz" ]; then
        log "✓ CSV files backed up"
    fi
fi

# =============================================================================
# Backup Reports
# =============================================================================

log "Backing up generated reports..."
if [ -d "${DATA_DIR}/reports" ]; then
    tar -czf "${BACKUP_DIR}/reports_${TIMESTAMP}.tar.gz" \
        -C "${DATA_DIR}" \
        reports/ 2>/dev/null || log "⚠ No reports found or backup failed"

    if [ -f "${BACKUP_DIR}/reports_${TIMESTAMP}.tar.gz" ]; then
        log "✓ Reports backed up"
    fi
fi

# =============================================================================
# Create Backup Manifest
# =============================================================================

log "Creating backup manifest..."
cat > "${BACKUP_DIR}/manifest.txt" <<EOF
Lust Rentals Tax Reporting - Backup Manifest
Date: $(date)
Timestamp: $TIMESTAMP
Data Directory: $DATA_DIR
Backup Directory: $BACKUP_DIR

Files:
EOF

ls -lh "$BACKUP_DIR" >> "${BACKUP_DIR}/manifest.txt"

# Calculate checksums
log "Calculating checksums..."
(cd "$BACKUP_DIR" && sha256sum * > checksums.sha256) || true

# =============================================================================
# Cloud Upload (Optional)
# =============================================================================

upload_to_cloud() {
    if [ -z "$BACKUP_DESTINATION" ]; then
        log "No cloud backup destination configured, skipping upload"
        return 0
    fi

    log "Uploading backup to: $BACKUP_DESTINATION"

    # Detect cloud provider from destination
    if [[ "$BACKUP_DESTINATION" == s3://* ]]; then
        # AWS S3
        if command -v aws &> /dev/null; then
            aws s3 sync "$BACKUP_DIR" "${BACKUP_DESTINATION}/${BACKUP_DATE}/" \
                --storage-class STANDARD_IA \
                --no-progress
            log "✓ Uploaded to AWS S3"
        else
            error "aws CLI not found, cannot upload to S3"
            return 1
        fi

    elif [[ "$BACKUP_DESTINATION" == gs://* ]]; then
        # Google Cloud Storage
        if command -v gsutil &> /dev/null; then
            gsutil -m rsync -r "$BACKUP_DIR" "${BACKUP_DESTINATION}/${BACKUP_DATE}/"
            log "✓ Uploaded to Google Cloud Storage"
        else
            error "gsutil not found, cannot upload to GCS"
            return 1
        fi

    elif [[ "$BACKUP_DESTINATION" == azure://* ]]; then
        # Azure Blob Storage
        CONTAINER=$(echo "$BACKUP_DESTINATION" | sed 's|azure://||' | cut -d'/' -f1)
        PATH_PREFIX=$(echo "$BACKUP_DESTINATION" | sed 's|azure://||' | cut -d'/' -f2-)

        if command -v az &> /dev/null; then
            az storage blob upload-batch \
                --account-name "$AZURE_STORAGE_ACCOUNT" \
                --destination "$CONTAINER" \
                --destination-path "${PATH_PREFIX}/${BACKUP_DATE}" \
                --source "$BACKUP_DIR" \
                --no-progress
            log "✓ Uploaded to Azure Blob Storage"
        else
            error "az CLI not found, cannot upload to Azure"
            return 1
        fi
    else
        error "Unknown backup destination format: $BACKUP_DESTINATION"
        return 1
    fi
}

upload_to_cloud

# =============================================================================
# Cleanup Old Backups
# =============================================================================

log "Cleaning up backups older than ${RETENTION_DAYS} days..."
find "$BACKUP_ROOT" -maxdepth 1 -type d -name "20*" -mtime +${RETENTION_DAYS} -exec rm -rf {} \; 2>/dev/null || true

REMAINING_BACKUPS=$(find "$BACKUP_ROOT" -maxdepth 1 -type d -name "20*" | wc -l)
log "✓ Cleanup complete. ${REMAINING_BACKUPS} backup(s) remaining"

# =============================================================================
# Backup Summary
# =============================================================================

BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "Backup completed successfully!"
log "Location: $BACKUP_DIR"
log "Size: $BACKUP_SIZE"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exit 0
