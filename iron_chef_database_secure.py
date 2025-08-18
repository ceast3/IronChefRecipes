import sqlite3
import json
import re
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple

class SecurityValidator:
    """Input validation and sanitization utilities"""
    
    @staticmethod
    def validate_integer(value: any, min_val: int = 0, max_val: int = None, field_name: str = "value") -> int:
        """Validate and sanitize integer input"""
        if value is None:
            return None
        try:
            int_val = int(value)
            if int_val < min_val:
                raise ValueError(f"{field_name} must be at least {min_val}")
            if max_val is not None and int_val > max_val:
                raise ValueError(f"{field_name} must be no more than {max_val}")
            return int_val
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid {field_name}: must be an integer")
    
    @staticmethod
    def validate_string(value: str, max_length: int = 500, 
                       pattern: str = None, field_name: str = "value") -> str:
        """Validate and sanitize string input"""
        if value is None:
            return None
        
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string")
        
        # Remove any null bytes
        value = value.replace('\x00', '')
        
        # Trim whitespace
        value = value.strip()
        
        # Check length
        if len(value) > max_length:
            raise ValueError(f"{field_name} exceeds maximum length of {max_length}")
        
        # Check pattern if provided
        if pattern and not re.match(pattern, value):
            raise ValueError(f"{field_name} contains invalid characters")
        
        return value
    
    @staticmethod
    def sanitize_sql_pattern(pattern: str) -> str:
        """Sanitize SQL LIKE pattern to prevent injection"""
        if not pattern:
            return '%'
        
        # Escape special SQL LIKE characters
        pattern = pattern.replace('\\', '\\\\')
        pattern = pattern.replace('%', '\\%')
        pattern = pattern.replace('_', '\\_')
        pattern = pattern.replace('[', '\\[')
        
        # Add wildcards for search
        return f'%{pattern}%'
    
    @staticmethod
    def validate_filename(filename: str) -> str:
        """Validate and sanitize filename to prevent path traversal"""
        if not filename:
            raise ValueError("Filename cannot be empty")
        
        # Remove any path components
        filename = os.path.basename(filename)
        
        # Remove any potentially dangerous characters
        filename = re.sub(r'[^\w\-_\.]', '_', filename)
        
        # Prevent directory traversal
        if '..' in filename or filename.startswith('/'):
            raise ValueError("Invalid filename")
        
        # Ensure it has a valid extension
        valid_extensions = ['.json', '.csv', '.txt', '.md']
        if not any(filename.endswith(ext) for ext in valid_extensions):
            filename += '.txt'
        
        return filename

