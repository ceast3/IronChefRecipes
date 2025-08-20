#!/usr/bin/env python3
"""
Query Optimization Utilities
Provides tools for analyzing and optimizing database queries in the Iron Chef Recipe Database.
"""

import sqlite3
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class IndexType(Enum):
    SINGLE_COLUMN = "single"
    MULTI_COLUMN = "multi"
    PARTIAL = "partial"
    EXPRESSION = "expression"

@dataclass
class IndexRecommendation:
    table_name: str
    columns: List[str]
    index_type: IndexType
    reason: str
    estimated_benefit: str
    sql_statement: str

class QueryOptimizer:
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
    
    def analyze_query(self, query: str, params: tuple = None) -> Dict[str, Any]:
        """Analyze a query and provide optimization recommendations"""
        cursor = self.connection.cursor()
        
        # Get query plan
        explain_query = f"EXPLAIN QUERY PLAN {query}"
        if params:
            cursor.execute(explain_query, params)
        else:
            cursor.execute(explain_query)
        
        query_plan = [dict(row) for row in cursor.fetchall()]
        
        # Analyze the query plan for optimization opportunities
        analysis = {
            'query': query,
            'query_plan': query_plan,
            'uses_index': self._check_index_usage(query_plan),
            'table_scans': self._find_table_scans(query_plan),
            'join_analysis': self._analyze_joins(query_plan),
            'recommendations': self._generate_recommendations(query, query_plan)
        }
        
        return analysis
    
    def _check_index_usage(self, query_plan: List[Dict]) -> bool:
        """Check if the query uses any indexes"""
        for step in query_plan:
            detail = step.get('detail', '').lower()
            if 'using index' in detail or 'using covering index' in detail:
                return True
        return False
    
    def _find_table_scans(self, query_plan: List[Dict]) -> List[str]:
        """Find tables that are being scanned instead of using indexes"""
        table_scans = []
        for step in query_plan:
            detail = step.get('detail', '').lower()
            if 'scan table' in detail:
                # Extract table name from detail
                match = re.search(r'scan table (\w+)', detail)
                if match:
                    table_scans.append(match.group(1))
        return table_scans
    
    def _analyze_joins(self, query_plan: List[Dict]) -> Dict[str, Any]:
        """Analyze JOIN operations in the query plan"""
        joins = []
        for step in query_plan:
            detail = step.get('detail', '').lower()
            if 'search table' in detail and 'using index' in detail:
                joins.append({
                    'type': 'indexed_join',
                    'detail': step.get('detail')
                })
            elif 'search table' in detail:
                joins.append({
                    'type': 'table_scan_join',
                    'detail': step.get('detail')
                })
        
        return {
            'total_joins': len(joins),
            'indexed_joins': len([j for j in joins if j['type'] == 'indexed_join']),
            'table_scan_joins': len([j for j in joins if j['type'] == 'table_scan_join']),
            'join_details': joins
        }
    
    def _generate_recommendations(self, query: str, query_plan: List[Dict]) -> List[IndexRecommendation]:
        """Generate index recommendations based on query analysis"""
        recommendations = []
        
        # Analyze WHERE clauses
        where_recommendations = self._analyze_where_clauses(query)
        recommendations.extend(where_recommendations)
        
        # Analyze JOIN conditions
        join_recommendations = self._analyze_join_conditions(query)
        recommendations.extend(join_recommendations)
        
        # Analyze ORDER BY clauses
        order_recommendations = self._analyze_order_by(query)
        recommendations.extend(order_recommendations)
        
        return recommendations
    
    def _analyze_where_clauses(self, query: str) -> List[IndexRecommendation]:
        """Analyze WHERE clauses for index opportunities"""
        recommendations = []
        
        # Simple pattern matching for common WHERE patterns
        # This is a basic implementation - a full parser would be more comprehensive
        
        # Look for equality conditions
        eq_pattern = r'WHERE\s+(\w+)\.(\w+)\s*=\s*\?'
        matches = re.finditer(eq_pattern, query, re.IGNORECASE)
        for match in matches:
            table, column = match.groups()
            recommendations.append(IndexRecommendation(
                table_name=table,
                columns=[column],
                index_type=IndexType.SINGLE_COLUMN,
                reason=f"Equality condition in WHERE clause on {table}.{column}",
                estimated_benefit="High - exact match lookups",
                sql_statement=f"CREATE INDEX idx_{table}_{column} ON {table}({column})"
            ))
        
        # Look for LIKE conditions
        like_pattern = r'WHERE\s+(\w+)\.(\w+)\s+LIKE\s+\?'
        matches = re.finditer(like_pattern, query, re.IGNORECASE)
        for match in matches:
            table, column = match.groups()
            recommendations.append(IndexRecommendation(
                table_name=table,
                columns=[column],
                index_type=IndexType.SINGLE_COLUMN,
                reason=f"LIKE condition in WHERE clause on {table}.{column}",
                estimated_benefit="Medium - prefix matching for LIKE queries",
                sql_statement=f"CREATE INDEX idx_{table}_{column} ON {table}({column})"
            ))
        
        return recommendations
    
    def _analyze_join_conditions(self, query: str) -> List[IndexRecommendation]:
        """Analyze JOIN conditions for index opportunities"""
        recommendations = []
        
        # Look for JOIN conditions
        join_pattern = r'JOIN\s+(\w+)\s+\w+\s+ON\s+\w+\.(\w+)\s*=\s*\w+\.(\w+)'
        matches = re.finditer(join_pattern, query, re.IGNORECASE)
        for match in matches:
            table, column1, column2 = match.groups()
            recommendations.append(IndexRecommendation(
                table_name=table,
                columns=[column1],
                index_type=IndexType.SINGLE_COLUMN,
                reason=f"JOIN condition on {table}.{column1}",
                estimated_benefit="High - JOIN performance improvement",
                sql_statement=f"CREATE INDEX idx_{table}_{column1} ON {table}({column1})"
            ))
        
        return recommendations
    
    def _analyze_order_by(self, query: str) -> List[IndexRecommendation]:
        """Analyze ORDER BY clauses for index opportunities"""
        recommendations = []
        
        # Look for ORDER BY clauses
        order_pattern = r'ORDER\s+BY\s+(\w+)\.(\w+)'
        matches = re.finditer(order_pattern, query, re.IGNORECASE)
        for match in matches:
            table, column = match.groups()
            recommendations.append(IndexRecommendation(
                table_name=table,
                columns=[column],
                index_type=IndexType.SINGLE_COLUMN,
                reason=f"ORDER BY clause on {table}.{column}",
                estimated_benefit="Medium - sorting performance improvement",
                sql_statement=f"CREATE INDEX idx_{table}_{column} ON {table}({column})"
            ))
        
        return recommendations
    
    def get_existing_indices(self) -> Dict[str, List[Dict]]:
        """Get all existing indices grouped by table"""
        cursor = self.connection.cursor()
        cursor.execute("""
            SELECT name, tbl_name, sql 
            FROM sqlite_master 
            WHERE type='index' AND sql IS NOT NULL
            ORDER BY tbl_name, name
        """)
        
        indices = {}
        for row in cursor.fetchall():
            table_name = row[1]
            if table_name not in indices:
                indices[table_name] = []
            indices[table_name].append({
                'name': row[0],
                'table': row[1],
                'sql': row[2]
            })
        
        return indices
    
    def suggest_composite_indices(self, query: str) -> List[IndexRecommendation]:
        """Suggest composite indices for complex queries"""
        recommendations = []
        
        # Look for queries with multiple WHERE conditions
        # This is a simplified approach - real implementation would parse the AST
        
        # Pattern for WHERE with AND conditions
        and_pattern = r'WHERE\s+(\w+)\.(\w+)\s*=\s*\?\s+AND\s+(\w+)\.(\w+)\s*[=><!]'
        matches = re.finditer(and_pattern, query, re.IGNORECASE)
        for match in matches:
            table1, col1, table2, col2 = match.groups()
            if table1 == table2:  # Same table
                recommendations.append(IndexRecommendation(
                    table_name=table1,
                    columns=[col1, col2],
                    index_type=IndexType.MULTI_COLUMN,
                    reason=f"Multiple conditions on {table1}",
                    estimated_benefit="High - composite index for multiple conditions",
                    sql_statement=f"CREATE INDEX idx_{table1}_{col1}_{col2} ON {table1}({col1}, {col2})"
                ))
        
        return recommendations
    
    def analyze_slow_queries(self, threshold_ms: float = 100.0) -> List[Dict]:
        """Identify and analyze potentially slow queries from the application"""
        # This would typically analyze query logs, but for demo purposes,
        # we'll analyze common query patterns from the database module
        
        from query_performance_benchmark import QueryBenchmark
        
        with QueryBenchmark(self.db_path) as benchmark:
            results = benchmark.benchmark_common_queries()
        
        slow_queries = []
        for result in results:
            if result['avg_time_ms'] > threshold_ms:
                analysis = self.analyze_query(result['query'], result['params'])
                slow_queries.append({
                    'query_name': result['name'],
                    'avg_time_ms': result['avg_time_ms'],
                    'analysis': analysis
                })
        
        return slow_queries
    
    def generate_optimization_report(self) -> Dict[str, Any]:
        """Generate a comprehensive optimization report"""
        
        # Get existing indices
        existing_indices = self.get_existing_indices()
        
        # Analyze slow queries
        slow_queries = self.analyze_slow_queries()
        
        # Get database statistics
        cursor = self.connection.cursor()
        
        # Table sizes
        tables = ['iron_chefs', 'competitors', 'episodes', 'dishes', 'recipes', 'ingredients', 'dish_ingredients']
        table_stats = {}
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                table_stats[table] = cursor.fetchone()[0]
            except sqlite3.Error:
                table_stats[table] = 0
        
        report = {
            'timestamp': sqlite3.datetime.datetime.now().isoformat(),
            'database_path': self.db_path,
            'table_statistics': table_stats,
            'existing_indices': existing_indices,
            'slow_queries': slow_queries,
            'total_indices': sum(len(indices) for indices in existing_indices.values()),
            'recommendations_summary': {
                'total_slow_queries': len(slow_queries),
                'queries_needing_optimization': len([q for q in slow_queries if q['avg_time_ms'] > 50]),
                'critical_queries': len([q for q in slow_queries if q['avg_time_ms'] > 200])
            }
        }
        
        return report

