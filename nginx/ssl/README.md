# SSL Certificate Setup

This directory should contain your SSL certificates for HTTPS.

## Required Files

- `certificate.crt` - Your SSL certificate
- `private.key` - Your private key

## Option 1: Self-Signed Certificate (Development/Testing Only)

**WARNING: Do NOT use self-signed certificates in production!**

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/private.key \
  -out nginx/ssl/certificate.crt \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
```

## Option 2: Let's Encrypt (Recommended for Production)

### Using Certbot

1. Install certbot:
```bash
sudo apt-get update
sudo apt-get install certbot
```

2. Stop nginx temporarily:
```bash
docker-compose -f docker-compose.production.yml stop nginx
```

3. Generate certificate:
```bash
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com
```

4. Copy certificates to nginx/ssl directory:
```bash
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/certificate.crt
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/private.key
```

5. Update nginx.conf to use your domain name (replace `server_name _;`)

6. Start nginx:
```bash
docker-compose -f docker-compose.production.yml up -d nginx
```

### Certificate Renewal

Let's Encrypt certificates expire after 90 days. Set up auto-renewal:

```bash
# Add to crontab (run twice daily)
0 0,12 * * * certbot renew --quiet --post-hook "docker-compose -f /path/to/docker-compose.production.yml restart nginx"
```

## Option 3: Commercial Certificate

If you purchased a certificate from a CA (e.g., DigiCert, Comodo):

1. Place the certificate file as `certificate.crt`
2. Place the private key as `private.key`
3. Ensure proper permissions:
```bash
chmod 600 nginx/ssl/private.key
chmod 644 nginx/ssl/certificate.crt
```

## Verify Certificate

After setup, verify your certificate:

```bash
openssl x509 -in nginx/ssl/certificate.crt -text -noout
```

Test SSL configuration:
```bash
curl -I https://yourdomain.com
```

Or use online tools:
- https://www.ssllabs.com/ssltest/
- https://www.digicert.com/help/
