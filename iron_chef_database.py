import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple

class IronChefDatabase:
    def __init__(self, db_path: str = "iron_chef_japan.db"):
        self.db_path = db_path
        self.connection = None
        self.cursor = None
        
    def __enter__(self):
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.cursor = self.connection.cursor()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.commit()
            self.connection.close()
            
    def initialize_database(self):
        """Create all tables from the schema"""
        with open('database_schema.sql', 'r') as f:
            schema = f.read()
        self.cursor.executescript(schema)
        self.connection.commit()
        
    def add_iron_chef(self, name: str, title: str = None, specialty: str = None, active_years: str = None) -> int:
        """Add a new Iron Chef to the database"""
        query = "INSERT INTO iron_chefs (name, title, specialty, active_years) VALUES (?, ?, ?, ?)"
        self.cursor.execute(query, (name, title, specialty, active_years))
        return self.cursor.lastrowid
        
    def add_competitor(self, name: str, restaurant: str = None, specialty: str = None, location: str = None) -> int:
        """Add a new competitor to the database"""
        query = "INSERT INTO competitors (name, restaurant, specialty, location) VALUES (?, ?, ?, ?)"
        self.cursor.execute(query, (name, restaurant, specialty, location))
        return self.cursor.lastrowid
        
    def add_episode(self, episode_number: int, theme: str, iron_chef_id: int, competitor_id: int,
                    air_date: str = None, winner: str = None, judges_scores: str = None) -> int:
        """Add a new episode to the database"""
        query = """INSERT INTO episodes (episode_number, air_date, theme, iron_chef_id, competitor_id, winner, judges_scores) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)"""
        self.cursor.execute(query, (episode_number, air_date, theme, iron_chef_id, competitor_id, winner, judges_scores))
        return self.cursor.lastrowid
        
    def add_dish(self, episode_id: int, chef_type: str, dish_number: int, dish_name: str,
                 description: str = None, main_ingredients: str = None, cooking_techniques: str = None) -> int:
        """Add a dish served in an episode"""
        query = """INSERT INTO dishes (episode_id, chef_type, dish_number, dish_name, description, main_ingredients, cooking_techniques)
                   VALUES (?, ?, ?, ?, ?, ?, ?)"""
        self.cursor.execute(query, (episode_id, chef_type, dish_number, dish_name, description, main_ingredients, cooking_techniques))
        return self.cursor.lastrowid
        
    def add_ingredient(self, name: str) -> int:
        """Add an ingredient to the master list"""
        try:
            self.cursor.execute("INSERT INTO ingredients (name) VALUES (?)", (name,))
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            # Ingredient already exists, get its ID
            self.cursor.execute("SELECT id FROM ingredients WHERE name = ?", (name,))
            return self.cursor.fetchone()[0]
            
    def link_dish_ingredient(self, dish_id: int, ingredient_id: int, quantity: str = None, unit: str = None):
        """Link an ingredient to a dish with optional quantity"""
        query = "INSERT INTO dish_ingredients (dish_id, ingredient_id, quantity, unit) VALUES (?, ?, ?, ?)"
        self.cursor.execute(query, (dish_id, ingredient_id, quantity, unit))
        
    def get_episode_details(self, episode_id: int) -> Dict:
        """Get full details of an episode including dishes"""
        # Get episode info
        query = """SELECT e.*, ic.name as iron_chef_name, c.name as competitor_name
                   FROM episodes e
                   JOIN iron_chefs ic ON e.iron_chef_id = ic.id
                   JOIN competitors c ON e.competitor_id = c.id
                   WHERE e.id = ?"""
        self.cursor.execute(query, (episode_id,))
        episode = dict(self.cursor.fetchone())
        
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
        """Search episodes by theme"""
        query = """SELECT e.*, ic.name as iron_chef_name, c.name as competitor_name
                   FROM episodes e
                   JOIN iron_chefs ic ON e.iron_chef_id = ic.id
                   JOIN competitors c ON e.competitor_id = c.id
                   WHERE e.theme LIKE ?"""
        self.cursor.execute(query, (f'%{theme}%',))
        return [dict(row) for row in self.cursor.fetchall()]
        
    def get_all_themes(self) -> List[str]:
        """Get a list of all unique themes"""
        self.cursor.execute("SELECT DISTINCT theme FROM episodes ORDER BY theme")
        return [row[0] for row in self.cursor.fetchall()]
        
    def get_dishes_by_ingredient(self, ingredient: str) -> List[Dict]:
        """Find all dishes containing a specific ingredient"""
        query = """SELECT d.*, e.theme, e.episode_number
                   FROM dishes d
                   JOIN episodes e ON d.episode_id = e.id
                   WHERE d.main_ingredients LIKE ?"""
        self.cursor.execute(query, (f'%{ingredient}%',))
        return [dict(row) for row in self.cursor.fetchall()]
        
    def add_recipe(self, dish_id: int, recipe_title: str, ingredients: str, instructions: str,
                   prep_time: int = None, cook_time: int = None, servings: int = None) -> int:
        """Add a generated recipe for a dish"""
        query = """INSERT INTO recipes (dish_id, recipe_title, ingredients, instructions, prep_time, cook_time, servings)
                   VALUES (?, ?, ?, ?, ?, ?, ?)"""
        self.cursor.execute(query, (dish_id, recipe_title, ingredients, instructions, prep_time, cook_time, servings))
        return self.cursor.lastrowid