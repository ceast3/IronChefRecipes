#!/usr/bin/env python3
"""
Recipe Export Utilities for Iron Chef Database - MIGRATED to use secure components
Supports exporting recipes and episode data to various formats with security validation
"""

import json
import csv
import os
from datetime import datetime
from typing import Dict, List
from iron_chef_database_secure import IronChefDatabaseSecure, SecurityValidator
from recipe_exporter_secure import SecureRecipeExporter

class RecipeExporter:
    """Legacy API wrapper that delegates to SecureRecipeExporter for backward compatibility"""
    
    def __init__(self, output_dir: str = None):
        """Initialize with secure exporter backend"""
        self.secure_exporter = SecureRecipeExporter(output_dir)
        self.timestamp = self.secure_exporter.timestamp
        self.validator = SecurityValidator()
    
    def export_episode_summary(self, output_format='json', filename=None):
        """Export a summary of all episodes using secure backend"""
        try:
            # Validate inputs
            if output_format not in ['json', 'csv']:
                raise ValueError("Supported formats: json, csv")
            
            if filename:
                filename = self.validator.validate_string(
                    filename, max_length=200, field_name="filename"
                )
            
            # Delegate to secure exporter
            filepath = self.secure_exporter.export_episode_summary(output_format, filename)
            
            # Return just the filename for backward compatibility
            return os.path.basename(filepath)
            
        except Exception as e:
            raise Exception(f"Episode export failed: {e}")
    
    def export_recipe(self, dish_id: int, output_format='json', filename=None):
        """Export a specific recipe using secure backend"""
        try:
            # Validate inputs
            dish_id = self.validator.validate_integer(dish_id, min_val=1, field_name="dish ID")
            
            if output_format not in ['json', 'txt']:
                raise ValueError("Supported formats: json, txt")
            
            if filename:
                filename = self.validator.validate_string(
                    filename, max_length=200, field_name="filename"
                )
            
            # Delegate to secure exporter
            filepath = self.secure_exporter.export_recipe(dish_id, output_format, filename)
            
            # Return just the filename for backward compatibility
            return os.path.basename(filepath)
            
        except Exception as e:
            raise Exception(f"Recipe export failed: {e}")
    
    def export_all_recipes(self, output_format='json', filename=None):
        """Export all recipes in the database using secure backend"""
        try:
            # Validate inputs
            if output_format not in ['json']:
                raise ValueError("Supported formats: json")
            
            if filename:
                filename = self.validator.validate_string(
                    filename, max_length=200, field_name="filename"
                )
            
            # Delegate to secure exporter
            filepath = self.secure_exporter.export_all_recipes(output_format, filename)
            
            # Return just the filename for backward compatibility
            return os.path.basename(filepath)
            
        except Exception as e:
            raise Exception(f"All recipes export failed: {e}")
    
    def export_dishes_by_theme(self, theme: str, output_format='json', filename=None):
        """Export all dishes for a specific theme using secure backend"""
        try:
            # Validate inputs
            theme = self.validator.validate_string(theme, max_length=100, field_name="theme")
            if not theme:
                raise ValueError("Theme is required")
            
            if output_format not in ['json']:
                raise ValueError("Supported formats: json")
            
            if filename:
                filename = self.validator.validate_string(
                    filename, max_length=200, field_name="filename"
                )
            
            # Delegate to secure exporter
            filepath = self.secure_exporter.export_dishes_by_theme(theme, output_format, filename)
            
            # Return just the filename for backward compatibility
            return os.path.basename(filepath)
            
        except Exception as e:
            raise Exception(f"Theme export failed: {e}")
    
    # Legacy methods for backward compatibility
    def _export_episodes_json(self, episodes: List[Dict], filename: str):
        """Legacy method - redirects to secure implementation"""
        # This method is no longer directly used but kept for compatibility
        # The secure exporter handles this internally
        pass
    
    def _export_episodes_csv(self, episodes: List[Dict], filename: str):
        """Legacy method - redirects to secure implementation"""
        # This method is no longer directly used but kept for compatibility
        # The secure exporter handles this internally
        pass
    
    def _export_recipe_json(self, recipe: Dict, filename: str):
        """Legacy method - redirects to secure implementation"""
        # This method is no longer directly used but kept for compatibility
        # The secure exporter handles this internally
        pass
    
    def _export_recipe_text(self, recipe: Dict, filename: str):
        """Legacy method - redirects to secure implementation"""
        # This method is no longer directly used but kept for compatibility
        # The secure exporter handles this internally
        pass

def main():
    """Command line interface for recipe exporter with enhanced security"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Export Iron Chef recipes and episode data (SECURE VERSION)')
    parser.add_argument('command', choices=['episodes', 'recipe', 'all-recipes', 'theme'], 
                       help='What to export')
    parser.add_argument('--format', choices=['json', 'csv', 'txt'], default='json',
                       help='Output format')
    parser.add_argument('--output', help='Output filename')
    parser.add_argument('--dish-id', type=int, help='Dish ID for recipe export')
    parser.add_argument('--theme', help='Theme name for theme export')
    parser.add_argument('--output-dir', help='Output directory (defaults to current/exports)')
    
    args = parser.parse_args()
    
    validator = SecurityValidator()
    
    try:
        # Initialize with secure exporter
        exporter = RecipeExporter(args.output_dir)
        
        if args.command == 'episodes':
            filename = exporter.export_episode_summary(args.format, args.output)
            print(f"Episodes exported to: {filename}")
        
        elif args.command == 'recipe':
            if not args.dish_id:
                print("Error: --dish-id required for recipe export")
                return
            
            # Validate dish ID
            dish_id = validator.validate_integer(args.dish_id, min_val=1, field_name="dish ID")
            filename = exporter.export_recipe(dish_id, args.format, args.output)
            print(f"Recipe exported to: {filename}")
        
        elif args.command == 'all-recipes':
            filename = exporter.export_all_recipes(args.format, args.output)
            print(f"All recipes exported to: {filename}")
        
        elif args.command == 'theme':
            if not args.theme:
                print("Error: --theme required for theme export")
                return
            
            # Validate theme
            theme = validator.validate_string(args.theme, max_length=100, field_name="theme")
            filename = exporter.export_dishes_by_theme(theme, args.format, args.output)
            print(f"Theme dishes exported to: {filename}")
            
    except ValueError as e:
        print(f"Validation error: {e}")
    except Exception as e:
        print(f"Export failed: {e}")

# For direct access to the secure exporter
class DirectSecureExporter:
    """Direct access to SecureRecipeExporter without legacy compatibility layer"""
    
    def __init__(self, output_dir: str = None):
        self.exporter = SecureRecipeExporter(output_dir)
    
    def export_episode_summary(self, output_format: str = 'json', filename: str = None) -> str:
        """Export episodes with full path return"""
        return self.exporter.export_episode_summary(output_format, filename)
    
    def export_recipe(self, dish_id: int, output_format: str = 'json', filename: str = None) -> str:
        """Export recipe with full path return"""
        return self.exporter.export_recipe(dish_id, output_format, filename)
    
    def export_all_recipes(self, output_format: str = 'json', filename: str = None) -> str:
        """Export all recipes with full path return"""
        return self.exporter.export_all_recipes(output_format, filename)
    
    def export_dishes_by_theme(self, theme: str, output_format: str = 'json', filename: str = None) -> str:
        """Export theme dishes with full path return"""
        return self.exporter.export_dishes_by_theme(theme, output_format, filename)

if __name__ == "__main__":
    main()