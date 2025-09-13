#!/usr/bin/env python3
"""
Base Processor Class
Provides common functionality for all processors
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from system.processor_logger import processor_logger as logger


class BaseProcessor(ABC):
    """Base class for all processors"""
    
    def __init__(self, name: str):
        self.name = name
        self.initialized = False
        self.status = "idle"
        self.error_count = 0
        self.max_errors = 5
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the processor"""
        pass
    
    @abstractmethod
    async def process(self, *args, **kwargs) -> bool:
        """Main processing method"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup resources"""
        pass
    
    async def get_status(self) -> Dict[str, Any]:
        """Get processor status"""
        return {
            'name': self.name,
            'status': self.status,
            'initialized': self.initialized,
            'error_count': self.error_count
        }
    
    def log_error(self, message: str, error: Exception = None):
        """Log error and increment error count"""
        self.error_count += 1
        if error:
            logger.log_error(f"{self.name}: {message} - {str(error)}")
        else:
            logger.log_error(f"{self.name}: {message}")
    
    def log_step(self, message: str):
        """Log step message"""
        logger.log_step(f"{self.name}: {message}")
    
    def is_healthy(self) -> bool:
        """Check if processor is healthy"""
        return self.error_count < self.max_errors and self.initialized
