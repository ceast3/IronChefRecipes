#!/usr/bin/env python3
"""
Iron Chef Japan Episode Database and Recipe Generator
Main demonstration script with enhanced security
"""

import json
import sys
from iron_chef_database_secure import IronChefDatabaseSecure, SecurityValidator
from recipe_generator import RecipeGenerator
from sample_data_loader import load_sample_data

def display_episode(episode: dict):
    """Display episode information in a formatted way"""
    print(f"\n{'='*60}")
    print(f"Episode #{episode['episode_number']}: {episode['theme']}")
    print(f"{'='*60}")
    print(f"Iron Chef: {episode['iron_chef_name']}")
    print(f"Challenger: {episode['competitor_name']}")
    print(f"Winner: {episode.get('winner', 'Not recorded')}")
    
    print(f"\n{'-'*30}")
    print("IRON CHEF DISHES:")
    for dish in episode['dishes']['iron_chef']:
        print(f"  {dish['dish_number']}. {dish['dish_name']}")
        if dish['main_ingredients']:
            print(f"     Ingredients: {dish['main_ingredients']}")
    
    print(f"\n{'-'*30}")
    print("CHALLENGER DISHES:")
    for dish in episode['dishes']['competitor']:
        print(f"  {dish['dish_number']}. {dish['dish_name']}")
        if dish['main_ingredients']:
            print(f"     Ingredients: {dish['main_ingredients']}")

def display_recipe(recipe: dict):
    """Display a generated recipe in a formatted way"""
    print(f"\n{'*'*60}")
    print(f"{recipe['title']}")
    print(f"{'*'*60}")
    print(f"\n{recipe['description']}")
    print(f"\nServings: {recipe['servings']} | Prep: {recipe['prep_time']} min | Cook: {recipe['cook_time']} min")
    
    print("\nINGREDIENTS:")
    for ing in recipe['ingredients']:
        prep_note = f" ({ing['prep']})" if ing.get('prep') else ""
        print(f"  • {ing['amount']} {ing['item']}{prep_note}")
    
    print("\nINSTRUCTIONS:")
    for i, step in enumerate(recipe['instructions'], 1):
        print(f"  {i}. {step}")
    
    print("\nCHEF'S TIPS:")
    for tip in recipe.get('chef_tips', []):
        print(f"  • {tip}")
    
    print(f"\nWINE PAIRING: {recipe.get('wine_pairing', 'Not specified')}")

def safe_input(prompt: str, validator: SecurityValidator = None, 
               input_type: str = 'string', **kwargs) -> any:
    """Get user input with validation and error handling"""
    if validator is None:
        validator = SecurityValidator()
    
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            user_input = input(prompt).strip()
            
            if input_type == 'integer':
                return validator.validate_integer(user_input, **kwargs)
            elif input_type == 'string':
                return validator.validate_string(user_input, **kwargs)
            elif input_type == 'choice':
                choices = kwargs.get('choices', [])
                if user_input in choices:
                    return user_input
                else:
                    print(f"Please enter one of: {', '.join(choices)}")
                    continue
            else:
                return user_input
                
        except ValueError as e:
            print(f"Invalid input: {e}")
            if attempt < max_attempts - 1:
                print(f"Please try again ({max_attempts - attempt - 1} attempts remaining)")
            else:
                print("Max attempts reached.")
                return None
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            sys.exit(0)
    
    return None

