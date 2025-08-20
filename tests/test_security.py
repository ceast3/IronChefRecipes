"""
Security Test Suite for Iron Chef Recipe Database
Tests SQL injection protection, path traversal prevention, and input validation
Enhanced for pytest framework with comprehensive security testing
"""

import pytest
import os
import sys
import tempfile
import shutil
import sqlite3
import json
import threading
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from iron_chef_database_secure import IronChefDatabaseSecure, SecurityValidator
from recipe_exporter_secure import SecureRecipeExporter
from recipe_generator import RecipeGenerator


@pytest.mark.security
@pytest.mark.database
class TestSQLInjectionProtection:
    """Test SQL injection protection across all database operations"""
    
    def test_classic_sql_injection_search(self, populated_db, malicious_inputs):
        """Test classic SQL injection attempts in search operations"""
        with IronChefDatabaseSecure(populated_db) as db:
            for malicious in malicious_inputs['sql_injection']:
                # Should not crash or return unauthorized data
                try:
                    results = db.search_episodes_by_theme(malicious)
                    assert isinstance(results, list)
                    # Should not return all records (which would indicate successful injection)
                    if results:
                        # Verify results are actually theme-related, not all episodes
                        assert all('theme' in str(result).lower() for result in results)
                except ValueError:
                    # Input validation rejection is acceptable
                    pass
    
    def test_sql_injection_ingredient_search(self, populated_db, malicious_inputs):
        """Test SQL injection protection in ingredient search"""
        with IronChefDatabaseSecure(populated_db) as db:
            for malicious in malicious_inputs['sql_injection']:
                try:
                    results = db.get_dishes_by_ingredient(malicious)
                    assert isinstance(results, list)
                except ValueError:
                    # Validation rejection is acceptable
                    pass
    
    def test_second_order_sql_injection(self, test_db):
        """Test second-order SQL injection through stored data"""
        with IronChefDatabaseSecure(test_db) as db:
            # Try to store malicious data that could be executed later
            malicious_names = [
                "Chef'; DROP TABLE episodes; --",
                "Competitor' UNION SELECT * FROM iron_chefs --",
                "Theme' OR '1'='1' --"
            ]
            
            for malicious_name in malicious_names:
                try:
                    # Store malicious data
                    chef_id = db.add_iron_chef(malicious_name, "Title", "Specialty", "2024")
                    
                    # Try to retrieve it - should be stored safely
                    db.cursor.execute("SELECT * FROM iron_chefs WHERE id = ?", (chef_id,))
                    result = db.cursor.fetchone()
                    
                    # Verify the data was sanitized or stored safely
                    assert result is not None
                    stored_name = result['name']
                    
                    # The malicious SQL should not be present in executable form
                    # or should be escaped/sanitized
                    assert "DROP TABLE" not in stored_name or stored_name != malicious_name
                    
                except ValueError:
                    # Input validation rejection is also acceptable
                    pass
    
    def test_sql_injection_parameterized_queries(self, populated_db):
        """Verify that parameterized queries are used correctly"""
        with IronChefDatabaseSecure(populated_db) as db:
            # Test that our queries use parameterization
            # by ensuring SQL injection attempts don't work
            
            # Attempt to inject through episode details
            try:
                # This should treat the input as a literal integer, not SQL
                result = db.get_episode_details("1; DROP TABLE episodes; --")
                # Should either fail validation or return None (not found)
                assert result is None
            except (ValueError, TypeError):
                # Type/validation error is expected and acceptable
                pass
    
    def test_sql_injection_in_recipe_operations(self, populated_db):
        """Test SQL injection protection in recipe operations"""
        with IronChefDatabaseSecure(populated_db) as db:
            # Get a valid dish ID
            db.cursor.execute("SELECT id FROM dishes LIMIT 1")
            dish_id = db.cursor.fetchone()['id']
            
            # Try malicious data in recipe fields
            malicious_json = '{"malicious": "\'; DROP TABLE recipes; --"}'
            
            try:
                recipe_id = db.add_recipe(
                    dish_id=dish_id,
                    recipe_title="'; DROP TABLE recipes; --",
                    ingredients=malicious_json,
                    instructions=malicious_json,
                    prep_time=20,
                    cook_time=30,
                    servings=4
                )
                
                # If it succeeds, verify the data is stored safely
                if recipe_id:
                    db.cursor.execute("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
                    result = db.cursor.fetchone()
                    assert result is not None
                    # Malicious SQL should not be executed
                    
            except ValueError:
                # Validation rejection is acceptable
                pass


@pytest.mark.security
@pytest.mark.filesystem
class TestPathTraversalProtection:
    """Test path traversal protection in file operations"""
    
    def test_filename_traversal_basic(self, secure_exporter, malicious_inputs):
        """Test basic path traversal protection"""
        for malicious_path in malicious_inputs['path_traversal']:
            sanitized = secure_exporter._sanitize_filename(malicious_path, ".txt")
            
            # Should not contain traversal sequences
            assert ".." not in sanitized
            assert "/" not in sanitized
            assert "\\" not in sanitized
            assert not sanitized.startswith("/")
            assert sanitized.endswith(".txt")
    
    def test_filepath_containment(self, secure_exporter, malicious_inputs):
        """Test that file paths are contained within export directory"""
        for malicious_path in malicious_inputs['path_traversal']:
            try:
                safe_path = secure_exporter._get_safe_filepath(malicious_path, ".txt")
                
                # Verify path is within export directory
                abs_safe_path = os.path.abspath(safe_path)
                abs_export_path = os.path.abspath(secure_exporter.export_path)
                
                assert abs_safe_path.startswith(abs_export_path), \
                    f"Path {abs_safe_path} escapes export directory {abs_export_path}"
                    
            except ValueError:
                # Rejection of dangerous paths is acceptable
                pass
    
    def test_hidden_file_prevention(self, secure_exporter):
        """Test prevention of hidden file creation"""
        hidden_files = [".bashrc", "..hidden", "...file", ".ssh/config"]
        
        for hidden_file in hidden_files:
            sanitized = secure_exporter._sanitize_filename(hidden_file, ".txt")
            assert not sanitized.startswith("."), f"Hidden file created: {sanitized}"
    
    def test_special_filesystem_names(self, secure_exporter):
        """Test handling of special filesystem names"""
        special_names = [
            "CON", "PRN", "AUX", "NUL",  # Windows reserved
            "COM1", "LPT1",  # Windows device names
            ".",  # Current directory
            "..",  # Parent directory
            "",  # Empty name
        ]
        
        for name in special_names:
            sanitized = secure_exporter._sanitize_filename(name, ".txt")
            
            # Should produce a safe, non-empty filename
            assert len(sanitized) > 4  # At least ".txt"
            assert sanitized.endswith(".txt")
            assert sanitized not in [".", "..", "CON.txt", "PRN.txt"]
    
    def test_unicode_filename_handling(self, secure_exporter):
        """Test handling of Unicode characters in filenames"""
        unicode_names = [
            "файл.txt",  # Cyrillic
            "文件.txt",   # Chinese
            "ファイル.txt", # Japanese
            "📁file.txt",  # Emoji
            "café.txt",    # Accented characters
        ]
        
        for name in unicode_names:
            sanitized = secure_exporter._sanitize_filename(name, ".txt")
            
            # Should produce a valid filename
            assert len(sanitized) > 0
            assert sanitized.endswith(".txt")
            # Characters may be replaced, but should not crash


@pytest.mark.security
class TestInputValidation:
    """Test comprehensive input validation"""
    
    def test_integer_validation_boundaries(self, security_validator):
        """Test integer validation at boundaries"""
        # Test minimum boundary
        assert security_validator.validate_integer(0, min_val=0) == 0
        with pytest.raises(ValueError):
            security_validator.validate_integer(-1, min_val=0)
        
        # Test maximum boundary
        assert security_validator.validate_integer(100, max_val=100) == 100
        with pytest.raises(ValueError):
            security_validator.validate_integer(101, max_val=100)
        
        # Test type conversion
        assert security_validator.validate_integer("42") == 42
        assert security_validator.validate_integer(42.0) == 42
        
        # Test invalid types
        with pytest.raises(ValueError):
            security_validator.validate_integer("not_a_number")
        with pytest.raises(ValueError):
            security_validator.validate_integer([42])
    
    def test_string_validation_comprehensive(self, security_validator, malicious_inputs):
        """Test comprehensive string validation"""
        # Test length limits
        long_string = "x" * 1000
        with pytest.raises(ValueError, match="exceeds maximum length"):
            security_validator.validate_string(long_string, max_length=100)
        
        # Test null byte removal
        test_string = "test\x00null\x00bytes"
        result = security_validator.validate_string(test_string)
        assert "\x00" not in result
        assert result == "testnullbytes"
        
        # Test whitespace trimming
        assert security_validator.validate_string("  test  ") == "test"
        
        # Test pattern validation
        assert security_validator.validate_string("test123", pattern=r'^[a-zA-Z0-9]+$') == "test123"
        with pytest.raises(ValueError, match="contains invalid characters"):
            security_validator.validate_string("test@#$", pattern=r'^[a-zA-Z0-9]+$')
        
        # Test malicious inputs
        for malicious in malicious_inputs['xss_attempts']:
            try:
                result = security_validator.validate_string(malicious, max_length=200)
                # Should not crash and should return sanitized string
                assert isinstance(result, str)
            except ValueError:
                # Rejection is also acceptable
                pass
    
    def test_sql_pattern_sanitization(self, security_validator):
        """Test SQL LIKE pattern sanitization"""
        # Test basic sanitization
        assert security_validator.sanitize_sql_pattern("test") == "%test%"
        assert security_validator.sanitize_sql_pattern("") == "%"
        assert security_validator.sanitize_sql_pattern(None) == "%"
        
        # Test special character escaping
        pattern = "test%_[\\with]special"
        result = security_validator.sanitize_sql_pattern(pattern)
        
        # Should escape SQL special characters
        assert "\\%" in result
        assert "\\_" in result  
        assert "\\[" in result
        assert "\\\\" in result
    
    def test_filename_validation_comprehensive(self, security_validator):
        """Test comprehensive filename validation"""
        # Valid filenames
        assert security_validator.validate_filename("test.txt") == "test.txt"
        assert security_validator.validate_filename("recipe_1.json") == "recipe_1.json"
        
        # Path traversal prevention
        dangerous_names = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "/absolute/path/file.txt",
            "C:\\Windows\\file.txt"
        ]
        
        for dangerous in dangerous_names:
            with pytest.raises(ValueError, match="Invalid filename"):
                security_validator.validate_filename(dangerous)
        
        # Special character handling
        result = security_validator.validate_filename("file@#$%.txt")
        assert "@" not in result
        assert "#" not in result
        assert "$" not in result
        
        # Extension handling
        result = security_validator.validate_filename("test")
        assert result.endswith(".txt")
        
        # Empty filename
        with pytest.raises(ValueError, match="Filename cannot be empty"):
            security_validator.validate_filename("")


