# Iron Chef Recipe Database - Deployment Guide

This guide covers deploying the Iron Chef Recipe Database web application in production.

## Prerequisites

- Python 3.7+
- pip package manager
- Web server (Apache/Nginx recommended)
- WSGI server (Gunicorn/uWSGI)

## Installation

1. **Clone the repository and install dependencies:**
```bash
git clone <repository-url>
cd IronChefRecipes
pip install -r requirements.txt
```

2. **Initialize the database:**
```bash
python3 -c "from iron_chef_database_secure import IronChefDatabaseSecure; db = IronChefDatabaseSecure(); db.initialize_database()"
```

3. **Load sample data (optional):**
```bash
python3 sample_data_loader.py
```

## Configuration

### Environment Variables

Set the following environment variables for production:

```bash
# Security
export SECRET_KEY="your-super-secret-key-here"
export FLASK_ENV="production"

# Database
export DATABASE_PATH="/path/to/production/database.db"

# Logging
export LOG_LEVEL="INFO"
export LOG_FILE="/var/log/iron-chef/app.log"
```

### Application Configuration

The app automatically configures itself for production when `FLASK_ENV=production`:

- Secure session cookies
- CSRF protection enabled
- Proper logging configuration
- Security headers

## Deployment Options

### Option 1: Gunicorn (Recommended)

1. **Install Gunicorn:**
```bash
pip install gunicorn
```

2. **Create systemd service file:**
```bash
sudo nano /etc/systemd/system/iron-chef.service
```

Content:
```ini
[Unit]
Description=Iron Chef Recipe Database
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/IronChefRecipes
Environment="PATH=/path/to/IronChefRecipes/venv/bin"
Environment="SECRET_KEY=your-secret-key"
Environment="FLASK_ENV=production"
ExecStart=/path/to/IronChefRecipes/venv/bin/gunicorn --workers 3 --bind unix:iron-chef.sock -m 007 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

3. **Enable and start the service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable iron-chef
sudo systemctl start iron-chef
```

### Option 2: Docker

1. **Create Dockerfile:**
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

ENV FLASK_ENV=production
ENV SECRET_KEY=your-secret-key

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
```

2. **Build and run:**
```bash
docker build -t iron-chef-db .
docker run -p 5000:5000 -e SECRET_KEY="your-secret-key" iron-chef-db
```

## Web Server Configuration

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        include proxy_params;
        proxy_pass http://unix:/path/to/IronChefRecipes/iron-chef.sock;
    }

    location /static {
        alias /path/to/IronChefRecipes/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
```

### Apache Configuration

```apache
<VirtualHost *:80>
    ServerName your-domain.com
    DocumentRoot /path/to/IronChefRecipes

    WSGIDaemonProcess iron-chef python-path=/path/to/IronChefRecipes
    WSGIProcessGroup iron-chef
    WSGIScriptAlias / /path/to/IronChefRecipes/app.wsgi

    <Directory /path/to/IronChefRecipes>
        WSGIApplicationGroup %{GLOBAL}
        Require all granted
    </Directory>

    Alias /static /path/to/IronChefRecipes/static
    <Directory /path/to/IronChefRecipes/static>
        Require all granted
    </Directory>
</VirtualHost>
```

## SSL/HTTPS Setup

For production, always use HTTPS:

1. **Using Let's Encrypt with Certbot:**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

2. **Update environment variable:**
```bash
export FLASK_ENV=production  # Enables secure cookies
```

## Database Management

### Backup
```bash
# Create backup
cp iron_chef_japan.db backups/iron_chef_japan_$(date +%Y%m%d_%H%M%S).db

# Automated backup script
crontab -e
# Add: 0 2 * * * /path/to/backup-script.sh
```

### Monitoring
```bash
# Check database size
ls -lh iron_chef_japan.db

# Check table counts
python3 -c "
from iron_chef_database_secure import IronChefDatabaseSecure
with IronChefDatabaseSecure() as db:
    for table in ['episodes', 'dishes', 'recipes']:
        db.cursor.execute(f'SELECT COUNT(*) FROM {table}')
        print(f'{table}: {db.cursor.fetchone()[0]}')
"
```

## Performance Optimization

### Application Level
- Enable gzip compression in web server
- Set proper cache headers for static files
- Use database connection pooling
- Monitor memory usage with `htop` or similar

### Database Level
- The application includes optimized indexes
- Regular VACUUM operations:
```bash
python3 -c "
from iron_chef_database_secure import IronChefDatabaseSecure
with IronChefDatabaseSecure() as db:
    db.cursor.execute('VACUUM')
"
```

## Monitoring and Logging

### Application Logs
- Logs are written to `iron_chef_app.log`
- Configure log rotation:

```bash
sudo nano /etc/logrotate.d/iron-chef
```

Content:
```
/var/log/iron-chef/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 www-data www-data
}
```

### Health Checks
```bash
# Simple health check script
curl -f http://localhost:5000/ > /dev/null 2>&1 && echo "OK" || echo "FAIL"
```

## Security Considerations

1. **Keep dependencies updated:**
```bash
pip list --outdated
pip install -U package-name
```

2. **Regular security scans:**
```bash
pip install safety
safety check
```

3. **File permissions:**
```bash
chmod 600 iron_chef_japan.db
chown www-data:www-data iron_chef_japan.db
```

4. **Firewall configuration:**
```bash
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

## Troubleshooting

### Common Issues

1. **Database locked error:**
   - Check file permissions
   - Ensure only one process is accessing the database

2. **Static files not loading:**
   - Verify web server static file configuration
   - Check file permissions

3. **CSRF errors:**
   - Ensure SECRET_KEY is set consistently
   - Check that HTTPS is properly configured

### Debug Mode
Never use debug mode in production, but for testing:
```bash
export FLASK_ENV=development
python3 app.py
```

## Scaling

For high-traffic deployments:

1. **Multiple workers:**
```bash
gunicorn --workers 4 --bind 0.0.0.0:5000 app:app
```

2. **Load balancing with multiple instances**
3. **CDN for static assets**
4. **Database replication (if needed)**

## Backup and Recovery

### Automated Backup Script
```bash
#!/bin/bash
# backup-script.sh
BACKUP_DIR="/backups/iron-chef"
DATE=$(date +%Y%m%d_%H%M%S)
DB_FILE="iron_chef_japan.db"

mkdir -p "$BACKUP_DIR"
cp "$DB_FILE" "$BACKUP_DIR/iron_chef_${DATE}.db"

# Keep only last 30 backups
cd "$BACKUP_DIR"
ls -t iron_chef_*.db | tail -n +31 | xargs -r rm
```

## Support

For deployment issues:
1. Check application logs
2. Verify environment variables
3. Test database connectivity
4. Check web server error logs

The application includes comprehensive error handling and logging to help diagnose issues quickly.