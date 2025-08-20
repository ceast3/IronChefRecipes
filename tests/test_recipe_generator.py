"""
Unit tests for RecipeGenerator class
Tests recipe generation logic, ingredient handling, and validation
"""

import pytest
import json
import tempfile
from unittest.mock import patch, MagicMock

# Import modules under test
from recipe_generator import RecipeGenerator
from iron_chef_database_secure import IronChefDatabaseSecure


@pytest.mark.unit
class TestRecipeGenerator:
    """Test the RecipeGenerator class"""
    
    def test_initialization(self, recipe_generator):
        """Test RecipeGenerator initialization"""
        assert recipe_generator.validator is not None
        assert isinstance(recipe_generator.cooking_methods, dict)
        assert isinstance(recipe_generator.flavor_profiles, dict)
        
        # Verify cuisine styles are present
        expected_cuisines = ['Japanese', 'Chinese', 'French', 'Italian']
        for cuisine in expected_cuisines:
            assert cuisine in recipe_generator.cooking_methods
            assert cuisine in recipe_generator.flavor_profiles
    
    def test_generate_recipe_valid_basic(self, recipe_generator):
        """Test basic recipe generation with valid inputs"""
        recipe = recipe_generator.generate_recipe(
            dish_name="Test Grilled Fish",
            main_ingredients="sea bream, soy sauce, ginger",
            cuisine_style="Japanese"
        )
        
        # Verify recipe structure
        assert isinstance(recipe, dict)
        required_fields = ['title', 'description', 'servings', 'prep_time', 'cook_time', 
                          'ingredients', 'instructions', 'chef_tips', 'wine_pairing']
        for field in required_fields:
            assert field in recipe
        
        # Verify field types and content
        assert isinstance(recipe['title'], str)
        assert "Test Grilled Fish" in recipe['title']
        assert isinstance(recipe['servings'], int)
        assert recipe['servings'] > 0
        assert isinstance(recipe['prep_time'], int)
        assert isinstance(recipe['cook_time'], int)
        assert isinstance(recipe['ingredients'], list)
        assert isinstance(recipe['instructions'], list)
        assert isinstance(recipe['chef_tips'], list)
        assert isinstance(recipe['wine_pairing'], str)
    
    def test_generate_recipe_different_cuisines(self, recipe_generator):
        """Test recipe generation for different cuisine styles"""
        dish_name = "Test Dish"
        ingredients = "test ingredient, salt, pepper"
        
        cuisines = ['Japanese', 'Chinese', 'French', 'Italian']
        
        for cuisine in cuisines:
            recipe = recipe_generator.generate_recipe(dish_name, ingredients, cuisine)
            assert isinstance(recipe, dict)
            assert recipe['title'] is not None
            assert recipe['wine_pairing'] is not None
            
            # Verify cuisine-specific elements might differ
            # (This is more of a smoke test to ensure no crashes)
    
    def test_generate_recipe_invalid_inputs(self, recipe_generator):
        """Test recipe generation with invalid inputs"""
        # Empty dish name
        with pytest.raises(ValueError, match="Dish name is required"):
            recipe_generator.generate_recipe("", "ingredients")
        
        # None dish name
        with pytest.raises(ValueError, match="Dish name is required"):
            recipe_generator.generate_recipe(None, "ingredients")
        
        # Empty ingredients
        with pytest.raises(ValueError, match="Main ingredients are required"):
            recipe_generator.generate_recipe("dish", "")
        
        # None ingredients
        with pytest.raises(ValueError, match="Main ingredients are required"):
            recipe_generator.generate_recipe("dish", None)
        
        # Too long dish name
        with pytest.raises(ValueError, match="validation error"):
            recipe_generator.generate_recipe("x" * 300, "ingredients")
    
    def test_generate_recipe_cuisine_fallback(self, recipe_generator):
        """Test cuisine style fallback to Japanese"""
        recipe = recipe_generator.generate_recipe(
            "Test Dish",
            "test ingredients",
            "NonExistentCuisine"
        )
        
        # Should not crash and should generate valid recipe
        assert isinstance(recipe, dict)
        assert recipe['title'] is not None
    
    def test_select_cooking_method_specific_dishes(self, recipe_generator):
        """Test cooking method selection for specific dish types"""
        test_cases = [
            ("Sashimi Platter", "prepare raw"),
            ("Grilled Fish", "grill"),
            ("Tempura Vegetables", "deep-fry"),
            ("Steamed Fish", "steam"),
            ("Lobster Bisque", "simmer"),
            ("Beef Stir-fry", "stir-fry"),
            ("Risotto", "risotto"),
            ("Ice Cream", "freeze")
        ]
        
        for dish_name, expected_method in test_cases:
            method = recipe_generator._select_cooking_method(dish_name, "Japanese")
            assert method == expected_method
    
    def test_select_cooking_method_fallback(self, recipe_generator):
        """Test cooking method selection fallback"""
        # Unknown dish should use cuisine-based random selection
        method = recipe_generator._select_cooking_method("Unknown Dish", "Japanese")
        assert method in recipe_generator.cooking_methods["Japanese"]
    
    def test_generate_description(self, recipe_generator):
        """Test dish description generation"""
        description = recipe_generator._generate_description(
            "Test Dish", "test ingredient", "Japanese"
        )
        
        assert isinstance(description, str)
        assert len(description) > 0
        assert "test ingredient" in description
    
    def test_generate_ingredient_list(self, recipe_generator):
        """Test ingredient list generation"""
        base_ingredients = ["lobster", "soy sauce", "ginger", "scallions"]
        ingredients = recipe_generator._generate_ingredient_list(
            base_ingredients, "lobster", "Grilled Lobster"
        )
        
        assert isinstance(ingredients, list)
        assert len(ingredients) > 0
        
        # Check primary ingredient is first and properly formatted
        primary = ingredients[0]
        assert isinstance(primary, dict)
        assert 'item' in primary
        assert 'amount' in primary
        assert 'prep' in primary
        assert primary['item'] == "Lobster"
        
        # Verify other ingredients are included
        ingredient_names = [ing['item'].lower() for ing in ingredients]
        assert any("soy" in name for name in ingredient_names)
    
    def test_estimate_amount_specific_ingredients(self, recipe_generator):
        """Test amount estimation for specific ingredients"""
        test_cases = [
            ("soy sauce", "2-3 tbsp"),
            ("dashi", "2 cups"),
            ("garlic", "1 tbsp, minced"),
            ("wasabi", "1 tsp"),
            ("truffle", "1 small, shaved"),
            ("parsley", "2 tbsp, chopped"),
            ("lobster", "4 oz"),
            ("rice", "1 cup"),
            ("parmesan", "1/2 cup, grated"),
            ("uni", "2 oz"),
            ("foie gras", "4 oz"),
            ("caviar", "1 oz"),
            ("saffron", "Pinch")
        ]
        
        for ingredient, expected_amount in test_cases:
            amount = recipe_generator._estimate_amount(ingredient)
            assert amount == expected_amount
    
    def test_get_primary_amount(self, recipe_generator):
        """Test primary ingredient amount calculation"""
        test_cases = [
            ("lobster", "Grilled Lobster", "1 lb"),
            ("lobster", "Lobster Sashimi", "8 oz"),
            ("sea bream", "Sea Bream Sashimi", "6 oz, sashimi grade"),
            ("sea bream", "Grilled Sea Bream", "1 lb, fresh"),
            ("foie gras", "Pan-seared Foie Gras", "6 oz"),
            ("bamboo shoots", "Bamboo Shoot Salad", "1 lb, fresh")
        ]
        
        for ingredient, dish_name, expected_amount in test_cases:
            amount = recipe_generator._get_primary_amount(ingredient, dish_name)
            assert amount == expected_amount
    
    def test_get_prep_method(self, recipe_generator):
        """Test preparation method determination"""
        test_cases = [
            ("lobster", "Lobster Sashimi", "cleaned, shell removed"),
            ("lobster", "Grilled Lobster", "cleaned and prepared"),
            ("sea bream", "Sea Bream Sashimi", "filleted, skin removed"),
            ("sea bream", "Grilled Sea Bream", "cleaned and scaled"),
            ("foie gras", "Pan-seared Foie Gras", "cleaned, veins removed"),
            ("bamboo shoots", "Bamboo Dish", "peeled and sliced"),
            ("mushroom", "Mushroom Dish", "cleaned and sliced")
        ]
        
        for ingredient, dish_name, expected_prep in test_cases:
            prep = recipe_generator._get_prep_method(ingredient, dish_name)
            assert prep == expected_prep
    
    def test_estimate_times(self, recipe_generator):
        """Test cooking time estimation"""
        test_cases = [
            ("Sashimi", "prepare raw", (20, 0)),
            ("Carpaccio", "prepare raw", (15, 0)),
            ("Grilled Fish", "grill", (10, 8)),
            ("Stir-fry", "stir-fry", (15, 5)),
            ("Tempura", "deep-fry", (20, 5)),
            ("Steamed Fish", "steam", (15, 12)),
            ("Lobster Bisque", "simmer", (20, 30)),
            ("Braised Beef", "braise", (20, 45)),
            ("Risotto", "risotto", (15, 25)),
            ("Ice Cream", "freeze", (30, 240))
        ]
        
        for dish_name, method, expected_times in test_cases:
            prep_time, cook_time = recipe_generator._estimate_times(dish_name, method)
            assert prep_time == expected_times[0]
            assert cook_time == expected_times[1]
    
    def test_generate_instructions_different_methods(self, recipe_generator):
        """Test instruction generation for different cooking methods"""
        ingredients = ["test ingredient", "salt", "pepper"]
        
        cooking_methods = [
            "prepare raw", "grill", "sear", "stir-fry", "steam", 
            "simmer", "deep-fry", "risotto", "pasta", "bake", "braise"
        ]
        
        for method in cooking_methods:
            instructions = recipe_generator._generate_instructions(
                "Test Dish", ingredients, method, "Japanese"
            )
            
            assert isinstance(instructions, list)
            assert len(instructions) > 0
            assert all(isinstance(instruction, str) for instruction in instructions)
            assert all(len(instruction) > 0 for instruction in instructions)
    
    def test_generate_instructions_sashimi_specific(self, recipe_generator):
        """Test sashimi-specific instruction generation"""
        instructions = recipe_generator._generate_instructions(
            "Sea Bream Sashimi", ["sea bream"], "prepare raw", "Japanese"
        )
        
        assert isinstance(instructions, list)
        assert any("sashimi knife" in instruction.lower() for instruction in instructions)
        assert any("slice" in instruction.lower() for instruction in instructions)
    
    def test_generate_chef_tips(self, recipe_generator):
        """Test chef tips generation"""
        tips = recipe_generator._generate_chef_tips("lobster", "Japanese")
        
        assert isinstance(tips, list)
        assert len(tips) <= 4  # Should return max 4 tips
        assert all(isinstance(tip, str) for tip in tips)
        assert all(len(tip) > 0 for tip in tips)
        
        # Should include general and specific tips
        tip_text = " ".join(tips).lower()
        assert "quality" in tip_text or "fresh" in tip_text
    
    def test_generate_chef_tips_cuisine_specific(self, recipe_generator):
        """Test cuisine-specific chef tips"""
        cuisines = ['Japanese', 'French', 'Chinese', 'Italian']
        
        for cuisine in cuisines:
            tips = recipe_generator._generate_chef_tips("test ingredient", cuisine)
            assert isinstance(tips, list)
            assert len(tips) > 0
    
    def test_generate_chef_tips_ingredient_specific(self, recipe_generator):
        """Test ingredient-specific chef tips"""
        # Test seafood tips
        seafood_tips = recipe_generator._generate_chef_tips("lobster", "Japanese")
        tip_text = " ".join(seafood_tips).lower()
        assert "seafood" in tip_text or "overcook" in tip_text or "ocean" in tip_text
        
        # Test foie gras tips
        foie_tips = recipe_generator._generate_chef_tips("foie gras", "French")
        tip_text = " ".join(foie_tips).lower()
        assert "foie gras" in tip_text or "score" in tip_text
    
    def test_suggest_wine_pairing(self, recipe_generator):
        """Test wine pairing suggestions"""
        cuisines = ['Japanese', 'Chinese', 'French', 'Italian']
        
        for cuisine in cuisines:
            pairing = recipe_generator._suggest_wine_pairing("Test Dish", cuisine)
            assert isinstance(pairing, str)
            assert len(pairing) > 0
    
    @pytest.mark.database
    def test_save_recipe_to_db_valid(self, recipe_generator, populated_db, sample_recipe_data):
        """Test saving recipe to database with valid data"""
        with IronChefDatabaseSecure(populated_db) as db:
            # Get existing dish ID
            db.cursor.execute("SELECT id FROM dishes LIMIT 1")
            dish_id = db.cursor.fetchone()['id']
        
        recipe_id = recipe_generator.save_recipe_to_db(dish_id, sample_recipe_data)
        
        assert recipe_id is not None
        assert recipe_id > 0
        
        # Verify recipe was saved
        with IronChefDatabaseSecure(populated_db) as db:
            db.cursor.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
            saved_recipe = db.cursor.fetchone()
            assert saved_recipe is not None
            assert saved_recipe['recipe_title'] == sample_recipe_data['title']
    
    @pytest.mark.database
    def test_save_recipe_to_db_invalid(self, recipe_generator):
        """Test saving recipe to database with invalid data"""
        # Invalid dish ID
        with pytest.raises(ValueError, match="dish ID"):
            recipe_generator.save_recipe_to_db(0, {})
        
        # Invalid recipe structure
        with pytest.raises(ValueError, match="Recipe must be a dictionary"):
            recipe_generator.save_recipe_to_db(1, "not a dict")
        
        # Missing required fields
        incomplete_recipe = {'title': 'Test'}
        with pytest.raises(ValueError, match="Recipe missing required field"):
            recipe_generator.save_recipe_to_db(1, incomplete_recipe)
    
    @pytest.mark.database
    def test_save_recipe_to_db_field_validation(self, recipe_generator, sample_recipe_data):
        """Test field validation when saving recipe to database"""
        # Invalid prep time
        invalid_recipe = sample_recipe_data.copy()
        invalid_recipe['prep_time'] = -1
        with pytest.raises(ValueError, match="prep time"):
            recipe_generator.save_recipe_to_db(1, invalid_recipe)
        
        # Invalid cook time
        invalid_recipe = sample_recipe_data.copy()
        invalid_recipe['cook_time'] = 500  # Over max
        with pytest.raises(ValueError, match="cook time"):
            recipe_generator.save_recipe_to_db(1, invalid_recipe)
        
        # Invalid servings
        invalid_recipe = sample_recipe_data.copy()
        invalid_recipe['servings'] = 0
        with pytest.raises(ValueError, match="servings"):
            recipe_generator.save_recipe_to_db(1, invalid_recipe)