@pytest.mark.security
@pytest.mark.database
class TestDatabaseSecurityIntegration:
    """Test security integration in database operations"""
    
    def test_foreign_key_enforcement(self, test_db):
        """Test that foreign key constraints prevent data integrity issues"""
        with IronChefDatabaseSecure(test_db) as db:
            # Try to add episode with non-existent chef/competitor
            with pytest.raises(sqlite3.IntegrityError):
                db.add_episode(1, "Test Theme", 99999, 99999)
            
            # Try to add dish with non-existent episode
            with pytest.raises(sqlite3.IntegrityError):
                db.add_dish(99999, "iron_chef", 1, "Test Dish")
    
    def test_data_type_validation(self, populated_db):
        """Test data type validation in database operations"""
        with IronChefDatabaseSecure(populated_db) as db:
            # Test invalid data types
            with pytest.raises(ValueError):
                db.add_episode("not_a_number", "Theme", 1, 1)
            
            with pytest.raises(ValueError):
                db.add_dish(1, "invalid_chef_type", 1, "Dish")
            
            with pytest.raises(ValueError):
                db.add_episode(1, "Theme", 1, 1, winner="InvalidWinner")
    
    def test_transaction_isolation(self, test_db):
        """Test that database transactions are properly isolated"""
        # Test that failed transactions don't affect database state
        initial_count = 0
        
        with IronChefDatabaseSecure(test_db) as db:
            db.cursor.execute("SELECT COUNT(*) FROM iron_chefs")
            initial_count = db.cursor.fetchone()[0]
        
        # Start transaction that should fail
        try:
            with IronChefDatabaseSecure(test_db) as db:
                db.add_iron_chef("Test Chef", "Title", "Specialty", "2024")
                # Force an error to trigger rollback
                raise Exception("Simulated error")
        except:
            pass
        
        # Verify rollback occurred
        with IronChefDatabaseSecure(test_db) as db:
            db.cursor.execute("SELECT COUNT(*) FROM iron_chefs")
            final_count = db.cursor.fetchone()[0]
            assert final_count == initial_count


