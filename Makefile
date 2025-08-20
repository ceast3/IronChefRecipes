# Iron Chef Recipe Database - Development Makefile

.PHONY: help install test test-unit test-integration test-security test-all test-fast clean lint format coverage docs api-test api-start api-dev api-prod deploy-dev deploy-prod

# Default target
help:
	@echo "Iron Chef Recipe Database - Available commands:"
	@echo ""
	@echo "Setup:"
	@echo "  install     Install dependencies"
	@echo "  install-dev Install development dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  test        Run all tests"
	@echo "  test-unit   Run unit tests only"
	@echo "  test-integration Run integration tests only"
	@echo "  test-security Run security tests only"
	@echo "  test-fast   Run fast tests only (no slow tests)"
	@echo "  test-all    Run all tests including slow ones"
	@echo "  coverage    Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint        Run code linting"
	@echo "  format      Format code with black"
	@echo "  security    Run security scans"
	@echo ""
	@echo "API Development:"
	@echo "  api-test    Run API-specific tests"
	@echo "  api-start   Start the API server"
	@echo "  api-dev     Start API in development mode"
	@echo "  api-prod    Start API in production mode"
	@echo ""
	@echo "Deployment:"
	@echo "  deploy-dev  Deploy for development"
	@echo "  deploy-prod Deploy for production"
	@echo "  deploy-test Deploy for testing"
	@echo ""
	@echo "Utilities:"
	@echo "  clean       Clean up temporary files"
	@echo "  docs        Generate documentation"

# Installation
install:
	pip install -r requirements.txt

install-dev: install
	pip install black flake8 mypy bandit safety pytest-benchmark

# Testing
test:
	pytest tests/ -v --tb=short

test-unit:
	pytest tests/ -v --tb=short -m "unit"

test-integration:
	pytest tests/ -v --tb=short -m "integration"

test-security:
	pytest tests/ -v --tb=short -m "security"

test-fast:
	pytest tests/ -v --tb=short -m "not slow"

test-all:
	pytest tests/ -v --tb=short

coverage:
	pytest tests/ --cov --cov-report=html --cov-report=term-missing --cov-report=xml
	@echo "Coverage report generated in htmlcov/index.html"

# Code Quality
lint:
	@echo "Running flake8..."
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
	@echo "Running mypy..."
	mypy iron_chef_database_secure.py recipe_generator.py recipe_exporter_secure.py --ignore-missing-imports || true

format:
	black --line-length 120 --target-version py38 *.py tests/*.py

security:
	@echo "Running Bandit security scan..."
	bandit -r . -f txt || true
	@echo "Checking for known vulnerabilities..."
	safety check || true

# Utilities
clean:
	rm -rf __pycache__/
	rm -rf tests/__pycache__/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -f coverage.xml
	rm -f *.db
	rm -f test_*.db
	rm -f *.pyc
	rm -rf exports/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

docs:
	@echo "Generating documentation..."
	@echo "API Documentation:" > API.md
	@echo "==================" >> API.md
	@echo "" >> API.md
	python -c "
import iron_chef_database_secure
import recipe_generator
import recipe_exporter_secure
import inspect

modules = [
    ('IronChefDatabaseSecure', iron_chef_database_secure.IronChefDatabaseSecure),
    ('SecurityValidator', iron_chef_database_secure.SecurityValidator),
    ('RecipeGenerator', recipe_generator.RecipeGenerator),
    ('SecureRecipeExporter', recipe_exporter_secure.SecureRecipeExporter),
]

with open('API.md', 'a') as f:
    for name, cls in modules:
        f.write(f'## {name}\n\n')
        if cls.__doc__:
            f.write(f'{cls.__doc__}\n\n')
        
        f.write('### Methods:\n\n')
        for method_name, method in inspect.getmembers(cls, inspect.isfunction):
            if not method_name.startswith('_'):
                sig = inspect.signature(method)
                f.write(f'- **{method_name}{sig}**\n')
                if method.__doc__:
                    doc_lines = method.__doc__.strip().split('\n')
                    f.write(f'  {doc_lines[0]}\n')
                f.write('\n')
        f.write('\n')
"
	@echo "Documentation generated in API.md"

# Database operations
init-db:
	python -c "
from iron_chef_database_secure import IronChefDatabaseSecure
with IronChefDatabaseSecure() as db:
    db.initialize_database()
    print('Database initialized successfully')
"

demo-data:
	python sample_data_loader.py

# Testing with specific markers
test-database:
	pytest tests/ -v -m "database"

test-filesystem:
	pytest tests/ -v -m "filesystem"

test-slow:
	pytest tests/ -v -m "slow"

# Performance testing
benchmark:
	pytest tests/ --benchmark-only --benchmark-json=benchmark.json

# Test specific files
test-db:
	pytest tests/test_database.py -v

test-gen:
	pytest tests/test_recipe_generator.py -v

test-exp:
	pytest tests/test_export.py -v

test-sec:
	pytest tests/test_security.py -v

# Development helpers
run-security-tests:
	python tests/test_security.py

export-sample:
	python recipe_exporter_secure.py episodes --format json --output sample_episodes

# CI/CD simulation
ci-test:
	@echo "Simulating CI/CD pipeline..."
	make lint
	make test-fast
	make security
	@echo "CI/CD simulation complete"

# API Development Commands
api-test:
	pytest tests/test_api.py -v --tb=short

api-start:
	python api_app.py

api-dev:
	FLASK_ENV=development python api_app.py

api-prod:
	FLASK_ENV=production python api_app.py

# Deployment Commands
deploy-dev:
	python deploy.py development

deploy-prod:
	python deploy.py production

deploy-test:
	python deploy.py testing

# API Documentation
api-docs:
	@echo "Generating API documentation..."
	python api_docs.py > openapi.json
	@echo "OpenAPI specification saved to openapi.json"

# API Testing with curl
test-api-endpoints:
	@echo "Testing API endpoints..."
	@echo "Health check:"
	curl -s http://localhost:5000/health | python -m json.tool || echo "Server not running"
	@echo ""
	@echo "API status:"
	curl -s http://localhost:5000/api/v1/status | python -m json.tool || echo "Server not running"
	@echo ""
	@echo "API info:"
	curl -s http://localhost:5000/api | python -m json.tool || echo "Server not running"

# Load testing
load-test:
	@echo "Running basic load test..."
	@echo "Install 'ab' (Apache Bench) for load testing"
	ab -n 100 -c 10 http://localhost:5000/api/v1/status || echo "Apache Bench not installed"

# Docker commands (for future use)
docker-build:
	docker build -t ironchef-api .

docker-run:
	docker run -p 5000:5000 ironchef-api

# Environment setup
setup-env:
	@echo "Setting up environment variables..."
	@echo "Creating .env file for development..."
	@echo "FLASK_ENV=development" > .env
	@echo "DEBUG=True" >> .env
	@echo "SECRET_KEY=iron-chef-dev-secret" >> .env
	@echo "API_KEY_REQUIRED=False" >> .env
	@echo "Environment file created: .env"

# Database migrations (for future use)
migrate-db:
	@echo "Running database migrations..."
	python database_migration_add_indices.py

# Performance testing
perf-test:
	python query_performance_benchmark.py

# Full development setup
dev-setup: install-dev init-db setup-env
	@echo "Development environment ready!"
	@echo "Run 'make api-dev' to start the development server"