#!/usr/bin/env python3
"""
Iron Chef Japan Episode Database and Recipe Generator
Main demonstration script - MIGRATED to use secure components
"""

import json
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
    print(f"Winner: {episode['winner']}")
    
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
        prep_note = f" ({ing['prep']})" if ing['prep'] else ""
        print(f"  • {ing['amount']} {ing['item']}{prep_note}")
    
    print("\nINSTRUCTIONS:")
    for i, step in enumerate(recipe['instructions'], 1):
        print(f"  {i}. {step}")
    
    print("\nCHEF'S TIPS:")
    for tip in recipe['chef_tips']:
        print(f"  • {tip}")
    
    print(f"\nWINE PAIRING: {recipe['wine_pairing']}")

def safe_operation(operation_name, operation_func, *args, **kwargs):
    """Execute operation with error handling and validation"""
    try:
        return operation_func(*args, **kwargs)
    except ValueError as e:
        print(f"Validation Error in {operation_name}: {e}")
        return None
    except Exception as e:
        print(f"Error in {operation_name}: {e}")
        return None

def main():
    print("Iron Chef Japan Database and Recipe Generator (SECURE VERSION)")
    print("=" * 60)
    
    # Initialize database and load sample data with error handling
    print("\n1. Loading sample data...")
    if not safe_operation("data loading", load_sample_data):
        print("Failed to load sample data. Exiting.")
        return
    
    # Demonstrate database queries with validation and error handling
    try:
        with IronChefDatabaseSecure() as db:
            # Show all themes
            print("\n2. Available themes in database:")
            themes = safe_operation("get themes", db.get_all_themes)
            if themes:
                for theme in themes:
                    print(f"   - {theme}")
            
            # Search for episodes by theme with input validation
            theme_to_search = "Lobster"
            print(f"\n3. Searching for {theme_to_search} episodes...")
            lobster_episodes = safe_operation("search episodes", db.search_episodes_by_theme, theme_to_search)
            if lobster_episodes:
                for ep in lobster_episodes:
                    print(f"   Episode #{ep['episode_number']}: {ep['iron_chef_name']} vs {ep['competitor_name']}")
            
            # Get detailed episode information
            episode_id = 4  # Lobster episode
            print(f"\n4. Getting detailed information for Episode ID {episode_id} (Lobster)...")
            episode = safe_operation("get episode details", db.get_episode_details, episode_id)
            if episode:
                display_episode(episode)
                
                # Generate recipes for dishes with error handling
                print("\n5. Generating recipes for selected dishes...")
                generator = RecipeGenerator()
                
                # Generate recipe for an Iron Chef dish
                if episode['dishes']['iron_chef']:
                    iron_chef_dish = episode['dishes']['iron_chef'][0]
                    recipe = safe_operation(
                        "recipe generation",
                        generator.generate_recipe,
                        iron_chef_dish['dish_name'],
                        iron_chef_dish['main_ingredients'],
                        cuisine_style='Japanese'
                    )
                    if recipe:
                        display_recipe(recipe)
                        
                        # Save recipe to database with validation
                        recipe_id = safe_operation(
                            "recipe saving",
                            generator.save_recipe_to_db,
                            iron_chef_dish['id'],
                            recipe
                        )
                        if recipe_id:
                            print(f"\n   Recipe saved to database with ID: {recipe_id}")
                
                # Generate recipe for a competitor dish
                if episode['dishes']['competitor']:
                    competitor_dish = episode['dishes']['competitor'][0]
                    recipe2 = safe_operation(
                        "recipe generation",
                        generator.generate_recipe,
                        competitor_dish['dish_name'],
                        competitor_dish['main_ingredients'],
                        cuisine_style='Italian'
                    )
                    if recipe2:
                        display_recipe(recipe2)
            
            # Search dishes by ingredient with validation
            ingredient_to_search = 'foie gras'
            print(f"\n6. Searching for dishes containing '{ingredient_to_search}'...")
            foie_gras_dishes = safe_operation("ingredient search", db.get_dishes_by_ingredient, ingredient_to_search)
            if foie_gras_dishes:
                for dish in foie_gras_dishes[:3]:  # Show first 3
                    print(f"   - {dish['dish_name']} (Episode #{dish['episode_number']}: {dish['theme']})")
    
    except Exception as e:
        print(f"Database connection error: {e}")
        print("Please ensure the database is properly initialized.")

