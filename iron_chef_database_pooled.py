"""
Iron Chef Database with Connection Pooling Support
A backward-compatible extension of the secure database class that integrates
with the ThreadSafeConnectionPool for improved performance and scalability.

This module provides:
- Drop-in replacement for IronChefDatabaseSecure
- Connection pooling for better concurrent performance
- Backward compatibility with existing API
- Enhanced monitoring and statistics
- Graceful fallback to direct connections if pool unavailable
"""

import sqlite3
import json
import re
import os
import logging
import threading
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any, Union
from contextlib import contextmanager

from iron_chef_database_secure import IronChefDatabaseSecure, SecurityValidator
from connection_pool import ThreadSafeConnectionPool, PoolConfig, get_global_pool, initialize_global_pool


logger = logging.getLogger(__name__)


class IronChefDatabasePooled(IronChefDatabaseSecure):
    """
    Enhanced Iron Chef database class with connection pooling support.
    
    This class extends IronChefDatabaseSecure to add connection pooling capabilities
    while maintaining full backward compatibility. It can operate in two modes:
    
    1. Pooled mode (default): Uses connection pool for better performance
    2. Legacy mode: Falls back to direct connections like the original class
    
    Features:
    - Thread-safe connection pooling
    - Automatic pool initialization and management
    - Backward compatible API
    - Enhanced error handling and retry logic
    - Connection pool statistics and monitoring
    - Graceful degradation to direct connections
    """
    
    # Class-level pool management
    _class_pool: Optional[ThreadSafeConnectionPool] = None
    _pool_lock = threading.Lock()
    _pool_initialized = False
    
    def __init__(self, db_path: str = "iron_chef_japan.db", 
                 use_pooling: bool = True,
                 pool_config: Optional[PoolConfig] = None,
                 fallback_to_direct: bool = True):
        """
        Initialize the database connection with optional pooling.
        
        Args:
            db_path: Path to the SQLite database file
            use_pooling: Whether to use connection pooling (default: True)
            pool_config: Optional pool configuration (uses defaults if None)
            fallback_to_direct: Whether to fallback to direct connections on pool errors
        """
        # Initialize parent class
        super().__init__(db_path)
        
        self.use_pooling = use_pooling
        self.pool_config = pool_config or PoolConfig.from_env()
        self.fallback_to_direct = fallback_to_direct
        self._pooled_connection = None
        self._direct_connection_active = False
        
        # Initialize class-level pool if needed
        if self.use_pooling:
            self._ensure_pool_initialized()
    
    @classmethod
    def _ensure_pool_initialized(cls):
        """Ensure the class-level connection pool is initialized"""
        with cls._pool_lock:
            if not cls._pool_initialized:
                try:
                    # Use global pool if available, otherwise create class pool
                    global_pool = get_global_pool()
                    if global_pool:
                        cls._class_pool = global_pool
                        logger.info("Using existing global connection pool")
                    else:
                        # Create a new pool for this class
                        db_path = "iron_chef_japan.db"  # Default path
                        config = PoolConfig.from_env()
                        cls._class_pool = ThreadSafeConnectionPool(db_path, config)
                        logger.info(f"Created new connection pool for {db_path}")
                    
                    cls._pool_initialized = True
                    
                except Exception as e:
                    logger.error(f"Failed to initialize connection pool: {e}")
                    cls._class_pool = None
                    cls._pool_initialized = False
                    raise
    
    @classmethod
    def initialize_pool(cls, db_path: str = "iron_chef_japan.db", 
                       config: Optional[PoolConfig] = None) -> bool:
        """
        Explicitly initialize the connection pool for the class.
        
        Args:
            db_path: Path to the database file
            config: Optional pool configuration
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with cls._pool_lock:
                if cls._class_pool:
                    cls._class_pool.shutdown()
                
                cls._class_pool = ThreadSafeConnectionPool(db_path, config or PoolConfig.from_env())
                cls._pool_initialized = True
                
                # Warm up the pool
                cls._class_pool.warmup()
                
                logger.info(f"Connection pool initialized successfully for {db_path}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            cls._class_pool = None
            cls._pool_initialized = False
            return False
    
    @classmethod
    def shutdown_pool(cls):
        """Shutdown the class-level connection pool"""
        with cls._pool_lock:
            if cls._class_pool:
                cls._class_pool.shutdown()
                cls._class_pool = None
                cls._pool_initialized = False
                logger.info("Connection pool shut down")
    
    @classmethod
    def get_pool_statistics(cls) -> Optional[Dict[str, Any]]:
        """Get connection pool statistics"""
        if cls._class_pool:
            return cls._class_pool.get_statistics()
        return None
    
    @classmethod
    def get_pool_status(cls) -> Optional[Dict[str, Any]]:
        """Get connection pool status"""
        if cls._class_pool:
            return cls._class_pool.get_pool_status()
        return None
    
    def __enter__(self):
        """Context manager entry - acquire connection"""
        if self.use_pooling and self._class_pool:
            try:
                # Try to get connection from pool
                self._pooled_connection = self._class_pool.get_connection()
                self.connection = self._pooled_connection.__enter__()
                self.connection.row_factory = sqlite3.Row
                self.cursor = self.connection.cursor()
                self._direct_connection_active = False
                logger.debug("Acquired pooled database connection")
                return self
                
            except Exception as e:
                logger.warning(f"Failed to acquire pooled connection: {e}")
                if self.fallback_to_direct:
                    logger.info("Falling back to direct connection")
                    return self._enter_direct_connection()
                else:
                    raise
        else:
            # Use direct connection (original behavior)
            return self._enter_direct_connection()
    
    def _enter_direct_connection(self):
        """Enter with a direct (non-pooled) connection"""
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.connection.cursor()
        self._direct_connection_active = True
        logger.debug("Acquired direct database connection")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - release connection"""
        try:
            if self._pooled_connection and not self._direct_connection_active:
                # Return pooled connection
                self._pooled_connection.__exit__(exc_type, exc_val, exc_tb)
                self._pooled_connection = None
                logger.debug("Released pooled database connection")
            elif self.connection and self._direct_connection_active:
                # Handle direct connection
                if exc_type is None:
                    self.connection.commit()
                else:
                    self.connection.rollback()
                self.connection.close()
                logger.debug("Closed direct database connection")
        except Exception as e:
            logger.error(f"Error releasing database connection: {e}")
        finally:
            self.connection = None
            self.cursor = None
            self._direct_connection_active = False
    
    def execute_with_retry(self, query: str, params: Optional[Tuple] = None, 
                          max_retries: int = 3) -> Any:
        """
        Execute a query with automatic retry on connection errors.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            max_retries: Maximum number of retry attempts
            
        Returns:
            Query result
            
        Raises:
            sqlite3.Error: If query fails after all retries
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                if params:
                    return self.cursor.execute(query, params)
                else:
                    return self.cursor.execute(query)
                    
            except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                last_error = e
                logger.warning(f"Query execution failed (attempt {attempt + 1}): {e}")
                
                if attempt < max_retries:
                    # Try to refresh the connection
                    if self.use_pooling and self._class_pool and not self._direct_connection_active:
                        try:
                            # Return current connection and get a new one
                            if self._pooled_connection:
                                self._pooled_connection.__exit__(None, None, None)
                            
                            self._pooled_connection = self._class_pool.get_connection()
                            self.connection = self._pooled_connection.__enter__()
                            self.connection.row_factory = sqlite3.Row
                            self.cursor = self.connection.cursor()
                            
                        except Exception as pool_error:
                            logger.warning(f"Failed to refresh pooled connection: {pool_error}")
                            if self.fallback_to_direct:
                                # Switch to direct connection
                                self._switch_to_direct_connection()
                else:
                    # All retries exhausted
                    raise last_error
        
        raise last_error
    
    def _switch_to_direct_connection(self):
        """Switch from pooled to direct connection"""
        try:
            if self._pooled_connection:
                self._pooled_connection.__exit__(None, None, None)
                self._pooled_connection = None
            
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys = ON")
            self.cursor = self.connection.cursor()
            self._direct_connection_active = True
            
            logger.info("Switched to direct connection due to pool issues")
            
        except Exception as e:
            logger.error(f"Failed to switch to direct connection: {e}")
            raise
    
    def batch_execute(self, operations: List[Tuple[str, Optional[Tuple]]], 
                     transaction: bool = True) -> List[Any]:
        """
        Execute multiple operations efficiently.
        
        Args:
            operations: List of (query, params) tuples
            transaction: Whether to wrap operations in a transaction
            
        Returns:
            List of results from each operation
        """
        results = []
        
        try:
            if transaction:
                self.cursor.execute("BEGIN")
            
            for query, params in operations:
                result = self.execute_with_retry(query, params, max_retries=1)
                results.append(result)
            
            if transaction:
                self.connection.commit()
                
        except Exception as e:
            if transaction:
                try:
                    self.connection.rollback()
                except:
                    pass
            logger.error(f"Batch execution failed: {e}")
            raise
        
        return results
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get information about the current connection"""
        return {
            'is_pooled': not self._direct_connection_active,
            'use_pooling': self.use_pooling,
            'db_path': self.db_path,
            'connection_active': self.connection is not None,
            'pool_available': self._class_pool is not None,
            'pool_statistics': self.get_pool_statistics() if self._class_pool else None
        }
    
    # Enhanced versions of parent methods with retry logic
    
    def add_episode(self, episode_number: int, theme: str, iron_chef_id: int, 
                   competitor_id: int, air_date: str = None, winner: str = None, 
                   judges_scores: str = None) -> int:
        """Add a new episode with retry logic"""
        # Validate inputs using parent method
        episode_number = self.validator.validate_integer(
            episode_number, min_val=1, max_val=999999, field_name="episode number"
        )
        theme = self.validator.validate_string(theme, max_length=100, field_name="theme")
        if not theme:
            raise ValueError("Theme is required")
        
        iron_chef_id = self.validator.validate_integer(
            iron_chef_id, min_val=1, field_name="iron chef ID"
        )
        competitor_id = self.validator.validate_integer(
            competitor_id, min_val=1, field_name="competitor ID"
        )
        
        if winner:
            winner = self.validator.validate_string(winner, max_length=20, field_name="winner")
            if winner not in ['Iron Chef', 'Competitor', 'Draw']:
                raise ValueError("Winner must be 'Iron Chef', 'Competitor', or 'Draw'")
        
        if air_date:
            air_date = self.validator.validate_string(
                air_date, max_length=10, 
                pattern=r'^\d{4}-\d{2}-\d{2}$', 
                field_name="air date"
            )
        
        judges_scores = self.validator.validate_string(
            judges_scores, max_length=100, field_name="judges scores"
        )
        
        query = """INSERT INTO episodes (episode_number, air_date, theme, iron_chef_id, 
                   competitor_id, winner, judges_scores) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)"""
        
        self.execute_with_retry(query, (episode_number, air_date, theme, iron_chef_id, 
                                       competitor_id, winner, judges_scores))
        return self.cursor.lastrowid
    
    def get_episode_details(self, episode_id: int) -> Dict:
        """Get episode details with retry logic"""
        episode_id = self.validator.validate_integer(episode_id, min_val=1, field_name="episode ID")
        
        # Get episode info
        query = """SELECT e.*, ic.name as iron_chef_name, c.name as competitor_name
                   FROM episodes e
                   JOIN iron_chefs ic ON e.iron_chef_id = ic.id
                   JOIN competitors c ON e.competitor_id = c.id
                   WHERE e.id = ?"""
        
        self.execute_with_retry(query, (episode_id,))
        result = self.cursor.fetchone()
        
        if not result:
            return None
        
        episode = dict(result)
        
        # Get dishes
        query = """SELECT * FROM dishes WHERE episode_id = ? ORDER BY chef_type, dish_number"""
        self.execute_with_retry(query, (episode_id,))
        dishes = [dict(row) for row in self.cursor.fetchall()]
        
        episode['dishes'] = {
            'iron_chef': [d for d in dishes if d['chef_type'] == 'iron_chef'],
            'competitor': [d for d in dishes if d['chef_type'] == 'competitor']
        }
        
        return episode
    
    def search_episodes_by_theme(self, theme: str) -> List[Dict]:
        """Search episodes by theme with retry logic"""
        if theme:
            theme = self.validator.validate_string(theme, max_length=100, field_name="theme")
        
        query = """SELECT e.*, ic.name as iron_chef_name, c.name as competitor_name
                   FROM episodes e
                   JOIN iron_chefs ic ON e.iron_chef_id = ic.id
                   JOIN competitors c ON e.competitor_id = c.id
                   WHERE e.theme LIKE ? ESCAPE '\\'"""
        
        search_pattern = self.validator.sanitize_sql_pattern(theme) if theme else '%'
        
        self.execute_with_retry(query, (search_pattern,))
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_all_themes(self) -> List[str]:
        """Get all themes with retry logic"""
        self.execute_with_retry("SELECT DISTINCT theme FROM episodes ORDER BY theme")
        return [row[0] for row in self.cursor.fetchall()]


# Convenience functions for easy migration

def create_pooled_database(db_path: str = "iron_chef_japan.db", 
                          pool_config: Optional[PoolConfig] = None) -> IronChefDatabasePooled:
    """
    Create a new pooled database instance with automatic pool initialization.
    
    Args:
        db_path: Path to the database file
        pool_config: Optional pool configuration
        
    Returns:
        IronChefDatabasePooled: Configured database instance
    """
    # Initialize the pool if not already done
    IronChefDatabasePooled.initialize_pool(db_path, pool_config)
    
    return IronChefDatabasePooled(db_path, use_pooling=True, pool_config=pool_config)


@contextmanager
def get_pooled_database(db_path: str = "iron_chef_japan.db", 
                       pool_config: Optional[PoolConfig] = None):
    """
    Context manager for getting a pooled database connection.
    
    Args:
        db_path: Path to the database file
        pool_config: Optional pool configuration
        
    Yields:
        IronChefDatabasePooled: Database instance with active connection
    """
    db = create_pooled_database(db_path, pool_config)
    with db:
        yield db


# Backward compatibility alias
IronChefDatabaseSecurePooled = IronChefDatabasePooled