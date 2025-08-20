"""
Connection Pool Concurrent Access and Stress Tests
Comprehensive test suite for validating connection pool performance,
thread safety, and scalability under various load conditions.

Test Categories:
- Basic functionality tests
- Thread safety validation
- Concurrent access stress tests
- Connection pool limits and timeouts
- Error handling and recovery
- Performance benchmarks
- Memory leak detection
"""

import pytest
import threading
import time
import random
import sqlite3
import tempfile
import os
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Callable
from unittest.mock import patch, MagicMock

from connection_pool import (
    ThreadSafeConnectionPool, PoolConfig, PooledConnection,
    initialize_global_pool, get_global_pool, shutdown_global_pool
)
from iron_chef_database_pooled import IronChefDatabasePooled, create_pooled_database
from pool_monitor import PoolMonitor, initialize_global_monitor
from pool_config import ConfigManager, EnvironmentType


# Test fixtures and utilities

@pytest.fixture(scope="function")
def temp_db():
    """Create a temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
        db_path = temp_file.name
    
    # Initialize test database with schema
    connection = sqlite3.connect(db_path)
    connection.executescript("""
        CREATE TABLE test_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id TEXT,
            timestamp TEXT,
            data TEXT
        );
        
        CREATE TABLE episodes (
            id INTEGER PRIMARY KEY,
            episode_number INTEGER,
            theme TEXT,
            iron_chef_id INTEGER,
            competitor_id INTEGER,
            winner TEXT
        );
        
        CREATE TABLE iron_chefs (
            id INTEGER PRIMARY KEY,
            name TEXT
        );
        
        CREATE TABLE competitors (
            id INTEGER PRIMARY KEY,
            name TEXT
        );
        
        INSERT INTO iron_chefs (name) VALUES ('Test Iron Chef');
        INSERT INTO competitors (name) VALUES ('Test Competitor');
        INSERT INTO episodes (episode_number, theme, iron_chef_id, competitor_id, winner)
        VALUES (1, 'Test Theme', 1, 1, 'Iron Chef');
    """)
    connection.close()
    
    yield db_path
    
    # Cleanup
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture(scope="function")
def test_pool_config():
    """Create test pool configuration"""
    return PoolConfig(
        min_connections=2,
        max_connections=5,
        connection_timeout=5.0,
        validation_timeout=2.0,
        retry_attempts=2,
        retry_delay=0.1,
        health_check_interval=60.0,  # Longer interval for tests
        enable_statistics=True,
        enable_leak_detection=True,
        connection_max_age=300.0
    )


@pytest.fixture(scope="function")
def connection_pool(temp_db, test_pool_config):
    """Create a connection pool for testing"""
    pool = ThreadSafeConnectionPool(temp_db, test_pool_config)
    yield pool
    pool.shutdown()


class TestBasicFunctionality:
    """Test basic connection pool functionality"""
    
    def test_pool_initialization(self, temp_db, test_pool_config):
        """Test pool initialization with proper configuration"""
        pool = ThreadSafeConnectionPool(temp_db, test_pool_config)
        
        assert pool.db_path == temp_db
        assert pool.config == test_pool_config
        
        status = pool.get_pool_status()
        assert status['db_path'] == temp_db
        assert status['is_healthy'] is True
        assert status['idle_connections'] >= test_pool_config.min_connections
        
        pool.shutdown()
    
    def test_connection_acquisition(self, connection_pool):
        """Test basic connection acquisition and release"""
        with connection_pool.get_connection() as conn:
            assert conn is not None
            assert isinstance(conn, sqlite3.Connection)
            
            # Test connection functionality
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1
    
    def test_connection_validation(self, connection_pool):
        """Test connection validation"""
        with connection_pool.get_connection() as conn:
            # Connection should be valid
            cursor = conn.cursor()
            cursor.execute("SELECT sqlite_version()")
            version = cursor.fetchone()
            assert version is not None
    
    def test_pool_statistics(self, connection_pool):
        """Test pool statistics collection"""
        initial_stats = connection_pool.get_statistics()
        assert initial_stats is not None
        assert 'total_connections_created' in initial_stats
        
        # Use connections and check statistics update
        with connection_pool.get_connection():
            pass
        
        updated_stats = connection_pool.get_statistics()
        assert updated_stats['total_connections_borrowed'] > initial_stats['total_connections_borrowed']
    
    def test_pool_warmup(self, temp_db, test_pool_config):
        """Test pool warmup functionality"""
        pool = ThreadSafeConnectionPool(temp_db, test_pool_config)
        
        # Pool should have minimum connections after warmup
        status = pool.get_pool_status()
        assert status['idle_connections'] >= test_pool_config.min_connections
        
        # Test explicit warmup
        result = pool.warmup()
        assert result is True
        
        pool.shutdown()


class TestThreadSafety:
    """Test thread safety of connection pool"""
    
    def test_concurrent_connection_acquisition(self, connection_pool):
        """Test acquiring connections from multiple threads simultaneously"""
        num_threads = 20
        results = []
        errors = []
        
        def acquire_connection(thread_id):
            try:
                with connection_pool.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO test_table (thread_id, timestamp, data) VALUES (?, ?, ?)",
                        (f"thread_{thread_id}", datetime.now().isoformat(), f"data_{thread_id}")
                    )
                    conn.commit()
                    
                    # Simulate some work
                    time.sleep(random.uniform(0.01, 0.1))
                    
                    cursor.execute("SELECT COUNT(*) FROM test_table WHERE thread_id = ?", (f"thread_{thread_id}",))
                    count = cursor.fetchone()[0]
                    results.append((thread_id, count))
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Create and start threads
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=acquire_connection, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=30)
        
        # Verify results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == num_threads
        
        # Verify data integrity
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM test_table")
            total_count = cursor.fetchone()[0]
            assert total_count == num_threads
    
    def test_connection_pool_limits(self, connection_pool):
        """Test connection pool respects maximum connection limits"""
        max_connections = connection_pool.config.max_connections
        active_connections = []
        
        def acquire_and_hold_connection(duration):
            with connection_pool.get_connection() as conn:
                time.sleep(duration)
        
        # Start threads that hold connections
        threads = []
        for i in range(max_connections + 2):  # Try to exceed limit
            thread = threading.Thread(target=acquire_and_hold_connection, args=(0.5,))
            threads.append(thread)
            thread.start()
            time.sleep(0.01)  # Small delay to stagger starts
        
        # Check that we don't exceed the maximum
        time.sleep(0.1)
        status = pool.get_pool_status()
        assert status['active_connections'] <= max_connections
        
        # Wait for threads to complete
        for thread in threads:
            thread.join(timeout=10)
    
    def test_connection_timeout(self, temp_db):
        """Test connection timeout behavior"""
        config = PoolConfig(
            min_connections=1,
            max_connections=2,
            connection_timeout=0.5,  # Short timeout for testing
            validation_timeout=1.0
        )
        
        pool = ThreadSafeConnectionPool(temp_db, config)
        
        def hold_connections():
            with pool.get_connection():
                time.sleep(2.0)  # Hold longer than timeout
        
        # Start threads to hold all connections
        threads = []
        for _ in range(config.max_connections):
            thread = threading.Thread(target=hold_connections)
            threads.append(thread)
            thread.start()
        
        time.sleep(0.1)  # Ensure connections are acquired
        
        # Try to acquire another connection (should timeout)
        start_time = time.time()
        try:
            with pool.get_connection(timeout=0.5):
                pass
            assert False, "Expected timeout error"
        except TimeoutError:
            elapsed = time.time() - start_time
            assert elapsed >= 0.4  # Should have waited for timeout
        
        # Cleanup
        for thread in threads:
            thread.join(timeout=5)
        pool.shutdown()


class TestStressConditions:
    """Test connection pool under stress conditions"""
    
    def test_high_concurrency_stress(self, connection_pool):
        """Test pool under high concurrent load"""
        num_workers = 50
        operations_per_worker = 10
        total_operations = num_workers * operations_per_worker
        
        completed_operations = []
        errors = []
        
        def worker_task(worker_id):
            worker_results = []
            worker_errors = []
            
            for op_id in range(operations_per_worker):
                try:
                    start_time = time.time()
                    with connection_pool.get_connection() as conn:
                        cursor = conn.cursor()
                        
                        # Perform multiple operations
                        cursor.execute(
                            "INSERT INTO test_table (thread_id, timestamp, data) VALUES (?, ?, ?)",
                            (f"worker_{worker_id}", datetime.now().isoformat(), f"op_{op_id}")
                        )
                        
                        cursor.execute("SELECT COUNT(*) FROM test_table")
                        count = cursor.fetchone()[0]
                        
                        # Simulate processing time
                        time.sleep(random.uniform(0.001, 0.01))
                        
                        conn.commit()
                    
                    elapsed = time.time() - start_time
                    worker_results.append((worker_id, op_id, elapsed))
                    
                except Exception as e:
                    worker_errors.append((worker_id, op_id, str(e)))
            
            completed_operations.extend(worker_results)
            errors.extend(worker_errors)
        
        # Execute stress test
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker_task, i) for i in range(num_workers)]
            
            for future in as_completed(futures, timeout=60):
                future.result()  # Wait for completion and raise any exceptions
        
        total_time = time.time() - start_time
        
        # Verify results
        assert len(errors) == 0, f"Errors occurred: {errors[:10]}..."  # Show first 10 errors
        assert len(completed_operations) == total_operations
        
        # Performance metrics
        avg_operation_time = sum(op[2] for op in completed_operations) / len(completed_operations)
        operations_per_second = total_operations / total_time
        
        print(f"Stress test results:")
        print(f"  Total operations: {total_operations}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Operations/second: {operations_per_second:.2f}")
        print(f"  Average operation time: {avg_operation_time*1000:.2f}ms")
        
        # Verify data integrity
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM test_table")
            final_count = cursor.fetchone()[0]
            assert final_count == total_operations
    
    def test_rapid_acquire_release_cycle(self, connection_pool):
        """Test rapid acquire/release cycles"""
        num_cycles = 1000
        errors = []
        
        def rapid_cycle_worker():
            for i in range(num_cycles // 10):  # 10 workers, each doing 100 cycles
                try:
                    with connection_pool.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT 1")
                        result = cursor.fetchone()
                        assert result[0] == 1
                except Exception as e:
                    errors.append(str(e))
        
        # Run rapid cycles with multiple workers
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=rapid_cycle_worker)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join(timeout=30)
        
        assert len(errors) == 0, f"Errors in rapid cycles: {errors[:5]}..."
    
    def test_connection_leakage_detection(self, temp_db):
        """Test detection of connection leaks"""
        config = PoolConfig(
            min_connections=1,
            max_connections=3,
            connection_timeout=1.0,
            enable_leak_detection=True
        )
        
        pool = ThreadSafeConnectionPool(temp_db, config)
        
        # Simulate connection leak (not using context manager)
        def leak_connection():
            conn_wrapper = pool._get_connection_with_timeout(5.0)
            # Intentionally not returning connection
            time.sleep(0.1)
        
        # This should be detected as a leak
        thread = threading.Thread(target=leak_connection)
        thread.start()
        thread.join()
        
        # Check if leak is detected in statistics
        time.sleep(0.5)
        stats = pool.get_statistics()
        
        # The pool should track that more connections were borrowed than returned
        assert stats['total_connections_borrowed'] > stats['total_connections_returned']
        
        pool.shutdown()


class TestErrorHandling:
    """Test error handling and recovery scenarios"""
    
    def test_database_connection_failure(self, temp_db, test_pool_config):
        """Test handling of database connection failures"""
        pool = ThreadSafeConnectionPool(temp_db, test_pool_config)
        
        # Remove database file to simulate connection failure
        os.unlink(temp_db)
        
        # Attempting to get connection should fail gracefully
        with pytest.raises((sqlite3.OperationalError, TimeoutError)):
            with pool.get_connection():
                pass
        
        pool.shutdown()
    
    def test_connection_validation_failure(self, connection_pool):
        """Test handling of connection validation failures"""
        # Get a connection and corrupt it
        with connection_pool.get_connection() as conn:
            # Close the underlying connection to simulate corruption
            conn.close()
        
        # Pool should detect and replace invalid connections
        with connection_pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1
    
    def test_pool_shutdown_during_operation(self, connection_pool):
        """Test graceful shutdown while operations are in progress"""
        active_operations = []
        
        def long_running_operation():
            try:
                with connection_pool.get_connection() as conn:
                    time.sleep(1.0)  # Simulate long operation
                    active_operations.append("completed")
            except Exception as e:
                active_operations.append(f"error: {str(e)}")
        
        # Start operation
        thread = threading.Thread(target=long_running_operation)
        thread.start()
        
        time.sleep(0.1)  # Let operation start
        
        # Shutdown pool
        connection_pool.shutdown(timeout=2.0)
        
        # Wait for operation to complete
        thread.join(timeout=5)
        
        # Operation should complete or fail gracefully
        assert len(active_operations) > 0


class TestPoolMonitoring:
    """Test pool monitoring and statistics"""
    
    def test_pool_monitor_initialization(self, connection_pool):
        """Test pool monitor initialization and basic functionality"""
        monitor = PoolMonitor(
            pool=connection_pool,
            collection_interval=0.1,  # Fast collection for testing
            enable_alerts=True
        )
        
        monitor.start_monitoring()
        time.sleep(0.3)  # Let monitor collect some data
        
        # Check that metrics are being collected
        metrics = monitor.get_current_metrics()
        assert metrics is not None
        
        history = monitor.get_metrics_history()
        assert len(history) > 0
        
        monitor.stop_monitoring()
    
    def test_performance_monitoring(self, connection_pool):
        """Test performance monitoring during operations"""
        monitor = PoolMonitor(
            pool=connection_pool,
            collection_interval=0.05,
            enable_alerts=True
        )
        
        monitor.start_monitoring()
        
        # Perform operations while monitoring
        for i in range(10):
            with connection_pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                time.sleep(0.01)
        
        time.sleep(0.2)  # Let monitor collect data
        
        # Check performance summary
        summary = monitor.get_performance_summary(timedelta(seconds=1))
        assert summary['connections']['total_borrowed'] > 0
        assert summary['performance']['average_borrow_time_ms'] > 0
        
        monitor.stop_monitoring()
    
    def test_alert_generation(self, temp_db):
        """Test alert generation for pool issues"""
        # Create pool with very low limits to trigger alerts
        config = PoolConfig(
            min_connections=1,
            max_connections=2,
            connection_timeout=0.1
        )
        
        pool = ThreadSafeConnectionPool(temp_db, config)
        monitor = PoolMonitor(
            pool=pool,
            collection_interval=0.05,
            enable_alerts=True
        )
        
        # Set low thresholds to trigger alerts
        monitor.alert_thresholds['connection_utilization'] = 50.0  # 50%
        
        monitor.start_monitoring()
        
        # Trigger high utilization
        def hold_connection():
            with pool.get_connection():
                time.sleep(0.5)
        
        threads = []
        for _ in range(2):  # Use all connections
            thread = threading.Thread(target=hold_connection)
            threads.append(thread)
            thread.start()
        
        time.sleep(0.2)  # Let monitor detect high utilization
        
        # Check for alerts
        alerts = monitor.get_active_alerts()
        
        # Cleanup
        for thread in threads:
            thread.join()
        monitor.stop_monitoring()
        pool.shutdown()
        
        # Should have generated utilization alert
        utilization_alerts = [a for a in alerts if 'utilization' in a.message.lower()]
        assert len(utilization_alerts) > 0


class TestPooledDatabaseIntegration:
    """Test integration with IronChefDatabasePooled"""
    
    def test_pooled_database_basic_operations(self, temp_db):
        """Test basic database operations with pooling"""
        # Initialize pooled database
        config = PoolConfig(min_connections=2, max_connections=5)
        IronChefDatabasePooled.initialize_pool(temp_db, config)
        
        db = IronChefDatabasePooled(temp_db, use_pooling=True)
        
        with db:
            # Test basic query
            db.cursor.execute("SELECT COUNT(*) FROM episodes")
            count = db.cursor.fetchone()[0]
            assert count > 0
            
            # Test connection info
            info = db.get_connection_info()
            assert info['is_pooled'] is True
            assert info['use_pooling'] is True
    
    def test_pooled_database_concurrent_access(self, temp_db):
        """Test concurrent access with pooled database"""
        config = PoolConfig(min_connections=2, max_connections=8)
        IronChefDatabasePooled.initialize_pool(temp_db, config)
        
        results = []
        errors = []
        
        def database_operation(thread_id):
            try:
                db = IronChefDatabasePooled(temp_db, use_pooling=True)
                with db:
                    # Perform database operations
                    db.cursor.execute("SELECT COUNT(*) FROM episodes")
                    count = db.cursor.fetchone()[0]
                    
                    db.cursor.execute(
                        "INSERT INTO test_table (thread_id, timestamp, data) VALUES (?, ?, ?)",
                        (f"thread_{thread_id}", datetime.now().isoformat(), f"data_{thread_id}")
                    )
                    
                    results.append((thread_id, count))
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Run concurrent operations
        threads = []
        for i in range(15):
            thread = threading.Thread(target=database_operation, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join(timeout=10)
        
        # Verify results
        assert len(errors) == 0, f"Errors: {errors}"
        assert len(results) == 15
        
        # Cleanup
        IronChefDatabasePooled.shutdown_pool()
    
    def test_pooled_database_fallback(self, temp_db):
        """Test fallback to direct connections when pool fails"""
        # Create database with pooling initially disabled
        db = IronChefDatabasePooled(temp_db, use_pooling=False)
        
        with db:
            info = db.get_connection_info()
            assert info['is_pooled'] is False
            assert info['use_pooling'] is False
            
            # Should still work
            db.cursor.execute("SELECT 1")
            result = db.cursor.fetchone()[0]
            assert result == 1


class TestConfigurationManagement:
    """Test configuration management system"""
    
    def test_config_manager_initialization(self):
        """Test configuration manager initialization"""
        config_manager = ConfigManager(environment=EnvironmentType.TESTING)
        
        config = config_manager.get_config()
        assert config.application.environment == EnvironmentType.TESTING
        assert config.pool.min_connections >= 1
        assert config.pool.max_connections >= config.pool.min_connections
    
    def test_environment_specific_configurations(self):
        """Test environment-specific configuration overrides"""
        # Test development environment
        dev_config = ConfigManager(environment=EnvironmentType.DEVELOPMENT)
        dev_settings = dev_config.get_config()
        assert dev_settings.application.debug is True
        
        # Test production environment
        prod_config = ConfigManager(environment=EnvironmentType.PRODUCTION)
        prod_settings = prod_config.get_config()
        assert prod_settings.application.debug is False
        assert prod_settings.monitoring.enable_monitoring is True
    
    def test_runtime_configuration_updates(self):
        """Test runtime configuration updates"""
        config_manager = ConfigManager(environment=EnvironmentType.TESTING)
        
        original_max_connections = config_manager.get_pool_config().max_connections
        
        # Update configuration
        updates = {'pool.max_connections': original_max_connections + 5}
        result = config_manager.update_config(updates)
        assert result is True
        
        # Verify update
        updated_max_connections = config_manager.get_pool_config().max_connections
        assert updated_max_connections == original_max_connections + 5


# Performance benchmark tests

class TestPerformanceBenchmarks:
    """Performance benchmark tests comparing pooled vs non-pooled connections"""
    
    def test_connection_acquisition_benchmark(self, temp_db):
        """Benchmark connection acquisition time"""
        config = PoolConfig(min_connections=3, max_connections=10)
        
        # Test pooled connections
        pool = ThreadSafeConnectionPool(temp_db, config)
        
        pooled_times = []
        for _ in range(100):
            start_time = time.time()
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
            elapsed = time.time() - start_time
            pooled_times.append(elapsed)
        
        pool.shutdown()
        
        # Test direct connections
        direct_times = []
        for _ in range(100):
            start_time = time.time()
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            elapsed = time.time() - start_time
            direct_times.append(elapsed)
        
        # Compare performance
        avg_pooled = sum(pooled_times) / len(pooled_times)
        avg_direct = sum(direct_times) / len(direct_times)
        
        print(f"Connection acquisition benchmark:")
        print(f"  Pooled average: {avg_pooled*1000:.2f}ms")
        print(f"  Direct average: {avg_direct*1000:.2f}ms")
        print(f"  Improvement: {((avg_direct - avg_pooled) / avg_direct * 100):.1f}%")
        
        # Pooled connections should be faster (especially after warmup)
        assert avg_pooled < avg_direct * 1.5  # Allow some overhead
    
    def test_concurrent_throughput_benchmark(self, temp_db):
        """Benchmark concurrent operation throughput"""
        config = PoolConfig(min_connections=5, max_connections=15)
        
        def run_operations(use_pool=True, num_operations=200, num_workers=20):
            results = []
            errors = []
            
            if use_pool:
                pool = ThreadSafeConnectionPool(temp_db, config)
                
                def pooled_worker():
                    worker_times = []
                    for _ in range(num_operations // num_workers):
                        try:
                            start_time = time.time()
                            with pool.get_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute("SELECT COUNT(*) FROM episodes")
                                result = cursor.fetchone()
                            elapsed = time.time() - start_time
                            worker_times.append(elapsed)
                        except Exception as e:
                            errors.append(str(e))
                    results.extend(worker_times)
                
                start_time = time.time()
                with ThreadPoolExecutor(max_workers=num_workers) as executor:
                    futures = [executor.submit(pooled_worker) for _ in range(num_workers)]
                    for future in as_completed(futures, timeout=30):
                        future.result()
                total_time = time.time() - start_time
                pool.shutdown()
                
            else:
                def direct_worker():
                    worker_times = []
                    for _ in range(num_operations // num_workers):
                        try:
                            start_time = time.time()
                            conn = sqlite3.connect(temp_db)
                            cursor = conn.cursor()
                            cursor.execute("SELECT COUNT(*) FROM episodes")
                            result = cursor.fetchone()
                            conn.close()
                            elapsed = time.time() - start_time
                            worker_times.append(elapsed)
                        except Exception as e:
                            errors.append(str(e))
                    results.extend(worker_times)
                
                start_time = time.time()
                with ThreadPoolExecutor(max_workers=num_workers) as executor:
                    futures = [executor.submit(direct_worker) for _ in range(num_workers)]
                    for future in as_completed(futures, timeout=30):
                        future.result()
                total_time = time.time() - start_time
            
            return {
                'total_time': total_time,
                'operations_per_second': len(results) / total_time,
                'avg_operation_time': sum(results) / len(results) if results else 0,
                'errors': len(errors)
            }
        
        # Run benchmarks
        pooled_results = run_operations(use_pool=True)
        direct_results = run_operations(use_pool=False)
        
        print(f"Concurrent throughput benchmark:")
        print(f"  Pooled: {pooled_results['operations_per_second']:.1f} ops/sec")
        print(f"  Direct: {direct_results['operations_per_second']:.1f} ops/sec")
        print(f"  Improvement: {((pooled_results['operations_per_second'] - direct_results['operations_per_second']) / direct_results['operations_per_second'] * 100):.1f}%")
        
        # Verify no errors
        assert pooled_results['errors'] == 0
        assert direct_results['errors'] == 0
        
        # Pooled should provide better throughput under concurrency
        assert pooled_results['operations_per_second'] >= direct_results['operations_per_second'] * 0.8


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])