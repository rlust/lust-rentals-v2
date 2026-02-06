# Mac Mini Home Server Deployment Guide

Complete guide for deploying Lust Rentals Tax Reporting on your Mac Mini for 24/7 operation with remote access.

## 🎯 Overview

This deployment provides:
- ✅ **Zero hosting costs** - runs on your existing Mac Mini
- ✅ **Maximum privacy** - your financial data never leaves your home
- ✅ **Auto-start on boot** - survives reboots automatically
- ✅ **Remote access** - access from anywhere via Tailscale VPN
- ✅ **Automated backups** - to external drive and iCloud
- ✅ **Health monitoring** - automatic alerts on failures

---

## 📋 Prerequisites

### Hardware
- Mac Mini (any model, M1/M2 recommended)
- External drive for backups (recommended)
- Stable internet connection

### Software
- macOS 11 (Big Sur) or later
- Docker Desktop for Mac
- 10GB free disk space

---

## 🚀 Quick Start (30 Minutes)

### Step 1: Install Docker Desktop

1. Download Docker Desktop: https://www.docker.com/products/docker-desktop/
2. Install Docker Desktop.app
3. Open Docker Desktop to start the daemon
4. Verify Docker is running (check menu bar icon)

### Step 2: Run Automated Setup

```bash
cd /Users/randylust/lust-rentals-tax-reporting
./scripts/mac-setup.sh
```

This script will:
- ✅ Check prerequisites
- ✅ Create production configuration
- ✅ Build Docker image
- ✅ Set up auto-start configuration
- ✅ Start the application

**That's it!** Your app is now running at http://localhost:8002

---

## 🔐 Post-Setup Configuration

### 1. Review .env.production

Edit the generated configuration file:

```bash
nano .env.production
```

Key settings to review:
- `BACKUP_DIR` - Set your external drive path
- `BACKUP_CLOUD_DIR` - iCloud Drive location
- `ALERT_EMAIL` - Your email for alerts
- `SMTP_*` - Email settings (optional)

### 2. Enable Auto-Start on Boot

```bash
# Install LaunchDaemon (requires sudo password)
sudo cp com.lustrental.taxreporting.plist /Library/LaunchDaemons/
sudo launchctl load /Library/LaunchDaemons/com.lustrental.taxreporting.plist
```

Now your app will start automatically when your Mac boots!

### 3. Set Up Remote Access

Install Tailscale for secure remote access:

```bash
./scripts/tailscale-setup.sh
```

This gives you a permanent URL like: `http://mac-mini.tail12345.ts.net:8002`

Install Tailscale on your other devices (phone, laptop) to access from anywhere!

### 4. Configure Backups

Set up automated backups:

```bash
# Configure backup locations
./scripts/mac-backup.sh setup

# Create first backup
./scripts/mac-backup.sh

# Schedule daily backups (2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /Users/randylust/lust-rentals-tax-reporting/scripts/mac-backup.sh") | crontab -
```

---

## 🔧 Service Management

### Start/Stop/Restart

```bash
# Start service
./scripts/mac-service.sh start

# Stop service
./scripts/mac-service.sh stop

# Restart service
./scripts/mac-service.sh restart

# Check status
./scripts/mac-service.sh status

# View logs
./scripts/mac-service.sh logs
```

### Update to Latest Version

```bash
# Pull latest changes and restart
./scripts/mac-service.sh update
```

---

## 📱 Accessing Your Application

### Local Access
- **Dashboard**: http://localhost:8002
- **Enhanced Review**: http://localhost:8002/review-enhanced
- **API Docs**: http://localhost:8002/docs

### Network Access
From other devices on your home network:
- **Dashboard**: http://mac-mini.local:8002

### Remote Access (via Tailscale)
From anywhere in the world:
- **Dashboard**: http://your-mac.tail12345.ts.net:8002

---

## 💾 Backup & Restore

### Manual Backup

```bash
# Create backup now
./scripts/mac-backup.sh

# List available backups
./scripts/mac-backup.sh list
```

### Restore from Backup

```bash
./scripts/mac-backup.sh restore
```

### Backup Locations

1. **External Drive** (Primary)
   - `/Volumes/Backup/lust-rentals-backups/`
   - Connect external drive before backups

2. **iCloud Drive** (Automatic Cloud Sync)
   - `~/Library/Mobile Documents/com~apple~CloudDocs/TaxBackups/`
   - Syncs automatically to cloud

3. **Time Machine** (System-Level)
   - Enable Time Machine for full Mac backup
   - Backs up everything including the app

---

## 🔍 Monitoring & Health Checks

### Manual Health Check

```bash
./scripts/health-monitor.sh
```

### Continuous Monitoring

```bash
# Monitor every 15 minutes (run in background)
./scripts/health-monitor.sh loop &
```

### Enable Monitoring via Cron

