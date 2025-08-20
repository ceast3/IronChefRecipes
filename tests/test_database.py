"""
Unit tests for IronChefDatabaseSecure class
Tests all CRUD operations, validation, and error handling
"""

import pytest
import sqlite3
import json
import os
import tempfile
from pathlib import Path

# Import modules under test
from iron_chef_database_secure import IronChefDatabaseSecure, SecurityValidator


@pytest.mark.unit
@pytest.mark.database
class TestSecurityValidator:
    """Test the SecurityValidator class"""
    
    def test_validate_integer_valid(self, security_validator):
        """Test integer validation with valid inputs"""
        assert security_validator.validate_integer(5) == 5
        assert security_validator.validate_integer("10", min_val=5, max_val=15) == 10
        assert security_validator.validate_integer(0, min_val=0) == 0
        
    def test_validate_integer_invalid(self, security_validator):
        """Test integer validation with invalid inputs"""
        with pytest.raises(ValueError, match="must be an integer"):
            security_validator.validate_integer("not_a_number")
        
        with pytest.raises(ValueError, match="must be at least"):
            security_validator.validate_integer(-5, min_val=0)
        
        with pytest.raises(ValueError, match="must be no more than"):
            security_validator.validate_integer(100, max_val=50)
    
    def test_validate_integer_none(self, security_validator):
        """Test integer validation with None input"""
        assert security_validator.validate_integer(None) is None
    
    def test_validate_string_valid(self, security_validator):
        """Test string validation with valid inputs"""
        assert security_validator.validate_string("test") == "test"
        assert security_validator.validate_string("  test  ") == "test"  # Trimmed
        assert security_validator.validate_string("test123", pattern=r'^[a-zA-Z0-9]+$') == "test123"
    
    def test_validate_string_invalid(self, security_validator):
        """Test string validation with invalid inputs"""
        with pytest.raises(ValueError, match="must be a string"):
            security_validator.validate_string(123)
        
        with pytest.raises(ValueError, match="exceeds maximum length"):
            security_validator.validate_string("x" * 1000, max_length=100)
        
        with pytest.raises(ValueError, match="contains invalid characters"):
            security_validator.validate_string("test@#$", pattern=r'^[a-zA-Z]+$')
    
    def test_validate_string_null_bytes(self, security_validator):
        """Test string validation removes null bytes"""
        result = security_validator.validate_string("test\x00null")
        assert "\x00" not in result
        assert result == "testnull"
    
    def test_validate_string_none(self, security_validator):
        """Test string validation with None input"""
        assert security_validator.validate_string(None) is None
    
    def test_sanitize_sql_pattern(self, security_validator):
        """Test SQL pattern sanitization"""
        assert security_validator.sanitize_sql_pattern("test") == "%test%"
        assert security_validator.sanitize_sql_pattern("") == "%"
        assert security_validator.sanitize_sql_pattern(None) == "%"
        
        # Test escaping of special characters
        result = security_validator.sanitize_sql_pattern("test%_[")
        assert "\\%" in result
        assert "\\_" in result
        assert "\\[" in result
    
    def test_validate_filename(self, security_validator):
        """Test filename validation and sanitization"""
        # Valid filename
        assert security_validator.validate_filename("test.txt") == "test.txt"
        
        # Path traversal prevention
        assert ".." not in security_validator.validate_filename("../test.txt")
        
        # Dangerous characters removed
        result = security_validator.validate_filename("test@#$.txt")
        assert "@" not in result and "#" not in result and "$" not in result
        
        # Extension added if missing
        result = security_validator.validate_filename("test")
        assert result.endswith(".txt")
        
        # Empty filename handling
        with pytest.raises(ValueError, match="Filename cannot be empty"):
            security_validator.validate_filename("")