def print_optimization_report(db_path: str):
    """Print a formatted optimization report"""
    
    with QueryOptimizer(db_path) as optimizer:
        report = optimizer.generate_optimization_report()
    
    print("=" * 80)
    print("DATABASE OPTIMIZATION REPORT")
    print("=" * 80)
    print(f"Database: {report['database_path']}")
    print(f"Generated: {report['timestamp']}")
    print()
    
    print("TABLE STATISTICS:")
    print("-" * 40)
    for table, count in report['table_statistics'].items():
        print(f"  {table:<20}: {count:>8,} rows")
    print()
    
    print("EXISTING INDICES:")
    print("-" * 40)
    for table, indices in report['existing_indices'].items():
        print(f"  {table}:")
        for idx in indices:
            print(f"    - {idx['name']}")
    print(f"Total indices: {report['total_indices']}")
    print()
    
    print("PERFORMANCE ANALYSIS:")
    print("-" * 40)
    print(f"Total queries analyzed: {len(report['slow_queries'])}")
    print(f"Queries needing optimization: {report['recommendations_summary']['queries_needing_optimization']}")
    print(f"Critical slow queries: {report['recommendations_summary']['critical_queries']}")
    print()
    
    if report['slow_queries']:
        print("SLOW QUERIES DETAILS:")
        print("-" * 40)
        for query in report['slow_queries']:
            print(f"  {query['query_name']}: {query['avg_time_ms']:.2f}ms")
            if not query['analysis']['uses_index']:
                print("    ⚠️  No index usage detected")
            if query['analysis']['table_scans']:
                print(f"    ⚠️  Table scans: {', '.join(query['analysis']['table_scans'])}")
        print()

if __name__ == "__main__":
    import sys
    
    # Default database path
    default_db_path = "iron_chef_japan.db"
    
    # Use command line argument if provided
    db_path = sys.argv[1] if len(sys.argv) > 1 else default_db_path
    
    print_optimization_report(db_path)