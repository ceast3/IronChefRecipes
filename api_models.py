#!/usr/bin/env python3
"""
Iron Chef Recipe Database API Models
Comprehensive Pydantic models for request/response validation and OpenAPI documentation
"""

from typing import List, Optional, Union, Dict, Any
from datetime import datetime, date
from enum import Enum
from pydantic import BaseModel, Field, validator, ConfigDict
from marshmallow import Schema, fields, validate


class ChefStyleEnum(str, Enum):
    """Available chef cooking styles"""
    traditional = "traditional"
    modern = "modern"
    fusion = "fusion"
    molecular = "molecular"


class DifficultyEnum(str, Enum):
    """Recipe difficulty levels"""
    easy = "easy"
    medium = "medium"
    hard = "hard"
    expert = "expert"


class ChefTypeEnum(str, Enum):
    """Chef types in episodes"""
    iron_chef = "iron_chef"
    competitor = "competitor"


class ExportFormatEnum(str, Enum):
    """Supported export formats"""
    json = "json"
    csv = "csv"
    txt = "txt"


class SearchTypeEnum(str, Enum):
    """Search result types"""
    episode = "episode"
    dish = "dish"
    recipe = "recipe"


# Request Models
class PaginationRequest(BaseModel):
    """Pagination parameters for list endpoints"""
    page: int = Field(default=1, ge=1, le=10000, description="Page number (1-based)")
    per_page: int = Field(default=12, ge=1, le=100, description="Items per page")


class EpisodeFilterRequest(PaginationRequest):
    """Episode filtering and pagination parameters"""
    theme: Optional[str] = Field(None, max_length=100, description="Filter by theme")
    chef: Optional[str] = Field(None, max_length=100, description="Filter by chef name")
    iron_chef_id: Optional[int] = Field(None, ge=1, description="Filter by Iron Chef ID")
    competitor_id: Optional[int] = Field(None, ge=1, description="Filter by competitor ID")
    air_date_from: Optional[date] = Field(None, description="Filter episodes from this date")
    air_date_to: Optional[date] = Field(None, description="Filter episodes to this date")
    winner: Optional[str] = Field(None, max_length=20, description="Filter by winner")

    @validator('air_date_to')
    def validate_date_range(cls, v, values):
        if v and 'air_date_from' in values and values['air_date_from']:
            if v < values['air_date_from']:
                raise ValueError('air_date_to must be after air_date_from')
        return v


class RecipeFilterRequest(PaginationRequest):
    """Recipe filtering and pagination parameters"""
    dish_name: Optional[str] = Field(None, max_length=100, description="Filter by dish name")
    ingredient: Optional[str] = Field(None, max_length=100, description="Filter by ingredient")
    chef_type: Optional[ChefTypeEnum] = Field(None, description="Filter by chef type")
    episode_id: Optional[int] = Field(None, ge=1, description="Filter by episode ID")
    theme: Optional[str] = Field(None, max_length=100, description="Filter by episode theme")
    prep_time_max: Optional[int] = Field(None, ge=0, description="Maximum prep time in minutes")
    cook_time_max: Optional[int] = Field(None, ge=0, description="Maximum cook time in minutes")
    servings: Optional[int] = Field(None, ge=1, le=20, description="Number of servings")


class SearchRequest(PaginationRequest):
    """Global search parameters"""
    q: str = Field(..., min_length=1, max_length=100, description="Search query")
    search_type: Optional[SearchTypeEnum] = Field(None, description="Limit search to specific type")


class RecipeGenerationRequest(BaseModel):
    """Recipe generation parameters"""
    dish_id: int = Field(..., ge=1, description="ID of the dish to generate recipe for")
    chef_style: ChefStyleEnum = Field(default=ChefStyleEnum.traditional, description="Cooking style")
    difficulty: DifficultyEnum = Field(default=DifficultyEnum.medium, description="Recipe difficulty")
    dietary_restrictions: List[str] = Field(default=[], description="Dietary restrictions to consider")
    servings: Optional[int] = Field(default=4, ge=1, le=20, description="Number of servings")
    prep_time_target: Optional[int] = Field(None, ge=5, le=300, description="Target prep time in minutes")
    cook_time_target: Optional[int] = Field(None, ge=5, le=480, description="Target cook time in minutes")

    @validator('dietary_restrictions')
    def validate_dietary_restrictions(cls, v):
        allowed = {
            'vegetarian', 'vegan', 'gluten-free', 'dairy-free', 'nut-free', 
            'shellfish-free', 'egg-free', 'soy-free', 'low-sodium', 'low-fat',
            'keto', 'paleo', 'halal', 'kosher'
        }
        for restriction in v:
            if restriction.lower() not in allowed:
                raise ValueError(f'Invalid dietary restriction: {restriction}')
        return v


