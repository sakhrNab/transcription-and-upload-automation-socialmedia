#!/usr/bin/env python3
"""
Error Recovery and Retry Logic System
Implements exponential backoff, circuit breakers, and retry strategies
"""

import asyncio
import time
import random
from functools import wraps
from typing import Callable, Any, Optional, Dict, List
from enum import Enum
from dataclasses import dataclass
from config import settings
from processor_logger import processor_logger as logger

class CircuitState(Enum):
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Circuit is open, requests fail fast
    HALF_OPEN = "HALF_OPEN"  # Testing if service is back

@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple = (Exception,)

class CircuitBreaker:
    """Circuit breaker pattern implementation"""
    
    def __init__(self, 
                 failure_threshold: int = None,
                 timeout: int = None,
                 expected_exception: type = Exception):
        self.failure_threshold = failure_threshold or settings.circuit_breaker_failure_threshold
        self.timeout = timeout or settings.circuit_breaker_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        
        # Statistics
        self.total_requests = 0
        self.total_failures = 0
        self.total_successes = 0
    
    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                self.state = CircuitState.HALF_OPEN
                logger.log_step(f"Circuit breaker transitioning to HALF_OPEN for {func.__name__}")
            else:
                raise Exception(f"Circuit breaker is OPEN for {func.__name__}")
        
        self.total_requests += 1
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    async def call_async(self, func: Callable, *args, **kwargs):
        """Execute async function with circuit breaker protection"""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                self.state = CircuitState.HALF_OPEN
                logger.log_step(f"Circuit breaker transitioning to HALF_OPEN for {func.__name__}")
            else:
                raise Exception(f"Circuit breaker is OPEN for {func.__name__}")
        
        self.total_requests += 1
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.total_successes += 1
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.total_failures += 1
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.log_error(f"Circuit breaker opened for {self.failure_count} consecutive failures")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics"""
        success_rate = (self.total_successes / self.total_requests * 100) if self.total_requests > 0 else 0
        return {
            'state': self.state.value,
            'total_requests': self.total_requests,
            'total_failures': self.total_failures,
            'total_successes': self.total_successes,
            'success_rate': success_rate,
            'failure_count': self.failure_count
        }

class RetryManager:
    """Advanced retry management with exponential backoff"""
    
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
    
    def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for service"""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker()
        return self.circuit_breakers[service_name]
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt"""
        delay = min(
            self.config.base_delay * (self.config.exponential_base ** attempt),
            self.config.max_delay
        )
        
        if self.config.jitter:
            # Add jitter to prevent thundering herd
            jitter = random.uniform(0, delay * 0.1)
            delay += jitter
        
        return delay
    
    def is_retryable(self, exception: Exception) -> bool:
        """Check if exception is retryable"""
        return isinstance(exception, self.config.retryable_exceptions)
    
    async def retry_async(self, 
                         func: Callable, 
                         *args, 
                         service_name: str = "default",
                         **kwargs) -> Any:
        """Retry async function with exponential backoff and circuit breaker"""
        circuit_breaker = self.get_circuit_breaker(service_name)
        
        for attempt in range(self.config.max_retries + 1):
            try:
                result = await circuit_breaker.call_async(func, *args, **kwargs)
                if attempt > 0:
                    logger.log_step(f"Function {func.__name__} succeeded after {attempt} retries")
                return result
            
            except Exception as e:
                if not self.is_retryable(e):
                    logger.log_error(f"Non-retryable exception in {func.__name__}: {str(e)}")
                    raise e
                
                if attempt == self.config.max_retries:
                    logger.log_error(f"Function {func.__name__} failed after {self.config.max_retries} retries: {str(e)}")
                    raise e
                
                delay = self.calculate_delay(attempt)
                logger.log_step(f"Retrying {func.__name__} in {delay:.2f}s (attempt {attempt + 1}/{self.config.max_retries})")
                await asyncio.sleep(delay)
    
    def retry_sync(self, 
                   func: Callable, 
                   *args, 
                   service_name: str = "default",
                   **kwargs) -> Any:
        """Retry sync function with exponential backoff and circuit breaker"""
        circuit_breaker = self.get_circuit_breaker(service_name)
        
        for attempt in range(self.config.max_retries + 1):
            try:
                result = circuit_breaker.call(func, *args, **kwargs)
                if attempt > 0:
                    logger.log_step(f"Function {func.__name__} succeeded after {attempt} retries")
                return result
            
            except Exception as e:
                if not self.is_retryable(e):
                    logger.log_error(f"Non-retryable exception in {func.__name__}: {str(e)}")
                    raise e
                
                if attempt == self.config.max_retries:
                    logger.log_error(f"Function {func.__name__} failed after {self.config.max_retries} retries: {str(e)}")
                    raise e
                
                delay = self.calculate_delay(attempt)
                logger.log_step(f"Retrying {func.__name__} in {delay:.2f}s (attempt {attempt + 1}/{self.config.max_retries})")
                time.sleep(delay)

# Decorators for easy retry application
def retry_async(config: RetryConfig = None, service_name: str = "default"):
    """Decorator for async retry logic"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retry_manager = RetryManager(config)
            return await retry_manager.retry_async(func, *args, service_name=service_name, **kwargs)
        return wrapper
    return decorator

def retry_sync(config: RetryConfig = None, service_name: str = "default"):
    """Decorator for sync retry logic"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retry_manager = RetryManager(config)
            return retry_manager.retry_sync(func, *args, service_name=service_name, **kwargs)
        return wrapper
    return decorator

# Specific retry configurations for different services
GOOGLE_API_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0,
    retryable_exceptions=(Exception,)
)

AIWAVERIDER_RETRY_CONFIG = RetryConfig(
    max_retries=5,
    base_delay=2.0,
    max_delay=60.0,
    retryable_exceptions=(Exception,)
)

FILE_OPERATION_RETRY_CONFIG = RetryConfig(
    max_retries=3,
    base_delay=0.5,
    max_delay=10.0,
    retryable_exceptions=(OSError, IOError)
)

# Global retry manager instance
retry_manager = RetryManager()

# Service-specific retry managers
google_retry_manager = RetryManager(GOOGLE_API_RETRY_CONFIG)
aiwaverider_retry_manager = RetryManager(AIWAVERIDER_RETRY_CONFIG)
file_retry_manager = RetryManager(FILE_OPERATION_RETRY_CONFIG)
