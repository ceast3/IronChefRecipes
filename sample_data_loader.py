from iron_chef_database import IronChefDatabase
import json

def load_sample_data():
    """Load sample Iron Chef Japan data into the database"""
    
    with IronChefDatabase() as db:
        # Initialize the database
        db.initialize_database()
        
        # Add Iron Chefs
        iron_chefs = {
            'chen': db.add_iron_chef("Chen Kenichi", "Iron Chef Chinese", "Szechuan Cuisine", "1993-1999"),
            'sakai': db.add_iron_chef("Hiroyuki Sakai", "Iron Chef French", "French Cuisine", "1994-1999"),
            'kobe': db.add_iron_chef("Masaharu Morimoto", "Iron Chef Japanese", "Japanese Cuisine", "1998-1999"),
            'michiba': db.add_iron_chef("Rokusaburo Michiba", "Iron Chef Japanese", "Traditional Japanese", "1993-1996"),
            'nakamura': db.add_iron_chef("Koumei Nakamura", "Iron Chef Japanese", "Japanese Cuisine", "1996-1998")
        }
        
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
                'iron_chef': 'chen',
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
                'iron_chef': 'kobe',
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
                'iron_chef': 'chen',
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
        
        # Load the episodes into the database
        for ep_data in episodes_data:
            # Add competitor
            comp = ep_data['competitor']
            competitor_id = db.add_competitor(comp['name'], comp.get('restaurant'), comp.get('specialty'), comp.get('location'))
            
            # Add episode
            episode_id = db.add_episode(
                ep_data['episode_number'],
                ep_data['theme'],
                iron_chefs[ep_data['iron_chef']],
                competitor_id,
                winner=ep_data.get('winner')
            )
            
            # Add Iron Chef dishes
            for i, dish in enumerate(ep_data['dishes']['iron_chef'], 1):
                db.add_dish(
                    episode_id,
                    'iron_chef',
                    i,
                    dish['name'],
                    main_ingredients=dish.get('ingredients')
                )
            
            # Add Competitor dishes
            for i, dish in enumerate(ep_data['dishes']['competitor'], 1):
                db.add_dish(
                    episode_id,
                    'competitor',
                    i,
                    dish['name'],
                    main_ingredients=dish.get('ingredients')
                )
        
        print(f"Loaded {len(episodes_data)} episodes with dishes into the database")

if __name__ == "__main__":
    load_sample_data()