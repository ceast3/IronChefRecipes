"""
Unit tests for SecureRecipeExporter class
Tests export functionality, file security, and format handling
"""

import pytest
import json
import csv
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, mock_open

# Import modules under test
from recipe_exporter_secure import SecureRecipeExporter
from iron_chef_database_secure import IronChefDatabaseSecure


@pytest.mark.unit
@pytest.mark.filesystem
class TestSecureRecipeExporter:
    """Test the SecureRecipeExporter class"""
    
    def test_initialization_default(self):
        """Test SecureRecipeExporter initialization with default directory"""
        exporter = SecureRecipeExporter()
        
        assert exporter.output_dir == os.path.abspath('.')
        assert exporter.timestamp is not None
        assert exporter.validator is not None
        assert os.path.exists(exporter.export_path)
        assert exporter.export_path.endswith('exports')
    
    def test_initialization_custom_dir(self, temp_dir):
        """Test SecureRecipeExporter initialization with custom directory"""
        exporter = SecureRecipeExporter(output_dir=temp_dir)
        
        assert exporter.output_dir == temp_dir
        assert os.path.exists(exporter.export_path)
        assert exporter.export_path == os.path.join(temp_dir, 'exports')
    
    def test_initialization_invalid_dir(self):
        """Test SecureRecipeExporter initialization with invalid directory"""
        # Non-existent directory
        with pytest.raises(ValueError, match="Output directory does not exist"):
            SecureRecipeExporter(output_dir="/nonexistent/path")
        
        # File instead of directory
        with tempfile.NamedTemporaryFile() as tmp:
            with pytest.raises(ValueError, match="Path is not a directory"):
                SecureRecipeExporter(output_dir=tmp.name)
    
    def test_validate_output_dir(self, temp_dir):
        """Test output directory validation"""
        exporter = SecureRecipeExporter()
        
        # Valid directory
        validated_dir = exporter._validate_output_dir(temp_dir)
        assert validated_dir == temp_dir
        
        # Non-existent directory
        with pytest.raises(ValueError, match="does not exist"):
            exporter._validate_output_dir("/nonexistent")
    
    def test_sanitize_filename_basic(self, secure_exporter):
        """Test basic filename sanitization"""
        # Normal filename
        result = secure_exporter._sanitize_filename("test_file", ".txt")
        assert result == "test_file.txt"
        
        # Filename with spaces
        result = secure_exporter._sanitize_filename("test file", ".txt")
        assert result == "test_file.txt"
        
        # Empty filename
        result = secure_exporter._sanitize_filename("", ".txt")
        assert result.endswith(".txt")
        assert "export_" in result
    
    def test_sanitize_filename_security(self, secure_exporter, malicious_inputs):
        """Test filename sanitization against malicious inputs"""
        # Path traversal attempts
        for malicious in malicious_inputs['path_traversal']:
            result = secure_exporter._sanitize_filename(malicious, ".txt")
            assert ".." not in result
            assert "/" not in result
            assert "\\" not in result
            assert result.endswith(".txt")
        
        # Special characters
        result = secure_exporter._sanitize_filename("test@#$%^&*()file", ".txt")
        assert "@" not in result
        assert "#" not in result
        assert "$" not in result
        assert result.endswith(".txt")
    
    def test_sanitize_filename_extensions(self, secure_exporter):
        """Test filename extension handling"""
        # Valid extensions
        valid_extensions = ['.json', '.csv', '.txt', '.md']
        for ext in valid_extensions:
            result = secure_exporter._sanitize_filename("test", ext)
            assert result.endswith(ext)
        
        # Invalid extension should default to .txt
        result = secure_exporter._sanitize_filename("test", ".exe")
        assert result.endswith(".txt")
        
        # Existing extension should be replaced
        result = secure_exporter._sanitize_filename("test.json", ".csv")
        assert result.endswith(".csv")
        assert result.count(".") == 1
    
    def test_sanitize_filename_length_limit(self, secure_exporter):
        """Test filename length limitation"""
        # Very long filename
        long_name = "x" * 300
        result = secure_exporter._sanitize_filename(long_name, ".txt")
        
        # Should be truncated but still have extension
        assert len(result) <= 204  # 200 + ".txt"
        assert result.endswith(".txt")
    
    def test_sanitize_filename_hidden_files(self, secure_exporter):
        """Test prevention of hidden file creation"""
        # Leading dots should be removed
        result = secure_exporter._sanitize_filename(".hidden_file", ".txt")
        assert not result.startswith(".")
        assert result.endswith(".txt")
        
        # Multiple leading dots
        result = secure_exporter._sanitize_filename("...file", ".txt")
        assert not result.startswith(".")
    
    def test_get_safe_filepath(self, secure_exporter):
        """Test safe filepath generation"""
        filepath = secure_exporter._get_safe_filepath("test_file", ".txt")
        
        # Should be within export directory
        abs_filepath = os.path.abspath(filepath)
        abs_export = os.path.abspath(secure_exporter.export_path)
        assert abs_filepath.startswith(abs_export)
        
        # Should have correct filename
        assert os.path.basename(filepath) == "test_file.txt"
    
    def test_get_safe_filepath_traversal_protection(self, secure_exporter):
        """Test filepath protection against traversal attacks"""
        # Attempt to escape export directory
        with pytest.raises(ValueError, match="Invalid file path detected"):
            # This should be caught by the double-check in _get_safe_filepath
            # We'll patch _sanitize_filename to return a dangerous path for testing
            with patch.object(secure_exporter, '_sanitize_filename', return_value="../dangerous.txt"):
                secure_exporter._get_safe_filepath("../dangerous.txt")


