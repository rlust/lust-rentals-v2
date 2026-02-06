#!/usr/bin/env bash

###############################################################################
# Lust Rentals Tax Reporting - Mac Mini Production Setup
#
# This script automates the complete setup of the application on your Mac Mini
# for 24/7 production use with auto-start on boot.
#
# What it does:
# 1. Checks prerequisites (Docker, Python)
# 2. Creates production configuration
# 3. Sets up LaunchDaemon for auto-start
# 4. Configures backups
# 5. Sets up monitoring
# 6. Starts the application
#
# Usage: ./scripts/mac-setup.sh
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Lust Rentals Tax Reporting - Mac Mini Setup            ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

###############################################################################
# Helper Functions
###############################################################################

print_step() {
    echo -e "\n${BLUE}▶${NC} ${1}"
}

print_success() {
    echo -e "${GREEN}✓${NC} ${1}"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} ${1}"
}

print_error() {
    echo -e "${RED}✗${NC} ${1}"
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

###############################################################################
# Step 1: Check Prerequisites
###############################################################################

print_step "Checking prerequisites..."

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    print_error "This script is designed for macOS only."
    exit 1
fi

print_success "Running on macOS"

# Check for Docker
if command_exists docker; then
    print_success "Docker is installed"
    docker --version
else
    print_warning "Docker is not installed"
    echo ""
    echo "Please install Docker Desktop for Mac:"
    echo "  1. Download from: https://www.docker.com/products/docker-desktop/"
    echo "  2. Install Docker Desktop.app"
    echo "  3. Open Docker Desktop to start the Docker daemon"
    echo "  4. Run this script again"
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_warning "Docker is not running"
    echo ""
    echo "Please start Docker Desktop:"
    echo "  1. Open Docker Desktop.app from Applications"
    echo "  2. Wait for Docker to start (check menu bar icon)"
    echo "  3. Run this script again"
    exit 1
fi

print_success "Docker is running"

# Check for Docker Compose
if command_exists docker-compose || docker compose version > /dev/null 2>&1; then
    print_success "Docker Compose is available"
else
    print_error "Docker Compose is not available"
    echo "Docker Compose should come with Docker Desktop."
    echo "Try reinstalling Docker Desktop."
    exit 1
fi

# Check for Python
if command_exists python3; then
    print_success "Python 3 is installed ($(python3 --version))"
else
    print_error "Python 3 is not installed"
    echo "Install Python 3 with Homebrew: brew install python3"
    exit 1
fi

###############################################################################
# Step 2: Create Production Configuration
###############################################################################

print_step "Setting up production configuration..."

# Check if .env.production exists
if [ -f "$PROJECT_DIR/.env.production" ]; then
    print_warning ".env.production already exists"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_success "Keeping existing .env.production"
    else
        cp "$PROJECT_DIR/.env.mac.example" "$PROJECT_DIR/.env.production"
        print_success "Created new .env.production from template"
    fi
else
    cp "$PROJECT_DIR/.env.mac.example" "$PROJECT_DIR/.env.production"
    print_success "Created .env.production from template"
fi

# Generate API secret if not set
if grep -q "CHANGE_ME_GENERATE_SECURE_KEY" "$PROJECT_DIR/.env.production"; then
    print_step "Generating secure API key..."
    API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

    # Use different sed syntax for macOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/API_SECRET_KEY=CHANGE_ME_GENERATE_SECURE_KEY/API_SECRET_KEY=${API_KEY}/" "$PROJECT_DIR/.env.production"
    else
        sed -i "s/API_SECRET_KEY=CHANGE_ME_GENERATE_SECURE_KEY/API_SECRET_KEY=${API_KEY}/" "$PROJECT_DIR/.env.production"
    fi

    print_success "Generated secure API key"
fi

# Generate backup password if not set
if grep -q "CHANGE_ME_BACKUP_PASSWORD" "$PROJECT_DIR/.env.production"; then
    print_step "Generating secure backup password..."
    BACKUP_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")

    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/BACKUP_PASSWORD=CHANGE_ME_BACKUP_PASSWORD/BACKUP_PASSWORD=${BACKUP_PASS}/" "$PROJECT_DIR/.env.production"
    else
        sed -i "s/BACKUP_PASSWORD=CHANGE_ME_BACKUP_PASSWORD/BACKUP_PASSWORD=${BACKUP_PASS}/" "$PROJECT_DIR/.env.production"
    fi

    print_success "Generated secure backup password"
    print_warning "Backup password saved in .env.production - keep this file secure!"
fi

###############################################################################
# Step 3: Create Data Directories
###############################################################################

print_step "Creating data directories..."

mkdir -p "$PROJECT_DIR/data/raw"
mkdir -p "$PROJECT_DIR/data/processed"
mkdir -p "$PROJECT_DIR/data/reports"
mkdir -p "$PROJECT_DIR/data/backups"
mkdir -p "$PROJECT_DIR/data/overrides"
mkdir -p "$PROJECT_DIR/logs"

print_success "Data directories created"

###############################################################################
# Step 4: Build Docker Image
###############################################################################

print_step "Building Docker image..."

cd "$PROJECT_DIR"
docker-compose -f docker-compose.production.yml build

print_success "Docker image built successfully"

###############################################################################
# Step 5: Create LaunchDaemon for Auto-Start
###############################################################################

print_step "Setting up auto-start on boot..."

# Create LaunchDaemon plist
PLIST_FILE="$PROJECT_DIR/com.lustrental.taxreporting.plist"

cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.lustrental.taxreporting</string>

    <key>ProgramArguments</key>
    <array>
        <string>${PROJECT_DIR}/scripts/mac-service.sh</string>
        <string>start</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>StandardOutPath</key>
    <string>${PROJECT_DIR}/logs/launchdaemon-stdout.log</string>

    <key>StandardErrorPath</key>
    <string>${PROJECT_DIR}/logs/launchdaemon-stderr.log</string>

    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/Applications/Docker.app/Contents/Resources/bin</string>
    </dict>
</dict>
</plist>
EOF

print_success "Created LaunchDaemon configuration"

# Note: We don't auto-install the LaunchDaemon as it requires sudo
print_warning "LaunchDaemon created but not installed (requires manual step)"
echo ""
echo "To enable auto-start on boot, run:"
echo "  sudo cp com.lustrental.taxreporting.plist /Library/LaunchDaemons/"
echo "  sudo launchctl load /Library/LaunchDaemons/com.lustrental.taxreporting.plist"
echo ""

###############################################################################
# Step 6: Test Configuration
###############################################################################

print_step "Testing configuration..."

# Test Docker Compose configuration
if docker-compose -f docker-compose.production.yml config > /dev/null 2>&1; then
    print_success "Docker Compose configuration is valid"
else
    print_error "Docker Compose configuration has errors"
    docker-compose -f docker-compose.production.yml config
    exit 1
fi

###############################################################################
# Step 7: Start the Application
###############################################################################

print_step "Starting the application..."

# Use the service script to start
"$PROJECT_DIR/scripts/mac-service.sh" start

###############################################################################
# Step 8: Verify Application is Running
###############################################################################

print_step "Verifying application is running..."

sleep 5  # Wait for application to start

# Check if container is running
if docker ps | grep -q "lust-rentals"; then
    print_success "Application container is running"
else
    print_error "Application container is not running"
    echo "Check logs with: docker-compose -f docker-compose.production.yml logs"
    exit 1
fi

# Check if health endpoint responds
if curl -s -f http://localhost:8002/health > /dev/null 2>&1; then
    print_success "Application health check passed"
else
    print_warning "Health check failed - application may still be starting"
fi

###############################################################################
# Final Steps & Instructions
###############################################################################

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║             Setup Complete! 🎉                           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${BLUE}📱 Access your application:${NC}"
echo "  Local:    http://localhost:8002"
echo "  Network:  http://$(hostname).local:8002"
echo ""

echo -e "${BLUE}🔐 Important Security Steps:${NC}"
echo "  1. Edit .env.production and review all settings"
echo "  2. Set up backup location (external drive or iCloud)"
echo "  3. Configure email alerts (optional)"
echo ""

echo -e "${BLUE}🚀 Next Steps:${NC}"
echo "  1. Install Tailscale for remote access:"
echo "     ${SCRIPT_DIR}/tailscale-setup.sh"
echo ""
echo "  2. Enable auto-start on boot (requires sudo):"
echo "     sudo cp com.lustrental.taxreporting.plist /Library/LaunchDaemons/"
echo "     sudo launchctl load /Library/LaunchDaemons/com.lustrental.taxreporting.plist"
echo ""
echo "  3. Set up automated backups:"
echo "     ${SCRIPT_DIR}/mac-backup.sh setup"
echo ""
echo "  4. Test the health monitor:"
echo "     ${SCRIPT_DIR}/health-monitor.sh"
echo ""

echo -e "${BLUE}📚 Documentation:${NC}"
echo "  Full guide: ${PROJECT_DIR}/MAC_MINI_DEPLOYMENT.md"
echo "  Remote access: ${PROJECT_DIR}/REMOTE_ACCESS_GUIDE.md"
echo "  Maintenance: ${PROJECT_DIR}/MAINTENANCE_GUIDE.md"
echo ""

echo -e "${BLUE}🔧 Service Management:${NC}"
echo "  Start:    ${SCRIPT_DIR}/mac-service.sh start"
echo "  Stop:     ${SCRIPT_DIR}/mac-service.sh stop"
echo "  Restart:  ${SCRIPT_DIR}/mac-service.sh restart"
echo "  Status:   ${SCRIPT_DIR}/mac-service.sh status"
echo "  Logs:     ${SCRIPT_DIR}/mac-service.sh logs"
echo ""

echo -e "${GREEN}✓ Your Lust Rentals Tax Reporting app is now running!${NC}"
echo ""
