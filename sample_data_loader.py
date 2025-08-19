from iron_chef_database_secure import IronChefDatabaseSecure, SecurityValidator
import json

def load_sample_data():
    """Load sample Iron Chef Japan data into the database using secure database"""
    
    validator = SecurityValidator()
    
    try:
        with IronChefDatabaseSecure() as db:
            # Check if database is already initialized
            try:
                db.cursor.execute("SELECT COUNT(*) FROM iron_chefs")
                chef_count = db.cursor.fetchone()[0]
                if chef_count > 0:
                    print(f"Database already exists with {chef_count} iron chefs, skipping data load...")
                    print("Data loading completed successfully.")
                    return True
                else:
                    db_exists = True
                    print("Database exists but is empty, loading data...")
            except:
                # Database doesn't exist, initialize it
                db.initialize_database()
                db_exists = False
                print("Database initialized, loading data...")
            
            # Add Iron Chefs with validation
            iron_chefs = {}
            
            iron_chef_data = [
                ("Chen Kenichi", "Iron Chef Chinese", "Szechuan Cuisine", "1993-1999"),
                ("Hiroyuki Sakai", "Iron Chef French", "French Cuisine", "1994-1999"),
                ("Masaharu Morimoto", "Iron Chef Japanese", "Japanese Cuisine", "1998-1999"),
                ("Rokusaburo Michiba", "Iron Chef Japanese", "Traditional Japanese", "1993-1996"),
                ("Koumei Nakamura", "Iron Chef Japanese", "Japanese Cuisine", "1996-1998")
            ]
            
            for name, title, specialty, active_years in iron_chef_data:
                try:
                    # Validate each field before adding
                    validated_name = validator.validate_string(name, max_length=100, field_name="chef name")
                    validated_title = validator.validate_string(title, max_length=100, field_name="title")
                    validated_specialty = validator.validate_string(specialty, max_length=100, field_name="specialty")
                    validated_years = validator.validate_string(active_years, max_length=50, field_name="active years")
                    
                    chef_id = db.add_iron_chef(validated_name, validated_title, validated_specialty, validated_years)
                    
                    # Store with simple key for easier reference
                    key = name.split()[1].lower()  # Use last name as key
                    iron_chefs[key] = chef_id
                    
                except ValueError as e:
                    print(f"Validation error adding Iron Chef {name}: {e}")
                    continue
                except Exception as e:
                    print(f"Error adding Iron Chef {name}: {e}")
                    continue
            
            # Sample episodes with real themes and competitors
            episodes_data = [
                {
                    'episode_number': 1,
                    'theme': 'Sea Bream',
                    'iron_chef': 'michiba',
                    'competitor': {'name': 'Yukio Hattori', 'restaurant': 'Hattori Nutrition College', 'specialty': 'Japanese'},
                    'winner': 'Iron Chef',
                    'dishes': {
                        'iron_chef': [
                            {'name': 'Sea Bream Sashimi with Plum Sauce', 'ingredients': 'sea bream, plum, soy sauce, wasabi'},
                            {'name': 'Grilled Sea Bream with Salt', 'ingredients': 'sea bream, sea salt, sudachi citrus'},
                            {'name': 'Sea Bream Rice', 'ingredients': 'sea bream, rice, dashi, mitsuba'},
                            {'name': 'Clear Sea Bream Soup', 'ingredients': 'sea bream bones, kombu, sake, salt'}
                        ],
                        'competitor': [
                            {'name': 'Sea Bream Carpaccio', 'ingredients': 'sea bream, olive oil, lemon, capers'},
                            {'name': 'Sea Bream Meunière', 'ingredients': 'sea bream, butter, flour, parsley'},
                            {'name': 'Sea Bream in Paper', 'ingredients': 'sea bream, vegetables, white wine, herbs'}
                        ]
                    }
                },
                {
                    'episode_number': 42,
                    'theme': 'Foie Gras',
                    'iron_chef': 'sakai',
                    'competitor': {'name': 'Alain Passard', 'restaurant': 'L\'Arpège', 'location': 'Paris', 'specialty': 'French'},
                    'winner': 'Iron Chef',
                    'dishes': {
                        'iron_chef': [
                            {'name': 'Foie Gras Terrine with Port Wine', 'ingredients': 'foie gras, port wine, cognac, truffle'},
                            {'name': 'Pan-Seared Foie Gras with Caramelized Apples', 'ingredients': 'foie gras, apples, calvados, butter'},
                            {'name': 'Foie Gras Ravioli in Consommé', 'ingredients': 'foie gras, pasta dough, chicken consommé, chives'},
                            {'name': 'Foie Gras Ice Cream', 'ingredients': 'foie gras, cream, eggs, sauternes'}
                        ],
                        'competitor': [
                            {'name': 'Foie Gras with Turnip Confit', 'ingredients': 'foie gras, baby turnips, honey, thyme'},
                            {'name': 'Foie Gras and Lobster', 'ingredients': 'foie gras, lobster, vanilla, butter'},
                            {'name': 'Foie Gras with Roasted Figs', 'ingredients': 'foie gras, figs, balsamic, arugula'}
                        ]
                    }
                },
                {
                    'episode_number': 75,
                    'theme': 'Shark Fin',
                    'iron_chef': 'kenichi',
                    'competitor': {'name': 'Kazunori Otowa', 'restaurant': 'Otowa Restaurant', 'specialty': 'Japanese-French'},
                    'winner': 'Iron Chef',
                    'dishes': {
                        'iron_chef': [
                            {'name': 'Buddha Jumps Over the Wall', 'ingredients': 'shark fin, abalone, sea cucumber, chinese ham'},
                            {'name': 'Shark Fin with Crab Meat Sauce', 'ingredients': 'shark fin, crab meat, egg white, superior stock'},
                            {'name': 'Shark Fin Dumpling Soup', 'ingredients': 'shark fin, shrimp, pork, wonton wrapper'},
                            {'name': 'Braised Shark Fin in Brown Sauce', 'ingredients': 'shark fin, soy sauce, oyster sauce, scallions'}
                        ],
                        'competitor': [
                            {'name': 'Shark Fin Consommé', 'ingredients': 'shark fin, chicken, vegetables, egg white'},
                            {'name': 'Shark Fin Gratin', 'ingredients': 'shark fin, bechamel, gruyere, truffle'},
                            {'name': 'Shark Fin Tempura', 'ingredients': 'shark fin, tempura batter, ponzu sauce'}
                        ]
                    }
                },
                {
                    'episode_number': 150,
                    'theme': 'Lobster',
                    'iron_chef': 'morimoto',
                    'competitor': {'name': 'Masahiko Kobe', 'restaurant': 'Ristorante Massa', 'location': 'Tokyo', 'specialty': 'Italian'},
                    'winner': 'Competitor',
                    'dishes': {
                        'iron_chef': [
                            {'name': 'Lobster Sashimi', 'ingredients': 'lobster, soy sauce, wasabi, shiso'},
                            {'name': 'Lobster Miso Soup', 'ingredients': 'lobster shells, miso, tofu, scallions'},
                            {'name': 'Grilled Lobster with Uni', 'ingredients': 'lobster, sea urchin, butter, sake'},
                            {'name': 'Lobster Shabu-Shabu', 'ingredients': 'lobster, kombu dashi, ponzu, vegetables'}
                        ],
                        'competitor': [
                            {'name': 'Lobster Risotto', 'ingredients': 'lobster, arborio rice, saffron, parmesan'},
                            {'name': 'Lobster Ravioli', 'ingredients': 'lobster, ricotta, pasta dough, tomato sauce'},
                            {'name': 'Lobster Carpaccio', 'ingredients': 'lobster, olive oil, lemon, arugula'},
                            {'name': 'Lobster Bisque', 'ingredients': 'lobster shells, cream, cognac, tomato paste'}
                        ]
                    }
                },
                {
                    'episode_number': 200,
                    'theme': 'Bamboo Shoots',
                    'iron_chef': 'kenichi',
                    'competitor': {'name': 'Yutaka Ishinabe', 'restaurant': 'Queen Alice', 'specialty': 'French'},
                    'winner': 'Iron Chef',
                    'dishes': {
                        'iron_chef': [
                            {'name': 'Stir-fried Bamboo Shoots with XO Sauce', 'ingredients': 'bamboo shoots, XO sauce, scallops, chili'},
                            {'name': 'Bamboo Shoot Spring Rolls', 'ingredients': 'bamboo shoots, shrimp, pork, spring roll wrapper'},
                            {'name': 'Bamboo Shoot and Pork Belly', 'ingredients': 'bamboo shoots, pork belly, soy sauce, star anise'},
                            {'name': 'Bamboo Shoot Soup', 'ingredients': 'bamboo shoots, chicken stock, ham, egg'}
                        ],
                        'competitor': [
                            {'name': 'Bamboo Shoot Gratin', 'ingredients': 'bamboo shoots, cream, gruyere, nutmeg'},
                            {'name': 'Bamboo Shoot Terrine', 'ingredients': 'bamboo shoots, foie gras, aspic, herbs'},
                            {'name': 'Bamboo Shoot Velouté', 'ingredients': 'bamboo shoots, butter, cream, white wine'}
                        ]
                    }
                }
            ]
            
            # Load the episodes into the database with validation
            for ep_data in episodes_data:
                try:
                    # Validate episode data
                    episode_number = validator.validate_integer(
                        ep_data['episode_number'], min_val=1, max_val=999999, field_name="episode number"
                    )
                    theme = validator.validate_string(
                        ep_data['theme'], max_length=100, field_name="theme"
                    )
                    winner = validator.validate_string(
                        ep_data.get('winner'), max_length=20, field_name="winner"
                    )
                    
                    # Add competitor with validation
                    comp = ep_data['competitor']
                    competitor_name = validator.validate_string(
                        comp['name'], max_length=100, field_name="competitor name"
                    )
                    competitor_restaurant = validator.validate_string(
                        comp.get('restaurant'), max_length=200, field_name="restaurant"
                    )
                    competitor_specialty = validator.validate_string(
                        comp.get('specialty'), max_length=100, field_name="specialty"
                    )
                    competitor_location = validator.validate_string(
                        comp.get('location'), max_length=100, field_name="location"
                    )
                    
                    competitor_id = db.add_competitor(
                        competitor_name, 
                        competitor_restaurant, 
                        competitor_specialty, 
                        competitor_location
                    )
                    
                    # Get Iron Chef ID
                    iron_chef_key = ep_data['iron_chef']
                    if iron_chef_key not in iron_chefs:
                        print(f"Warning: Unknown Iron Chef key '{iron_chef_key}', skipping episode {episode_number}")
                        continue
                    
                    # Add episode with validation
                    episode_id = db.add_episode(
                        episode_number,
                        theme,
                        iron_chefs[iron_chef_key],
                        competitor_id,
                        winner=winner
                    )
                    
                    # Add Iron Chef dishes with validation
                    for i, dish in enumerate(ep_data['dishes']['iron_chef'], 1):
                        try:
                            dish_name = validator.validate_string(
                                dish['name'], max_length=200, field_name="dish name"
                            )
                            ingredients = validator.validate_string(
                                dish.get('ingredients'), max_length=500, field_name="ingredients"
                            )
                            
                            db.add_dish(
                                episode_id,
                                'iron_chef',
                                i,
                                dish_name,
                                main_ingredients=ingredients
                            )
                        except ValueError as e:
                            print(f"Validation error adding Iron Chef dish '{dish['name']}': {e}")
                            continue
                    
                    # Add Competitor dishes with validation
                    for i, dish in enumerate(ep_data['dishes']['competitor'], 1):
                        try:
                            dish_name = validator.validate_string(
                                dish['name'], max_length=200, field_name="dish name"
                            )
                            ingredients = validator.validate_string(
                                dish.get('ingredients'), max_length=500, field_name="ingredients"
                            )
                            
                            db.add_dish(
                                episode_id,
                                'competitor',
                                i,
                                dish_name,
                                main_ingredients=ingredients
                            )
                        except ValueError as e:
                            print(f"Validation error adding competitor dish '{dish['name']}': {e}")
                            continue
                            
                except ValueError as e:
                    print(f"Validation error processing episode {ep_data.get('episode_number', 'unknown')}: {e}")
                    continue
                except Exception as e:
                    print(f"Error processing episode {ep_data.get('episode_number', 'unknown')}: {e}")
                    continue
            
            print(f"Successfully loaded {len(episodes_data)} episodes with dishes into the database")
            return True
            
    except Exception as e:
        print(f"Database initialization error: {e}")
        raise

if __name__ == "__main__":
    load_sample_data()