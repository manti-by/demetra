#!/bin/bash
# Setup script for Demetra FastAPI systemd service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="demetra-api"
SERVICE_FILE="demetra-api.service"
PROJECT_DIR="/home/manti/www/demetra"
SYSTEMD_DIR="/etc/systemd/system"
USER="manti"

echo -e "${BLUE}🚀 Demetra FastAPI Systemd Service Setup${NC}\n"

# Function to print status messages
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if running as root for system service installation
check_permissions() {
    if [[ $EUID -eq 0 ]]; then
        print_warning "Running as root. This is needed for system service installation."
    else
        print_error "This script needs to be run with sudo for system service installation."
        echo "Run: sudo $0"
        exit 1
    fi
}

# Validate project directory and files
validate_project() {
    print_info "Validating project setup..."

    if [[ ! -d "$PROJECT_DIR" ]]; then
        print_error "Project directory not found: $PROJECT_DIR"
        exit 1
    fi

    if [[ ! -f "$PROJECT_DIR/fastapi_app.py" ]]; then
        print_error "FastAPI application not found: $PROJECT_DIR/fastapi_app.py"
        exit 1
    fi

    if [[ ! -f "$PROJECT_DIR/$SERVICE_FILE" ]]; then
        print_error "Service file not found: $PROJECT_DIR/$SERVICE_FILE"
        exit 1
    fi

    if [[ ! -f "$PROJECT_DIR/.env" ]]; then
        print_warning "Environment file not found: $PROJECT_DIR/.env"
        print_info "Copy .env.example to .env and configure your API keys"
        print_info "cp $PROJECT_DIR/.env.example $PROJECT_DIR/.env"
        echo
    fi

    print_status "Project validation complete"
}

# Install the systemd service
install_service() {
    print_info "Installing systemd service..."

    # Copy service file to systemd directory
    cp "$PROJECT_DIR/$SERVICE_FILE" "$SYSTEMD_DIR/"
    print_status "Service file copied to $SYSTEMD_DIR/"

    # Reload systemd daemon
    systemctl daemon-reload
    print_status "Systemd daemon reloaded"

    # Enable the service
    systemctl enable "$SERVICE_NAME"
    print_status "Service enabled for startup"
}

# Check dependencies
check_dependencies() {
    print_info "Checking dependencies..."

    # Check if Python virtual environment exists
    if [[ ! -d "$PROJECT_DIR/.venv" ]]; then
        print_error "Python virtual environment not found at $PROJECT_DIR/.venv"
        print_info "Run: cd $PROJECT_DIR && uv sync --all-extras --dev"
        exit 1
    fi

    # Check if uvicorn is installed
    if [[ ! -f "$PROJECT_DIR/.venv/bin/uvicorn" ]]; then
        print_error "Uvicorn not found in virtual environment"
        print_info "Run: cd $PROJECT_DIR && uv sync --all-extras --dev"
        exit 1
    fi

    print_status "Dependencies check complete"
}

# Set proper permissions
set_permissions() {
    print_info "Setting permissions..."

    # Ensure the project directory is owned by the service user
    chown -R "$USER:$USER" "$PROJECT_DIR"

    # Make scripts executable
    chmod +x "$PROJECT_DIR/run_api.py"
    chmod +x "$PROJECT_DIR/test_api.py"
    chmod +x "$PROJECT_DIR/example_usage.py"

    print_status "Permissions set"
}

# Show service management commands
show_usage() {
    echo
    print_info "Service Management Commands:"
    echo "  Start service:    sudo systemctl start $SERVICE_NAME"
    echo "  Stop service:     sudo systemctl stop $SERVICE_NAME"
    echo "  Restart service:  sudo systemctl restart $SERVICE_NAME"
    echo "  Service status:   sudo systemctl status $SERVICE_NAME"
    echo "  View logs:        sudo journalctl -u $SERVICE_NAME -f"
    echo "  Disable service:  sudo systemctl disable $SERVICE_NAME"
    echo

    print_info "Configuration:"
    echo "  Service file:     $SYSTEMD_DIR/$SERVICE_FILE"
    echo "  Environment:      $PROJECT_DIR/.env"
    echo "  Working dir:      $PROJECT_DIR"
    echo "  Log output:       journalctl -u $SERVICE_NAME"
    echo
}

# Main installation process
main() {
    echo "This script will:"
    echo "  1. Validate project setup and dependencies"
    echo "  2. Install the systemd service"
    echo "  3. Set proper permissions"
    echo "  4. Enable the service for startup"
    echo

    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi

    check_permissions
    validate_project
    check_dependencies
    install_service
    set_permissions

    print_status "Installation complete!"

    echo
    print_info "Next steps:"
    echo "  1. Configure environment variables in $PROJECT_DIR/.env"
    echo "  2. Start the service: sudo systemctl start $SERVICE_NAME"
    echo "  3. Check status: sudo systemctl status $SERVICE_NAME"
    echo "  4. View logs: sudo journalctl -u $SERVICE_NAME -f"

    show_usage
}

# Parse command line arguments
case "${1:-install}" in
    "install")
        main
        ;;
    "uninstall")
        print_info "Uninstalling service..."
        systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        systemctl disable "$SERVICE_NAME" 2>/dev/null || true
        rm -f "$SYSTEMD_DIR/$SERVICE_FILE"
        systemctl daemon-reload
        print_status "Service uninstalled"
        ;;
    "status")
        systemctl status "$SERVICE_NAME"
        ;;
    "logs")
        journalctl -u "$SERVICE_NAME" -f
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [install|uninstall|status|logs|help]"
        echo
        echo "Commands:"
        echo "  install    - Install and enable the systemd service (default)"
        echo "  uninstall  - Stop, disable and remove the systemd service"
        echo "  status     - Show service status"
        echo "  logs       - Show service logs (follow)"
        echo "  help       - Show this help message"
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Run '$0 help' for usage information"
        exit 1
        ;;
esac