@pytest.mark.unit
@pytest.mark.database
class TestIronChefDatabaseSecure:
    """Test the IronChefDatabaseSecure class"""
    
    def test_database_initialization(self, temp_db_path):
        """Test database initialization and context manager"""
        with IronChefDatabaseSecure(temp_db_path) as db:
            assert db.connection is not None
            assert db.cursor is not None
            assert db.db_path == temp_db_path
    
    def test_database_path_validation(self):
        """Test database path validation"""
        with pytest.raises(ValueError, match="database path"):
            IronChefDatabaseSecure("invalid@path!")
    
    def test_initialize_database(self, temp_db_path):
        """Test database schema initialization"""
        # Copy schema file for test
        schema_path = Path(__file__).parent.parent / "database_schema.sql"
        
        with IronChefDatabaseSecure(temp_db_path) as db:
            db.initialize_database()
            
            # Verify tables were created
            db.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in db.cursor.fetchall()]
            
            expected_tables = ['iron_chefs', 'competitors', 'episodes', 'dishes', 'recipes', 'ingredients', 'dish_ingredients']
            for table in expected_tables:
                assert table in tables
    
    def test_add_iron_chef_valid(self, test_db):
        """Test adding valid iron chef"""
        with IronChefDatabaseSecure(test_db) as db:
            chef_id = db.add_iron_chef(
                name="Test Chef",
                title="Iron Chef Test",
                specialty="Test Cuisine",
                active_years="2024"
            )
            
            assert chef_id is not None
            assert chef_id > 0
            
            # Verify chef was added
            db.cursor.execute("SELECT * FROM iron_chefs WHERE id = ?", (chef_id,))
            chef = db.cursor.fetchone()
            assert chef['name'] == "Test Chef"
            assert chef['title'] == "Iron Chef Test"
    
    def test_add_iron_chef_invalid(self, test_db):
        """Test adding iron chef with invalid data"""
        with IronChefDatabaseSecure(test_db) as db:
            # Empty name should fail
            with pytest.raises(ValueError, match="Chef name is required"):
                db.add_iron_chef("")
            
            # None name should fail
            with pytest.raises(ValueError, match="Chef name is required"):
                db.add_iron_chef(None)
            
            # Too long name should fail
            with pytest.raises(ValueError, match="exceeds maximum length"):
                db.add_iron_chef("x" * 200)
    
    def test_add_competitor_valid(self, test_db):
        """Test adding valid competitor"""
        with IronChefDatabaseSecure(test_db) as db:
            comp_id = db.add_competitor(
                name="Test Competitor",
                restaurant="Test Restaurant",
                specialty="Test Style",
                location="Test City"
            )
            
            assert comp_id is not None
            assert comp_id > 0
            
            # Verify competitor was added
            db.cursor.execute("SELECT * FROM competitors WHERE id = ?", (comp_id,))
            competitor = db.cursor.fetchone()
            assert competitor['name'] == "Test Competitor"
            assert competitor['restaurant'] == "Test Restaurant"
    
    def test_add_competitor_invalid(self, test_db):
        """Test adding competitor with invalid data"""
        with IronChefDatabaseSecure(test_db) as db:
            # Empty name should fail
            with pytest.raises(ValueError, match="Competitor name is required"):
                db.add_competitor("")
            
            # Too long restaurant name should fail
            with pytest.raises(ValueError, match="exceeds maximum length"):
                db.add_competitor("Test", "x" * 300)
    
    def test_add_episode_valid(self, populated_db):
        """Test adding valid episode"""
        with IronChefDatabaseSecure(populated_db) as db:
            # Get existing chef and competitor IDs
            db.cursor.execute("SELECT id FROM iron_chefs LIMIT 1")
            chef_id = db.cursor.fetchone()['id']
            
            db.cursor.execute("SELECT id FROM competitors LIMIT 1")
            comp_id = db.cursor.fetchone()['id']
            
            episode_id = db.add_episode(
                episode_number=999,
                theme="Test Theme",
                iron_chef_id=chef_id,
                competitor_id=comp_id,
                air_date="2024-01-01",
                winner="Iron Chef",
                judges_scores="20-19"
            )
            
            assert episode_id is not None
            assert episode_id > 0
            
            # Verify episode was added
            db.cursor.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,))
            episode = db.cursor.fetchone()
            assert episode['episode_number'] == 999
            assert episode['theme'] == "Test Theme"
            assert episode['winner'] == "Iron Chef"
    
    def test_add_episode_invalid(self, populated_db):
        """Test adding episode with invalid data"""
        with IronChefDatabaseSecure(populated_db) as db:
            # Get valid IDs for foreign keys
            db.cursor.execute("SELECT id FROM iron_chefs LIMIT 1")
            chef_id = db.cursor.fetchone()['id']
            
            db.cursor.execute("SELECT id FROM competitors LIMIT 1") 
            comp_id = db.cursor.fetchone()['id']
            
            # Invalid episode number
            with pytest.raises(ValueError, match="episode number"):
                db.add_episode(0, "Theme", chef_id, comp_id)
            
            # Empty theme
            with pytest.raises(ValueError, match="Theme is required"):
                db.add_episode(1, "", chef_id, comp_id)
            
            # Invalid winner value
            with pytest.raises(ValueError, match="Winner must be"):
                db.add_episode(1, "Theme", chef_id, comp_id, winner="Invalid")
            
            # Invalid date format
            with pytest.raises(ValueError, match="air date"):
                db.add_episode(1, "Theme", chef_id, comp_id, air_date="not-a-date")
    
    def test_add_dish_valid(self, populated_db):
        """Test adding valid dish"""
        with IronChefDatabaseSecure(populated_db) as db:
            # Get existing episode ID
            db.cursor.execute("SELECT id FROM episodes LIMIT 1")
            episode_id = db.cursor.fetchone()['id']
            
            dish_id = db.add_dish(
                episode_id=episode_id,
                chef_type="iron_chef",
                dish_number=1,
                dish_name="Test Dish",
                description="A test dish for testing",
                main_ingredients="test ingredients",
                cooking_techniques="test techniques"
            )
            
            assert dish_id is not None
            assert dish_id > 0
            
            # Verify dish was added
            db.cursor.execute("SELECT * FROM dishes WHERE id = ?", (dish_id,))
            dish = db.cursor.fetchone()
            assert dish['dish_name'] == "Test Dish"
            assert dish['chef_type'] == "iron_chef"
    
    def test_add_dish_invalid(self, populated_db):
        """Test adding dish with invalid data"""
        with IronChefDatabaseSecure(populated_db) as db:
            # Get valid episode ID
            db.cursor.execute("SELECT id FROM episodes LIMIT 1")
            episode_id = db.cursor.fetchone()['id']
            
            # Invalid chef type
            with pytest.raises(ValueError, match="Chef type must be"):
                db.add_dish(episode_id, "invalid_chef", 1, "Test Dish")
            
            # Empty dish name
            with pytest.raises(ValueError, match="Dish name is required"):
                db.add_dish(episode_id, "iron_chef", 1, "")
            
            # Invalid dish number
            with pytest.raises(ValueError, match="dish number"):
                db.add_dish(episode_id, "iron_chef", 0, "Test Dish")
    
    def test_add_ingredient(self, test_db):
        """Test adding ingredients"""
        with IronChefDatabaseSecure(test_db) as db:
            # Add new ingredient
            ingredient_id = db.add_ingredient("Test Ingredient")
            assert ingredient_id is not None
            assert ingredient_id > 0
            
            # Try to add same ingredient again (should return existing ID)
            duplicate_id = db.add_ingredient("Test Ingredient")
            assert duplicate_id == ingredient_id
    
    def test_add_ingredient_invalid(self, test_db):
        """Test adding invalid ingredients"""
        with IronChefDatabaseSecure(test_db) as db:
            # Empty ingredient name
            with pytest.raises(ValueError, match="Ingredient name is required"):
                db.add_ingredient("")
            
            # Too long ingredient name
            with pytest.raises(ValueError, match="exceeds maximum length"):
                db.add_ingredient("x" * 200)
    
    def test_link_dish_ingredient(self, populated_db):
        """Test linking dishes to ingredients"""
        with IronChefDatabaseSecure(populated_db) as db:
            # Get existing dish and ingredient IDs
            db.cursor.execute("SELECT id FROM dishes LIMIT 1")
            dish_id = db.cursor.fetchone()['id']
            
            ingredient_id = db.add_ingredient("Test Link Ingredient")
            
            # Link dish to ingredient
            db.link_dish_ingredient(
                dish_id=dish_id,
                ingredient_id=ingredient_id,
                quantity="1 cup",
                unit="chopped"
            )
            
            # Verify link was created
            db.cursor.execute(
                "SELECT * FROM dish_ingredients WHERE dish_id = ? AND ingredient_id = ?",
                (dish_id, ingredient_id)
            )
            link = db.cursor.fetchone()
            assert link is not None
            assert link['quantity'] == "1 cup"
            assert link['unit'] == "chopped"
    
    def test_get_episode_details(self, populated_db):
        """Test retrieving episode details with dishes"""
        with IronChefDatabaseSecure(populated_db) as db:
            # Get an episode ID
            db.cursor.execute("SELECT id FROM episodes LIMIT 1")
            episode_id = db.cursor.fetchone()['id']
            
            episode_details = db.get_episode_details(episode_id)
            
            assert episode_details is not None
            assert 'dishes' in episode_details
            assert 'iron_chef' in episode_details['dishes']
            assert 'competitor' in episode_details['dishes']
            assert episode_details['iron_chef_name'] is not None
            assert episode_details['competitor_name'] is not None
    
    def test_get_episode_details_nonexistent(self, test_db):
        """Test retrieving details for non-existent episode"""
        with IronChefDatabaseSecure(test_db) as db:
            episode_details = db.get_episode_details(99999)
            assert episode_details is None
    
    def test_search_episodes_by_theme(self, populated_db):
        """Test searching episodes by theme"""
        with IronChefDatabaseSecure(populated_db) as db:
            # Search for existing theme
            results = db.search_episodes_by_theme("Lobster")
            assert len(results) > 0
            assert any("Lobster" in result['theme'] for result in results)
            
            # Search for partial match
            results = db.search_episodes_by_theme("Sea")
            assert len(results) > 0
            assert any("Sea" in result['theme'] for result in results)
            
            # Search for non-existent theme
            results = db.search_episodes_by_theme("NonExistentTheme")
            assert len(results) == 0
    
    def test_search_episodes_security(self, populated_db, malicious_inputs):
        """Test episode search with malicious inputs"""
        with IronChefDatabaseSecure(populated_db) as db:
            # Test SQL injection attempts
            for malicious in malicious_inputs['sql_injection']:
                try:
                    results = db.search_episodes_by_theme(malicious)
                    # Should not crash and should not return all records
                    assert isinstance(results, list)
                except ValueError:
                    # Validation rejection is acceptable
                    pass
    
    def test_get_all_themes(self, populated_db):
        """Test retrieving all unique themes"""
        with IronChefDatabaseSecure(populated_db) as db:
            themes = db.get_all_themes()
            assert isinstance(themes, list)
            assert len(themes) > 0
            assert "Lobster" in themes
            assert "Sea Bream" in themes
    
    def test_get_dishes_by_ingredient(self, populated_db):
        """Test finding dishes by ingredient"""
        with IronChefDatabaseSecure(populated_db) as db:
            # Search for existing ingredient
            results = db.get_dishes_by_ingredient("lobster")
            assert len(results) > 0
            assert any("lobster" in result['main_ingredients'].lower() for result in results)
            
            # Search for non-existent ingredient
            results = db.get_dishes_by_ingredient("nonexistent")
            assert len(results) == 0
    
    def test_add_recipe_valid(self, populated_db, sample_recipe_data):
        """Test adding valid recipe"""
        with IronChefDatabaseSecure(populated_db) as db:
            # Get existing dish ID
            db.cursor.execute("SELECT id FROM dishes LIMIT 1")
            dish_id = db.cursor.fetchone()['id']
            
            recipe_id = db.add_recipe(
                dish_id=dish_id,
                recipe_title=sample_recipe_data['title'],
                ingredients=json.dumps(sample_recipe_data['ingredients']),
                instructions=json.dumps(sample_recipe_data['instructions']),
                prep_time=sample_recipe_data['prep_time'],
                cook_time=sample_recipe_data['cook_time'],
                servings=sample_recipe_data['servings']
            )
            
            assert recipe_id is not None
            assert recipe_id > 0
            
            # Verify recipe was added
            db.cursor.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
            recipe = db.cursor.fetchone()
            assert recipe['recipe_title'] == sample_recipe_data['title']
            assert recipe['prep_time'] == sample_recipe_data['prep_time']
    
    def test_add_recipe_invalid(self, populated_db):
        """Test adding recipe with invalid data"""
        with IronChefDatabaseSecure(populated_db) as db:
            # Get valid dish ID
            db.cursor.execute("SELECT id FROM dishes LIMIT 1")
            dish_id = db.cursor.fetchone()['id']
            
            # Empty title
            with pytest.raises(ValueError, match="Recipe title is required"):
                db.add_recipe(dish_id, "", "[]", "[]")
            
            # Invalid JSON for ingredients
            with pytest.raises(ValueError, match="Invalid ingredients format"):
                db.add_recipe(dish_id, "Test Recipe", "invalid json", "[]")
            
            # Invalid JSON for instructions
            with pytest.raises(ValueError, match="Invalid instructions format"):
                db.add_recipe(dish_id, "Test Recipe", "[]", "invalid json")
            
            # Invalid prep time
            with pytest.raises(ValueError, match="prep time"):
                db.add_recipe(dish_id, "Test Recipe", "[]", "[]", prep_time=-1)
    
    @pytest.mark.slow
    def test_database_transactions(self, test_db):
        """Test database transaction handling"""
        # Test successful transaction
        with IronChefDatabaseSecure(test_db) as db:
            chef_id = db.add_iron_chef("Transaction Test Chef")
            assert chef_id is not None
        
        # Verify data was committed
        with IronChefDatabaseSecure(test_db) as db:
            db.cursor.execute("SELECT * FROM iron_chefs WHERE name = ?", ("Transaction Test Chef",))
            chef = db.cursor.fetchone()
            assert chef is not None
        
        # Test transaction rollback on exception
        try:
            with IronChefDatabaseSecure(test_db) as db:
                db.add_iron_chef("Should Rollback Chef")
                raise Exception("Test exception")
        except:
            pass
        
        # Verify rollback occurred
        with IronChefDatabaseSecure(test_db) as db:
            db.cursor.execute("SELECT * FROM iron_chefs WHERE name = ?", ("Should Rollback Chef",))
            chef = db.cursor.fetchone()
            assert chef is None
    
    def test_foreign_key_constraints(self, test_db):
        """Test foreign key constraint enforcement"""
        with IronChefDatabaseSecure(test_db) as db:
            # Try to add episode with non-existent chef ID
            with pytest.raises(sqlite3.IntegrityError):
                db.add_episode(1, "Test Theme", 99999, 99999)