@pytest.mark.integration
@pytest.mark.filesystem
@pytest.mark.database
class TestSecureRecipeExporterExports:
    """Test actual export functionality"""
    
    def test_export_episode_summary_json(self, secure_exporter, populated_db):
        """Test exporting episode summary as JSON"""
        # Mock the database path for the exporter's internal database usage
        with patch('recipe_exporter_secure.IronChefDatabaseSecure') as mock_db_class:
            mock_db = mock_db_class.return_value.__enter__.return_value
            mock_db.search_episodes_by_theme.return_value = [
                {
                    'id': 1,
                    'episode_number': 1,
                    'theme': 'Lobster',
                    'iron_chef_name': 'Chen Kenichi',
                    'competitor_name': 'Test Challenger',
                    'winner': 'Iron Chef',
                    'air_date': '1993-10-10'
                }
            ]
            
            filepath = secure_exporter.export_episode_summary('json', 'test_episodes')
            
            # Verify file was created
            assert os.path.exists(filepath)
            assert filepath.endswith('.json')
            
            # Verify content
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]['theme'] == 'Lobster'
    
    def test_export_episode_summary_csv(self, secure_exporter):
        """Test exporting episode summary as CSV"""
        with patch('recipe_exporter_secure.IronChefDatabaseSecure') as mock_db_class:
            mock_db = mock_db_class.return_value.__enter__.return_value
            mock_db.search_episodes_by_theme.return_value = [
                {
                    'episode_number': 1,
                    'theme': 'Lobster',
                    'iron_chef_name': 'Chen Kenichi',
                    'competitor_name': 'Test Challenger',
                    'winner': 'Iron Chef',
                    'air_date': '1993-10-10'
                }
            ]
            
            filepath = secure_exporter.export_episode_summary('csv', 'test_episodes')
            
            # Verify file was created
            assert os.path.exists(filepath)
            assert filepath.endswith('.csv')
            
            # Verify content
            with open(filepath, 'r', newline='') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            assert len(rows) == 1
            assert rows[0]['theme'] == 'Lobster'
    
    def test_export_episode_summary_empty_data(self, secure_exporter):
        """Test exporting empty episode data"""
        with patch('recipe_exporter_secure.IronChefDatabaseSecure') as mock_db_class:
            mock_db = mock_db_class.return_value.__enter__.return_value
            mock_db.search_episodes_by_theme.return_value = []
            
            # JSON export
            filepath = secure_exporter.export_episode_summary('json', 'empty_episodes')
            assert os.path.exists(filepath)
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            assert data == []
            
            # CSV export
            filepath = secure_exporter.export_episode_summary('csv', 'empty_episodes')
            assert os.path.exists(filepath)
            
            with open(filepath, 'r') as f:
                content = f.read()
            # Should have headers even with no data
            assert 'episode_number,theme' in content
    
    def test_export_episode_summary_invalid_format(self, secure_exporter):
        """Test exporting with invalid format"""
        with pytest.raises(ValueError, match="Supported formats"):
            secure_exporter.export_episode_summary('xml')
    
    def test_export_recipe_json(self, secure_exporter):
        """Test exporting single recipe as JSON"""
        mock_recipe_data = {
            'id': 1,
            'dish_id': 1,
            'recipe_title': 'Test Recipe',
            'ingredients': json.dumps([{'item': 'Test Ingredient', 'amount': '1 cup'}]),
            'instructions': json.dumps(['Step 1', 'Step 2']),
            'prep_time': 20,
            'cook_time': 30,
            'servings': 4
        }
        
        mock_dish_data = {
            'id': 1,
            'dish_name': 'Test Dish',
            'chef_type': 'iron_chef',
            'theme': 'Test Theme',
            'episode_number': 1,
            'iron_chef': 'Test Chef',
            'competitor': 'Test Competitor'
        }
        
        with patch('recipe_exporter_secure.IronChefDatabaseSecure') as mock_db_class:
            mock_db = mock_db_class.return_value.__enter__.return_value
            mock_db.cursor.execute.side_effect = [
                None,  # First query
                None   # Second query
            ]
            mock_db.cursor.fetchone.side_effect = [
                mock_recipe_data,  # Recipe query result
                mock_dish_data     # Dish query result
            ]
            
            filepath = secure_exporter.export_recipe(1, 'json', 'test_recipe')
            
            # Verify file was created
            assert os.path.exists(filepath)
            assert filepath.endswith('.json')
            
            # Verify content
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            assert data['recipe_title'] == 'Test Recipe'
            assert isinstance(data['ingredients'], list)
            assert isinstance(data['instructions'], list)
            assert 'dish_info' in data
    
    def test_export_recipe_txt(self, secure_exporter):
        """Test exporting single recipe as text"""
        mock_recipe_data = {
            'recipe_title': 'Test Recipe',
            'ingredients': json.dumps([
                {'item': 'Test Ingredient', 'amount': '1 cup', 'prep': 'chopped'}
            ]),
            'instructions': json.dumps(['Step 1: Prepare', 'Step 2: Cook']),
            'prep_time': 20,
            'cook_time': 30,
            'servings': 4
        }
        
        mock_dish_data = {
            'dish_name': 'Test Dish',
            'chef_type': 'iron_chef',
            'theme': 'Test Theme',
            'episode_number': 1
        }
        
        with patch('recipe_exporter_secure.IronChefDatabaseSecure') as mock_db_class:
            mock_db = mock_db_class.return_value.__enter__.return_value
            mock_db.cursor.fetchone.side_effect = [mock_recipe_data, mock_dish_data]
            
            filepath = secure_exporter.export_recipe(1, 'txt', 'test_recipe')
            
            # Verify file was created
            assert os.path.exists(filepath)
            assert filepath.endswith('.txt')
            
            # Verify content
            with open(filepath, 'r') as f:
                content = f.read()
            
            assert 'Test Recipe' in content
            assert 'INGREDIENTS:' in content
            assert 'INSTRUCTIONS:' in content
            assert 'Test Ingredient' in content
            assert '1 cup' in content
    
    def test_export_recipe_nonexistent(self, secure_exporter):
        """Test exporting non-existent recipe"""
        with patch('recipe_exporter_secure.IronChefDatabaseSecure') as mock_db_class:
            mock_db = mock_db_class.return_value.__enter__.return_value
            mock_db.cursor.fetchone.return_value = None
            
            with pytest.raises(ValueError, match="No recipe found"):
                secure_exporter.export_recipe(99999, 'json')
    
    def test_export_recipe_invalid_dish_id(self, secure_exporter):
        """Test exporting recipe with invalid dish ID"""
        with pytest.raises(ValueError, match="dish ID"):
            secure_exporter.export_recipe(0, 'json')
        
        with pytest.raises(ValueError, match="dish ID"):
            secure_exporter.export_recipe(-1, 'json')
    
    def test_export_recipe_invalid_format(self, secure_exporter):
        """Test exporting recipe with invalid format"""
        with pytest.raises(ValueError, match="Supported formats"):
            secure_exporter.export_recipe(1, 'xml')
    
    def test_export_all_recipes(self, secure_exporter):
        """Test exporting all recipes"""
        mock_recipes = [
            {
                'id': 1,
                'dish_id': 1,
                'recipe_title': 'Recipe 1',
                'ingredients': json.dumps([]),
                'instructions': json.dumps([]),
                'dish_name': 'Dish 1',
                'chef_type': 'iron_chef',
                'theme': 'Theme 1',
                'episode_number': 1
            },
            {
                'id': 2,
                'dish_id': 2,
                'recipe_title': 'Recipe 2',
                'ingredients': json.dumps([]),
                'instructions': json.dumps([]),
                'dish_name': 'Dish 2',
                'chef_type': 'competitor',
                'theme': 'Theme 2',
                'episode_number': 2
            }
        ]
        
        with patch('recipe_exporter_secure.IronChefDatabaseSecure') as mock_db_class:
            mock_db = mock_db_class.return_value.__enter__.return_value
            mock_db.cursor.fetchall.return_value = mock_recipes
            
            filepath = secure_exporter.export_all_recipes('json', 'all_recipes')
            
            # Verify file was created
            assert os.path.exists(filepath)
            assert filepath.endswith('.json')
            
            # Verify content
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            assert len(data) == 2
            assert data[0]['recipe_title'] == 'Recipe 1'
            assert data[1]['recipe_title'] == 'Recipe 2'
    
    def test_export_all_recipes_corrupted_data(self, secure_exporter):
        """Test exporting all recipes with corrupted JSON data"""
        mock_recipes = [
            {
                'recipe_title': 'Recipe 1',
                'ingredients': 'invalid json',  # Corrupted
                'instructions': 'also invalid',  # Corrupted
                'dish_name': 'Dish 1'
            }
        ]
        
        with patch('recipe_exporter_secure.IronChefDatabaseSecure') as mock_db_class:
            mock_db = mock_db_class.return_value.__enter__.return_value
            mock_db.cursor.fetchall.return_value = mock_recipes
            
            filepath = secure_exporter.export_all_recipes('json')
            
            # Should handle corrupted data gracefully
            assert os.path.exists(filepath)
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            assert len(data) == 1
            assert data[0]['ingredients'] == []  # Should be empty list
            assert data[0]['instructions'] == []  # Should be empty list
    
    def test_export_dishes_by_theme(self, secure_exporter):
        """Test exporting dishes filtered by theme"""
        mock_episodes = [
            {'id': 1, 'theme': 'Lobster', 'episode_number': 1}
        ]
        
        mock_episode_details = {
            'id': 1,
            'theme': 'Lobster',
            'episode_number': 1,
            'dishes': {
                'iron_chef': [{'dish_name': 'Lobster Dish 1'}],
                'competitor': [{'dish_name': 'Lobster Dish 2'}]
            }
        }
        
        with patch('recipe_exporter_secure.IronChefDatabaseSecure') as mock_db_class:
            mock_db = mock_db_class.return_value.__enter__.return_value
            mock_db.search_episodes_by_theme.return_value = mock_episodes
            mock_db.get_episode_details.return_value = mock_episode_details
            
            filepath = secure_exporter.export_dishes_by_theme('Lobster', 'json', 'lobster_dishes')
            
            # Verify file was created
            assert os.path.exists(filepath)
            assert filepath.endswith('.json')
            
            # Verify content
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            assert data['theme'] == 'Lobster'
            assert len(data['episodes']) == 1
            assert data['episodes'][0]['id'] == 1
    
    def test_export_dishes_by_theme_not_found(self, secure_exporter):
        """Test exporting dishes for non-existent theme"""
        with patch('recipe_exporter_secure.IronChefDatabaseSecure') as mock_db_class:
            mock_db = mock_db_class.return_value.__enter__.return_value
            mock_db.search_episodes_by_theme.return_value = []
            
            with pytest.raises(ValueError, match="No episodes found"):
                secure_exporter.export_dishes_by_theme('NonExistentTheme', 'json')
    
    def test_export_dishes_by_theme_invalid_theme(self, secure_exporter):
        """Test exporting dishes with invalid theme"""
        with pytest.raises(ValueError, match="Theme is required"):
            secure_exporter.export_dishes_by_theme('', 'json')
        
        with pytest.raises(ValueError, match="Theme is required"):
            secure_exporter.export_dishes_by_theme(None, 'json')


