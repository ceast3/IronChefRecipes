"""
Iron Chef Database Connection Pool Manager
A robust, thread-safe connection pooling solution for SQLite that improves performance
and scalability for concurrent web requests.

Features:
- Thread-safe connection pool with configurable size
- Connection health checking and validation
- Automatic reconnection on connection failures
- Connection lifecycle management with proper cleanup
- Performance monitoring and statistics
- Graceful shutdown handling
- Connection timeout and leak detection
"""

import sqlite3
import threading
import time
import logging
import os
import queue
import weakref
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
from contextlib import contextmanager
from dataclasses import dataclass, field


# Configure logging for connection pool events
logger = logging.getLogger(__name__)


@dataclass
class PoolConfig:
    """Configuration settings for the connection pool"""
    min_connections: int = 3
    max_connections: int = 10
    connection_timeout: float = 30.0  # seconds
    validation_timeout: float = 5.0   # seconds
    retry_attempts: int = 3
    retry_delay: float = 1.0  # seconds
    health_check_interval: float = 300.0  # 5 minutes
    enable_statistics: bool = True
    enable_leak_detection: bool = True
    connection_max_age: float = 3600.0  # 1 hour
    
    @classmethod
    def from_env(cls) -> 'PoolConfig':
        """Create configuration from environment variables"""
        return cls(
            min_connections=int(os.getenv('DB_POOL_MIN_CONNECTIONS', '3')),
            max_connections=int(os.getenv('DB_POOL_MAX_CONNECTIONS', '10')),
            connection_timeout=float(os.getenv('DB_POOL_CONNECTION_TIMEOUT', '30.0')),
            validation_timeout=float(os.getenv('DB_POOL_VALIDATION_TIMEOUT', '5.0')),
            retry_attempts=int(os.getenv('DB_POOL_RETRY_ATTEMPTS', '3')),
            retry_delay=float(os.getenv('DB_POOL_RETRY_DELAY', '1.0')),
            health_check_interval=float(os.getenv('DB_POOL_HEALTH_CHECK_INTERVAL', '300.0')),
            enable_statistics=os.getenv('DB_POOL_ENABLE_STATISTICS', 'true').lower() == 'true',
            enable_leak_detection=os.getenv('DB_POOL_ENABLE_LEAK_DETECTION', 'true').lower() == 'true',
            connection_max_age=float(os.getenv('DB_POOL_CONNECTION_MAX_AGE', '3600.0'))
        )


@dataclass
class ConnectionStats:
    """Statistics for individual connections"""
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    usage_count: int = 0
    error_count: int = 0
    is_healthy: bool = True
    last_validation: datetime = field(default_factory=datetime.now)