@pytest.mark.integration 
@pytest.mark.database
class TestDatabaseIntegration:
    """Integration tests for database operations"""
    
    def test_full_episode_workflow(self, test_db):
        """Test complete workflow from chef creation to episode details"""
        with IronChefDatabaseSecure(test_db) as db:
            # Create chef
            chef_id = db.add_iron_chef("Integration Chef", "Iron Chef", "Test Cuisine", "2024")
            
            # Create competitor
            comp_id = db.add_competitor("Integration Competitor", "Test Restaurant", "Test Style", "Test City")
            
            # Create episode
            episode_id = db.add_episode(1, "Integration Theme", chef_id, comp_id, winner="Iron Chef")
            
            # Create dishes
            dish1_id = db.add_dish(episode_id, "iron_chef", 1, "Chef Dish", main_ingredients="test ingredients")
            dish2_id = db.add_dish(episode_id, "competitor", 1, "Competitor Dish", main_ingredients="other ingredients")
            
            # Create ingredients and link
            ingredient_id = db.add_ingredient("Integration Ingredient")
            db.link_dish_ingredient(dish1_id, ingredient_id, "1 cup", "diced")
            
            # Get episode details and verify everything is connected
            episode_details = db.get_episode_details(episode_id)
            
            assert episode_details['iron_chef_name'] == "Integration Chef"
            assert episode_details['competitor_name'] == "Integration Competitor"
            assert episode_details['theme'] == "Integration Theme"
            assert len(episode_details['dishes']['iron_chef']) == 1
            assert len(episode_details['dishes']['competitor']) == 1
    
    def test_search_and_filter_operations(self, populated_db):
        """Test various search and filtering operations"""
        with IronChefDatabaseSecure(populated_db) as db:
            # Test theme search
            lobster_episodes = db.search_episodes_by_theme("Lobster")
            sea_episodes = db.search_episodes_by_theme("Sea")
            
            assert len(lobster_episodes) > 0
            assert len(sea_episodes) > 0
            
            # Test ingredient search
            lobster_dishes = db.get_dishes_by_ingredient("lobster")
            assert len(lobster_dishes) > 0
            
            # Test theme listing
            all_themes = db.get_all_themes()
            assert "Lobster" in all_themes
            assert "Sea Bream" in all_themes
    
    @pytest.mark.slow
    def test_performance_with_large_dataset(self, test_db):
        """Test database performance with larger dataset"""
        with IronChefDatabaseSecure(test_db) as db:
            # Create multiple chefs, competitors, and episodes
            chef_ids = []
            comp_ids = []
            
            # Create 10 chefs
            for i in range(10):
                chef_id = db.add_iron_chef(f"Chef {i}", f"Iron Chef {i}", f"Cuisine {i}", "2024")
                chef_ids.append(chef_id)
            
            # Create 20 competitors  
            for i in range(20):
                comp_id = db.add_competitor(f"Competitor {i}", f"Restaurant {i}", f"Style {i}", f"City {i}")
                comp_ids.append(comp_id)
            
            # Create 50 episodes with dishes
            for i in range(50):
                chef_id = chef_ids[i % len(chef_ids)]
                comp_id = comp_ids[i % len(comp_ids)]
                
                episode_id = db.add_episode(i + 1, f"Theme {i}", chef_id, comp_id)
                
                # Add dishes for each episode
                db.add_dish(episode_id, "iron_chef", 1, f"Iron Chef Dish {i}")
                db.add_dish(episode_id, "competitor", 1, f"Competitor Dish {i}")
            
            # Test search performance
            import time
            start_time = time.time()
            
            # Perform various searches
            all_episodes = db.search_episodes_by_theme("")
            themes = db.get_all_themes()
            
            end_time = time.time()
            
            # Should complete in reasonable time (less than 1 second)
            assert end_time - start_time < 1.0
            assert len(all_episodes) == 50
            assert len(themes) == 50