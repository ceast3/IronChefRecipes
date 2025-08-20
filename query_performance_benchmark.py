#!/usr/bin/env python3
"""
Query Performance Benchmark Tool
Measures and compares query performance before and after index optimization.
"""

import sqlite3
import time
import statistics
from typing import List, Dict, Tuple, Any
import json
from datetime import datetime
from pathlib import Path

class QueryBenchmark:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection = None
        
    def __enter__(self):
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.close()
    
    def execute_query_with_timing(self, query: str, params: tuple = None, iterations: int = 5) -> Dict[str, Any]:
        """Execute a query multiple times and measure performance"""
        times = []
        result_count = 0
        
        for _ in range(iterations):
            start_time = time.perf_counter()
            cursor = self.connection.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
                
            results = cursor.fetchall()
            end_time = time.perf_counter()
            
            execution_time = (end_time - start_time) * 1000  # Convert to milliseconds
            times.append(execution_time)
            result_count = len(results)
        
        return {
            'query': query,
            'params': params,
            'iterations': iterations,
            'result_count': result_count,
            'times_ms': times,
            'avg_time_ms': statistics.mean(times),
            'min_time_ms': min(times),
            'max_time_ms': max(times),
            'std_dev_ms': statistics.stdev(times) if len(times) > 1 else 0
        }
    
    def get_query_plan(self, query: str, params: tuple = None) -> List[Dict]:
        """Get the query execution plan"""
        cursor = self.connection.cursor()
        explain_query = f"EXPLAIN QUERY PLAN {query}"
        
        if params:
            cursor.execute(explain_query, params)
        else:
            cursor.execute(explain_query)
            
        return [dict(row) for row in cursor.fetchall()]
    
    def benchmark_common_queries(self) -> List[Dict[str, Any]]:
        """Benchmark common queries that should benefit from indexing"""
        
        test_queries = [
            {
                'name': 'search_episodes_by_theme',
                'description': 'Search episodes by theme (LIKE query)',
                'query': "SELECT * FROM episodes WHERE theme LIKE ?",
                'params': ('%Beef%',)
            },
            {
                'name': 'get_episode_details_with_joins',
                'description': 'Get episode details with chef names (JOINs)',
                'query': """
                    SELECT e.*, ic.name as iron_chef_name, c.name as competitor_name
                    FROM episodes e
                    JOIN iron_chefs ic ON e.iron_chef_id = ic.id
                    JOIN competitors c ON e.competitor_id = c.id
                    WHERE e.id = ?
                """,
                'params': (1,)
            },
            {
                'name': 'get_dishes_for_episode',
                'description': 'Get all dishes for an episode',
                'query': "SELECT * FROM dishes WHERE episode_id = ? ORDER BY chef_type, dish_number",
                'params': (1,)
            },
            {
                'name': 'get_recipes_by_dish',
                'description': 'Get recipes for a specific dish (foreign key lookup)',
                'query': "SELECT * FROM recipes WHERE dish_id = ?",
                'params': (1,)
            },
            {
                'name': 'get_recent_recipes',
                'description': 'Get recently generated recipes (temporal query)',
                'query': "SELECT * FROM recipes WHERE generated_date >= datetime('now', '-30 days') ORDER BY generated_date DESC",
                'params': None
            },
            {
                'name': 'get_dish_ingredients',
                'description': 'Get ingredients for dishes (junction table query)',
                'query': """
                    SELECT di.*, i.name as ingredient_name, d.dish_name
                    FROM dish_ingredients di
                    JOIN ingredients i ON di.ingredient_id = i.id
                    JOIN dishes d ON di.dish_id = d.id
                    WHERE di.dish_id = ?
                """,
                'params': (1,)
            },
            {
                'name': 'search_dishes_by_ingredient',
                'description': 'Find dishes containing specific ingredients',
                'query': """
                    SELECT DISTINCT d.*, e.theme, e.episode_number
                    FROM dishes d
                    JOIN dish_ingredients di ON d.id = di.dish_id
                    JOIN ingredients i ON di.ingredient_id = i.id
                    JOIN episodes e ON d.episode_id = e.id
                    WHERE i.name LIKE ?
                """,
                'params': ('%fish%',)
            },
            {
                'name': 'get_episodes_by_date_range',
                'description': 'Get episodes within a date range',
                'query': "SELECT * FROM episodes WHERE air_date BETWEEN ? AND ? ORDER BY air_date",
                'params': ('1999-01-01', '2000-12-31')
            },
            {
                'name': 'composite_episode_theme_date',
                'description': 'Search by theme and date (composite index test)',
                'query': "SELECT * FROM episodes WHERE theme LIKE ? AND air_date > ? ORDER BY air_date",
                'params': ('%Beef%', '1999-01-01')
            },
            {
                'name': 'complex_aggregation_query',
                'description': 'Complex aggregation with multiple JOINs',
                'query': """
                    SELECT ic.name as iron_chef, COUNT(*) as episode_count, 
                           AVG(julianday(e.air_date)) as avg_air_date_julian
                    FROM episodes e
                    JOIN iron_chefs ic ON e.iron_chef_id = ic.id
                    GROUP BY ic.id, ic.name
                    ORDER BY episode_count DESC
                """,
                'params': None
            }
        ]
        
        results = []
        
        for test in test_queries:
            print(f"Benchmarking: {test['name']} - {test['description']}")
            
            # Get query plan
            query_plan = self.get_query_plan(test['query'], test['params'])
            
            # Run performance test
            perf_result = self.execute_query_with_timing(test['query'], test['params'])
            
            # Combine results
            result = {
                **test,
                **perf_result,
                'query_plan': query_plan
            }
            
            results.append(result)
            
            print(f"  Average time: {perf_result['avg_time_ms']:.2f}ms ({perf_result['result_count']} results)")
        
        return results
    
    def save_benchmark_results(self, results: List[Dict], filename_prefix: str = "benchmark"):
        """Save benchmark results to JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{timestamp}.json"
        
        output_data = {
            'timestamp': timestamp,
            'database_path': self.db_path,
            'benchmark_results': results
        }
        
        with open(filename, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
        
        print(f"Benchmark results saved to: {filename}")
        return filename
    
    def compare_benchmarks(self, before_file: str, after_file: str) -> Dict:
        """Compare benchmark results before and after optimization"""
        
        with open(before_file, 'r') as f:
            before_data = json.load(f)
        
        with open(after_file, 'r') as f:
            after_data = json.load(f)
        
        before_results = {r['name']: r for r in before_data['benchmark_results']}
        after_results = {r['name']: r for r in after_data['benchmark_results']}
        
        comparisons = []
        
        for query_name in before_results:
            if query_name in after_results:
                before = before_results[query_name]
                after = after_results[query_name]
                
                improvement_pct = ((before['avg_time_ms'] - after['avg_time_ms']) / before['avg_time_ms']) * 100
                
                comparison = {
                    'query_name': query_name,
                    'description': before['description'],
                    'before_avg_ms': before['avg_time_ms'],
                    'after_avg_ms': after['avg_time_ms'],
                    'improvement_ms': before['avg_time_ms'] - after['avg_time_ms'],
                    'improvement_percent': improvement_pct,
                    'result_count': before['result_count']
                }
                
                comparisons.append(comparison)
        
        return {
            'before_file': before_file,
            'after_file': after_file,
            'comparisons': comparisons,
            'overall_improvement': statistics.mean([c['improvement_percent'] for c in comparisons])
        }

def run_benchmark(db_path: str, save_results: bool = True) -> List[Dict]:
    """Run performance benchmark on the database"""
    
    if not Path(db_path).exists():
        print(f"Database file not found: {db_path}")
        return []
    
    print(f"Running performance benchmark on: {db_path}")
    print("=" * 60)
    
    with QueryBenchmark(db_path) as benchmark:
        results = benchmark.benchmark_common_queries()
        
        if save_results:
            filename = benchmark.save_benchmark_results(results)
            return results, filename
        
        return results

def print_benchmark_summary(results: List[Dict]):
    """Print a summary of benchmark results"""
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    
    total_avg_time = sum(r['avg_time_ms'] for r in results)
    
    print(f"Total queries tested: {len(results)}")
    print(f"Total average execution time: {total_avg_time:.2f}ms")
    print(f"Average time per query: {total_avg_time/len(results):.2f}ms")
    
    print("\nSlowest queries:")
    sorted_results = sorted(results, key=lambda x: x['avg_time_ms'], reverse=True)
    for i, result in enumerate(sorted_results[:5]):
        print(f"  {i+1}. {result['name']}: {result['avg_time_ms']:.2f}ms")

if __name__ == "__main__":
    import sys
    
    # Default database path
    default_db_path = "iron_chef_japan.db"
    
    # Use command line argument if provided
    db_path = sys.argv[1] if len(sys.argv) > 1 else default_db_path
    
    results, filename = run_benchmark(db_path)
    print_benchmark_summary(results)
    
    print(f"\nRun the migration script and then benchmark again to compare:")
    print(f"python database_migration_add_indices.py {db_path}")
    print(f"python query_performance_benchmark.py {db_path}")