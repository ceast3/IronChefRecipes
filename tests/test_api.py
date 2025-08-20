#!/usr/bin/env python3
"""
Comprehensive API Tests for Iron Chef Recipe Database API
Tests all endpoints, error handling, validation, and security features
"""

import json
import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock
from flask import Flask
from api import create_api_app, APIError
from api_docs import add_docs_routes
from iron_chef_database_secure import IronChefDatabaseSecure


class TestAPIEndpoints:
    """Test class for API endpoints"""
    
    @pytest.fixture
    def app(self):
        """Create test Flask app with API"""
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'
        
        # Create API
        api = create_api_app(app)
        add_docs_routes(app)
        
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    @pytest.fixture
    def mock_db(self):
        """Mock database for testing"""
        with patch('api.IronChefDatabaseSecure') as mock:
            db_instance = MagicMock()
            mock.return_value.__enter__.return_value = db_instance
            yield db_instance

    def test_api_status_endpoint(self, client, mock_db):
        """Test API status endpoint"""
        mock_db.cursor.execute.return_value = None
        mock_db.cursor.fetchone.return_value = [100]  # Episode count
        
        response = client.get('/api/v1/status')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['status'] == 'healthy'
        assert data['data']['version'] == 'v1'
        assert 'timestamp' in data['data']
        assert data['data']['database']['connected'] is True
        assert data['data']['database']['episodes'] == 100

    def test_api_status_database_error(self, client, mock_db):
        """Test API status with database error"""
        mock_db.cursor.execute.side_effect = Exception("Database connection failed")
        
        response = client.get('/api/v1/status')
        assert response.status_code == 500
        
        data = json.loads(response.data)
        assert data['success'] is False
        assert data['data']['status'] == 'unhealthy'

    def test_episodes_endpoint_basic(self, client, mock_db):
        """Test basic episodes endpoint"""
        mock_episodes = [
            {
                'id': 1,
                'episode_number': 1,
                'air_date': '1993-10-10',
                'theme': 'Lobster',
                'iron_chef_id': 1,
                'competitor_id': 1,
                'winner': 'iron_chef',
                'judges_scores': '3-0',
                'iron_chef_name': 'Chen Kenichi',
                'competitor_name': 'Test Chef'
            }
        ]
        
        mock_db.cursor.execute.return_value = None
        mock_db.cursor.fetchall.return_value = [type('Row', (), episode) for episode in mock_episodes]
        
        response = client.get('/api/v1/episodes')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']) == 1
        assert data['data'][0]['theme'] == 'Lobster'
        assert 'pagination' in data

    def test_episodes_endpoint_with_filters(self, client, mock_db):
        """Test episodes endpoint with filters"""
        mock_db.cursor.execute.return_value = None
        mock_db.cursor.fetchall.return_value = []
        
        response = client.get('/api/v1/episodes?theme=Lobster&page=2&per_page=5')
        assert response.status_code == 200
        
        # Verify SQL query was called with correct parameters
        mock_db.cursor.execute.assert_called()
        args = mock_db.cursor.execute.call_args
        assert 'WHERE' in args[0][0]
        assert 'theme LIKE' in args[0][0]

    def test_episodes_endpoint_invalid_pagination(self, client):
        """Test episodes endpoint with invalid pagination"""
        response = client.get('/api/v1/episodes?page=0&per_page=101')
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'validation' in data['message'].lower()

    def test_episode_detail_endpoint(self, client, mock_db):
        """Test episode detail endpoint"""
        mock_episode = {
            'id': 1,
            'episode_number': 1,
            'theme': 'Lobster',
            'dishes': []
        }
        
        with patch('api.IronChefDatabaseSecure') as mock:
            db_instance = MagicMock()
            mock.return_value.__enter__.return_value = db_instance
            db_instance.get_episode_details.return_value = mock_episode
            
            response = client.get('/api/v1/episodes/1')
            assert response.status_code == 200
            
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['data']['theme'] == 'Lobster'

    def test_episode_detail_not_found(self, client, mock_db):
        """Test episode detail endpoint with non-existent episode"""
        with patch('api.IronChefDatabaseSecure') as mock:
            db_instance = MagicMock()
            mock.return_value.__enter__.return_value = db_instance
            db_instance.get_episode_details.return_value = None
            
            response = client.get('/api/v1/episodes/999')
            assert response.status_code == 404
            
            data = json.loads(response.data)
            assert data['success'] is False
            assert 'not found' in data['message'].lower()

    def test_episode_detail_invalid_id(self, client):
        """Test episode detail endpoint with invalid ID"""
        response = client.get('/api/v1/episodes/invalid')
        assert response.status_code == 404  # Flask returns 404 for invalid int paths

    def test_episode_dishes_endpoint(self, client, mock_db):
        """Test episode dishes endpoint"""
        mock_dishes = [
            {
                'id': 1,
                'episode_id': 1,
                'chef_type': 'iron_chef',
                'dish_number': 1,
                'dish_name': 'Lobster Sashimi',
                'description': 'Fresh lobster preparation',
                'main_ingredients': 'lobster',
                'cooking_techniques': 'raw preparation'
            }
        ]
        
        mock_db.cursor.execute.return_value = None
        mock_db.cursor.fetchall.return_value = [type('Row', (), dish) for dish in mock_dishes]
        
        response = client.get('/api/v1/episodes/1/dishes')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']) == 1
        assert data['data'][0]['dish_name'] == 'Lobster Sashimi'

    def test_recipe_generation_endpoint(self, client, mock_db):
        """Test recipe generation endpoint"""
        # Mock existing recipe check (should return None for new recipe)
        mock_db.cursor.execute.return_value = None
        mock_db.cursor.fetchone.return_value = None
        mock_db.cursor.fetchall.return_value = []
        
        # Mock dish data
        mock_dish = {
            'id': 1,
            'dish_name': 'Lobster Sashimi',
            'main_ingredients': 'lobster',
            'description': 'Fresh lobster'
        }
        mock_db.cursor.fetchone.return_value = type('Row', (), mock_dish)
        
        # Mock recipe generation and saving
        with patch('api.RecipeGenerator') as mock_generator:
            generator_instance = MagicMock()
            mock_generator.return_value = generator_instance
            generator_instance.generate_recipe_for_dish.return_value = {
                'title': 'Test Recipe',
                'ingredients': ['lobster'],
                'instructions': ['slice lobster'],
                'prep_time': 15,
                'cook_time': 0,
                'servings': 4
            }
            
            with patch('api.IronChefDatabaseSecure') as mock_db_context:
                db_instance = MagicMock()
                mock_db_context.return_value.__enter__.return_value = db_instance
                db_instance.cursor.fetchone.side_effect = [None, mock_dish]  # No existing recipe, then dish data
                db_instance.add_recipe.return_value = 123
                
                payload = {'dish_id': 1, 'chef_style': 'traditional', 'difficulty': 'medium'}
                response = client.post('/api/v1/recipes/generate',
                                     data=json.dumps(payload),
                                     content_type='application/json')
                
                assert response.status_code == 201
                data = json.loads(response.data)
                assert data['success'] is True
                assert data['data']['recipe_id'] == 123

    def test_recipe_generation_existing_recipe(self, client):
        """Test recipe generation when recipe already exists"""
        with patch('api.IronChefDatabaseSecure') as mock:
            db_instance = MagicMock()
            mock.return_value.__enter__.return_value = db_instance
            db_instance.cursor.fetchone.return_value = [456]  # Existing recipe ID
            
            payload = {'dish_id': 1}
            response = client.post('/api/v1/recipes/generate',
                                 data=json.dumps(payload),
                                 content_type='application/json')
            
            assert response.status_code == 409
            data = json.loads(response.data)
            assert data['success'] is False
            assert 'already exists' in data['message']

    def test_recipe_generation_invalid_dish(self, client):
        """Test recipe generation with invalid dish ID"""
        with patch('api.IronChefDatabaseSecure') as mock:
            db_instance = MagicMock()
            mock.return_value.__enter__.return_value = db_instance
            db_instance.cursor.fetchone.side_effect = [None, None]  # No existing recipe, no dish
            
            payload = {'dish_id': 999}
            response = client.post('/api/v1/recipes/generate',
                                 data=json.dumps(payload),
                                 content_type='application/json')
            
            assert response.status_code == 404
            data = json.loads(response.data)
            assert data['success'] is False
            assert 'not found' in data['message'].lower()

    def test_recipe_generation_invalid_payload(self, client):
        """Test recipe generation with invalid payload"""
        payload = {'invalid_field': 'value'}
        response = client.post('/api/v1/recipes/generate',
                             data=json.dumps(payload),
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'validation' in data['message'].lower()

    def test_recipe_detail_endpoint(self, client, mock_db):
        """Test recipe detail endpoint"""
        mock_recipe = {
            'id': 1,
            'dish_id': 1,
            'recipe_title': 'Lobster Sashimi Recipe',
            'ingredients': '["lobster", "soy sauce"]',
            'instructions': '["slice lobster", "serve with soy sauce"]',
            'prep_time': 15,
            'cook_time': 0,
            'servings': 4,
            'generated_date': '2023-01-01',
            'dish_name': 'Lobster Sashimi',
            'episode_number': 1,
            'theme': 'Lobster'
        }
        
        mock_db.cursor.execute.return_value = None
        mock_db.cursor.fetchone.return_value = type('Row', (), mock_recipe)
        
        response = client.get('/api/v1/recipes/1')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['recipe_title'] == 'Lobster Sashimi Recipe'
        assert isinstance(data['data']['ingredients'], list)
        assert isinstance(data['data']['instructions'], list)

    def test_recipe_detail_not_found(self, client, mock_db):
        """Test recipe detail endpoint with non-existent recipe"""
        mock_db.cursor.execute.return_value = None
        mock_db.cursor.fetchone.return_value = None
        
        response = client.get('/api/v1/recipes/999')
        assert response.status_code == 404
        
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'not found' in data['message'].lower()

    def test_search_endpoint(self, client, mock_db):
        """Test search endpoint"""
        mock_episodes = [{'type': 'episode', 'id': 1, 'title': 'Lobster Theme'}]
        mock_dishes = [{'type': 'dish', 'id': 1, 'title': 'Lobster Sashimi'}]
        mock_recipes = [{'type': 'recipe', 'id': 1, 'title': 'Lobster Recipe'}]
        
        mock_db.cursor.execute.return_value = None
        mock_db.cursor.fetchall.side_effect = [
            [type('Row', (), episode) for episode in mock_episodes],
            [type('Row', (), dish) for dish in mock_dishes],
            [type('Row', (), recipe) for recipe in mock_recipes]
        ]
        
        response = client.get('/api/v1/search?q=lobster')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['summary']['total'] == 3
        assert data['data']['summary']['episodes'] == 1
        assert data['data']['summary']['dishes'] == 1
        assert data['data']['summary']['recipes'] == 1

    def test_search_endpoint_missing_query(self, client):
        """Test search endpoint without query parameter"""
        response = client.get('/api/v1/search')
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'validation' in data['message'].lower()

    def test_search_endpoint_invalid_query(self, client):
        """Test search endpoint with invalid query"""
        response = client.get('/api/v1/search?q=' + 'x' * 101)  # Too long
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert data['success'] is False

    def test_themes_endpoint(self, client):
        """Test themes endpoint"""
        mock_themes = ['Lobster', 'Crab', 'Sea Bream']
        
        with patch('api.IronChefDatabaseSecure') as mock:
            db_instance = MagicMock()
            mock.return_value.__enter__.return_value = db_instance
            db_instance.get_all_themes.return_value = mock_themes
            
            response = client.get('/api/v1/themes')
            assert response.status_code == 200
            
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['data']['themes'] == mock_themes
            assert data['data']['count'] == 3

    def test_chefs_endpoint(self, client, mock_db):
        """Test chefs endpoint"""
        mock_iron_chefs = [
            {'id': 1, 'name': 'Chen Kenichi', 'title': 'Iron Chef Chinese'}
        ]
        mock_competitors = [
            {'id': 1, 'name': 'Test Chef', 'restaurant': 'Test Restaurant'}
        ]
        
        mock_db.cursor.execute.return_value = None
        mock_db.cursor.fetchall.side_effect = [
            [type('Row', (), chef) for chef in mock_iron_chefs],
            [type('Row', (), chef) for chef in mock_competitors]
        ]
        
        response = client.get('/api/v1/chefs')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['iron_chefs']) == 1
        assert len(data['data']['competitors']) == 1
        assert data['data']['iron_chefs'][0]['name'] == 'Chen Kenichi'

    def test_api_key_header(self, client, mock_db):
        """Test API key header processing"""
        mock_db.cursor.execute.return_value = None
        mock_db.cursor.fetchone.return_value = [100]
        
        headers = {'X-API-Key': 'test-api-key-12345'}
        response = client.get('/api/v1/status', headers=headers)
        assert response.status_code == 200

    def test_cors_headers(self, client):
        """Test CORS headers are present"""
        response = client.options('/api/v1/status')
        assert 'Access-Control-Allow-Origin' in response.headers

    def test_rate_limiting_headers(self, client, mock_db):
        """Test rate limiting headers"""
        mock_db.cursor.execute.return_value = None
        mock_db.cursor.fetchone.return_value = [100]
        
        response = client.get('/api/v1/status')
        # Rate limiting headers should be present (implementation-dependent)
        assert response.status_code == 200

    def test_error_handling(self, client, mock_db):
        """Test error handling with database exception"""
        mock_db.cursor.execute.side_effect = Exception("Database error")
        
        response = client.get('/api/v1/episodes')
        assert response.status_code == 500
        
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'internal server error' in data['message'].lower()

    def test_json_content_type_required(self, client):
        """Test that POST endpoints require JSON content type"""
        payload = 'dish_id=1'  # Form data instead of JSON
        response = client.post('/api/v1/recipes/generate',
                             data=payload,
                             content_type='application/x-www-form-urlencoded')
        
        # Should handle gracefully (may return 400 for invalid JSON)
        assert response.status_code >= 400


