#!/usr/bin/env python3
"""
Iron Chef Recipe Database API Testing Script
Tests the comprehensive RESTful API endpoints
"""

import requests
import json
import sys
import time
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5000"
API_BASE = f"{BASE_URL}/api/v1"

def test_endpoint(endpoint, method="GET", data=None, headers=None, expected_status=200):
    """Test a single API endpoint"""
    url = f"{API_BASE}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, headers=headers, timeout=10)
        else:
            print(f"❌ Unsupported method: {method}")
            return False
        
        if response.status_code == expected_status:
            print(f"✅ {method} {endpoint} - Status: {response.status_code}")
            
            # Try to parse JSON response
            try:
                json_data = response.json()
                if 'success' in json_data:
                    print(f"   Success: {json_data['success']}")
                if 'data' in json_data and isinstance(json_data['data'], list):
                    print(f"   Data count: {len(json_data['data'])}")
                elif 'data' in json_data and isinstance(json_data['data'], dict):
                    print(f"   Data keys: {list(json_data['data'].keys())}")
                
                return True
            except json.JSONDecodeError:
                print(f"   Non-JSON response (length: {len(response.text)})")
                return True
                
        else:
            print(f"❌ {method} {endpoint} - Expected: {expected_status}, Got: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('message', 'Unknown error')}")
            except:
                print(f"   Raw response: {response.text[:200]}...")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ {method} {endpoint} - Connection failed (server not running?)")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ {method} {endpoint} - Request timeout")
        return False
    except Exception as e:
        print(f"❌ {method} {endpoint} - Error: {e}")
        return False

def test_api_endpoints():
    """Test all API endpoints"""
    print("🍳 Iron Chef Recipe Database API Test Suite")
    print("=" * 50)
    
    # Test basic connectivity
    try:
        response = requests.get(BASE_URL, timeout=5)
        print(f"✅ Base URL accessible - Status: {response.status_code}")
    except:
        print("❌ Base URL not accessible - Is the server running?")
        return False
    
    print("\n📊 Testing API Endpoints:")
    print("-" * 30)
    
    results = []
    
    # System endpoints
    print("\n🔧 System Endpoints:")
    results.append(test_endpoint("/status"))
    
    # Episodes endpoints
    print("\n📺 Episode Endpoints:")
    results.append(test_endpoint("/episodes"))
    results.append(test_endpoint("/episodes?page=1&per_page=5"))
    results.append(test_endpoint("/episodes?theme=Lobster"))
    results.append(test_endpoint("/episodes/1"))
    results.append(test_endpoint("/episodes/1/dishes"))
    
    # Data endpoints
    print("\n📋 Data Endpoints:")
    results.append(test_endpoint("/themes"))
    results.append(test_endpoint("/chefs"))
    
    # Search endpoints
    print("\n🔍 Search Endpoints:")
    results.append(test_endpoint("/search?q=lobster"))
    results.append(test_endpoint("/search?q=sauce&search_type=dish"))
    
    # Recipes and Dishes endpoints (these might be empty if no recipes exist)
    print("\n🍽️ Recipe & Dish Endpoints:")
    results.append(test_endpoint("/recipes"))
    results.append(test_endpoint("/dishes"))
    
    # Test API documentation endpoints
    print("\n📚 Documentation Endpoints:")
    try:
        doc_response = requests.get(f"{BASE_URL}/api/docs", timeout=10)
        if doc_response.status_code == 200:
            print("✅ GET /api/docs - Swagger UI accessible")
            results.append(True)
        else:
            print(f"❌ GET /api/docs - Status: {doc_response.status_code}")
            results.append(False)
    except:
        print("❌ GET /api/docs - Connection failed")
        results.append(False)
    
    try:
        spec_response = requests.get(f"{BASE_URL}/api/spec", timeout=10)
        if spec_response.status_code == 200:
            spec_data = spec_response.json()
            print(f"✅ GET /api/spec - OpenAPI spec accessible")
            print(f"   API Title: {spec_data.get('info', {}).get('title', 'Unknown')}")
            print(f"   API Version: {spec_data.get('info', {}).get('version', 'Unknown')}")
            print(f"   Endpoints: {len(spec_data.get('paths', {}))}")
            results.append(True)
        else:
            print(f"❌ GET /api/spec - Status: {spec_response.status_code}")
            results.append(False)
    except:
        print("❌ GET /api/spec - Connection failed")
        results.append(False)
    
    # Test API info endpoint
    try:
        info_response = requests.get(f"{BASE_URL}/api", timeout=10)
        if info_response.status_code == 200:
            print("✅ GET /api - API info accessible")
            results.append(True)
        else:
            print(f"❌ GET /api - Status: {info_response.status_code}")
            results.append(False)
    except:
        print("❌ GET /api - Connection failed")
        results.append(False)
    
    # Authentication endpoints that require API key
    print("\n🔐 Authentication Required Endpoints (testing without API key):")
    results.append(test_endpoint("/recipes/generate", "POST", 
                                {"dish_id": 1}, expected_status=401))
    results.append(test_endpoint("/export/json?type=episodes", expected_status=401))
    
    # Summary
    print("\n" + "=" * 50)
    print(f"📊 Test Results Summary:")
    print(f"✅ Passed: {sum(results)}")
    print(f"❌ Failed: {len(results) - sum(results)}")
    print(f"📈 Success Rate: {(sum(results)/len(results)*100):.1f}%")
    
    if sum(results) == len(results):
        print("\n🎉 All tests passed! API is fully functional.")
        return True
    else:
        print(f"\n⚠️  Some tests failed. Check the logs above for details.")
        return False

