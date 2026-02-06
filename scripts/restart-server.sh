#!/bin/bash

# Lust Rentals Tax Reporting - Server Restart Script
# Restarts the application server (supports both local and Docker deployments)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="${PROJECT_DIR}/logs/restart.log"
PID_FILE="${PROJECT_DIR}/.server.pid"

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

# Function to check if running in Docker
is_docker() {
    if [ -f /.dockerenv ]; then
        return 0
    fi

    if grep -q docker /proc/1/cgroup 2>/dev/null; then
        return 0
    fi

    return 1
}

# Function to detect deployment type
detect_deployment() {
    if is_docker; then
        echo "docker-internal"
    elif docker ps --format '{{.Names}}' 2>/dev/null | grep -q "lust-rentals"; then
        echo "docker-compose"
    elif [ -f "$PID_FILE" ]; then
        echo "local-managed"
    elif pgrep -f "uvicorn.*src.api.server:app" > /dev/null; then
        echo "local-unmanaged"
    else
        echo "unknown"
    fi
}

# Function to restart Docker Compose deployment
restart_docker_compose() {
    log_info "Detected Docker Compose deployment"

    cd "$PROJECT_DIR"

    # Check which compose file to use
    if [ -f "docker-compose.production.yml" ]; then
        COMPOSE_FILE="docker-compose.production.yml"
    elif [ -f "docker-compose.yml" ]; then
        COMPOSE_FILE="docker-compose.yml"
    else
        log_error "No docker-compose file found"
        return 1
    fi

    log_info "Using $COMPOSE_FILE"

    # Restart the application container
    log_info "Restarting containers..."
    if docker-compose -f "$COMPOSE_FILE" restart app; then
        log_success "Containers restarted successfully"

        # Wait for health check
        log_info "Waiting for application to be healthy..."
        sleep 5

        if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
            log_success "Application is healthy and responding"
            return 0
        else
            log_warning "Application may still be starting up"
            echo -e "${YELLOW}Check logs with: docker-compose -f $COMPOSE_FILE logs -f app${NC}"
            return 0
        fi
    else
        log_error "Failed to restart containers"
        return 1
    fi
}

# Function to restart local managed server
restart_local_managed() {
    log_info "Detected locally managed server"

    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        log_info "Found PID file with PID: $OLD_PID"

        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            log_info "Stopping server (PID: $OLD_PID)..."
            kill "$OLD_PID"

            # Wait for process to stop
            for i in {1..10}; do
                if ! ps -p "$OLD_PID" > /dev/null 2>&1; then
                    log_success "Server stopped"
                    break
                fi
                sleep 1
            done

            # Force kill if still running
            if ps -p "$OLD_PID" > /dev/null 2>&1; then
                log_warning "Force killing server..."
                kill -9 "$OLD_PID"
            fi
        else
            log_warning "PID file exists but process is not running"
        fi

        rm -f "$PID_FILE"
    fi

    # Start new server
    start_local_server
}

# Function to restart local unmanaged server
restart_local_unmanaged() {
    log_info "Detected locally running server (not managed by this script)"

    # Find all uvicorn processes
    PIDS=$(pgrep -f "uvicorn.*src.api.server:app" || true)

    if [ -z "$PIDS" ]; then
        log_warning "No running server found"
        read -p "Would you like to start the server? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            start_local_server
            return $?
        else
            return 1
        fi
    fi

    log_warning "Found server process(es): $PIDS"
    echo -e "${YELLOW}This server was not started by the restart script.${NC}"
    read -p "Kill existing process(es) and restart? (y/n) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Stopping existing server process(es)..."
        echo "$PIDS" | xargs kill

        # Wait for processes to stop
        sleep 2

        # Force kill if needed
        REMAINING=$(pgrep -f "uvicorn.*src.api.server:app" || true)
        if [ -n "$REMAINING" ]; then
            log_warning "Force killing remaining processes..."
            echo "$REMAINING" | xargs kill -9
        fi

        log_success "Server stopped"

        # Start new server
        start_local_server
    else
        log_info "Restart cancelled by user"
        return 1
    fi
}

# Function to start local server
start_local_server() {
    cd "$PROJECT_DIR"

    log_info "Starting server..."

    # Check if virtual environment exists
    if [ -d "venv" ]; then
        log_info "Activating virtual environment..."
        source venv/bin/activate
    fi

    # Check if dependencies are installed
    if ! python -c "import fastapi" 2>/dev/null; then
        log_warning "Dependencies not installed. Installing..."
        pip install -r requirements.txt
    fi

    # Start server in background
    nohup python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8000 > "$LOG_FILE" 2>&1 &
    NEW_PID=$!

    echo "$NEW_PID" > "$PID_FILE"
    log_info "Server started with PID: $NEW_PID"

    # Wait for server to be ready
    log_info "Waiting for server to be ready..."
    for i in {1..30}; do
        if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
            log_success "Server is healthy and responding"
            echo -e "\n${GREEN}✓${NC} Server restarted successfully"
            echo -e "${BLUE}ℹ${NC} Server running at http://localhost:8000"
            echo -e "${BLUE}ℹ${NC} Dashboard at http://localhost:8000/review"
            echo -e "${BLUE}ℹ${NC} Logs: $LOG_FILE"
            return 0
        fi
        sleep 1
    done

    log_error "Server did not become healthy within 30 seconds"
    echo -e "${RED}Check logs at: $LOG_FILE${NC}"
    return 1
}

# Function to restart Docker internal (when running inside container)
restart_docker_internal() {
    log_error "Cannot restart from inside Docker container"
    echo -e "${RED}This script is running inside a Docker container.${NC}"
    echo -e "${YELLOW}To restart the container, run from the host:${NC}"
    echo "  docker restart <container_name>"
    echo "  OR"
    echo "  docker-compose -f docker-compose.production.yml restart app"
    return 1
}

# Main execution
log_info "Starting server restart process..."

DEPLOYMENT_TYPE=$(detect_deployment)
log_info "Detected deployment type: $DEPLOYMENT_TYPE"

case $DEPLOYMENT_TYPE in
    docker-internal)
        restart_docker_internal
        ;;
    docker-compose)
        restart_docker_compose
        ;;
    local-managed)
        restart_local_managed
        ;;
    local-unmanaged)
        restart_local_unmanaged
        ;;
    unknown)
        log_warning "Could not detect deployment type"
        echo -e "${YELLOW}No running server detected.${NC}"
        read -p "Would you like to start the server? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            start_local_server
        else
            log_info "Restart cancelled"
            exit 1
        fi
        ;;
esac

exit $?
