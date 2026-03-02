# Systemd Service Setup for Demetra FastAPI

This guide explains how to set up and manage the Demetra FastAPI application as a systemd service for production deployment.

## Overview

The systemd service configuration provides:
- **Automatic startup** on system boot
- **Process management** with automatic restarts on failure
- **Logging** through journald
- **Security hardening** with restricted permissions
- **Multiple workers** for better performance
- **Graceful shutdown** handling

## Quick Setup

### 1. Install the Service

```bash
# Make sure environment variables are configured
cp .env.example .env
# Edit .env with your API keys

# Install the systemd service
sudo ./setup_systemd.sh install
```

### 2. Start the Service

```bash
# Start the service
make service-start

# Check status
make service-status

# Test the API
make service-test
```

## Manual Setup Steps

### 1. Environment Configuration

Create and configure the environment file:

```bash
cp .env.example .env
```

Edit `.env` and set your API keys:
```bash
LINEAR_API_KEY=your_actual_linear_api_key
LINEAR_TEAM_ID=your_actual_team_id
GROQ_API_KEY=your_actual_groq_api_key
```

### 2. Service Installation

The service file `demetra-api.service` includes:

```ini
[Unit]
Description=Demetra FastAPI Ticket Creator
After=network.target

[Service]
Type=exec
User=manti
Group=manti
WorkingDirectory=/home/manti/www/demetra
Environment=PATH=/home/manti/www/demetra/.venv/bin
ExecStart=/home/manti/www/demetra/.venv/bin/uvicorn fastapi_app:app --host 0.0.0.0 --port 8000 --workers 4
ExecReload=/bin/kill -HUP $MAINPID
KillMode=mixed
Restart=on-failure
RestartSec=5
TimeoutStopSec=30

# Security hardening
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/home/manti/www/demetra
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes

# Environment and logging
EnvironmentFile=-/home/manti/www/demetra/.env
Environment=PYTHONPATH=/home/manti/www/demetra
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal
SyslogIdentifier=demetra-api

[Install]
WantedBy=multi-user.target
```

## Service Management

### Using Make Commands

```bash
# Service lifecycle
make service-start     # Start the service
make service-stop      # Stop the service
make service-restart   # Restart the service
make service-status    # Show service status

# Monitoring
make service-logs      # View live logs
make service-test      # Test API health

# Installation
make service-install   # Install systemd service (requires sudo)
```

### Using Management Script

```bash
# Basic operations
./manage_service.sh start
./manage_service.sh stop
./manage_service.sh restart
./manage_service.sh status

# Monitoring
./manage_service.sh logs       # Follow live logs
./manage_service.sh recent     # Show recent logs
./manage_service.sh test       # Test API health

# Configuration
./manage_service.sh enable     # Enable for startup
./manage_service.sh disable    # Disable from startup
./manage_service.sh reload     # Reload systemd config
```

### Direct Systemctl Commands

```bash
# Service control
sudo systemctl start demetra-api
sudo systemctl stop demetra-api
sudo systemctl restart demetra-api
sudo systemctl status demetra-api

# Enable/disable
sudo systemctl enable demetra-api    # Start on boot
sudo systemctl disable demetra-api   # Don't start on boot

# Logs
sudo journalctl -u demetra-api -f    # Follow logs
sudo journalctl -u demetra-api -n 50 # Recent logs
```

## Configuration

### Service Configuration

The main service configuration is in `demetra-api.service`. Key settings:

- **Workers**: 4 uvicorn workers for better performance
- **Host/Port**: Binds to `0.0.0.0:8000` (all interfaces)
- **User**: Runs as `manti` user (non-root)
- **Restart Policy**: Automatically restarts on failure
- **Security**: Multiple hardening options enabled

### Environment Variables

Environment variables are loaded from:
1. `/home/manti/www/demetra/.env` file
2. Built-in environment variables in the service file

Required variables:
```bash
LINEAR_API_KEY=your_key
LINEAR_TEAM_ID=your_team_id
GROQ_API_KEY=your_groq_key
```

### Uvicorn Configuration

Optional: Use the included `uvicorn.conf` file for advanced configuration:

```bash
# Edit the service to use config file
ExecStart=/home/manti/www/demetra/.venv/bin/uvicorn --config uvicorn.conf
```

## Monitoring and Troubleshooting

### Health Checks

```bash
# API health check
curl http://localhost:8000/health

# Service status
systemctl is-active demetra-api

# Test the API
make service-test
```

### Log Analysis

```bash
# Live logs
sudo journalctl -u demetra-api -f

# Error logs only
sudo journalctl -u demetra-api -p err

# Logs since boot
sudo journalctl -u demetra-api -b

# Logs with timestamps
sudo journalctl -u demetra-api -o short-iso
```

### Common Issues

**Service won't start:**
```bash
# Check service status
sudo systemctl status demetra-api

# Check detailed logs
sudo journalctl -u demetra-api -n 50

# Verify environment file
cat /home/manti/www/demetra/.env

# Test manual start
cd /home/manti/www/demetra
./.venv/bin/uvicorn fastapi_app:app --host 0.0.0.0 --port 8000
```

**Permission issues:**
```bash
# Fix ownership
sudo chown -R manti:manti /home/manti/www/demetra

# Verify file permissions
ls -la /home/manti/www/demetra/
```

**Port conflicts:**
```bash
# Check what's using port 8000
sudo netstat -tulpn | grep :8000

# Change port in service file if needed
sudo systemctl edit demetra-api
```

## Security Considerations

The service includes several security hardening measures:

- **Non-root execution**: Runs as `manti` user
- **Filesystem protection**: Limited write access
- **Kernel protection**: Protected from kernel modifications
- **Process isolation**: Private temporary directory
- **No privilege escalation**: Cannot gain additional privileges

For additional security:

1. **Firewall**: Consider restricting access to port 8000
2. **TLS**: Add SSL/TLS termination (nginx reverse proxy recommended)
3. **Rate limiting**: Implement at the reverse proxy level
4. **Monitoring**: Set up log monitoring and alerting

## Performance Tuning

### Worker Configuration

Adjust workers based on your server:
```bash
# CPU cores * 2 + 1 is a good starting point
workers = 4  # For 2-core server
```

### Resource Limits

Add to service file if needed:
```ini
[Service]
MemoryLimit=512M
CPUQuota=50%
```

### Database Connection Pooling

For high load, consider:
- Connection pooling for Linear API
- Request caching
- Async processing for heavy operations

## Backup and Updates

### Code Updates

```bash
# Stop service
make service-stop

# Update code
git pull

# Install dependencies
uv sync --all-extras --dev

# Start service
make service-start
```

### Service File Updates

```bash
# After modifying demetra-api.service
sudo cp demetra-api.service /etc/systemd/system/
sudo systemctl daemon-reload
make service-restart
```

## Uninstallation

```bash
# Stop and disable service
sudo systemctl stop demetra-api
sudo systemctl disable demetra-api

# Remove service file
sudo rm /etc/systemd/system/demetra-api.service
sudo systemctl daemon-reload

# Or use the setup script
sudo ./setup_systemd.sh uninstall
```

This setup provides a robust, production-ready deployment of your FastAPI application with proper process management, logging, and security.