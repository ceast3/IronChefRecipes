#!/usr/bin/env python3
"""
OpenAPI Documentation Generator for Iron Chef API
Generates interactive Swagger UI documentation
"""

import json
from flask import Flask, render_template_string, jsonify
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec_webframeworks.flask import FlaskPlugin

def create_swagger_ui_html(spec_url: str) -> str:
    """Create Swagger UI HTML template"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Iron Chef Recipe Database API</title>
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@4.15.5/swagger-ui.css" />
    <style>
        html {
            box-sizing: border-box;
            overflow: -moz-scrollbars-vertical;
            overflow-y: scroll;
        }
        *, *:before, *:after {
            box-sizing: inherit;
        }
        body {
            margin:0;
            background: #fafafa;
        }
        .swagger-ui .topbar {
            background-color: #1f2937;
        }
        .swagger-ui .topbar .download-url-wrapper .select-label {
            color: #ffffff;
        }
        .swagger-ui .info .title {
            color: #1f2937;
        }
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@4.15.5/swagger-ui-bundle.js"></script>
    <script src="https://unpkg.com/swagger-ui-dist@4.15.5/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = function() {
            const ui = SwaggerUIBundle({
                url: '{{ spec_url }}',
                dom_id: '#swagger-ui',
                deepLinking: true,
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                plugins: [
                    SwaggerUIBundle.plugins.DownloadUrl
                ],
                layout: "StandaloneLayout",
                validatorUrl: null,
                tryItOutEnabled: true,
                defaultModelsExpandDepth: -1,
                defaultModelExpandDepth: 2,
                docExpansion: 'list',
                apisSorter: 'alpha',
                operationsSorter: 'alpha'
            });
        };
    </script>
</body>
</html>
"""

