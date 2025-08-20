"""
Shared pytest fixtures for Iron Chef Recipe Database tests
"""

import os
import tempfile
import shutil
import sqlite3
import pytest
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from iron_chef_database_secure import IronChefDatabaseSecure, SecurityValidator
from recipe_generator import RecipeGenerator
from recipe_exporter_secure import SecureRecipeExporter


@pytest.fixture(scope="function")
def temp_db_path():
    """Create a temporary database file for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(scope="function")
def temp_dir():
    """Create a temporary directory for testing"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    # Cleanup
    if os.path.exists(temp_path):
        shutil.rmtree(temp_path)


@pytest.fixture(scope="function")
def test_db(temp_db_path):
    """Create a test database with schema initialized"""
    # Copy schema to temp location for test
    schema_path = Path(__file__).parent.parent / "database_schema.sql"
    
    with IronChefDatabaseSecure(temp_db_path) as db:
        # Read and execute schema
        with open(schema_path, 'r') as f:
            schema = f.read()
        db.cursor.executescript(schema)
        db.connection.commit()
    
    yield temp_db_path


@pytest.fixture(scope="function")
def populated_db(test_db):
    """Create a test database with sample data"""
    with IronChefDatabaseSecure(test_db) as db:
        # Add sample iron chefs
        chef1_id = db.add_iron_chef(
            "Chen Kenichi", 
            "Iron Chef Chinese", 
            "Szechuan Cuisine", 
            "1993-2012"
        )
        chef2_id = db.add_iron_chef(
            "Michiba Rokusaburo", 
            "Iron Chef Japanese", 
            "Traditional Japanese", 
            "1993-1996"
        )
        
        # Add sample competitors
        comp1_id = db.add_competitor(
            "Test Challenger 1",
            "Test Restaurant 1", 
            "French Cuisine",
            "Tokyo"
        )
        comp2_id = db.add_competitor(
            "Test Challenger 2",
            "Test Restaurant 2",
            "Italian Cuisine", 
            "Osaka"
        )
        
        # Add sample episodes
        episode1_id = db.add_episode(
            episode_number=1,
            theme="Lobster",
            iron_chef_id=chef1_id,
            competitor_id=comp1_id,
            air_date="1993-10-10",
            winner="Iron Chef",
            judges_scores="20-18"
        )
        
        episode2_id = db.add_episode(
            episode_number=2,
            theme="Sea Bream",
            iron_chef_id=chef2_id,
            competitor_id=comp2_id,
            air_date="1993-10-17",
            winner="Competitor",
            judges_scores="19-20"
        )
        
        # Add sample dishes
        dish1_id = db.add_dish(
            episode_id=episode1_id,
            chef_type="iron_chef",
            dish_number=1,
            dish_name="Szechuan Lobster with Spicy Sauce",
            description="A fiery lobster dish with traditional Szechuan flavors",
            main_ingredients="lobster, szechuan peppercorns, chili oil",
            cooking_techniques="stir-fry, deep-fry"
        )
        
        dish2_id = db.add_dish(
            episode_id=episode1_id,
            chef_type="competitor",
            dish_number=1,
            dish_name="French Lobster Bisque",
            description="Classic French lobster bisque with cognac",
            main_ingredients="lobster, cream, cognac, tomato",
            cooking_techniques="simmer, strain, reduce"
        )
        
        dish3_id = db.add_dish(
            episode_id=episode2_id,
            chef_type="iron_chef",
            dish_number=1,
            dish_name="Sea Bream Sashimi",
            description="Fresh sea bream served as sashimi",
            main_ingredients="sea bream, wasabi, soy sauce",
            cooking_techniques="knife work, preparation"
        )
        
        # Add some ingredients
        lobster_id = db.add_ingredient("Lobster")
        sea_bream_id = db.add_ingredient("Sea Bream")
        wasabi_id = db.add_ingredient("Wasabi")
        
        # Link dishes to ingredients
        db.link_dish_ingredient(dish1_id, lobster_id, "1 lb", "whole")
        db.link_dish_ingredient(dish2_id, lobster_id, "2 lbs", "shells")
        db.link_dish_ingredient(dish3_id, sea_bream_id, "1 lb", "fillet")
        db.link_dish_ingredient(dish3_id, wasabi_id, "1 tsp", "fresh")
        
        # Store IDs for test reference
        db._test_data = {
            'chefs': [chef1_id, chef2_id],
            'competitors': [comp1_id, comp2_id],
            'episodes': [episode1_id, episode2_id],
            'dishes': [dish1_id, dish2_id, dish3_id],
            'ingredients': [lobster_id, sea_bream_id, wasabi_id]
        }
    
    yield test_db