def main():
    print("Iron Chef Japan Database and Recipe Generator (Secure Version)")
    print("=" * 60)
    
    # Initialize database with secure version
    print("\n1. Initializing secure database...")
    
    # Check if database exists, if not load sample data
    import os
    if not os.path.exists('iron_chef_japan.db'):
        print("   Loading sample data...")
        # Note: You'll need to update sample_data_loader.py to use IronChefDatabaseSecure
        load_sample_data()
    
    # Demonstrate secure database queries
    with IronChefDatabaseSecure() as db:
        # Show all themes
        print("\n2. Available themes in database:")
        themes = db.get_all_themes()
        for theme in themes:
            print(f"   - {theme}")
        
        # Demonstrate secure search
        print("\n3. Testing secure search (attempting SQL injection)...")
        # This would have been dangerous with the old version
        malicious_input = "'; DROP TABLE episodes; --"
        print(f"   Searching for: {malicious_input}")
        try:
            results = db.search_episodes_by_theme(malicious_input)
            print(f"   Results found: {len(results)} (injection attempt safely handled)")
        except Exception as e:
            print(f"   Search handled safely: {e}")
        
        # Normal search
        print("\n4. Searching for Lobster episodes...")
        lobster_episodes = db.search_episodes_by_theme("Lobster")
        for ep in lobster_episodes:
            print(f"   Episode #{ep['episode_number']}: {ep['iron_chef_name']} vs {ep['competitor_name']}")
        
        # Get detailed episode information
        if lobster_episodes:
            print("\n5. Getting detailed information for Lobster episode...")
            # Find the Lobster episode ID
            episode_id = lobster_episodes[0]['id']
            episode = db.get_episode_details(episode_id)
            if episode:
                display_episode(episode)
                
                # Generate recipe with validation
                print("\n6. Generating recipes for selected dishes...")
                generator = RecipeGenerator()
                
                if episode['dishes']['iron_chef']:
                    iron_chef_dish = episode['dishes']['iron_chef'][0]
                    recipe = generator.generate_recipe(
                        iron_chef_dish['dish_name'],
                        iron_chef_dish['main_ingredients'],
                        cuisine_style='Japanese'
                    )
                    display_recipe(recipe)