def generate_openapi_spec_complete() -> dict:
    """Generate a comprehensive OpenAPI specification for all endpoints"""
    return {
        "openapi": "3.0.2",
        "info": {
            "title": "Iron Chef Recipe Database API",
            "version": "v1",
            "description": """A comprehensive RESTful API for accessing Iron Chef episodes, dishes, and recipes.

## Features
- **Episodes**: Browse and search Iron Chef episodes with filtering
- **Dishes**: Access dish information from each episode
- **Recipes**: Generate and retrieve detailed recipes
- **Search**: Global search across all content
- **Export**: Data export in multiple formats
- **Authentication**: Optional API key for enhanced features

## Rate Limits
- **Guest users**: 50 requests/hour, 10/minute
- **API key users**: 200 requests/hour, 50/minute
- **Premium users**: 1000 requests/hour, 100/minute
- **Recipe generation**: 10 requests/minute (authenticated users only)

## Authentication
API key authentication is optional for most endpoints but required for:
- Recipe generation
- Data export
- Enhanced rate limits

Include your API key in the `X-API-Key` header.
            """,
            "contact": {
                "name": "Iron Chef API Team",
                "email": "api@ironchef.example.com",
                "url": "https://github.com/ironchef/api"
            },
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT"
            },
            "termsOfService": "https://ironchef.example.com/terms"
        },
        "servers": [
            {
                "url": "http://localhost:5000",
                "description": "Development server"
            },
            {
                "url": "https://api.ironchef.example.com",
                "description": "Production server"
            }
        ],
        "tags": [
            {
                "name": "System",
                "description": "System health and status endpoints"
            },
            {
                "name": "Episodes",
                "description": "Iron Chef episode information and management"
            },
            {
                "name": "Dishes",
                "description": "Dish information from episodes"
            },
            {
                "name": "Recipes",
                "description": "Recipe generation and management"
            },
            {
                "name": "Search",
                "description": "Global search functionality"
            },
            {
                "name": "Data",
                "description": "Data export and statistics"
            },
            {
                "name": "Admin",
                "description": "Administrative endpoints (admin access required)"
            }
        ],
        "components": {
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                    "description": "Optional API key for enhanced rate limits and premium features"
                }
            },
            "schemas": {
                "APIResponse": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "description": "Whether the request was successful"},
                        "data": {"type": "object", "description": "Response data"},
                        "message": {"type": "string", "description": "Response message"},
                        "errors": {"type": "array", "items": {"type": "string"}, "description": "Error messages"},
                        "pagination": {"$ref": "#/components/schemas/Pagination"},
                        "meta": {"type": "object", "description": "Additional metadata"}
                    },
                    "required": ["success"]
                },
                "Pagination": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer", "description": "Current page number"},
                        "per_page": {"type": "integer", "description": "Items per page"},
                        "total": {"type": "integer", "description": "Total number of items"},
                        "pages": {"type": "integer", "description": "Total number of pages"},
                        "has_next": {"type": "boolean", "description": "Whether there is a next page"},
                        "has_prev": {"type": "boolean", "description": "Whether there is a previous page"},
                        "next_page": {"type": "integer", "description": "Next page number"},
                        "prev_page": {"type": "integer", "description": "Previous page number"}
                    }
                },
                "Episode": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "description": "Episode ID", "example": 1},
                        "episode_number": {"type": "integer", "description": "Episode number", "example": 1},
                        "air_date": {"type": "string", "format": "date", "description": "Air date", "example": "1993-10-10"},
                        "theme": {"type": "string", "description": "Episode theme/secret ingredient", "example": "Lobster"},
                        "iron_chef_id": {"type": "integer", "description": "Iron Chef ID", "example": 1},
                        "competitor_id": {"type": "integer", "description": "Competitor ID", "example": 1},
                        "winner": {"type": "string", "description": "Episode winner", "example": "Iron Chef"},
                        "judges_scores": {"type": "string", "description": "Judges scores", "example": "19-18"},
                        "iron_chef_name": {"type": "string", "description": "Iron Chef name", "example": "Chen Kenichi"},
                        "competitor_name": {"type": "string", "description": "Competitor name", "example": "Toshiro Kandagawa"}
                    }
                },
                "IronChef": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "description": "Iron Chef ID", "example": 1},
                        "name": {"type": "string", "description": "Iron Chef name", "example": "Chen Kenichi"},
                        "title": {"type": "string", "description": "Iron Chef title", "example": "The Szechuan Sage"},
                        "specialty": {"type": "string", "description": "Culinary specialty", "example": "Szechuan Cuisine"},
                        "active_years": {"type": "string", "description": "Years active", "example": "1993-2012"}
                    }
                },
                "Competitor": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "description": "Competitor ID", "example": 1},
                        "name": {"type": "string", "description": "Competitor name", "example": "Toshiro Kandagawa"},
                        "restaurant": {"type": "string", "description": "Restaurant", "example": "Nadaman"},
                        "specialty": {"type": "string", "description": "Specialty", "example": "Japanese Cuisine"},
                        "location": {"type": "string", "description": "Location", "example": "Tokyo, Japan"}
                    }
                },
                "Dish": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "description": "Dish ID", "example": 1},
                        "episode_id": {"type": "integer", "description": "Episode ID", "example": 1},
                        "chef_type": {"type": "string", "enum": ["iron_chef", "competitor"], "description": "Chef type"},
                        "dish_number": {"type": "integer", "description": "Dish number", "example": 1},
                        "dish_name": {"type": "string", "description": "Dish name", "example": "Lobster with Black Bean Sauce"},
                        "description": {"type": "string", "description": "Dish description"},
                        "main_ingredients": {"type": "string", "description": "Main ingredients"},
                        "cooking_techniques": {"type": "string", "description": "Cooking techniques"}
                    }
                },
                "Recipe": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "description": "Recipe ID", "example": 1},
                        "dish_id": {"type": "integer", "description": "Dish ID", "example": 1},
                        "recipe_title": {"type": "string", "description": "Recipe title", "example": "Traditional Lobster with Black Bean Sauce"},
                        "ingredients": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "example": "Lobster"},
                                    "amount": {"type": "string", "example": "2 lbs"},
                                    "preparation": {"type": "string", "example": "cleaned and chopped"}
                                }
                            },
                            "description": "Recipe ingredients"
                        },
                        "instructions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Cooking instructions",
                            "example": ["Heat oil in wok", "Add lobster and stir-fry", "Add black bean sauce"]
                        },
                        "prep_time": {"type": "integer", "description": "Prep time in minutes", "example": 30},
                        "cook_time": {"type": "integer", "description": "Cook time in minutes", "example": 15},
                        "servings": {"type": "integer", "description": "Number of servings", "example": 4},
                        "generated_date": {"type": "string", "format": "date-time", "description": "Generation timestamp"}
                    }
                },
                "SearchResult": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["episode", "dish", "recipe"], "description": "Result type"},
                        "id": {"type": "integer", "description": "Item ID"},
                        "title": {"type": "string", "description": "Item title"},
                        "description": {"type": "string", "description": "Item description"},
                        "episode_number": {"type": "integer", "description": "Related episode number"},
                        "theme": {"type": "string", "description": "Related episode theme"},
                        "relevance_score": {"type": "number", "description": "Search relevance score"}
                    }
                },
                "RecipeGenerationRequest": {
                    "type": "object",
                    "properties": {
                        "dish_id": {"type": "integer", "minimum": 1, "description": "Dish ID", "example": 1},
                        "chef_style": {
                            "type": "string", 
                            "enum": ["traditional", "modern", "fusion", "molecular"],
                            "default": "traditional",
                            "description": "Cooking style"
                        },
                        "difficulty": {
                            "type": "string",
                            "enum": ["easy", "medium", "hard", "expert"],
                            "default": "medium",
                            "description": "Recipe difficulty"
                        },
                        "dietary_restrictions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Dietary restrictions",
                            "example": ["vegetarian", "gluten-free"]
                        },
                        "servings": {"type": "integer", "minimum": 1, "maximum": 20, "default": 4},
                        "prep_time_target": {"type": "integer", "minimum": 5, "maximum": 300, "description": "Target prep time in minutes"},
                        "cook_time_target": {"type": "integer", "minimum": 5, "maximum": 480, "description": "Target cook time in minutes"}
                    },
                    "required": ["dish_id"]
                },
                "HealthCheck": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "example": "healthy"},
                        "version": {"type": "string", "example": "v1"},
                        "timestamp": {"type": "string", "format": "date-time"},
                        "database": {
                            "type": "object",
                            "properties": {
                                "connected": {"type": "boolean"},
                                "episodes": {"type": "integer"}
                            }
                        },
                        "uptime": {"type": "string", "example": "2 days, 3 hours"}
                    }
                },
                "Error": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean", "example": false},
                        "message": {"type": "string", "description": "Error message"},
                        "errors": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Detailed error messages"
                        },
                        "error_code": {"type": "string", "description": "Error code"},
                        "timestamp": {"type": "string", "format": "date-time"}
                    }
                }
            },
            "responses": {
                "BadRequest": {
                    "description": "Bad Request",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Error"}
                        }
                    }
                },
                "Unauthorized": {
                    "description": "Unauthorized",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Error"}
                        }
                    }
                },
                "Forbidden": {
                    "description": "Forbidden",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Error"}
                        }
                    }
                },
                "NotFound": {
                    "description": "Not Found",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Error"}
                        }
                    }
                },
                "RateLimitExceeded": {
                    "description": "Rate Limit Exceeded",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Error"}
                        }
                    }
                },
                "InternalServerError": {
                    "description": "Internal Server Error",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Error"}
                        }
                    }
                }
            }
        },
        "paths": {
            "/api/v1/status": {
                "get": {
                    "tags": ["System"],
                    "summary": "API health check",
                    "description": "Check API status and health",
                    "operationId": "getStatus",
                    "responses": {
                        "200": {
                            "description": "API is healthy",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "allOf": [
                                            {"$ref": "#/components/schemas/APIResponse"},
                                            {
                                                "properties": {
                                                    "data": {"$ref": "#/components/schemas/HealthCheck"}
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        },
                        "500": {"$ref": "#/components/responses/InternalServerError"}
                    }
                }
            },
            "/api/v1/episodes": {
                "get": {
                    "tags": ["Episodes"],
                    "summary": "List episodes",
                    "description": "Get episodes with optional filtering and pagination",
                    "operationId": "getEpisodes",
                    "parameters": [
                        {
                            "name": "page",
                            "in": "query",
                            "description": "Page number",
                            "schema": {"type": "integer", "minimum": 1, "default": 1}
                        },
                        {
                            "name": "per_page",
                            "in": "query",
                            "description": "Items per page",
                            "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 12}
                        },
                        {
                            "name": "theme",
                            "in": "query",
                            "description": "Filter by theme",
                            "schema": {"type": "string", "maxLength": 100}
                        },
                        {
                            "name": "chef",
                            "in": "query",
                            "description": "Filter by chef name",
                            "schema": {"type": "string", "maxLength": 100}
                        },
                        {
                            "name": "iron_chef_id",
                            "in": "query",
                            "description": "Filter by Iron Chef ID",
                            "schema": {"type": "integer", "minimum": 1}
                        },
                        {
                            "name": "competitor_id",
                            "in": "query",
                            "description": "Filter by competitor ID",
                            "schema": {"type": "integer", "minimum": 1}
                        },
                        {
                            "name": "air_date_from",
                            "in": "query",
                            "description": "Filter episodes from this date",
                            "schema": {"type": "string", "format": "date"}
                        },
                        {
                            "name": "air_date_to",
                            "in": "query",
                            "description": "Filter episodes to this date",
                            "schema": {"type": "string", "format": "date"}
                        },
                        {
                            "name": "winner",
                            "in": "query",
                            "description": "Filter by winner",
                            "schema": {"type": "string", "maxLength": 20}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "List of episodes",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "allOf": [
                                            {"$ref": "#/components/schemas/APIResponse"},
                                            {
                                                "properties": {
                                                    "data": {
                                                        "type": "array",
                                                        "items": {"$ref": "#/components/schemas/Episode"}
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "429": {"$ref": "#/components/responses/RateLimitExceeded"},
                        "500": {"$ref": "#/components/responses/InternalServerError"}
                    },
                    "security": [{"ApiKeyAuth": []}, {}]
                }
            },
            "/api/v1/episodes/{id}": {
                "get": {
                    "tags": ["Episodes"],
                    "summary": "Get episode details",
                    "description": "Get detailed information about a specific episode",
                    "operationId": "getEpisode",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": true,
                            "description": "Episode ID",
                            "schema": {"type": "integer", "minimum": 1}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Episode details",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "allOf": [
                                            {"$ref": "#/components/schemas/APIResponse"},
                                            {
                                                "properties": {
                                                    "data": {"$ref": "#/components/schemas/Episode"}
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "404": {"$ref": "#/components/responses/NotFound"},
                        "429": {"$ref": "#/components/responses/RateLimitExceeded"},
                        "500": {"$ref": "#/components/responses/InternalServerError"}
                    },
                    "security": [{"ApiKeyAuth": []}, {}]
                }
            },
            "/api/v1/episodes/{id}/dishes": {
                "get": {
                    "tags": ["Dishes"],
                    "summary": "Get episode dishes",
                    "description": "Get all dishes from a specific episode",
                    "operationId": "getEpisodeDishes",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": true,
                            "description": "Episode ID",
                            "schema": {"type": "integer", "minimum": 1}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "List of dishes",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "allOf": [
                                            {"$ref": "#/components/schemas/APIResponse"},
                                            {
                                                "properties": {
                                                    "data": {
                                                        "type": "array",
                                                        "items": {"$ref": "#/components/schemas/Dish"}
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "404": {"$ref": "#/components/responses/NotFound"},
                        "429": {"$ref": "#/components/responses/RateLimitExceeded"},
                        "500": {"$ref": "#/components/responses/InternalServerError"}
                    },
                    "security": [{"ApiKeyAuth": []}, {}]
                }
            },
            "/api/v1/recipes/generate": {
                "post": {
                    "tags": ["Recipes"],
                    "summary": "Generate recipe",
                    "description": "Generate a recipe from dish data. Requires API key authentication.",
                    "operationId": "generateRecipe",
                    "requestBody": {
                        "required": true,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/RecipeGenerationRequest"},
                                "examples": {
                                    "basic": {
                                        "summary": "Basic recipe generation",
                                        "value": {
                                            "dish_id": 1,
                                            "chef_style": "traditional",
                                            "difficulty": "medium"
                                        }
                                    },
                                    "advanced": {
                                        "summary": "Advanced recipe with restrictions",
                                        "value": {
                                            "dish_id": 1,
                                            "chef_style": "modern",
                                            "difficulty": "hard",
                                            "dietary_restrictions": ["vegetarian", "gluten-free"],
                                            "servings": 6,
                                            "prep_time_target": 45,
                                            "cook_time_target": 30
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Recipe generated successfully",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "allOf": [
                                            {"$ref": "#/components/schemas/APIResponse"},
                                            {
                                                "properties": {
                                                    "data": {
                                                        "type": "object",
                                                        "properties": {
                                                            "recipe_id": {"type": "integer"},
                                                            "message": {"type": "string"}
                                                        }
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                        "404": {"$ref": "#/components/responses/NotFound"},
                        "409": {
                            "description": "Recipe already exists",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Error"}
                                }
                            }
                        },
                        "429": {"$ref": "#/components/responses/RateLimitExceeded"},
                        "500": {"$ref": "#/components/responses/InternalServerError"}
                    },
                    "security": [{"ApiKeyAuth": []}]
                }
            },
            "/api/v1/recipes/{id}": {
                "get": {
                    "tags": ["Recipes"],
                    "summary": "Get recipe details",
                    "description": "Get detailed information about a specific recipe",
                    "operationId": "getRecipe",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": true,
                            "description": "Recipe ID",
                            "schema": {"type": "integer", "minimum": 1}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Recipe details",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "allOf": [
                                            {"$ref": "#/components/schemas/APIResponse"},
                                            {
                                                "properties": {
                                                    "data": {"$ref": "#/components/schemas/Recipe"}
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "404": {"$ref": "#/components/responses/NotFound"},
                        "429": {"$ref": "#/components/responses/RateLimitExceeded"},
                        "500": {"$ref": "#/components/responses/InternalServerError"}
                    },
                    "security": [{"ApiKeyAuth": []}, {}]
                }
            },
            "/api/v1/search": {
                "get": {
                    "tags": ["Search"],
                    "summary": "Global search",
                    "description": "Search across episodes, dishes, and recipes",
                    "operationId": "search",
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "required": true,
                            "description": "Search query",
                            "schema": {"type": "string", "minLength": 1, "maxLength": 100}
                        },
                        {
                            "name": "search_type",
                            "in": "query",
                            "description": "Limit search to specific type",
                            "schema": {"type": "string", "enum": ["episode", "dish", "recipe"]}
                        },
                        {
                            "name": "page",
                            "in": "query",
                            "description": "Page number",
                            "schema": {"type": "integer", "minimum": 1, "default": 1}
                        },
                        {
                            "name": "per_page",
                            "in": "query",
                            "description": "Items per page",
                            "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 12}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Search results",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "allOf": [
                                            {"$ref": "#/components/schemas/APIResponse"},
                                            {
                                                "properties": {
                                                    "data": {
                                                        "type": "object",
                                                        "properties": {
                                                            "results": {
                                                                "type": "array",
                                                                "items": {"$ref": "#/components/schemas/SearchResult"}
                                                            },
                                                            "summary": {
                                                                "type": "object",
                                                                "properties": {
                                                                    "episodes": {"type": "integer"},
                                                                    "dishes": {"type": "integer"},
                                                                    "recipes": {"type": "integer"},
                                                                    "total": {"type": "integer"}
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "429": {"$ref": "#/components/responses/RateLimitExceeded"},
                        "500": {"$ref": "#/components/responses/InternalServerError"}
                    },
                    "security": [{"ApiKeyAuth": []}, {}]
                }
            },
            "/api/v1/themes": {
                "get": {
                    "tags": ["Data"],
                    "summary": "Get all themes",
                    "description": "Get all available episode themes",
                    "operationId": "getThemes",
                    "responses": {
                        "200": {
                            "description": "List of themes",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "allOf": [
                                            {"$ref": "#/components/schemas/APIResponse"},
                                            {
                                                "properties": {
                                                    "data": {
                                                        "type": "object",
                                                        "properties": {
                                                            "themes": {
                                                                "type": "array",
                                                                "items": {"type": "string"}
                                                            },
                                                            "count": {"type": "integer"}
                                                        }
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        },
                        "429": {"$ref": "#/components/responses/RateLimitExceeded"},
                        "500": {"$ref": "#/components/responses/InternalServerError"}
                    },
                    "security": [{"ApiKeyAuth": []}, {}]
                }
            },
            "/api/v1/chefs": {
                "get": {
                    "tags": ["Data"],
                    "summary": "Get all chefs",
                    "description": "Get all iron chefs and competitors",
                    "operationId": "getChefs",
                    "responses": {
                        "200": {
                            "description": "List of chefs",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "allOf": [
                                            {"$ref": "#/components/schemas/APIResponse"},
                                            {
                                                "properties": {
                                                    "data": {
                                                        "type": "object",
                                                        "properties": {
                                                            "iron_chefs": {
                                                                "type": "array",
                                                                "items": {"$ref": "#/components/schemas/IronChef"}
                                                            },
                                                            "competitors": {
                                                                "type": "array",
                                                                "items": {"$ref": "#/components/schemas/Competitor"}
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        },
                        "429": {"$ref": "#/components/responses/RateLimitExceeded"},
                        "500": {"$ref": "#/components/responses/InternalServerError"}
                    },
                    "security": [{"ApiKeyAuth": []}, {}]
                }
            },
            "/api/v1/export/{format}": {
                "get": {
                    "tags": ["Data"],
                    "summary": "Export data",
                    "description": "Export data in various formats. Requires API key authentication.",
                    "operationId": "exportData",
                    "parameters": [
                        {
                            "name": "format",
                            "in": "path",
                            "required": true,
                            "description": "Export format",
                            "schema": {"type": "string", "enum": ["json", "csv", "txt"]}
                        },
                        {
                            "name": "type",
                            "in": "query",
                            "required": true,
                            "description": "Data type to export",
                            "schema": {"type": "string", "enum": ["episodes", "recipes", "dishes", "theme"]}
                        },
                        {
                            "name": "theme",
                            "in": "query",
                            "description": "Theme filter (required for theme exports)",
                            "schema": {"type": "string", "maxLength": 100}
                        },
                        {
                            "name": "include_recipes",
                            "in": "query",
                            "description": "Include recipe data",
                            "schema": {"type": "boolean", "default": true}
                        },
                        {
                            "name": "date_from",
                            "in": "query",
                            "description": "Include data from this date",
                            "schema": {"type": "string", "format": "date"}
                        },
                        {
                            "name": "date_to",
                            "in": "query",
                            "description": "Include data up to this date",
                            "schema": {"type": "string", "format": "date"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Export file",
                            "content": {
                                "application/json": {"schema": {"type": "object"}},
                                "text/csv": {"schema": {"type": "string"}},
                                "text/plain": {"schema": {"type": "string"}}
                            }
                        },
                        "400": {"$ref": "#/components/responses/BadRequest"},
                        "401": {"$ref": "#/components/responses/Unauthorized"},
                        "429": {"$ref": "#/components/responses/RateLimitExceeded"},
                        "500": {"$ref": "#/components/responses/InternalServerError"}
                    },
                    "security": [{"ApiKeyAuth": []}]
                }
            }
        }
    }

def add_docs_routes(app: Flask):
    """Add documentation routes to Flask app"""
    
    @app.route('/api/docs')
    def api_docs():
        """Serve Swagger UI documentation"""
        return render_template_string(
            create_swagger_ui_html('/api/spec'),
            spec_url='/api/spec'
        )
    
    @app.route('/api/spec')
    def api_spec():
        """Serve OpenAPI specification"""
        return jsonify(generate_openapi_spec_complete())
    
    @app.route('/api/redoc')
    def api_redoc():
        """Serve ReDoc documentation"""
        redoc_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Iron Chef Recipe Database API</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <style>
        body { margin: 0; padding: 0; }
    </style>
</head>
<body>
    <redoc spec-url='/api/spec'></redoc>
    <script src="https://cdn.jsdelivr.net/npm/redoc@2.0.0/bundles/redoc.standalone.js"></script>
</body>
</html>
        """
        return render_template_string(redoc_html)

if __name__ == '__main__':
    # Generate and print the spec for development
    spec = generate_openapi_spec()
    print(json.dumps(spec, indent=2))