class ExportRequest(BaseModel):
    """Data export parameters"""
    format: ExportFormatEnum = Field(default=ExportFormatEnum.json, description="Export format")
    theme: Optional[str] = Field(None, max_length=100, description="Filter by theme (for theme exports)")
    include_recipes: bool = Field(default=True, description="Include recipe data in exports")
    date_from: Optional[date] = Field(None, description="Include data from this date")
    date_to: Optional[date] = Field(None, description="Include data up to this date")


# Response Models
class IronChef(BaseModel):
    """Iron Chef information"""
    id: int = Field(..., description="Iron Chef ID")
    name: str = Field(..., description="Iron Chef name")
    title: Optional[str] = Field(None, description="Iron Chef title")
    specialty: Optional[str] = Field(None, description="Culinary specialty")
    active_years: Optional[str] = Field(None, description="Years active on the show")


class Competitor(BaseModel):
    """Competitor chef information"""
    id: int = Field(..., description="Competitor ID")
    name: str = Field(..., description="Competitor name")
    restaurant: Optional[str] = Field(None, description="Restaurant affiliation")
    specialty: Optional[str] = Field(None, description="Culinary specialty")
    location: Optional[str] = Field(None, description="Location")


class Episode(BaseModel):
    """Episode information"""
    id: int = Field(..., description="Episode ID")
    episode_number: int = Field(..., description="Episode number")
    air_date: Optional[date] = Field(None, description="Original air date")
    theme: str = Field(..., description="Episode theme/secret ingredient")
    iron_chef_id: int = Field(..., description="Iron Chef ID")
    competitor_id: int = Field(..., description="Competitor ID")
    winner: Optional[str] = Field(None, description="Episode winner")
    judges_scores: Optional[str] = Field(None, description="Judges' scores")
    iron_chef_name: Optional[str] = Field(None, description="Iron Chef name")
    competitor_name: Optional[str] = Field(None, description="Competitor name")


class EpisodeDetail(Episode):
    """Detailed episode information with related data"""
    iron_chef: Optional[IronChef] = Field(None, description="Iron Chef details")
    competitor: Optional[Competitor] = Field(None, description="Competitor details")
    dishes: List['Dish'] = Field(default=[], description="Dishes from this episode")
    recipes_count: int = Field(default=0, description="Number of generated recipes")


class Dish(BaseModel):
    """Dish information"""
    id: int = Field(..., description="Dish ID")
    episode_id: int = Field(..., description="Episode ID")
    chef_type: ChefTypeEnum = Field(..., description="Chef type")
    dish_number: int = Field(..., description="Dish number in the episode")
    dish_name: str = Field(..., description="Name of the dish")
    description: Optional[str] = Field(None, description="Dish description")
    main_ingredients: Optional[str] = Field(None, description="Main ingredients")
    cooking_techniques: Optional[str] = Field(None, description="Cooking techniques used")


class DishDetail(Dish):
    """Detailed dish information with related data"""
    episode: Optional[Episode] = Field(None, description="Episode details")
    recipe: Optional['Recipe'] = Field(None, description="Generated recipe if available")
    has_recipe: bool = Field(default=False, description="Whether a recipe exists for this dish")


class Recipe(BaseModel):
    """Recipe information"""
    id: int = Field(..., description="Recipe ID")
    dish_id: int = Field(..., description="Dish ID")
    recipe_title: str = Field(..., description="Recipe title")
    ingredients: List[Dict[str, Any]] = Field(..., description="Recipe ingredients")
    instructions: List[str] = Field(..., description="Cooking instructions")
    prep_time: Optional[int] = Field(None, description="Preparation time in minutes")
    cook_time: Optional[int] = Field(None, description="Cooking time in minutes")
    servings: Optional[int] = Field(None, description="Number of servings")
    generated_date: datetime = Field(..., description="Recipe generation timestamp")


