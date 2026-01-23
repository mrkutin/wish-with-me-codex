# Nginx Configuration

This directory contains the nginx reverse proxy configuration for production deployments.

## SSL Certificate Setup

### Initial Setup (One-time)

1. Stop nginx if running:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml stop nginx
```

2. Obtain SSL certificates using Certbot:
```bash
sudo certbot certonly --standalone \
  -d wishwith.me \
  -d www.wishwith.me \
  --agree-tos \
  --email your-email@example.com
```

3. Copy certificates to nginx directory:
```bash
sudo cp /etc/letsencrypt/live/wishwith.me/fullchain.pem ./ssl/
sudo cp /etc/letsencrypt/live/wishwith.me/privkey.pem ./ssl/
sudo chown $USER:$USER ./ssl/*
```

4. Start nginx:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d nginx
```

### Certificate Renewal

Let's Encrypt certificates expire every 90 days. Set up auto-renewal:

1. Test renewal (dry run):
```bash
sudo certbot renew --dry-run
```

2. Add cron job for automatic renewal:
```bash
sudo crontab -e
```

Add this line:
```cron
0 0 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/wishwith.me/*.pem /home/ubuntu/wish-with-me-codex/nginx/ssl/ && docker-compose -f /home/ubuntu/wish-with-me-codex/docker-compose.yml -f /home/ubuntu/wish-with-me-codex/docker-compose.prod.yml restart nginx
```

This runs on the 1st of each month at midnight.

## Development (No SSL)

For development without SSL, you can use nginx in HTTP-only mode:

1. Comment out the HTTPS server block in nginx.conf
2. Remove the redirect from HTTP to HTTPS
3. Access the site via http://localhost

## Directory Structure

```
nginx/
├── nginx.conf      # Main nginx configuration
├── ssl/            # SSL certificates (not in git)
│   ├── fullchain.pem
│   └── privkey.pem
└── README.md       # This file
```

## Testing Configuration

Test nginx configuration before reloading:

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec nginx nginx -t
```

Reload nginx after configuration changes:

```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec nginx nginx -s reload
```
