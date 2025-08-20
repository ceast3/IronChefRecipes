#!/usr/bin/env python3
"""
Iron Chef Recipe Database API Demo
Demonstrates the API capabilities with sample requests
"""

import json
import time
from flask import Flask
from api import create_api_app
from api_docs import add_docs_routes


def create_demo_app():
    """Create a demo application with sample data"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    
    # Initialize API
    api = create_api_app(app)
    add_docs_routes(app)
    
    return app


def demo_api_endpoints():
    """Demonstrate API endpoints with sample calls"""
    app = create_demo_app()
    
    print("=" * 60)
    print("Iron Chef Recipe Database API Demo")
    print("=" * 60)
    
    with app.test_client() as client:
        
        # Test API status
        print("\n1. Testing API Status Endpoint")
        print("-" * 30)
        response = client.get('/api/v1/status')
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = json.loads(response.data)
            print(f"API Status: {data['data']['status']}")
            print(f"Version: {data['data']['version']}")
        
        # Test episodes endpoint
        print("\n2. Testing Episodes Endpoint")
        print("-" * 30)
        response = client.get('/api/v1/episodes')
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = json.loads(response.data)
            print(f"Success: {data['success']}")
            print(f"Episodes returned: {len(data['data'])}")
            if 'pagination' in data:
                print(f"Pagination info: {data['pagination']}")
        
        # Test episodes with parameters
        print("\n3. Testing Episodes with Filters")
        print("-" * 30)
        response = client.get('/api/v1/episodes?page=1&per_page=5&theme=Lobster')
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = json.loads(response.data)
            print(f"Filtered episodes: {len(data['data'])}")
        
        # Test search endpoint
        print("\n4. Testing Search Endpoint")
        print("-" * 30)
        response = client.get('/api/v1/search?q=lobster')
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = json.loads(response.data)
            print(f"Search success: {data['success']}")
            if 'data' in data and 'summary' in data['data']:
                summary = data['data']['summary']
                print(f"Search results: {summary}")
        
        # Test themes endpoint
        print("\n5. Testing Themes Endpoint")
        print("-" * 30)
        response = client.get('/api/v1/themes')
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = json.loads(response.data)
            print(f"Success: {data['success']}")
            if 'data' in data:
                themes_data = data['data']
                if 'themes' in themes_data:
                    print(f"Available themes: {len(themes_data['themes'])}")
        
        # Test chefs endpoint
        print("\n6. Testing Chefs Endpoint")
        print("-" * 30)
        response = client.get('/api/v1/chefs')
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = json.loads(response.data)
            print(f"Success: {data['success']}")
            if 'data' in data:
                chefs_data = data['data']
                iron_chefs = chefs_data.get('iron_chefs', [])
                competitors = chefs_data.get('competitors', [])
                print(f"Iron Chefs: {len(iron_chefs)}")
                print(f"Competitors: {len(competitors)}")
        
        # Test recipe generation (will fail without database, but tests validation)
        print("\n7. Testing Recipe Generation Validation")
        print("-" * 30)
        payload = {
            'dish_id': 1,
            'chef_style': 'traditional',
            'difficulty': 'medium'
        }
        response = client.post('/api/v1/recipes/generate',
                             data=json.dumps(payload),
                             content_type='application/json')
        print(f"Status Code: {response.status_code}")
        # Expected to fail with 500 due to no database, but validates input
        if response.status_code != 200:
            print("Expected error due to no sample database data")
        
        # Test invalid requests
        print("\n8. Testing Input Validation")
        print("-" * 30)
        
        # Invalid pagination
        response = client.get('/api/v1/episodes?page=0')
        print(f"Invalid page parameter: {response.status_code}")
        
        # Missing required parameter
        response = client.get('/api/v1/search')
        print(f"Missing search query: {response.status_code}")
        
        # Invalid JSON
        response = client.post('/api/v1/recipes/generate',
                             data='invalid json',
                             content_type='application/json')
        print(f"Invalid JSON: {response.status_code}")
        
        # Test documentation endpoints
        print("\n9. Testing Documentation Endpoints")
        print("-" * 30)
        
        response = client.get('/api/spec')
        print(f"OpenAPI Spec: {response.status_code}")
        
        response = client.get('/api/docs')
        print(f"Swagger UI: {response.status_code}")
        
        response = client.get('/api/redoc')
        print(f"ReDoc: {response.status_code}")
    
    print("\n" + "=" * 60)
    print("✅ API Demo Complete!")
    print("=" * 60)
    print("\nTo start the full API server:")
    print("  python api_app.py")
    print("\nTo access documentation:")
    print("  http://localhost:5000/api/docs")
    print("  http://localhost:5000/api/redoc")
    print("\nTo get API information:")
    print("  curl http://localhost:5000/api")
    print("=" * 60)


def demo_api_features():
    """Demonstrate key API features"""
    print("\n🚀 Iron Chef Recipe Database API Features:")
    print("=" * 50)
    
    features = [
        "✓ RESTful API endpoints with proper HTTP methods",
        "✓ Comprehensive request/response validation",
        "✓ Rate limiting and CORS protection",
        "✓ OpenAPI/Swagger documentation",
        "✓ Consistent error handling",
        "✓ Pagination support for list endpoints",
        "✓ Advanced filtering and search capabilities",
        "✓ AI-powered recipe generation",
        "✓ Security headers and input sanitization",
        "✓ Production-ready configuration options",
        "✓ Comprehensive test suite",
        "✓ Easy deployment scripts"
    ]
    
    for feature in features:
        print(f"  {feature}")
    
    print("\n🔧 API Endpoints:")
    print("=" * 50)
    
    endpoints = [
        ("GET", "/api/v1/status", "API health check"),
        ("GET", "/api/v1/episodes", "List episodes with filtering"),
        ("GET", "/api/v1/episodes/{id}", "Get episode details"),
        ("GET", "/api/v1/episodes/{id}/dishes", "Get episode dishes"),
        ("POST", "/api/v1/recipes/generate", "Generate AI recipe"),
        ("GET", "/api/v1/recipes/{id}", "Get recipe details"),
        ("GET", "/api/v1/search", "Global search"),
        ("GET", "/api/v1/themes", "Get available themes"),
        ("GET", "/api/v1/chefs", "Get chefs data")
    ]
    
    for method, endpoint, description in endpoints:
        print(f"  {method:4} {endpoint:30} - {description}")
    
    print("\n📚 Documentation:")
    print("=" * 50)
    print("  • Interactive Swagger UI: /api/docs")
    print("  • ReDoc documentation: /api/redoc")
    print("  • OpenAPI specification: /api/spec")
    print("  • API information: /api")


if __name__ == '__main__':
    try:
        demo_api_features()
        demo_api_endpoints()
    except Exception as e:
        print(f"Demo failed: {e}")
        import traceback
        traceback.print_exc()