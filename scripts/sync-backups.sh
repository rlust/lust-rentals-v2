#!/bin/bash

# Configuration
APP_DIR="/Users/randylust/.openclaw/workspace/lust-rentals-v2"
BACKUP_SOURCE="$APP_DIR/data/backups"
ICLOUD_DEST="/Users/randylust/Library/Mobile Documents/com~apple~CloudDocs/taxes/lust_llc_backup"
LOG_FILE="$APP_DIR/logs/backup_sync.log"

# Create destination if it doesn't exist (just in case)
mkdir -p "$ICLOUD_DEST"
mkdir -p "$(dirname "$LOG_FILE")"

echo "[$(date)] Starting iCloud backup sync..." >> "$LOG_FILE"

# 1. Trigger a new backup via API (optional, ensures fresh data)
# We use curl to hit the backup endpoint. Assuming app is running on localhost:8000
# If app is down, we just sync what we have.
curl -s -X POST "http://localhost:8000/backup/create?include_reports=true" > /dev/null
if [ $? -eq 0 ]; then
    echo "[$(date)] Triggered fresh backup via API." >> "$LOG_FILE"
else
    echo "[$(date)] Warning: Could not trigger API backup (App might be down). Syncing existing files." >> "$LOG_FILE"
fi

# 2. Sync files
# We use rsync to copy new files. 
# --ignore-existing to avoid re-copying huge files
# --remove-source-files? NO, keep local copies for now.
echo "[$(date)] Copying backups to iCloud..." >> "$LOG_FILE"
cp -n "$BACKUP_SOURCE"/*.zip "$ICLOUD_DEST/" 2>> "$LOG_FILE"

# 3. Prune old backups in iCloud (Keep last 30 days)
# Find files older than 30 days in destination and delete them
find "$ICLOUD_DEST" -name "*.zip" -type f -mtime +30 -delete
echo "[$(date)] Pruned backups older than 30 days in iCloud." >> "$LOG_FILE"

echo "[$(date)] Backup sync complete." >> "$LOG_FILE"
