#!/usr/bin/env bash

###############################################################################
# Mac Mini Backup Script for Lust Rentals Tax Reporting
#
# Creates comprehensive backups of your tax data with multiple backup targets:
# 1. External drive (primary backup)
# 2. iCloud Drive (automatic cloud sync)
# 3. Optional: Time Machine (system-level backup)
#
# Backups include:
# - SQLite databases
# - Uploaded CSV files
# - Generated reports
# - Configuration files (excluding secrets)
# - Logs (last 7 days)
#
# Usage:
#   ./mac-backup.sh              # Create backup
#   ./mac-backup.sh setup        # Configure backup locations
#   ./mac-backup.sh restore      # Restore from backup
#   ./mac-backup.sh list         # List available backups
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get directories
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load environment if exists
if [ -f "$PROJECT_DIR/.env.production" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env.production" | xargs)
fi

# Backup configuration
BACKUP_EXTERNAL="${BACKUP_DIR:-/Volumes/Backup/lust-rentals-backups}"
BACKUP_ICLOUD="${BACKUP_CLOUD_DIR:-$HOME/Library/Mobile Documents/com~apple~CloudDocs/TaxBackups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-90}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="lust-rentals-backup-${TIMESTAMP}"

# Helper functions
print_step() { echo -e "\n${BLUE}▶${NC} ${1}"; }
print_success() { echo -e "${GREEN}✓${NC} ${1}"; }
print_warning() { echo -e "${YELLOW}⚠${NC} ${1}"; }
print_error() { echo -e "${RED}✗${NC} ${1}"; }

###############################################################################
# Backup Functions
###############################################################################

create_backup() {
    local dest_dir="$1"
    local backup_path="$dest_dir/$BACKUP_NAME"

    print_step "Creating backup at: $dest_dir"

    # Create backup directory
    mkdir -p "$backup_path"

    # Backup databases
    print_step "Backing up databases..."
    if [ -d "$PROJECT_DIR/data/processed" ]; then
        cp -r "$PROJECT_DIR/data/processed" "$backup_path/"
        print_success "Processed data backed up"
    fi

    if [ -d "$PROJECT_DIR/data/overrides" ]; then
        cp -r "$PROJECT_DIR/data/overrides" "$backup_path/"
        print_success "Overrides backed up"
    fi

    # Backup raw data
    print_step "Backing up raw transaction files..."
    if [ -d "$PROJECT_DIR/data/raw" ]; then
        mkdir -p "$backup_path/raw"
        # Only backup CSV files
        find "$PROJECT_DIR/data/raw" -name "*.csv" -exec cp {} "$backup_path/raw/" \; 2>/dev/null || true
        print_success "Raw data backed up"
    fi

    # Backup reports
    print_step "Backing up generated reports..."
    if [ -d "$PROJECT_DIR/data/reports" ]; then
        cp -r "$PROJECT_DIR/data/reports" "$backup_path/"
        print_success "Reports backed up"
    fi

    # Backup configuration (excluding secrets)
    print_step "Backing up configuration..."
    mkdir -p "$backup_path/config"

    # Copy docker compose files
    cp "$PROJECT_DIR/docker-compose.production.yml" "$backup_path/config/" 2>/dev/null || true
    cp "$PROJECT_DIR/Dockerfile" "$backup_path/config/" 2>/dev/null || true

    # Copy sanitized env file (remove secrets)
    if [ -f "$PROJECT_DIR/.env.production" ]; then
        grep -v "PASSWORD\|SECRET\|KEY" "$PROJECT_DIR/.env.production" > "$backup_path/config/.env.template" || true
        print_success "Configuration backed up (secrets excluded)"
    fi

    # Backup logs (last 7 days)
    print_step "Backing up recent logs..."
    if [ -d "$PROJECT_DIR/logs" ]; then
        mkdir -p "$backup_path/logs"
        find "$PROJECT_DIR/logs" -type f -mtime -7 -exec cp {} "$backup_path/logs/" \; 2>/dev/null || true
        print_success "Recent logs backed up"
    fi

    # Create backup manifest
    print_step "Creating backup manifest..."
    cat > "$backup_path/MANIFEST.txt" << EOF
Lust Rentals Tax Reporting Backup
Created: $(date)
Hostname: $(hostname)
User: $(whoami)

Backup Contents:
$(du -sh "$backup_path"/* 2>/dev/null || echo "Size calculation pending")

Files:
$(find "$backup_path" -type f | wc -l | xargs) files
$(find "$backup_path" -type d | wc -l | xargs) directories

Database Files:
$(find "$backup_path" -name "*.db" -exec ls -lh {} \; 2>/dev/null || echo "No database files")

To restore this backup:
1. Run: ./scripts/mac-backup.sh restore
2. Select this backup: $BACKUP_NAME
3. Confirm restoration
EOF

    print_success "Manifest created"

    # Compress backup if requested
    if [ "$BACKUP_ENCRYPT" = "true" ] && [ -n "$BACKUP_PASSWORD" ]; then
        print_step "Encrypting backup..."
        cd "$dest_dir"
        tar czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"
        openssl enc -aes-256-cbc -salt -in "${BACKUP_NAME}.tar.gz" -out "${BACKUP_NAME}.tar.gz.enc" -pass pass:"$BACKUP_PASSWORD"
        rm "${BACKUP_NAME}.tar.gz"
        rm -rf "$BACKUP_NAME"
        print_success "Backup encrypted: ${BACKUP_NAME}.tar.gz.enc"
    else
        # Just compress
        print_step "Compressing backup..."
        cd "$dest_dir"
        tar czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"
        rm -rf "$BACKUP_NAME"
        print_success "Backup compressed: ${BACKUP_NAME}.tar.gz"
    fi

    # Calculate size
    if [ "$BACKUP_ENCRYPT" = "true" ]; then
        BACKUP_SIZE=$(du -h "${BACKUP_NAME}.tar.gz.enc" | cut -f1)
        print_success "Backup complete: ${BACKUP_SIZE}"
    else
        BACKUP_SIZE=$(du -h "${BACKUP_NAME}.tar.gz" | cut -f1)
        print_success "Backup complete: ${BACKUP_SIZE}"
    fi
}

perform_backup() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║            Creating Tax Data Backup                     ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Backup to external drive
    if [ -d "$(dirname "$BACKUP_EXTERNAL")" ]; then
        print_step "Backing up to external drive..."
        mkdir -p "$BACKUP_EXTERNAL"
        create_backup "$BACKUP_EXTERNAL"
    else
        print_warning "External drive not found: $BACKUP_EXTERNAL"
        echo "Skipping external backup"
    fi

    # Backup to iCloud Drive
    print_step "Backing up to iCloud Drive..."
    mkdir -p "$BACKUP_ICLOUD"
    create_backup "$BACKUP_ICLOUD"
    print_success "iCloud backup complete (will sync automatically)"

    # Clean old backups
    print_step "Cleaning old backups (older than $BACKUP_RETENTION_DAYS days)..."
    clean_old_backups "$BACKUP_EXTERNAL"
    clean_old_backups "$BACKUP_ICLOUD"

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║             Backup Complete! 🎉                          ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Backup locations:"
    if [ -d "$BACKUP_EXTERNAL" ]; then
        echo "  • External: $BACKUP_EXTERNAL"
    fi
    echo "  • iCloud:   $BACKUP_ICLOUD"
    echo ""
}

clean_old_backups() {
    local backup_dir="$1"

    if [ ! -d "$backup_dir" ]; then
        return
    fi

    # Find and delete old backups
    find "$backup_dir" -name "lust-rentals-backup-*.tar.gz*" -type f -mtime +$BACKUP_RETENTION_DAYS -delete 2>/dev/null || true

    local deleted_count=$(find "$backup_dir" -name "lust-rentals-backup-*.tar.gz*" -type f -mtime +$BACKUP_RETENTION_DAYS | wc -l | xargs)
    if [ "$deleted_count" -gt 0 ]; then
        print_success "Removed $deleted_count old backup(s)"
    fi
}

list_backups() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║            Available Backups                             ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # List external backups
    if [ -d "$BACKUP_EXTERNAL" ]; then
        echo -e "${BLUE}External Drive:${NC}"
        find "$BACKUP_EXTERNAL" -name "lust-rentals-backup-*.tar.gz*" -type f -exec ls -lh {} \; 2>/dev/null | \
            awk '{print "  " $9 " (" $5 ")"}'  || echo "  No backups found"
        echo ""
    fi

    # List iCloud backups
    if [ -d "$BACKUP_ICLOUD" ]; then
        echo -e "${BLUE}iCloud Drive:${NC}"
        find "$BACKUP_ICLOUD" -name "lust-rentals-backup-*.tar.gz*" -type f -exec ls -lh {} \; 2>/dev/null | \
            awk '{print "  " $9 " (" $5 ")"}'  || echo "  No backups found"
        echo ""
    fi
}

setup_backup() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║            Backup Configuration Setup                    ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Check external drive
    echo -e "${BLUE}1. External Drive Backup${NC}"
    echo "   Current: $BACKUP_EXTERNAL"
    echo ""

    if [ ! -d "$(dirname "$BACKUP_EXTERNAL")" ]; then
        print_warning "External drive not found"
        echo ""
        echo "Connect an external drive and note its mount point, then update .env.production:"
        echo "  BACKUP_DIR=/Volumes/YourDriveName/lust-rentals-backups"
        echo ""
    else
        print_success "External drive accessible"
        mkdir -p "$BACKUP_EXTERNAL"
        echo ""
    fi

    # Check iCloud
    echo -e "${BLUE}2. iCloud Drive Backup${NC}"
    echo "   Current: $BACKUP_ICLOUD"
    echo ""

    if [ ! -d "$HOME/Library/Mobile Documents/com~apple~CloudDocs" ]; then
        print_warning "iCloud Drive not enabled"
        echo ""
        echo "To enable iCloud Drive:"
        echo "  1. Open System Preferences > Apple ID > iCloud"
        echo "  2. Enable 'iCloud Drive'"
        echo "  3. Run this setup again"
        echo ""
    else
        print_success "iCloud Drive enabled"
        mkdir -p "$BACKUP_ICLOUD"
        echo ""
    fi

    # Test backup
    echo -e "${BLUE}3. Test Backup${NC}"
    read -p "Would you like to create a test backup now? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        perform_backup
    fi

    echo ""
    echo -e "${GREEN}Setup complete!${NC}"
    echo ""
    echo "To create backups automatically, add to cron:"
    echo "  0 2 * * * $SCRIPT_DIR/mac-backup.sh"
    echo ""
}

restore_backup() {
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║            Restore from Backup                           ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""

    print_warning "This will replace your current data with backup data"
    echo ""

    # List available backups
    list_backups

    echo ""
    read -p "Enter backup filename to restore (or 'cancel'): " backup_file

    if [ "$backup_file" = "cancel" ]; then
        echo "Restore cancelled"
        exit 0
    fi

    # Find backup file
    BACKUP_PATH=""
    if [ -f "$BACKUP_EXTERNAL/$backup_file" ]; then
        BACKUP_PATH="$BACKUP_EXTERNAL/$backup_file"
    elif [ -f "$BACKUP_ICLOUD/$backup_file" ]; then
        BACKUP_PATH="$BACKUP_ICLOUD/$backup_file"
    else
        print_error "Backup file not found: $backup_file"
        exit 1
    fi

    # Confirm restoration
    echo ""
    echo "Restore from: $BACKUP_PATH"
    read -p "Are you sure? This cannot be undone! (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        echo "Restore cancelled"
        exit 0
    fi

    # Create safety backup first
    print_step "Creating safety backup of current data..."
    SAFETY_BACKUP="$PROJECT_DIR/data-before-restore-$(date +%Y%m%d_%H%M%S)"
    cp -r "$PROJECT_DIR/data" "$SAFETY_BACKUP"
    print_success "Safety backup created: $SAFETY_BACKUP"

    # Extract backup
    print_step "Extracting backup..."
    TMP_DIR=$(mktemp -d)

    if [[ "$BACKUP_PATH" == *.enc ]]; then
        # Encrypted backup
        if [ -z "$BACKUP_PASSWORD" ]; then
            read -sp "Enter backup password: " BACKUP_PASSWORD
            echo
        fi
        openssl enc -aes-256-cbc -d -in "$BACKUP_PATH" -out "$TMP_DIR/backup.tar.gz" -pass pass:"$BACKUP_PASSWORD"
        tar xzf "$TMP_DIR/backup.tar.gz" -C "$TMP_DIR"
    else
        tar xzf "$BACKUP_PATH" -C "$TMP_DIR"
    fi

    # Restore data
    print_step "Restoring data..."
    BACKUP_DIR=$(find "$TMP_DIR" -name "lust-rentals-backup-*" -type d | head -1)

    if [ -d "$BACKUP_DIR/processed" ]; then
        cp -r "$BACKUP_DIR/processed" "$PROJECT_DIR/data/"
        print_success "Database restored"
    fi

    if [ -d "$BACKUP_DIR/overrides" ]; then
        cp -r "$BACKUP_DIR/overrides" "$PROJECT_DIR/data/"
        print_success "Overrides restored"
    fi

    if [ -d "$BACKUP_DIR/raw" ]; then
        cp -r "$BACKUP_DIR/raw" "$PROJECT_DIR/data/"
        print_success "Raw data restored"
    fi

    if [ -d "$BACKUP_DIR/reports" ]; then
        cp -r "$BACKUP_DIR/reports" "$PROJECT_DIR/data/"
        print_success "Reports restored"
    fi

    # Cleanup
    rm -rf "$TMP_DIR"

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║             Restore Complete! 🎉                         ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Safety backup of previous data: $SAFETY_BACKUP"
    echo ""
    echo "Restart the application:"
    echo "  ./scripts/mac-service.sh restart"
    echo ""
}

show_help() {
    echo "Mac Mini Backup Script"
    echo ""
    echo "Usage: $0 {command}"
    echo ""
    echo "Commands:"
    echo "  (no args)   Create backup"
    echo "  setup       Configure backup locations"
    echo "  restore     Restore from backup"
    echo "  list        List available backups"
    echo "  help        Show this help"
    echo ""
}

###############################################################################
# Main
###############################################################################

case "${1:-backup}" in
    backup|"")
        perform_backup
        ;;
    setup)
        setup_backup
        ;;
    restore)
        restore_backup
        ;;
    list)
        list_backups
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac

exit 0
