# BRD-18: Infrastructure & Deployment

**Document ID:** BRD-18
**Version:** 1.0
**Status:** Draft
**Author:** BSA Agent
**Date:** 2026-05-26
**Implementation Order:** 19 of 19

---

## 1. Executive Summary

Define the infrastructure setup for Oracle VM deployment with Caddy reverse proxy, systemd services, and PostgreSQL. This BRD covers the complete deployment pipeline from development to production.

## 2. RF Traceability

| RF | Requirement | Coverage |
|----|-------------|----------|
| RF-05 | Single-server scope | Complete |
| tech-stack | Oracle VM, Caddy, systemd | Complete |

## 3. Dependencies

| Depends On | Required For |
|------------|--------------|
| All previous BRDs | Production |

---

## 4. Technical Specification

### 4.1 Infrastructure Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Oracle VM                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                      Caddy                               │ │
│  │         (HTTPS termination, reverse proxy)               │ │
│  │         novum.duckdns.org:443                           │ │
│  └─────────────────────────────────────────────────────────┘ │
│                           │                                  │
│          ┌────────────────┴────────────────┐                │
│          │                                 │                │
│          ▼                                 ▼                │
│  ┌───────────────┐               ┌─────────────────┐        │
│  │   Backend     │               │    Frontend     │        │
│  │   (uvicorn)   │               │    (static)     │        │
│  │   :8000       │               │    /var/www     │        │
│  └───────────────┘               └─────────────────┘        │
│          │                                                   │
│          ▼                                                   │
│  ┌───────────────┐                                          │
│  │  PostgreSQL   │                                          │
│  │    :5432      │                                          │
│  └───────────────┘                                          │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 File Structure

```
deploy/
  caddy/
    Caddyfile
  systemd/
    novum-backend.service
    novum-worker.service (V2)
  scripts/
    setup.sh              # Initial server setup
    deploy.sh             # Deployment script
    backup.sh             # Database backup
  nginx/                  # Not used (Caddy instead)
```

### 4.3 Caddy Configuration

#### deploy/caddy/Caddyfile

```caddyfile
# Caddyfile for Novum
# Automatic HTTPS via Let's Encrypt

{
    email admin@example.com
    # Uncomment for staging during testing
    # acme_ca https://acme-staging-v02.api.letsencrypt.org/directory
}

novum.duckdns.org {
    # Enable compression
    encode gzip zstd

    # API routes -> Backend
    handle /api/* {
        reverse_proxy localhost:8000 {
            # SSE support
            flush_interval -1
            
            # Health check
            health_uri /api/health
            health_interval 30s
            health_timeout 5s
        }
    }

    # Static frontend files
    handle {
        root * /var/www/novum
        try_files {path} /index.html
        file_server
    }

    # Security headers
    header {
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        X-XSS-Protection "1; mode=block"
        Referrer-Policy "strict-origin-when-cross-origin"
        # Remove server header
        -Server
    }

    # Logging
    log {
        output file /var/log/caddy/access.log {
            roll_size 10mb
            roll_keep 5
        }
        format json
    }
}

# Health check endpoint (internal)
:2019 {
    metrics /metrics
}
```

### 4.4 Systemd Service

#### deploy/systemd/novum-backend.service

```ini
[Unit]
Description=Novum Backend API
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=exec
User=novum
Group=novum
WorkingDirectory=/opt/novum/backend

# Environment
EnvironmentFile=/opt/novum/.env

# Command
ExecStart=/opt/novum/.venv/bin/uvicorn app.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 1 \
    --log-level info

# Restart policy
Restart=always
RestartSec=5

# Security hardening
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/novum/backend/logs

# Resource limits
MemoryMax=1G
CPUQuota=80%

[Install]
WantedBy=multi-user.target
```

### 4.5 Server Setup Script

#### deploy/scripts/setup.sh

