"""
Connection Pool Monitoring and Statistics Module
Provides comprehensive monitoring, statistics collection, and health checking
for the Iron Chef Database connection pool.

Features:
- Real-time pool statistics and metrics
- Performance monitoring and alerting
- Health check dashboard
- Historical data collection
- Performance recommendations
- Export capabilities for analysis
"""

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from collections import defaultdict, deque

from connection_pool import ThreadSafeConnectionPool, PoolConfig, get_global_pool


logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics collected over time"""
    timestamp: datetime
    active_connections: int
    idle_connections: int
    total_connections: int
    connections_borrowed: int
    connections_returned: int
    validation_failures: int
    timeout_errors: int
    average_borrow_time: float
    peak_active_connections: int
    cpu_usage: float = 0.0
    memory_usage: float = 0.0


@dataclass
class HealthStatus:
    """Health status of the connection pool"""
    is_healthy: bool
    health_score: float  # 0-100
    issues: List[str]
    warnings: List[str]
    recommendations: List[str]
    last_check: datetime


@dataclass
class Alert:
    """Alert for connection pool issues"""
    severity: str  # INFO, WARNING, ERROR, CRITICAL
    message: str
    timestamp: datetime
    metric_name: str
    current_value: Any
    threshold_value: Any
    is_resolved: bool = False
    resolved_at: Optional[datetime] = None


class PoolMonitor:
    """
    Comprehensive monitoring system for connection pools with real-time
    statistics, alerting, and performance analysis.
    """
    
    def __init__(self, pool: Optional[ThreadSafeConnectionPool] = None,
                 collection_interval: float = 10.0,
                 history_size: int = 1000,
                 enable_alerts: bool = True):
        """
        Initialize the pool monitor.
        
        Args:
            pool: Connection pool to monitor (uses global pool if None)
            collection_interval: Interval between metric collections (seconds)
            history_size: Maximum number of historical metrics to keep
            enable_alerts: Whether to enable alerting system
        """
        self.pool = pool or get_global_pool()
        self.collection_interval = collection_interval
        self.history_size = history_size
        self.enable_alerts = enable_alerts
        
        # Monitoring state
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        # Data storage
        self._metrics_history: deque = deque(maxlen=history_size)
        self._alerts: List[Alert] = []
        self._health_status: Optional[HealthStatus] = None
        
        # Alert thresholds (configurable)
        self.alert_thresholds = {
            'connection_utilization': 80.0,  # % of max connections
            'average_borrow_time': 5.0,      # seconds
            'validation_failure_rate': 5.0,  # %
            'timeout_error_rate': 2.0,       # %
            'queue_wait_time': 10.0,         # seconds
            'unhealthy_connections': 10.0    # %
        }
        
        # Alert callbacks
        self._alert_callbacks: List[Callable[[Alert], None]] = []
        
        # Statistics aggregation
        self._lock = threading.Lock()
        self._last_stats: Optional[Dict[str, Any]] = None
    
    def start_monitoring(self):
        """Start the monitoring thread"""
        if self._monitoring:
            logger.warning("Monitor already running")
            return
        
        if not self.pool:
            logger.error("No connection pool available for monitoring")
            return
        
        self._monitoring = True
        self._shutdown_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            name="PoolMonitor",
            daemon=True
        )
        self._monitor_thread.start()
        logger.info("Connection pool monitoring started")
    
    def stop_monitoring(self):
        """Stop the monitoring thread"""
        if not self._monitoring:
            return
        
        self._monitoring = False
        self._shutdown_event.set()
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)
        
        logger.info("Connection pool monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self._monitoring and not self._shutdown_event.is_set():
            try:
                # Collect metrics
                metrics = self._collect_metrics()
                if metrics:
                    with self._lock:
                        self._metrics_history.append(metrics)
                    
                    # Check for alerts
                    if self.enable_alerts:
                        self._check_alerts(metrics)
                    
                    # Update health status
                    self._update_health_status(metrics)
                
                # Wait for next collection
                self._shutdown_event.wait(self.collection_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(1.0)  # Brief pause before retrying
    
    def _collect_metrics(self) -> Optional[PerformanceMetrics]:
        """Collect current performance metrics"""
        try:
            if not self.pool:
                return None
            
            # Get pool statistics
            pool_stats = self.pool.get_statistics()
            pool_status = self.pool.get_pool_status()
            
            if not pool_stats or not pool_status:
                return None
            
            # Create metrics object
            metrics = PerformanceMetrics(
                timestamp=datetime.now(),
                active_connections=pool_status.get('active_connections', 0),
                idle_connections=pool_status.get('idle_connections', 0),
                total_connections=pool_status.get('total_connections', 0),
                connections_borrowed=pool_stats.get('total_connections_borrowed', 0),
                connections_returned=pool_stats.get('total_connections_returned', 0),
                validation_failures=pool_stats.get('total_validation_failures', 0),
                timeout_errors=pool_stats.get('total_timeout_errors', 0),
                average_borrow_time=pool_stats.get('average_borrow_time_ms', 0.0) / 1000.0,
                peak_active_connections=pool_stats.get('peak_active_connections', 0)
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            return None
    
    def _check_alerts(self, metrics: PerformanceMetrics):
        """Check for alert conditions"""
        try:
            new_alerts = []
            
            # Connection utilization alert
            if self.pool:
                max_connections = self.pool.config.max_connections
                utilization = (metrics.active_connections / max_connections) * 100
                
                if utilization > self.alert_thresholds['connection_utilization']:
                    alert = Alert(
                        severity='WARNING' if utilization < 95 else 'CRITICAL',
                        message=f"High connection utilization: {utilization:.1f}%",
                        timestamp=datetime.now(),
                        metric_name='connection_utilization',
                        current_value=utilization,
                        threshold_value=self.alert_thresholds['connection_utilization']
                    )
                    new_alerts.append(alert)
            
            # Average borrow time alert
            if metrics.average_borrow_time > self.alert_thresholds['average_borrow_time']:
                alert = Alert(
                    severity='WARNING',
                    message=f"High average borrow time: {metrics.average_borrow_time:.2f}s",
                    timestamp=datetime.now(),
                    metric_name='average_borrow_time',
                    current_value=metrics.average_borrow_time,
                    threshold_value=self.alert_thresholds['average_borrow_time']
                )
                new_alerts.append(alert)
            
            # Validation failure rate alert
            if metrics.connections_borrowed > 0:
                failure_rate = (metrics.validation_failures / metrics.connections_borrowed) * 100
                if failure_rate > self.alert_thresholds['validation_failure_rate']:
                    alert = Alert(
                        severity='ERROR',
                        message=f"High validation failure rate: {failure_rate:.1f}%",
                        timestamp=datetime.now(),
                        metric_name='validation_failure_rate',
                        current_value=failure_rate,
                        threshold_value=self.alert_thresholds['validation_failure_rate']
                    )
                    new_alerts.append(alert)
            
            # Timeout error rate alert
            if metrics.connections_borrowed > 0:
                timeout_rate = (metrics.timeout_errors / metrics.connections_borrowed) * 100
                if timeout_rate > self.alert_thresholds['timeout_error_rate']:
                    alert = Alert(
                        severity='ERROR',
                        message=f"High timeout error rate: {timeout_rate:.1f}%",
                        timestamp=datetime.now(),
                        metric_name='timeout_error_rate',
                        current_value=timeout_rate,
                        threshold_value=self.alert_thresholds['timeout_error_rate']
                    )
                    new_alerts.append(alert)
            
            # Add new alerts and trigger callbacks
            for alert in new_alerts:
                self._alerts.append(alert)
                self._trigger_alert_callbacks(alert)
                
                logger.log(
                    logging.WARNING if alert.severity in ['WARNING'] else logging.ERROR,
                    f"Pool Alert [{alert.severity}]: {alert.message}"
                )
            
        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
    
    def _update_health_status(self, metrics: PerformanceMetrics):
        """Update the overall health status"""
        try:
            issues = []
            warnings = []
            recommendations = []
            health_score = 100.0
            
            # Check various health indicators
            if self.pool:
                max_connections = self.pool.config.max_connections
                utilization = (metrics.active_connections / max_connections) * 100
                
                # Connection utilization
                if utilization > 90:
                    issues.append("Very high connection utilization")
                    health_score -= 20
                elif utilization > 80:
                    warnings.append("High connection utilization")
                    health_score -= 10
                
                # Borrow time
                if metrics.average_borrow_time > 5.0:
                    issues.append("High average connection borrow time")
                    health_score -= 15
                    recommendations.append("Consider increasing pool size")
                elif metrics.average_borrow_time > 2.0:
                    warnings.append("Elevated connection borrow time")
                    health_score -= 5
                
                # Error rates
                if metrics.connections_borrowed > 0:
                    validation_failure_rate = (metrics.validation_failures / metrics.connections_borrowed) * 100
                    timeout_error_rate = (metrics.timeout_errors / metrics.connections_borrowed) * 100
                    
                    if validation_failure_rate > 5.0:
                        issues.append(f"High validation failure rate: {validation_failure_rate:.1f}%")
                        health_score -= 15
                        recommendations.append("Check database connectivity and health")
                    
                    if timeout_error_rate > 2.0:
                        issues.append(f"High timeout error rate: {timeout_error_rate:.1f}%")
                        health_score -= 10
                        recommendations.append("Increase connection timeout or pool size")
                
                # Pool configuration recommendations
                if metrics.peak_active_connections > max_connections * 0.9:
                    recommendations.append("Consider increasing maximum pool size")
                
                if len(self._metrics_history) > 10:
                    recent_metrics = list(self._metrics_history)[-10:]
                    avg_active = sum(m.active_connections for m in recent_metrics) / len(recent_metrics)
                    if avg_active < max_connections * 0.3:
                        recommendations.append("Consider reducing pool size to save resources")
            
            # Calculate final health status
            is_healthy = health_score >= 70 and len(issues) == 0
            health_score = max(0.0, min(100.0, health_score))
            
            self._health_status = HealthStatus(
                is_healthy=is_healthy,
                health_score=health_score,
                issues=issues,
                warnings=warnings,
                recommendations=recommendations,
                last_check=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Error updating health status: {e}")
    
    def _trigger_alert_callbacks(self, alert: Alert):
        """Trigger registered alert callbacks"""
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")
    
    def add_alert_callback(self, callback: Callable[[Alert], None]):
        """Add an alert callback function"""
        self._alert_callbacks.append(callback)
    
    def remove_alert_callback(self, callback: Callable[[Alert], None]):
        """Remove an alert callback function"""
        if callback in self._alert_callbacks:
            self._alert_callbacks.remove(callback)
    
    def get_current_metrics(self) -> Optional[PerformanceMetrics]:
        """Get the most recent metrics"""
        with self._lock:
            return self._metrics_history[-1] if self._metrics_history else None
    
    def get_metrics_history(self, duration: Optional[timedelta] = None) -> List[PerformanceMetrics]:
        """
        Get metrics history for a specified duration.
        
        Args:
            duration: Time period to retrieve (None for all available)
            
        Returns:
            List of metrics within the specified duration
        """
        with self._lock:
            if not duration:
                return list(self._metrics_history)
            
            cutoff_time = datetime.now() - duration
            return [m for m in self._metrics_history if m.timestamp >= cutoff_time]
    
    def get_health_status(self) -> Optional[HealthStatus]:
        """Get the current health status"""
        return self._health_status
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active (unresolved) alerts"""
        return [alert for alert in self._alerts if not alert.is_resolved]
    
    def get_alert_history(self, duration: Optional[timedelta] = None) -> List[Alert]:
        """
        Get alert history for a specified duration.
        
        Args:
            duration: Time period to retrieve (None for all available)
            
        Returns:
            List of alerts within the specified duration
        """
        if not duration:
            return list(self._alerts)
        
        cutoff_time = datetime.now() - duration
        return [alert for alert in self._alerts if alert.timestamp >= cutoff_time]
    
    def resolve_alert(self, alert: Alert):
        """Mark an alert as resolved"""
        alert.is_resolved = True
        alert.resolved_at = datetime.now()
    
    def get_performance_summary(self, duration: timedelta = timedelta(hours=1)) -> Dict[str, Any]:
        """
        Get a performance summary for the specified duration.
        
        Args:
            duration: Time period to analyze
            
        Returns:
            Dictionary containing performance summary
        """
        metrics = self.get_metrics_history(duration)
        
        if not metrics:
            return {'error': 'No metrics available'}
        
        # Calculate aggregated statistics
        total_borrowed = metrics[-1].connections_borrowed - metrics[0].connections_borrowed
        total_returned = metrics[-1].connections_returned - metrics[0].connections_returned
        total_failures = metrics[-1].validation_failures - metrics[0].validation_failures
        total_timeouts = metrics[-1].timeout_errors - metrics[0].timeout_errors
        
        avg_active = sum(m.active_connections for m in metrics) / len(metrics)
        avg_borrow_time = sum(m.average_borrow_time for m in metrics) / len(metrics)
        peak_active = max(m.active_connections for m in metrics)
        
        efficiency = (total_returned / max(total_borrowed, 1)) * 100
        failure_rate = (total_failures / max(total_borrowed, 1)) * 100
        timeout_rate = (total_timeouts / max(total_borrowed, 1)) * 100
        
        return {
            'duration_hours': duration.total_seconds() / 3600,
            'sample_count': len(metrics),
            'connections': {
                'average_active': round(avg_active, 1),
                'peak_active': peak_active,
                'total_borrowed': total_borrowed,
                'total_returned': total_returned,
                'efficiency_percent': round(efficiency, 2)
            },
            'performance': {
                'average_borrow_time_ms': round(avg_borrow_time * 1000, 2),
                'validation_failure_rate_percent': round(failure_rate, 2),
                'timeout_error_rate_percent': round(timeout_rate, 2)
            },
            'health': asdict(self._health_status) if self._health_status else None,
            'active_alerts': len(self.get_active_alerts()),
            'total_alerts': len(self._alerts)
        }
    
    def export_metrics(self, filepath: str, format_type: str = 'json',
                      duration: Optional[timedelta] = None):
        """
        Export metrics to a file.
        
        Args:
            filepath: Output file path
            format_type: Export format ('json' or 'csv')
            duration: Time period to export (None for all available)
        """
        metrics = self.get_metrics_history(duration)
        
        if format_type.lower() == 'json':
            data = {
                'export_timestamp': datetime.now().isoformat(),
                'duration_requested': duration.total_seconds() if duration else None,
                'metrics_count': len(metrics),
                'metrics': [asdict(m) for m in metrics],
                'alerts': [asdict(a) for a in self.get_alert_history(duration)],
                'health_status': asdict(self._health_status) if self._health_status else None
            }
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        
        elif format_type.lower() == 'csv':
            import csv
            
            with open(filepath, 'w', newline='') as f:
                if metrics:
                    writer = csv.DictWriter(f, fieldnames=asdict(metrics[0]).keys())
                    writer.writeheader()
                    for metric in metrics:
                        writer.writerow({k: str(v) for k, v in asdict(metric).items()})
        
        else:
            raise ValueError(f"Unsupported export format: {format_type}")
        
        logger.info(f"Exported {len(metrics)} metrics to {filepath}")
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive data for a monitoring dashboard"""
        return {
            'current_metrics': asdict(self.get_current_metrics()) if self.get_current_metrics() else None,
            'health_status': asdict(self._health_status) if self._health_status else None,
            'active_alerts': [asdict(alert) for alert in self.get_active_alerts()],
            'recent_performance': self.get_performance_summary(timedelta(minutes=30)),
            'pool_status': self.pool.get_pool_status() if self.pool else None,
            'monitoring_info': {
                'is_monitoring': self._monitoring,
                'collection_interval': self.collection_interval,
                'history_size': len(self._metrics_history),
                'alert_thresholds': self.alert_thresholds
            }
        }


# Global monitor instance
_global_monitor: Optional[PoolMonitor] = None
_monitor_lock = threading.Lock()


def initialize_global_monitor(pool: Optional[ThreadSafeConnectionPool] = None,
                             **kwargs) -> PoolMonitor:
    """Initialize the global pool monitor"""
    global _global_monitor
    
    with _monitor_lock:
        if _global_monitor:
            _global_monitor.stop_monitoring()
        
        _global_monitor = PoolMonitor(pool, **kwargs)
        _global_monitor.start_monitoring()
        
        return _global_monitor


def get_global_monitor() -> Optional[PoolMonitor]:
    """Get the global pool monitor instance"""
    return _global_monitor


def shutdown_global_monitor():
    """Shutdown the global pool monitor"""
    global _global_monitor
    
    with _monitor_lock:
        if _global_monitor:
            _global_monitor.stop_monitoring()
            _global_monitor = None