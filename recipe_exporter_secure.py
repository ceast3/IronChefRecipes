#!/usr/bin/env python3
"""
Secure Recipe Export Utilities for Iron Chef Database
Includes path traversal protection and input validation
"""

import json
import csv
import os
import re
from datetime import datetime
from typing import Dict, List, Optional
from iron_chef_database_secure import IronChefDatabaseSecure, SecurityValidator

class SecureRecipeExporter:
    def __init__(self, output_dir: str = None):
        """Initialize exporter with secure output directory"""
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.validator = SecurityValidator()
        
        # Set and validate output directory
        if output_dir:
            self.output_dir = self._validate_output_dir(output_dir)
        else:
            # Use current directory as default
            self.output_dir = os.path.abspath('.')
        
        # Ensure exports subdirectory exists
        self.export_path = os.path.join(self.output_dir, 'exports')
        os.makedirs(self.export_path, exist_ok=True)
    
    def _validate_output_dir(self, directory: str) -> str:
        """Validate output directory path"""
        # Convert to absolute path
        abs_path = os.path.abspath(directory)
        
        # Check if directory exists
        if not os.path.exists(abs_path):
            raise ValueError(f"Output directory does not exist: {abs_path}")
        
        if not os.path.isdir(abs_path):
            raise ValueError(f"Path is not a directory: {abs_path}")
        
        # Check write permissions
        if not os.access(abs_path, os.W_OK):
            raise ValueError(f"No write permission for directory: {abs_path}")
        
        return abs_path
    
    def _sanitize_filename(self, filename: str, extension: str = '.txt') -> str:
        """Sanitize filename to prevent path traversal attacks"""
        if not filename:
            # Generate default filename if none provided
            filename = f"export_{self.timestamp}"
        
        # Remove any directory separators and parent directory references
        filename = os.path.basename(filename)
        filename = filename.replace('..', '')
        filename = filename.replace(os.sep, '_')
        filename = filename.replace('/', '_')
        filename = filename.replace('\\', '_')
        
        # Remove any potentially dangerous characters
        # Allow only alphanumeric, dash, underscore, and dot
        filename = re.sub(r'[^a-zA-Z0-9\-_\.]', '_', filename)
        
        # Remove leading dots (hidden files on Unix)
        filename = filename.lstrip('.')
        
        # Limit filename length
        max_base_length = 200
        if len(filename) > max_base_length:
            filename = filename[:max_base_length]
        
        # Ensure proper extension
        valid_extensions = ['.json', '.csv', '.txt', '.md']
        
        # Remove any existing extension
        for ext in valid_extensions:
            if filename.endswith(ext):
                filename = filename[:-len(ext)]
                break
        
        # Add the specified extension
        if extension not in valid_extensions:
            extension = '.txt'
        
        filename = filename + extension
        
        # Final safety check - ensure filename is not empty
        if not filename or filename == extension:
            filename = f"export_{self.timestamp}{extension}"
        
        return filename
    
    def _get_safe_filepath(self, filename: str, extension: str = '.txt') -> str:
        """Get safe full filepath for export"""
        safe_filename = self._sanitize_filename(filename, extension)
        filepath = os.path.join(self.export_path, safe_filename)
        
        # Ensure the final path is still within our export directory
        # (defense in depth against any potential bypass)
        abs_filepath = os.path.abspath(filepath)
        abs_export_path = os.path.abspath(self.export_path)
        
        if not abs_filepath.startswith(abs_export_path):
            raise ValueError("Invalid file path detected")
        
        return abs_filepath
    
    def export_episode_summary(self, output_format: str = 'json', filename: str = None) -> str:
        """Export a summary of all episodes with security validation"""
        # Validate output format
        output_format = output_format.lower()
        if output_format not in ['json', 'csv']:
            raise ValueError("Supported formats: json, csv")
        
        # Get safe filepath
        extension = f'.{output_format}'
        if filename is None:
            filename = f"iron_chef_episodes_{self.timestamp}"
        
        filepath = self._get_safe_filepath(filename, extension)
        
        with IronChefDatabaseSecure() as db:
            episodes = db.search_episodes_by_theme('')  # Get all episodes
            
            if output_format == 'json':
                self._export_episodes_json(episodes, filepath)
            elif output_format == 'csv':
                self._export_episodes_csv(episodes, filepath)
        
        return filepath
    
    def export_recipe(self, dish_id: int, output_format: str = 'json', filename: str = None) -> str:
        """Export a specific recipe with security validation"""
        # Validate dish_id
        dish_id = self.validator.validate_integer(dish_id, min_val=1, field_name="dish ID")
        
        # Validate output format
        output_format = output_format.lower()
        if output_format not in ['json', 'txt']:
            raise ValueError("Supported formats: json, txt")
        
        # Get safe filepath
        extension = f'.{output_format}'
        if filename is None:
            filename = f"recipe_{dish_id}_{self.timestamp}"
        
        filepath = self._get_safe_filepath(filename, extension)
        
        with IronChefDatabaseSecure() as db:
            # Get recipe if it exists
            db.cursor.execute("SELECT * FROM recipes WHERE dish_id = ?", (dish_id,))
            recipe_row = db.cursor.fetchone()
            
            if not recipe_row:
                raise ValueError(f"No recipe found for dish ID {dish_id}")
            
            recipe_data = dict(recipe_row)
            # Parse JSON strings back to objects
            recipe_data['ingredients'] = json.loads(recipe_data['ingredients'])
            recipe_data['instructions'] = json.loads(recipe_data['instructions'])
            
            # Get dish details
            db.cursor.execute("""
                SELECT d.*, e.theme, e.episode_number, ic.name as iron_chef, c.name as competitor
                FROM dishes d
                JOIN episodes e ON d.episode_id = e.id
                LEFT JOIN iron_chefs ic ON e.iron_chef_id = ic.id
                LEFT JOIN competitors c ON e.competitor_id = c.id
                WHERE d.id = ?
            """, (dish_id,))
            dish_data = dict(db.cursor.fetchone())
            
            recipe_data['dish_info'] = dish_data
            
            if output_format == 'json':
                self._export_recipe_json(recipe_data, filepath)
            elif output_format == 'txt':
                self._export_recipe_text(recipe_data, filepath)
        
        return filepath
    
    def export_all_recipes(self, output_format: str = 'json', filename: str = None) -> str:
        """Export all recipes in the database with security validation"""
        # Validate output format
        output_format = output_format.lower()
        if output_format not in ['json']:
            raise ValueError("Supported formats: json")
        
        # Get safe filepath
        extension = f'.{output_format}'
        if filename is None:
            filename = f"all_recipes_{self.timestamp}"
        
        filepath = self._get_safe_filepath(filename, extension)
        
        with IronChefDatabaseSecure() as db:
            db.cursor.execute("""
                SELECT r.*, d.dish_name, d.chef_type, e.theme, e.episode_number
                FROM recipes r
                JOIN dishes d ON r.dish_id = d.id
                JOIN episodes e ON d.episode_id = e.id
                ORDER BY e.episode_number, d.chef_type, d.dish_number
            """)
            recipes = [dict(row) for row in db.cursor.fetchall()]
            
            # Parse JSON strings for each recipe
            for recipe in recipes:
                try:
                    recipe['ingredients'] = json.loads(recipe['ingredients'])
                    recipe['instructions'] = json.loads(recipe['instructions'])
                except json.JSONDecodeError:
                    # Handle corrupted data gracefully
                    recipe['ingredients'] = []
                    recipe['instructions'] = []
            
            if output_format == 'json':
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(recipes, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def export_dishes_by_theme(self, theme: str, output_format: str = 'json', filename: str = None) -> str:
        """Export all dishes for a specific theme with security validation"""
        # Validate theme input
        theme = self.validator.validate_string(theme, max_length=100, field_name="theme")
        if not theme:
            raise ValueError("Theme is required")
        
        # Validate output format
        output_format = output_format.lower()
        if output_format not in ['json']:
            raise ValueError("Supported formats: json")
        
        # Get safe filepath
        extension = f'.{output_format}'
        if filename is None:
            # Create filename from theme
            safe_theme = re.sub(r'[^a-zA-Z0-9]', '_', theme.lower())
            filename = f"dishes_{safe_theme}_{self.timestamp}"
        
        filepath = self._get_safe_filepath(filename, extension)
        
        with IronChefDatabaseSecure() as db:
            episodes = db.search_episodes_by_theme(theme)
            if not episodes:
                raise ValueError(f"No episodes found for theme: {theme}")
            
            theme_data = {
                'theme': theme,
                'episodes': []
            }
            
            for episode in episodes:
                episode_details = db.get_episode_details(episode['id'])
                if episode_details:
                    theme_data['episodes'].append(episode_details)
            
            if output_format == 'json':
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(theme_data, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def _export_episodes_json(self, episodes: List[Dict], filepath: str):
        """Export episodes to JSON format with error handling"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(episodes, f, indent=2, ensure_ascii=False)
        except (IOError, OSError) as e:
            raise IOError(f"Failed to write JSON file: {e}")
    
    def _export_episodes_csv(self, episodes: List[Dict], filepath: str):
        """Export episodes to CSV format with error handling"""
        if not episodes:
            # Write empty file with headers
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                f.write("episode_number,theme,iron_chef_name,competitor_name,winner,air_date\n")
            return
        
        fieldnames = ['episode_number', 'theme', 'iron_chef_name', 'competitor_name', 'winner', 'air_date']
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for episode in episodes:
                    # Only write fields that exist in fieldnames
                    row = {k: v for k, v in episode.items() if k in fieldnames}
                    writer.writerow(row)
        except (IOError, OSError) as e:
            raise IOError(f"Failed to write CSV file: {e}")
    
    def _export_recipe_json(self, recipe: Dict, filepath: str):
        """Export recipe to JSON format with error handling"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(recipe, f, indent=2, ensure_ascii=False)
        except (IOError, OSError) as e:
            raise IOError(f"Failed to write JSON file: {e}")
    
    def _export_recipe_text(self, recipe: Dict, filepath: str):
        """Export recipe to readable text format with error handling"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # Header
                f.write("=" * 60 + "\n")
                f.write(f"{recipe.get('recipe_title', 'Recipe')}\n")
                f.write("=" * 60 + "\n\n")
                
                # Episode info
                dish_info = recipe.get('dish_info', {})
                f.write(f"From Episode #{dish_info.get('episode_number', 'Unknown')}: {dish_info.get('theme', 'Unknown')}\n")
                f.write(f"Original Dish: {dish_info.get('dish_name', 'Unknown')}\n")
                chef_type = dish_info.get('chef_type', 'unknown').replace('_', ' ').title()
                f.write(f"Chef Type: {chef_type}\n\n")
                
                # Recipe details
                f.write(f"Servings: {recipe.get('servings', 'Unknown')}\n")
                f.write(f"Prep Time: {recipe.get('prep_time', 'Unknown')} minutes\n")
                f.write(f"Cook Time: {recipe.get('cook_time', 'Unknown')} minutes\n\n")
                
                # Ingredients
                f.write("INGREDIENTS:\n")
                f.write("-" * 40 + "\n")
                for ingredient in recipe.get('ingredients', []):
                    if isinstance(ingredient, dict):
                        prep_note = f" ({ingredient.get('prep', '')})" if ingredient.get('prep') else ""
                        f.write(f"• {ingredient.get('amount', '')} {ingredient.get('item', '')}{prep_note}\n")
                f.write("\n")
                
                # Instructions
                f.write("INSTRUCTIONS:\n")
                f.write("-" * 40 + "\n")
                instructions = recipe.get('instructions', [])
                for i, instruction in enumerate(instructions, 1):
                    f.write(f"{i}. {instruction}\n\n")
                
                # Footer
                generated_date = recipe.get('generated_date', 'Unknown')
                f.write(f"Generated: {generated_date}\n")
                f.write("Iron Chef Japan Recipe Database (Secure Version)\n")
        except (IOError, OSError) as e:
            raise IOError(f"Failed to write text file: {e}")

def main():
    """Command line interface for secure recipe exporter"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Securely export Iron Chef recipes and episode data')
    parser.add_argument('command', choices=['episodes', 'recipe', 'all-recipes', 'theme'], 
                       help='What to export')
    parser.add_argument('--format', choices=['json', 'csv', 'txt'], default='json',
                       help='Output format')
    parser.add_argument('--output', help='Output filename (will be sanitized)')
    parser.add_argument('--output-dir', help='Output directory (must exist)')
    parser.add_argument('--dish-id', type=int, help='Dish ID for recipe export')
    parser.add_argument('--theme', help='Theme name for theme export')
    
    args = parser.parse_args()
    
    try:
        exporter = SecureRecipeExporter(output_dir=args.output_dir)
        
        if args.command == 'episodes':
            filepath = exporter.export_episode_summary(args.format, args.output)
            print(f"Episodes exported to: {filepath}")
        
        elif args.command == 'recipe':
            if not args.dish_id:
                print("Error: --dish-id required for recipe export")
                return 1
            filepath = exporter.export_recipe(args.dish_id, args.format, args.output)
            print(f"Recipe exported to: {filepath}")
        
        elif args.command == 'all-recipes':
            filepath = exporter.export_all_recipes(args.format, args.output)
            print(f"All recipes exported to: {filepath}")
        
        elif args.command == 'theme':
            if not args.theme:
                print("Error: --theme required for theme export")
                return 1
            filepath = exporter.export_dishes_by_theme(args.theme, args.format, args.output)
            print(f"Theme dishes exported to: {filepath}")
    
    except ValueError as e:
        print(f"Validation error: {e}")
        return 1
    except IOError as e:
        print(f"File error: {e}")
        return 1
    except Exception as e:
        print(f"Export failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())