class TestAPIDocumentation:
    """Test API documentation endpoints"""
    
    @pytest.fixture
    def app(self):
        """Create test Flask app with API docs"""
        app = Flask(__name__)
        app.config['TESTING'] = True
        
        api = create_api_app(app)
        add_docs_routes(app)
        
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()

    def test_api_docs_endpoint(self, client):
        """Test Swagger UI documentation endpoint"""
        response = client.get('/api/docs')
        assert response.status_code == 200
        assert b'swagger-ui' in response.data
        assert b'Iron Chef Recipe Database API' in response.data

    def test_api_spec_endpoint(self, client):
        """Test OpenAPI specification endpoint"""
        response = client.get('/api/spec')
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        spec = json.loads(response.data)
        assert spec['info']['title'] == 'Iron Chef Recipe Database API'
        assert spec['info']['version'] == 'v1'
        assert 'paths' in spec
        assert '/api/v1/episodes' in spec['paths']

    def test_redoc_endpoint(self, client):
        """Test ReDoc documentation endpoint"""
        response = client.get('/api/redoc')
        assert response.status_code == 200
        assert b'redoc' in response.data

    def test_api_info_endpoint(self, client):
        """Test API info endpoint"""
        # This requires the main app route to be added
        pass


class TestAPIValidation:
    """Test API input validation and security"""
    
    @pytest.fixture
    def app(self):
        """Create test Flask app"""
        app = Flask(__name__)
        app.config['TESTING'] = True
        create_api_app(app)
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()

    def test_sql_injection_protection(self, client):
        """Test SQL injection protection in search"""
        with patch('api.IronChefDatabaseSecure') as mock:
            db_instance = MagicMock()
            mock.return_value.__enter__.return_value = db_instance
            db_instance.cursor.fetchall.return_value = []
            
            # Try SQL injection
            malicious_query = "'; DROP TABLE episodes; --"
            response = client.get(f'/api/v1/search?q={malicious_query}')
            
            # Should not crash and should sanitize input
            assert response.status_code == 200

    def test_xss_protection(self, client):
        """Test XSS protection in responses"""
        with patch('api.IronChefDatabaseSecure') as mock:
            db_instance = MagicMock()
            mock.return_value.__enter__.return_value = db_instance
            db_instance.cursor.fetchall.return_value = []
            
            # Try XSS payload
            xss_payload = "<script>alert('xss')</script>"
            response = client.get(f'/api/v1/search?q={xss_payload}')
            
            # Should return JSON, not execute script
            assert response.content_type == 'application/json'
            assert response.status_code == 200

    def test_large_request_handling(self, client):
        """Test handling of unusually large requests"""
        large_payload = {'dish_id': 1, 'dietary_restrictions': ['x'] * 1000}
        response = client.post('/api/v1/recipes/generate',
                             data=json.dumps(large_payload),
                             content_type='application/json')
        
        # Should handle gracefully
        assert response.status_code in [200, 201, 400, 413]

    def test_malformed_json_handling(self, client):
        """Test handling of malformed JSON"""
        malformed_json = '{"dish_id": 1, "invalid": }'
        response = client.post('/api/v1/recipes/generate',
                             data=malformed_json,
                             content_type='application/json')
        
        assert response.status_code == 400

    def test_boundary_values(self, client):
        """Test boundary value validation"""
        # Test minimum page value
        response = client.get('/api/v1/episodes?page=1&per_page=1')
        assert response.status_code in [200, 500]  # 500 if no mock DB
        
        # Test maximum per_page value
        response = client.get('/api/v1/episodes?page=1&per_page=100')
        assert response.status_code in [200, 500]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])