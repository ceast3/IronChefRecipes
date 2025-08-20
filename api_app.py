#!/usr/bin/env python3
"""
Production-ready Iron Chef Recipe Database API Application
Integrates the web interface with the RESTful API using proper configuration
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import HTTPException

from config import get_config, create_directories, add_security_headers, APIKeyManager
from api import create_api_app
from api_docs import add_docs_routes
from iron_chef_database_secure import IronChefDatabaseSecure


def create_app(config_name=None):
    """Application factory for creating Flask app with proper configuration"""
    
    # Get configuration
    config = get_config() if config_name is None else config_name
    
    # Create Flask app
    app = Flask(__name__)
    app.config.from_object(config)
    
    # Create necessary directories
    create_directories(config)
    
    # Configure logging
    configure_logging(app, config)
    
    # Initialize API key manager
    api_key_manager = APIKeyManager(config)
    app.api_key_manager = api_key_manager
    
    # Add proxy support for production deployment
    if not app.debug:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    
    # Initialize API
    try:
        api = create_api_app(app)
        app.logger.info("RESTful API initialized successfully")
    except Exception as e:
        app.logger.error(f"Failed to initialize API: {e}")
        raise
    
    # Add API documentation routes
    try:
        add_docs_routes(app)
        app.logger.info("API documentation routes added")
    except Exception as e:
        app.logger.error(f"Failed to add documentation routes: {e}")
    
    # Add security headers to all responses
    @app.after_request
    def apply_security_headers(response):
        return add_security_headers(response)
    
    # Global error handlers
    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        """Handle HTTP exceptions with consistent JSON response"""
        return jsonify({
            'success': False,
            'message': error.description,
            'errors': [error.description],
            'status_code': error.code
        }), error.code
    
    @app.errorhandler(Exception)
    def handle_general_exception(error):
        """Handle unexpected exceptions"""
        app.logger.error(f"Unhandled exception: {error}", exc_info=True)
        return jsonify({
            'success': False,
            'message': 'Internal server error',
            'errors': ['An unexpected error occurred']
        }), 500
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Application health check"""
        try:
            with IronChefDatabaseSecure() as db:
                db.cursor.execute("SELECT 1")
                db_status = True
        except Exception as e:
            app.logger.error(f"Database health check failed: {e}")
            db_status = False
        
        status = 'healthy' if db_status else 'unhealthy'
        status_code = 200 if db_status else 503
        
        return jsonify({
            'status': status,
            'database': db_status,
            'version': app.config['API_VERSION'],
            'environment': os.environ.get('FLASK_ENV', 'development')
        }), status_code
    
    # API information endpoint
    @app.route('/api')
    def api_info():
        """API information and links"""
        base_url = os.environ.get('API_BASE_URL', 'http://localhost:5000')
        
        return jsonify({
            'name': app.config['API_TITLE'],
            'version': app.config['API_VERSION'],
            'description': app.config['API_DESCRIPTION'],
            'documentation': {
                'swagger_ui': f'{base_url}/api/docs',
                'redoc': f'{base_url}/api/redoc',
                'openapi_spec': f'{base_url}/api/spec'
            },
            'endpoints': {
                'status': f'{base_url}/api/v1/status',
                'health': f'{base_url}/health',
                'episodes': f'{base_url}/api/v1/episodes',
                'episode_details': f'{base_url}/api/v1/episodes/{{id}}',
                'episode_dishes': f'{base_url}/api/v1/episodes/{{id}}/dishes',
                'recipe_generation': f'{base_url}/api/v1/recipes/generate',
                'recipe_details': f'{base_url}/api/v1/recipes/{{id}}',
                'search': f'{base_url}/api/v1/search',
                'themes': f'{base_url}/api/v1/themes',
                'chefs': f'{base_url}/api/v1/chefs'
            },
            'authentication': {
                'type': 'API Key (optional)' if not app.config.get('API_KEY_REQUIRED') else 'API Key (required)',
                'header': 'X-API-Key',
                'required': app.config.get('API_KEY_REQUIRED', False)
            },
            'rate_limits': {
                'default': app.config.get('RATELIMIT_DEFAULT'),
                'recipe_generation': app.config.get('RATELIMIT_RECIPE_GENERATION'),
                'search': app.config.get('RATELIMIT_SEARCH')
            },
            'features': [
                'RESTful API endpoints',
                'OpenAPI/Swagger documentation',
                'Rate limiting protection',
                'CORS support',
                'Request validation',
                'Comprehensive error handling',
                'Security headers',
                'Health checks'
            ]
        })
    
    # Initialize database
    try:
        with IronChefDatabaseSecure() as db:
            db.initialize_database()
        app.logger.info("Database initialized successfully")
    except Exception as e:
        app.logger.error(f"Database initialization failed: {e}")
        # Don't raise in production - let app start and handle gracefully
        if app.debug:
            raise
    
    return app


def configure_logging(app, config):
    """Configure application logging"""
    
    # Set log level
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    app.logger.setLevel(log_level)
    
    # Remove default handlers
    app.logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(config.LOG_FORMAT)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    app.logger.addHandler(console_handler)
    
    # File handler (if not testing)
    if not app.testing and config.LOG_FILE:
        try:
            file_handler = RotatingFileHandler(
                config.LOG_FILE,
                maxBytes=config.LOG_MAX_BYTES,
                backupCount=config.LOG_BACKUP_COUNT
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            app.logger.addHandler(file_handler)
        except (IOError, OSError) as e:
            app.logger.warning(f"Could not create log file {config.LOG_FILE}: {e}")
    
    # Set other loggers to warning level to reduce noise
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def main():
    """Main entry point for running the application"""
    
    # Create app
    app = create_app()
    
    # Get configuration
    config = app.config
    
    # Print startup information
    print("=" * 60)
    print("Iron Chef Recipe Database API")
    print("=" * 60)
    print(f"Environment: {os.environ.get('FLASK_ENV', 'development')}")
    print(f"Debug mode: {app.debug}")
    print(f"API version: {config['API_VERSION']}")
    print(f"Database: {config['DATABASE_PATH']}")
    print(f"API Key required: {config.get('API_KEY_REQUIRED', False)}")
    print("=" * 60)
    print("Available endpoints:")
    print(f"  • Web Interface: http://localhost:5000")
    print(f"  • API Root: http://localhost:5000/api")
    print(f"  • API Documentation: http://localhost:5000/api/docs")
    print(f"  • Health Check: http://localhost:5000/health")
    print("=" * 60)
    
    # Run the application
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    
    if app.debug:
        # Development server
        app.run(host=host, port=port, debug=True)
    else:
        # Production server (use gunicorn or similar in real production)
        print(f"Starting production server on {host}:{port}")
        print("Note: For production deployment, use a WSGI server like Gunicorn")
        app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == '__main__':
    main()