@pytest.mark.unit
@pytest.mark.filesystem
class TestSecureRecipeExporterFileOperations:
    """Test file operation helpers"""
    
    def test_export_episodes_json_error_handling(self, secure_exporter):
        """Test JSON export error handling"""
        # Test with read-only directory to trigger write error
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            with pytest.raises(IOError, match="Failed to write JSON file"):
                secure_exporter._export_episodes_json([], "/fake/path/file.json")
    
    def test_export_episodes_csv_error_handling(self, secure_exporter):
        """Test CSV export error handling"""
        # Test with read-only directory to trigger write error
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            with pytest.raises(IOError, match="Failed to write CSV file"):
                secure_exporter._export_episodes_csv([], "/fake/path/file.csv")
    
    def test_export_recipe_json_error_handling(self, secure_exporter):
        """Test recipe JSON export error handling"""
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            with pytest.raises(IOError, match="Failed to write JSON file"):
                secure_exporter._export_recipe_json({}, "/fake/path/file.json")
    
    def test_export_recipe_text_error_handling(self, secure_exporter):
        """Test recipe text export error handling"""
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            with pytest.raises(IOError, match="Failed to write text file"):
                secure_exporter._export_recipe_text({}, "/fake/path/file.txt")
    
    def test_export_recipe_text_content_formatting(self, secure_exporter):
        """Test recipe text export formatting"""
        mock_recipe = {
            'recipe_title': 'Test Recipe Title',
            'dish_info': {
                'episode_number': 5,
                'theme': 'Test Theme',
                'dish_name': 'Test Dish Name',
                'chef_type': 'iron_chef'
            },
            'servings': 4,
            'prep_time': 20,
            'cook_time': 30,
            'ingredients': [
                {'item': 'Ingredient 1', 'amount': '1 cup', 'prep': 'chopped'},
                {'item': 'Ingredient 2', 'amount': '2 tbsp', 'prep': ''}
            ],
            'instructions': [
                'First instruction step',
                'Second instruction step'
            ],
            'generated_date': '2024-01-01'
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp:
            try:
                secure_exporter._export_recipe_text(mock_recipe, tmp.name)
                
                # Read back and verify formatting
                with open(tmp.name, 'r') as f:
                    content = f.read()
                
                # Check structure
                assert 'Test Recipe Title' in content
                assert 'Episode #5' in content
                assert 'Test Theme' in content
                assert 'Iron Chef' in content  # chef_type formatted
                assert 'Servings: 4' in content
                assert 'Prep Time: 20 minutes' in content
                assert 'Cook Time: 30 minutes' in content
                assert 'INGREDIENTS:' in content
                assert 'INSTRUCTIONS:' in content
                assert '• 1 cup Ingredient 1 (chopped)' in content
                assert '• 2 tbsp Ingredient 2' in content
                assert '1. First instruction step' in content
                assert '2. Second instruction step' in content
                assert 'Generated: 2024-01-01' in content
                
            finally:
                os.unlink(tmp.name)


@pytest.mark.integration
@pytest.mark.slow
class TestSecureRecipeExporterPerformance:
    """Test export performance with larger datasets"""
    
    def test_large_episode_export_performance(self, secure_exporter, benchmark_timer):
        """Test performance with large episode dataset"""
        # Create mock large dataset
        large_dataset = []
        for i in range(1000):
            large_dataset.append({
                'episode_number': i + 1,
                'theme': f'Theme {i}',
                'iron_chef_name': f'Chef {i % 10}',
                'competitor_name': f'Competitor {i}',
                'winner': 'Iron Chef' if i % 2 else 'Competitor',
                'air_date': '2024-01-01'
            })
        
        with patch('recipe_exporter_secure.IronChefDatabaseSecure') as mock_db_class:
            mock_db = mock_db_class.return_value.__enter__.return_value
            mock_db.search_episodes_by_theme.return_value = large_dataset
            
            benchmark_timer.start()
            filepath = secure_exporter.export_episode_summary('json', 'large_episodes')
            elapsed_time = benchmark_timer.stop()
            
            # Should complete in reasonable time (less than 5 seconds)
            assert elapsed_time < 5.0
            assert os.path.exists(filepath)
            
            # Verify data integrity
            with open(filepath, 'r') as f:
                data = json.load(f)
            assert len(data) == 1000
    
    def test_concurrent_export_safety(self, temp_dir):
        """Test that concurrent exports don't interfere with each other"""
        import threading
        import time
        
        results = []
        errors = []
        
        def export_worker(worker_id):
            try:
                exporter = SecureRecipeExporter(output_dir=temp_dir)
                
                # Mock database
                with patch('recipe_exporter_secure.IronChefDatabaseSecure') as mock_db_class:
                    mock_db = mock_db_class.return_value.__enter__.return_value
                    mock_db.search_episodes_by_theme.return_value = [
                        {'episode_number': worker_id, 'theme': f'Theme {worker_id}'}
                    ]
                    
                    filepath = exporter.export_episode_summary('json', f'worker_{worker_id}')
                    results.append((worker_id, filepath))
                    
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # Start multiple worker threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=export_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify no errors and all files created
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 5
        
        # Verify all files exist and have correct content
        for worker_id, filepath in results:
            assert os.path.exists(filepath)
            with open(filepath, 'r') as f:
                data = json.load(f)
            assert data[0]['episode_number'] == worker_id


@pytest.mark.unit
class TestSecureRecipeExporterSecurity:
    """Test security aspects of the exporter"""
    
    def test_filename_security_comprehensive(self, secure_exporter, malicious_inputs):
        """Comprehensive test of filename security"""
        # Test all categories of malicious inputs
        for category, inputs in malicious_inputs.items():
            for malicious_input in inputs[:3]:  # Test first 3 of each category
                try:
                    result = secure_exporter._sanitize_filename(malicious_input, ".txt")
                    
                    # Verify result is safe
                    assert isinstance(result, str)
                    assert result.endswith(".txt")
                    assert ".." not in result
                    assert "/" not in result
                    assert "\\" not in result
                    assert not result.startswith(".")
                    assert len(result) <= 204  # Max length including extension
                    
                except Exception as e:
                    # Any exception during sanitization is a test failure
                    pytest.fail(f"Sanitization failed for input '{malicious_input}': {e}")
    
    def test_export_path_containment(self, secure_exporter):
        """Test that all export paths stay within the export directory"""
        test_filenames = [
            "normal_file",
            "../parent_dir",
            "../../grandparent",
            "/absolute/path",
            "C:\\Windows\\System32\\file",
            "sub/dir/file",
            "file with spaces",
            "file@#$%^&*()",
            ".hidden_file",
            "very_long_filename_" + "x" * 200
        ]
        
        for filename in test_filenames:
            try:
                filepath = secure_exporter._get_safe_filepath(filename, ".txt")
                
                # Verify path is contained within export directory
                abs_filepath = os.path.abspath(filepath)
                abs_export = os.path.abspath(secure_exporter.export_path)
                
                assert abs_filepath.startswith(abs_export), \
                    f"Path {abs_filepath} escapes export directory {abs_export}"
                
            except ValueError:
                # Rejection is acceptable for some inputs
                pass
    
    def test_file_write_permissions(self, temp_dir):
        """Test handling of file write permission issues"""
        # Create exporter with temp directory
        exporter = SecureRecipeExporter(output_dir=temp_dir)
        
        # Create a directory where we can't write
        restricted_dir = os.path.join(temp_dir, 'restricted')
        os.makedirs(restricted_dir, mode=0o444)  # Read-only
        
        try:
            # Patch export_path to point to restricted directory
            exporter.export_path = restricted_dir
            
            with patch('recipe_exporter_secure.IronChefDatabaseSecure') as mock_db_class:
                mock_db = mock_db_class.return_value.__enter__.return_value
                mock_db.search_episodes_by_theme.return_value = []
                
                # Should handle permission error gracefully
                with pytest.raises(IOError):
                    exporter.export_episode_summary('json', 'test')
                    
        finally:
            # Cleanup: restore permissions and remove directory
            os.chmod(restricted_dir, 0o755)
            os.rmdir(restricted_dir)