def interactive_mode():
    """Run the system in interactive mode with enhanced security validation"""
    print("\nIron Chef Database - Interactive Mode (SECURE VERSION)")
    print("=" * 60)
    
    validator = SecurityValidator()
    
    while True:
        try:
            print("\nOptions:")
            print("1. View all episodes")
            print("2. Search episodes by theme")
            print("3. View episode details")
            print("4. Generate recipe for a dish")
            print("5. Search dishes by ingredient")
            print("6. Exit")
            
            choice = input("\nSelect option (1-6): ").strip()
            
            if not choice:
                continue
            
            # Validate choice input
            try:
                choice_num = validator.validate_integer(choice, min_val=1, max_val=6, field_name="menu choice")
            except ValueError as e:
                print(f"Invalid choice: {e}")
                continue
            
            with IronChefDatabaseSecure() as db:
                if choice == '1':
                    episodes = safe_operation("get all episodes", db.search_episodes_by_theme, '')
                    if episodes:
                        for ep in episodes:
                            print(f"Episode #{ep['episode_number']}: {ep['theme']} - {ep['iron_chef_name']} vs {ep['competitor_name']}")
                    else:
                        print("No episodes found in database.")
                
                elif choice == '2':
                    theme = input("Enter theme to search: ").strip()
                    try:
                        theme = validator.validate_string(theme, max_length=100, field_name="theme")
                        episodes = safe_operation("search by theme", db.search_episodes_by_theme, theme)
                        if episodes:
                            for ep in episodes:
                                print(f"Episode #{ep['episode_number']}: {ep['theme']} - {ep['iron_chef_name']} vs {ep['competitor_name']}")
                        else:
                            print(f"No episodes found with theme containing '{theme}'.")
                    except ValueError as e:
                        print(f"Invalid theme input: {e}")
                
                elif choice == '3':
                    try:
                        ep_id_input = input("Enter episode ID: ").strip()
                        ep_id = validator.validate_integer(ep_id_input, min_val=1, field_name="episode ID")
                        episode = safe_operation("get episode details", db.get_episode_details, ep_id)
                        if episode:
                            display_episode(episode)
                        else:
                            print(f"Episode with ID {ep_id} not found.")
                    except ValueError as e:
                        print(f"Invalid episode ID: {e}")
                    except Exception as e:
                        print(f"Error retrieving episode: {e}")
                
                elif choice == '4':
                    try:
                        ep_id_input = input("Enter episode ID: ").strip()
                        ep_id = validator.validate_integer(ep_id_input, min_val=1, field_name="episode ID")
                        episode = safe_operation("get episode details", db.get_episode_details, ep_id)
                        if not episode:
                            print(f"Episode with ID {ep_id} not found.")
                            continue
                            
                        display_episode(episode)
                        
                        chef_type = input("\nGenerate recipe for (i)ron chef or (c)ompetitor dish? ").lower().strip()
                        chef_type = validator.validate_string(chef_type, max_length=1, field_name="chef type")
                        if chef_type not in ['i', 'c']:
                            print("Please enter 'i' for Iron Chef or 'c' for competitor.")
                            continue
                            
                        dishes = episode['dishes']['iron_chef'] if chef_type == 'i' else episode['dishes']['competitor']
                        
                        if not dishes:
                            print("No dishes found for this chef type.")
                            continue
                            
                        print("\nAvailable dishes:")
                        for i, dish in enumerate(dishes):
                            print(f"{i+1}. {dish['dish_name']}")
                        
                        dish_num_input = input("Select dish number: ").strip()
                        dish_num = validator.validate_integer(dish_num_input, min_val=1, max_val=len(dishes), field_name="dish number") - 1
                        
                        if 0 <= dish_num < len(dishes):
                            dish = dishes[dish_num]
                            generator = RecipeGenerator()
                            
                            # Determine cuisine style based on chef type and episode context
                            cuisine_style = 'Japanese'
                            if chef_type == 'c':
                                # Try to infer cuisine from dish name or use French as default
                                dish_name_lower = dish['dish_name'].lower()
                                if 'risotto' in dish_name_lower or 'pasta' in dish_name_lower:
                                    cuisine_style = 'Italian'
                                else:
                                    cuisine_style = 'French'
                            
                            recipe = safe_operation(
                                "recipe generation",
                                generator.generate_recipe,
                                dish['dish_name'],
                                dish['main_ingredients'],
                                cuisine_style=cuisine_style
                            )
                            if recipe:
                                display_recipe(recipe)
                                
                                save = input("\nSave recipe to database? (y/n): ").lower().strip()
                                save = validator.validate_string(save, max_length=1, field_name="save choice")
                                if save == 'y':
                                    recipe_id = safe_operation(
                                        "recipe saving",
                                        generator.save_recipe_to_db,
                                        dish['id'],
                                        recipe
                                    )
                                    if recipe_id:
                                        print(f"Recipe saved with ID: {recipe_id}")
                        else:
                            print("Invalid dish number selected.")
                            
                    except ValueError as e:
                        print(f"Invalid input: {e}")
                    except Exception as e:
                        print(f"Error generating recipe: {e}")
                
                elif choice == '5':
                    ingredient = input("Enter ingredient to search: ").strip()
                    try:
                        ingredient = validator.validate_string(ingredient, max_length=100, field_name="ingredient")
                        if ingredient:
                            dishes = safe_operation("ingredient search", db.get_dishes_by_ingredient, ingredient)
                            if dishes:
                                print(f"\nDishes containing '{ingredient}':")
                                for dish in dishes:
                                    print(f"- {dish['dish_name']} (Episode #{dish['episode_number']}: {dish['theme']})")
                            else:
                                print(f"No dishes found containing '{ingredient}'.")
                        else:
                            print("Please enter an ingredient to search for.")
                    except ValueError as e:
                        print(f"Invalid ingredient input: {e}")
                
                elif choice == '6':
                    print("Exiting...")
                    break
                
                else:
                    print("Invalid option. Please select 1-6.")
                    
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except EOFError:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            print("Please try again.")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        interactive_mode()
    else:
        main()