```bash
# Check every 15 minutes
(crontab -l 2>/dev/null; echo "*/15 * * * * /Users/randylust/lust-rentals-tax-reporting/scripts/health-monitor.sh") | crontab -
```

---

## 🛡️ Security Best Practices

### 1. Enable FileVault

Encrypt your Mac's disk:
- System Preferences → Security & Privacy → FileVault
- Click "Turn On FileVault"

### 2. Enable Firewall

```bash
# Enable macOS firewall
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on
```

### 3. Keep macOS Updated

Enable automatic updates:
- System Preferences → Software Update
- Enable "Automatically keep my Mac up to date"

### 4. Secure .env.production

```bash
# Restrict file permissions
chmod 600 .env.production
```

### 5. Regular Backups

- Daily: Automated backup via cron
- Weekly: Verify backups are working
- Monthly: Test restore procedure

---

## 🔧 Troubleshooting

### Application Won't Start

```bash
# Check if Docker is running
docker ps

# If Docker not running, start Docker Desktop
open -a Docker

# Check logs
./scripts/mac-service.sh logs
```

### Can't Access Remotely

```bash
# Check Tailscale status
tailscale status

# Restart Tailscale
sudo tailscale down
sudo tailscale up
```

### Backup Fails

```bash
# Check external drive is connected
ls /Volumes/

# Check iCloud Drive is enabled
ls ~/Library/Mobile\ Documents/com~apple~CloudDocs/

# Run backup setup again
./scripts/mac-backup.sh setup
```

### High CPU/Memory Usage

```bash
# Check resource usage
docker stats

# Restart service
./scripts/mac-service.sh restart
```

---

## 📊 Performance Optimization

### For M1/M2 Mac Mini

The application is optimized for Apple Silicon. No changes needed!

### For Intel Mac Mini

If experiencing slow performance:

1. Increase Docker resources:
   - Docker Desktop → Preferences → Resources
   - CPU: 4 cores
   - Memory: 4GB

2. Enable SSD optimization:
   ```bash
   # Add to .env.production
   SQLITE_WAL_MODE=true
   ```

---

## 🔄 Maintenance Schedule

### Daily (Automated)
- ✅ Backups (2 AM)
- ✅ Health checks (every 15 min)

### Weekly (Manual - 5 minutes)
- Check disk space: `df -h`
- Review logs: `./scripts/mac-service.sh logs | tail -100`
- Verify backups exist: `./scripts/mac-backup.sh list`

### Monthly (Manual - 15 minutes)
- Test backup restore
- Update application: `./scripts/mac-service.sh update`
- Check for macOS updates
- Clean old backups (automated, but verify)

### Annually (Manual - 30 minutes)
- Full security review
- Test disaster recovery
- Update documentation
- Review and archive old tax years

---

## 💡 Pro Tips

### 1. Energy Saver Settings

Keep Mac Mini always on:
- System Preferences → Energy Saver
- Uncheck "Put hard disks to sleep when possible"
- Set "Start up automatically after a power failure"

### 2. Remote Desktop

Enable Screen Sharing for remote management:
- System Preferences → Sharing → Screen Sharing
- Access via Tailscale: `vnc://mac-mini.tail12345.ts.net`

### 3. Notification on Failures

macOS notifications are enabled by default. You'll see alerts on:
- Container crashes
- Health check failures
- Backup errors

### 4. Multiple Users

To allow other household members:
1. Set up their devices with Tailscale (same account)
2. Share the Tailscale URL with them
3. They can access from their phone/computer

---

## 📚 Additional Resources

### Documentation
- [Enhanced Review Guide](ENHANCED_REVIEW_GUIDE.md)
- [Backup Export Guide](BACKUP_EXPORT_GUIDE.md)
- [Property Management Guide](PROPERTY_MANAGEMENT_FEATURE.md)

### Scripts Reference
- `scripts/mac-setup.sh` - Initial setup
- `scripts/mac-service.sh` - Service management
- `scripts/mac-backup.sh` - Backup operations
- `scripts/tailscale-setup.sh` - Remote access setup
- `scripts/health-monitor.sh` - Health monitoring

### Support
- GitHub Issues: https://github.com/rlust/lust-rentals-tax-reporting/issues
- Tailscale Support: https://tailscale.com/contact/support/
- Docker Support: https://docs.docker.com/desktop/mac/

---

## 🎉 You're All Set!

Your Lust Rentals Tax Reporting application is now:
- ✅ Running 24/7 on your Mac Mini
- ✅ Auto-starting on boot
- ✅ Accessible remotely via Tailscale
- ✅ Automatically backing up to multiple locations
- ✅ Monitored for health and uptime

**Access your app:**
- Local: http://localhost:8002
- Remote: http://your-mac.tail12345.ts.net:8002

**Need help?** Run any script with `--help` for detailed usage information.

---

**Last Updated:** November 2025
**Version:** 2.0
**Deployment Type:** Mac Mini Home Server
