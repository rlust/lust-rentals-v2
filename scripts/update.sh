#!/bin/bash

# Lust Rentals Tax Reporting - Update Script
# Pulls latest changes from GitHub repository

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${PROJECT_DIR}/logs/update.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create logs directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

log_info "Starting update process..."

# Change to project directory
cd "$PROJECT_DIR"

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    log_error "Not a git repository. Cannot update."
    exit 1
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    log_warning "You have uncommitted changes."
    echo -e "${YELLOW}Uncommitted changes detected:${NC}"
    git status --short
    read -p "Do you want to stash these changes and continue? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Stashing local changes..."
        git stash push -m "Auto-stash before update $(date +'%Y-%m-%d %H:%M:%S')"
        log_success "Changes stashed successfully"
    else
        log_error "Update cancelled by user"
        exit 1
    fi
fi

# Get current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
log_info "Current branch: $CURRENT_BRANCH"

# Get current commit hash
CURRENT_COMMIT=$(git rev-parse HEAD)
log_info "Current commit: $CURRENT_COMMIT"

# Fetch latest changes
log_info "Fetching latest changes from remote..."
if git fetch origin; then
    log_success "Fetch completed successfully"
else
    log_error "Failed to fetch from remote"
    exit 1
fi

# Check if there are updates available
UPDATES_AVAILABLE=$(git rev-list HEAD..origin/$CURRENT_BRANCH --count)

if [ "$UPDATES_AVAILABLE" -eq 0 ]; then
    log_info "Already up to date. No updates available."
    exit 0
fi

log_info "$UPDATES_AVAILABLE update(s) available"

# Show commits that will be pulled
echo -e "\n${BLUE}Changes to be applied:${NC}"
git log --oneline HEAD..origin/$CURRENT_BRANCH

# Pull latest changes
log_info "Pulling latest changes..."
if git pull origin "$CURRENT_BRANCH"; then
    NEW_COMMIT=$(git rev-parse HEAD)
    log_success "Updated successfully from $CURRENT_COMMIT to $NEW_COMMIT"
else
    log_error "Failed to pull changes"
    exit 1
fi

# Check if requirements.txt was updated
if git diff --name-only "$CURRENT_COMMIT" HEAD | grep -q "requirements.txt"; then
    log_warning "requirements.txt was updated. You may need to reinstall dependencies."
    echo -e "${YELLOW}To update dependencies, run:${NC}"
    echo "  pip install -r requirements.txt"
    echo "  OR restart the Docker container if running in Docker"
fi

# Check if there are stashed changes
STASH_COUNT=$(git stash list | wc -l)
if [ "$STASH_COUNT" -gt 0 ]; then
    log_warning "You have $STASH_COUNT stashed change(s)."
    echo -e "${YELLOW}To restore your changes, run:${NC}"
    echo "  git stash pop"
fi

log_success "Update completed successfully!"
echo -e "\n${GREEN}✓${NC} Application updated to latest version"
echo -e "${BLUE}ℹ${NC} Server restart required for changes to take effect"
echo -e "${YELLOW}→${NC} Run: ./scripts/restart-server.sh"

exit 0
