#!/usr/bin/env bash

###############################################################################
# Health Monitor for Lust Rentals Tax Reporting
#
# Monitors application health and sends alerts on failures
# Can be run manually or via cron for continuous monitoring
#
# Usage:
#   ./health-monitor.sh        # Check health once
#   ./health-monitor.sh loop   # Monitor continuously (every 15 min)
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
PROJECT_DIR="$(cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd)"
HEALTH_URL="http://localhost:8002/health"
CHECK_INTERVAL=900  # 15 minutes

# Load environment
if [ -f "$PROJECT_DIR/.env.production" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env.production" | sed 's/\r$//' | xargs)
fi

print_success() { echo -e "${GREEN}✓${NC} ${1}"; }
print_warning() { echo -e "${YELLOW}⚠${NC} ${1}"; }
print_error() { echo -e "${RED}✗${NC} ${1}"; }
print_info() { echo -e "${BLUE}ℹ${NC} ${1}"; }

check_health() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$timestamp] Checking application health..."

    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "lust-rentals"; then
        print_error "Container is not running"
        send_alert "Container Down" "The Lust Rentals application container is not running"
        return 1
    fi

    # Check health endpoint
    if curl -s -f "$HEALTH_URL" > /dev/null 2>&1; then
        print_success "Health check passed"
        return 0
    else
        print_error "Health endpoint not responding"
        send_alert "Health Check Failed" "The application health endpoint is not responding"
        return 1
    fi
}

send_alert() {
    local subject="$1"
    local message="$2"

    # Log alert
    echo "[$timestamp] ALERT: $subject - $message" >> "$PROJECT_DIR/logs/health-alerts.log"

    # Send email if configured
    if [ -n "$SMTP_HOST" ] && [ -n "$ALERT_EMAIL" ]; then
        echo "$message" | mail -s "Lust Rentals Alert: $subject" "$ALERT_EMAIL" 2>/dev/null || true
    fi

    # macOS notification
    osascript -e "display notification \"$message\" with title \"Lust Rentals Alert\" subtitle \"$subject\"" 2>/dev/null || true
}

monitor_loop() {
    print_info "Starting continuous health monitoring (every 15 minutes)"
    echo "Press Ctrl+C to stop"
    echo ""

    while true; do
        check_health
        sleep $CHECK_INTERVAL
    done
}

case "${1:-once}" in
    once|"")
        check_health
        ;;
    loop)
        monitor_loop
        ;;
    *)
        echo "Usage: $0 {once|loop}"
        exit 1
        ;;
esac