```bash
#!/bin/bash
# Server setup script for Novum

set -euo pipefail

echo "=== Novum Server Setup ==="

# Update system
echo "[1/8] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install dependencies
echo "[2/8] Installing system dependencies..."
sudo apt install -y \
    python3.12 \
    python3.12-venv \
    python3-pip \
    postgresql-16 \
    postgresql-contrib \
    curl \
    git \
    htop

# Install Caddy
echo "[3/8] Installing Caddy..."
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy

# Create application user
echo "[4/8] Creating application user..."
sudo useradd -r -s /bin/false -m -d /opt/novum novum || true

# Create directories
echo "[5/8] Creating directories..."
sudo mkdir -p /opt/novum/{backend,frontend,logs}
sudo mkdir -p /var/www/novum
sudo mkdir -p /var/log/caddy
sudo chown -R novum:novum /opt/novum
sudo chown caddy:caddy /var/log/caddy

# Setup PostgreSQL
echo "[6/8] Setting up PostgreSQL..."
sudo -u postgres psql -c "CREATE USER novum WITH PASSWORD 'changeme';" || true
sudo -u postgres psql -c "CREATE DATABASE novum OWNER novum;" || true
sudo -u postgres psql -c "CREATE DATABASE novum_test OWNER novum;" || true

# Install uv
echo "[7/8] Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh

# Setup Python environment
echo "[8/8] Setting up Python environment..."
cd /opt/novum/backend
sudo -u novum python3.12 -m venv /opt/novum/.venv

echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Copy .env file to /opt/novum/.env"
echo "2. Copy Caddyfile to /etc/caddy/Caddyfile"
echo "3. Copy systemd service to /etc/systemd/system/"
echo "4. Run: sudo systemctl daemon-reload"
echo "5. Run: sudo systemctl enable --now novum-backend caddy"
```

### 4.6 Deployment Script

#### deploy/scripts/deploy.sh

```bash
#!/bin/bash
# Deployment script for Novum

set -euo pipefail

DEPLOY_DIR="/opt/novum"
REPO_URL="https://github.com/your-org/novum.git"
BRANCH="${1:-main}"

echo "=== Deploying Novum (branch: $BRANCH) ==="

# Pull latest code
echo "[1/6] Pulling latest code..."
cd "$DEPLOY_DIR"
if [ -d ".git" ]; then
    sudo -u novum git fetch origin
    sudo -u novum git checkout "$BRANCH"
    sudo -u novum git pull origin "$BRANCH"
else
    sudo -u novum git clone -b "$BRANCH" "$REPO_URL" .
fi

# Install backend dependencies
echo "[2/6] Installing backend dependencies..."
cd "$DEPLOY_DIR/backend"
sudo -u novum /opt/novum/.venv/bin/pip install -e ".[dev]"

# Run migrations
echo "[3/6] Running database migrations..."
sudo -u novum /opt/novum/.venv/bin/alembic upgrade head

# Build frontend
echo "[4/6] Building frontend..."
cd "$DEPLOY_DIR/frontend"
sudo -u novum npm ci
sudo -u novum npm run build

# Copy frontend to web root
echo "[5/6] Deploying frontend..."
sudo rm -rf /var/www/novum/*
sudo cp -r "$DEPLOY_DIR/frontend/dist/"* /var/www/novum/
sudo chown -R caddy:caddy /var/www/novum

# Restart services
echo "[6/6] Restarting services..."
sudo systemctl restart novum-backend
sudo systemctl reload caddy

echo "=== Deployment Complete ==="
echo ""
echo "Health check: curl https://novum.duckdns.org/api/health"
```

### 4.7 Database Backup Script

#### deploy/scripts/backup.sh

```bash
#!/bin/bash
# Database backup script

set -euo pipefail

BACKUP_DIR="/opt/novum/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/novum_$TIMESTAMP.sql.gz"
RETENTION_DAYS=7

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

# Create backup
echo "Creating backup: $BACKUP_FILE"
sudo -u postgres pg_dump novum | gzip > "$BACKUP_FILE"

# Verify backup
if [ -s "$BACKUP_FILE" ]; then
    echo "Backup successful: $(ls -lh "$BACKUP_FILE")"
else
    echo "ERROR: Backup file is empty!"
    exit 1
fi

# Remove old backups
echo "Removing backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "novum_*.sql.gz" -mtime +$RETENTION_DAYS -delete

echo "Current backups:"
ls -lh "$BACKUP_DIR"
```

### 4.8 Environment File Template

#### deploy/.env.template

