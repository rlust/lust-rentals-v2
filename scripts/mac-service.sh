#!/usr/bin/env bash

###############################################################################
# Lust Rentals Tax Reporting - Service Management Script
#
# Manages the application service (start, stop, restart, status, logs)
#
# Usage:
#   ./mac-service.sh start      # Start the service
#   ./mac-service.sh stop       # Stop the service
#   ./mac-service.sh restart    # Restart the service
#   ./mac-service.sh status     # Check service status
#   ./mac-service.sh logs       # View logs
#   ./mac-service.sh update     # Pull latest changes and restart
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get project directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Compose file
COMPOSE_FILE="$PROJECT_DIR/docker-compose.production.yml"

# Helper functions
print_success() { echo -e "${GREEN}✓${NC} ${1}"; }
print_error() { echo -e "${RED}✗${NC} ${1}"; }
print_info() { echo -e "${BLUE}ℹ${NC} ${1}"; }
print_warning() { echo -e "${YELLOW}⚠${NC} ${1}"; }

###############################################################################
# Functions
###############################################################################

start_service() {
    print_info "Starting Lust Rentals Tax Reporting service..."

    cd "$PROJECT_DIR"

    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running"
        echo "Please start Docker Desktop and try again"
        exit 1
    fi

    # Start with docker-compose
    docker-compose -f "$COMPOSE_FILE" up -d

    print_success "Service started"
    echo ""
    print_info "Access your application at:"
    echo "  • http://localhost:8002"
    echo "  • http://$(hostname).local:8002"
    echo ""
}

stop_service() {
    print_info "Stopping Lust Rentals Tax Reporting service..."

    cd "$PROJECT_DIR"

    docker-compose -f "$COMPOSE_FILE" down

    print_success "Service stopped"
}

restart_service() {
    print_info "Restarting Lust Rentals Tax Reporting service..."

    stop_service
    sleep 2
    start_service

    print_success "Service restarted"
}

status_service() {
    cd "$PROJECT_DIR"

    echo -e "${BLUE}═══════════════════════════════════════════${NC}"
    echo -e "${BLUE}  Service Status${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════${NC}"
    echo ""

    # Check if container is running
    if docker ps --format '{{.Names}}' | grep -q "lust-rentals"; then
        print_success "Container is running"

        # Get container info
        echo ""
        docker ps --filter "name=lust-rentals" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

        # Check health endpoint
        echo ""
        if curl -s -f http://localhost:8002/health > /dev/null 2>&1; then
            print_success "Health check: OK"
        else
            print_warning "Health check: Failed"
        fi

        # Show resource usage
        echo ""
        echo "Resource Usage:"
        docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | grep lust-rentals || true

    else
        print_warning "Container is not running"
        echo ""
        echo "Start the service with: $0 start"
    fi

    echo ""
}

view_logs() {
    cd "$PROJECT_DIR"

    print_info "Showing service logs (press Ctrl+C to exit)..."
    echo ""

    docker-compose -f "$COMPOSE_FILE" logs -f --tail=100
}

update_service() {
    print_info "Updating Lust Rentals Tax Reporting to latest version..."

    cd "$PROJECT_DIR"

    # Pull latest code
    print_info "Pulling latest code from Git..."
    git pull

    # Rebuild Docker image
    print_info "Rebuilding Docker image..."
    docker-compose -f "$COMPOSE_FILE" build --no-cache

    # Restart service
    restart_service

    print_success "Update complete"
}

backup_service() {
    print_info "Creating backup..."

    cd "$PROJECT_DIR"

    if [ -f "$PROJECT_DIR/scripts/mac-backup.sh" ]; then
        "$PROJECT_DIR/scripts/mac-backup.sh"
    else
        print_warning "Backup script not found"
        echo "Run the setup script first: ./scripts/mac-setup.sh"
    fi
}

show_help() {
    echo "Lust Rentals Tax Reporting - Service Management"
    echo ""
    echo "Usage: $0 {command}"
    echo ""
    echo "Commands:"
    echo "  start      Start the service"
    echo "  stop       Stop the service"
    echo "  restart    Restart the service"
    echo "  status     Show service status"
    echo "  logs       View service logs (live tail)"
    echo "  update     Pull latest code and restart"
    echo "  backup     Create a backup"
    echo "  help       Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 status"
    echo "  $0 logs"
    echo ""
}

###############################################################################
# Main
###############################################################################

# Check if command provided
if [ $# -eq 0 ]; then
    print_error "No command specified"
    echo ""
    show_help
    exit 1
fi

# Execute command
case "$1" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        status_service
        ;;
    logs)
        view_logs
        ;;
    update)
        update_service
        ;;
    backup)
        backup_service
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac

exit 0