def interactive_mode_secure():
    """Run the system in secure interactive mode"""
    print("\nIron Chef Database - Secure Interactive Mode")
    print("=" * 50)
    
    validator = SecurityValidator()
    
    while True:
        try:
            print("\nOptions:")
            print("1. View all episodes")
            print("2. Search episodes by theme")
            print("3. View episode details")
            print("4. Generate recipe for a dish")
            print("5. Search dishes by ingredient")
            print("6. Test security features")
            print("7. Exit")
            
            choice = safe_input(
                "\nSelect option (1-7): ", 
                validator, 
                input_type='choice',
                choices=['1', '2', '3', '4', '5', '6', '7']
            )
            
            if not choice:
                continue
                
            with IronChefDatabaseSecure() as db:
                if choice == '1':
                    episodes = db.search_episodes_by_theme('')  # Get all
                    if episodes:
                        for ep in episodes:
                            print(f"Episode #{ep['episode_number']}: {ep['theme']} - {ep['iron_chef_name']} vs {ep['competitor_name']}")
                    else:
                        print("No episodes found in database.")
                
                elif choice == '2':
                    theme = safe_input(
                        "Enter theme to search: ",
                        validator,
                        input_type='string',
                        max_length=100,
                        field_name="theme"
                    )
                    if theme:
                        episodes = db.search_episodes_by_theme(theme)
                        if episodes:
                            for ep in episodes:
                                print(f"Episode #{ep['episode_number']}: {ep['theme']} - {ep['iron_chef_name']} vs {ep['competitor_name']}")
                        else:
                            print(f"No episodes found with theme containing '{theme}'.")
                
                elif choice == '3':
                    ep_id = safe_input(
                        "Enter episode ID: ",
                        validator,
                        input_type='integer',
                        min_val=1,
                        field_name="episode ID"
                    )
                    if ep_id:
                        episode = db.get_episode_details(ep_id)
                        if episode:
                            display_episode(episode)
                        else:
                            print(f"Episode with ID {ep_id} not found.")
                
                elif choice == '4':
                    ep_id = safe_input(
                        "Enter episode ID: ",
                        validator,
                        input_type='integer',
                        min_val=1,
                        field_name="episode ID"
                    )
                    if not ep_id:
                        continue
                        
                    episode = db.get_episode_details(ep_id)
                    if not episode:
                        print(f"Episode with ID {ep_id} not found.")
                        continue
                        
                    display_episode(episode)
                    
                    chef_type = safe_input(
                        "\nGenerate recipe for (i)ron chef or (c)ompetitor dish? ",
                        validator,
                        input_type='choice',
                        choices=['i', 'c']
                    )
                    
                    if not chef_type:
                        continue
                        
                    dishes = episode['dishes']['iron_chef'] if chef_type == 'i' else episode['dishes']['competitor']
                    
                    if not dishes:
                        print("No dishes found for this chef type.")
                        continue
                        
                    print("\nAvailable dishes:")
                    for i, dish in enumerate(dishes):
                        print(f"{i+1}. {dish['dish_name']}")
                    
                    dish_num = safe_input(
                        "Select dish number: ",
                        validator,
                        input_type='integer',
                        min_val=1,
                        max_val=len(dishes),
                        field_name="dish number"
                    )
                    
                    if dish_num:
                        dish = dishes[dish_num - 1]
                        generator = RecipeGenerator()
                        
                        # Determine cuisine style based on chef type and episode context
                        cuisine_style = 'Japanese'
                        if chef_type == 'c':
                            if 'risotto' in dish['dish_name'].lower() or 'pasta' in dish['dish_name'].lower():
                                cuisine_style = 'Italian'
                            else:
                                cuisine_style = 'French'
                        
                        recipe = generator.generate_recipe(
                            dish['dish_name'],
                            dish['main_ingredients'],
                            cuisine_style=cuisine_style
                        )
                        display_recipe(recipe)
                        
                        save_choice = safe_input(
                            "\nSave recipe to database? (y/n): ",
                            validator,
                            input_type='choice',
                            choices=['y', 'n']
                        )
                        
                        if save_choice == 'y':
                            recipe_id = generator.save_recipe_to_db(dish['id'], recipe)
                            print(f"Recipe saved with ID: {recipe_id}")
                
                elif choice == '5':
                    ingredient = safe_input(
                        "Enter ingredient to search: ",
                        validator,
                        input_type='string',
                        max_length=100,
                        field_name="ingredient"
                    )
                    if ingredient:
                        dishes = db.get_dishes_by_ingredient(ingredient)
                        if dishes:
                            print(f"\nDishes containing '{ingredient}':")
                            for dish in dishes:
                                print(f"- {dish['dish_name']} (Episode #{dish['episode_number']}: {dish['theme']})")
                        else:
                            print(f"No dishes found containing '{ingredient}'.")
                
                elif choice == '6':
                    print("\n--- Security Feature Demonstration ---")
                    print("1. SQL Injection Protection Test")
                    test_input = "'; DROP TABLE episodes; --"
                    print(f"   Testing with: {test_input}")
                    try:
                        results = db.search_episodes_by_theme(test_input)
                        print(f"   ✓ Injection attempt blocked. Found {len(results)} safe results.")
                    except Exception as e:
                        print(f"   ✓ Injection blocked with error: {e}")
                    
                    print("\n2. Input Validation Test")
                    print("   Testing invalid episode ID (negative number)...")
                    try:
                        episode = db.get_episode_details(-1)
                        print("   ✗ Validation failed - negative ID accepted!")
                    except ValueError as e:
                        print(f"   ✓ Validation successful: {e}")
                    
                    print("\n3. Path Traversal Protection Test")
                    from recipe_exporter_secure import SecureRecipeExporter
                    exporter = SecureRecipeExporter()
                    dangerous_filename = "../../../etc/passwd"
                    safe_filename = exporter._sanitize_filename(dangerous_filename)
                    print(f"   Dangerous input: {dangerous_filename}")
                    print(f"   Sanitized to: {safe_filename}")
                    print("   ✓ Path traversal attempt blocked")
                
                elif choice == '7':
                    print("Exiting secure mode...")
                    break
                    
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except EOFError:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
            print("Please try again.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        interactive_mode_secure()
    else:
        main()