class IronChefDatabaseSecure:
    def __init__(self, db_path: str = "iron_chef_japan.db"):
        # Validate database path
        db_path = SecurityValidator.validate_string(
            db_path, max_length=255, 
            pattern=r'^[\w\-_./]+\.db$', 
            field_name="database path"
        )
        
        self.db_path = db_path
        self.connection = None
        self.cursor = None
        self.validator = SecurityValidator()
        
    def __enter__(self):
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        # Enable foreign key constraints for data integrity
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.connection.cursor()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            if exc_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()
            self.connection.close()
            
    def initialize_database(self):
        """Create all tables from the schema"""
        with open('database_schema.sql', 'r') as f:
            schema = f.read()
        
        # Use executescript for schema creation only
        self.cursor.executescript(schema)
        self.connection.commit()
        
    def add_iron_chef(self, name: str, title: str = None, 
                     specialty: str = None, active_years: str = None) -> int:
        """Add a new Iron Chef to the database with validation"""
        # Validate inputs
        name = self.validator.validate_string(name, max_length=100, field_name="chef name")
        if not name:
            raise ValueError("Chef name is required")
        
        title = self.validator.validate_string(title, max_length=100, field_name="title")
        specialty = self.validator.validate_string(specialty, max_length=100, field_name="specialty")
        active_years = self.validator.validate_string(active_years, max_length=50, field_name="active years")
        
        query = "INSERT INTO iron_chefs (name, title, specialty, active_years) VALUES (?, ?, ?, ?)"
        self.cursor.execute(query, (name, title, specialty, active_years))
        return self.cursor.lastrowid
        
    def add_competitor(self, name: str, restaurant: str = None, 
                      specialty: str = None, location: str = None) -> int:
        """Add a new competitor to the database with validation"""
        # Validate inputs
        name = self.validator.validate_string(name, max_length=100, field_name="competitor name")
        if not name:
            raise ValueError("Competitor name is required")
        
        restaurant = self.validator.validate_string(restaurant, max_length=200, field_name="restaurant")
        specialty = self.validator.validate_string(specialty, max_length=100, field_name="specialty")
        location = self.validator.validate_string(location, max_length=100, field_name="location")
        
        query = "INSERT INTO competitors (name, restaurant, specialty, location) VALUES (?, ?, ?, ?)"
        self.cursor.execute(query, (name, restaurant, specialty, location))
        return self.cursor.lastrowid
        
    def add_episode(self, episode_number: int, theme: str, iron_chef_id: int, 
                   competitor_id: int, air_date: str = None, winner: str = None, 
                   judges_scores: str = None) -> int:
        """Add a new episode to the database with validation"""
        # Validate inputs
        episode_number = self.validator.validate_integer(
            episode_number, min_val=1, max_val=999999, field_name="episode number"
        )
        theme = self.validator.validate_string(theme, max_length=100, field_name="theme")
        if not theme:
            raise ValueError("Theme is required")
        
        iron_chef_id = self.validator.validate_integer(
            iron_chef_id, min_val=1, field_name="iron chef ID"
        )
        competitor_id = self.validator.validate_integer(
            competitor_id, min_val=1, field_name="competitor ID"
        )
        
        # Validate winner value
        if winner:
            winner = self.validator.validate_string(winner, max_length=20, field_name="winner")
            if winner not in ['Iron Chef', 'Competitor', 'Draw']:
                raise ValueError("Winner must be 'Iron Chef', 'Competitor', or 'Draw'")
        
        # Validate date format if provided
        if air_date:
            air_date = self.validator.validate_string(
                air_date, max_length=10, 
                pattern=r'^\d{4}-\d{2}-\d{2}$', 
                field_name="air date"
            )
        
        judges_scores = self.validator.validate_string(
            judges_scores, max_length=100, field_name="judges scores"
        )
        
        query = """INSERT INTO episodes (episode_number, air_date, theme, iron_chef_id, 
                   competitor_id, winner, judges_scores) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)"""
        self.cursor.execute(query, (episode_number, air_date, theme, iron_chef_id, 
                                   competitor_id, winner, judges_scores))
        return self.cursor.lastrowid
        
    def add_dish(self, episode_id: int, chef_type: str, dish_number: int, 
                dish_name: str, description: str = None, main_ingredients: str = None, 
                cooking_techniques: str = None) -> int:
        """Add a dish served in an episode with validation"""
        # Validate inputs
        episode_id = self.validator.validate_integer(
            episode_id, min_val=1, field_name="episode ID"
        )
        
        chef_type = self.validator.validate_string(chef_type, max_length=20, field_name="chef type")
        if chef_type not in ['iron_chef', 'competitor']:
            raise ValueError("Chef type must be 'iron_chef' or 'competitor'")
        
        dish_number = self.validator.validate_integer(
            dish_number, min_val=1, max_val=20, field_name="dish number"
        )
        
        dish_name = self.validator.validate_string(dish_name, max_length=200, field_name="dish name")
        if not dish_name:
            raise ValueError("Dish name is required")
        
        description = self.validator.validate_string(description, max_length=1000, field_name="description")
        main_ingredients = self.validator.validate_string(
            main_ingredients, max_length=500, field_name="main ingredients"
        )
        cooking_techniques = self.validator.validate_string(
            cooking_techniques, max_length=500, field_name="cooking techniques"
        )
        
        query = """INSERT INTO dishes (episode_id, chef_type, dish_number, dish_name, 
                   description, main_ingredients, cooking_techniques)
                   VALUES (?, ?, ?, ?, ?, ?, ?)"""
        self.cursor.execute(query, (episode_id, chef_type, dish_number, dish_name, 
                                   description, main_ingredients, cooking_techniques))
        return self.cursor.lastrowid
        
    def add_ingredient(self, name: str) -> int:
        """Add an ingredient to the master list with validation"""
        name = self.validator.validate_string(name, max_length=100, field_name="ingredient name")
        if not name:
            raise ValueError("Ingredient name is required")
        
        try:
            self.cursor.execute("INSERT INTO ingredients (name) VALUES (?)", (name,))
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            # Ingredient already exists, get its ID
            self.cursor.execute("SELECT id FROM ingredients WHERE name = ?", (name,))
            result = self.cursor.fetchone()
            return result[0] if result else None
            
    def link_dish_ingredient(self, dish_id: int, ingredient_id: int, 
                           quantity: str = None, unit: str = None):
        """Link an ingredient to a dish with optional quantity (with validation)"""
        dish_id = self.validator.validate_integer(dish_id, min_val=1, field_name="dish ID")
        ingredient_id = self.validator.validate_integer(
            ingredient_id, min_val=1, field_name="ingredient ID"
        )
        quantity = self.validator.validate_string(quantity, max_length=50, field_name="quantity")
        unit = self.validator.validate_string(unit, max_length=20, field_name="unit")
        
        query = "INSERT INTO dish_ingredients (dish_id, ingredient_id, quantity, unit) VALUES (?, ?, ?, ?)"
        self.cursor.execute(query, (dish_id, ingredient_id, quantity, unit))
        
    def get_episode_details(self, episode_id: int) -> Dict:
        """Get full details of an episode including dishes (with validation)"""
        episode_id = self.validator.validate_integer(episode_id, min_val=1, field_name="episode ID")
        
        # Get episode info
        query = """SELECT e.*, ic.name as iron_chef_name, c.name as competitor_name
                   FROM episodes e
                   JOIN iron_chefs ic ON e.iron_chef_id = ic.id
                   JOIN competitors c ON e.competitor_id = c.id
                   WHERE e.id = ?"""
        self.cursor.execute(query, (episode_id,))
        result = self.cursor.fetchone()
        
        if not result:
            return None
        
        episode = dict(result)
        
        # Get dishes
        query = """SELECT * FROM dishes WHERE episode_id = ? ORDER BY chef_type, dish_number"""
        self.cursor.execute(query, (episode_id,))
        dishes = [dict(row) for row in self.cursor.fetchall()]
        
        episode['dishes'] = {
            'iron_chef': [d for d in dishes if d['chef_type'] == 'iron_chef'],
            'competitor': [d for d in dishes if d['chef_type'] == 'competitor']
        }
        
        return episode
        
    def search_episodes_by_theme(self, theme: str) -> List[Dict]:
        """Search episodes by theme with SQL injection protection"""
        # Validate and sanitize input
        if theme:
            theme = self.validator.validate_string(theme, max_length=100, field_name="theme")
        
        # Use parameterized query with escaped LIKE pattern
        query = """SELECT e.*, ic.name as iron_chef_name, c.name as competitor_name
                   FROM episodes e
                   JOIN iron_chefs ic ON e.iron_chef_id = ic.id
                   JOIN competitors c ON e.competitor_id = c.id
                   WHERE e.theme LIKE ? ESCAPE '\\'"""
        
        # Properly escape the search pattern
        search_pattern = self.validator.sanitize_sql_pattern(theme) if theme else '%'
        
        self.cursor.execute(query, (search_pattern,))
        return [dict(row) for row in self.cursor.fetchall()]
        
    def get_all_themes(self) -> List[str]:
        """Get a list of all unique themes"""
        self.cursor.execute("SELECT DISTINCT theme FROM episodes ORDER BY theme")
        return [row[0] for row in self.cursor.fetchall()]
        
    def get_dishes_by_ingredient(self, ingredient: str) -> List[Dict]:
        """Find all dishes containing a specific ingredient with SQL injection protection"""
        # Validate and sanitize input
        if ingredient:
            ingredient = self.validator.validate_string(
                ingredient, max_length=100, field_name="ingredient"
            )
        
        query = """SELECT d.*, e.theme, e.episode_number
                   FROM dishes d
                   JOIN episodes e ON d.episode_id = e.id
                   WHERE d.main_ingredients LIKE ? ESCAPE '\\'"""
        
        # Properly escape the search pattern
        search_pattern = self.validator.sanitize_sql_pattern(ingredient) if ingredient else '%'
        
        self.cursor.execute(query, (search_pattern,))
        return [dict(row) for row in self.cursor.fetchall()]
        
    def add_recipe(self, dish_id: int, recipe_title: str, ingredients: str, 
                  instructions: str, prep_time: int = None, cook_time: int = None, 
                  servings: int = None) -> int:
        """Add a generated recipe for a dish with validation"""
        # Validate all inputs
        dish_id = self.validator.validate_integer(dish_id, min_val=1, field_name="dish ID")
        
        recipe_title = self.validator.validate_string(
            recipe_title, max_length=200, field_name="recipe title"
        )
        if not recipe_title:
            raise ValueError("Recipe title is required")
        
        # Validate JSON strings
        try:
            if isinstance(ingredients, str):
                json.loads(ingredients)
            else:
                ingredients = json.dumps(ingredients)
        except json.JSONDecodeError:
            raise ValueError("Invalid ingredients format")
        
        try:
            if isinstance(instructions, str):
                json.loads(instructions)
            else:
                instructions = json.dumps(instructions)
        except json.JSONDecodeError:
            raise ValueError("Invalid instructions format")
        
        prep_time = self.validator.validate_integer(
            prep_time, min_val=0, max_val=999, field_name="prep time"
        )
        cook_time = self.validator.validate_integer(
            cook_time, min_val=0, max_val=999, field_name="cook time"
        )
        servings = self.validator.validate_integer(
            servings, min_val=1, max_val=100, field_name="servings"
        )
        
        query = """INSERT INTO recipes (dish_id, recipe_title, ingredients, instructions, 
                   prep_time, cook_time, servings)
                   VALUES (?, ?, ?, ?, ?, ?, ?)"""
        self.cursor.execute(query, (dish_id, recipe_title, ingredients, instructions, 
                                   prep_time, cook_time, servings))
        return self.cursor.lastrowid