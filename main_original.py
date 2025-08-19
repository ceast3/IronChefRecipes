#!/usr/bin/env python3
"""
Iron Chef Japan Episode Database and Recipe Generator
Main demonstration script
"""

import json
from iron_chef_database import IronChefDatabase
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

def main():
    print("Iron Chef Japan Database and Recipe Generator")
    print("=" * 50)
    
    # Initialize database and load sample data
    print("\n1. Loading sample data...")
    load_sample_data()
    
    # Demonstrate database queries
    with IronChefDatabase() as db:
        # Show all themes
        print("\n2. Available themes in database:")
        themes = db.get_all_themes()
        for theme in themes:
            print(f"   - {theme}")
        
        # Search for episodes by theme
        print("\n3. Searching for Lobster episodes...")
        lobster_episodes = db.search_episodes_by_theme("Lobster")
        for ep in lobster_episodes:
            print(f"   Episode #{ep['episode_number']}: {ep['iron_chef_name']} vs {ep['competitor_name']}")
        
        # Get detailed episode information
        print("\n4. Getting detailed information for Episode #150 (Lobster)...")
        episode = db.get_episode_details(4)  # Lobster episode
        display_episode(episode)
        
        # Generate recipes for dishes
        print("\n5. Generating recipes for selected dishes...")
        generator = RecipeGenerator()
        
        # Generate recipe for an Iron Chef dish
        iron_chef_dish = episode['dishes']['iron_chef'][0]
        recipe = generator.generate_recipe(
            iron_chef_dish['dish_name'],
            iron_chef_dish['main_ingredients'],
            cuisine_style='Japanese'
        )
        display_recipe(recipe)
        
        # Save recipe to database
        recipe_id = generator.save_recipe_to_db(iron_chef_dish['id'], recipe)
        print(f"\n   Recipe saved to database with ID: {recipe_id}")
        
        # Generate recipe for a competitor dish
        competitor_dish = episode['dishes']['competitor'][0]
        recipe2 = generator.generate_recipe(
            competitor_dish['dish_name'],
            competitor_dish['main_ingredients'],
            cuisine_style='Italian'
        )
        display_recipe(recipe2)
        
        # Search dishes by ingredient
        print("\n6. Searching for dishes containing 'foie gras'...")
        foie_gras_dishes = db.get_dishes_by_ingredient('foie gras')
        for dish in foie_gras_dishes[:3]:  # Show first 3
            print(f"   - {dish['dish_name']} (Episode #{dish['episode_number']}: {dish['theme']})")

def interactive_mode():
    """Run the system in interactive mode"""
    print("\nIron Chef Database - Interactive Mode")
    print("=" * 50)
    
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
                
                with IronChefDatabase() as db:
                    if choice == '1':
                        episodes = db.search_episodes_by_theme('')  # Get all
                        if episodes:
                            for ep in episodes:
                                print(f"Episode #{ep['episode_number']}: {ep['theme']} - {ep['iron_chef_name']} vs {ep['competitor_name']}")
                        else:
                            print("No episodes found in database.")
                    
                    elif choice == '2':
                        theme = input("Enter theme to search: ").strip()
                        episodes = db.search_episodes_by_theme(theme)
                        if episodes:
                            for ep in episodes:
                                print(f"Episode #{ep['episode_number']}: {ep['theme']} - {ep['iron_chef_name']} vs {ep['competitor_name']}")
                        else:
                            print(f"No episodes found with theme containing '{theme}'.")
                    
                    elif choice == '3':
                        try:
                            ep_id = int(input("Enter episode ID: "))
                            episode = db.get_episode_details(ep_id)
                            if episode:
                                display_episode(episode)
                            else:
                                print(f"Episode with ID {ep_id} not found.")
                        except ValueError:
                            print("Please enter a valid episode ID number.")
                        except Exception as e:
                            print(f"Error retrieving episode: {e}")
                    
                    elif choice == '4':
                        try:
                            ep_id = int(input("Enter episode ID: "))
                            episode = db.get_episode_details(ep_id)
                            if not episode:
                                print(f"Episode with ID {ep_id} not found.")
                                continue
                                
                            display_episode(episode)
                            
                            chef_type = input("\nGenerate recipe for (i)ron chef or (c)ompetitor dish? ").lower().strip()
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
                            
                            dish_num = int(input("Select dish number: ")) - 1
                            if 0 <= dish_num < len(dishes):
                                dish = dishes[dish_num]
                                generator = RecipeGenerator()
                                
                                # Determine cuisine style based on chef type and episode context
                                cuisine_style = 'Japanese'
                                if chef_type == 'c':
                                    # Try to infer cuisine from dish name or use French as default
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
                                
                                save = input("\nSave recipe to database? (y/n): ").lower().strip()
                                if save == 'y':
                                    recipe_id = generator.save_recipe_to_db(dish['id'], recipe)
                                    print(f"Recipe saved with ID: {recipe_id}")
                            else:
                                print("Invalid dish number selected.")
                                
                        except ValueError:
                            print("Please enter valid numbers.")
                        except Exception as e:
                            print(f"Error generating recipe: {e}")
                    
                    elif choice == '5':
                        ingredient = input("Enter ingredient to search: ").strip()
                        if ingredient:
                            dishes = db.get_dishes_by_ingredient(ingredient)
                            if dishes:
                                print(f"\nDishes containing '{ingredient}':")
                                for dish in dishes:
                                    print(f"- {dish['dish_name']} (Episode #{dish['episode_number']}: {dish['theme']})")
                            else:
                                print(f"No dishes found containing '{ingredient}'.")
                        else:
                            print("Please enter an ingredient to search for.")
                    
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