@pytest.mark.security
class TestXSSPrevention:
    """Test XSS prevention in data handling"""
    
    def test_xss_in_data_storage(self, test_db, malicious_inputs):
        """Test that XSS attempts are handled safely in data storage"""
        with IronChefDatabaseSecure(test_db) as db:
            for xss_attempt in malicious_inputs['xss_attempts']:
                try:
                    # Try to store XSS payload in various fields
                    chef_id = db.add_iron_chef(xss_attempt, "Title", "Specialty", "2024")
                    
                    # Retrieve and verify it's stored safely
                    db.cursor.execute("SELECT name FROM iron_chefs WHERE id = ?", (chef_id,))
                    stored_name = db.cursor.fetchone()['name']
                    
                    # Data should be stored (possibly sanitized) but not executed
                    assert isinstance(stored_name, str)
                    
                except ValueError:
                    # Input validation rejection is acceptable
                    pass
    
    def test_xss_in_recipe_generation(self, recipe_generator, malicious_inputs):
        """Test XSS prevention in recipe generation"""
        for xss_attempt in malicious_inputs['xss_attempts'][:3]:  # Test first 3
            try:
                recipe = recipe_generator.generate_recipe(
                    dish_name=xss_attempt,
                    main_ingredients="test ingredients",
                    cuisine_style="Japanese"
                )
                
                # Recipe should be generated safely
                assert isinstance(recipe, dict)
                assert 'title' in recipe
                
                # XSS payload should not be executable in output
                title = recipe['title']
                assert isinstance(title, str)
                
            except ValueError:
                # Validation rejection is acceptable
                pass
    
    def test_xss_in_export_data(self, secure_exporter, temp_dir):
        """Test XSS prevention in exported data"""
        xss_data = [
            {
                'episode_number': 1,
                'theme': '<script>alert("XSS")</script>',
                'iron_chef_name': 'javascript:alert("XSS")',
                'competitor_name': 'Normal Name',
                'winner': 'Iron Chef'
            }
        ]
        
        # Export as JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
            try:
                secure_exporter._export_episodes_json(xss_data, tmp.name)
                
                # Read back and verify XSS is not executable
                with open(tmp.name, 'r') as f:
                    content = f.read()
                
                # Should contain escaped/safe versions
                assert 'script' in content.lower()  # May contain as text
                # But should be JSON-escaped and not executable
                
                # Verify it's valid JSON
                import json
                data = json.loads(content)
                assert len(data) == 1
                
            finally:
                os.unlink(tmp.name)


