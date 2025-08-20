#!/usr/bin/env python3
"""
Iron Chef Recipe Database Web Application
A secure, modern web interface for browsing episodes, dishes, and recipes
"""

import os
import json
import math
import logging
import atexit
from datetime import datetime
from flask import Flask, render_template, request, jsonify, abort, flash, redirect, url_for, send_file
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError
from iron_chef_database_secure import IronChefDatabaseSecure, SecurityValidator
from iron_chef_database_pooled import IronChefDatabasePooled, create_pooled_database
from recipe_exporter_secure import SecureRecipeExporter
from recipe_generator import RecipeGenerator
from api import create_api_app
from api_docs import add_docs_routes
from connection_pool import initialize_global_pool, shutdown_global_pool, PoolConfig
from pool_monitor import initialize_global_monitor, shutdown_global_monitor
from pool_config import initialize_config_manager, get_config, EnvironmentType
from shutdown_handler import setup_flask_shutdown, graceful_shutdown, get_shutdown_handler

# Initialize configuration management
config_manager = initialize_config_manager()
app_config = config_manager.get_application_config()
pool_config = config_manager.get_pool_config()
monitoring_config = config_manager.get_monitoring_config()
database_config = config_manager.get_database_config()

# Initialize Flask app with security configurations
app = Flask(__name__)
app.secret_key = app_config.secret_key

# Try to import and initialize CSRF protection (optional dependency)
try:
    from flask_wtf.csrf import CSRFProtect, validate_csrf
    if app_config.csrf_enabled:
        csrf = CSRFProtect(app)
        CSRF_ENABLED = True
    else:
        CSRF_ENABLED = False
        def validate_csrf(token):
            pass
except ImportError:
    CSRF_ENABLED = False
    def validate_csrf(token):
        pass  # No-op if CSRF not available

# Security configuration
app.config.update(
    SESSION_COOKIE_SECURE=app_config.environment == EnvironmentType.PRODUCTION,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=app_config.session_timeout,
    WTF_CSRF_TIME_LIMIT=7200,  # 2 hours for CSRF tokens
    WTF_CSRF_SSL_STRICT=app_config.environment == EnvironmentType.PRODUCTION,
    MAX_CONTENT_LENGTH=app_config.max_content_length,
)

