#!/usr/bin/env python3
"""
Configuration settings for Iron Chef Recipe Database API
Handles development, testing, and production configurations
"""

import os
from datetime import timedelta


class Config:
    """Base configuration class"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'iron-chef-secure-key-change-in-production'
    DEBUG = False
    TESTING = False
    
    # Database settings
    DATABASE_PATH = os.environ.get('DATABASE_PATH', 'iron_chef_recipes.db')
    
    # API settings
    API_VERSION = 'v1'
    API_TITLE = 'Iron Chef Recipe Database API'
    API_DESCRIPTION = 'RESTful API for accessing Iron Chef episodes, dishes, and recipes'
    
    # Security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)
    WTF_CSRF_TIME_LIMIT = 7200  # 2 hours
    WTF_CSRF_SSL_STRICT = True
    
    # Rate limiting settings
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'memory://')
    RATELIMIT_DEFAULT = '200 per hour, 50 per minute'
    RATELIMIT_RECIPE_GENERATION = '10 per minute'
    RATELIMIT_SEARCH = '20 per minute'
    RATELIMIT_EPISODES = '30 per minute'
    RATELIMIT_RECIPES = '60 per minute'
    RATELIMIT_REFERENCE = '100 per minute'
    
    # CORS settings
    CORS_ORIGINS = ['*']
    CORS_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
    CORS_ALLOW_HEADERS = ['Content-Type', 'Authorization', 'X-API-Key']
    
    # API Key settings
    API_KEY_REQUIRED = False  # Set to True in production
    API_KEYS_FILE = os.environ.get('API_KEYS_FILE', 'api_keys.txt')
    
    # Pagination settings
    DEFAULT_PER_PAGE = 12
    MAX_PER_PAGE = 100
    MAX_PAGE = 10000
    
    # Validation settings
    MAX_SEARCH_LENGTH = 100
    MAX_RECIPE_TITLE_LENGTH = 200
    MAX_INGREDIENT_LENGTH = 500
    MAX_DESCRIPTION_LENGTH = 1000
    
    # Request size limits
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # Logging settings
    LOG_LEVEL = 'INFO'
    LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s [%(pathname)s:%(lineno)d] %(message)s'
    LOG_FILE = 'iron_chef_api.log'
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5
    
    # Cache settings
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes
    
    # Performance settings
    JSONIFY_PRETTYPRINT_REGULAR = False  # Compact JSON in production


class DevelopmentConfig(Config):
    """Development configuration"""
    
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_SSL_STRICT = False
    
    # Relaxed rate limits for development
    RATELIMIT_DEFAULT = '1000 per hour, 100 per minute'
    RATELIMIT_RECIPE_GENERATION = '50 per minute'
    RATELIMIT_SEARCH = '100 per minute'
    
    # Enable pretty-printed JSON for debugging
    JSONIFY_PRETTYPRINT_REGULAR = True
    
    # Development-specific logging
    LOG_LEVEL = 'DEBUG'


class TestingConfig(Config):
    """Testing configuration"""
    
    TESTING = True
    DEBUG = True
    
    # Use in-memory database for testing
    DATABASE_PATH = ':memory:'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Disable rate limiting for testing
    RATELIMIT_ENABLED = False
    
    # Use memory storage for rate limiting in tests
    RATELIMIT_STORAGE_URL = 'memory://'
    
    # Relaxed security for testing
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_SSL_STRICT = False
    
    # Faster timeouts for testing
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=5)
    
    # Disable API key requirement for testing
    API_KEY_REQUIRED = False


class ProductionConfig(Config):
    """Production configuration"""
    
    DEBUG = False
    TESTING = False
    
    # Enforce API key requirement in production
    API_KEY_REQUIRED = True
    
    # Strict security settings
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_SSL_STRICT = True
    
    # Production rate limits
    RATELIMIT_DEFAULT = '200 per hour, 50 per minute'
    RATELIMIT_RECIPE_GENERATION = '10 per minute'
    RATELIMIT_SEARCH = '20 per minute'
    
    # Restrict CORS origins in production
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    
    # Production database
    DATABASE_PATH = os.environ.get('DATABASE_PATH', '/var/lib/ironchef/iron_chef_recipes.db')
    
    # Use Redis for rate limiting in production
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/1')
    
    # Production logging
    LOG_LEVEL = 'WARNING'
    LOG_FILE = '/var/log/ironchef/api.log'
    
    # Performance optimizations
    JSONIFY_PRETTYPRINT_REGULAR = False


class APIKeyManager:
    """Manages API key validation and storage"""
    
    def __init__(self, config):
        self.config = config
        self.api_keys = self._load_api_keys()
    
    def _load_api_keys(self):
        """Load API keys from file or environment"""
        api_keys = set()
        
        # Load from environment variable
        env_keys = os.environ.get('API_KEYS', '')
        if env_keys:
            api_keys.update(key.strip() for key in env_keys.split(',') if key.strip())
        
        # Load from file
        if os.path.exists(self.config.API_KEYS_FILE):
            try:
                with open(self.config.API_KEYS_FILE, 'r') as f:
                    for line in f:
                        key = line.strip()
                        if key and not key.startswith('#'):
                            api_keys.add(key)
            except IOError:
                pass
        
        return api_keys
    
    def is_valid_key(self, api_key):
        """Validate an API key"""
        if not self.config.API_KEY_REQUIRED:
            return True
        
        return api_key in self.api_keys
    
    def add_key(self, api_key):
        """Add a new API key"""
        self.api_keys.add(api_key)
        self._save_api_keys()
    
    def remove_key(self, api_key):
        """Remove an API key"""
        self.api_keys.discard(api_key)
        self._save_api_keys()
    
    def _save_api_keys(self):
        """Save API keys to file"""
        try:
            with open(self.config.API_KEYS_FILE, 'w') as f:
                f.write("# Iron Chef API Keys\n")
                f.write("# One key per line\n")
                f.write("# Lines starting with # are comments\n\n")
                for key in sorted(self.api_keys):
                    f.write(f"{key}\n")
        except IOError:
            pass


def get_config():
    """Get configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'development').lower()
    
    if env == 'production':
        return ProductionConfig()
    elif env == 'testing':
        return TestingConfig()
    else:
        return DevelopmentConfig()


def create_directories(config):
    """Create necessary directories for the application"""
    directories = []
    
    # Extract directory paths from config
    if hasattr(config, 'DATABASE_PATH') and config.DATABASE_PATH != ':memory:':
        directories.append(os.path.dirname(config.DATABASE_PATH))
    
    if hasattr(config, 'LOG_FILE'):
        directories.append(os.path.dirname(config.LOG_FILE))
    
    # Create directories
    for directory in directories:
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, mode=0o755)
            except OSError:
                pass


# Security headers middleware
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


if __name__ == '__main__':
    # Test configuration loading
    config = get_config()
    print(f"Configuration: {config.__class__.__name__}")
    print(f"Debug mode: {config.DEBUG}")
    print(f"API Key required: {config.API_KEY_REQUIRED}")
    print(f"Database path: {config.DATABASE_PATH}")
    print(f"Rate limit: {config.RATELIMIT_DEFAULT}")