@pytest.mark.security
@pytest.mark.slow
class TestSecurityPerformance:
    """Test security measures don't significantly impact performance"""
    
    def test_validation_performance(self, security_validator, benchmark_timer):
        """Test that input validation performs acceptably"""
        test_strings = ["test string"] * 1000
        
        benchmark_timer.start()
        
        for test_string in test_strings:
            security_validator.validate_string(test_string, max_length=100)
        
        elapsed = benchmark_timer.stop()
        
        # Should validate 1000 strings in reasonable time (< 1 second)
        assert elapsed < 1.0
    
    def test_sql_injection_protection_performance(self, populated_db, benchmark_timer):
        """Test SQL injection protection doesn't severely impact query performance"""
        search_terms = ["Lobster", "Sea Bream", "Test"] * 100
        
        benchmark_timer.start()
        
        with IronChefDatabaseSecure(populated_db) as db:
            for term in search_terms:
                db.search_episodes_by_theme(term)
        
        elapsed = benchmark_timer.stop()
        
        # Should complete 300 searches in reasonable time (< 5 seconds)
        assert elapsed < 5.0


@pytest.mark.security
class TestConcurrencySecurityIssues:
    """Test security in concurrent access scenarios"""
    
    def test_concurrent_database_access(self, test_db):
        """Test that concurrent database access doesn't create security issues"""
        results = []
        errors = []
        
        def database_worker(worker_id):
            try:
                with IronChefDatabaseSecure(test_db) as db:
                    # Each worker adds data
                    chef_id = db.add_iron_chef(f"Chef {worker_id}", "Title", "Specialty", "2024")
                    results.append((worker_id, chef_id))
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # Start multiple workers
        threads = []
        for i in range(5):
            thread = threading.Thread(target=database_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify no security issues occurred
        assert len(errors) == 0, f"Errors in concurrent access: {errors}"
        assert len(results) == 5
        
        # Verify data integrity
        with IronChefDatabaseSecure(test_db) as db:
            db.cursor.execute("SELECT COUNT(*) FROM iron_chefs")
            count = db.cursor.fetchone()[0]
            assert count == 5
    
    def test_concurrent_file_operations(self, temp_dir):
        """Test that concurrent file operations don't create security issues"""
        results = []
        errors = []
        
        def file_worker(worker_id):
            try:
                exporter = SecureRecipeExporter(output_dir=temp_dir)
                filepath = exporter._get_safe_filepath(f"worker_{worker_id}", ".txt")
                
                # Write test file
                with open(filepath, 'w') as f:
                    f.write(f"Worker {worker_id} output")
                
                results.append((worker_id, filepath))
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # Start multiple workers
        threads = []
        for i in range(5):
            thread = threading.Thread(target=file_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify no security issues
        assert len(errors) == 0, f"Errors in concurrent file operations: {errors}"
        assert len(results) == 5
        
        # Verify all files are within safe directory
        export_path = os.path.join(temp_dir, 'exports')
        for worker_id, filepath in results:
            assert filepath.startswith(export_path)
            assert os.path.exists(filepath)


@pytest.mark.security
class TestEdgeCaseSecurityIssues:
    """Test security with edge cases and boundary conditions"""
    
    def test_memory_exhaustion_protection(self, security_validator):
        """Test protection against memory exhaustion attacks"""
        # Very long string should be rejected, not cause memory issues
        very_long_string = "x" * (10 * 1024 * 1024)  # 10MB string
        
        with pytest.raises(ValueError, match="exceeds maximum length"):
            security_validator.validate_string(very_long_string, max_length=1000)
    
    def test_null_and_control_character_handling(self, security_validator):
        """Test handling of null bytes and control characters"""
        test_strings = [
            "test\x00null",
            "test\x01control",
            "test\x1funit_separator",
            "test\x7fdelete",
            "test\r\nline_break",
            "test\ttab"
        ]
        
        for test_string in test_strings:
            result = security_validator.validate_string(test_string)
            
            # Should handle gracefully
            assert isinstance(result, str)
            assert "\x00" not in result  # Null bytes should be removed
    
    def test_unicode_normalization_attacks(self, security_validator):
        """Test protection against Unicode normalization attacks"""
        # Different Unicode representations of same character
        unicode_variations = [
            "café",  # é as single character
            "cafe\u0301",  # é as e + combining acute accent
            "file\u202e.txt\u202d",  # Right-to-left override attack
        ]
        
        for variant in unicode_variations:
            try:
                result = security_validator.validate_string(variant, max_length=100)
                assert isinstance(result, str)
            except ValueError:
                # Rejection of complex Unicode is acceptable
                pass
    
    def test_time_based_attacks_resistance(self, security_validator):
        """Test that validation timing doesn't leak information"""
        import time
        
        # Test that validation time is consistent for different inputs
        test_cases = [
            "short",
            "a" * 100,  # longer string
            "complex@#$%string!",
            "unicode_测试_string"
        ]
        
        times = []
        for test_case in test_cases:
            start_time = time.time()
            try:
                security_validator.validate_string(test_case, max_length=200)
            except:
                pass
            end_time = time.time()
            times.append(end_time - start_time)
        
        # Times should be relatively consistent (not revealing information)
        # Allow for some variation but check they're in same order of magnitude
        max_time = max(times)
        min_time = min(times)
        
        # Should not vary by more than 100x (very generous)
        if min_time > 0:
            assert max_time / min_time < 100


# Integration test combining multiple security aspects
@pytest.mark.security
@pytest.mark.integration 
@pytest.mark.slow
class TestSecurityIntegration:
    """Integration tests combining multiple security aspects"""
    
    def test_end_to_end_security_workflow(self, temp_dir):
        """Test complete workflow with security considerations"""
        # Create secure database
        db_path = os.path.join(temp_dir, "secure_test.db")
        
        with IronChefDatabaseSecure(db_path) as db:
            db.initialize_database()
            
            # Add data with potential security issues
            chef_id = db.add_iron_chef(
                "Chef's \"Special\" <Name>",  # Quotes and brackets
                "Iron Chef & Master",  # Ampersand
                "Japanese/French Fusion",  # Slash
                "1990-2024"
            )
            
            comp_id = db.add_competitor(
                "Challenger #1",  # Hash symbol
                "Restaurant@Home",  # At symbol
                "50% Traditional",  # Percent
                "City, State"  # Comma
            )
            
            episode_id = db.add_episode(
                episode_number=1,
                theme="Sea & Land Special",
                iron_chef_id=chef_id,
                competitor_id=comp_id,
                winner="Iron Chef"
            )
            
            dish_id = db.add_dish(
                episode_id=episode_id,
                chef_type="iron_chef",
                dish_number=1,
                dish_name="Fusion Dish #1",
                main_ingredients="seafood, vegetables, special sauce"
            )
        
        # Generate recipe with potential security input
        generator = RecipeGenerator()
        recipe = generator.generate_recipe(
            "Chef's Special Dish",
            "seafood, special ingredients",
            "Japanese"
        )
        
        # Save recipe to database
        with IronChefDatabaseSecure(db_path) as db:
            recipe_id = db.add_recipe(
                dish_id=dish_id,
                recipe_title=recipe['title'],
                ingredients=json.dumps(recipe['ingredients']),
                instructions=json.dumps(recipe['instructions']),
                prep_time=recipe['prep_time'],
                cook_time=recipe['cook_time'],
                servings=recipe['servings']
            )
        
        # Export data securely
        exporter = SecureRecipeExporter(output_dir=temp_dir)
        
        # Export episodes
        episodes_file = exporter.export_episode_summary('json', 'secure_episodes')
        assert os.path.exists(episodes_file)
        
        # Export recipe
        recipe_file = exporter.export_recipe(dish_id, 'txt', 'secure_recipe')
        assert os.path.exists(recipe_file)
        
        # Verify exported files are safe and readable
        with open(episodes_file, 'r') as f:
            episodes_data = json.load(f)
        assert len(episodes_data) == 1
        
        with open(recipe_file, 'r') as f:
            recipe_content = f.read()
        assert "Chef's Special Dish" in recipe_content
        
        # Verify all operations completed without security issues
        assert os.path.exists(db_path)
        assert os.path.exists(episodes_file)
        assert os.path.exists(recipe_file)