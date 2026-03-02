#!/bin/bash
# Service management script for Demetra FastAPI

SERVICE_NAME="demetra-api"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

check_service_exists() {
    if ! systemctl list-unit-files | grep -q "$SERVICE_NAME.service"; then
        print_error "Service $SERVICE_NAME is not installed"
        print_info "Run: sudo ./setup_systemd.sh install"
        exit 1
    fi
}

start_service() {
    check_service_exists
    print_info "Starting $SERVICE_NAME service..."
    if sudo systemctl start "$SERVICE_NAME"; then
        print_status "Service started successfully"
        show_status
    else
        print_error "Failed to start service"
        exit 1
    fi
}

stop_service() {
    check_service_exists
    print_info "Stopping $SERVICE_NAME service..."
    if sudo systemctl stop "$SERVICE_NAME"; then
        print_status "Service stopped successfully"
    else
        print_error "Failed to stop service"
        exit 1
    fi
}

restart_service() {
    check_service_exists
    print_info "Restarting $SERVICE_NAME service..."
    if sudo systemctl restart "$SERVICE_NAME"; then
        print_status "Service restarted successfully"
        show_status
    else
        print_error "Failed to restart service"
        exit 1
    fi
}

show_status() {
    check_service_exists
    echo
    sudo systemctl status "$SERVICE_NAME" --no-pager
    echo

    # Show if service is running
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        print_status "Service is running"
        print_info "API available at: http://localhost:8000"
        print_info "Documentation: http://localhost:8000/docs"
    else
        print_warning "Service is not running"
    fi
}

show_logs() {
    check_service_exists
    print_info "Showing logs for $SERVICE_NAME (press Ctrl+C to exit)"
    sudo journalctl -u "$SERVICE_NAME" -f
}

show_recent_logs() {
    check_service_exists
    print_info "Recent logs for $SERVICE_NAME:"
    sudo journalctl -u "$SERVICE_NAME" --no-pager -n 50
}

enable_service() {
    check_service_exists
    print_info "Enabling $SERVICE_NAME for startup..."
    if sudo systemctl enable "$SERVICE_NAME"; then
        print_status "Service enabled for startup"
    else
        print_error "Failed to enable service"
        exit 1
    fi
}

disable_service() {
    check_service_exists
    print_info "Disabling $SERVICE_NAME from startup..."
    if sudo systemctl disable "$SERVICE_NAME"; then
        print_status "Service disabled from startup"
    else
        print_error "Failed to disable service"
        exit 1
    fi
}

reload_config() {
    check_service_exists
    print_info "Reloading systemd configuration..."
    sudo systemctl daemon-reload
    print_status "Configuration reloaded"
    print_info "You may need to restart the service: ./manage_service.sh restart"
}

test_api() {
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        print_info "Testing API health check..."
        if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health | grep -q "200"; then
            print_status "API is healthy and responding"
            print_info "Full test: make test-api"
        else
            print_warning "API health check failed"
        fi
    else
        print_error "Service is not running"
        print_info "Start it with: ./manage_service.sh start"
    fi
}

show_help() {
    echo "Usage: $0 <command>"
    echo
    echo "Commands:"
    echo "  start     - Start the service"
    echo "  stop      - Stop the service"
    echo "  restart   - Restart the service"
    echo "  status    - Show service status"
    echo "  logs      - Show live logs (follow)"
    echo "  recent    - Show recent logs"
    echo "  enable    - Enable service for startup"
    echo "  disable   - Disable service from startup"
    echo "  reload    - Reload systemd configuration"
    echo "  test      - Test API health"
    echo "  help      - Show this help message"
    echo
    echo "Examples:"
    echo "  $0 start          # Start the service"
    echo "  $0 status         # Check if service is running"
    echo "  $0 logs           # Watch live logs"
    echo "  $0 test           # Test if API is responding"
}

# Main command handling
case "${1:-help}" in
    "start")
        start_service
        ;;
    "stop")
        stop_service
        ;;
    "restart")
        restart_service
        ;;
    "status")
        show_status
        ;;
    "logs")
        show_logs
        ;;
    "recent")
        show_recent_logs
        ;;
    "enable")
        enable_service
        ;;
    "disable")
        disable_service
        ;;
    "reload")
        reload_config
        ;;
    "test")
        test_api
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo
        show_help
        exit 1
        ;;
esac