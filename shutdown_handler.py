"""
Graceful Shutdown and Cleanup Handler
Provides comprehensive shutdown management for the Iron Chef application
with proper resource cleanup, connection pool shutdown, and monitoring termination.

Features:
- Graceful connection pool shutdown
- Monitoring system cleanup
- Resource leak prevention
- Configurable shutdown timeouts
- Signal handling
- Health check during shutdown
- Cleanup verification
"""

import signal
import threading
import time
import logging
import atexit
from typing import List, Callable, Optional, Dict, Any
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


class ShutdownHandler:
    """
    Comprehensive shutdown handler for the Iron Chef application.
    Manages graceful shutdown of all components with proper resource cleanup.
    """
    
    def __init__(self, shutdown_timeout: float = 30.0):
        """
        Initialize shutdown handler.
        
        Args:
            shutdown_timeout: Maximum time to wait for graceful shutdown
        """
        self.shutdown_timeout = shutdown_timeout
        self.shutdown_started = False
        self.shutdown_complete = False
        self.cleanup_functions: List[Callable] = []
        self._lock = threading.Lock()
        self.start_time: Optional[datetime] = None
        
        # Register built-in cleanup functions
        self._register_builtin_cleanup()
        
        # Register signal handlers
        self._register_signal_handlers()
        
        # Register atexit handler as fallback
        atexit.register(self._emergency_cleanup)
    
    def _register_builtin_cleanup(self):
        """Register built-in cleanup functions"""
        
        def cleanup_connection_pool():
            """Cleanup connection pools"""
            try:
                from iron_chef_database_pooled import IronChefDatabasePooled
                from connection_pool import shutdown_global_pool
                
                logger.info("Shutting down database connection pools...")
                
                # Shutdown class-level pool
                IronChefDatabasePooled.shutdown_pool()
                logger.info("Database class pool shut down")
                
                # Shutdown global pool
                shutdown_global_pool()
                logger.info("Global connection pool shut down")
                
            except Exception as e:
                logger.error(f"Error shutting down connection pools: {e}")
        
        def cleanup_monitoring():
            """Cleanup monitoring systems"""
            try:
                from pool_monitor import shutdown_global_monitor
                
                logger.info("Shutting down monitoring systems...")
                shutdown_global_monitor()
                logger.info("Pool monitoring shut down")
                
            except Exception as e:
                logger.error(f"Error shutting down monitoring: {e}")
        
        def cleanup_background_threads():
            """Cleanup any remaining background threads"""
            try:
                logger.info("Checking for active background threads...")
                
                active_threads = [t for t in threading.enumerate() if t != threading.current_thread()]
                daemon_threads = [t for t in active_threads if t.daemon]
                non_daemon_threads = [t for t in active_threads if not t.daemon]
                
                if non_daemon_threads:
                    logger.warning(f"Found {len(non_daemon_threads)} non-daemon threads still running")
                    for thread in non_daemon_threads:
                        if hasattr(thread, 'stop'):
                            logger.info(f"Stopping thread: {thread.name}")
                            thread.stop()
                
                if daemon_threads:
                    logger.info(f"Found {len(daemon_threads)} daemon threads (will terminate automatically)")
                
            except Exception as e:
                logger.error(f"Error cleaning up background threads: {e}")
        
        def cleanup_temp_files():
            """Cleanup temporary files"""
            try:
                import tempfile
                import os
                import glob
                
                logger.info("Cleaning up temporary files...")
                
                # Clean up any temp files in the temp directory
                temp_dir = tempfile.gettempdir()
                iron_chef_temp_files = glob.glob(os.path.join(temp_dir, "*iron_chef*"))
                
                for temp_file in iron_chef_temp_files:
                    try:
                        os.unlink(temp_file)
                        logger.debug(f"Removed temp file: {temp_file}")
                    except OSError:
                        pass  # File may have been already removed
                
                if iron_chef_temp_files:
                    logger.info(f"Cleaned up {len(iron_chef_temp_files)} temporary files")
                
            except Exception as e:
                logger.error(f"Error cleaning up temporary files: {e}")
        
        # Register cleanup functions in reverse order of importance
        # (most important cleanup happens last)
        self.cleanup_functions.extend([
            cleanup_temp_files,
            cleanup_background_threads,
            cleanup_monitoring,
            cleanup_connection_pool
        ])
    
    def register_cleanup(self, cleanup_func: Callable, name: Optional[str] = None):
        """
        Register a custom cleanup function.
        
        Args:
            cleanup_func: Function to call during shutdown
            name: Optional name for the cleanup function
        """
        with self._lock:
            if name:
                cleanup_func.__name__ = name
            self.cleanup_functions.append(cleanup_func)
            logger.debug(f"Registered cleanup function: {getattr(cleanup_func, '__name__', 'unnamed')}")
    
    def _register_signal_handlers(self):
        """Register signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            logger.info(f"Received {signal_name} signal, initiating graceful shutdown...")
            self.shutdown()
        
        # Register handlers for common shutdown signals
        for sig in [signal.SIGINT, signal.SIGTERM]:
            try:
                signal.signal(sig, signal_handler)
            except (ValueError, OSError) as e:
                logger.warning(f"Could not register handler for signal {sig}: {e}")
    
    def shutdown(self, timeout: Optional[float] = None) -> bool:
        """
        Perform graceful shutdown of all components.
        
        Args:
            timeout: Maximum time to wait for shutdown (uses default if None)
            
        Returns:
            bool: True if shutdown completed successfully, False if timeout
        """
        with self._lock:
            if self.shutdown_started:
                logger.warning("Shutdown already in progress")
                return self.shutdown_complete
            
            self.shutdown_started = True
            self.start_time = datetime.now()
        
        timeout = timeout or self.shutdown_timeout
        logger.info(f"Starting graceful shutdown (timeout: {timeout}s)")
        
        success = True
        
        try:
            # Run cleanup functions in reverse order (LIFO)
            for cleanup_func in reversed(self.cleanup_functions):
                func_name = getattr(cleanup_func, '__name__', 'unnamed')
                
                try:
                    logger.info(f"Running cleanup: {func_name}")
                    start_time = time.time()
                    
                    cleanup_func()
                    
                    elapsed = time.time() - start_time
                    logger.info(f"Cleanup '{func_name}' completed in {elapsed:.2f}s")
                    
                except Exception as e:
                    logger.error(f"Error in cleanup function '{func_name}': {e}")
                    success = False
                
                # Check if we're running out of time
                if self.start_time:
                    elapsed_total = (datetime.now() - self.start_time).total_seconds()
                    if elapsed_total > timeout:
                        logger.warning(f"Shutdown timeout exceeded ({timeout}s), stopping cleanup")
                        success = False
                        break
            
            # Final verification
            self._verify_cleanup()
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            success = False
        
        finally:
            with self._lock:
                self.shutdown_complete = True
            
            total_time = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
            
            if success:
                logger.info(f"Graceful shutdown completed successfully in {total_time:.2f}s")
            else:
                logger.warning(f"Shutdown completed with errors in {total_time:.2f}s")
        
        return success
    
    def _verify_cleanup(self):
        """Verify that cleanup was successful"""
        try:
            # Check for active non-daemon threads
            active_threads = [t for t in threading.enumerate() 
                            if t != threading.current_thread() and not t.daemon]
            
            if active_threads:
                logger.warning(f"Found {len(active_threads)} active threads after cleanup:")
                for thread in active_threads:
                    logger.warning(f"  - {thread.name} (alive: {thread.is_alive()})")
            
            # Check pool status if available
            try:
                from iron_chef_database_pooled import IronChefDatabasePooled
                status = IronChefDatabasePooled.get_pool_status()
                if status and status.get('is_healthy', False):
                    logger.warning("Database pool still reports as healthy after shutdown")
            except:
                pass  # Pool may be already shut down
            
            logger.info("Cleanup verification completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup verification: {e}")
    
    def _emergency_cleanup(self):
        """Emergency cleanup function called by atexit"""
        if not self.shutdown_complete:
            logger.warning("Emergency cleanup triggered (process terminating)")
            
            try:
                # Quick cleanup of critical resources
                from iron_chef_database_pooled import IronChefDatabasePooled
                from connection_pool import shutdown_global_pool
                from pool_monitor import shutdown_global_monitor
                
                IronChefDatabasePooled.shutdown_pool()
                shutdown_global_pool()
                shutdown_global_monitor()
                
                logger.info("Emergency cleanup completed")
                
            except Exception as e:
                logger.error(f"Error during emergency cleanup: {e}")
    
    def get_shutdown_status(self) -> Dict[str, Any]:
        """Get current shutdown status"""
        with self._lock:
            return {
                'shutdown_started': self.shutdown_started,
                'shutdown_complete': self.shutdown_complete,
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'elapsed_time': (datetime.now() - self.start_time).total_seconds() if self.start_time else None,
                'cleanup_functions_registered': len(self.cleanup_functions),
                'timeout': self.shutdown_timeout
            }
    
    def force_shutdown(self):
        """Force immediate shutdown without waiting"""
        logger.warning("Force shutdown requested - terminating immediately")
        
        try:
            self._emergency_cleanup()
        except Exception as e:
            logger.error(f"Error during force shutdown: {e}")
        
        import os
        os._exit(1)


# Global shutdown handler instance
_shutdown_handler: Optional[ShutdownHandler] = None


def initialize_shutdown_handler(timeout: float = 30.0) -> ShutdownHandler:
    """Initialize the global shutdown handler"""
    global _shutdown_handler
    
    if _shutdown_handler is None:
        _shutdown_handler = ShutdownHandler(timeout)
        logger.info(f"Shutdown handler initialized with {timeout}s timeout")
    
    return _shutdown_handler


def get_shutdown_handler() -> Optional[ShutdownHandler]:
    """Get the global shutdown handler"""
    return _shutdown_handler


def register_cleanup_function(cleanup_func: Callable, name: Optional[str] = None):
    """Register a cleanup function with the global shutdown handler"""
    handler = get_shutdown_handler()
    if handler:
        handler.register_cleanup(cleanup_func, name)
    else:
        logger.warning("No shutdown handler available to register cleanup function")


def graceful_shutdown(timeout: Optional[float] = None) -> bool:
    """Perform graceful shutdown using the global handler"""
    handler = get_shutdown_handler()
    if handler:
        return handler.shutdown(timeout)
    else:
        logger.error("No shutdown handler available for graceful shutdown")
        return False


def force_shutdown():
    """Force immediate shutdown using the global handler"""
    handler = get_shutdown_handler()
    if handler:
        handler.force_shutdown()
    else:
        logger.error("No shutdown handler available for force shutdown")
        import os
        os._exit(1)


class ShutdownContext:
    """Context manager for ensuring cleanup on exit"""
    
    def __init__(self, cleanup_func: Callable, name: Optional[str] = None):
        self.cleanup_func = cleanup_func
        self.name = name
    
    def __enter__(self):
        register_cleanup_function(self.cleanup_func, self.name)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Cleanup is handled by the shutdown handler
        pass


# Flask integration helper
def setup_flask_shutdown(app, timeout: float = 30.0):
    """
    Setup graceful shutdown for Flask application.
    
    Args:
        app: Flask application instance
        timeout: Shutdown timeout in seconds
    """
    # Initialize shutdown handler
    handler = initialize_shutdown_handler(timeout)
    
    # Add Flask-specific cleanup
    def flask_cleanup():
        """Flask-specific cleanup"""
        try:
            logger.info("Performing Flask application cleanup...")
            
            # Any Flask-specific cleanup can go here
            # For example, closing background tasks, cleaning up extensions, etc.
            
            logger.info("Flask cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during Flask cleanup: {e}")
    
    handler.register_cleanup(flask_cleanup, "flask_cleanup")
    
    # Add shutdown endpoint for graceful shutdown via HTTP
    @app.route('/admin/shutdown', methods=['POST'])
    def shutdown_endpoint():
        """Administrative endpoint for graceful shutdown"""
        try:
            # In production, this should be protected by authentication
            logger.info("Shutdown requested via HTTP endpoint")
            
            # Start shutdown in background thread
            def background_shutdown():
                time.sleep(0.1)  # Brief delay to allow response to be sent
                handler.shutdown()
            
            threading.Thread(target=background_shutdown, daemon=True).start()
            
            return {'message': 'Graceful shutdown initiated', 'status': 'success'}, 200
            
        except Exception as e:
            logger.error(f"Error initiating shutdown via endpoint: {e}")
            return {'message': 'Shutdown failed', 'error': str(e)}, 500
    
    # Add status endpoint
    @app.route('/admin/shutdown/status')
    def shutdown_status():
        """Get shutdown status"""
        return handler.get_shutdown_status()
    
    logger.info("Flask shutdown handlers configured")
    return handler