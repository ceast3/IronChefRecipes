-- Iron Chef Japan Episodes Database Schema

-- Iron Chefs table
CREATE TABLE iron_chefs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    title VARCHAR(100),
    specialty VARCHAR(100),
    active_years VARCHAR(50)
);

-- Competitors table
CREATE TABLE competitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    restaurant VARCHAR(200),
    specialty VARCHAR(100),
    location VARCHAR(100)
);

-- Episodes table
CREATE TABLE episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_number INTEGER NOT NULL,
    air_date DATE,
    theme VARCHAR(100) NOT NULL,
    iron_chef_id INTEGER NOT NULL,
    competitor_id INTEGER NOT NULL,
    winner VARCHAR(20),
    judges_scores VARCHAR(100),
    FOREIGN KEY (iron_chef_id) REFERENCES iron_chefs(id),
    FOREIGN KEY (competitor_id) REFERENCES competitors(id)
);

-- Dishes table
CREATE TABLE dishes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id INTEGER NOT NULL,
    chef_type VARCHAR(20) NOT NULL, -- 'iron_chef' or 'competitor'
    dish_number INTEGER NOT NULL,
    dish_name VARCHAR(200) NOT NULL,
    description TEXT,
    main_ingredients TEXT,
    cooking_techniques TEXT,
    FOREIGN KEY (episode_id) REFERENCES episodes(id)
);

-- Recipes table (for future recipe generation)
CREATE TABLE recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dish_id INTEGER NOT NULL,
    recipe_title VARCHAR(200) NOT NULL,
    ingredients TEXT NOT NULL,
    instructions TEXT NOT NULL,
    prep_time INTEGER,
    cook_time INTEGER,
    servings INTEGER,
    generated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dish_id) REFERENCES dishes(id)
);

-- Ingredients table (for detailed ingredient tracking)
CREATE TABLE ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- Dish ingredients junction table
CREATE TABLE dish_ingredients (
    dish_id INTEGER NOT NULL,
    ingredient_id INTEGER NOT NULL,
    quantity VARCHAR(50),
    unit VARCHAR(20),
    PRIMARY KEY (dish_id, ingredient_id),
    FOREIGN KEY (dish_id) REFERENCES dishes(id),
    FOREIGN KEY (ingredient_id) REFERENCES ingredients(id)
);

-- Create indexes for better query performance
CREATE INDEX idx_episodes_theme ON episodes(theme);
CREATE INDEX idx_episodes_iron_chef ON episodes(iron_chef_id);
CREATE INDEX idx_episodes_competitor ON episodes(competitor_id);
CREATE INDEX idx_dishes_episode ON dishes(episode_id);
CREATE INDEX idx_dishes_chef_type ON dishes(chef_type);