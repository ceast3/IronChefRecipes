#!/usr/bin/env python3
"""
Integration Test for Connection Pooling Implementation
Quick validation that all components work together correctly.
"""

import sys
import os
import tempfile
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor

def test_basic_functionality():
    """Test basic connection pool functionality"""
    print("Testing basic functionality...")
    
    from connection_pool import PoolConfig, ThreadSafeConnectionPool
    
    # Create temp database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Initialize test database
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, data TEXT)")
        conn.execute("INSERT INTO test_table (data) VALUES ('test data')")
        conn.commit()
        conn.close()
        
        # Test pool
        config = PoolConfig(min_connections=2, max_connections=5)
        pool = ThreadSafeConnectionPool(db_path, config)
        
        # Test connection acquisition
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM test_table")
            count = cursor.fetchone()[0]
            assert count == 1, f"Expected 1 row, got {count}"
        
        pool.shutdown()
        print("✓ Basic functionality test passed")
        
    finally:
        try:
            os.unlink(db_path)
        except:
            pass

def test_concurrent_access():
    """Test concurrent access to the pool"""
    print("Testing concurrent access...")
    
    from connection_pool import PoolConfig, ThreadSafeConnectionPool
    
    # Create temp database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Initialize test database
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE concurrent_test (id INTEGER PRIMARY KEY, thread_id TEXT)")
        conn.commit()
        conn.close()
        
        # Create pool
        config = PoolConfig(min_connections=2, max_connections=5)
        pool = ThreadSafeConnectionPool(db_path, config)
        
        results = []
        errors = []
        
        def worker(thread_id):
            try:
                with pool.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO concurrent_test (thread_id) VALUES (?)", (f"thread_{thread_id}",))
                    conn.commit()
                    
                    cursor.execute("SELECT COUNT(*) FROM concurrent_test WHERE thread_id = ?", (f"thread_{thread_id}",))
                    count = cursor.fetchone()[0]
                    results.append((thread_id, count))
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Run concurrent workers
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, i) for i in range(10)]
            for future in futures:
                future.result()
        
        pool.shutdown()
        
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10, f"Expected 10 results, got {len(results)}"
        print("✓ Concurrent access test passed")
        
    finally:
        try:
            os.unlink(db_path)
        except:
            pass

def test_pooled_database_class():
    """Test the IronChefDatabasePooled class"""
    print("Testing pooled database class...")
    
    from iron_chef_database_pooled import IronChefDatabasePooled, PoolConfig
    
    # Create temp database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Initialize test database with schema
        conn = sqlite3.connect(db_path)
        conn.executescript("""
            CREATE TABLE episodes (
                id INTEGER PRIMARY KEY,
                episode_number INTEGER,
                theme TEXT
            );
            
            INSERT INTO episodes (episode_number, theme) VALUES (1, 'Test Theme');
        """)
        conn.commit()
        conn.close()
        
        # Initialize pool for class
        config = PoolConfig(min_connections=1, max_connections=3)
        IronChefDatabasePooled.initialize_pool(db_path, config)
        
        # Test pooled database usage
        db = IronChefDatabasePooled(db_path, use_pooling=True)
        with db:
            db.cursor.execute("SELECT COUNT(*) FROM episodes")
            count = db.cursor.fetchone()[0]
            assert count == 1, f"Expected 1 episode, got {count}"
            
            # Test connection info
            info = db.get_connection_info()
            assert info['is_pooled'] == True, "Expected pooled connection"
        
        IronChefDatabasePooled.shutdown_pool()
        print("✓ Pooled database class test passed")
        
    finally:
        try:
            os.unlink(db_path)
        except:
            pass

def test_configuration_system():
    """Test configuration management"""
    print("Testing configuration system...")
    
    from pool_config import ConfigManager, EnvironmentType
    
    # Test different environments
    for env in [EnvironmentType.DEVELOPMENT, EnvironmentType.TESTING, EnvironmentType.PRODUCTION]:
        config_manager = ConfigManager(environment=env)
        config = config_manager.get_config()
        
        assert config.application.environment == env, f"Environment mismatch: {config.application.environment} != {env}"
        assert config.pool.min_connections >= 1, "Min connections should be at least 1"
        assert config.pool.max_connections >= config.pool.min_connections, "Max should be >= min connections"
    
    # Test configuration updates
    config_manager = ConfigManager(environment=EnvironmentType.TESTING)
    original_max = config_manager.get_pool_config().max_connections
    
    updates = {'pool.max_connections': original_max + 5}
    result = config_manager.update_config(updates)
    assert result == True, "Configuration update should succeed"
    
    updated_max = config_manager.get_pool_config().max_connections
    assert updated_max == original_max + 5, "Configuration should be updated"
    
    print("✓ Configuration system test passed")

def test_monitoring_system():
    """Test monitoring components"""
    print("Testing monitoring system...")
    
    from connection_pool import PoolConfig, ThreadSafeConnectionPool
    from pool_monitor import PoolMonitor
    
    # Create temp database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    try:
        # Initialize test database
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
        conn.close()
        
        # Create pool and monitor
        config = PoolConfig(min_connections=1, max_connections=3)
        pool = ThreadSafeConnectionPool(db_path, config)
        
        monitor = PoolMonitor(
            pool=pool,
            collection_interval=0.1,  # Fast collection for testing
            enable_alerts=True
        )
        
        monitor.start_monitoring()
        
        # Do some operations to generate metrics
        for _ in range(5):
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
        
        time.sleep(0.2)  # Let monitor collect data
        
        # Check metrics
        metrics = monitor.get_current_metrics()
        assert metrics is not None, "Should have collected metrics"
        
        health = monitor.get_health_status()
        assert health is not None, "Should have health status"
        
        monitor.stop_monitoring()
        pool.shutdown()
        print("✓ Monitoring system test passed")
        
    finally:
        try:
            os.unlink(db_path)
        except:
            pass

def main():
    """Run all integration tests"""
    print("🧪 Iron Chef Connection Pooling - Integration Tests")
    print("=" * 60)
    
    tests = [
        test_basic_functionality,
        test_concurrent_access,
        test_pooled_database_class,
        test_configuration_system,
        test_monitoring_system
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All integration tests passed! Connection pooling is ready for production.")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())