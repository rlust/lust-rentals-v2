#!/bin/bash

# Lust Rentals Tax Reporting - Mac Installation Script
# Comprehensive installation script for macOS

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
PYTHON_MIN_VERSION="3.8"
REPO_URL="https://github.com/rlust/lust-rentals-tax-reporting.git"
APP_NAME="Lust Rentals Tax Reporting"

# Determine script and project directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.git/config" ] || [ -d "$SCRIPT_DIR/.git" ]; then
    PROJECT_DIR="$SCRIPT_DIR"
    IN_REPO=true
else
    PROJECT_DIR="$HOME/lust-rentals-tax-reporting"
    IN_REPO=false
fi

# ============================================================================
# Logging Functions
# ============================================================================

log_header() {
    echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}\n"
}

log_step() {
    echo -e "${BLUE}▶${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_info() {
    echo -e "${MAGENTA}ℹ${NC} $1"
}

# ============================================================================
# Utility Functions
# ============================================================================

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

version_ge() {
    # Compare versions: returns 0 if $1 >= $2
    printf '%s\n%s' "$2" "$1" | sort -V -C
}

get_python_version() {
    local python_cmd="$1"
    "$python_cmd" --version 2>&1 | awk '{print $2}'
}

is_python_version_ok() {
    local python_cmd="$1"
    local version
    version=$(get_python_version "$python_cmd")
    version_ge "$version" "$PYTHON_MIN_VERSION"
}

wait_for_enter() {
    echo -e "\n${CYAN}Press ENTER to continue...${NC}"
    read -r
}

# ============================================================================
# Installation Functions
# ============================================================================

check_macos() {
    log_step "Checking operating system..."
    if [[ "$OSTYPE" != "darwin"* ]]; then
        log_error "This script is designed for macOS only."
        log_info "Detected OS: $OSTYPE"
        exit 1
    fi
    log_success "Running on macOS"
}

install_homebrew() {
    log_step "Checking for Homebrew..."
    if command_exists brew; then
        log_success "Homebrew is already installed"
        return 0
    fi

    log_warning "Homebrew is not installed"
    echo -e "\nHomebrew is the recommended package manager for macOS."
    echo -e "It will be used to install Python and other dependencies.\n"
    read -p "Would you like to install Homebrew now? (y/n) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_step "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

        # Add Homebrew to PATH for Apple Silicon Macs
        if [[ $(uname -m) == 'arm64' ]]; then
            echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile"
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi

        log_success "Homebrew installed successfully"
    else
        log_error "Installation cancelled. Homebrew is required for automatic installation."
        log_info "Please install Homebrew manually from https://brew.sh/"
        exit 1
    fi
}

check_python() {
    log_step "Checking for Python installation..."

    local python_cmd=""

    # Check various Python commands
    for cmd in python3 python python3.11 python3.10 python3.9 python3.8; do
        if command_exists "$cmd"; then
            if is_python_version_ok "$cmd"; then
                python_cmd="$cmd"
                break
            fi
        fi
    done

    if [ -n "$python_cmd" ]; then
        local version
        version=$(get_python_version "$python_cmd")
        log_success "Found compatible Python: $python_cmd (version $version)"
        PYTHON_CMD="$python_cmd"
        return 0
    fi

    log_warning "Compatible Python (>= $PYTHON_MIN_VERSION) not found"
    return 1
}

install_python() {
    if check_python; then
        return 0
    fi

    echo -e "\n${YELLOW}Python $PYTHON_MIN_VERSION or higher is required.${NC}"
    read -p "Would you like to install Python via Homebrew? (y/n) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_step "Installing Python via Homebrew..."
        brew install python3

        # Verify installation
        if check_python; then
            log_success "Python installed successfully"
        else
            log_error "Python installation failed"
            exit 1
        fi
    else
        log_error "Installation cancelled. Python is required."
        log_info "Please install Python manually from https://www.python.org/downloads/"
        exit 1
    fi
}

check_git() {
    log_step "Checking for Git installation..."
    if command_exists git; then
        log_success "Git is installed"
        return 0
    fi

    log_warning "Git is not installed"
    echo -e "\n${YELLOW}Git is required to clone the repository.${NC}"
    read -p "Would you like to install Git via Homebrew? (y/n) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_step "Installing Git via Homebrew..."
        brew install git
        log_success "Git installed successfully"
    else
        log_error "Installation cancelled. Git is required."
        log_info "Git can also be installed via Xcode Command Line Tools:"
        log_info "  xcode-select --install"
        exit 1
    fi
}

