#!/bin/bash
#
# Lust Rentals Tax Reporting - Backup Restore Script
#
# This script restores backups created by backup.sh
#

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

BACKUP_ROOT="${BACKUP_ROOT:-/app/backups}"
DATA_DIR="${LUST_DATA_DIR:-/app/data}"

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
# Usage
# =============================================================================

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Restore Lust Rentals Tax Reporting backups

OPTIONS:
    -d DATE         Backup date to restore (format: YYYY-MM-DD)
    -l              List available backups
    -h              Show this help message

EXAMPLES:
    # List available backups
    $0 -l

    # Restore specific backup
    $0 -d 2025-01-15

    # Restore latest backup
    $0 -d latest
EOF
    exit 1
}

# =============================================================================
# List Backups
# =============================================================================

list_backups() {
    log "Available backups in: $BACKUP_ROOT"
    echo ""

    if [ ! -d "$BACKUP_ROOT" ]; then
        error "Backup directory not found: $BACKUP_ROOT"
        exit 1
    fi

    local backups=$(find "$BACKUP_ROOT" -maxdepth 1 -type d -name "20*" | sort -r)

    if [ -z "$backups" ]; then
        log "No backups found"
        exit 0
    fi

    printf "%-15s %-15s %-s\n" "DATE" "SIZE" "FILES"
    printf "%-15s %-15s %-s\n" "----" "----" "-----"

    for backup_dir in $backups; do
        local date=$(basename "$backup_dir")
        local size=$(du -sh "$backup_dir" 2>/dev/null | cut -f1)
        local files=$(ls -1 "$backup_dir" 2>/dev/null | wc -l)

        printf "%-15s %-15s %-s\n" "$date" "$size" "$files files"
    done

    exit 0
}

# =============================================================================
# Restore Function
# =============================================================================

restore_backup() {
    local backup_date="$1"

    # Handle "latest" keyword
    if [ "$backup_date" = "latest" ]; then
        backup_date=$(find "$BACKUP_ROOT" -maxdepth 1 -type d -name "20*" | sort -r | head -n1 | xargs basename)
        log "Using latest backup: $backup_date"
    fi

    local backup_dir="${BACKUP_ROOT}/${backup_date}"

    if [ ! -d "$backup_dir" ]; then
        error "Backup not found: $backup_dir"
        exit 1
    fi

    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Restoring backup from: $backup_date"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Verify checksums
    if [ -f "${backup_dir}/checksums.sha256" ]; then
        log "Verifying backup integrity..."
        (cd "$backup_dir" && sha256sum -c checksums.sha256 --quiet) || {
            error "Checksum verification failed!"
            exit 1
        }
        log "✓ Backup integrity verified"
    else
        log "⚠ Warning: No checksums found, skipping verification"
    fi

    # Confirm before proceeding
    echo ""
    log "WARNING: This will overwrite existing data!"
    read -p "Are you sure you want to continue? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        log "Restore cancelled"
        exit 0
    fi

    # Create backup of current state before restore
    log "Creating backup of current state..."
    local pre_restore_backup="${DATA_DIR}_pre_restore_$(date +%Y%m%d_%H%M%S)"
    if [ -d "$DATA_DIR" ]; then
        cp -r "$DATA_DIR" "$pre_restore_backup"
        log "✓ Current state backed up to: $pre_restore_backup"
    fi

    # Restore databases
    restore_database() {
        local db_backup="$1"
        local db_destination="$2"

        if [ -f "$db_backup" ]; then
            log "Restoring database: $(basename "$db_backup")"
            mkdir -p "$(dirname "$db_destination")"
            cp "$db_backup" "$db_destination"

            # Verify restored database
            if command -v sqlite3 &> /dev/null; then
                if sqlite3 "$db_destination" "PRAGMA integrity_check;" | grep -q "ok"; then
                    log "✓ Database restored and verified: $(basename "$db_destination")"
                else
                    error "Database integrity check failed: $(basename "$db_destination")"
                    return 1
                fi
            fi
        else
            log "⚠ Database backup not found: $db_backup"
        fi
    }

    # Restore overrides database
    restore_database \
        "${backup_dir}/overrides.db.backup" \
        "${DATA_DIR}/overrides/overrides.db"

    # Restore processed database
    restore_database \
        "${backup_dir}/processed.db.backup" \
        "${DATA_DIR}/processed/processed.db"

    # Restore CSV files
    log "Restoring CSV files..."
    local csv_archive=$(find "$backup_dir" -name "processed_csv_*.tar.gz" | head -n1)
    if [ -f "$csv_archive" ]; then
        mkdir -p "${DATA_DIR}/processed"
        tar -xzf "$csv_archive" -C "$DATA_DIR"
        log "✓ CSV files restored"
    else
        log "⚠ CSV archive not found"
    fi

    # Restore reports
    log "Restoring reports..."
    local reports_archive=$(find "$backup_dir" -name "reports_*.tar.gz" | head -n1)
    if [ -f "$reports_archive" ]; then
        mkdir -p "${DATA_DIR}/reports"
        tar -xzf "$reports_archive" -C "$DATA_DIR"
        log "✓ Reports restored"
    else
        log "⚠ Reports archive not found"
    fi

    # Display manifest
    if [ -f "${backup_dir}/manifest.txt" ]; then
        echo ""
        log "Backup manifest:"
        cat "${backup_dir}/manifest.txt"
    fi

    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "Restore completed successfully!"
    log "Pre-restore backup: $pre_restore_backup"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# =============================================================================
# Main
# =============================================================================

# Parse arguments
while getopts "d:lh" opt; do
    case $opt in
        d) BACKUP_DATE="$OPTARG" ;;
        l) list_backups ;;
        h) usage ;;
        *) usage ;;
    esac
done

if [ -z "${BACKUP_DATE:-}" ]; then
    error "Missing required argument: -d DATE"
    echo ""
    usage
fi

restore_backup "$BACKUP_DATE"