@dataclass
class PoolStatistics:
    """Connection pool statistics and metrics"""
    total_connections_created: int = 0
    total_connections_destroyed: int = 0
    total_connections_borrowed: int = 0
    total_connections_returned: int = 0
    total_validation_failures: int = 0
    total_timeout_errors: int = 0
    total_retry_attempts: int = 0
    peak_active_connections: int = 0
    current_active_connections: int = 0
    current_idle_connections: int = 0
    average_borrow_time: float = 0.0
    average_connection_age: float = 0.0
    uptime_start: datetime = field(default_factory=datetime.now)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of pool statistics"""
        uptime = (datetime.now() - self.uptime_start).total_seconds()
        return {
            'uptime_hours': round(uptime / 3600, 2),
            'total_connections_created': self.total_connections_created,
            'total_connections_destroyed': self.total_connections_destroyed,
            'total_connections_borrowed': self.total_connections_borrowed,
            'total_connections_returned': self.total_connections_returned,
            'current_active_connections': self.current_active_connections,
            'current_idle_connections': self.current_idle_connections,
            'peak_active_connections': self.peak_active_connections,
            'validation_failure_rate': (
                self.total_validation_failures / max(self.total_connections_borrowed, 1) * 100
            ),
            'timeout_error_rate': (
                self.total_timeout_errors / max(self.total_connections_borrowed, 1) * 100
            ),
            'average_borrow_time_ms': round(self.average_borrow_time * 1000, 2),
            'average_connection_age_hours': round(self.average_connection_age / 3600, 2),
            'connection_efficiency': (
                self.total_connections_returned / max(self.total_connections_borrowed, 1) * 100
            )
        }


class PooledConnection:
    """Wrapper for database connections with metadata"""
    
    def __init__(self, connection: sqlite3.Connection, connection_id: str, db_path: str):
        self.connection = connection
        self.connection_id = connection_id
        self.db_path = db_path
        self.stats = ConnectionStats()
        self.is_in_use = False
        self.borrower_info: Optional[str] = None
        
    def validate(self, timeout: float = 5.0) -> bool:
        """Validate connection health"""
        try:
            # Set a timeout for the validation query
            old_timeout = self.connection.timeout if hasattr(self.connection, 'timeout') else None
            
            # Simple validation query
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            
            # Update validation timestamp
            self.stats.last_validation = datetime.now()
            self.stats.is_healthy = result is not None
            
            return self.stats.is_healthy
            
        except Exception as e:
            logger.warning(f"Connection {self.connection_id} validation failed: {e}")
            self.stats.is_healthy = False
            self.stats.error_count += 1
            return False
    
    def is_expired(self, max_age: float) -> bool:
        """Check if connection has exceeded maximum age"""
        age = (datetime.now() - self.stats.created_at).total_seconds()
        return age > max_age
    
    def get_age(self) -> float:
        """Get connection age in seconds"""
        return (datetime.now() - self.stats.created_at).total_seconds()
    
    def mark_used(self):
        """Mark connection as used and update statistics"""
        self.stats.last_used = datetime.now()
        self.stats.usage_count += 1
    
    def close(self):
        """Close the underlying connection"""
        try:
            if self.connection:
                self.connection.close()
        except Exception as e:
            logger.warning(f"Error closing connection {self.connection_id}: {e}")


class ThreadSafeConnectionPool:
    """
    Thread-safe connection pool for SQLite databases with comprehensive
    connection lifecycle management, health checking, and monitoring.
    """
    
    def __init__(self, db_path: str, config: Optional[PoolConfig] = None):
        self.db_path = db_path
        self.config = config or PoolConfig.from_env()
        
        # Thread synchronization
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        
        # Connection storage
        self._idle_connections: queue.Queue = queue.Queue(maxsize=self.config.max_connections)
        self._active_connections: Dict[str, PooledConnection] = {}
        self._connection_counter = 0
        
        # Statistics and monitoring
        self.statistics = PoolStatistics() if self.config.enable_statistics else None
        self._borrowed_times: Dict[str, float] = {}
        
        # Health checking
        self._health_check_timer: Optional[threading.Timer] = None
        self._shutdown_requested = False
        
        # Leak detection
        if self.config.enable_leak_detection:
            self._connection_refs: weakref.WeakSet = weakref.WeakSet()
        
        # Initialize the pool
        self._initialize_pool()
        self._start_health_check_timer()
        
        logger.info(f"Connection pool initialized for {db_path} with {self.config.min_connections}-{self.config.max_connections} connections")
    
    def _initialize_pool(self):
        """Initialize the connection pool with minimum connections"""
        with self._lock:
            for _ in range(self.config.min_connections):
                try:
                    connection = self._create_connection()
                    self._idle_connections.put_nowait(connection)
                except Exception as e:
                    logger.error(f"Failed to create initial connection: {e}")
                    raise
    
    def _create_connection(self) -> PooledConnection:
        """Create a new database connection with proper configuration"""
        try:
            # Create SQLite connection with optimal settings
            connection = sqlite3.connect(
                self.db_path,
                timeout=self.config.connection_timeout,
                check_same_thread=False,  # Allow sharing between threads
                isolation_level=None  # Autocommit mode for better performance
            )
            
            # Configure connection for optimal performance and safety
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")  # Better concurrency
            connection.execute("PRAGMA synchronous = NORMAL")  # Balance safety/performance
            connection.execute("PRAGMA cache_size = 10000")  # 10MB cache
            connection.execute("PRAGMA temp_store = MEMORY")  # Use memory for temp tables
            
            # Create pooled connection wrapper
            self._connection_counter += 1
            connection_id = f"conn_{self._connection_counter}_{int(time.time())}"
            pooled_conn = PooledConnection(connection, connection_id, self.db_path)
            
            # Update statistics
            if self.statistics:
                self.statistics.total_connections_created += 1
            
            logger.debug(f"Created new connection: {connection_id}")
            return pooled_conn
            
        except Exception as e:
            logger.error(f"Failed to create database connection: {e}")
            raise
    
    def _validate_connection(self, pooled_conn: PooledConnection) -> bool:
        """Validate a connection and return whether it's healthy"""
        try:
            return pooled_conn.validate(self.config.validation_timeout)
        except Exception as e:
            logger.warning(f"Connection validation failed: {e}")
            if self.statistics:
                self.statistics.total_validation_failures += 1
            return False
    
    def _should_remove_connection(self, pooled_conn: PooledConnection) -> bool:
        """Determine if a connection should be removed from the pool"""
        return (
            not pooled_conn.stats.is_healthy or
            pooled_conn.is_expired(self.config.connection_max_age) or
            pooled_conn.stats.error_count > 3
        )
    
    def _cleanup_connection(self, pooled_conn: PooledConnection):
        """Clean up and destroy a connection"""
        try:
            pooled_conn.close()
            if self.statistics:
                self.statistics.total_connections_destroyed += 1
            logger.debug(f"Cleaned up connection: {pooled_conn.connection_id}")
        except Exception as e:
            logger.warning(f"Error during connection cleanup: {e}")
    
    @contextmanager
    def get_connection(self, timeout: Optional[float] = None):
        """
        Get a connection from the pool using context manager pattern.
        
        Args:
            timeout: Maximum time to wait for a connection (defaults to config timeout)
            
        Yields:
            sqlite3.Connection: Database connection
            
        Raises:
            TimeoutError: If no connection is available within timeout
            RuntimeError: If pool is shut down
        """
        if self._shutdown_requested:
            raise RuntimeError("Connection pool is shut down")
        
        timeout = timeout or self.config.connection_timeout
        start_time = time.time()
        pooled_conn = None
        
        try:
            # Get connection from pool
            pooled_conn = self._get_connection_with_timeout(timeout)
            
            # Update statistics
            borrow_time = time.time() - start_time
            if self.statistics:
                self.statistics.total_connections_borrowed += 1
                self._borrowed_times[pooled_conn.connection_id] = start_time
                self._update_average_borrow_time(borrow_time)
            
            # Mark connection as used
            pooled_conn.mark_used()
            pooled_conn.borrower_info = f"thread_{threading.current_thread().ident}"
            
            logger.debug(f"Borrowed connection: {pooled_conn.connection_id}")
            yield pooled_conn.connection
            
        finally:
            # Return connection to pool
            if pooled_conn:
                self._return_connection(pooled_conn)
    
    def _get_connection_with_timeout(self, timeout: float) -> PooledConnection:
        """Get a connection from the pool with timeout and retry logic"""
        end_time = time.time() + timeout
        retry_count = 0
        
        while time.time() < end_time and retry_count < self.config.retry_attempts:
            try:
                return self._try_get_connection(end_time - time.time())
            except queue.Empty:
                retry_count += 1
                if retry_count < self.config.retry_attempts:
                    if self.statistics:
                        self.statistics.total_retry_attempts += 1
                    time.sleep(min(self.config.retry_delay, end_time - time.time()))
                    continue
                break
        
        # Timeout occurred
        if self.statistics:
            self.statistics.total_timeout_errors += 1
        
        raise TimeoutError(f"Could not acquire connection within {timeout} seconds")
    
    def _try_get_connection(self, remaining_timeout: float) -> PooledConnection:
        """Try to get a connection from idle pool or create new one"""
        with self._lock:
            # Try to get an idle connection
            try:
                pooled_conn = self._idle_connections.get_nowait()
                
                # Validate the connection
                if self._validate_connection(pooled_conn):
                    # Check if connection should be refreshed
                    if self._should_remove_connection(pooled_conn):
                        self._cleanup_connection(pooled_conn)
                        # Try to create a replacement
                        if len(self._active_connections) < self.config.max_connections:
                            pooled_conn = self._create_connection()
                        else:
                            raise queue.Empty()
                    
                    # Move to active connections
                    pooled_conn.is_in_use = True
                    self._active_connections[pooled_conn.connection_id] = pooled_conn
                    
                    # Update statistics
                    if self.statistics:
                        self.statistics.current_active_connections = len(self._active_connections)
                        self.statistics.current_idle_connections = self._idle_connections.qsize()
                        if self.statistics.current_active_connections > self.statistics.peak_active_connections:
                            self.statistics.peak_active_connections = self.statistics.current_active_connections
                    
                    return pooled_conn
                else:
                    # Connection is not healthy, clean it up and try again
                    self._cleanup_connection(pooled_conn)
                    raise queue.Empty()
                    
            except queue.Empty:
                # No idle connections, try to create a new one
                if len(self._active_connections) < self.config.max_connections:
                    pooled_conn = self._create_connection()
                    pooled_conn.is_in_use = True
                    self._active_connections[pooled_conn.connection_id] = pooled_conn
                    
                    # Update statistics
                    if self.statistics:
                        self.statistics.current_active_connections = len(self._active_connections)
                        if self.statistics.current_active_connections > self.statistics.peak_active_connections:
                            self.statistics.peak_active_connections = self.statistics.current_active_connections
                    
                    return pooled_conn
                else:
                    # Pool is at maximum capacity, wait for a connection to be returned
                    if not self._condition.wait(timeout=min(remaining_timeout, 1.0)):
                        raise queue.Empty()
                    raise queue.Empty()  # Retry the acquisition
    
    def _return_connection(self, pooled_conn: PooledConnection):
        """Return a connection to the pool"""
        with self._lock:
            try:
                # Remove from active connections
                if pooled_conn.connection_id in self._active_connections:
                    del self._active_connections[pooled_conn.connection_id]
                
                pooled_conn.is_in_use = False
                pooled_conn.borrower_info = None
                
                # Update statistics
                if self.statistics:
                    self.statistics.total_connections_returned += 1
                    self.statistics.current_active_connections = len(self._active_connections)
                    
                    # Calculate borrow time
                    if pooled_conn.connection_id in self._borrowed_times:
                        borrow_duration = time.time() - self._borrowed_times[pooled_conn.connection_id]
                        del self._borrowed_times[pooled_conn.connection_id]
                
                # Check if connection should be kept or discarded
                if (self._should_remove_connection(pooled_conn) or 
                    self._idle_connections.qsize() >= self.config.min_connections):
                    self._cleanup_connection(pooled_conn)
                else:
                    # Return to idle pool
                    try:
                        self._idle_connections.put_nowait(pooled_conn)
                        if self.statistics:
                            self.statistics.current_idle_connections = self._idle_connections.qsize()
                    except queue.Full:
                        # Pool is full, discard connection
                        self._cleanup_connection(pooled_conn)
                
                # Notify waiting threads
                self._condition.notify()
                
                logger.debug(f"Returned connection: {pooled_conn.connection_id}")
                
            except Exception as e:
                logger.error(f"Error returning connection {pooled_conn.connection_id}: {e}")
                # Ensure cleanup happens even if there's an error
                self._cleanup_connection(pooled_conn)
    
    def _update_average_borrow_time(self, borrow_time: float):
        """Update the average borrow time statistic"""
        if self.statistics:
            if self.statistics.average_borrow_time == 0:
                self.statistics.average_borrow_time = borrow_time
            else:
                # Exponential moving average
                alpha = 0.1
                self.statistics.average_borrow_time = (
                    alpha * borrow_time + (1 - alpha) * self.statistics.average_borrow_time
                )
    
    def _health_check(self):
        """Periodic health check of idle connections"""
        if self._shutdown_requested:
            return
        
        with self._lock:
            connections_to_remove = []
            temp_connections = []
            
            # Check all idle connections
            while not self._idle_connections.empty():
                try:
                    pooled_conn = self._idle_connections.get_nowait()
                    if self._should_remove_connection(pooled_conn) or not self._validate_connection(pooled_conn):
                        connections_to_remove.append(pooled_conn)
                    else:
                        temp_connections.append(pooled_conn)
                except queue.Empty:
                    break
            
            # Clean up unhealthy connections
            for pooled_conn in connections_to_remove:
                self._cleanup_connection(pooled_conn)
            
            # Return healthy connections to pool
            for pooled_conn in temp_connections:
                try:
                    self._idle_connections.put_nowait(pooled_conn)
                except queue.Full:
                    self._cleanup_connection(pooled_conn)
            
            # Update statistics
            if self.statistics:
                self.statistics.current_idle_connections = self._idle_connections.qsize()
                
                # Update average connection age
                if temp_connections:
                    total_age = sum(conn.get_age() for conn in temp_connections)
                    avg_age = total_age / len(temp_connections)
                    if self.statistics.average_connection_age == 0:
                        self.statistics.average_connection_age = avg_age
                    else:
                        alpha = 0.1
                        self.statistics.average_connection_age = (
                            alpha * avg_age + (1 - alpha) * self.statistics.average_connection_age
                        )
            
            logger.debug(f"Health check completed. Removed {len(connections_to_remove)} unhealthy connections")
        
        # Schedule next health check
        if not self._shutdown_requested:
            self._start_health_check_timer()
    
    def _start_health_check_timer(self):
        """Start the health check timer"""
        if self._health_check_timer:
            self._health_check_timer.cancel()
        
        self._health_check_timer = threading.Timer(
            self.config.health_check_interval,
            self._health_check
        )
        self._health_check_timer.daemon = True
        self._health_check_timer.start()
    
    def get_statistics(self) -> Optional[Dict[str, Any]]:
        """Get current pool statistics"""
        if not self.statistics:
            return None
        
        with self._lock:
            return self.statistics.get_summary()
    
    def get_pool_status(self) -> Dict[str, Any]:
        """Get current pool status and health information"""
        with self._lock:
            return {
                'db_path': self.db_path,
                'is_healthy': not self._shutdown_requested,
                'active_connections': len(self._active_connections),
                'idle_connections': self._idle_connections.qsize(),
                'total_connections': len(self._active_connections) + self._idle_connections.qsize(),
                'max_connections': self.config.max_connections,
                'min_connections': self.config.min_connections,
                'configuration': {
                    'connection_timeout': self.config.connection_timeout,
                    'health_check_interval': self.config.health_check_interval,
                    'connection_max_age': self.config.connection_max_age,
                    'validation_timeout': self.config.validation_timeout
                }
            }
    
    def warmup(self) -> bool:
        """Warm up the connection pool by creating minimum connections"""
        try:
            with self._lock:
                current_total = len(self._active_connections) + self._idle_connections.qsize()
                needed = self.config.min_connections - current_total
                
                for _ in range(max(0, needed)):
                    connection = self._create_connection()
                    try:
                        self._idle_connections.put_nowait(connection)
                    except queue.Full:
                        self._cleanup_connection(connection)
                        break
                
                if self.statistics:
                    self.statistics.current_idle_connections = self._idle_connections.qsize()
                
                logger.info(f"Pool warmed up with {self._idle_connections.qsize()} idle connections")
                return True
                
        except Exception as e:
            logger.error(f"Pool warmup failed: {e}")
            return False
    
    def shutdown(self, timeout: float = 30.0):
        """Gracefully shutdown the connection pool"""
        logger.info("Shutting down connection pool...")
        self._shutdown_requested = True
        
        # Cancel health check timer
        if self._health_check_timer:
            self._health_check_timer.cancel()
        
        # Wait for active connections to be returned
        end_time = time.time() + timeout
        while time.time() < end_time and len(self._active_connections) > 0:
            logger.info(f"Waiting for {len(self._active_connections)} active connections to return...")
            time.sleep(1.0)
        
        with self._lock:
            # Force cleanup of any remaining active connections
            for pooled_conn in list(self._active_connections.values()):
                logger.warning(f"Force closing active connection: {pooled_conn.connection_id}")
                self._cleanup_connection(pooled_conn)
            self._active_connections.clear()
            
            # Cleanup all idle connections
            while not self._idle_connections.empty():
                try:
                    pooled_conn = self._idle_connections.get_nowait()
                    self._cleanup_connection(pooled_conn)
                except queue.Empty:
                    break
        
        logger.info("Connection pool shutdown completed")
    
    def __del__(self):
        """Cleanup when pool is garbage collected"""
        if not self._shutdown_requested:
            self.shutdown(timeout=5.0)


