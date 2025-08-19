#!/usr/bin/env python3
"""
Recipe Export Utilities for Iron Chef Database
Supports exporting recipes and episode data to various formats
"""

import json
import csv
from datetime import datetime
from typing import Dict, List
from iron_chef_database import IronChefDatabase

class RecipeExporter:
    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def export_episode_summary(self, output_format='json', filename=None):
        """Export a summary of all episodes"""
        if filename is None:
            filename = f"iron_chef_episodes_{self.timestamp}.{output_format.lower()}"
        
        with IronChefDatabase() as db:
            episodes = db.search_episodes_by_theme('')  # Get all episodes
            
            if output_format.lower() == 'json':
                self._export_episodes_json(episodes, filename)
            elif output_format.lower() == 'csv':
                self._export_episodes_csv(episodes, filename)
            else:
                raise ValueError("Supported formats: json, csv")
        
        return filename
    
    def export_recipe(self, dish_id: int, output_format='json', filename=None):
        """Export a specific recipe"""
        if filename is None:
            filename = f"recipe_{dish_id}_{self.timestamp}.{output_format.lower()}"
        
        with IronChefDatabase() as db:
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
            
            if output_format.lower() == 'json':
                self._export_recipe_json(recipe_data, filename)
            elif output_format.lower() == 'txt':
                self._export_recipe_text(recipe_data, filename)
            else:
                raise ValueError("Supported formats: json, txt")
        
        return filename
    
    def export_all_recipes(self, output_format='json', filename=None):
        """Export all recipes in the database"""
        if filename is None:
            filename = f"all_recipes_{self.timestamp}.{output_format.lower()}"
        
        with IronChefDatabase() as db:
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
                recipe['ingredients'] = json.loads(recipe['ingredients'])
                recipe['instructions'] = json.loads(recipe['instructions'])
            
            if output_format.lower() == 'json':
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(recipes, f, indent=2, ensure_ascii=False)
            else:
                raise ValueError("Supported formats: json")
        
        return filename
    
    def export_dishes_by_theme(self, theme: str, output_format='json', filename=None):
        """Export all dishes for a specific theme"""
        if filename is None:
            safe_theme = theme.replace(' ', '_').lower()
            filename = f"dishes_{safe_theme}_{self.timestamp}.{output_format.lower()}"
        
        with IronChefDatabase() as db:
            episodes = db.search_episodes_by_theme(theme)
            if not episodes:
                raise ValueError(f"No episodes found for theme: {theme}")
            
            theme_data = {
                'theme': theme,
                'episodes': []
            }
            
            for episode in episodes:
                episode_details = db.get_episode_details(episode['id'])
                theme_data['episodes'].append(episode_details)
            
            if output_format.lower() == 'json':
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(theme_data, f, indent=2, ensure_ascii=False)
            else:
                raise ValueError("Supported formats: json")
        
        return filename
    
    def _export_episodes_json(self, episodes: List[Dict], filename: str):
        """Export episodes to JSON format"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(episodes, f, indent=2, ensure_ascii=False)
    
    def _export_episodes_csv(self, episodes: List[Dict], filename: str):
        """Export episodes to CSV format"""
        if not episodes:
            return
        
        fieldnames = ['episode_number', 'theme', 'iron_chef_name', 'competitor_name', 'winner', 'air_date']
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for episode in episodes:
                # Only write fields that exist in fieldnames
                row = {k: v for k, v in episode.items() if k in fieldnames}
                writer.writerow(row)
    
    def _export_recipe_json(self, recipe: Dict, filename: str):
        """Export recipe to JSON format"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(recipe, f, indent=2, ensure_ascii=False)
    
    def _export_recipe_text(self, recipe: Dict, filename: str):
        """Export recipe to readable text format"""
        with open(filename, 'w', encoding='utf-8') as f:
            # Header
            f.write("=" * 60 + "\n")
            f.write(f"{recipe['recipe_title']}\n")
            f.write("=" * 60 + "\n\n")
            
            # Episode info
            dish_info = recipe['dish_info']
            f.write(f"From Episode #{dish_info['episode_number']}: {dish_info['theme']}\n")
            f.write(f"Original Dish: {dish_info['dish_name']}\n")
            f.write(f"Chef Type: {dish_info['chef_type'].replace('_', ' ').title()}\n\n")
            
            # Recipe details
            f.write(f"Servings: {recipe['servings']}\n")
            f.write(f"Prep Time: {recipe['prep_time']} minutes\n")
            f.write(f"Cook Time: {recipe['cook_time']} minutes\n\n")
            
            # Ingredients
            f.write("INGREDIENTS:\n")
            f.write("-" * 40 + "\n")
            for ingredient in recipe['ingredients']:
                prep_note = f" ({ingredient['prep']})" if ingredient['prep'] else ""
                f.write(f"• {ingredient['amount']} {ingredient['item']}{prep_note}\n")
            f.write("\n")
            
            # Instructions
            f.write("INSTRUCTIONS:\n")
            f.write("-" * 40 + "\n")
            for i, instruction in enumerate(recipe['instructions'], 1):
                f.write(f"{i}. {instruction}\n\n")
            
            # Chef Tips
            if 'chef_tips' in recipe:
                chef_tips = json.loads(recipe.get('chef_tips', '[]')) if isinstance(recipe.get('chef_tips'), str) else recipe.get('chef_tips', [])
                if chef_tips:
                    f.write("CHEF'S TIPS:\n")
                    f.write("-" * 40 + "\n")
                    for tip in chef_tips:
                        f.write(f"• {tip}\n")
                    f.write("\n")
            
            # Wine pairing
            if 'wine_pairing' in recipe:
                f.write(f"WINE PAIRING: {recipe['wine_pairing']}\n\n")
            
            # Footer
            generated_date = recipe.get('generated_date', 'Unknown')
            f.write(f"Generated: {generated_date}\n")
            f.write("Iron Chef Japan Recipe Database\n")

def main():
    """Command line interface for recipe exporter"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Export Iron Chef recipes and episode data')
    parser.add_argument('command', choices=['episodes', 'recipe', 'all-recipes', 'theme'], 
                       help='What to export')
    parser.add_argument('--format', choices=['json', 'csv', 'txt'], default='json',
                       help='Output format')
    parser.add_argument('--output', help='Output filename')
    parser.add_argument('--dish-id', type=int, help='Dish ID for recipe export')
    parser.add_argument('--theme', help='Theme name for theme export')
    
    args = parser.parse_args()
    
    exporter = RecipeExporter()
    
    try:
        if args.command == 'episodes':
            filename = exporter.export_episode_summary(args.format, args.output)
            print(f"Episodes exported to: {filename}")
        
        elif args.command == 'recipe':
            if not args.dish_id:
                print("Error: --dish-id required for recipe export")
                return
            filename = exporter.export_recipe(args.dish_id, args.format, args.output)
            print(f"Recipe exported to: {filename}")
        
        elif args.command == 'all-recipes':
            filename = exporter.export_all_recipes(args.format, args.output)
            print(f"All recipes exported to: {filename}")
        
        elif args.command == 'theme':
            if not args.theme:
                print("Error: --theme required for theme export")
                return
            filename = exporter.export_dishes_by_theme(args.theme, args.format, args.output)
            print(f"Theme dishes exported to: {filename}")
            
    except Exception as e:
        print(f"Export failed: {e}")

if __name__ == "__main__":
    main()