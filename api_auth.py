#!/usr/bin/env python3
"""
Iron Chef Recipe Database API Authentication
Enhanced authentication, API key management, and security handlers
"""

import os
import hashlib
import secrets
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from functools import wraps
from dataclasses import dataclass
from enum import Enum

from flask import request, jsonify, g, current_app
from werkzeug.exceptions import Unauthorized, Forbidden, TooManyRequests
from iron_chef_database_secure import SecurityValidator


logger = logging.getLogger(__name__)


class APIKeyStatus(Enum):
    """API key status enumeration"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    REVOKED = "revoked"


class UserRole(Enum):
    """User role enumeration"""
    GUEST = "guest"
    USER = "user"
    PREMIUM = "premium"
    ADMIN = "admin"


@dataclass
class APIKey:
    """API key data structure"""
    key_id: str
    key_hash: str
    name: str
    user_email: str
    role: UserRole
    status: APIKeyStatus
    created_at: datetime
    expires_at: Optional[datetime]
    last_used: Optional[datetime]
    usage_count: int
    rate_limit: int
    allowed_ips: List[str]
    allowed_endpoints: List[str]


@dataclass
class RateLimit:
    """Rate limit configuration"""
    requests_per_minute: int
    requests_per_hour: int
    requests_per_day: int
    burst_limit: int


class APIKeyManager:
    """Manages API keys and authentication"""
    
    def __init__(self, db_path: str = "iron_chef.db"):
        self.db_path = db_path
        self.validator = SecurityValidator()
        self._init_auth_tables()
    
    def _init_auth_tables(self):
        """Initialize authentication tables if they don't exist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS api_keys (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key_id TEXT UNIQUE NOT NULL,
                        key_hash TEXT NOT NULL,
                        name TEXT NOT NULL,
                        user_email TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'user',
                        status TEXT NOT NULL DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP,
                        last_used TIMESTAMP,
                        usage_count INTEGER DEFAULT 0,
                        rate_limit INTEGER DEFAULT 100,
                        allowed_ips TEXT,
                        allowed_endpoints TEXT
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS api_usage (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key_id TEXT NOT NULL,
                        endpoint TEXT NOT NULL,
                        method TEXT NOT NULL,
                        ip_address TEXT,
                        user_agent TEXT,
                        response_status INTEGER,
                        response_time_ms INTEGER,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (key_id) REFERENCES api_keys(key_id)
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_api_keys_key_id 
                    ON api_keys(key_id)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_api_usage_key_timestamp 
                    ON api_usage(key_id, timestamp)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_api_usage_endpoint 
                    ON api_usage(endpoint, timestamp)
                """)
                
                conn.commit()
                logger.info("Authentication tables initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize auth tables: {e}")
            raise
    
    def generate_api_key(
        self, 
        name: str, 
        user_email: str, 
        role: UserRole = UserRole.USER,
        expires_days: Optional[int] = None,
        rate_limit: int = 100,
        allowed_ips: Optional[List[str]] = None,
        allowed_endpoints: Optional[List[str]] = None
    ) -> Tuple[str, str]:
        """
        Generate a new API key
        Returns (key_id, api_key) tuple
        """
        try:
            # Validate inputs
            name = self.validator.validate_string(name, max_length=100, field_name="API key name")
            user_email = self.validator.validate_string(user_email, max_length=200, field_name="user email")
            
            # Generate secure key
            key_id = secrets.token_urlsafe(16)
            api_key = secrets.token_urlsafe(32)
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()
            
            # Calculate expiry
            expires_at = None
            if expires_days:
                expires_at = datetime.utcnow() + timedelta(days=expires_days)
            
            # Prepare data
            allowed_ips_str = ",".join(allowed_ips) if allowed_ips else None
            allowed_endpoints_str = ",".join(allowed_endpoints) if allowed_endpoints else None
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO api_keys (
                        key_id, key_hash, name, user_email, role, status,
                        expires_at, rate_limit, allowed_ips, allowed_endpoints
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    key_id, key_hash, name, user_email, role.value, 
                    APIKeyStatus.ACTIVE.value, expires_at, rate_limit,
                    allowed_ips_str, allowed_endpoints_str
                ))
                conn.commit()
                
            logger.info(f"Generated API key for {user_email}: {key_id}")
            return key_id, f"ic_{api_key}"  # Prefix for identification
            
        except Exception as e:
            logger.error(f"Failed to generate API key: {e}")
            raise
    
    def validate_api_key(self, api_key: str) -> Optional[APIKey]:
        """Validate an API key and return key info if valid"""
        try:
            if not api_key or not api_key.startswith("ic_"):
                return None
                
            # Extract actual key (remove prefix)
            actual_key = api_key[3:]
            key_hash = hashlib.sha256(actual_key.encode()).hexdigest()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT * FROM api_keys WHERE key_hash = ?
                """, (key_hash,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                # Parse the row data
                api_key_obj = APIKey(
                    key_id=row['key_id'],
                    key_hash=row['key_hash'],
                    name=row['name'],
                    user_email=row['user_email'],
                    role=UserRole(row['role']),
                    status=APIKeyStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None,
                    last_used=datetime.fromisoformat(row['last_used']) if row['last_used'] else None,
                    usage_count=row['usage_count'],
                    rate_limit=row['rate_limit'],
                    allowed_ips=row['allowed_ips'].split(',') if row['allowed_ips'] else [],
                    allowed_endpoints=row['allowed_endpoints'].split(',') if row['allowed_endpoints'] else []
                )
                
                # Check if key is valid
                if api_key_obj.status != APIKeyStatus.ACTIVE:
                    logger.warning(f"API key {api_key_obj.key_id} is not active: {api_key_obj.status}")
                    return None
                
                if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
                    logger.warning(f"API key {api_key_obj.key_id} has expired")
                    self._update_key_status(api_key_obj.key_id, APIKeyStatus.EXPIRED)
                    return None
                
                return api_key_obj
                
        except Exception as e:
            logger.error(f"Failed to validate API key: {e}")
            return None
    
    def update_key_usage(self, key_id: str, endpoint: str, method: str, 
                        ip_address: str, user_agent: str, response_status: int, 
                        response_time_ms: int):
        """Update API key usage statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Update usage count and last used
                conn.execute("""
                    UPDATE api_keys 
                    SET usage_count = usage_count + 1, last_used = CURRENT_TIMESTAMP
                    WHERE key_id = ?
                """, (key_id,))
                
                # Record usage details
                conn.execute("""
                    INSERT INTO api_usage (
                        key_id, endpoint, method, ip_address, user_agent,
                        response_status, response_time_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (key_id, endpoint, method, ip_address, user_agent, 
                     response_status, response_time_ms))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to update key usage: {e}")
    
    def check_rate_limit(self, key_id: str) -> Tuple[bool, Dict]:
        """Check if API key has exceeded rate limits"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get current usage for the last hour
                cursor = conn.execute("""
                    SELECT COUNT(*) as count_1h
                    FROM api_usage 
                    WHERE key_id = ? 
                    AND timestamp > datetime('now', '-1 hour')
                """, (key_id,))
                
                count_1h = cursor.fetchone()[0]
                
                # Get current usage for the last minute
                cursor = conn.execute("""
                    SELECT COUNT(*) as count_1m
                    FROM api_usage 
                    WHERE key_id = ? 
                    AND timestamp > datetime('now', '-1 minute')
                """, (key_id,))
                
                count_1m = cursor.fetchone()[0]
                
                # Get API key rate limit
                cursor = conn.execute("""
                    SELECT rate_limit FROM api_keys WHERE key_id = ?
                """, (key_id,))
                
                row = cursor.fetchone()
                if not row:
                    return False, {"error": "API key not found"}
                
                rate_limit = row[0]
                
                # Check limits (simple implementation)
                minute_limit = min(rate_limit, 50)  # Max 50 per minute
                hour_limit = rate_limit
                
                if count_1m >= minute_limit:
                    return False, {
                        "error": "Rate limit exceeded",
                        "limit_type": "per_minute",
                        "limit": minute_limit,
                        "used": count_1m,
                        "reset_time": 60
                    }
                
                if count_1h >= hour_limit:
                    return False, {
                        "error": "Rate limit exceeded", 
                        "limit_type": "per_hour",
                        "limit": hour_limit,
                        "used": count_1h,
                        "reset_time": 3600
                    }
                
                return True, {
                    "remaining_minute": minute_limit - count_1m,
                    "remaining_hour": hour_limit - count_1h,
                    "used_minute": count_1m,
                    "used_hour": count_1h
                }
                
        except Exception as e:
            logger.error(f"Failed to check rate limit: {e}")
            return False, {"error": "Rate limit check failed"}
    
    def _update_key_status(self, key_id: str, status: APIKeyStatus):
        """Update API key status"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE api_keys SET status = ? WHERE key_id = ?
                """, (status.value, key_id))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to update key status: {e}")
    
    def get_key_stats(self, key_id: str) -> Optional[Dict]:
        """Get usage statistics for an API key"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_requests,
                        COUNT(CASE WHEN timestamp > datetime('now', '-1 day') THEN 1 END) as requests_today,
                        COUNT(CASE WHEN timestamp > datetime('now', '-1 hour') THEN 1 END) as requests_hour,
                        AVG(response_time_ms) as avg_response_time,
                        MAX(timestamp) as last_request
                    FROM api_usage 
                    WHERE key_id = ?
                """, (key_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                return {
                    "total_requests": row[0],
                    "requests_today": row[1], 
                    "requests_hour": row[2],
                    "avg_response_time_ms": round(row[3] or 0, 2),
                    "last_request": row[4]
                }
                
        except Exception as e:
            logger.error(f"Failed to get key stats: {e}")
            return None
    
    def list_api_keys(self, user_email: Optional[str] = None) -> List[Dict]:
        """List API keys (optionally filtered by user)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                if user_email:
                    cursor = conn.execute("""
                        SELECT key_id, name, user_email, role, status, created_at, 
                               expires_at, last_used, usage_count, rate_limit
                        FROM api_keys 
                        WHERE user_email = ?
                        ORDER BY created_at DESC
                    """, (user_email,))
                else:
                    cursor = conn.execute("""
                        SELECT key_id, name, user_email, role, status, created_at,
                               expires_at, last_used, usage_count, rate_limit
                        FROM api_keys 
                        ORDER BY created_at DESC
                    """)
                
                return [dict(row) for row in cursor.fetchall()]
                
        except Exception as e:
            logger.error(f"Failed to list API keys: {e}")
            return []


# Authentication decorators
def require_api_key(optional: bool = False):
    """Decorator to require API key authentication"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = datetime.utcnow()
            api_key = request.headers.get('X-API-Key')
            
            # Initialize rate limit info
            g.rate_limit_info = {}
            g.api_key_info = None
            
            if not api_key:
                if optional:
                    # Allow request without API key but with reduced rate limits
                    g.rate_limit_info = {
                        "remaining_minute": 10,
                        "remaining_hour": 50,
                        "guest_mode": True
                    }
                    return f(*args, **kwargs)
                else:
                    return jsonify({
                        'success': False,
                        'message': 'API key required',
                        'errors': ['X-API-Key header is required for this endpoint']
                    }), 401
            
            # Validate API key
            key_manager = APIKeyManager()
            api_key_obj = key_manager.validate_api_key(api_key)
            
            if not api_key_obj:
                return jsonify({
                    'success': False,
                    'message': 'Invalid API key',
                    'errors': ['The provided API key is invalid or expired']
                }), 401
            
            # Check IP restrictions
            if api_key_obj.allowed_ips:
                client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
                if client_ip not in api_key_obj.allowed_ips:
                    logger.warning(f"API key {api_key_obj.key_id} used from unauthorized IP: {client_ip}")
                    return jsonify({
                        'success': False,
                        'message': 'IP not authorized',
                        'errors': ['Your IP address is not authorized for this API key']
                    }), 403
            
            # Check endpoint restrictions
            if api_key_obj.allowed_endpoints:
                endpoint = request.endpoint
                if endpoint not in api_key_obj.allowed_endpoints:
                    return jsonify({
                        'success': False,
                        'message': 'Endpoint not authorized',
                        'errors': ['This API key is not authorized for this endpoint']
                    }), 403
            
            # Check rate limits
            rate_limit_ok, rate_info = key_manager.check_rate_limit(api_key_obj.key_id)
            if not rate_limit_ok:
                return jsonify({
                    'success': False,
                    'message': rate_info.get('error', 'Rate limit exceeded'),
                    'errors': [f"Rate limit exceeded: {rate_info}"]
                }), 429
            
            # Store info for use in the request
            g.api_key_info = api_key_obj
            g.rate_limit_info = rate_info
            
            # Execute the function
            try:
                result = f(*args, **kwargs)
                status_code = 200
                if isinstance(result, tuple):
                    status_code = result[1]
                    
                return result
                
            finally:
                # Log usage
                end_time = datetime.utcnow()
                response_time = int((end_time - start_time).total_seconds() * 1000)
                
                key_manager.update_key_usage(
                    api_key_obj.key_id,
                    request.endpoint or request.path,
                    request.method,
                    request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr),
                    request.headers.get('User-Agent', ''),
                    status_code,
                    response_time
                )
        
        return decorated_function
    return decorator


def require_role(required_role: UserRole):
    """Decorator to require specific user role"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'api_key_info') or not g.api_key_info:
                return jsonify({
                    'success': False,
                    'message': 'Authentication required',
                    'errors': ['Valid API key required for this endpoint']
                }), 401
            
            user_role = g.api_key_info.role
            role_hierarchy = {
                UserRole.GUEST: 0,
                UserRole.USER: 1,
                UserRole.PREMIUM: 2,
                UserRole.ADMIN: 3
            }
            
            if role_hierarchy[user_role] < role_hierarchy[required_role]:
                return jsonify({
                    'success': False,
                    'message': 'Insufficient permissions',
                    'errors': [f'This endpoint requires {required_role.value} role or higher']
                }), 403
            
            return f(*args, **kwargs)
            
        return decorated_function
    return decorator


def add_rate_limit_headers(response):
    """Add rate limit headers to response"""
    if hasattr(g, 'rate_limit_info') and g.rate_limit_info:
        if not g.rate_limit_info.get('guest_mode'):
            response.headers['X-RateLimit-Remaining-Minute'] = str(g.rate_limit_info.get('remaining_minute', 0))
            response.headers['X-RateLimit-Remaining-Hour'] = str(g.rate_limit_info.get('remaining_hour', 0))
            response.headers['X-RateLimit-Used-Minute'] = str(g.rate_limit_info.get('used_minute', 0))
            response.headers['X-RateLimit-Used-Hour'] = str(g.rate_limit_info.get('used_hour', 0))
        else:
            response.headers['X-RateLimit-Guest-Mode'] = 'true'
    
    return response


# Utility functions
def get_current_user_role() -> UserRole:
    """Get current user's role from request context"""
    if hasattr(g, 'api_key_info') and g.api_key_info:
        return g.api_key_info.role
    return UserRole.GUEST


def get_current_api_key_id() -> Optional[str]:
    """Get current API key ID from request context"""
    if hasattr(g, 'api_key_info') and g.api_key_info:
        return g.api_key_info.key_id
    return None


def is_admin_user() -> bool:
    """Check if current user is admin"""
    return get_current_user_role() == UserRole.ADMIN


# CLI functions for key management
def create_admin_key():
    """Create an admin API key (for CLI use)"""
    key_manager = APIKeyManager()
    key_id, api_key = key_manager.generate_api_key(
        name="Admin Key",
        user_email="admin@ironchef.local",
        role=UserRole.ADMIN,
        rate_limit=1000
    )
    print(f"Admin API Key created:")
    print(f"Key ID: {key_id}")
    print(f"API Key: {api_key}")
    print(f"Rate Limit: 1000 requests/hour")
    print("\nUse this key in your requests with the X-API-Key header")


if __name__ == '__main__':
    # CLI interface for key management
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "create-admin":
        create_admin_key()
    else:
        print("Usage: python api_auth.py create-admin")