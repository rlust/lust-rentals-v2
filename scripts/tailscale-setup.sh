#!/usr/bin/env bash

###############################################################################
# Tailscale VPN Setup for Mac Mini
#
# Tailscale provides secure remote access to your Mac Mini from anywhere.
# It creates a private VPN network that's easier than port forwarding.
#
# What you get:
# - Access your app from anywhere: http://mac-mini.tail12345.ts.net:8002
# - No port forwarding or dynamic DNS needed
# - Encrypted connections
# - Works behind any firewall/NAT
# - Free for personal use
#
# Usage: ./tailscale-setup.sh
###############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() { echo -e "\n${BLUE}▶${NC} ${1}"; }
print_success() { echo -e "${GREEN}✓${NC} ${1}"; }
print_warning() { echo -e "${YELLOW}⚠${NC} ${1}"; }
print_error() { echo -e "${RED}✗${NC} ${1}"; }

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          Tailscale VPN Setup for Remote Access          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

###############################################################################
# Check if Tailscale is already installed
###############################################################################

if command -v tailscale >/dev/null 2>&1; then
    print_success "Tailscale is already installed"

    # Check if Tailscale is running
    if tailscale status > /dev/null 2>&1; then
        print_success "Tailscale is running"
        echo ""
        echo "Your Tailscale status:"
        tailscale status
        echo ""
        echo -e "${GREEN}You're all set!${NC}"
        echo ""
        echo "Access your app from any device on your Tailscale network:"
        HOSTNAME=$(tailscale status --json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['Self']['DNSName'].rstrip('.'))" 2>/dev/null || echo "your-mac-hostname")
        echo "  http://${HOSTNAME}:8002"
        echo ""
        exit 0
    else
        print_warning "Tailscale is installed but not running"
        echo "Starting Tailscale..."
        sudo tailscale up
        exit 0
    fi
fi

###############################################################################
# Install Tailscale
###############################################################################

print_step "Installing Tailscale..."

# Check if Homebrew is installed
if ! command -v brew >/dev/null 2>&1; then
    print_warning "Homebrew is not installed"
    echo ""
    echo "Tailscale can be installed via:"
    echo "  1. Download from https://tailscale.com/download/mac"
    echo "  2. Or install Homebrew first: https://brew.sh"
    echo ""
    read -p "Download Tailscale from website? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$  ]] || [[ -z $REPLY ]]; then
        open "https://tailscale.com/download/mac"
        echo ""
        print_info "Please:"
        echo "  1. Download and install Tailscale from the website"
        echo "  2. Run this script again after installation"
        echo ""
    fi
    exit 0
fi

# Install via Homebrew
print_info "Installing Tailscale via Homebrew..."
brew install tailscale

print_success "Tailscale installed"

###############################################################################
# Start Tailscale
###############################################################################

print_step "Starting Tailscale..."

# Start Tailscale daemon
sudo tailscale up

print_success "Tailscale is running"

###############################################################################
# Get connection info
###############################################################################

print_step "Getting your Tailscale information..."

# Wait a moment for Tailscale to fully start
sleep 2

# Get Tailscale hostname
TAILSCALE_HOSTNAME=$(tailscale status --json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['Self']['DNSName'].rstrip('.'))" 2>/dev/null || echo "")

if [ -z "$TAILSCALE_HOSTNAME" ]; then
    print_warning "Could not automatically detect Tailscale hostname"
    echo ""
    echo "Run 'tailscale status' to see your hostname"
    TAILSCALE_HOSTNAME="your-mac-hostname.tail12345.ts.net"
else
    print_success "Your Tailscale hostname: $TAILSCALE_HOSTNAME"
fi

###############################################################################
# Update .env.production with Tailscale hostname
###############################################################################

print_step "Updating configuration..."

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
ENV_FILE="$PROJECT_DIR/.env.production"

if [ -f "$ENV_FILE" ]; then
    # Update TAILSCALE_HOSTNAME in .env.production
    if grep -q "TAILSCALE_HOSTNAME=" "$ENV_FILE"; then
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|TAILSCALE_HOSTNAME=.*|TAILSCALE_HOSTNAME=${TAILSCALE_HOSTNAME}|" "$ENV_FILE"
        else
            sed -i "s|TAILSCALE_HOSTNAME=.*|TAILSCALE_HOSTNAME=${TAILSCALE_HOSTNAME}|" "$ENV_FILE"
        fi
        print_success "Updated .env.production with Tailscale hostname"
    fi

    # Update ALLOWED_ORIGINS
    if grep -q "ALLOWED_ORIGINS=" "$ENV_FILE"; then
        CURRENT_ORIGINS=$(grep "ALLOWED_ORIGINS=" "$ENV_FILE" | cut -d'=' -f2)
        NEW_ORIGIN="http://${TAILSCALE_HOSTNAME}:8002"

        if [[ ! "$CURRENT_ORIGINS" =~ "$NEW_ORIGIN" ]]; then
            NEW_ORIGINS="${CURRENT_ORIGINS},${NEW_ORIGIN}"
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' "s|ALLOWED_ORIGINS=.*|ALLOWED_ORIGINS=${NEW_ORIGINS}|" "$ENV_FILE"
            else
                sed -i "s|ALLOWED_ORIGINS=.*|ALLOWED_ORIGINS=${NEW_ORIGINS}|" "$ENV_FILE"
            fi
            print_success "Added Tailscale URL to allowed origins"
        fi
    fi
fi

###############################################################################
# Test access
###############################################################################

print_step "Testing local access..."

if curl -s -f http://localhost:8002/health > /dev/null 2>&1; then
    print_success "Local access working"
else
    print_warning "Application is not running locally"
    echo "Start it with: ./scripts/mac-service.sh start"
fi

###############################################################################
# Final instructions
###############################################################################

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║             Tailscale Setup Complete! 🎉                 ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${BLUE}📱 Access your app from anywhere:${NC}"
echo "  http://${TAILSCALE_HOSTNAME}:8002"
echo ""

echo -e "${BLUE}🔐 Install Tailscale on other devices:${NC}"
echo "  • iPhone/iPad: Install from App Store"
echo "  • Android: Install from Play Store"
echo "  • Windows/Mac/Linux: Download from https://tailscale.com/download"
echo ""
echo "  Login with the same account on all devices to access your Mac Mini"
echo ""

echo -e "${BLUE}💡 Tailscale Tips:${NC}"
echo "  • Check status: tailscale status"
echo "  • See IP address: tailscale ip"
echo "  • Restart: sudo tailscale down && sudo tailscale up"
echo "  • Enable exit node (route all traffic): sudo tailscale up --advertise-exit-node"
echo ""

echo -e "${BLUE}📚 Resources:${NC}"
echo "  • Tailscale Admin: https://login.tailscale.com/admin/machines"
echo "  • Documentation: https://tailscale.com/kb/"
echo "  • Support: https://tailscale.com/contact/support/"
echo ""

echo -e "${BLUE}🔧 Next Steps:${NC}"
echo "  1. Install Tailscale on your phone/laptop"
echo "  2. Login with the same account"
echo "  3. Access http://${TAILSCALE_HOSTNAME}:8002 from any device"
echo "  4. Bookmark the URL for easy access"
echo ""

echo -e "${GREEN}✓ You can now access your Tax Reporting app from anywhere!${NC}"
echo ""
