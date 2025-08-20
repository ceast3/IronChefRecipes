#!/usr/bin/env python3
"""
Deployment script for Iron Chef Recipe Database API
Handles environment setup, dependency installation, and configuration
"""

import os
import sys
import subprocess
import argparse
import shutil
from pathlib import Path


class APIDeployer:
    """Handles deployment of the Iron Chef API"""
    
    def __init__(self, environment='development'):
        self.environment = environment
        self.project_root = Path(__file__).parent
        self.venv_path = self.project_root / 'venv'
        
    def check_python_version(self):
        """Check if Python version is compatible"""
        if sys.version_info < (3, 7):
            print("ERROR: Python 3.7 or higher is required")
            sys.exit(1)
        print(f"✓ Python {sys.version} is compatible")
    
    def create_virtual_environment(self):
        """Create and activate virtual environment"""
        print("Creating virtual environment...")
        
        if self.venv_path.exists():
            print("Virtual environment already exists")
            return
        
        try:
            subprocess.run([sys.executable, '-m', 'venv', str(self.venv_path)], 
                         check=True, capture_output=True)
            print("✓ Virtual environment created")
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to create virtual environment: {e}")
            sys.exit(1)
    
    def install_dependencies(self):
        """Install Python dependencies"""
        print("Installing dependencies...")
        
        pip_path = self.venv_path / ('Scripts' if os.name == 'nt' else 'bin') / 'pip'
        requirements_file = self.project_root / 'requirements.txt'
        
        if not requirements_file.exists():
            print("ERROR: requirements.txt not found")
            sys.exit(1)
        
        try:
            subprocess.run([str(pip_path), 'install', '-r', str(requirements_file)], 
                         check=True, capture_output=True)
            print("✓ Dependencies installed")
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to install dependencies: {e}")
            sys.exit(1)
    
    def setup_database(self):
        """Initialize the database"""
        print("Setting up database...")
        
        python_path = self.venv_path / ('Scripts' if os.name == 'nt' else 'bin') / 'python'
        
        try:
            # Test database setup
            test_script = """
import sys
sys.path.insert(0, '.')
from iron_chef_database_secure import IronChefDatabaseSecure

try:
    with IronChefDatabaseSecure() as db:
        db.initialize_database()
    print("Database initialized successfully")
except Exception as e:
    print(f"Database initialization failed: {e}")
    sys.exit(1)
"""
            
            result = subprocess.run([str(python_path), '-c', test_script], 
                                  cwd=self.project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✓ Database setup completed")
            else:
                print(f"ERROR: Database setup failed: {result.stderr}")
                sys.exit(1)
                
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to setup database: {e}")
            sys.exit(1)
    
    def create_config_files(self):
        """Create configuration files for the environment"""
        print(f"Creating configuration for {self.environment} environment...")
        
        # Create .env file
        env_file = self.project_root / '.env'
        env_content = self._get_env_content()
        
        with open(env_file, 'w') as f:
            f.write(env_content)
        
        print(f"✓ Environment file created: {env_file}")
        
        # Create API keys file for production
        if self.environment == 'production':
            api_keys_file = self.project_root / 'api_keys.txt'
            if not api_keys_file.exists():
                with open(api_keys_file, 'w') as f:
                    f.write("# Iron Chef API Keys\n")
                    f.write("# One key per line\n")
                    f.write("# Lines starting with # are comments\n\n")
                    f.write("# Add your API keys here\n")
                print(f"✓ API keys file created: {api_keys_file}")
    
    def _get_env_content(self):
        """Generate environment file content"""
        if self.environment == 'development':
            return """# Iron Chef API Development Configuration
FLASK_ENV=development
DEBUG=True
SECRET_KEY=iron-chef-dev-secret-key

# Database
DATABASE_PATH=iron_chef_recipes.db

# API Configuration
API_KEY_REQUIRED=False
CORS_ORIGINS=*

# Rate Limiting
RATELIMIT_STORAGE_URL=memory://

# Logging
LOG_LEVEL=DEBUG
"""
        
        elif self.environment == 'production':
            return """# Iron Chef API Production Configuration
FLASK_ENV=production
DEBUG=False
SECRET_KEY=CHANGE-THIS-IN-PRODUCTION

# Database
DATABASE_PATH=/var/lib/ironchef/iron_chef_recipes.db

# API Configuration
API_KEY_REQUIRED=True
CORS_ORIGINS=https://yourdomain.com

# Rate Limiting (use Redis in production)
REDIS_URL=redis://localhost:6379/1
RATELIMIT_STORAGE_URL=redis://localhost:6379/1

# Server Configuration
HOST=0.0.0.0
PORT=5000
API_BASE_URL=https://api.yourdomain.com

# Logging
LOG_LEVEL=WARNING
LOG_FILE=/var/log/ironchef/api.log
"""
        
        else:  # testing
            return """# Iron Chef API Testing Configuration
FLASK_ENV=testing
DEBUG=True
TESTING=True
SECRET_KEY=test-secret-key

# Database
DATABASE_PATH=:memory:

# API Configuration
API_KEY_REQUIRED=False
RATELIMIT_ENABLED=False

# Logging
LOG_LEVEL=DEBUG
"""
    
    def create_systemd_service(self):
        """Create systemd service file for production deployment"""
        if self.environment != 'production':
            return
        
        print("Creating systemd service file...")
        
        service_content = f"""[Unit]
Description=Iron Chef Recipe Database API
After=network.target

[Service]
Type=exec
User=ironchef
Group=ironchef
WorkingDirectory={self.project_root}
Environment=PATH={self.venv_path}/bin
EnvironmentFile={self.project_root}/.env
ExecStart={self.venv_path}/bin/python api_app.py
ExecReload=/bin/kill -HUP $MAINPID
RestartSec=1
Restart=always

# Security
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths={self.project_root} /var/lib/ironchef /var/log/ironchef

[Install]
WantedBy=multi-user.target
"""
        
        service_file = self.project_root / 'ironchef-api.service'
        with open(service_file, 'w') as f:
            f.write(service_content)
        
        print(f"✓ Systemd service file created: {service_file}")
        print("  To install: sudo cp ironchef-api.service /etc/systemd/system/")
        print("  To enable: sudo systemctl enable ironchef-api")
        print("  To start: sudo systemctl start ironchef-api")
    
    def create_nginx_config(self):
        """Create nginx configuration for production"""
        if self.environment != 'production':
            return
        
        print("Creating nginx configuration...")
        
        nginx_content = """server {
    listen 80;
    server_name api.yourdomain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;
    
    # SSL configuration
    ssl_certificate /path/to/your/cert.pem;
    ssl_certificate_key /path/to/your/private.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;
    
    # Proxy to Flask app
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeout settings
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
    
    # Static files (if needed)
    location /static/ {
        alias /path/to/static/files/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        proxy_pass http://127.0.0.1:5000/health;
    }
}
"""
        
        nginx_file = self.project_root / 'ironchef-api.nginx'
        with open(nginx_file, 'w') as f:
            f.write(nginx_content)
        
        print(f"✓ Nginx configuration created: {nginx_file}")
        print("  Update server_name and SSL certificate paths")
        print("  To install: sudo cp ironchef-api.nginx /etc/nginx/sites-available/")
        print("  To enable: sudo ln -s /etc/nginx/sites-available/ironchef-api.nginx /etc/nginx/sites-enabled/")
    
    def run_tests(self):
        """Run the test suite"""
        print("Running tests...")
        
        python_path = self.venv_path / ('Scripts' if os.name == 'nt' else 'bin') / 'python'
        
        try:
            result = subprocess.run([str(python_path), '-m', 'pytest', 'tests/', '-v'], 
                                  cwd=self.project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✓ All tests passed")
            else:
                print(f"⚠ Some tests failed:\n{result.stdout}\n{result.stderr}")
                
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to run tests: {e}")
    
    def deploy(self, skip_tests=False):
        """Run full deployment process"""
        print(f"Deploying Iron Chef API for {self.environment} environment...")
        print("=" * 60)
        
        self.check_python_version()
        self.create_virtual_environment()
        self.install_dependencies()
        self.setup_database()
        self.create_config_files()
        
        if self.environment == 'production':
            self.create_systemd_service()
            self.create_nginx_config()
        
        if not skip_tests:
            self.run_tests()
        
        print("=" * 60)
        print("✅ Deployment completed successfully!")
        print()
        
        if self.environment == 'development':
            print("To start the development server:")
            print(f"  source {self.venv_path}/bin/activate")
            print("  python api_app.py")
        elif self.environment == 'production':
            print("Production deployment notes:")
            print("1. Update the SECRET_KEY in .env file")
            print("2. Configure your database path")
            print("3. Add API keys to api_keys.txt")
            print("4. Install and configure nginx")
            print("5. Install systemd service")
            print("6. Start the service: sudo systemctl start ironchef-api")
        
        print()
        print("API Documentation will be available at:")
        print("  http://localhost:5000/api/docs")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Deploy Iron Chef Recipe Database API')
    parser.add_argument('environment', choices=['development', 'testing', 'production'],
                      help='Deployment environment')
    parser.add_argument('--skip-tests', action='store_true',
                      help='Skip running tests during deployment')
    
    args = parser.parse_args()
    
    deployer = APIDeployer(args.environment)
    deployer.deploy(skip_tests=args.skip_tests)


if __name__ == '__main__':
    main()