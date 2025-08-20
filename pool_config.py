"""
Connection Pool Configuration Management System
Provides centralized configuration management for connection pool settings with
environment-based configuration, validation, and runtime updates.

Features:
- Environment variable configuration
- Configuration validation and defaults
- Runtime configuration updates
- Configuration profiles for different environments
- Configuration export and import
- Hot reload capabilities
"""

import os
import json
import logging
import threading
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, asdict, fields
from enum import Enum
from pathlib import Path

from connection_pool import PoolConfig


logger = logging.getLogger(__name__)


class EnvironmentType(Enum):
    """Environment types for configuration profiles"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class DatabaseConfig:
    """Database-specific configuration settings"""
    db_path: str = "iron_chef_japan.db"
    sqlite_timeout: float = 30.0
    sqlite_journal_mode: str = "WAL"
    sqlite_synchronous: str = "NORMAL"
    sqlite_cache_size: int = 10000
    sqlite_temp_store: str = "MEMORY"
    foreign_keys: bool = True
    
    def get_pragma_settings(self) -> Dict[str, Any]:
        """Get SQLite PRAGMA settings"""
        return {
            'journal_mode': self.sqlite_journal_mode,
            'synchronous': self.sqlite_synchronous,
            'cache_size': self.sqlite_cache_size,
            'temp_store': self.sqlite_temp_store,
            'foreign_keys': 'ON' if self.foreign_keys else 'OFF'
        }


@dataclass
class MonitoringConfig:
    """Monitoring and statistics configuration"""
    enable_monitoring: bool = True
    collection_interval: float = 10.0
    history_size: int = 1000
    enable_alerts: bool = True
    enable_statistics: bool = True
    enable_leak_detection: bool = True
    export_interval: float = 3600.0  # 1 hour
    export_directory: str = "pool_exports"
    
    # Alert thresholds
    connection_utilization_threshold: float = 80.0
    average_borrow_time_threshold: float = 5.0
    validation_failure_rate_threshold: float = 5.0
    timeout_error_rate_threshold: float = 2.0
    queue_wait_time_threshold: float = 10.0
    unhealthy_connections_threshold: float = 10.0


@dataclass
class ApplicationConfig:
    """Application-level configuration"""
    app_name: str = "Iron Chef Recipe Database"
    environment: EnvironmentType = EnvironmentType.DEVELOPMENT
    debug: bool = False
    log_level: str = "INFO"
    secret_key: str = "iron-chef-secure-key-change-in-production"
    
    # Flask settings
    flask_host: str = "0.0.0.0"
    flask_port: int = 5000
    flask_threaded: bool = True
    
    # Security settings
    csrf_enabled: bool = True
    session_timeout: int = 3600  # 1 hour
    
    # Performance settings
    max_content_length: int = 16 * 1024 * 1024  # 16MB
    request_timeout: float = 30.0


@dataclass
class CompleteConfig:
    """Complete application configuration"""
    pool: PoolConfig
    database: DatabaseConfig
    monitoring: MonitoringConfig
    application: ApplicationConfig
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            'pool': asdict(self.pool),
            'database': asdict(self.database),
            'monitoring': asdict(self.monitoring),
            'application': asdict(self.application)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CompleteConfig':
        """Create configuration from dictionary"""
        return cls(
            pool=PoolConfig(**data.get('pool', {})),
            database=DatabaseConfig(**data.get('database', {})),
            monitoring=MonitoringConfig(**data.get('monitoring', {})),
            application=ApplicationConfig(**data.get('application', {}))
        )


class ConfigManager:
    """
    Configuration manager for the Iron Chef application with support for
    environment-based configuration, validation, and runtime updates.
    """
    
    def __init__(self, config_file: Optional[str] = None, 
                 environment: Optional[EnvironmentType] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Optional configuration file path
            environment: Environment type (defaults to environment variable)
        """
        self._lock = threading.RLock()
        self._config: Optional[CompleteConfig] = None
        self._config_file = config_file
        self._environment = environment or self._detect_environment()
        self._watchers = []  # Configuration change watchers
        
        # Load configuration
        self.reload()
    
    def _detect_environment(self) -> EnvironmentType:
        """Detect environment from environment variables"""
        env_str = os.getenv('FLASK_ENV', os.getenv('APP_ENV', 'development')).lower()
        
        env_mapping = {
            'development': EnvironmentType.DEVELOPMENT,
            'dev': EnvironmentType.DEVELOPMENT,
            'testing': EnvironmentType.TESTING,
            'test': EnvironmentType.TESTING,
            'staging': EnvironmentType.STAGING,
            'stage': EnvironmentType.STAGING,
            'production': EnvironmentType.PRODUCTION,
            'prod': EnvironmentType.PRODUCTION
        }
        
        return env_mapping.get(env_str, EnvironmentType.DEVELOPMENT)
    
    def _load_from_environment(self) -> CompleteConfig:
        """Load configuration from environment variables"""
        
        # Pool configuration
        pool_config = PoolConfig(
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
        
        # Database configuration
        database_config = DatabaseConfig(
            db_path=os.getenv('DATABASE_PATH', 'iron_chef_japan.db'),
            sqlite_timeout=float(os.getenv('SQLITE_TIMEOUT', '30.0')),
            sqlite_journal_mode=os.getenv('SQLITE_JOURNAL_MODE', 'WAL'),
            sqlite_synchronous=os.getenv('SQLITE_SYNCHRONOUS', 'NORMAL'),
            sqlite_cache_size=int(os.getenv('SQLITE_CACHE_SIZE', '10000')),
            sqlite_temp_store=os.getenv('SQLITE_TEMP_STORE', 'MEMORY'),
            foreign_keys=os.getenv('SQLITE_FOREIGN_KEYS', 'true').lower() == 'true'
        )
        
        # Monitoring configuration
        monitoring_config = MonitoringConfig(
            enable_monitoring=os.getenv('POOL_MONITORING_ENABLED', 'true').lower() == 'true',
            collection_interval=float(os.getenv('POOL_MONITORING_INTERVAL', '10.0')),
            history_size=int(os.getenv('POOL_MONITORING_HISTORY_SIZE', '1000')),
            enable_alerts=os.getenv('POOL_ALERTS_ENABLED', 'true').lower() == 'true',
            enable_statistics=os.getenv('POOL_STATISTICS_ENABLED', 'true').lower() == 'true',
            enable_leak_detection=os.getenv('POOL_LEAK_DETECTION_ENABLED', 'true').lower() == 'true',
            export_interval=float(os.getenv('POOL_EXPORT_INTERVAL', '3600.0')),
            export_directory=os.getenv('POOL_EXPORT_DIRECTORY', 'pool_exports'),
            connection_utilization_threshold=float(os.getenv('POOL_ALERT_CONNECTION_UTILIZATION', '80.0')),
            average_borrow_time_threshold=float(os.getenv('POOL_ALERT_BORROW_TIME', '5.0')),
            validation_failure_rate_threshold=float(os.getenv('POOL_ALERT_VALIDATION_FAILURE', '5.0')),
            timeout_error_rate_threshold=float(os.getenv('POOL_ALERT_TIMEOUT_ERROR', '2.0')),
            queue_wait_time_threshold=float(os.getenv('POOL_ALERT_QUEUE_WAIT', '10.0')),
            unhealthy_connections_threshold=float(os.getenv('POOL_ALERT_UNHEALTHY_CONNECTIONS', '10.0'))
        )
        
        # Application configuration
        application_config = ApplicationConfig(
            app_name=os.getenv('APP_NAME', 'Iron Chef Recipe Database'),
            environment=self._environment,
            debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true',
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            secret_key=os.getenv('SECRET_KEY', 'iron-chef-secure-key-change-in-production'),
            flask_host=os.getenv('FLASK_HOST', '0.0.0.0'),
            flask_port=int(os.getenv('FLASK_PORT', '5000')),
            flask_threaded=os.getenv('FLASK_THREADED', 'true').lower() == 'true',
            csrf_enabled=os.getenv('CSRF_ENABLED', 'true').lower() == 'true',
            session_timeout=int(os.getenv('SESSION_TIMEOUT', '3600')),
            max_content_length=int(os.getenv('MAX_CONTENT_LENGTH', str(16 * 1024 * 1024))),
            request_timeout=float(os.getenv('REQUEST_TIMEOUT', '30.0'))
        )
        
        return CompleteConfig(
            pool=pool_config,
            database=database_config,
            monitoring=monitoring_config,
            application=application_config
        )
    
    def _load_from_file(self, file_path: str) -> CompleteConfig:
        """Load configuration from file"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Merge with environment variables (env vars take precedence)
            env_config = self._load_from_environment()
            file_config = CompleteConfig.from_dict(data)
            
            # Environment variables override file settings
            return self._merge_configs(file_config, env_config)
            
        except FileNotFoundError:
            logger.warning(f"Configuration file {file_path} not found, using environment variables")
            return self._load_from_environment()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file {file_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading configuration file {file_path}: {e}")
            raise
    
    def _merge_configs(self, base: CompleteConfig, override: CompleteConfig) -> CompleteConfig:
        """Merge two configurations, with override taking precedence"""
        merged_dict = base.to_dict()
        override_dict = override.to_dict()
        
        # Deep merge dictionaries
        for section, section_data in override_dict.items():
            if section in merged_dict:
                merged_dict[section].update(section_data)
            else:
                merged_dict[section] = section_data
        
        return CompleteConfig.from_dict(merged_dict)
    
    def _apply_environment_overrides(self, config: CompleteConfig) -> CompleteConfig:
        """Apply environment-specific overrides"""
        if self._environment == EnvironmentType.PRODUCTION:
            # Production overrides
            config.application.debug = False
            config.pool.enable_statistics = True
            config.monitoring.enable_monitoring = True
            config.monitoring.enable_alerts = True
            
        elif self._environment == EnvironmentType.DEVELOPMENT:
            # Development overrides
            config.application.debug = True
            config.application.log_level = "DEBUG"
            config.pool.min_connections = max(1, config.pool.min_connections // 2)
            config.pool.max_connections = max(3, config.pool.max_connections // 2)
            
        elif self._environment == EnvironmentType.TESTING:
            # Testing overrides
            config.application.debug = False
            config.pool.min_connections = 1
            config.pool.max_connections = 3
            config.monitoring.enable_monitoring = False
            config.monitoring.enable_alerts = False
            
        return config
    
    def _validate_config(self, config: CompleteConfig) -> bool:
        """Validate configuration settings"""
        errors = []
        
        # Pool validation
        if config.pool.min_connections < 1:
            errors.append("min_connections must be at least 1")
        if config.pool.max_connections < config.pool.min_connections:
            errors.append("max_connections must be >= min_connections")
        if config.pool.connection_timeout <= 0:
            errors.append("connection_timeout must be positive")
        if config.pool.validation_timeout <= 0:
            errors.append("validation_timeout must be positive")
        
        # Database validation
        if not config.database.db_path:
            errors.append("database path cannot be empty")
        if config.database.sqlite_timeout <= 0:
            errors.append("sqlite_timeout must be positive")
        if config.database.sqlite_cache_size < 1000:
            errors.append("sqlite_cache_size should be at least 1000 for reasonable performance")
        
        # Application validation
        if config.application.flask_port < 1 or config.application.flask_port > 65535:
            errors.append("flask_port must be between 1 and 65535")
        if config.application.session_timeout < 60:
            errors.append("session_timeout should be at least 60 seconds")
        
        # Monitoring validation
        if config.monitoring.collection_interval <= 0:
            errors.append("monitoring collection_interval must be positive")
        if config.monitoring.history_size < 10:
            errors.append("monitoring history_size should be at least 10")
        
        if errors:
            logger.error(f"Configuration validation failed: {', '.join(errors)}")
            return False
        
        return True
    
    def reload(self) -> bool:
        """Reload configuration from source"""
        with self._lock:
            try:
                if self._config_file:
                    new_config = self._load_from_file(self._config_file)
                else:
                    new_config = self._load_from_environment()
                
                # Apply environment-specific overrides
                new_config = self._apply_environment_overrides(new_config)
                
                # Validate configuration
                if not self._validate_config(new_config):
                    return False
                
                old_config = self._config
                self._config = new_config
                
                # Notify watchers of configuration change
                self._notify_watchers(old_config, new_config)
                
                logger.info(f"Configuration reloaded successfully for {self._environment.value} environment")
                return True
                
            except Exception as e:
                logger.error(f"Failed to reload configuration: {e}")
                return False
    
    def get_config(self) -> CompleteConfig:
        """Get current configuration"""
        with self._lock:
            if self._config is None:
                raise RuntimeError("Configuration not loaded")
            return self._config
    
    def get_pool_config(self) -> PoolConfig:
        """Get pool configuration"""
        return self.get_config().pool
    
    def get_database_config(self) -> DatabaseConfig:
        """Get database configuration"""
        return self.get_config().database
    
    def get_monitoring_config(self) -> MonitoringConfig:
        """Get monitoring configuration"""
        return self.get_config().monitoring
    
    def get_application_config(self) -> ApplicationConfig:
        """Get application configuration"""
        return self.get_config().application
    
    def update_config(self, updates: Dict[str, Any]) -> bool:
        """
        Update configuration at runtime.
        
        Args:
            updates: Dictionary of configuration updates in format:
                     {'section.key': value} e.g., {'pool.max_connections': 20}
        
        Returns:
            bool: True if successful, False otherwise
        """
        with self._lock:
            try:
                config_dict = self._config.to_dict()
                
                # Apply updates
                for key, value in updates.items():
                    parts = key.split('.')
                    if len(parts) != 2:
                        logger.warning(f"Invalid configuration key format: {key}")
                        continue
                    
                    section, setting = parts
                    if section in config_dict:
                        config_dict[section][setting] = value
                        logger.info(f"Updated configuration: {key} = {value}")
                    else:
                        logger.warning(f"Unknown configuration section: {section}")
                
                # Create new configuration and validate
                new_config = CompleteConfig.from_dict(config_dict)
                if not self._validate_config(new_config):
                    return False
                
                old_config = self._config
                self._config = new_config
                
                # Notify watchers
                self._notify_watchers(old_config, new_config)
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to update configuration: {e}")
                return False
    
    def add_watcher(self, callback):
        """Add a configuration change watcher"""
        self._watchers.append(callback)
    
    def remove_watcher(self, callback):
        """Remove a configuration change watcher"""
        if callback in self._watchers:
            self._watchers.remove(callback)
    
    def _notify_watchers(self, old_config: Optional[CompleteConfig], 
                        new_config: CompleteConfig):
        """Notify configuration change watchers"""
        for watcher in self._watchers:
            try:
                watcher(old_config, new_config)
            except Exception as e:
                logger.error(f"Error in configuration watcher: {e}")
    
    def export_config(self, file_path: str) -> bool:
        """Export current configuration to file"""
        try:
            with self._lock:
                config_dict = self._config.to_dict()
                
                # Add metadata
                config_dict['_metadata'] = {
                    'exported_at': str(datetime.now()),
                    'environment': self._environment.value,
                    'version': '1.0'
                }
                
                with open(file_path, 'w') as f:
                    json.dump(config_dict, f, indent=2, default=str)
                
                logger.info(f"Configuration exported to {file_path}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to export configuration: {e}")
            return False
    
    def get_environment_template(self, environment: EnvironmentType) -> str:
        """
        Get environment variable template for the specified environment.
        
        Args:
            environment: Target environment type
            
        Returns:
            String containing environment variable template
        """
        template_configs = {
            EnvironmentType.DEVELOPMENT: {
                'DB_POOL_MIN_CONNECTIONS': '2',
                'DB_POOL_MAX_CONNECTIONS': '5',
                'FLASK_DEBUG': 'true',
                'LOG_LEVEL': 'DEBUG',
                'POOL_MONITORING_ENABLED': 'true'
            },
            EnvironmentType.TESTING: {
                'DB_POOL_MIN_CONNECTIONS': '1',
                'DB_POOL_MAX_CONNECTIONS': '3',
                'FLASK_DEBUG': 'false',
                'LOG_LEVEL': 'WARNING',
                'POOL_MONITORING_ENABLED': 'false'
            },
            EnvironmentType.STAGING: {
                'DB_POOL_MIN_CONNECTIONS': '3',
                'DB_POOL_MAX_CONNECTIONS': '8',
                'FLASK_DEBUG': 'false',
                'LOG_LEVEL': 'INFO',
                'POOL_MONITORING_ENABLED': 'true'
            },
            EnvironmentType.PRODUCTION: {
                'DB_POOL_MIN_CONNECTIONS': '5',
                'DB_POOL_MAX_CONNECTIONS': '15',
                'FLASK_DEBUG': 'false',
                'LOG_LEVEL': 'WARNING',
                'POOL_MONITORING_ENABLED': 'true',
                'SECRET_KEY': 'CHANGE-THIS-IN-PRODUCTION'
            }
        }
        
        base_vars = {
            'FLASK_ENV': environment.value,
            'DATABASE_PATH': 'iron_chef_japan.db',
            'FLASK_HOST': '0.0.0.0',
            'FLASK_PORT': '5000',
            'DB_POOL_CONNECTION_TIMEOUT': '30.0',
            'DB_POOL_VALIDATION_TIMEOUT': '5.0',
            'DB_POOL_HEALTH_CHECK_INTERVAL': '300.0',
            'SQLITE_JOURNAL_MODE': 'WAL',
            'SQLITE_SYNCHRONOUS': 'NORMAL',
            'SQLITE_CACHE_SIZE': '10000'
        }
        
        # Merge base and environment-specific variables
        env_vars = {**base_vars, **template_configs.get(environment, {})}
        
        # Create template string
        template_lines = []
        template_lines.append(f"# Iron Chef Database - {environment.value.title()} Environment")
        template_lines.append(f"# Generated configuration template")
        template_lines.append("")
        
        for key, value in sorted(env_vars.items()):
            template_lines.append(f"{key}={value}")
        
        return "\n".join(template_lines)


# Global configuration manager instance
_global_config_manager: Optional[ConfigManager] = None
_config_lock = threading.Lock()


def initialize_config_manager(config_file: Optional[str] = None,
                            environment: Optional[EnvironmentType] = None) -> ConfigManager:
    """Initialize the global configuration manager"""
    global _global_config_manager
    
    with _config_lock:
        _global_config_manager = ConfigManager(config_file, environment)
        return _global_config_manager


def get_config_manager() -> Optional[ConfigManager]:
    """Get the global configuration manager instance"""
    return _global_config_manager


def get_config() -> CompleteConfig:
    """Get the current configuration"""
    if not _global_config_manager:
        # Initialize with defaults if not already done
        initialize_config_manager()
    
    return _global_config_manager.get_config()


def get_pool_config() -> PoolConfig:
    """Get pool configuration"""
    return get_config().pool


def get_database_config() -> DatabaseConfig:
    """Get database configuration"""
    return get_config().database


def get_monitoring_config() -> MonitoringConfig:
    """Get monitoring configuration"""
    return get_config().monitoring


def get_application_config() -> ApplicationConfig:
    """Get application configuration"""
    return get_config().application