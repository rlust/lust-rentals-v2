# Production Deployment Guide

This guide covers deploying the Lust Rentals Tax Reporting application to production.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Configuration](#configuration)
4. [SSL Certificate Setup](#ssl-certificate-setup)
5. [Deployment](#deployment)
6. [Monitoring & Maintenance](#monitoring--maintenance)
7. [Backup & Recovery](#backup--recovery)
8. [Troubleshooting](#troubleshooting)
9. [Security Checklist](#security-checklist)

---

## Prerequisites

### Hardware Requirements

**Minimum (Small deployment):**
- 2 CPU cores
- 4 GB RAM
- 50 GB storage (SSD recommended)

**Recommended (Production):**
- 4 CPU cores
- 8 GB RAM
- 100 GB storage (SSD)
- Additional storage for backups

### Software Requirements

- Docker Engine 20.10+
- Docker Compose 2.0+
- Linux OS (Ubuntu 20.04+ or similar)
- Domain name (for SSL certificates)

### Network Requirements

- Ports 80 (HTTP) and 443 (HTTPS) open
- Outbound internet access (for backups, if using cloud storage)

---

## Initial Setup

### 1. Clone Repository

```bash
git clone https://github.com/rlust/lust-rentals-tax-reporting.git
cd lust-rentals-tax-reporting
```

### 2. Create Required Directories

```bash
mkdir -p data/raw data/processed data/reports data/overrides
mkdir -p backups logs nginx/logs
```

### 3. Set Permissions

```bash
# Ensure proper permissions for data directories
chmod -R 755 data
chmod -R 755 backups
chmod -R 755 logs
```

---

## Configuration

### 1. Environment Configuration

Copy the production environment template:

```bash
cp .env.production.example .env.production
```

Edit `.env.production` and configure:

#### Required Settings

```bash
# Generate a secure secret key
openssl rand -hex 32

# Edit .env.production
LUST_DATA_DIR=/app/data
LUST_LOG_LEVEL=INFO
API_SECRET_KEY=<your-generated-key>
ALLOWED_ORIGINS=https://yourdomain.com
AUTH_ENABLED=true
```

#### Backup Configuration

**Option A: Local Backups Only**
```bash
BACKUP_ENABLED=true
BACKUP_RETENTION_DAYS=90
```

**Option B: AWS S3 Backups**
```bash
BACKUP_ENABLED=true
BACKUP_RETENTION_DAYS=90
BACKUP_DESTINATION=s3://your-backup-bucket/lust-rentals
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
```

**Option C: Google Cloud Storage**
```bash
BACKUP_ENABLED=true
BACKUP_RETENTION_DAYS=90
BACKUP_DESTINATION=gs://your-backup-bucket/lust-rentals
# Place GCP credentials at: ./config/gcp-credentials.json
GOOGLE_APPLICATION_CREDENTIALS=/app/config/gcp-credentials.json
```

**Option D: Azure Blob Storage**
```bash
BACKUP_ENABLED=true
BACKUP_RETENTION_DAYS=90
BACKUP_DESTINATION=azure://your-container/lust-rentals
AZURE_STORAGE_ACCOUNT=yourstorageaccount
AZURE_STORAGE_KEY=your_storage_key
```

### 2. Docker Compose Configuration

The `docker-compose.production.yml` file is pre-configured with:
- FastAPI application
- Nginx reverse proxy with SSL
- Automated backup service

Review and adjust resource limits if needed:

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
```

---

## SSL Certificate Setup

### Option 1: Let's Encrypt (Recommended)

#### Using Certbot

1. **Install Certbot:**
```bash
sudo apt-get update
sudo apt-get install certbot
```

2. **Generate Certificate:**
```bash
sudo certbot certonly --standalone \
  -d yourdomain.com \
  -d www.yourdomain.com \
  --email your-email@example.com \
  --agree-tos
```

3. **Copy Certificates:**
```bash
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem \
  nginx/ssl/certificate.crt
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem \
  nginx/ssl/private.key
```

4. **Update nginx.conf:**
```bash
# Edit nginx/nginx.conf
# Change: server_name _;
# To:     server_name yourdomain.com www.yourdomain.com;
```

5. **Set Up Auto-Renewal:**
```bash
# Add to crontab
sudo crontab -e

# Add this line:
0 0 * * * certbot renew --quiet --post-hook "cd /path/to/lust-rentals-tax-reporting && docker-compose -f docker-compose.production.yml restart nginx"
```

### Option 2: Self-Signed (Development/Testing Only)

⚠️ **WARNING: Do NOT use in production!**

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/private.key \
  -out nginx/ssl/certificate.crt \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
```

### Verify SSL Setup

```bash
# Check certificate
openssl x509 -in nginx/ssl/certificate.crt -text -noout

# Verify expiration date
openssl x509 -in nginx/ssl/certificate.crt -noout -dates
```

---

## Deployment

### 1. Build the Application

```bash
docker-compose -f docker-compose.production.yml build
```

### 2. Start Services

```bash
# Start in detached mode
docker-compose -f docker-compose.production.yml up -d

# View logs
docker-compose -f docker-compose.production.yml logs -f
```

### 3. Verify Deployment

```bash
# Check service health
docker-compose -f docker-compose.production.yml ps

# Test health endpoint
curl https://yourdomain.com/health

# Expected response: {"status":"ok"}
```

### 4. Initial Data Setup

Place your initial data files:

```bash
# Copy bank transaction file
cp transaction_report-3.csv data/raw/

# Copy deposit mapping file
cp deposit_amount_map.csv data/raw/
```

### 5. Access the Application

Navigate to: `https://yourdomain.com/review`

---

## Monitoring & Maintenance

### View Logs

```bash
# All services
docker-compose -f docker-compose.production.yml logs -f

# Specific service
docker-compose -f docker-compose.production.yml logs -f app
docker-compose -f docker-compose.production.yml logs -f nginx
docker-compose -f docker-compose.production.yml logs -f backup
```

### Monitor Resource Usage

```bash
# Container stats
docker stats

# Disk usage
df -h
du -sh data/ backups/
```

### Service Management

```bash
# Restart a service
docker-compose -f docker-compose.production.yml restart app

# Stop all services
docker-compose -f docker-compose.production.yml down

# Stop and remove volumes (⚠️ DESTRUCTIVE)
docker-compose -f docker-compose.production.yml down -v
```

### Update Application

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose -f docker-compose.production.yml build
docker-compose -f docker-compose.production.yml up -d

# Verify
docker-compose -f docker-compose.production.yml ps
```

---

## Backup & Recovery

### Automated Backups

Backups run automatically daily at 2 AM UTC via the backup service.

View backup logs:
```bash
docker-compose -f docker-compose.production.yml logs backup
tail -f backups/backup.log
```

### Manual Backup

```bash
# Run backup immediately
docker-compose -f docker-compose.production.yml exec backup /bin/sh /app/backup.sh
```

### List Available Backups

```bash
./scripts/restore.sh -l
```

### Restore from Backup

⚠️ **WARNING: This will overwrite current data!**

```bash
# Restore latest backup
./scripts/restore.sh -d latest

# Restore specific date
./scripts/restore.sh -d 2025-01-15
```

### Download Cloud Backups

If using cloud storage:

**AWS S3:**
```bash
aws s3 ls s3://your-backup-bucket/lust-rentals/
aws s3 sync s3://your-backup-bucket/lust-rentals/2025-01-15/ ./restore/
```

**Google Cloud Storage:**
```bash
gsutil ls gs://your-backup-bucket/lust-rentals/
gsutil -m rsync -r gs://your-backup-bucket/lust-rentals/2025-01-15/ ./restore/
```

**Azure:**
```bash
az storage blob list --container-name your-container --prefix lust-rentals/
az storage blob download-batch \
  --source your-container \
  --destination ./restore/ \
  --pattern "lust-rentals/2025-01-15/*"
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose -f docker-compose.production.yml logs

# Verify configuration
docker-compose -f docker-compose.production.yml config

# Check disk space
df -h
```

### SSL Certificate Errors

```bash
# Verify certificate files exist
ls -lh nginx/ssl/

# Check certificate validity
openssl x509 -in nginx/ssl/certificate.crt -text -noout

# Test SSL connection
openssl s_client -connect yourdomain.com:443
```

### Database Locked Errors

SQLite may lock under heavy concurrent access. Solutions:

1. **Enable WAL mode** (Write-Ahead Logging):
```bash
sqlite3 data/overrides/overrides.db 'PRAGMA journal_mode=WAL;'
sqlite3 data/processed/processed.db 'PRAGMA journal_mode=WAL;'
```

2. **Consider PostgreSQL migration** for multi-user scenarios

### Application Not Accessible

```bash
# Check if nginx is running
docker-compose -f docker-compose.production.yml ps nginx

# Check nginx logs
docker-compose -f docker-compose.production.yml logs nginx

# Verify ports are open
sudo netstat -tlnp | grep -E ':80|:443'

# Test internal connectivity
docker-compose -f docker-compose.production.yml exec nginx curl http://app:8000/health
```

### High Memory Usage

```bash
# Check container stats
docker stats

# Restart application
docker-compose -f docker-compose.production.yml restart app

# Adjust resource limits in docker-compose.production.yml
```

---

## Security Checklist

Before going live, verify:

- [ ] SSL certificates installed and valid
- [ ] `.env.production` contains strong, unique `API_SECRET_KEY`
- [ ] `.env.production` is NOT committed to version control
- [ ] Firewall configured (only ports 80, 443, and SSH open)
- [ ] Authentication enabled (`AUTH_ENABLED=true`)
- [ ] Automated backups enabled and tested
- [ ] Cloud backup destination configured (if applicable)
- [ ] Backup restore process tested
- [ ] Admin password changed from default
- [ ] File permissions set correctly (no world-writable files)
- [ ] Nginx security headers enabled (already in config)
- [ ] Rate limiting configured (already in nginx.conf)
- [ ] Database files backed up regularly
- [ ] SSL certificate auto-renewal configured
- [ ] Monitoring and alerting set up
- [ ] Incident response plan documented
- [ ] Access logs enabled and retained

---

## Additional Security Recommendations

### 1. Add Authentication

The current application does NOT include authentication. Before production deployment, add:

- OAuth2/JWT authentication
- Role-based access control (RBAC)
- Session management
- Login rate limiting

### 2. Database Security

Consider migrating from SQLite to PostgreSQL for:
- Better concurrency
- Row-level locking
- Enhanced security features
- Better backup tools

### 3. Network Security

- Use a VPN or private network
- Implement IP whitelisting if possible
- Enable fail2ban for SSH protection
- Use security groups (if on cloud platform)

### 4. Monitoring

Set up monitoring with:
- **Uptime**: Better Uptime, Pingdom
- **Errors**: Sentry (configure `SENTRY_DSN`)
- **Metrics**: Prometheus + Grafana
- **Logs**: ELK stack or CloudWatch

### 5. Compliance

For tax/financial data:
- Keep audit logs for 7+ years
- Encrypt data at rest
- Implement data retention policy
- Document access controls
- Regular security audits

---

## Support

For issues or questions:

1. Check logs: `docker-compose -f docker-compose.production.yml logs`
2. Review troubleshooting section above
3. Check GitHub issues
4. Contact system administrator

---

## Maintenance Schedule

| Task | Frequency | Command/Action |
|------|-----------|----------------|
| Check backups | Daily | Verify `backups/backup.log` |
| Review logs | Weekly | `docker-compose logs` |
| Update SSL cert | Every 60 days | Certbot auto-renewal |
| Security updates | Monthly | `apt update && apt upgrade` |
| Database vacuum | Monthly | `sqlite3 db 'VACUUM;'` |
| Test restore | Quarterly | `./scripts/restore.sh -d latest` |
| Security audit | Annually | External audit |

---

**Last Updated:** 2025-11-06
**Version:** 1.0