@pytest.fixture(scope="function")
def db_connection(populated_db):
    """Provide a database connection for tests"""
    with IronChefDatabaseSecure(populated_db) as db:
        yield db


@pytest.fixture(scope="function")
def security_validator():
    """Provide a SecurityValidator instance"""
    return SecurityValidator()


@pytest.fixture(scope="function") 
def recipe_generator():
    """Provide a RecipeGenerator instance"""
    return RecipeGenerator()


@pytest.fixture(scope="function")
def secure_exporter(temp_dir):
    """Provide a SecureRecipeExporter instance with temp directory"""
    return SecureRecipeExporter(output_dir=temp_dir)


@pytest.fixture(scope="function")
def sample_recipe_data():
    """Provide sample recipe data for testing"""
    return {
        'title': 'Test Iron Chef Recipe',
        'description': 'A test recipe for unit testing',
        'servings': 4,
        'prep_time': 20,
        'cook_time': 30,
        'ingredients': [
            {'item': 'Test Ingredient 1', 'amount': '1 lb', 'prep': 'cleaned'},
            {'item': 'Test Ingredient 2', 'amount': '2 tbsp', 'prep': 'chopped'}
        ],
        'instructions': [
            'Prepare all ingredients mise en place',
            'Cook using appropriate technique',
            'Season to taste',
            'Plate and serve immediately'
        ],
        'chef_tips': [
            'Use the freshest ingredients possible',
            'Taste and adjust seasoning throughout'
        ],
        'wine_pairing': 'Sake'
    }


@pytest.fixture(scope="function")
def malicious_inputs():
    """Provide various malicious input strings for security testing"""
    return {
        'sql_injection': [
            "'; DROP TABLE episodes; --",
            "' UNION SELECT * FROM iron_chefs --",
            "Lobster' OR '1'='1",
            "test\x00'; DROP TABLE recipes; --"
        ],
        'path_traversal': [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config",
            "/etc/passwd",
            "C:\\Windows\\System32\\config",
            "%2e%2e%2f%2e%2e%2fetc%2fpasswd"
        ],
        'xss_attempts': [
            "<script>alert('XSS')</script>",
            "javascript:alert('XSS')",
            "<img src=x onerror=alert('XSS')>",
            "' onmouseover='alert(1)' '",
            "<svg onload=alert('XSS')>"
        ],
        'long_strings': [
            'A' * 1000,  # Overly long input
            'B' * 10000,  # Very long input
            '测试' * 500  # Unicode characters
        ],
        'special_characters': [
            "test\x00null",  # Null bytes
            "test\r\nheader",  # CRLF injection
            "test\x1f\x7f",  # Control characters
            "🍣🍜🍱",  # Emoji
            "café résumé naïve"  # Accented characters
        ]
    }


@pytest.fixture(autouse=True)
def cleanup_test_files():
    """Automatically cleanup test files after each test"""
    yield
    # Cleanup any test database files that might be left behind
    test_files = [
        "test_security.db",
        "test_temp.db", 
        "test_export.db"
    ]
    for file in test_files:
        if os.path.exists(file):
            try:
                os.unlink(file)
            except:
                pass


# Test markers for categorizing tests
pytest_plugins = []


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "security: marks tests as security-focused tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )
    config.addinivalue_line(
        "markers", "database: marks tests that require database operations"
    )
    config.addinivalue_line(
        "markers", "filesystem: marks tests that require filesystem operations"
    )


# Performance measurement fixtures
@pytest.fixture
def benchmark_timer():
    """Simple benchmark timer for performance testing"""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
            return self.elapsed
        
        @property
        def elapsed(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None
    
    return Timer()