clone_repository() {
    if [ "$IN_REPO" = true ]; then
        log_info "Already in repository directory: $PROJECT_DIR"
        return 0
    fi

    log_step "Checking for existing repository..."

    if [ -d "$PROJECT_DIR" ]; then
        log_warning "Directory already exists: $PROJECT_DIR"
        read -p "Would you like to use the existing directory? (y/n) " -n 1 -r
        echo

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cd "$PROJECT_DIR"
            if [ -d ".git" ]; then
                log_info "Using existing repository"
                return 0
            else
                log_error "Directory exists but is not a git repository"
                exit 1
            fi
        else
            log_error "Installation cancelled"
            exit 1
        fi
    fi

    log_step "Cloning repository from GitHub..."
    log_info "Repository: $REPO_URL"
    log_info "Target directory: $PROJECT_DIR"

    git clone "$REPO_URL" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
    log_success "Repository cloned successfully"
}

create_virtual_environment() {
    log_step "Setting up Python virtual environment..."

    local venv_dir="$PROJECT_DIR/venv"

    if [ -d "$venv_dir" ]; then
        log_info "Virtual environment already exists"
        read -p "Would you like to recreate it? (y/n) " -n 1 -r
        echo

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_step "Removing existing virtual environment..."
            rm -rf "$venv_dir"
        else
            log_info "Using existing virtual environment"
            return 0
        fi
    fi

    log_step "Creating virtual environment..."
    "$PYTHON_CMD" -m venv "$venv_dir"
    log_success "Virtual environment created"
}

install_dependencies() {
    log_step "Installing Python dependencies..."

    local venv_dir="$PROJECT_DIR/venv"
    local pip_cmd="$venv_dir/bin/pip"

    if [ ! -f "$pip_cmd" ]; then
        log_error "Virtual environment not found. Please run the installation again."
        exit 1
    fi

    log_info "Upgrading pip..."
    "$pip_cmd" install --upgrade pip

    log_info "Installing requirements..."
    "$pip_cmd" install -r "$PROJECT_DIR/requirements.txt"

    log_success "Dependencies installed successfully"
}

setup_directories() {
    log_step "Setting up data directories..."

    local data_dir="$PROJECT_DIR/data"

    mkdir -p "$data_dir/raw"
    mkdir -p "$data_dir/processed"
    mkdir -p "$data_dir/overrides"
    mkdir -p "$data_dir/reports"
    mkdir -p "$PROJECT_DIR/logs"

    log_success "Directory structure created"
    log_info "Data directory: $data_dir"
}

setup_environment() {
    log_step "Setting up environment configuration..."

    local env_file="$PROJECT_DIR/.env"
    local env_example="$PROJECT_DIR/.env.example"

    if [ -f "$env_file" ]; then
        log_info "Environment file already exists: $env_file"
        return 0
    fi

    # Create .env file
    cat > "$env_file" << 'EOF'
# Lust Rentals Tax Reporting - Environment Configuration

# Data directory (defaults to ./data)
LUST_DATA_DIR=./data

# Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LUST_LOG_LEVEL=INFO

# Server configuration
HOST=0.0.0.0
PORT=8000

# Optional: Set to production for deployment
# ENVIRONMENT=development
EOF

    log_success "Environment file created: $env_file"
    log_info "You can customize settings by editing this file"
}