@pytest.mark.integration
class TestRecipeGeneratorIntegration:
    """Integration tests for RecipeGenerator"""
    
    @pytest.mark.database
    def test_full_recipe_generation_workflow(self, recipe_generator, populated_db):
        """Test complete workflow from dish to saved recipe"""
        with IronChefDatabaseSecure(populated_db) as db:
            # Get an existing dish
            db.cursor.execute("SELECT * FROM dishes LIMIT 1")
            dish = dict(db.cursor.fetchone())
            
            # Generate recipe for the dish
            recipe = recipe_generator.generate_recipe(
                dish_name=dish['dish_name'],
                main_ingredients=dish['main_ingredients'],
                cuisine_style="Japanese"
            )
            
            # Save recipe to database
            recipe_id = recipe_generator.save_recipe_to_db(dish['id'], recipe)
            
            # Verify complete recipe was saved and can be retrieved
            db.cursor.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
            saved_recipe = dict(db.cursor.fetchone())
            
            assert saved_recipe['recipe_title'] == recipe['title']
            assert saved_recipe['prep_time'] == recipe['prep_time']
            assert saved_recipe['cook_time'] == recipe['cook_time']
            assert saved_recipe['servings'] == recipe['servings']
            
            # Verify JSON fields can be parsed
            ingredients = json.loads(saved_recipe['ingredients'])
            instructions = json.loads(saved_recipe['instructions'])
            assert isinstance(ingredients, list)
            assert isinstance(instructions, list)
    
    def test_recipe_generation_edge_cases(self, recipe_generator):
        """Test recipe generation with edge case inputs"""
        # Single ingredient
        recipe = recipe_generator.generate_recipe("Simple Dish", "salt")
        assert isinstance(recipe, dict)
        assert len(recipe['ingredients']) > 0
        
        # Very long ingredient list
        long_ingredients = ", ".join([f"ingredient{i}" for i in range(20)])
        recipe = recipe_generator.generate_recipe("Complex Dish", long_ingredients)
        assert isinstance(recipe, dict)
        
        # Unusual dish names
        unusual_dishes = [
            "Molecular Gastronomy Sphere",
            "Traditional Grandma's Secret Recipe",
            "Ultra-Modern Fusion Concept"
        ]
        
        for dish_name in unusual_dishes:
            recipe = recipe_generator.generate_recipe(dish_name, "test ingredients")
            assert isinstance(recipe, dict)
            assert dish_name in recipe['title']
    
    @pytest.mark.slow
    def test_recipe_generation_performance(self, recipe_generator, benchmark_timer):
        """Test recipe generation performance"""
        dish_name = "Performance Test Dish"
        ingredients = "test ingredient 1, test ingredient 2, test ingredient 3"
        
        benchmark_timer.start()
        
        # Generate multiple recipes
        recipes = []
        for i in range(50):
            recipe = recipe_generator.generate_recipe(f"{dish_name} {i}", ingredients)
            recipes.append(recipe)
        
        elapsed_time = benchmark_timer.stop()
        
        # Should complete 50 recipes in reasonable time (less than 5 seconds)
        assert elapsed_time < 5.0
        assert len(recipes) == 50
        assert all(isinstance(recipe, dict) for recipe in recipes)
    
    def test_recipe_consistency(self, recipe_generator):
        """Test that recipe generation is consistent for same inputs"""
        dish_name = "Consistency Test Dish"
        ingredients = "test ingredient, salt, pepper"
        cuisine = "Japanese"
        
        # Generate same recipe multiple times
        recipes = []
        for i in range(5):
            recipe = recipe_generator.generate_recipe(dish_name, ingredients, cuisine)
            recipes.append(recipe)
        
        # Some elements should be consistent
        for recipe in recipes:
            assert dish_name in recipe['title']
            assert recipe['servings'] == 4  # Default servings
            # Cooking method should be consistent for same dish name
            # (Instructions will vary due to randomness, but structure should be similar)
    
    def test_recipe_generation_all_cooking_methods(self, recipe_generator):
        """Test recipe generation covers all cooking methods"""
        # Test dishes that should trigger different cooking methods
        test_dishes = [
            ("Sashimi Platter", "sea bream"),
            ("Grilled Steak", "beef"),
            ("Tempura Vegetables", "vegetables"),
            ("Steamed Fish", "fish"),
            ("Beef Stew", "beef"),
            ("Lobster Bisque", "lobster"),
            ("Mushroom Risotto", "rice, mushrooms"),
            ("Pasta Carbonara", "pasta, eggs"),
            ("Baked Salmon", "salmon"),
            ("Ice Cream", "cream, sugar")
        ]
        
        generated_methods = set()
        
        for dish_name, ingredients in test_dishes:
            recipe = recipe_generator.generate_recipe(dish_name, ingredients)
            
            # Determine cooking method from instructions
            instructions_text = " ".join(recipe['instructions']).lower()
            
            if "sashimi" in instructions_text or "slice" in instructions_text:
                generated_methods.add("raw")
            elif "grill" in instructions_text:
                generated_methods.add("grill")
            elif "fry" in instructions_text:
                generated_methods.add("fry")
            elif "steam" in instructions_text:
                generated_methods.add("steam")
            elif "simmer" in instructions_text:
                generated_methods.add("simmer")
            elif "risotto" in instructions_text:
                generated_methods.add("risotto")
            elif "pasta" in instructions_text:
                generated_methods.add("pasta")
            elif "bake" in instructions_text:
                generated_methods.add("bake")
        
        # Should have covered multiple cooking methods
        assert len(generated_methods) > 5