# Configure logging based on config
log_level = getattr(logging, app_config.log_level.upper(), logging.INFO)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    handlers=[
        logging.FileHandler('iron_chef_app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize global connection pool
logger.info("Initializing connection pool...")
try:
    global_pool = initialize_global_pool(database_config.db_path, pool_config)
    logger.info(f"Connection pool initialized with {pool_config.min_connections}-{pool_config.max_connections} connections")
    
    # Initialize pool monitoring if enabled
    if monitoring_config.enable_monitoring:
        logger.info("Initializing pool monitoring...")
        global_monitor = initialize_global_monitor(
            pool=global_pool,
            collection_interval=monitoring_config.collection_interval,
            history_size=monitoring_config.history_size,
            enable_alerts=monitoring_config.enable_alerts
        )
        logger.info("Pool monitoring started")
    
except Exception as e:
    logger.error(f"Failed to initialize connection pool: {e}")
    logger.warning("Falling back to direct database connections")
    global_pool = None

# Initialize pooled database class
try:
    IronChefDatabasePooled.initialize_pool(database_config.db_path, pool_config)
    DATABASE_CLASS = IronChefDatabasePooled
    logger.info("Using pooled database connections")
except Exception as e:
    logger.warning(f"Failed to initialize pooled database class: {e}")
    logger.info("Using direct database connections")
    DATABASE_CLASS = IronChefDatabaseSecure

# Initialize security validator
validator = SecurityValidator()

# Setup graceful shutdown handling
shutdown_handler = setup_flask_shutdown(app, timeout=30.0)

# Constants
ITEMS_PER_PAGE = 12
MAX_SEARCH_LENGTH = 100

def validate_pagination_params(page=1, per_page=ITEMS_PER_PAGE):
    """Validate pagination parameters"""
    try:
        page = validator.validate_integer(page, min_val=1, max_val=10000, field_name="page")
        per_page = validator.validate_integer(per_page, min_val=1, max_val=100, field_name="per_page")
        return page, per_page
    except ValueError as e:
        raise BadRequest(str(e))

def paginate_results(results, page, per_page):
    """Paginate results and return pagination info"""
    total = len(results)
    start = (page - 1) * per_page
    end = start + per_page
    
    paginated_results = results[start:end]
    
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': math.ceil(total / per_page) if total > 0 else 1,
        'has_prev': page > 1,
        'has_next': end < total,
        'prev_num': page - 1 if page > 1 else None,
        'next_num': page + 1 if end < total else None
    }
    
    return paginated_results, pagination

@app.errorhandler(400)
def bad_request(error):
    """Handle bad request errors"""
    return render_template('error.html', 
                         error_code=400, 
                         error_message="Bad Request - Invalid input provided"), 400

@app.errorhandler(404)
def not_found(error):
    """Handle not found errors"""
    return render_template('error.html', 
                         error_code=404, 
                         error_message="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors"""
    return render_template('error.html', 
                         error_code=500, 
                         error_message="Internal server error"), 500

@app.route('/')
def index():
    """Homepage with featured episodes and recent recipes"""
    try:
        with DATABASE_CLASS() as db:
            # Get recent episodes
            db.cursor.execute("""
                SELECT e.*, ic.name as iron_chef_name, c.name as competitor_name
                FROM episodes e
                JOIN iron_chefs ic ON e.iron_chef_id = ic.id
                JOIN competitors c ON e.competitor_id = c.id
                ORDER BY e.episode_number DESC
                LIMIT 6
            """)
            recent_episodes = [dict(row) for row in db.cursor.fetchall()]
            
            # Get episode count
            db.cursor.execute("SELECT COUNT(*) FROM episodes")
            episode_count = db.cursor.fetchone()[0]
            
            # Get recipe count
            db.cursor.execute("SELECT COUNT(*) FROM recipes")
            recipe_count = db.cursor.fetchone()[0]
            
            # Get themes for quick access
            themes = db.get_all_themes()[:8]  # Limit to 8 themes
            
            return render_template('index.html', 
                                 recent_episodes=recent_episodes,
                                 episode_count=episode_count,
                                 recipe_count=recipe_count,
                                 themes=themes)
    except Exception as e:
        logger.error(f"Error loading homepage: {e}")
        abort(500)

@app.route('/episodes')
def episodes():
    """Browse all episodes with search and pagination"""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        page, per_page = validate_pagination_params(page)
        
        # Get search parameters
        search_theme = request.args.get('theme', '').strip()
        search_chef = request.args.get('chef', '').strip()
        
        # Validate search inputs
        if search_theme:
            search_theme = validator.validate_string(search_theme, max_length=MAX_SEARCH_LENGTH, field_name="theme search")
        if search_chef:
            search_chef = validator.validate_string(search_chef, max_length=MAX_SEARCH_LENGTH, field_name="chef search")
        
        with DATABASE_CLASS() as db:
            # Build query based on search parameters
            base_query = """
                SELECT e.*, ic.name as iron_chef_name, c.name as competitor_name
                FROM episodes e
                JOIN iron_chefs ic ON e.iron_chef_id = ic.id
                JOIN competitors c ON e.competitor_id = c.id
            """
            
            conditions = []
            params = []
            
            if search_theme:
                conditions.append("e.theme LIKE ? ESCAPE '\\'")
                params.append(validator.sanitize_sql_pattern(search_theme))
            
            if search_chef:
                conditions.append("(ic.name LIKE ? ESCAPE '\\' OR c.name LIKE ? ESCAPE '\\')")
                chef_pattern = validator.sanitize_sql_pattern(search_chef)
                params.extend([chef_pattern, chef_pattern])
            
            if conditions:
                base_query += " WHERE " + " AND ".join(conditions)
            
            base_query += " ORDER BY e.episode_number"
            
            db.cursor.execute(base_query, params)
            all_episodes = [dict(row) for row in db.cursor.fetchall()]
            
            # Apply pagination
            episodes_page, pagination = paginate_results(all_episodes, page, per_page)
            
            # Get all themes for filter dropdown
            all_themes = db.get_all_themes()
            
            return render_template('episodes.html', 
                                 episodes=episodes_page,
                                 pagination=pagination,
                                 all_themes=all_themes,
                                 search_theme=search_theme,
                                 search_chef=search_chef)
            
    except BadRequest:
        raise
    except Exception as e:
        logger.error(f"Error loading episodes: {e}")
        abort(500)

@app.route('/episode/<int:episode_id>')
def episode_detail(episode_id):
    """Show detailed episode information with dishes"""
    try:
        episode_id = validator.validate_integer(episode_id, min_val=1, field_name="episode ID")
        
        with DATABASE_CLASS() as db:
            episode = db.get_episode_details(episode_id)
            
            if not episode:
                abort(404)
            
            return render_template('episode_detail.html', episode=episode)
            
    except BadRequest:
        raise
    except Exception as e:
        logger.error(f"Error loading episode {episode_id}: {e}")
        abort(500)

@app.route('/recipes')
def recipes():
    """Browse all recipes with search and pagination"""
    try:
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        page, per_page = validate_pagination_params(page)
        
        # Get search parameters
        search_dish = request.args.get('dish', '').strip()
        search_ingredient = request.args.get('ingredient', '').strip()
        
        # Validate search inputs
        if search_dish:
            search_dish = validator.validate_string(search_dish, max_length=MAX_SEARCH_LENGTH, field_name="dish search")
        if search_ingredient:
            search_ingredient = validator.validate_string(search_ingredient, max_length=MAX_SEARCH_LENGTH, field_name="ingredient search")
        
        with DATABASE_CLASS() as db:
            # Build query based on search parameters
            base_query = """
                SELECT r.*, d.dish_name, d.chef_type, e.theme, e.episode_number,
                       ic.name as iron_chef_name, c.name as competitor_name
                FROM recipes r
                JOIN dishes d ON r.dish_id = d.id
                JOIN episodes e ON d.episode_id = e.id
                JOIN iron_chefs ic ON e.iron_chef_id = ic.id
                JOIN competitors c ON e.competitor_id = c.id
            """
            
            conditions = []
            params = []
            
            if search_dish:
                conditions.append("d.dish_name LIKE ? ESCAPE '\\'")
                params.append(validator.sanitize_sql_pattern(search_dish))
            
            if search_ingredient:
                conditions.append("r.ingredients LIKE ? ESCAPE '\\'")
                params.append(validator.sanitize_sql_pattern(search_ingredient))
            
            if conditions:
                base_query += " WHERE " + " AND ".join(conditions)
            
            base_query += " ORDER BY e.episode_number, d.chef_type, d.dish_number"
            
            db.cursor.execute(base_query, params)
            all_recipes = [dict(row) for row in db.cursor.fetchall()]
            
            # Parse JSON ingredients for display
            for recipe in all_recipes:
                try:
                    recipe['ingredients_parsed'] = json.loads(recipe['ingredients'])
                    recipe['instructions_parsed'] = json.loads(recipe['instructions'])
                except json.JSONDecodeError:
                    recipe['ingredients_parsed'] = []
                    recipe['instructions_parsed'] = []
            
            # Apply pagination
            recipes_page, pagination = paginate_results(all_recipes, page, per_page)
            
            return render_template('recipes.html', 
                                 recipes=recipes_page,
                                 pagination=pagination,
                                 search_dish=search_dish,
                                 search_ingredient=search_ingredient)
            
    except BadRequest:
        raise
    except Exception as e:
        logger.error(f"Error loading recipes: {e}")
        abort(500)

@app.route('/recipe/<int:recipe_id>')
def recipe_detail(recipe_id):
    """Show detailed recipe information"""
    try:
        recipe_id = validator.validate_integer(recipe_id, min_val=1, field_name="recipe ID")
        
        with DATABASE_CLASS() as db:
            db.cursor.execute("""
                SELECT r.*, d.dish_name, d.description, d.chef_type, 
                       e.theme, e.episode_number, e.air_date,
                       ic.name as iron_chef_name, c.name as competitor_name
                FROM recipes r
                JOIN dishes d ON r.dish_id = d.id
                JOIN episodes e ON d.episode_id = e.id
                JOIN iron_chefs ic ON e.iron_chef_id = ic.id
                JOIN competitors c ON e.competitor_id = c.id
                WHERE r.id = ?
            """, (recipe_id,))
            
            result = db.cursor.fetchone()
            if not result:
                abort(404)
            
            recipe = dict(result)
            
            # Parse JSON data
            try:
                recipe['ingredients_parsed'] = json.loads(recipe['ingredients'])
                recipe['instructions_parsed'] = json.loads(recipe['instructions'])
            except json.JSONDecodeError:
                recipe['ingredients_parsed'] = []
                recipe['instructions_parsed'] = []
            
            return render_template('recipe_detail.html', recipe=recipe)
            
    except BadRequest:
        raise
    except Exception as e:
        logger.error(f"Error loading recipe {recipe_id}: {e}")
        abort(500)

@app.route('/recipe/<int:recipe_id>/print')
def recipe_print(recipe_id):
    """Print-friendly version of recipe"""
    try:
        recipe_id = validator.validate_integer(recipe_id, min_val=1, field_name="recipe ID")
        
        with DATABASE_CLASS() as db:
            db.cursor.execute("""
                SELECT r.*, d.dish_name, d.description, d.chef_type, 
                       e.theme, e.episode_number, e.air_date,
                       ic.name as iron_chef_name, c.name as competitor_name
                FROM recipes r
                JOIN dishes d ON r.dish_id = d.id
                JOIN episodes e ON d.episode_id = e.id
                JOIN iron_chefs ic ON e.iron_chef_id = ic.id
                JOIN competitors c ON e.competitor_id = c.id
                WHERE r.id = ?
            """, (recipe_id,))
            
            result = db.cursor.fetchone()
            if not result:
                abort(404)
            
            recipe = dict(result)
            
            # Parse JSON data
            try:
                recipe['ingredients_parsed'] = json.loads(recipe['ingredients'])
                recipe['instructions_parsed'] = json.loads(recipe['instructions'])
            except json.JSONDecodeError:
                recipe['ingredients_parsed'] = []
                recipe['instructions_parsed'] = []
            
            return render_template('recipe_print.html', recipe=recipe)
            
    except BadRequest:
        raise
    except Exception as e:
        logger.error(f"Error loading recipe for print {recipe_id}: {e}")
        abort(500)

@app.route('/search')
def search():
    """Global search across episodes, dishes, and recipes"""
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return render_template('search.html', results=None, query='')
        
        # Validate search query
        query = validator.validate_string(query, max_length=MAX_SEARCH_LENGTH, field_name="search query")
        
        with DATABASE_CLASS() as db:
            search_pattern = validator.sanitize_sql_pattern(query)
            
            # Search episodes
            db.cursor.execute("""
                SELECT 'episode' as type, e.id, e.episode_number, e.theme, 
                       ic.name as iron_chef_name, c.name as competitor_name,
                       e.theme as title, '' as description
                FROM episodes e
                JOIN iron_chefs ic ON e.iron_chef_id = ic.id
                JOIN competitors c ON e.competitor_id = c.id
                WHERE e.theme LIKE ? ESCAPE '\\'
                   OR ic.name LIKE ? ESCAPE '\\'
                   OR c.name LIKE ? ESCAPE '\\'
            """, (search_pattern, search_pattern, search_pattern))
            episodes = [dict(row) for row in db.cursor.fetchall()]
            
            # Search dishes
            db.cursor.execute("""
                SELECT 'dish' as type, d.id, d.dish_name as title, d.description,
                       e.episode_number, e.theme, d.chef_type
                FROM dishes d
                JOIN episodes e ON d.episode_id = e.id
                WHERE d.dish_name LIKE ? ESCAPE '\\'
                   OR d.description LIKE ? ESCAPE '\\'
                   OR d.main_ingredients LIKE ? ESCAPE '\\'
            """, (search_pattern, search_pattern, search_pattern))
            dishes = [dict(row) for row in db.cursor.fetchall()]
            
            # Search recipes
            db.cursor.execute("""
                SELECT 'recipe' as type, r.id, r.recipe_title as title, 
                       d.dish_name as description, e.episode_number, e.theme
                FROM recipes r
                JOIN dishes d ON r.dish_id = d.id
                JOIN episodes e ON d.episode_id = e.id
                WHERE r.recipe_title LIKE ? ESCAPE '\\'
                   OR r.ingredients LIKE ? ESCAPE '\\'
                   OR r.instructions LIKE ? ESCAPE '\\'
            """, (search_pattern, search_pattern, search_pattern))
            recipes = [dict(row) for row in db.cursor.fetchall()]
            
            results = {
                'episodes': episodes,
                'dishes': dishes,
                'recipes': recipes,
                'total': len(episodes) + len(dishes) + len(recipes)
            }
            
            return render_template('search.html', results=results, query=query)
            
    except BadRequest:
        raise
    except Exception as e:
        logger.error(f"Error in search: {e}")
        abort(500)

@app.route('/generate-recipe/<int:dish_id>', methods=['POST'])
def generate_recipe(dish_id):
    """Generate a recipe for a specific dish"""
    # Validate CSRF token if enabled
    if CSRF_ENABLED:
        try:
            validate_csrf(request.form.get('csrf_token'))
        except Exception:
            flash('Security validation failed. Please try again.', 'error')
            return redirect(request.referrer or url_for('index'))
    try:
        dish_id = validator.validate_integer(dish_id, min_val=1, field_name="dish ID")
        
        # Check if recipe already exists
        with DATABASE_CLASS() as db:
            db.cursor.execute("SELECT id FROM recipes WHERE dish_id = ?", (dish_id,))
            existing_recipe = db.cursor.fetchone()
            
            if existing_recipe:
                flash('Recipe already exists for this dish!', 'info')
                return redirect(url_for('recipe_detail', recipe_id=existing_recipe[0]))
            
            # Get dish details
            db.cursor.execute("SELECT * FROM dishes WHERE id = ?", (dish_id,))
            dish = db.cursor.fetchone()
            
            if not dish:
                abort(404)
            
            dish_data = dict(dish)
        
        # Generate recipe using the recipe generator
        generator = RecipeGenerator()
        recipe_data = generator.generate_recipe_for_dish(dish_data)
        
        # Save recipe to database
        with DATABASE_CLASS() as db:
            recipe_id = db.add_recipe(
                dish_id=dish_id,
                recipe_title=recipe_data['title'],
                ingredients=json.dumps(recipe_data['ingredients']),
                instructions=json.dumps(recipe_data['instructions']),
                prep_time=recipe_data.get('prep_time'),
                cook_time=recipe_data.get('cook_time'),
                servings=recipe_data.get('servings', 4)
            )
        
        flash('Recipe generated successfully!', 'success')
        return redirect(url_for('recipe_detail', recipe_id=recipe_id))
        
    except BadRequest:
        raise
    except Exception as e:
        logger.error(f"Error generating recipe for dish {dish_id}: {e}")
        flash('Error generating recipe. Please try again.', 'error')
        return redirect(url_for('episode_detail', episode_id=request.form.get('episode_id', 1)))

@app.route('/export/<export_type>')
def export_data(export_type):
    """Export data in various formats"""
    try:
        # Validate export type
        if export_type not in ['episodes', 'recipes', 'theme']:
            abort(404)
        
        # Get format and other parameters
        format_type = request.args.get('format', 'json')
        if format_type not in ['json', 'csv', 'txt']:
            raise BadRequest("Invalid format")
        
        exporter = SecureRecipeExporter()
        
        if export_type == 'episodes':
            filepath = exporter.export_episode_summary(format_type)
        elif export_type == 'recipes':
            filepath = exporter.export_all_recipes(format_type)
        elif export_type == 'theme':
            theme = request.args.get('theme')
            if not theme:
                raise BadRequest("Theme parameter required")
            theme = validator.validate_string(theme, max_length=100, field_name="theme")
            filepath = exporter.export_dishes_by_theme(theme, format_type)
        
        return send_file(filepath, as_attachment=True)
        
    except BadRequest:
        raise
    except Exception as e:
        logger.error(f"Error exporting {export_type}: {e}")
        abort(500)

@app.route('/api/dashboard-stats')
def api_dashboard_stats():
    """API endpoint for enhanced dashboard statistics"""
    try:
        with DATABASE_CLASS() as db:
            # Get comprehensive stats
            stats = {}
            
            # Basic counts
            db.cursor.execute("SELECT COUNT(*) FROM episodes")
            stats['episodes'] = db.cursor.fetchone()[0]
            
            db.cursor.execute("SELECT COUNT(*) FROM recipes")
            stats['recipes'] = db.cursor.fetchone()[0]
            
            db.cursor.execute("SELECT COUNT(*) FROM dishes")
            stats['dishes'] = db.cursor.fetchone()[0]
            
            db.cursor.execute("SELECT COUNT(DISTINCT iron_chef_id) FROM episodes")
            stats['iron_chefs'] = db.cursor.fetchone()[0]
            
            # Winner distribution
            db.cursor.execute("""
                SELECT winner, COUNT(*) as count 
                FROM episodes 
                WHERE winner IS NOT NULL
                GROUP BY winner
            """)
            stats['winners'] = [{'winner': row[0], 'count': row[1]} for row in db.cursor.fetchall()]
            
            # Most popular themes
            db.cursor.execute("""
                SELECT theme, COUNT(*) as count 
                FROM episodes 
                GROUP BY theme 
                ORDER BY count DESC 
                LIMIT 5
            """)
            stats['popular_themes'] = [{'theme': row[0], 'count': row[1]} for row in db.cursor.fetchall()]
            
            # Recent activity
            db.cursor.execute("""
                SELECT COUNT(*) 
                FROM recipes 
                WHERE date(generated_date) = date('now')
            """)
            stats['recipes_today'] = db.cursor.fetchone()[0]
            
            return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        return jsonify({'error': 'Failed to load statistics'}), 500

@app.route('/api/themes')
def api_themes():
    """API endpoint to get all themes"""
    try:
        with DATABASE_CLASS() as db:
            themes = db.get_all_themes()
            return jsonify({'themes': themes})
    except Exception as e:
        logger.error(f"Error getting themes: {e}")
        return jsonify({'error': 'Failed to load themes'}), 500

@app.route('/api/stats')
def api_stats():
    """API endpoint for dashboard statistics"""
    try:
        with DATABASE_CLASS() as db:
            # Get counts
            db.cursor.execute("SELECT COUNT(*) FROM episodes")
            episode_count = db.cursor.fetchone()[0]
            
            db.cursor.execute("SELECT COUNT(*) FROM recipes")
            recipe_count = db.cursor.fetchone()[0]
            
            db.cursor.execute("SELECT COUNT(*) FROM dishes")
            dish_count = db.cursor.fetchone()[0]
            
            # Get theme distribution
            db.cursor.execute("""
                SELECT theme, COUNT(*) as count 
                FROM episodes 
                GROUP BY theme 
                ORDER BY count DESC 
                LIMIT 10
            """)
            theme_stats = [{'theme': row[0], 'count': row[1]} for row in db.cursor.fetchall()]
            
            return jsonify({
                'episodes': episode_count,
                'recipes': recipe_count,
                'dishes': dish_count,
                'theme_distribution': theme_stats
            })
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': 'Failed to load statistics'}), 500

@app.route('/api/pool/status')
def api_pool_status():
    """API endpoint for connection pool status"""
    try:
        if DATABASE_CLASS == IronChefDatabasePooled:
            pool_status = IronChefDatabasePooled.get_pool_status()
            pool_stats = IronChefDatabasePooled.get_pool_statistics()
            
            return jsonify({
                'pooling_enabled': True,
                'status': pool_status,
                'statistics': pool_stats
            })
        else:
            return jsonify({
                'pooling_enabled': False,
                'message': 'Connection pooling not active'
            })
    except Exception as e:
        logger.error(f"Error getting pool status: {e}")
        return jsonify({'error': 'Failed to load pool status'}), 500

@app.route('/api/pool/health')
def api_pool_health():
    """API endpoint for connection pool health"""
    try:
        from pool_monitor import get_global_monitor
        
        monitor = get_global_monitor()
        if monitor:
            health_status = monitor.get_health_status()
            current_metrics = monitor.get_current_metrics()
            active_alerts = monitor.get_active_alerts()
            
            return jsonify({
                'monitoring_enabled': True,
                'health_status': health_status.__dict__ if health_status else None,
                'current_metrics': current_metrics.__dict__ if current_metrics else None,
                'active_alerts': [alert.__dict__ for alert in active_alerts],
                'alert_count': len(active_alerts)
            })
        else:
            return jsonify({
                'monitoring_enabled': False,
                'message': 'Pool monitoring not active'
            })
    except Exception as e:
        logger.error(f"Error getting pool health: {e}")
        return jsonify({'error': 'Failed to load pool health'}), 500

@app.route('/api/pool/performance')
def api_pool_performance():
    """API endpoint for connection pool performance metrics"""
    try:
        from pool_monitor import get_global_monitor
        from datetime import timedelta
        
        monitor = get_global_monitor()
        if monitor:
            # Get performance summary for different time periods
            duration_param = request.args.get('duration', '1h')
            
            duration_map = {
                '5m': timedelta(minutes=5),
                '15m': timedelta(minutes=15),
                '1h': timedelta(hours=1),
                '24h': timedelta(hours=24)
            }
            
            duration = duration_map.get(duration_param, timedelta(hours=1))
            
            performance_summary = monitor.get_performance_summary(duration)
            metrics_history = monitor.get_metrics_history(duration)
            
            return jsonify({
                'monitoring_enabled': True,
                'duration': duration_param,
                'performance_summary': performance_summary,
                'metrics_count': len(metrics_history),
                'latest_metrics': metrics_history[-1].__dict__ if metrics_history else None
            })
        else:
            return jsonify({
                'monitoring_enabled': False,
                'message': 'Pool monitoring not active'
            })
    except Exception as e:
        logger.error(f"Error getting pool performance: {e}")
        return jsonify({'error': 'Failed to load pool performance'}), 500

if __name__ == '__main__':
    # Create database if it doesn't exist
    try:
        with DATABASE_CLASS() as db:
            db.initialize_database()
        print("Database initialized successfully")
        if DATABASE_CLASS == IronChefDatabasePooled:
            print(f"Using pooled connections ({pool_config.min_connections}-{pool_config.max_connections})")
        else:
            print("Using direct connections")
    except Exception as e:
        print(f"Database initialization error: {e}")
    
    # Initialize API
    api = create_api_app(app)
    print("RESTful API initialized successfully")
    
    # Add API documentation routes
    add_docs_routes(app)
    print("API documentation routes added")
    
    # Add API info route
    @app.route('/api')
    def api_info():
        """API information and links"""
        return jsonify({
            'name': 'Iron Chef Recipe Database API',
            'version': 'v1',
            'description': 'RESTful API for accessing Iron Chef episodes, dishes, and recipes',
            'documentation': {
                'swagger_ui': '/api/docs',
                'redoc': '/api/redoc',
                'openapi_spec': '/api/spec'
            },
            'endpoints': {
                'status': '/api/v1/status',
                'episodes': '/api/v1/episodes',
                'episode_details': '/api/v1/episodes/{id}',
                'episode_dishes': '/api/v1/episodes/{id}/dishes',
                'recipe_generation': '/api/v1/recipes/generate',
                'recipe_details': '/api/v1/recipes/{id}',
                'search': '/api/v1/search',
                'themes': '/api/v1/themes',
                'chefs': '/api/v1/chefs'
            },
            'pool_monitoring': {
                'status': '/api/pool/status',
                'health': '/api/pool/health',
                'performance': '/api/pool/performance'
            },
            'authentication': 'Optional API key via X-API-Key header',
            'rate_limits': {
                'default': '200 per hour, 50 per minute',
                'recipe_generation': '10 per minute',
                'search': '20 per minute'
            },
            'pooling': {
                'enabled': DATABASE_CLASS == IronChefDatabasePooled,
                'monitoring': monitoring_config.enable_monitoring if monitoring_config else False
            }
        })
    
    print("Starting Iron Chef Recipe Database with Connection Pooling...")
    print(f"Environment: {app_config.environment.value}")
    print(f"Web Interface: http://{app_config.flask_host}:{app_config.flask_port}")
    print(f"API Documentation: http://{app_config.flask_host}:{app_config.flask_port}/api/docs")
    print(f"API Info: http://{app_config.flask_host}:{app_config.flask_port}/api")
    
    if DATABASE_CLASS == IronChefDatabasePooled:
        print(f"Pool Monitoring: http://{app_config.flask_host}:{app_config.flask_port}/api/pool/status")
    
    # Signal handlers are automatically registered by shutdown_handler
    
    # Run application
    try:
        app.run(
            debug=app_config.debug,
            host=app_config.flask_host,
            port=app_config.flask_port,
            threaded=app_config.flask_threaded
        )
    except KeyboardInterrupt:
        print("\nApplication stopped by user")
        graceful_shutdown()
    except Exception as e:
        print(f"Application error: {e}")
        graceful_shutdown()
    finally:
        # Graceful shutdown is handled by shutdown_handler
        print("Application terminated")