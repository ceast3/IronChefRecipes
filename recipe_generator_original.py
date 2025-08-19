import json
import random
from typing import Dict, List
from iron_chef_database import IronChefDatabase

class RecipeGenerator:
    def __init__(self):
        self.cooking_methods = {
            'Japanese': ['grill', 'steam', 'simmer', 'deep-fry', 'sauté', 'blanch', 'marinate'],
            'Chinese': ['stir-fry', 'deep-fry', 'steam', 'braise', 'roast', 'blanch', 'smoke'],
            'French': ['sauté', 'braise', 'poach', 'roast', 'grill', 'flambe', 'reduce'],
            'Italian': ['sauté', 'braise', 'grill', 'roast', 'simmer', 'bake', 'poach']
        }
        
        self.flavor_profiles = {
            'Japanese': ['umami', 'delicate', 'clean', 'subtle', 'balanced'],
            'Chinese': ['savory', 'spicy', 'sweet and sour', 'aromatic', 'rich'],
            'French': ['rich', 'buttery', 'complex', 'refined', 'layered'],
            'Italian': ['robust', 'fresh', 'herbaceous', 'rustic', 'vibrant']
        }
        
    def generate_recipe(self, dish_name: str, main_ingredients: str, cuisine_style: str = 'Japanese') -> Dict:
        """Generate a recipe based on dish name and ingredients"""
        
        # Parse ingredients
        ingredients_list = [ing.strip() for ing in main_ingredients.split(',')]
        primary_ingredient = ingredients_list[0] if ingredients_list else 'ingredient'
        
        # Determine cooking method based on dish name and cuisine
        cooking_method = self._select_cooking_method(dish_name, cuisine_style)
        
        # Generate realistic prep and cook times based on cooking method
        prep_time, cook_time = self._estimate_times(dish_name, cooking_method)
        
        # Generate recipe components
        recipe = {
            'title': f"Iron Chef Style {dish_name}",
            'description': self._generate_description(dish_name, primary_ingredient, cuisine_style),
            'servings': 4,
            'prep_time': prep_time,
            'cook_time': cook_time,
            'ingredients': self._generate_ingredient_list(ingredients_list, primary_ingredient, dish_name),
            'instructions': self._generate_instructions(dish_name, ingredients_list, cooking_method, cuisine_style),
            'chef_tips': self._generate_chef_tips(primary_ingredient, cuisine_style),
            'wine_pairing': self._suggest_wine_pairing(dish_name, cuisine_style)
        }
        
        return recipe
    
    def _select_cooking_method(self, dish_name: str, cuisine_style: str) -> str:
        """Select appropriate cooking method based on dish name"""
        dish_lower = dish_name.lower()
        
        # Raw preparations
        if 'sashimi' in dish_lower or 'carpaccio' in dish_lower:
            return 'prepare raw'
        
        # Liquid-based cooking
        elif 'soup' in dish_lower or 'bisque' in dish_lower or 'consommé' in dish_lower:
            return 'simmer'
        elif 'shabu-shabu' in dish_lower:
            return 'hot pot'
        
        # High-heat cooking
        elif any(word in dish_lower for word in ['grilled', 'grill', 'barbecue', 'bbq']):
            return 'grill'
        elif any(word in dish_lower for word in ['pan-seared', 'seared', 'pan-fried']):
            return 'sear'
        elif any(word in dish_lower for word in ['stir-fried', 'stir-fry']):
            return 'stir-fry'
        elif any(word in dish_lower for word in ['fried', 'tempura', 'deep-fried']):
            return 'deep-fry'
        
        # Gentle cooking
        elif 'steamed' in dish_lower:
            return 'steam'
        elif 'braised' in dish_lower:
            return 'braise'
        elif 'poached' in dish_lower:
            return 'poach'
        
        # Pasta and rice dishes
        elif 'risotto' in dish_lower:
            return 'risotto'
        elif 'ravioli' in dish_lower or 'pasta' in dish_lower:
            return 'pasta'
        
        # Baked dishes
        elif any(word in dish_lower for word in ['gratin', 'baked', 'roasted']):
            return 'bake'
        elif 'terrine' in dish_lower:
            return 'terrine'
        
        # Ice cream and desserts
        elif 'ice cream' in dish_lower:
            return 'freeze'
        
        # Default based on cuisine
        else:
            methods = self.cooking_methods.get(cuisine_style, self.cooking_methods['Japanese'])
            return random.choice(methods)
    
    def _generate_description(self, dish_name: str, primary_ingredient: str, cuisine_style: str) -> str:
        """Generate a compelling dish description"""
        flavor = random.choice(self.flavor_profiles.get(cuisine_style, self.flavor_profiles['Japanese']))
        
        templates = [
            f"A {flavor} interpretation of {primary_ingredient}, showcasing the mastery of {cuisine_style} cuisine.",
            f"This exquisite {dish_name} highlights the natural flavors of {primary_ingredient} with {flavor} notes.",
            f"An Iron Chef masterpiece that transforms humble {primary_ingredient} into a {flavor} culinary experience.",
            f"Inspired by traditional {cuisine_style} techniques, this dish brings out the {flavor} essence of {primary_ingredient}."
        ]
        
        return random.choice(templates)
    
    def _generate_ingredient_list(self, base_ingredients: List[str], primary: str, dish_name: str) -> List[Dict]:
        """Generate detailed ingredient list with measurements"""
        ingredients = []
        
        # Add primary ingredient with realistic amounts
        amount = self._get_primary_amount(primary, dish_name)
        ingredients.append({
            'item': primary.title(),
            'amount': amount,
            'prep': self._get_prep_method(primary, dish_name)
        })
        
        # Add other listed ingredients
        for ing in base_ingredients[1:]:
            if ing != primary:
                ingredients.append({
                    'item': ing.strip().title(),
                    'amount': self._estimate_amount(ing),
                    'prep': self._get_prep_method(ing, dish_name)
                })
        
        # Add appropriate seasonings based on dish type
        if 'sashimi' not in dish_name.lower() and 'carpaccio' not in dish_name.lower():
            ingredients.extend([
                {'item': 'Salt', 'amount': 'To taste', 'prep': ''},
                {'item': 'White Pepper', 'amount': '1/4 tsp', 'prep': 'freshly ground'}
            ])
        
        # Add cooking oil only if needed
        if not any(word in dish_name.lower() for word in ['sashimi', 'carpaccio', 'ice cream', 'soup']):
            ingredients.append({'item': 'High-quality Oil', 'amount': '2 tbsp', 'prep': 'for cooking'})
        
        return ingredients
    
    def _estimate_amount(self, ingredient: str) -> str:
        """Estimate appropriate amount for an ingredient"""
        ing_lower = ingredient.lower()
        
        # Sauces and liquids
        if any(word in ing_lower for word in ['soy sauce', 'ponzu', 'miso']):
            return '2-3 tbsp'
        elif any(word in ing_lower for word in ['sauce', 'oil', 'vinegar', 'wine', 'sake', 'cognac']):
            return '2 tbsp'
        elif 'dashi' in ing_lower or 'stock' in ing_lower or 'broth' in ing_lower:
            return '2 cups'
        elif 'cream' in ing_lower:
            return '1/2 cup'
        
        # Aromatics
        elif any(word in ing_lower for word in ['garlic', 'ginger', 'shallot']):
            return '1 tbsp, minced'
        elif ing_lower in ['wasabi']:
            return '1 tsp'
        elif ing_lower in ['truffle']:
            return '1 small, shaved'
        
        # Herbs and garnishes
        elif any(word in ing_lower for word in ['herb', 'cilantro', 'parsley', 'basil', 'chives', 'scallions', 'shiso']):
            return '2 tbsp, chopped'
        elif 'arugula' in ing_lower:
            return '2 cups'
        
        # Vegetables
        elif any(word in ing_lower for word in ['vegetable', 'mushroom', 'onion', 'turnip', 'bamboo']):
            return '1 cup, sliced'
        elif 'tofu' in ing_lower:
            return '4 oz, cubed'
        
        # Proteins
        elif any(word in ing_lower for word in ['crab', 'shrimp', 'scallop']):
            return '4 oz'
        elif 'egg' in ing_lower:
            return '2 large'
        
        # Grains and starches
        elif 'rice' in ing_lower:
            return '1 cup'
        elif 'pasta' in ing_lower or 'dough' in ing_lower:
            return '12 oz'
        
        # Cheese
        elif any(word in ing_lower for word in ['parmesan', 'gruyere', 'ricotta']):
            return '1/2 cup, grated'
        
        # Specialty items
        elif 'uni' in ing_lower or 'sea urchin' in ing_lower:
            return '2 oz'
        elif 'foie gras' in ing_lower:
            return '4 oz'
        elif 'caviar' in ing_lower:
            return '1 oz'
        elif 'saffron' in ing_lower:
            return 'Pinch'
        
        else:
            return '1/2 cup'
    
    def _get_primary_amount(self, primary: str, dish_name: str) -> str:
        """Get realistic amount for primary ingredient based on dish type"""
        primary_lower = primary.lower()
        dish_lower = dish_name.lower()
        
        # Seafood amounts
        if any(word in primary_lower for word in ['lobster', 'crab']):
            if 'sashimi' in dish_lower or 'carpaccio' in dish_lower:
                return '8 oz'
            else:
                return '1 lb'
        elif any(word in primary_lower for word in ['sea bream', 'fish', 'salmon', 'tuna']):
            if 'sashimi' in dish_lower:
                return '6 oz, sashimi grade'
            else:
                return '1 lb, fresh'
        
        # Specialty proteins
        elif 'foie gras' in primary_lower:
            return '6 oz'
        elif 'shark fin' in primary_lower:
            return '4 oz, prepared'
        
        # Vegetables
        elif 'bamboo shoots' in primary_lower:
            return '1 lb, fresh'
        
        # Default amounts
        elif any(word in primary_lower for word in ['meat', 'beef', 'pork']):
            return '1 lb'
        else:
            return '1 lb'
    
    def _get_prep_method(self, ingredient: str, dish_name: str) -> str:
        """Get appropriate prep method for ingredient"""
        ing_lower = ingredient.lower()
        dish_lower = dish_name.lower()
        
        if any(word in ing_lower for word in ['lobster', 'crab']):
            if 'sashimi' in dish_lower:
                return 'cleaned, shell removed'
            else:
                return 'cleaned and prepared'
        elif 'sea bream' in ing_lower or 'fish' in ing_lower:
            if 'sashimi' in dish_lower:
                return 'filleted, skin removed'
            else:
                return 'cleaned and scaled'
        elif 'foie gras' in ing_lower:
            return 'cleaned, veins removed'
        elif 'bamboo shoots' in ing_lower:
            return 'peeled and sliced'
        elif any(word in ing_lower for word in ['vegetable', 'mushroom']):
            return 'cleaned and sliced'
        else:
            return 'prepared'
    
    def _estimate_times(self, dish_name: str, cooking_method: str) -> tuple:
        """Estimate realistic prep and cook times based on dish and method"""
        dish_lower = dish_name.lower()
        
        # Raw preparations - no cooking time
        if cooking_method == 'prepare raw':
            if 'sashimi' in dish_lower:
                return (20, 0)  # 20 min prep, no cooking
            else:
                return (15, 0)
        
        # Quick cooking methods
        elif cooking_method in ['sear', 'stir-fry']:
            return (15, 5)
        elif cooking_method == 'grill':
            return (10, 8)
        elif cooking_method == 'deep-fry':
            return (20, 5)
        
        # Medium cooking methods
        elif cooking_method in ['steam', 'poach']:
            return (15, 12)
        elif cooking_method == 'simmer':
            if 'soup' in dish_lower:
                return (20, 30)
            else:
                return (15, 15)
        
        # Longer cooking methods
        elif cooking_method == 'braise':
            return (20, 45)
        elif cooking_method == 'bake':
            return (25, 35)
        elif cooking_method == 'risotto':
            return (15, 25)
        elif cooking_method == 'pasta':
            return (20, 15)
        elif cooking_method == 'terrine':
            return (45, 90)
        elif cooking_method == 'hot pot':
            return (15, 10)
        elif cooking_method == 'freeze':
            return (30, 240)  # Ice cream needs freezing time
        
        # Default times
        else:
            return (20, 25)
    
    def _generate_instructions(self, dish_name: str, ingredients: List[str], method: str, cuisine: str) -> List[str]:
        """Generate step-by-step cooking instructions"""
        primary = ingredients[0] if ingredients else 'ingredient'
        dish_lower = dish_name.lower()
        
        instructions = []
        
        # Preparation step
        if method == 'prepare raw':
            instructions.append(f"Ensure the {primary} is of the highest quality and freshness. Chill all plates and utensils.")
        else:
            instructions.append(f"Begin by preparing all ingredients mise en place. Clean and prep the {primary} appropriately.")
        
        # Method-specific cooking instructions
        if method == 'prepare raw':
            if 'sashimi' in dish_lower:
                instructions.extend([
                    f"Using a very sharp sashimi knife, slice the {primary} against the grain in clean, decisive cuts.",
                    "Each slice should be about 1/4 inch thick for optimal texture and presentation.",
                    "Arrange on chilled plates immediately, leaving space between pieces."
                ])
            else:
                instructions.extend([
                    f"Slice the {primary} paper-thin using a sharp knife or mandoline.",
                    "Arrange overlapping slices on chilled plates in an attractive pattern.",
                    "Drizzle with accompanying sauce just before serving."
                ])
        
        elif method == 'grill':
            instructions.extend([
                "Preheat grill to high heat and clean grates thoroughly.",
                f"Season the {primary} with salt and pepper, let come to room temperature.",
                f"Grill the {primary} for 3-4 minutes per side, creating distinct grill marks.",
                "Use tongs to turn only once, avoid pressing down on the protein."
            ])
        
        elif method == 'sear':
            instructions.extend([
                "Heat a heavy-bottomed pan over high heat until smoking.",
                f"Season the {primary} generously with salt and pepper.",
                f"Sear the {primary} for 2-3 minutes per side until golden brown.",
                "Do not move the protein until it releases naturally from the pan."
            ])
        
        elif method == 'stir-fry':
            instructions.extend([
                "Heat wok over highest heat until smoking. Add oil and swirl to coat.",
                "Add aromatics (garlic, ginger) first, stir for 10 seconds until fragrant.",
                f"Add {primary} and other ingredients in order of cooking time required.",
                "Keep ingredients moving constantly with wok hei technique for 2-3 minutes."
            ])
        
        elif method == 'steam':
            instructions.extend([
                "Set up a steamer basket over simmering water, ensuring water doesn't touch basket.",
                f"Arrange {primary} in steamer, leaving space for steam circulation.",
                "Cover and steam for 8-12 minutes until just cooked through.",
                "Check doneness by gently pressing - should be firm but yielding."
            ])
        
        elif method == 'simmer':
            if 'soup' in dish_lower or 'bisque' in dish_lower:
                instructions.extend([
                    f"In a heavy pot, sauté aromatics until fragrant, then add {primary}.",
                    "Add stock or broth gradually, bringing to a gentle simmer.",
                    "Simmer for 20-30 minutes, skimming impurities from surface regularly.",
                    "Strain if desired and adjust seasoning at the end."
                ])
            else:
                instructions.extend([
                    f"Place {primary} in a wide, heavy pan with minimal liquid.",
                    "Bring to a gentle simmer, cover, and cook until tender.",
                    "Turn once halfway through cooking time."
                ])
        
        elif method == 'deep-fry':
            instructions.extend([
                "Heat oil to 350°F (175°C) in a deep fryer or heavy pot.",
                f"Coat {primary} in batter or breading as desired.",
                f"Fry {primary} in small batches to avoid temperature drop.",
                "Remove when golden brown and drain on paper towels immediately."
            ])
        
        elif method == 'risotto':
            instructions.extend([
                "Warm stock in a separate pan and keep at a gentle simmer.",
                "In a heavy-bottomed pan, sauté aromatics in butter until soft.",
                "Add rice and stir to coat with fat, toasting for 1-2 minutes.",
                "Add warm stock one ladle at a time, stirring constantly until absorbed.",
                f"Continue for 18-20 minutes until rice is creamy. Fold in {primary} near the end."
            ])
        
        elif method == 'pasta':
            instructions.extend([
                "Bring a large pot of salted water to rolling boil.",
                "Cook pasta until al dente, reserving 1 cup pasta water before draining.",
                f"In a large pan, combine {primary} with cooked pasta and a splash of pasta water.",
                "Toss vigorously to create a silky sauce that coats the pasta."
            ])
        
        elif method == 'bake':
            instructions.extend([
                "Preheat oven to 375°F (190°C).",
                f"Season {primary} and place in an appropriate baking dish.",
                "Bake for 25-35 minutes until cooked through and golden.",
                "Let rest for 5 minutes before serving."
            ])
        
        elif method == 'braise':
            instructions.extend([
                f"Sear {primary} in a heavy Dutch oven until browned on all sides.",
                "Add aromatics and cook until fragrant.",
                "Add liquid to come halfway up the protein, bring to simmer.",
                "Cover and cook in 325°F oven for 45 minutes to 1 hour until tender."
            ])
        
        elif method == 'hot pot':
            instructions.extend([
                "Prepare a flavorful dashi or broth and keep hot in a tabletop setup.",
                f"Slice {primary} into thin pieces for quick cooking.",
                "Cook ingredients briefly in the hot broth, 30 seconds to 2 minutes.",
                "Serve immediately with dipping sauces."
            ])
        
        else:
            instructions.extend([
                f"Heat oil in a suitable pan over medium-high heat.",
                f"Cook the {primary} using proper {method} technique until done.",
                "Monitor temperature and timing for optimal results."
            ])
        
        # Final presentation
        if method == 'prepare raw':
            instructions.append("Serve immediately on chilled plates with accompanying sauces and garnishes.")
        else:
            instructions.extend([
                "Plate with attention to visual composition, balancing colors and heights.",
                "Add final garnishes and serve at the optimal temperature."
            ])
        
        return instructions
    
    def _generate_chef_tips(self, primary_ingredient: str, cuisine_style: str) -> List[str]:
        """Generate professional chef tips"""
        
        # Base tips
        tips = [
            f"Quality is paramount - source the freshest {primary_ingredient} possible.",
            "Taste and adjust seasonings throughout the cooking process.",
            "Visual presentation should reflect the dish's flavor profile.",
            "Mise en place is essential - prepare all ingredients before cooking.",
            "Sharp knives are safer and produce better results than dull ones."
        ]
        
        # Cuisine-specific tips
        if cuisine_style == 'Japanese':
            tips.extend([
                "Respect the natural flavors - less is often more in Japanese cuisine.",
                "Temperature contrast adds interest - serve hot dishes on warmed plates.",
                "The knife work should be precise and deliberate for best results.",
                "Umami is the fifth taste - build layers of savory depth."
            ])
        elif cuisine_style == 'French':
            tips.extend([
                "Master your knife skills - precise cuts ensure even cooking.",
                "Butter and cream should be added off heat to prevent breaking.",
                "Build flavors in layers using proper foundational techniques.",
                "Temperature control separates good from great French cooking."
            ])
        elif cuisine_style == 'Chinese':
            tips.extend([
                "High heat and constant motion are key to proper wok cooking.",
                "Velvet proteins for silky texture in stir-fried dishes.",
                "Balance the five flavors: sweet, sour, bitter, spicy, and salty.",
                "Cook ingredients in order of their required cooking times."
            ])
        elif cuisine_style == 'Italian':
            tips.extend([
                "Use the best quality ingredients you can afford - simplicity shines.",
                "Salt your pasta water generously - it should taste like seawater.",
                "Finish pasta dishes with reserved pasta water for silky sauces.",
                "Let tomatoes and herbs speak for themselves with minimal interference."
            ])
        
        # Ingredient-specific tips
        primary_lower = primary_ingredient.lower()
        if any(word in primary_lower for word in ['fish', 'seafood', 'lobster', 'crab']):
            tips.append("Never overcook seafood - it becomes tough and loses its delicate flavor.")
            tips.append("Fresh seafood should smell like the ocean, not 'fishy'.")
        elif 'foie gras' in primary_lower:
            tips.append("Score foie gras before cooking to prevent excessive shrinkage.")
            tips.append("Cook foie gras quickly over high heat for crispy exterior, creamy interior.")
        elif any(word in primary_lower for word in ['vegetable', 'bamboo']):
            tips.append("Cook vegetables until just tender to preserve color and nutrients.")
            tips.append("Blanch and shock green vegetables to maintain vibrant color.")
        
        # Return 3-4 most relevant tips
        return random.sample(tips, min(4, len(tips)))
    
    def _suggest_wine_pairing(self, dish_name: str, cuisine_style: str) -> str:
        """Suggest wine pairing based on dish and cuisine"""
        pairings = {
            'Japanese': ['Sake', 'Junmai Daiginjo', 'Light Riesling', 'Grüner Veltliner'],
            'Chinese': ['Gewürztraminer', 'Riesling', 'Chenin Blanc', 'Light Pinot Noir'],
            'French': ['Burgundy', 'Bordeaux', 'Champagne', 'Sancerre'],
            'Italian': ['Chianti', 'Barolo', 'Pinot Grigio', 'Prosecco']
        }
        
        wine_options = pairings.get(cuisine_style, pairings['Japanese'])
        return random.choice(wine_options)
    
    def save_recipe_to_db(self, dish_id: int, recipe: Dict):
        """Save generated recipe to database"""
        with IronChefDatabase() as db:
            ingredients_json = json.dumps(recipe['ingredients'], indent=2)
            instructions_json = json.dumps(recipe['instructions'], indent=2)
            
            recipe_id = db.add_recipe(
                dish_id=dish_id,
                recipe_title=recipe['title'],
                ingredients=ingredients_json,
                instructions=instructions_json,
                prep_time=recipe['prep_time'],
                cook_time=recipe['cook_time'],
                servings=recipe['servings']
            )
            
            return recipe_id