make_scripts_executable() {
    log_step "Making scripts executable..."

    if [ -d "$PROJECT_DIR/scripts" ]; then
        chmod +x "$PROJECT_DIR"/scripts/*.sh
        log_success "Scripts are now executable"
    fi

    # Make this install script executable
    chmod +x "$PROJECT_DIR/install-mac.sh" 2>/dev/null || true
}

verify_installation() {
    log_step "Verifying installation..."

    local venv_python="$PROJECT_DIR/venv/bin/python"

    if [ ! -f "$venv_python" ]; then
        log_error "Python executable not found in virtual environment"
        return 1
    fi

    # Check if we can import key modules
    if ! "$venv_python" -c "import fastapi, uvicorn, pandas" 2>/dev/null; then
        log_error "Failed to import required Python modules"
        return 1
    fi

    log_success "Installation verified successfully"
    return 0
}

# ============================================================================
# Main Installation Flow
# ============================================================================

show_banner() {
    clear
    echo -e "${CYAN}"
    cat << 'EOF'
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║        LUST RENTALS TAX REPORTING - MAC INSTALLER            ║
║                                                               ║
║          Automated Installation for macOS Systems            ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}\n"
}

show_welcome() {
    echo -e "Welcome to the ${GREEN}$APP_NAME${NC} installer!\n"
    echo -e "This script will:"
    echo -e "  ${BLUE}1.${NC} Install Homebrew (if needed)"
    echo -e "  ${BLUE}2.${NC} Install Python 3.8+ (if needed)"
    echo -e "  ${BLUE}3.${NC} Install Git (if needed)"
    echo -e "  ${BLUE}4.${NC} Clone the repository (if needed)"
    echo -e "  ${BLUE}5.${NC} Create a Python virtual environment"
    echo -e "  ${BLUE}6.${NC} Install all Python dependencies"
    echo -e "  ${BLUE}7.${NC} Set up data directories and configuration"
    echo -e "  ${BLUE}8.${NC} Verify the installation\n"

    read -p "Press ENTER to begin installation or Ctrl+C to cancel..."
    echo
}

show_completion() {
    log_header "Installation Complete!"

    echo -e "${GREEN}✓${NC} ${APP_NAME} has been installed successfully!\n"

    echo -e "${CYAN}Next Steps:${NC}\n"

    echo -e "${BLUE}1.${NC} Activate the virtual environment:"
    echo -e "   ${YELLOW}cd $PROJECT_DIR${NC}"
    echo -e "   ${YELLOW}source venv/bin/activate${NC}\n"

    echo -e "${BLUE}2.${NC} Start the application server:"
    echo -e "   ${YELLOW}python -m uvicorn src.api.server:app --reload${NC}\n"

    echo -e "${BLUE}3.${NC} Open the web interface:"
    echo -e "   ${YELLOW}http://localhost:8000/review${NC}\n"

    echo -e "${CYAN}Quick Commands:${NC}\n"
    echo -e "  Process bank data:    ${YELLOW}python -m src.cli.app process-bank --year 2025${NC}"
    echo -e "  Generate reports:     ${YELLOW}python -m src.cli.app generate-reports --year 2025${NC}"
    echo -e "  Run tests:            ${YELLOW}pytest${NC}"
    echo -e "  Update application:   ${YELLOW}./scripts/update.sh${NC}\n"

    echo -e "${CYAN}Documentation:${NC}\n"
    echo -e "  README:               ${YELLOW}$PROJECT_DIR/README.md${NC}"
    echo -e "  Mac Setup Guide:      ${YELLOW}$PROJECT_DIR/docs/MAC_INSTALLATION_GUIDE.md${NC}\n"

    echo -e "${GREEN}Happy tax reporting! 📊${NC}\n"
}

handle_error() {
    log_error "Installation failed at step: $1"
    log_info "Please check the error messages above and try again."
    log_info "For help, see: $PROJECT_DIR/README.md"
    exit 1
}

main() {
    show_banner
    show_welcome

    log_header "System Requirements Check"
    check_macos || handle_error "OS Check"
    install_homebrew || handle_error "Homebrew Installation"
    check_git || handle_error "Git Check"
    install_python || handle_error "Python Installation"

    log_header "Repository Setup"
    clone_repository || handle_error "Repository Clone"

    # Ensure we're in the project directory
    cd "$PROJECT_DIR"

    log_header "Python Environment Setup"
    create_virtual_environment || handle_error "Virtual Environment Creation"
    install_dependencies || handle_error "Dependency Installation"

    log_header "Application Configuration"
    setup_directories || handle_error "Directory Setup"
    setup_environment || handle_error "Environment Setup"
    make_scripts_executable || handle_error "Script Permissions"

    log_header "Installation Verification"
    verify_installation || handle_error "Installation Verification"

    show_completion
}

# ============================================================================
# Script Entry Point
# ============================================================================

# Trap errors
trap 'handle_error "Unexpected error"' ERR

# Run main installation
main

exit 0