class RecipeDetail(Recipe):
    """Detailed recipe information with related data"""
    dish: Optional[Dish] = Field(None, description="Dish details")
    episode: Optional[Episode] = Field(None, description="Episode details")
    total_time: Optional[int] = Field(None, description="Total time (prep + cook)")
    difficulty_estimate: Optional[str] = Field(None, description="Estimated difficulty")
    dietary_tags: List[str] = Field(default=[], description="Detected dietary tags")


class SearchResult(BaseModel):
    """Search result item"""
    type: SearchTypeEnum = Field(..., description="Result type")
    id: int = Field(..., description="Item ID")
    title: str = Field(..., description="Item title")
    description: Optional[str] = Field(None, description="Item description")
    episode_number: Optional[int] = Field(None, description="Related episode number")
    theme: Optional[str] = Field(None, description="Related episode theme")
    relevance_score: Optional[float] = Field(None, description="Search relevance score")


class SearchResults(BaseModel):
    """Search results with summary"""
    results: List[SearchResult] = Field(..., description="Search results")
    summary: Dict[str, int] = Field(..., description="Results count by type")
    total: int = Field(..., description="Total number of results")
    query: str = Field(..., description="Original search query")


class Pagination(BaseModel):
    """Pagination information"""
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    total: int = Field(..., description="Total number of items")
    pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")
    next_page: Optional[int] = Field(None, description="Next page number")
    prev_page: Optional[int] = Field(None, description="Previous page number")


