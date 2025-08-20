# Iron Chef Recipe Database API

A comprehensive RESTful API for accessing Iron Chef episodes, dishes, and recipes with AI-powered recipe generation capabilities.

## Features

### 🚀 **Core API Endpoints**
- **Episodes**: Browse and filter episodes with pagination
- **Dishes**: Access detailed dish information from episodes  
- **Recipes**: Generate AI-powered recipes and retrieve existing ones
- **Search**: Global search across episodes, dishes, and recipes
- **Reference Data**: Access themes and chef information

### 🔒 **Security & Performance**
- Optional API key authentication
- Rate limiting protection (configurable by endpoint)
- CORS support for web applications
- Input validation and SQL injection protection
- Comprehensive error handling with consistent responses
- Security headers and HTTPS support

### 📚 **Documentation**
- Interactive Swagger UI documentation
- ReDoc alternative documentation
- OpenAPI 3.0 specification
- Comprehensive examples and schemas

### 🛠 **Developer Experience**
- Consistent JSON responses
- Proper HTTP status codes
- Request/response validation
- Comprehensive test suite
- Easy deployment scripts

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd IronChefRecipes

# Install dependencies
pip install -r requirements.txt

# Initialize database
python -c "from iron_chef_database_secure import IronChefDatabaseSecure; 
with IronChefDatabaseSecure() as db: db.initialize_database()"
```

### 2. Development Server

```bash
# Start development server
python api_app.py

# Or using make
make api-dev
```

### 3. Access Documentation

- **API Root**: http://localhost:5000/api
- **Swagger UI**: http://localhost:5000/api/docs  
- **ReDoc**: http://localhost:5000/api/redoc
- **OpenAPI Spec**: http://localhost:5000/api/spec

## API Endpoints

### Core Endpoints

| Endpoint | Method | Description | Rate Limit |
|----------|--------|-------------|------------|
| `/api/v1/status` | GET | API health check | 60/min |
| `/api/v1/episodes` | GET | List episodes with filtering | 30/min |
| `/api/v1/episodes/{id}` | GET | Get episode details | 60/min |
| `/api/v1/episodes/{id}/dishes` | GET | Get episode dishes | 60/min |
| `/api/v1/recipes/generate` | POST | Generate new recipe | 10/min |
| `/api/v1/recipes/{id}` | GET | Get recipe details | 60/min |
| `/api/v1/search` | GET | Global search | 20/min |
| `/api/v1/themes` | GET | Get all themes | 100/min |
| `/api/v1/chefs` | GET | Get chefs data | 100/min |

### Authentication

API key authentication is optional by default but can be enabled for production:

```bash
# Include API key in requests
curl -H "X-API-Key: your-api-key" http://localhost:5000/api/v1/episodes
```

## Usage Examples

### Get Episodes with Filtering

```bash
# Get all episodes
curl "http://localhost:5000/api/v1/episodes"

# Filter by theme
curl "http://localhost:5000/api/v1/episodes?theme=Lobster"

# Filter by chef and paginate
curl "http://localhost:5000/api/v1/episodes?chef=Chen&page=2&per_page=5"

# Filter by date range
curl "http://localhost:5000/api/v1/episodes?air_date_from=1993-01-01&air_date_to=1995-12-31"
```

### Generate Recipe

```bash
# Generate recipe for a dish
curl -X POST "http://localhost:5000/api/v1/recipes/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "dish_id": 1,
    "chef_style": "traditional",
    "difficulty": "medium",
    "dietary_restrictions": ["vegetarian"]
  }'
```

### Search Content

```bash
# Search across all content
curl "http://localhost:5000/api/v1/search?q=lobster&page=1&per_page=10"
```

### Response Format

All API responses follow a consistent format:

```json
{
  "success": true,
  "data": { /* response data */ },
  "message": "Optional message",
  "pagination": { /* pagination info for list endpoints */ },
  "errors": [] /* error messages if any */
}
```

## Configuration

### Environment Variables

Create a `.env` file for configuration:

```bash
# Environment
FLASK_ENV=development
DEBUG=True
SECRET_KEY=your-secret-key

# Database
DATABASE_PATH=iron_chef_recipes.db

# API Configuration
API_KEY_REQUIRED=False
CORS_ORIGINS=*

# Rate Limiting
RATELIMIT_STORAGE_URL=memory://

# Logging
LOG_LEVEL=INFO
```

### Production Configuration

For production deployment:

```bash
# Set environment
export FLASK_ENV=production

# Configure security
export API_KEY_REQUIRED=True
export SECRET_KEY=your-production-secret-key

# Configure database
export DATABASE_PATH=/var/lib/ironchef/iron_chef_recipes.db

# Configure rate limiting (use Redis)
export REDIS_URL=redis://localhost:6379/1
export RATELIMIT_STORAGE_URL=redis://localhost:6379/1
```

## Deployment

### Development Deployment

```bash
# Quick setup
make dev-setup

# Start development server  
make api-dev
```

### Production Deployment

```bash
# Deploy for production
python deploy.py production

# Or using make
make deploy-prod
```

This creates:
- Virtual environment with dependencies
- Production configuration files
- Systemd service file
- Nginx configuration template
- Database initialization

### Using Docker (Future)

```bash
# Build image
make docker-build

# Run container
make docker-run
```

## Testing

### Run API Tests

```bash
# Run all API tests
make api-test

# Run specific test file
pytest tests/test_api.py -v

# Run with coverage
pytest tests/test_api.py --cov=api --cov-report=html
```

### Test API Endpoints

```bash
# Test endpoints with curl
make test-api-endpoints

# Load testing
make load-test
```

## Security Features

### Input Validation
- All inputs are validated using Marshmallow schemas
- SQL injection protection with parameterized queries
- XSS protection in responses
- Request size limits

### Rate Limiting
- Configurable rate limits per endpoint
- Memory or Redis storage backends
- Graceful handling of rate limit exceeded

### Security Headers
- Strict Transport Security
- Content Security Policy
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- X-XSS-Protection

### API Keys (Optional)
- Simple API key authentication
- File-based key storage
- Rate limit exemptions for authenticated requests

## Error Handling

### HTTP Status Codes

- `200 OK`: Successful request
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource already exists
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

### Error Response Format

```json
{
  "success": false,
  "message": "Error description",
  "errors": ["Detailed error messages"],
  "validation_errors": { /* field-specific errors */ }
}
```

## Performance

### Optimization Features
- Database indexes for common queries
- Efficient pagination
- JSON response compression
- Query result caching (future)
- Connection pooling (future)

### Monitoring
- Health check endpoint (`/health`)
- Structured logging
- Request tracking
- Performance metrics (future)

## Contributing

### Development Setup

```bash
# Install development dependencies
make install-dev

# Set up development environment
make dev-setup

# Run tests
make test

# Check code quality
make lint
make format
make security
```

### Adding New Endpoints

1. Add endpoint to `api.py`
2. Add validation schemas
3. Add tests to `tests/test_api.py`
4. Update OpenAPI documentation
5. Update this README

## API Versioning

- Current version: `v1`
- All endpoints prefixed with `/api/v1/`
- Future versions will maintain backward compatibility
- Deprecation notices provided for breaking changes

## License

MIT License - see LICENSE file for details.

## Support

- **Documentation**: http://localhost:5000/api/docs
- **Issues**: Create GitHub issues for bugs and feature requests
- **API Status**: http://localhost:5000/api/v1/status

---

**Built with Flask-RESTful, OpenAPI 3.0, and comprehensive security practices.**