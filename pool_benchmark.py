"""
Connection Pool Performance Benchmark Suite
Comprehensive benchmarking tool for comparing pooled vs non-pooled database
connections under various load conditions and usage patterns.

Features:
- Multiple benchmark scenarios
- Detailed performance metrics
- Statistical analysis
- Load testing capabilities
- Resource usage monitoring
- Comparative analysis
- Report generation
"""

import time
import threading
import sqlite3
import tempfile
import os
import json
import csv
import statistics
import psutil
import gc
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, asdict
from contextlib import contextmanager

from connection_pool import ThreadSafeConnectionPool, PoolConfig
from iron_chef_database_pooled import IronChefDatabasePooled
from pool_monitor import PoolMonitor


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run"""
    name: str
    scenario: str
    use_pooling: bool
    total_operations: int
    total_time: float
    operations_per_second: float
    average_operation_time: float
    min_operation_time: float
    max_operation_time: float
    std_deviation: float
    percentile_95: float
    percentile_99: float
    success_rate: float
    errors: int
    memory_usage_mb: float
    cpu_usage_percent: float
    concurrent_connections: int
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics"""
        return {
            'name': self.name,
            'scenario': self.scenario,
            'pooling': 'Yes' if self.use_pooling else 'No',
            'ops_per_second': round(self.operations_per_second, 2),
            'avg_time_ms': round(self.average_operation_time * 1000, 2),
            'p95_time_ms': round(self.percentile_95 * 1000, 2),
            'success_rate': round(self.success_rate, 3),
            'memory_mb': round(self.memory_usage_mb, 1),
            'cpu_percent': round(self.cpu_usage_percent, 1)
        }


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs"""
    num_operations: int = 1000
    num_workers: int = 10
    warmup_operations: int = 100
    duration_seconds: Optional[float] = None
    operation_delay: float = 0.0
    pool_config: Optional[PoolConfig] = None
    collect_detailed_metrics: bool = True
    monitor_resources: bool = True


class PerformanceBenchmark:
    """
    Comprehensive performance benchmark suite for connection pooling.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize benchmark suite.
        
        Args:
            db_path: Database path (creates temp if None)
        """
        self.db_path = db_path
        self._temp_db = None
        self._cleanup_required = False
        
        if not self.db_path:
            self._create_temp_database()
        
        self.results: List[BenchmarkResult] = []
        self._resource_monitor = None
    
    def _create_temp_database(self):
        """Create a temporary test database"""
        temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._temp_db = temp_file.name
        temp_file.close()
        
        self.db_path = self._temp_db
        self._cleanup_required = True
        
        # Initialize with test schema and data
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            -- Episodes table
            CREATE TABLE episodes (
                id INTEGER PRIMARY KEY,
                episode_number INTEGER NOT NULL,
                air_date TEXT,
                theme TEXT NOT NULL,
                iron_chef_id INTEGER,
                competitor_id INTEGER,
                winner TEXT
            );
            
            -- Iron chefs table
            CREATE TABLE iron_chefs (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                title TEXT,
                specialty TEXT
            );
            
            -- Competitors table
            CREATE TABLE competitors (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                restaurant TEXT,
                specialty TEXT
            );
            
            -- Test data
            INSERT INTO iron_chefs (name, title, specialty) VALUES
            ('Chen Kenichi', 'The Szechuan Sage', 'Szechuan Cuisine'),
            ('Hiroyuki Sakai', 'The Delacroix of French Cuisine', 'French Cuisine'),
            ('Masaharu Morimoto', 'The Iron Chef', 'Japanese Cuisine');
            
            INSERT INTO competitors (name, restaurant, specialty) VALUES
            ('Toshiro Kandagawa', 'Nadaman', 'Japanese Cuisine'),
            ('Alain Passard', "L'Arpège", 'French Cuisine'),
            ('Martin Blunos', 'Lettonie', 'Modern European');
            
            -- Generate test episodes
            INSERT INTO episodes (episode_number, theme, iron_chef_id, competitor_id, winner)
            SELECT 
                seq,
                'Theme ' || (seq % 20 + 1),
                (seq % 3) + 1,
                (seq % 3) + 1,
                CASE (seq % 3) WHEN 0 THEN 'Iron Chef' WHEN 1 THEN 'Competitor' ELSE 'Draw' END
            FROM (
                WITH RECURSIVE sequence(seq) AS (
                    SELECT 1
                    UNION ALL
                    SELECT seq + 1 FROM sequence WHERE seq < 1000
                )
                SELECT seq FROM sequence
            );
            
            -- Test table for benchmarks
            CREATE TABLE benchmark_test (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT,
                operation_id INTEGER,
                timestamp TEXT,
                data TEXT
            );
            
            -- Create indexes for better performance
            CREATE INDEX idx_episodes_theme ON episodes(theme);
            CREATE INDEX idx_episodes_chef ON episodes(iron_chef_id, competitor_id);
            CREATE INDEX idx_benchmark_thread ON benchmark_test(thread_id);
        """)
        conn.close()
    
    def __del__(self):
        """Cleanup temporary files"""
        if self._cleanup_required and self._temp_db:
            try:
                os.unlink(self._temp_db)
            except OSError:
                pass
    
    @contextmanager
    def _resource_monitoring(self):
        """Context manager for resource monitoring"""
        if not psutil:
            yield None, None
            return
        
        process = psutil.Process()
        start_memory = process.memory_info().rss / 1024 / 1024  # MB
        start_cpu = process.cpu_percent()
        
        yield process, start_memory
        
        end_memory = process.memory_info().rss / 1024 / 1024  # MB
        end_cpu = process.cpu_percent()
        
        return end_memory, end_cpu
    
    def _run_operation_batch(self, operation_func: Callable, 
                           config: BenchmarkConfig,
                           use_pooling: bool) -> Tuple[List[float], int]:
        """Run a batch of operations and collect timing data"""
        operation_times = []
        errors = 0
        
        if use_pooling:
            pool_config = config.pool_config or PoolConfig(
                min_connections=max(2, config.num_workers // 4),
                max_connections=max(config.num_workers, 10),
                connection_timeout=30.0
            )
            pool = ThreadSafeConnectionPool(self.db_path, pool_config)
        else:
            pool = None
        
        try:
            def worker_task(worker_id: int) -> List[Tuple[float, bool]]:
                worker_results = []
                operations_per_worker = config.num_operations // config.num_workers
                
                for op_id in range(operations_per_worker):
                    try:
                        start_time = time.perf_counter()
                        success = operation_func(worker_id, op_id, pool)
                        end_time = time.perf_counter()
                        
                        worker_results.append((end_time - start_time, success))
                        
                        if config.operation_delay > 0:
                            time.sleep(config.operation_delay)
                            
                    except Exception as e:
                        worker_results.append((0.0, False))
                
                return worker_results
            
            # Run workers concurrently
            with ThreadPoolExecutor(max_workers=config.num_workers) as executor:
                futures = [
                    executor.submit(worker_task, i) 
                    for i in range(config.num_workers)
                ]
                
                for future in as_completed(futures, timeout=300):
                    worker_results = future.result()
                    for op_time, success in worker_results:
                        operation_times.append(op_time)
                        if not success:
                            errors += 1
        
        finally:
            if pool:
                pool.shutdown()
        
        return operation_times, errors
    
    def benchmark_simple_queries(self, config: BenchmarkConfig) -> Tuple[BenchmarkResult, BenchmarkResult]:
        """Benchmark simple SELECT queries"""
        
        def simple_query_operation(worker_id: int, op_id: int, pool: Optional[ThreadSafeConnectionPool]) -> bool:
            try:
                if pool:
                    with pool.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM episodes WHERE theme LIKE 'Theme%'")
                        result = cursor.fetchone()
                        return result[0] > 0
                else:
                    conn = sqlite3.connect(self.db_path)
                    try:
                        cursor = conn.cursor()
                        cursor.execute("SELECT COUNT(*) FROM episodes WHERE theme LIKE 'Theme%'")
                        result = cursor.fetchone()
                        return result[0] > 0
                    finally:
                        conn.close()
            except Exception:
                return False
        
        # Benchmark with pooling
        print("Running simple queries benchmark with pooling...")
        with self._resource_monitoring() as (process, start_memory):
            start_time = time.perf_counter()
            pooled_times, pooled_errors = self._run_operation_batch(
                simple_query_operation, config, use_pooling=True
            )
            end_time = time.perf_counter()
        
        pooled_result = self._create_benchmark_result(
            name="Simple Queries",
            scenario="SELECT COUNT with LIKE filter",
            use_pooling=True,
            operation_times=pooled_times,
            total_time=end_time - start_time,
            errors=pooled_errors,
            config=config,
            process=process,
            start_memory=start_memory
        )
        
        # Benchmark without pooling
        print("Running simple queries benchmark without pooling...")
        with self._resource_monitoring() as (process, start_memory):
            start_time = time.perf_counter()
            direct_times, direct_errors = self._run_operation_batch(
                simple_query_operation, config, use_pooling=False
            )
            end_time = time.perf_counter()
        
        direct_result = self._create_benchmark_result(
            name="Simple Queries",
            scenario="SELECT COUNT with LIKE filter",
            use_pooling=False,
            operation_times=direct_times,
            total_time=end_time - start_time,
            errors=direct_errors,
            config=config,
            process=process,
            start_memory=start_memory
        )
        
        return pooled_result, direct_result
    
    def benchmark_complex_queries(self, config: BenchmarkConfig) -> Tuple[BenchmarkResult, BenchmarkResult]:
        """Benchmark complex JOIN queries"""
        
        def complex_query_operation(worker_id: int, op_id: int, pool: Optional[ThreadSafeConnectionPool]) -> bool:
            try:
                query = """
                    SELECT e.episode_number, e.theme, ic.name as iron_chef, c.name as competitor,
                           COUNT(*) OVER() as total_episodes
                    FROM episodes e
                    JOIN iron_chefs ic ON e.iron_chef_id = ic.id
                    JOIN competitors c ON e.competitor_id = c.id
                    WHERE e.theme LIKE ? 
                    ORDER BY e.episode_number
                    LIMIT 10
                """
                theme_filter = f"Theme {(worker_id + op_id) % 20 + 1}%"
                
                if pool:
                    with pool.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(query, (theme_filter,))
                        results = cursor.fetchall()
                        return len(results) > 0
                else:
                    conn = sqlite3.connect(self.db_path)
                    try:
                        cursor = conn.cursor()
                        cursor.execute(query, (theme_filter,))
                        results = cursor.fetchall()
                        return len(results) > 0
                    finally:
                        conn.close()
            except Exception:
                return False
        
        # Benchmark with pooling
        print("Running complex queries benchmark with pooling...")
        with self._resource_monitoring() as (process, start_memory):
            start_time = time.perf_counter()
            pooled_times, pooled_errors = self._run_operation_batch(
                complex_query_operation, config, use_pooling=True
            )
            end_time = time.perf_counter()
        
        pooled_result = self._create_benchmark_result(
            name="Complex Queries",
            scenario="Multi-table JOIN with window function",
            use_pooling=True,
            operation_times=pooled_times,
            total_time=end_time - start_time,
            errors=pooled_errors,
            config=config,
            process=process,
            start_memory=start_memory
        )
        
        # Benchmark without pooling
        print("Running complex queries benchmark without pooling...")
        with self._resource_monitoring() as (process, start_memory):
            start_time = time.perf_counter()
            direct_times, direct_errors = self._run_operation_batch(
                complex_query_operation, config, use_pooling=False
            )
            end_time = time.perf_counter()
        
        direct_result = self._create_benchmark_result(
            name="Complex Queries",
            scenario="Multi-table JOIN with window function",
            use_pooling=False,
            operation_times=direct_times,
            total_time=end_time - start_time,
            errors=direct_errors,
            config=config,
            process=process,
            start_memory=start_memory
        )
        
        return pooled_result, direct_result
    
    def benchmark_write_operations(self, config: BenchmarkConfig) -> Tuple[BenchmarkResult, BenchmarkResult]:
        """Benchmark INSERT operations"""
        
        def write_operation(worker_id: int, op_id: int, pool: Optional[ThreadSafeConnectionPool]) -> bool:
            try:
                timestamp = datetime.now().isoformat()
                data = f"worker_{worker_id}_op_{op_id}_data"
                
                if pool:
                    with pool.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT INTO benchmark_test (thread_id, operation_id, timestamp, data) VALUES (?, ?, ?, ?)",
                            (f"worker_{worker_id}", op_id, timestamp, data)
                        )
                        conn.commit()
                        return True
                else:
                    conn = sqlite3.connect(self.db_path)
                    try:
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT INTO benchmark_test (thread_id, operation_id, timestamp, data) VALUES (?, ?, ?, ?)",
                            (f"worker_{worker_id}", op_id, timestamp, data)
                        )
                        conn.commit()
                        return True
                    finally:
                        conn.close()
            except Exception:
                return False
        
        # Clear test table
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM benchmark_test")
        conn.commit()
        conn.close()
        
        # Benchmark with pooling
        print("Running write operations benchmark with pooling...")
        with self._resource_monitoring() as (process, start_memory):
            start_time = time.perf_counter()
            pooled_times, pooled_errors = self._run_operation_batch(
                write_operation, config, use_pooling=True
            )
            end_time = time.perf_counter()
        
        pooled_result = self._create_benchmark_result(
            name="Write Operations",
            scenario="Concurrent INSERT operations",
            use_pooling=True,
            operation_times=pooled_times,
            total_time=end_time - start_time,
            errors=pooled_errors,
            config=config,
            process=process,
            start_memory=start_memory
        )
        
        # Clear test table again
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM benchmark_test")
        conn.commit()
        conn.close()
        
        # Benchmark without pooling
        print("Running write operations benchmark without pooling...")
        with self._resource_monitoring() as (process, start_memory):
            start_time = time.perf_counter()
            direct_times, direct_errors = self._run_operation_batch(
                write_operation, config, use_pooling=False
            )
            end_time = time.perf_counter()
        
        direct_result = self._create_benchmark_result(
            name="Write Operations",
            scenario="Concurrent INSERT operations",
            use_pooling=False,
            operation_times=direct_times,
            total_time=end_time - start_time,
            errors=direct_errors,
            config=config,
            process=process,
            start_memory=start_memory
        )
        
        return pooled_result, direct_result
    
    def benchmark_mixed_workload(self, config: BenchmarkConfig) -> Tuple[BenchmarkResult, BenchmarkResult]:
        """Benchmark mixed read/write workload"""
        
        def mixed_operation(worker_id: int, op_id: int, pool: Optional[ThreadSafeConnectionPool]) -> bool:
            try:
                # 70% reads, 30% writes
                is_write = (op_id % 10) < 3
                
                if pool:
                    with pool.get_connection() as conn:
                        cursor = conn.cursor()
                        if is_write:
                            cursor.execute(
                                "INSERT INTO benchmark_test (thread_id, operation_id, timestamp, data) VALUES (?, ?, ?, ?)",
                                (f"worker_{worker_id}", op_id, datetime.now().isoformat(), f"mixed_data_{op_id}")
                            )
                            conn.commit()
                        else:
                            cursor.execute(
                                "SELECT e.theme, ic.name FROM episodes e JOIN iron_chefs ic ON e.iron_chef_id = ic.id WHERE e.id = ?",
                                ((worker_id + op_id) % 1000 + 1,)
                            )
                            result = cursor.fetchone()
                            return result is not None
                        return True
                else:
                    conn = sqlite3.connect(self.db_path)
                    try:
                        cursor = conn.cursor()
                        if is_write:
                            cursor.execute(
                                "INSERT INTO benchmark_test (thread_id, operation_id, timestamp, data) VALUES (?, ?, ?, ?)",
                                (f"worker_{worker_id}", op_id, datetime.now().isoformat(), f"mixed_data_{op_id}")
                            )
                            conn.commit()
                        else:
                            cursor.execute(
                                "SELECT e.theme, ic.name FROM episodes e JOIN iron_chefs ic ON e.iron_chef_id = ic.id WHERE e.id = ?",
                                ((worker_id + op_id) % 1000 + 1,)
                            )
                            result = cursor.fetchone()
                            return result is not None
                        return True
                    finally:
                        conn.close()
            except Exception:
                return False
        
        # Clear test table
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM benchmark_test")
        conn.commit()
        conn.close()
        
        # Benchmark with pooling
        print("Running mixed workload benchmark with pooling...")
        with self._resource_monitoring() as (process, start_memory):
            start_time = time.perf_counter()
            pooled_times, pooled_errors = self._run_operation_batch(
                mixed_operation, config, use_pooling=True
            )
            end_time = time.perf_counter()
        
        pooled_result = self._create_benchmark_result(
            name="Mixed Workload",
            scenario="70% reads, 30% writes",
            use_pooling=True,
            operation_times=pooled_times,
            total_time=end_time - start_time,
            errors=pooled_errors,
            config=config,
            process=process,
            start_memory=start_memory
        )
        
        # Clear test table again
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM benchmark_test")
        conn.commit()
        conn.close()
        
        # Benchmark without pooling
        print("Running mixed workload benchmark without pooling...")
        with self._resource_monitoring() as (process, start_memory):
            start_time = time.perf_counter()
            direct_times, direct_errors = self._run_operation_batch(
                mixed_operation, config, use_pooling=False
            )
            end_time = time.perf_counter()
        
        direct_result = self._create_benchmark_result(
            name="Mixed Workload",
            scenario="70% reads, 30% writes",
            use_pooling=False,
            operation_times=direct_times,
            total_time=end_time - start_time,
            errors=direct_errors,
            config=config,
            process=process,
            start_memory=start_memory
        )
        
        return pooled_result, direct_result
    
    def _create_benchmark_result(self, name: str, scenario: str, use_pooling: bool,
                                operation_times: List[float], total_time: float,
                                errors: int, config: BenchmarkConfig,
                                process=None, start_memory: float = 0) -> BenchmarkResult:
        """Create a benchmark result from timing data"""
        
        if not operation_times:
            operation_times = [0.0]
        
        total_operations = len(operation_times)
        success_rate = (total_operations - errors) / total_operations if total_operations > 0 else 0
        
        # Calculate statistics
        avg_time = statistics.mean(operation_times) if operation_times else 0
        min_time = min(operation_times) if operation_times else 0
        max_time = max(operation_times) if operation_times else 0
        std_dev = statistics.stdev(operation_times) if len(operation_times) > 1 else 0
        
        # Calculate percentiles
        sorted_times = sorted(operation_times)
        p95_idx = int(0.95 * len(sorted_times))
        p99_idx = int(0.99 * len(sorted_times))
        
        p95_time = sorted_times[p95_idx] if sorted_times else 0
        p99_time = sorted_times[p99_idx] if sorted_times else 0
        
        # Resource usage
        memory_usage = 0.0
        cpu_usage = 0.0
        if process:
            try:
                memory_usage = process.memory_info().rss / 1024 / 1024 - start_memory
                cpu_usage = process.cpu_percent()
            except:
                pass
        
        return BenchmarkResult(
            name=name,
            scenario=scenario,
            use_pooling=use_pooling,
            total_operations=total_operations,
            total_time=total_time,
            operations_per_second=total_operations / total_time if total_time > 0 else 0,
            average_operation_time=avg_time,
            min_operation_time=min_time,
            max_operation_time=max_time,
            std_deviation=std_dev,
            percentile_95=p95_time,
            percentile_99=p99_time,
            success_rate=success_rate,
            errors=errors,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=cpu_usage,
            concurrent_connections=config.num_workers
        )
    
    def run_full_benchmark_suite(self, config: Optional[BenchmarkConfig] = None) -> List[BenchmarkResult]:
        """Run the complete benchmark suite"""
        if config is None:
            config = BenchmarkConfig()
        
        print(f"Starting comprehensive benchmark suite...")
        print(f"Configuration: {config.num_operations} operations, {config.num_workers} workers")
        print(f"Database: {self.db_path}")
        print("-" * 60)
        
        all_results = []
        
        # Run all benchmarks
        benchmarks = [
            ("Simple Queries", self.benchmark_simple_queries),
            ("Complex Queries", self.benchmark_complex_queries),
            ("Write Operations", self.benchmark_write_operations),
            ("Mixed Workload", self.benchmark_mixed_workload)
        ]
        
        for benchmark_name, benchmark_func in benchmarks:
            print(f"\n=== {benchmark_name} ===")
            try:
                pooled_result, direct_result = benchmark_func(config)
                all_results.extend([pooled_result, direct_result])
                
                # Print comparison
                self._print_comparison(pooled_result, direct_result)
                
            except Exception as e:
                print(f"Error running {benchmark_name}: {e}")
        
        self.results.extend(all_results)
        return all_results
    
    def _print_comparison(self, pooled: BenchmarkResult, direct: BenchmarkResult):
        """Print comparison between pooled and direct results"""
        print(f"\nResults for {pooled.name}:")
        print(f"  Metric                 | Pooled      | Direct      | Improvement")
        print(f"  -----------------------|-------------|-------------|------------")
        
        # Operations per second
        ops_improvement = ((pooled.operations_per_second - direct.operations_per_second) 
                          / direct.operations_per_second * 100) if direct.operations_per_second > 0 else 0
        print(f"  Ops/second             | {pooled.operations_per_second:8.1f} | {direct.operations_per_second:8.1f} | {ops_improvement:+7.1f}%")
        
        # Average time
        time_improvement = ((direct.average_operation_time - pooled.average_operation_time) 
                           / direct.average_operation_time * 100) if direct.average_operation_time > 0 else 0
        print(f"  Avg time (ms)          | {pooled.average_operation_time*1000:8.2f} | {direct.average_operation_time*1000:8.2f} | {time_improvement:+7.1f}%")
        
        # 95th percentile
        p95_improvement = ((direct.percentile_95 - pooled.percentile_95) 
                          / direct.percentile_95 * 100) if direct.percentile_95 > 0 else 0
        print(f"  P95 time (ms)          | {pooled.percentile_95*1000:8.2f} | {direct.percentile_95*1000:8.2f} | {p95_improvement:+7.1f}%")
        
        # Memory usage
        memory_change = pooled.memory_usage_mb - direct.memory_usage_mb
        print(f"  Memory usage (MB)      | {pooled.memory_usage_mb:8.1f} | {direct.memory_usage_mb:8.1f} | {memory_change:+7.1f}")
        
        # Success rate
        print(f"  Success rate           | {pooled.success_rate:8.3f} | {direct.success_rate:8.3f} | {(pooled.success_rate - direct.success_rate):+7.3f}")
    
    def export_results(self, filepath: str, format_type: str = 'json'):
        """Export benchmark results to file"""
        if format_type.lower() == 'json':
            with open(filepath, 'w') as f:
                data = {
                    'benchmark_info': {
                        'timestamp': datetime.now().isoformat(),
                        'database': self.db_path,
                        'total_benchmarks': len(self.results)
                    },
                    'results': [asdict(result) for result in self.results]
                }
                json.dump(data, f, indent=2, default=str)
        
        elif format_type.lower() == 'csv':
            with open(filepath, 'w', newline='') as f:
                if self.results:
                    writer = csv.DictWriter(f, fieldnames=asdict(self.results[0]).keys())
                    writer.writeheader()
                    for result in self.results:
                        writer.writerow(asdict(result))
        
        print(f"Results exported to {filepath}")
    
    def generate_report(self, filepath: Optional[str] = None) -> str:
        """Generate a comprehensive benchmark report"""
        if not self.results:
            return "No benchmark results available"
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("Iron Chef Database Connection Pool Benchmark Report")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Database: {self.db_path}")
        report_lines.append(f"Total Benchmarks: {len(self.results)}")
        report_lines.append("")
        
        # Group results by name
        grouped_results = {}
        for result in self.results:
            if result.name not in grouped_results:
                grouped_results[result.name] = []
            grouped_results[result.name].append(result)
        
        # Summary table
        report_lines.append("PERFORMANCE SUMMARY")
        report_lines.append("-" * 40)
        report_lines.append(f"{'Benchmark':<20} {'Pooled OPS':<12} {'Direct OPS':<12} {'Improvement':<12}")
        report_lines.append("-" * 56)
        
        total_improvements = []
        
        for name, results in grouped_results.items():
            pooled = next((r for r in results if r.use_pooling), None)
            direct = next((r for r in results if not r.use_pooling), None)
            
            if pooled and direct:
                improvement = ((pooled.operations_per_second - direct.operations_per_second) 
                              / direct.operations_per_second * 100) if direct.operations_per_second > 0 else 0
                total_improvements.append(improvement)
                
                report_lines.append(f"{name:<20} {pooled.operations_per_second:<12.1f} {direct.operations_per_second:<12.1f} {improvement:<+11.1f}%")
        
        if total_improvements:
            avg_improvement = statistics.mean(total_improvements)
            report_lines.append("-" * 56)
            report_lines.append(f"{'Average Improvement':<20} {'':<12} {'':<12} {avg_improvement:<+11.1f}%")
        
        report_lines.append("")
        
        # Detailed results
        report_lines.append("DETAILED RESULTS")
        report_lines.append("-" * 40)
        
        for name, results in grouped_results.items():
            report_lines.append(f"\n{name}:")
            report_lines.append("-" * 20)
            
            for result in results:
                pooling_str = "Pooled" if result.use_pooling else "Direct"
                report_lines.append(f"  {pooling_str} Connections:")
                report_lines.append(f"    Operations/second: {result.operations_per_second:.2f}")
                report_lines.append(f"    Average time: {result.average_operation_time*1000:.2f}ms")
                report_lines.append(f"    95th percentile: {result.percentile_95*1000:.2f}ms")
                report_lines.append(f"    Success rate: {result.success_rate:.3f}")
                report_lines.append(f"    Memory usage: {result.memory_usage_mb:.1f}MB")
                report_lines.append("")
        
        # Recommendations
        report_lines.append("RECOMMENDATIONS")
        report_lines.append("-" * 40)
        
        if total_improvements and statistics.mean(total_improvements) > 10:
            report_lines.append("✓ Connection pooling provides significant performance benefits")
            report_lines.append("✓ Recommended for production use with high concurrency")
        elif total_improvements and statistics.mean(total_improvements) > 0:
            report_lines.append("+ Connection pooling provides moderate performance benefits")
            report_lines.append("+ Consider for applications with concurrent database access")
        else:
            report_lines.append("- Connection pooling shows minimal performance improvement")
            report_lines.append("- May not be necessary for low-concurrency applications")
        
        report_lines.append("")
        report_lines.append("Note: Results may vary based on hardware, database size, and workload patterns.")
        
        report = "\n".join(report_lines)
        
        if filepath:
            with open(filepath, 'w') as f:
                f.write(report)
            print(f"Report saved to {filepath}")
        
        return report