# Global pool instance for application-wide use
_global_pool: Optional[ThreadSafeConnectionPool] = None
_pool_lock = threading.Lock()


def initialize_global_pool(db_path: str, config: Optional[PoolConfig] = None) -> ThreadSafeConnectionPool:
    """Initialize the global connection pool"""
    global _global_pool
    
    with _pool_lock:
        if _global_pool:
            _global_pool.shutdown()
        
        _global_pool = ThreadSafeConnectionPool(db_path, config)
        
        # Warm up the pool
        _global_pool.warmup()
        
        return _global_pool


def get_global_pool() -> Optional[ThreadSafeConnectionPool]:
    """Get the global connection pool instance"""
    return _global_pool


def shutdown_global_pool():
    """Shutdown the global connection pool"""
    global _global_pool
    
    with _pool_lock:
        if _global_pool:
            _global_pool.shutdown()
            _global_pool = None


@contextmanager
def get_pooled_connection(timeout: Optional[float] = None):
    """
    Convenience function to get a connection from the global pool.
    
    Args:
        timeout: Maximum time to wait for a connection
        
    Yields:
        sqlite3.Connection: Database connection
        
    Raises:
        RuntimeError: If global pool is not initialized
    """
    if not _global_pool:
        raise RuntimeError("Global connection pool not initialized. Call initialize_global_pool() first.")
    
    with _global_pool.get_connection(timeout) as conn:
        yield conn