#!/usr/bin/env python3
"""
Iron Chef Recipe Database RESTful API
A comprehensive API for third-party integration
"""

import json
import logging
import os
from datetime import datetime
from functools import wraps
from typing import Dict, List, Optional, Any

from flask import Flask, request, jsonify, g
from flask_restful import Api, Resource, reqparse
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from marshmallow import Schema, fields, ValidationError, validate
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec_webframeworks.flask import FlaskPlugin
from werkzeug.exceptions import BadRequest, NotFound, Unauthorized, TooManyRequests

from iron_chef_database_secure import IronChefDatabaseSecure, SecurityValidator
from recipe_generator import RecipeGenerator
from recipe_exporter_secure import SecureRecipeExporter
from api_auth import require_api_key, add_rate_limit_headers, APIKeyManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

# API Configuration
API_VERSION = "v1"
API_TITLE = "Iron Chef Recipe Database API"
API_DESCRIPTION = "RESTful API for accessing Iron Chef episodes, dishes, and recipes"

class APIError(Exception):
    """Custom API exception with status code and message"""
    def __init__(self, message: str, status_code: int = 400, payload: Dict = None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.payload = payload

# Marshmallow Schemas for request/response validation
class PaginationSchema(Schema):
    page = fields.Int(load_default=1, validate=validate.Range(min=1, max=10000))
    per_page = fields.Int(load_default=12, validate=validate.Range(min=1, max=100))

class EpisodeFilterSchema(PaginationSchema):
    theme = fields.Str(load_default=None, validate=validate.Length(max=100), allow_none=True)
    chef = fields.Str(load_default=None, validate=validate.Length(max=100), allow_none=True)
    iron_chef_id = fields.Int(load_default=None, validate=validate.Range(min=1), allow_none=True)
    competitor_id = fields.Int(load_default=None, validate=validate.Range(min=1), allow_none=True)
    air_date_from = fields.Date(load_default=None, allow_none=True)
    air_date_to = fields.Date(load_default=None, allow_none=True)

class SearchSchema(PaginationSchema):
    q = fields.Str(required=True, validate=validate.Length(min=1, max=100))

class RecipeGenerationSchema(Schema):
    dish_id = fields.Int(required=True, validate=validate.Range(min=1))
    chef_style = fields.Str(load_default="traditional", validate=validate.OneOf([
        "traditional", "modern", "fusion", "molecular"
    ]))
    difficulty = fields.Str(load_default="medium", validate=validate.OneOf([
        "easy", "medium", "hard", "expert"
    ]))
    dietary_restrictions = fields.List(fields.Str(), load_default=[])

# Response Schemas
class IronChefSchema(Schema):
    id = fields.Int()
    name = fields.Str()
    title = fields.Str()
    specialty = fields.Str()
    active_years = fields.Str()

class CompetitorSchema(Schema):
    id = fields.Int()
    name = fields.Str()
    restaurant = fields.Str()
    specialty = fields.Str()
    location = fields.Str()

class EpisodeSchema(Schema):
    id = fields.Int()
    episode_number = fields.Int()
    air_date = fields.Date()
    theme = fields.Str()
    iron_chef_id = fields.Int()
    competitor_id = fields.Int()
    winner = fields.Str()
    judges_scores = fields.Str()
    iron_chef_name = fields.Str()
    competitor_name = fields.Str()

class DishSchema(Schema):
    id = fields.Int()
    episode_id = fields.Int()
    chef_type = fields.Str()
    dish_number = fields.Int()
    dish_name = fields.Str()
    description = fields.Str()
    main_ingredients = fields.Str()
    cooking_techniques = fields.Str()

class RecipeSchema(Schema):
    id = fields.Int()
    dish_id = fields.Int()
    recipe_title = fields.Str()
    ingredients = fields.Raw()  # JSON field
    instructions = fields.Raw()  # JSON field
    prep_time = fields.Int()
    cook_time = fields.Int()
    servings = fields.Int()
    generated_date = fields.DateTime()
    dish_name = fields.Str()
    episode_number = fields.Int()
    theme = fields.Str()

class APIResponseSchema(Schema):
    """Standard API response wrapper"""
    success = fields.Bool()
    data = fields.Raw()
    message = fields.Str()
    errors = fields.List(fields.Str())
    pagination = fields.Dict()

def create_api_app(app: Flask) -> Api:
    """Create and configure the Flask-RESTful API"""
    
    # Initialize CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": ["*"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-API-Key"]
        }
    })
    
    # Initialize rate limiter
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["200 per hour", "50 per minute"],
        storage_uri="memory://"
    )
    limiter.init_app(app)
    
    # Initialize API
    api = Api(app, prefix=f'/api/{API_VERSION}')
    
    # Initialize validator
    validator = SecurityValidator()
    
    # Initialize API key manager
    key_manager = APIKeyManager()
    
    # Add response headers after each request
    @app.after_request
    def after_request(response):
        return add_rate_limit_headers(response)
    
    # Error handlers
    @app.errorhandler(APIError)
    def handle_api_error(error):
        response = {
            'success': False,
            'message': error.message,
            'errors': [error.message]
        }
        if error.payload:
            response.update(error.payload)
        return jsonify(response), error.status_code
    
    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        return jsonify({
            'success': False,
            'message': 'Validation error',
            'errors': error.messages
        }), 400
    
    @app.errorhandler(429)
    def handle_rate_limit(error):
        return jsonify({
            'success': False,
            'message': 'Rate limit exceeded',
            'errors': ['Too many requests. Please try again later.']
        }), 429

    # API Resources
    class EpisodesResource(Resource):
        decorators = [limiter.limit("30 per minute"), require_api_key(optional=True)]
        
        def get(self):
            """Get episodes with filtering and pagination"""
            try:
                # Validate and parse query parameters
                schema = EpisodeFilterSchema()
                args = schema.load(request.args)
                
                with IronChefDatabaseSecure() as db:
                    # Build query
                    base_query = """
                        SELECT e.*, ic.name as iron_chef_name, c.name as competitor_name
                        FROM episodes e
                        JOIN iron_chefs ic ON e.iron_chef_id = ic.id
                        JOIN competitors c ON e.competitor_id = c.id
                    """
                    
                    conditions = []
                    params = []
                    
                    if args.get('theme'):
                        conditions.append("e.theme LIKE ? ESCAPE '\\'")
                        params.append(validator.sanitize_sql_pattern(args['theme']))
                    
                    if args.get('chef'):
                        conditions.append("(ic.name LIKE ? ESCAPE '\\' OR c.name LIKE ? ESCAPE '\\')")
                        chef_pattern = validator.sanitize_sql_pattern(args['chef'])
                        params.extend([chef_pattern, chef_pattern])
                    
                    if args.get('iron_chef_id'):
                        conditions.append("e.iron_chef_id = ?")
                        params.append(args['iron_chef_id'])
                    
                    if args.get('competitor_id'):
                        conditions.append("e.competitor_id = ?")
                        params.append(args['competitor_id'])
                    
                    if args.get('air_date_from'):
                        conditions.append("e.air_date >= ?")
                        params.append(args['air_date_from'].isoformat())
                    
                    if args.get('air_date_to'):
                        conditions.append("e.air_date <= ?")
                        params.append(args['air_date_to'].isoformat())
                    
                    if conditions:
                        base_query += " WHERE " + " AND ".join(conditions)
                    
                    base_query += " ORDER BY e.episode_number"
                    
                    db.cursor.execute(base_query, params)
                    all_episodes = [dict(row) for row in db.cursor.fetchall()]
                    
                    # Apply pagination
                    page = args['page']
                    per_page = args['per_page']
                    total = len(all_episodes)
                    start = (page - 1) * per_page
                    end = start + per_page
                    episodes = all_episodes[start:end]
                    
                    # Serialize response
                    episode_schema = EpisodeSchema(many=True)
                    serialized_episodes = episode_schema.dump(episodes)
                    
                    pagination = {
                        'page': page,
                        'per_page': per_page,
                        'total': total,
                        'pages': (total + per_page - 1) // per_page,
                        'has_next': end < total,
                        'has_prev': page > 1
                    }
                    
                    return {
                        'success': True,
                        'data': serialized_episodes,
                        'pagination': pagination
                    }
                    
            except ValidationError as e:
                raise APIError("Invalid parameters", 400, {'validation_errors': e.messages})
            except Exception as e:
                logger.error(f"Error fetching episodes: {e}")
                raise APIError("Internal server error", 500)

    class EpisodeResource(Resource):
        decorators = [limiter.limit("60 per minute"), require_api_key(optional=True)]
        
        def get(self, episode_id):
            """Get specific episode details"""
            try:
                episode_id = validator.validate_integer(episode_id, min_val=1, field_name="episode_id")
                
                with IronChefDatabaseSecure() as db:
                    episode = db.get_episode_details(episode_id)
                    
                    if not episode:
                        raise APIError("Episode not found", 404)
                    
                    # Serialize response
                    episode_schema = EpisodeSchema()
                    serialized_episode = episode_schema.dump(episode)
                    
                    return {
                        'success': True,
                        'data': serialized_episode
                    }
                    
            except ValueError as e:
                raise APIError(str(e), 400)
            except Exception as e:
                logger.error(f"Error fetching episode {episode_id}: {e}")
                raise APIError("Internal server error", 500)

    class EpisodeDishesResource(Resource):
        decorators = [limiter.limit("60 per minute"), require_api_key(optional=True)]
        
        def get(self, episode_id):
            """Get dishes for a specific episode"""
            try:
                episode_id = validator.validate_integer(episode_id, min_val=1, field_name="episode_id")
                
                with IronChefDatabaseSecure() as db:
                    db.cursor.execute("""
                        SELECT d.* FROM dishes d
                        WHERE d.episode_id = ?
                        ORDER BY d.chef_type, d.dish_number
                    """, (episode_id,))
                    
                    dishes = [dict(row) for row in db.cursor.fetchall()]
                    
                    if not dishes:
                        # Check if episode exists
                        db.cursor.execute("SELECT id FROM episodes WHERE id = ?", (episode_id,))
                        if not db.cursor.fetchone():
                            raise APIError("Episode not found", 404)
                    
                    # Serialize response
                    dish_schema = DishSchema(many=True)
                    serialized_dishes = dish_schema.dump(dishes)
                    
                    return {
                        'success': True,
                        'data': serialized_dishes
                    }
                    
            except ValueError as e:
                raise APIError(str(e), 400)
            except Exception as e:
                logger.error(f"Error fetching dishes for episode {episode_id}: {e}")
                raise APIError("Internal server error", 500)

    class RecipeGenerationResource(Resource):
        decorators = [limiter.limit("10 per minute"), require_api_key(optional=False)]
        
        def post(self):
            """Generate a recipe from dish data"""
            try:
                # Validate request data
                schema = RecipeGenerationSchema()
                data = schema.load(request.get_json() or {})
                
                dish_id = data['dish_id']
                
                with IronChefDatabaseSecure() as db:
                    # Check if recipe already exists
                    db.cursor.execute("SELECT id FROM recipes WHERE dish_id = ?", (dish_id,))
                    existing_recipe = db.cursor.fetchone()
                    
                    if existing_recipe:
                        raise APIError("Recipe already exists for this dish", 409, {
                            'recipe_id': existing_recipe[0]
                        })
                    
                    # Get dish details
                    db.cursor.execute("SELECT * FROM dishes WHERE id = ?", (dish_id,))
                    dish = db.cursor.fetchone()
                    
                    if not dish:
                        raise APIError("Dish not found", 404)
                    
                    dish_data = dict(dish)
                
                # Generate recipe
                generator = RecipeGenerator()
                recipe_data = generator.generate_recipe_for_dish(
                    dish_data,
                    style=data.get('chef_style', 'traditional'),
                    difficulty=data.get('difficulty', 'medium'),
                    dietary_restrictions=data.get('dietary_restrictions', [])
                )
                
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
                
                return {
                    'success': True,
                    'data': {
                        'recipe_id': recipe_id,
                        'message': 'Recipe generated successfully'
                    }
                }, 201
                
            except ValidationError as e:
                raise APIError("Invalid request data", 400, {'validation_errors': e.messages})
            except APIError:
                raise
            except Exception as e:
                logger.error(f"Error generating recipe: {e}")
                raise APIError("Internal server error", 500)

    class RecipeResource(Resource):
        decorators = [limiter.limit("60 per minute"), require_api_key(optional=True)]
        
        def get(self, recipe_id):
            """Get specific recipe details"""
            try:
                recipe_id = validator.validate_integer(recipe_id, min_val=1, field_name="recipe_id")
                
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
                        raise APIError("Recipe not found", 404)
                    
                    recipe = dict(result)
                    
                    # Parse JSON fields
                    try:
                        recipe['ingredients'] = json.loads(recipe['ingredients'])
                        recipe['instructions'] = json.loads(recipe['instructions'])
                    except json.JSONDecodeError:
                        recipe['ingredients'] = []
                        recipe['instructions'] = []
                    
                    # Serialize response
                    recipe_schema = RecipeSchema()
                    serialized_recipe = recipe_schema.dump(recipe)
                    
                    return {
                        'success': True,
                        'data': serialized_recipe
                    }
                    
            except ValueError as e:
                raise APIError(str(e), 400)
            except Exception as e:
                logger.error(f"Error fetching recipe {recipe_id}: {e}")
                raise APIError("Internal server error", 500)

    class SearchResource(Resource):
        decorators = [limiter.limit("20 per minute"), require_api_key(optional=True)]
        
        def get(self):
            """Global search functionality"""
            try:
                # Validate query parameters
                schema = SearchSchema()
                args = schema.load(request.args)
                
                query = args['q']
                page = args['page']
                per_page = args['per_page']
                
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
                    
                    # Combine and paginate results
                    all_results = episodes + dishes + recipes
                    total = len(all_results)
                    start = (page - 1) * per_page
                    end = start + per_page
                    paginated_results = all_results[start:end]
                    
                    pagination = {
                        'page': page,
                        'per_page': per_page,
                        'total': total,
                        'pages': (total + per_page - 1) // per_page,
                        'has_next': end < total,
                        'has_prev': page > 1
                    }
                    
                    return {
                        'success': True,
                        'data': {
                            'results': paginated_results,
                            'summary': {
                                'episodes': len(episodes),
                                'dishes': len(dishes),
                                'recipes': len(recipes),
                                'total': total
                            }
                        },
                        'pagination': pagination
                    }
                    
            except ValidationError as e:
                raise APIError("Invalid parameters", 400, {'validation_errors': e.messages})
            except Exception as e:
                logger.error(f"Error performing search: {e}")
                raise APIError("Internal server error", 500)

    class ThemesResource(Resource):
        decorators = [limiter.limit("100 per minute"), require_api_key(optional=True)]
        
        def get(self):
            """Get all available themes"""
            try:
                with IronChefDatabaseSecure() as db:
                    themes = db.get_all_themes()
                    
                    return {
                        'success': True,
                        'data': {
                            'themes': themes,
                            'count': len(themes)
                        }
                    }
                    
            except Exception as e:
                logger.error(f"Error fetching themes: {e}")
                raise APIError("Internal server error", 500)

    class ChefsResource(Resource):
        decorators = [limiter.limit("100 per minute"), require_api_key(optional=True)]
        
        def get(self):
            """Get all iron chefs and competitors"""
            try:
                with IronChefDatabaseSecure() as db:
                    # Get iron chefs
                    db.cursor.execute("SELECT * FROM iron_chefs ORDER BY name")
                    iron_chefs = [dict(row) for row in db.cursor.fetchall()]
                    
                    # Get competitors
                    db.cursor.execute("SELECT * FROM competitors ORDER BY name")
                    competitors = [dict(row) for row in db.cursor.fetchall()]
                    
                    # Serialize response
                    iron_chef_schema = IronChefSchema(many=True)
                    competitor_schema = CompetitorSchema(many=True)
                    
                    return {
                        'success': True,
                        'data': {
                            'iron_chefs': iron_chef_schema.dump(iron_chefs),
                            'competitors': competitor_schema.dump(competitors)
                        }
                    }
                    
            except Exception as e:
                logger.error(f"Error fetching chefs: {e}")
                raise APIError("Internal server error", 500)

    class APIStatusResource(Resource):
        def get(self):
            """API health check and status"""
            try:
                with IronChefDatabaseSecure() as db:
                    # Test database connection
                    db.cursor.execute("SELECT COUNT(*) FROM episodes")
                    episode_count = db.cursor.fetchone()[0]
                    
                    return {
                        'success': True,
                        'data': {
                            'status': 'healthy',
                            'version': API_VERSION,
                            'timestamp': datetime.utcnow().isoformat(),
                            'database': {
                                'connected': True,
                                'episodes': episode_count
                            }
                        }
                    }
                    
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return {
                    'success': False,
                    'data': {
                        'status': 'unhealthy',
                        'version': API_VERSION,
                        'timestamp': datetime.utcnow().isoformat(),
                        'error': str(e)
                    }
                }, 500

    class ExportResource(Resource):
        decorators = [limiter.limit("5 per minute"), require_api_key(optional=False)]
        
        def get(self, format_type):
            """Export data in various formats"""
            try:
                # Validate format
                if format_type not in ['json', 'csv', 'txt']:
                    raise APIError("Invalid export format", 400)
                
                # Get and validate parameters
                export_type = request.args.get('type')
                if not export_type or export_type not in ['episodes', 'recipes', 'dishes', 'theme']:
                    raise APIError("Invalid or missing export type parameter", 400)
                
                theme = request.args.get('theme', '')
                include_recipes = request.args.get('include_recipes', 'true').lower() == 'true'
                date_from = request.args.get('date_from')
                date_to = request.args.get('date_to')
                
                # Validate theme for theme exports
                if export_type == 'theme' and not theme:
                    raise APIError("Theme parameter required for theme exports", 400)
                
                # Validate theme parameter
                if theme:
                    theme = validator.validate_string(theme, max_length=100, field_name="theme")
                
                # Initialize exporter
                exporter = SecureRecipeExporter()
                
                # Perform export based on type
                if export_type == 'episodes':
                    filepath = exporter.export_episode_summary(format_type)
                elif export_type == 'recipes':
                    filepath = exporter.export_all_recipes(format_type)
                elif export_type == 'dishes':
                    # Create a basic dishes export
                    with IronChefDatabaseSecure() as db:
                        db.cursor.execute("""
                            SELECT d.*, e.theme, e.episode_number, e.air_date
                            FROM dishes d
                            JOIN episodes e ON d.episode_id = e.id
                            ORDER BY e.episode_number, d.chef_type, d.dish_number
                        """)
                        dishes = [dict(row) for row in db.cursor.fetchall()]
                    
                    # Export dishes data
                    import tempfile
                    import json
                    import csv
                    
                    with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{format_type}', delete=False) as temp_file:
                        if format_type == 'json':
                            json.dump(dishes, temp_file, indent=2, default=str)
                        elif format_type == 'csv':
                            if dishes:
                                writer = csv.DictWriter(temp_file, fieldnames=dishes[0].keys())
                                writer.writeheader()
                                writer.writerows(dishes)
                        elif format_type == 'txt':
                            for dish in dishes:
                                temp_file.write(f"Episode {dish['episode_number']}: {dish['theme']}\n")
                                temp_file.write(f"  {dish['chef_type']} - {dish['dish_name']}\n")
                                temp_file.write(f"  {dish['description']}\n\n")
                        
                        filepath = temp_file.name
                        
                elif export_type == 'theme':
                    filepath = exporter.export_dishes_by_theme(theme, format_type)
                
                # Read file content and return appropriate response
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Set appropriate content type
                if format_type == 'json':
                    content_type = 'application/json'
                    try:
                        # Validate JSON and return as object
                        json_data = json.loads(content)
                        return {
                            'success': True,
                            'data': json_data,
                            'meta': {
                                'export_type': export_type,
                                'format': format_type,
                                'exported_at': datetime.utcnow().isoformat(),
                                'record_count': len(json_data) if isinstance(json_data, list) else 1
                            }
                        }
                    except json.JSONDecodeError:
                        content_type = 'text/plain'
                elif format_type == 'csv':
                    content_type = 'text/csv'
                else:
                    content_type = 'text/plain'
                
                # For CSV and TXT, return the content directly with appropriate headers
                from flask import Response
                response = Response(
                    content,
                    content_type=content_type,
                    headers={
                        'Content-Disposition': f'attachment; filename="{export_type}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.{format_type}"'
                    }
                )
                return response
                
            except APIError:
                raise
            except Exception as e:
                logger.error(f"Error exporting {export_type} as {format_type}: {e}")
                raise APIError("Export failed", 500)

    class RecipesResource(Resource):
        decorators = [limiter.limit("30 per minute"), require_api_key(optional=True)]
        
        def get(self):
            """Get recipes with filtering and pagination"""
            try:
                # Validate and parse query parameters
                page = request.args.get('page', 1, type=int)
                per_page = request.args.get('per_page', 12, type=int)
                dish_name = request.args.get('dish_name', '').strip()
                ingredient = request.args.get('ingredient', '').strip()
                chef_type = request.args.get('chef_type', '').strip()
                episode_id = request.args.get('episode_id', type=int)
                theme = request.args.get('theme', '').strip()
                
                # Validate parameters
                page = validator.validate_integer(page, min_val=1, max_val=10000, field_name="page")
                per_page = validator.validate_integer(per_page, min_val=1, max_val=100, field_name="per_page")
                
                if dish_name:
                    dish_name = validator.validate_string(dish_name, max_length=100, field_name="dish_name")
                if ingredient:
                    ingredient = validator.validate_string(ingredient, max_length=100, field_name="ingredient")
                if chef_type and chef_type not in ['iron_chef', 'competitor']:
                    raise APIError("Invalid chef_type parameter", 400)
                if episode_id:
                    episode_id = validator.validate_integer(episode_id, min_val=1, field_name="episode_id")
                if theme:
                    theme = validator.validate_string(theme, max_length=100, field_name="theme")
                
                with IronChefDatabaseSecure() as db:
                    # Build query
                    base_query = """
                        SELECT r.*, d.dish_name, d.description, d.chef_type,
                               e.theme, e.episode_number, e.air_date,
                               ic.name as iron_chef_name, c.name as competitor_name
                        FROM recipes r
                        JOIN dishes d ON r.dish_id = d.id
                        JOIN episodes e ON d.episode_id = e.id
                        JOIN iron_chefs ic ON e.iron_chef_id = ic.id
                        JOIN competitors c ON e.competitor_id = c.id
                    """
                    
                    conditions = []
                    params = []
                    
                    if dish_name:
                        conditions.append("d.dish_name LIKE ? ESCAPE '\\'")
                        params.append(validator.sanitize_sql_pattern(dish_name))
                    
                    if ingredient:
                        conditions.append("r.ingredients LIKE ? ESCAPE '\\'")
                        params.append(validator.sanitize_sql_pattern(ingredient))
                    
                    if chef_type:
                        conditions.append("d.chef_type = ?")
                        params.append(chef_type)
                    
                    if episode_id:
                        conditions.append("e.id = ?")
                        params.append(episode_id)
                    
                    if theme:
                        conditions.append("e.theme LIKE ? ESCAPE '\\'")
                        params.append(validator.sanitize_sql_pattern(theme))
                    
                    if conditions:
                        base_query += " WHERE " + " AND ".join(conditions)
                    
                    base_query += " ORDER BY e.episode_number, d.chef_type, d.dish_number"
                    
                    db.cursor.execute(base_query, params)
                    all_recipes = [dict(row) for row in db.cursor.fetchall()]
                    
                    # Parse JSON fields
                    for recipe in all_recipes:
                        try:
                            recipe['ingredients'] = json.loads(recipe['ingredients'])
                            recipe['instructions'] = json.loads(recipe['instructions'])
                        except json.JSONDecodeError:
                            recipe['ingredients'] = []
                            recipe['instructions'] = []
                    
                    # Apply pagination
                    total = len(all_recipes)
                    start = (page - 1) * per_page
                    end = start + per_page
                    recipes = all_recipes[start:end]
                    
                    # Serialize response
                    recipe_schema = RecipeSchema(many=True)
                    serialized_recipes = recipe_schema.dump(recipes)
                    
                    pagination = {
                        'page': page,
                        'per_page': per_page,
                        'total': total,
                        'pages': (total + per_page - 1) // per_page,
                        'has_next': end < total,
                        'has_prev': page > 1
                    }
                    
                    return {
                        'success': True,
                        'data': serialized_recipes,
                        'pagination': pagination
                    }
                    
            except APIError:
                raise
            except Exception as e:
                logger.error(f"Error fetching recipes: {e}")
                raise APIError("Internal server error", 500)

    class DishesResource(Resource):
        decorators = [limiter.limit("30 per minute"), require_api_key(optional=True)]
        
        def get(self):
            """Get dishes with filtering and pagination"""
            try:
                # Validate and parse query parameters
                page = request.args.get('page', 1, type=int)
                per_page = request.args.get('per_page', 12, type=int)
                episode_id = request.args.get('episode_id', type=int)
                chef_type = request.args.get('chef_type', '').strip()
                dish_name = request.args.get('dish_name', '').strip()
                
                # Validate parameters
                page = validator.validate_integer(page, min_val=1, max_val=10000, field_name="page")
                per_page = validator.validate_integer(per_page, min_val=1, max_val=100, field_name="per_page")
                
                if episode_id:
                    episode_id = validator.validate_integer(episode_id, min_val=1, field_name="episode_id")
                if chef_type and chef_type not in ['iron_chef', 'competitor']:
                    raise APIError("Invalid chef_type parameter", 400)
                if dish_name:
                    dish_name = validator.validate_string(dish_name, max_length=100, field_name="dish_name")
                
                with IronChefDatabaseSecure() as db:
                    # Build query
                    base_query = """
                        SELECT d.*, e.theme, e.episode_number, e.air_date
                        FROM dishes d
                        JOIN episodes e ON d.episode_id = e.id
                    """
                    
                    conditions = []
                    params = []
                    
                    if episode_id:
                        conditions.append("d.episode_id = ?")
                        params.append(episode_id)
                    
                    if chef_type:
                        conditions.append("d.chef_type = ?")
                        params.append(chef_type)
                    
                    if dish_name:
                        conditions.append("d.dish_name LIKE ? ESCAPE '\\'")
                        params.append(validator.sanitize_sql_pattern(dish_name))
                    
                    if conditions:
                        base_query += " WHERE " + " AND ".join(conditions)
                    
                    base_query += " ORDER BY e.episode_number, d.chef_type, d.dish_number"
                    
                    db.cursor.execute(base_query, params)
                    all_dishes = [dict(row) for row in db.cursor.fetchall()]
                    
                    # Apply pagination
                    total = len(all_dishes)
                    start = (page - 1) * per_page
                    end = start + per_page
                    dishes = all_dishes[start:end]
                    
                    # Serialize response
                    dish_schema = DishSchema(many=True)
                    serialized_dishes = dish_schema.dump(dishes)
                    
                    pagination = {
                        'page': page,
                        'per_page': per_page,
                        'total': total,
                        'pages': (total + per_page - 1) // per_page,
                        'has_next': end < total,
                        'has_prev': page > 1
                    }
                    
                    return {
                        'success': True,
                        'data': serialized_dishes,
                        'pagination': pagination
                    }
                    
            except APIError:
                raise
            except Exception as e:
                logger.error(f"Error fetching dishes: {e}")
                raise APIError("Internal server error", 500)

    # Register API routes
    api.add_resource(APIStatusResource, '/status')
    api.add_resource(EpisodesResource, '/episodes')
    api.add_resource(EpisodeResource, '/episodes/<int:episode_id>')
    api.add_resource(EpisodeDishesResource, '/episodes/<int:episode_id>/dishes')
    api.add_resource(DishesResource, '/dishes')
    api.add_resource(RecipesResource, '/recipes')
    api.add_resource(RecipeGenerationResource, '/recipes/generate')
    api.add_resource(RecipeResource, '/recipes/<int:recipe_id>')
    api.add_resource(SearchResource, '/search')
    api.add_resource(ThemesResource, '/themes')
    api.add_resource(ChefsResource, '/chefs')
    api.add_resource(ExportResource, '/export/<format_type>')
    
    return api

def create_openapi_spec(app: Flask) -> APISpec:
    """Create OpenAPI specification for the API"""
    spec = APISpec(
        title=API_TITLE,
        version=API_VERSION,
        openapi_version="3.0.2",
        info=dict(
            description=API_DESCRIPTION,
            contact=dict(name="Iron Chef API Team"),
            license=dict(name="MIT")
        ),
        servers=[
            dict(description="Development server", url="http://localhost:5000"),
        ],
        plugins=[FlaskPlugin(), MarshmallowPlugin()],
    )
    
    # Add security schemes
    spec.components.security_scheme("ApiKeyAuth", {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key"
    })
    
    # Add schemas
    spec.components.schema("Episode", schema=EpisodeSchema)
    spec.components.schema("Dish", schema=DishSchema)
    spec.components.schema("Recipe", schema=RecipeSchema)
    spec.components.schema("IronChef", schema=IronChefSchema)
    spec.components.schema("Competitor", schema=CompetitorSchema)
    spec.components.schema("APIResponse", schema=APIResponseSchema)
    
    return spec

if __name__ == '__main__':
    # This module is designed to be imported by the main app
    pass