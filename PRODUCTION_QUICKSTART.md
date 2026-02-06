# Production Deployment - Quick Start

This is a condensed guide for experienced users. For detailed instructions, see [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md).

## Prerequisites

- Docker & Docker Compose installed
- Domain name configured
- Ports 80 & 443 open

## 5-Minute Deployment

### 1. Configure Environment

```bash
# Copy template
cp .env.production.example .env.production

# Generate secret key
echo "API_SECRET_KEY=$(openssl rand -hex 32)" >> .env.production

# Edit other settings
nano .env.production
```

Key settings:
- `ALLOWED_ORIGINS=https://yourdomain.com`
- `BACKUP_ENABLED=true`
- `BACKUP_DESTINATION=s3://your-bucket/path` (optional)

### 2. Set Up SSL

**Let's Encrypt:**
```bash
sudo certbot certonly --standalone -d yourdomain.com
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/certificate.crt
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/private.key
```

**Self-signed (dev only):**
```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/private.key \
  -out nginx/ssl/certificate.crt \
  -subj "/CN=localhost"
```

### 3. Update Nginx Config

```bash
# Edit nginx/nginx.conf
# Change: server_name _;
# To:     server_name yourdomain.com;
```

### 4. Deploy

```bash
# Create directories
mkdir -p data/{raw,processed,reports,overrides} backups logs

# Build and start
docker-compose -f docker-compose.production.yml build
docker-compose -f docker-compose.production.yml up -d

# Verify
docker-compose -f docker-compose.production.yml ps
curl https://yourdomain.com/health
```

### 5. Access Application

Navigate to: `https://yourdomain.com/review`

## Common Commands

```bash
# View logs
docker-compose -f docker-compose.production.yml logs -f

# Restart service
docker-compose -f docker-compose.production.yml restart app

# Stop all
docker-compose -f docker-compose.production.yml down

# Manual backup
docker-compose -f docker-compose.production.yml exec backup /app/backup.sh

# List backups
./scripts/restore.sh -l

# Restore
./scripts/restore.sh -d latest
```

## Security Checklist

Before going live:

- [ ] SSL certificates installed
- [ ] Strong `API_SECRET_KEY` set
- [ ] Backups enabled and tested
- [ ] Firewall configured
- [ ] Domain configured in nginx.conf
- [ ] `.env.production` not in git

## Need Help?

See detailed guide: [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md)
