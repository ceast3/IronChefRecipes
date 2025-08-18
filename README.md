# Iron Chef Japan Episode Database & Recipe Generator

A comprehensive database system for tracking Iron Chef Japan episodes, including iron chefs, challengers, themes, dishes served, and an automated recipe generation system.

## Features

- **Episode Database**: Store complete episode information including:
  - Episode number and air date
  - Theme ingredient
  - Iron Chef and challenger details
  - Winner and judges' scores
  - All dishes served by both chefs

- **Recipe Generator**: Automatically generate detailed recipes based on:
  - Dish names and ingredients from episodes
  - Cuisine style (Japanese, Chinese, French, Italian)
  - Professional cooking techniques
  - Wine pairings and chef tips

- **Search Capabilities**:
  - Search episodes by theme
  - Find dishes by ingredient
  - Browse all episodes and chefs

## Installation

1. Make sure you have Python 3.7+ installed
2. Clone or download this repository
3. No additional dependencies required (uses sqlite3 from standard library)

## Usage

### Quick Demo
Run the main demonstration script:
```bash
python main.py
```

This will:
1. Initialize the database
2. Load sample episode data
3. Demonstrate various queries
4. Generate sample recipes
5. Show search capabilities

### Interactive Mode
For interactive exploration:
```bash
python main.py --interactive
```

This allows you to:
- Browse all episodes
- Search by theme or ingredient
- View detailed episode information
- Generate recipes on demand
- Save recipes to the database

### Load Sample Data Only
To just populate the database:
```bash
python sample_data_loader.py
```

## Database Schema

The system uses SQLite with the following main tables:
- `iron_chefs`: Iron Chef information
- `competitors`: Challenger details
- `episodes`: Episode metadata
- `dishes`: All dishes served in episodes
- `recipes`: Generated recipes
- `ingredients`: Master ingredient list

## Sample Data

The system includes sample data from iconic Iron Chef Japan episodes:
- **Episode 1**: Sea Bream (Michiba vs Yukio Hattori)
- **Episode 42**: Foie Gras (Sakai vs Alain Passard)
- **Episode 75**: Shark Fin (Chen vs Kazunori Otowa)
- **Episode 150**: Lobster (Morimoto vs Masahiko Kobe)
- **Episode 200**: Bamboo Shoots (Chen vs Yutaka Ishinabe)

## Recipe Generation

The recipe generator creates professional-style recipes including:
- **Realistic ingredient quantities** based on dish type and serving size
- **Accurate cooking times** for different preparation methods (0 min for sashimi, 25 min for risotto, etc.)
- **Method-specific instructions** with proper techniques for grilling, steaming, stir-frying, etc.
- **Cuisine-specific chef tips** (Japanese umami techniques, French butter handling, Italian pasta tips)
- **Intelligent wine pairings** based on cuisine style
- **Professional presentation guidance**

Recipes are generated based on:
- **Advanced dish name parsing** to detect cooking methods (risotto, sashimi, gratin, etc.)
- **Ingredient-specific preparation methods** (lobster cleaning, foie gras scoring, etc.)
- **Cuisine-appropriate techniques** matching the chef's background
- **Professional culinary standards** with mise en place and temperature control

## Extending the Database

To add more episodes:
1. Use the `IronChefDatabase` class methods
2. Add iron chefs with `add_iron_chef()`
3. Add competitors with `add_competitor()`
4. Add episodes with `add_episode()`
5. Add dishes with `add_dish()`

Example:
```python
from iron_chef_database import IronChefDatabase

with IronChefDatabase() as db:
    chef_id = db.add_iron_chef("Chen Kenichi", "Iron Chef Chinese", "Szechuan Cuisine", "1993-1999")
    comp_id = db.add_competitor("Guest Chef", "Restaurant Name", "Specialty")
    ep_id = db.add_episode(300, "Mystery Theme", chef_id, comp_id)
    db.add_dish(ep_id, "iron_chef", 1, "Amazing Dish", main_ingredients="ingredient1, ingredient2")
```

## Export Functionality

The new export system allows you to save data in multiple formats:

```bash
# Export all episodes to JSON or CSV
python recipe_exporter.py episodes --format json
python recipe_exporter.py episodes --format csv

# Export a specific recipe to text or JSON
python recipe_exporter.py recipe --dish-id 22 --format txt
python recipe_exporter.py recipe --dish-id 22 --format json

# Export all recipes in the database
python recipe_exporter.py all-recipes --format json

# Export all dishes for a specific theme
python recipe_exporter.py theme --theme "Lobster" --format json
```

## Error Handling & Interactive Mode

The interactive mode now includes:
- **Robust error handling** for invalid inputs and missing data
- **Graceful EOF/Keyboard interrupt handling** 
- **Input validation** with helpful error messages
- **Automatic cuisine detection** based on dish names and chef background

## Files

- `database_schema.sql`: Complete database schema
- `iron_chef_database.py`: Database management class
- `recipe_generator.py`: Enhanced recipe generation system with realistic cooking methods
- `recipe_exporter.py`: Export utilities for multiple formats
- `sample_data_loader.py`: Sample data population
- `main.py`: Demonstration and interactive interface with error handling
- `iron_chef_japan.db`: SQLite database (created on first run)

## Improvements Made

### Recipe Realism
- ✅ Fixed cooking times (sashimi = 0 min, not 24 min)
- ✅ Realistic ingredient quantities (8 oz lobster for sashimi, not 2 cups)
- ✅ Proper cooking method detection (risotto, pasta, gratin, tempura, etc.)
- ✅ Ingredient-specific preparation notes

### Enhanced Instructions
- ✅ Method-specific step-by-step instructions for 15+ cooking techniques
- ✅ Professional culinary terminology and techniques
- ✅ Temperature and timing guidance
- ✅ Presentation and plating instructions

### Better User Experience
- ✅ Robust interactive mode with error handling
- ✅ Export functionality in multiple formats
- ✅ Improved chef tips with cuisine-specific advice
- ✅ Better wine pairing logic

## Future Enhancements

- Add more episodes from the complete Iron Chef Japan series
- Implement nutritional information calculation
- Create a web interface for browsing and searching
- Add image generation for dishes
- Integration with recipe sharing platforms