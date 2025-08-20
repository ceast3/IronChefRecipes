#!/usr/bin/env python3
"""
Database Migration Script: Add Performance Indices
Migrates existing Iron Chef databases to include optimized indices for better query performance.
"""

import sqlite3
import time
import logging
from pathlib import Path
from typing import List, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DatabaseMigration:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
        
    def __enter__(self):
        self.connection = sqlite3.connect(self.db_path)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.close()
    
    def get_existing_indices(self) -> List[str]:
        """Get list of existing indices in the database"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND sql IS NOT NULL")
        return [row[0] for row in cursor.fetchall()]
    
    def create_index_safely(self, index_sql: str, index_name: str) -> bool:
        """Create an index if it doesn't already exist"""
        existing_indices = self.get_existing_indices()
        
        if index_name in existing_indices:
            logger.info(f"Index {index_name} already exists, skipping...")
            return False
            
        try:
            start_time = time.time()
            cursor = self.connection.cursor()
            cursor.execute(index_sql)
            self.connection.commit()
            elapsed_time = time.time() - start_time
            logger.info(f"Created index {index_name} in {elapsed_time:.2f} seconds")
            return True
        except sqlite3.Error as e:
            logger.error(f"Failed to create index {index_name}: {e}")
            return False
    
    def migrate_indices(self) -> Tuple[int, int]:
        """Add all new performance indices to the database"""
        indices_to_create = [
            # Episode-related indices
            ("CREATE INDEX IF NOT EXISTS idx_episodes_air_date ON episodes(air_date)", "idx_episodes_air_date"),
            ("CREATE INDEX IF NOT EXISTS idx_episodes_episode_number ON episodes(episode_number)", "idx_episodes_episode_number"),
            
            # Recipe-related indices (foreign key and temporal queries)
            ("CREATE INDEX IF NOT EXISTS idx_recipes_dish_id ON recipes(dish_id)", "idx_recipes_dish_id"),
            ("CREATE INDEX IF NOT EXISTS idx_recipes_generated_date ON recipes(generated_date)", "idx_recipes_generated_date"),
            
            # Dish ingredients junction table indices (critical for join performance)
            ("CREATE INDEX IF NOT EXISTS idx_dish_ingredients_dish_id ON dish_ingredients(dish_id)", "idx_dish_ingredients_dish_id"),
            ("CREATE INDEX IF NOT EXISTS idx_dish_ingredients_ingredient_id ON dish_ingredients(ingredient_id)", "idx_dish_ingredients_ingredient_id"),
            
            # Ingredient search optimization
            ("CREATE INDEX IF NOT EXISTS idx_ingredients_name ON ingredients(name)", "idx_ingredients_name"),
            
            # Composite indices for common query patterns
            ("CREATE INDEX IF NOT EXISTS idx_episodes_theme_date ON episodes(theme, air_date)", "idx_episodes_theme_date"),
            ("CREATE INDEX IF NOT EXISTS idx_dishes_episode_chef ON dishes(episode_id, chef_type)", "idx_dishes_episode_chef"),
            ("CREATE INDEX IF NOT EXISTS idx_recipes_dish_date ON recipes(dish_id, generated_date)", "idx_recipes_dish_date"),
        ]
        
        created_count = 0
        total_count = len(indices_to_create)
        
        logger.info(f"Starting migration: adding {total_count} performance indices...")
        
        for index_sql, index_name in indices_to_create:
            if self.create_index_safely(index_sql, index_name):
                created_count += 1
        
        logger.info(f"Migration completed: {created_count}/{total_count} new indices created")
        return created_count, total_count
    
    def analyze_database(self):
        """Run ANALYZE to update SQLite's query planner statistics"""
        logger.info("Running ANALYZE to update query planner statistics...")
        try:
            start_time = time.time()
            cursor = self.connection.cursor()
            cursor.execute("ANALYZE")
            self.connection.commit()
            elapsed_time = time.time() - start_time
            logger.info(f"ANALYZE completed in {elapsed_time:.2f} seconds")
        except sqlite3.Error as e:
            logger.error(f"Failed to run ANALYZE: {e}")
    
    def get_database_stats(self) -> dict:
        """Get basic database statistics"""
        cursor = self.connection.cursor()
        stats = {}
        
        # Table row counts
        tables = ['iron_chefs', 'competitors', 'episodes', 'dishes', 'recipes', 'ingredients', 'dish_ingredients']
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[f"{table}_count"] = cursor.fetchone()[0]
            except sqlite3.Error:
                stats[f"{table}_count"] = 0
        
        # Index count
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND sql IS NOT NULL")
        stats['index_count'] = cursor.fetchone()[0]
        
        # Database size
        stats['database_size_bytes'] = Path(self.db_path).stat().st_size
        stats['database_size_mb'] = stats['database_size_bytes'] / (1024 * 1024)
        
        return stats

def migrate_database(db_path: str) -> bool:
    """Main migration function"""
    if not Path(db_path).exists():
        logger.error(f"Database file not found: {db_path}")
        return False
    
    logger.info(f"Starting migration for database: {db_path}")
    
    try:
        with DatabaseMigration(db_path) as migration:
            # Get pre-migration stats
            pre_stats = migration.get_database_stats()
            logger.info(f"Pre-migration stats: {pre_stats}")
            
            # Run migration
            created, total = migration.migrate_indices()
            
            # Analyze database for query optimization
            migration.analyze_database()
            
            # Get post-migration stats
            post_stats = migration.get_database_stats()
            logger.info(f"Post-migration stats: {post_stats}")
            
            logger.info("Migration completed successfully!")
            return True
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    # Default database path
    default_db_path = "iron_chef_japan.db"
    
    # Use command line argument if provided
    db_path = sys.argv[1] if len(sys.argv) > 1 else default_db_path
    
    success = migrate_database(db_path)
    sys.exit(0 if success else 1)