@pytest.mark.unit
class TestRecipeGeneratorErrorHandling:
    """Test error handling and edge cases in RecipeGenerator"""
    
    def test_malicious_input_handling(self, recipe_generator, malicious_inputs):
        """Test handling of malicious inputs"""
        # SQL injection attempts in dish name
        for malicious in malicious_inputs['sql_injection'][:3]:  # Test first 3
            try:
                recipe = recipe_generator.generate_recipe(malicious, "test ingredients")
                # Should either generate safely or reject with validation error
                if isinstance(recipe, dict):
                    assert 'title' in recipe
            except ValueError:
                # Validation rejection is acceptable
                pass
        
        # XSS attempts in ingredients
        for malicious in malicious_inputs['xss_attempts'][:3]:  # Test first 3
            try:
                recipe = recipe_generator.generate_recipe("Test Dish", malicious)
                if isinstance(recipe, dict):
                    assert 'ingredients' in recipe
            except ValueError:
                # Validation rejection is acceptable
                pass
    
    def test_unicode_input_handling(self, recipe_generator):
        """Test handling of Unicode characters"""
        # Japanese characters
        recipe = recipe_generator.generate_recipe("寿司", "魚, 米, 海苔")
        assert isinstance(recipe, dict)
        
        # Emoji in dish name
        recipe = recipe_generator.generate_recipe("🍣 Sushi Roll", "fish, rice")
        assert isinstance(recipe, dict)
        
        # Accented characters
        recipe = recipe_generator.generate_recipe("Café Dish", "café ingredients")
        assert isinstance(recipe, dict)
    
    def test_boundary_value_inputs(self, recipe_generator):
        """Test boundary value inputs"""
        # Maximum length inputs
        max_dish_name = "x" * 200  # At the limit
        max_ingredients = "x" * 500  # At the limit
        
        recipe = recipe_generator.generate_recipe(max_dish_name, max_ingredients)
        assert isinstance(recipe, dict)
        
        # Single character inputs
        recipe = recipe_generator.generate_recipe("a", "b")
        assert isinstance(recipe, dict)
    
    def test_special_character_handling(self, recipe_generator):
        """Test handling of special characters"""
        special_dishes = [
            "Dish & Sauce",
            "Chef's Special",
            "50/50 Mix",
            "100% Pure",
            "@Home Cooking",
            "Recipe #1"
        ]
        
        for dish in special_dishes:
            try:
                recipe = recipe_generator.generate_recipe(dish, "test ingredients")
                assert isinstance(recipe, dict)
            except ValueError:
                # Some special characters might be rejected by validation
                pass