```bash
# Novum Environment Configuration
# Copy to /opt/novum/.env and fill in values

# Database
DATABASE_URL=postgresql+asyncpg://novum:changeme@localhost:5432/novum

# LLM Provider
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

# Search
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxx

# Application
LOG_LEVEL=info
CORS_ORIGINS=https://novum.duckdns.org

# Optional
# SSE_HEARTBEAT_SECONDS=15
# MAX_SEARCHES=20
# CONFIDENCE_THRESHOLD=0.7
```

### 4.9 DuckDNS Setup

```bash
# Add to crontab for dynamic DNS update
# crontab -e

# Update DuckDNS every 5 minutes
*/5 * * * * curl -s "https://www.duckdns.org/update?domains=novum&token=YOUR_TOKEN&ip=" > /dev/null
```

### 4.10 Monitoring

#### Basic health monitoring with systemd

```ini
# /etc/systemd/system/novum-health.timer
[Unit]
Description=Novum Health Check Timer

[Timer]
OnCalendar=*:0/5
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/novum-health.service
[Unit]
Description=Novum Health Check

[Service]
Type=oneshot
ExecStart=/opt/novum/deploy/scripts/health-check.sh
```

#### deploy/scripts/health-check.sh

```bash
#!/bin/bash
# Health check script

HEALTH_URL="http://localhost:8000/api/health"
WEBHOOK_URL="${ALERT_WEBHOOK_URL:-}"

response=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" --max-time 5)

if [ "$response" != "200" ]; then
    echo "Health check failed! HTTP $response"
    
    # Send alert if webhook configured
    if [ -n "$WEBHOOK_URL" ]; then
        curl -X POST "$WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{\"text\": \"🚨 Novum health check failed! HTTP $response\"}"
    fi
    
    # Restart service
    systemctl restart novum-backend
    exit 1
fi

echo "Health check passed"
```

---

## 5. Acceptance Criteria

### AC-01: HTTPS Works
```gherkin
Given the server is deployed
When I visit https://novum.duckdns.org
Then I see the frontend
  And the connection uses HTTPS
  And the certificate is valid
```

### AC-02: API Accessible
```gherkin
Given the server is deployed
When I call https://novum.duckdns.org/api/health
Then I receive {"status": "ok"}
```

### AC-03: SSE Streams Through Caddy
```gherkin
Given an active SSE connection
When events are emitted
Then they stream through Caddy without buffering
```

### AC-04: Service Auto-Restarts
```gherkin
Given the backend crashes
When systemd detects the failure
Then the service is restarted within 5 seconds
```

---

## 6. Implementation Checklist

- [ ] Create `deploy/caddy/Caddyfile`
- [ ] Create `deploy/systemd/novum-backend.service`
- [ ] Create `deploy/scripts/setup.sh`
- [ ] Create `deploy/scripts/deploy.sh`
- [ ] Create `deploy/scripts/backup.sh`
- [ ] Create `deploy/.env.template`
- [ ] Setup DuckDNS account and domain
- [ ] Configure Oracle VM firewall (ports 80, 443)
- [ ] Run setup script on server
- [ ] Deploy application
- [ ] Verify HTTPS and health checks
- [ ] Setup cron for backups

## 7. Infrastructure Details

| Component | Version | Port | Purpose |
|-----------|---------|------|---------|
| Caddy | 2.x | 80, 443 | Reverse proxy, HTTPS |
| uvicorn | 0.x | 8000 | ASGI server |
| PostgreSQL | 16 | 5432 | Database |
| Python | 3.12 | - | Backend runtime |
| Node.js | 22 | - | Frontend build |

## 8. Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection |
| `GITHUB_TOKEN` | Yes | LLM provider auth |
| `TAVILY_API_KEY` | Yes | Search API key |
| `CORS_ORIGINS` | Yes | Allowed origins |
| `LOG_LEVEL` | No | Logging verbosity |

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Server down | High | Low | Health checks + alerts |
| SSL cert expiry | High | Low | Caddy auto-renewal |
| Database loss | Critical | Low | Daily backups |
| DDoS | Med | Low | Oracle Cloud firewall |

## 10. Out of Scope

- Multi-server deployment
- Kubernetes
- CI/CD pipeline (manual deploy in V1)
- APM/tracing
