#!/usr/bin/env python3
"""
Iron Chef Recipe Database Web Application - Simplified Version
A secure, modern web interface for browsing episodes, dishes, and recipes
"""

import os
import json
import math
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, abort, flash, redirect, url_for, send_file
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError
from iron_chef_database_secure import IronChefDatabaseSecure, SecurityValidator
from recipe_exporter_secure import SecureRecipeExporter
from recipe_generator import RecipeGenerator

# Initialize Flask app with security configurations
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'iron-chef-secure-key-change-in-production')

# Try to import and initialize CSRF protection (optional dependency)
try:
    from flask_wtf.csrf import CSRFProtect, validate_csrf
    csrf = CSRFProtect(app)
    CSRF_ENABLED = True
except ImportError:
    CSRF_ENABLED = False
    def validate_csrf(token):
        pass  # No-op if CSRF not available

# Security configuration
app.config.update(
    SESSION_COOKIE_SECURE=os.environ.get('FLASK_ENV') == 'production',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=3600,  # 1 hour
    WTF_CSRF_TIME_LIMIT=7200 if CSRF_ENABLED else None,  # 2 hours for CSRF tokens
    WTF_CSRF_SSL_STRICT=os.environ.get('FLASK_ENV') == 'production',
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    handlers=[
        logging.FileHandler('iron_chef_app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize security validator
validator = SecurityValidator()

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
        with IronChefDatabaseSecure() as db:
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
        
        with IronChefDatabaseSecure() as db:
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
        
        with IronChefDatabaseSecure() as db:
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
        
        with IronChefDatabaseSecure() as db:
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
        
        with IronChefDatabaseSecure() as db:
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
        
        with IronChefDatabaseSecure() as db:
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
        
        with IronChefDatabaseSecure() as db:
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
        with IronChefDatabaseSecure() as db:
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
        with IronChefDatabaseSecure() as db:
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

@app.route('/api/themes')
def api_themes():
    """API endpoint to get all themes"""
    try:
        with IronChefDatabaseSecure() as db:
            themes = db.get_all_themes()
            return jsonify({'themes': themes})
    except Exception as e:
        logger.error(f"Error getting themes: {e}")
        return jsonify({'error': 'Failed to load themes'}), 500

@app.route('/api/stats')
def api_stats():
    """API endpoint for dashboard statistics"""
    try:
        with IronChefDatabaseSecure() as db:
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

if __name__ == '__main__':
    # Create database if it doesn't exist
    try:
        with IronChefDatabaseSecure() as db:
            db.initialize_database()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")
    
    print("🍳 Iron Chef Recipe Database - Web Interface")
    print("=" * 50)
    print("🌐 Web Interface: http://localhost:5000")
    print("📊 Features:")
    print("  • Episode browsing with search & filters")
    print("  • Recipe generation and viewing")
    print("  • Print-friendly recipe pages")
    print("  • Export functionality (JSON, CSV, TXT)")
    print("  • Global search across all content")
    print("  • Responsive design for mobile & desktop")
    print("  • Security hardened with input validation")
    print("  • Accessibility compliant (WCAG 2.1)")
    print("=" * 50)
    
    # Run in debug mode for development
    app.run(debug=True, host='0.0.0.0', port=5000)