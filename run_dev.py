#!/usr/bin/env python3
"""
Development server runner for Iron Chef Recipe Database
Provides a convenient way to run the application in development mode
"""

import os
import sys
import logging
from pathlib import Path

def setup_development_environment():
    """Setup development environment variables and logging"""
    
    # Set development environment
    os.environ.setdefault('FLASK_ENV', 'development')
    os.environ.setdefault('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Setup logging for development
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('iron_chef_dev.log')
        ]
    )
    
    print("🔧 Development environment configured")
    print(f"📁 Working directory: {Path.cwd()}")
    print(f"📊 Database file: {'iron_chef_japan.db' if Path('iron_chef_japan.db').exists() else 'Not found - will be created'}")

def check_dependencies():
    """Check if required dependencies are installed"""
    required_modules = [
        'flask',
        'werkzeug',
        'jinja2'
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print(f"❌ Missing required modules: {', '.join(missing_modules)}")
        print("💡 Install them with: pip install -r requirements.txt")
        return False
    
    print("✅ All required dependencies are installed")
    return True

def initialize_database():
    """Initialize database if it doesn't exist or is empty"""
    try:
        from iron_chef_database_secure import IronChefDatabaseSecure
        
        with IronChefDatabaseSecure() as db:
            # Check if database has data
            db.cursor.execute("SELECT COUNT(*) FROM episodes")
            episode_count = db.cursor.fetchone()[0]
            
            if episode_count == 0:
                print("📊 Database is empty, loading sample data...")
                try:
                    # Try to load sample data
                    exec(open('sample_data_loader.py').read())
                    print("✅ Sample data loaded successfully")
                except FileNotFoundError:
                    print("⚠️  sample_data_loader.py not found - running with empty database")
                except Exception as e:
                    print(f"⚠️  Could not load sample data: {e}")
            else:
                print(f"✅ Database has {episode_count} episodes")
                
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        return False
    
    return True

def run_development_server():
    """Run the Flask development server"""
    try:
        from app import app
        
        print("\n🚀 Starting Iron Chef Recipe Database development server")
        print("📱 Access the application at: http://127.0.0.1:5000")
        print("🔍 API endpoints available at:")
        print("   - http://127.0.0.1:5000/api/themes")
        print("   - http://127.0.0.1:5000/api/stats")
        print("   - http://127.0.0.1:5000/api/dashboard-stats")
        print("\n⏹️  Press CTRL+C to stop the server\n")
        
        # Run with development settings
        app.run(
            host='127.0.0.1',
            port=5000,
            debug=True,
            use_reloader=True,
            use_debugger=True
        )
        
    except KeyboardInterrupt:
        print("\n🛑 Development server stopped")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

def main():
    """Main development server runner"""
    print("=" * 60)
    print("🍳 Iron Chef Recipe Database - Development Server")
    print("=" * 60)
    
    # Setup development environment
    setup_development_environment()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Initialize database
    if not initialize_database():
        print("⚠️  Continuing with database issues - some features may not work")
    
    # Run development server
    run_development_server()

if __name__ == '__main__':
    main()