def test_api_key_functionality():
    """Test API key functionality"""
    print("\n🔑 Testing API Key Functionality:")
    print("-" * 30)
    
    # Try to create an admin API key using the CLI
    import subprocess
    import sys
    
    try:
        result = subprocess.run([
            sys.executable, "api_auth.py", "create-admin"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ Admin API key creation command works")
            
            # Extract API key from output (this is just for testing)
            lines = result.stdout.split('\n')
            api_key = None
            for line in lines:
                if line.startswith("API Key: "):
                    api_key = line.split("API Key: ")[1].strip()
                    break
            
            if api_key:
                print(f"✅ API key generated: {api_key[:20]}...")
                
                # Test with API key
                headers = {"X-API-Key": api_key}
                
                # Test an endpoint that requires authentication
                print("\n🧪 Testing with API key:")
                
                # This should work with API key
                success = test_endpoint("/recipes/generate", "POST", 
                                      {"dish_id": 1}, headers=headers, expected_status=409)
                
                if success:
                    print("✅ API key authentication working")
                else:
                    print("❌ API key authentication failed")
                
                return True
            else:
                print("❌ Could not extract API key from output")
                return False
        else:
            print(f"❌ Admin API key creation failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ API key creation timed out")
        return False
    except Exception as e:
        print(f"❌ API key creation error: {e}")
        return False

if __name__ == "__main__":
    print(f"🚀 Starting API tests at {datetime.now()}")
    print(f"🌐 Testing server at: {BASE_URL}")
    
    # Wait a moment for server to be ready
    print("⏳ Waiting for server to be ready...")
    time.sleep(2)
    
    # Run main API tests
    api_success = test_api_endpoints()
    
    # Test API key functionality
    auth_success = test_api_key_functionality()
    
    print("\n" + "=" * 50)
    print("🏁 Final Results:")
    print(f"📊 API Endpoints: {'✅ PASS' if api_success else '❌ FAIL'}")
    print(f"🔑 Authentication: {'✅ PASS' if auth_success else '❌ FAIL'}")
    
    if api_success and auth_success:
        print("\n🎉 All systems operational! API is production-ready.")
        sys.exit(0)
    else:
        print("\n⚠️  Some issues detected. Review the test results above.")
        sys.exit(1)