class APIResponse(BaseModel):
    """Standard API response wrapper"""
    success: bool = Field(..., description="Whether the request was successful")
    data: Optional[Union[Dict[str, Any], List[Any], str, int]] = Field(None, description="Response data")
    message: Optional[str] = Field(None, description="Response message")
    errors: List[str] = Field(default=[], description="Error messages")
    pagination: Optional[Pagination] = Field(None, description="Pagination information")
    meta: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class APIError(BaseModel):
    """API error response"""
    success: bool = Field(default=False, description="Always false for errors")
    message: str = Field(..., description="Error message")
    errors: List[str] = Field(..., description="Detailed error messages")
    error_code: Optional[str] = Field(None, description="Error code for programmatic handling")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class HealthCheck(BaseModel):
    """API health check response"""
    status: str = Field(..., description="API status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(..., description="Current timestamp")
    database: Dict[str, Any] = Field(..., description="Database status")
    uptime: Optional[str] = Field(None, description="Service uptime")


class ThemeList(BaseModel):
    """List of available themes"""
    themes: List[str] = Field(..., description="Available episode themes")
    count: int = Field(..., description="Number of themes")
    popular_themes: Optional[List[Dict[str, Any]]] = Field(None, description="Most popular themes with counts")


class ChefsList(BaseModel):
    """List of iron chefs and competitors"""
    iron_chefs: List[IronChef] = Field(..., description="Iron chefs")
    competitors: List[Competitor] = Field(..., description="Competitor chefs")
    total_iron_chefs: int = Field(..., description="Total number of iron chefs")
    total_competitors: int = Field(..., description="Total number of competitors")


class ExportResult(BaseModel):
    """Export operation result"""
    filename: str = Field(..., description="Generated filename")
    format: ExportFormatEnum = Field(..., description="Export format")
    record_count: int = Field(..., description="Number of records exported")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Export timestamp")
    download_url: str = Field(..., description="Download URL")


class APIStats(BaseModel):
    """API usage statistics"""
    total_requests: int = Field(..., description="Total API requests")
    requests_today: int = Field(..., description="Requests today")
    active_api_keys: int = Field(..., description="Number of active API keys")
    popular_endpoints: List[Dict[str, Any]] = Field(..., description="Most popular endpoints")
    response_times: Dict[str, float] = Field(..., description="Average response times")


# Update forward references
EpisodeDetail.model_rebuild()
DishDetail.model_rebuild()
RecipeDetail.model_rebuild()


# Marshmallow schemas for backward compatibility with existing API
class EpisodeFilterSchema(Schema):
    """Marshmallow schema for episode filtering"""
    page = fields.Int(load_default=1, validate=validate.Range(min=1, max=10000))
    per_page = fields.Int(load_default=12, validate=validate.Range(min=1, max=100))
    theme = fields.Str(load_default=None, validate=validate.Length(max=100), allow_none=True)
    chef = fields.Str(load_default=None, validate=validate.Length(max=100), allow_none=True)
    iron_chef_id = fields.Int(load_default=None, validate=validate.Range(min=1), allow_none=True)
    competitor_id = fields.Int(load_default=None, validate=validate.Range(min=1), allow_none=True)
    air_date_from = fields.Date(load_default=None, allow_none=True)
    air_date_to = fields.Date(load_default=None, allow_none=True)
    winner = fields.Str(load_default=None, validate=validate.Length(max=20), allow_none=True)


class RecipeGenerationSchema(Schema):
    """Marshmallow schema for recipe generation"""
    dish_id = fields.Int(required=True, validate=validate.Range(min=1))
    chef_style = fields.Str(load_default="traditional", validate=validate.OneOf([
        "traditional", "modern", "fusion", "molecular"
    ]))
    difficulty = fields.Str(load_default="medium", validate=validate.OneOf([
        "easy", "medium", "hard", "expert"
    ]))
    dietary_restrictions = fields.List(fields.Str(), load_default=[])
    servings = fields.Int(load_default=4, validate=validate.Range(min=1, max=20))
    prep_time_target = fields.Int(load_default=None, validate=validate.Range(min=5, max=300), allow_none=True)
    cook_time_target = fields.Int(load_default=None, validate=validate.Range(min=5, max=480), allow_none=True)


class SearchSchema(Schema):
    """Marshmallow schema for search"""
    page = fields.Int(load_default=1, validate=validate.Range(min=1, max=10000))
    per_page = fields.Int(load_default=12, validate=validate.Range(min=1, max=100))
    q = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    search_type = fields.Str(load_default=None, validate=validate.OneOf([
        "episode", "dish", "recipe"
    ]), allow_none=True)


# Response serialization schemas
class IronChefSchema(Schema):
    """Iron Chef serialization schema"""
    id = fields.Int()
    name = fields.Str()
    title = fields.Str()
    specialty = fields.Str()
    active_years = fields.Str()


class CompetitorSchema(Schema):
    """Competitor serialization schema"""
    id = fields.Int()
    name = fields.Str()
    restaurant = fields.Str()
    specialty = fields.Str()
    location = fields.Str()


class EpisodeSchema(Schema):
    """Episode serialization schema"""
    id = fields.Int()
    episode_number = fields.Int()
    air_date = fields.Date()
    theme = fields.Str()
    iron_chef_id = fields.Int()
    competitor_id = fields.Int()
    winner = fields.Str()
    judges_scores = fields.Str()
    iron_chef_name = fields.Str()
    competitor_name = fields.Str()


class DishSchema(Schema):
    """Dish serialization schema"""
    id = fields.Int()
    episode_id = fields.Int()
    chef_type = fields.Str()
    dish_number = fields.Int()
    dish_name = fields.Str()
    description = fields.Str()
    main_ingredients = fields.Str()
    cooking_techniques = fields.Str()


class RecipeSchema(Schema):
    """Recipe serialization schema"""
    id = fields.Int()
    dish_id = fields.Int()
    recipe_title = fields.Str()
    ingredients = fields.Raw()  # JSON field
    instructions = fields.Raw()  # JSON field
    prep_time = fields.Int()
    cook_time = fields.Int()
    servings = fields.Int()
    generated_date = fields.DateTime()
    dish_name = fields.Str()
    episode_number = fields.Int()
    theme = fields.Str()


class APIResponseSchema(Schema):
    """Standard API response schema"""
    success = fields.Bool()
    data = fields.Raw()
    message = fields.Str()
    errors = fields.List(fields.Str())
    pagination = fields.Dict()
    meta = fields.Dict()