def main():
    """Main function for running benchmarks from command line"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Iron Chef Database Connection Pool Benchmark")
    parser.add_argument("--operations", type=int, default=1000, help="Number of operations per benchmark")
    parser.add_argument("--workers", type=int, default=10, help="Number of concurrent workers")
    parser.add_argument("--db-path", type=str, help="Database file path (temp if not specified)")
    parser.add_argument("--output", type=str, help="Output file for results")
    parser.add_argument("--format", choices=['json', 'csv'], default='json', help="Output format")
    parser.add_argument("--report", type=str, help="Generate text report to file")
    
    args = parser.parse_args()
    
    # Create benchmark configuration
    config = BenchmarkConfig(
        num_operations=args.operations,
        num_workers=args.workers,
        warmup_operations=args.operations // 10
    )
    
    # Run benchmarks
    benchmark = PerformanceBenchmark(args.db_path)
    
    try:
        results = benchmark.run_full_benchmark_suite(config)
        
        # Export results
        if args.output:
            benchmark.export_results(args.output, args.format)
        
        # Generate report
        if args.report:
            benchmark.generate_report(args.report)
        else:
            print("\n" + benchmark.generate_report())
        
    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user")
    except Exception as e:
        print(f"Error running benchmark: {e}")
        raise


if __name__ == "__main__":
    main()