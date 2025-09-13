#!/usr/bin/env python3
"""
Health Monitoring and Metrics Collection System
Tracks performance, errors, and system health
"""

import time
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum
from .config import settings
from .database import db_manager
from .processor_logger import processor_logger as logger

class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"

@dataclass
class Metric:
    name: str
    value: float
    unit: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    metric_type: MetricType = MetricType.GAUGE

@dataclass
class ProcessingMetrics:
    """Comprehensive processing metrics"""
    start_time: float
    end_time: float
    files_processed: int = 0
    videos_processed: int = 0
    thumbnails_processed: int = 0
    uploads_successful: int = 0
    uploads_failed: int = 0
    google_drive_uploads: int = 0
    aiwaverider_uploads: int = 0
    sheets_updates: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    retries_attempted: int = 0
    errors_encountered: int = 0
    memory_peak_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    
    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time
    
    @property
    def success_rate(self) -> float:
        total = self.uploads_successful + self.uploads_failed
        return (self.uploads_successful / total * 100) if total > 0 else 0.0
    
    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0.0
    
    @property
    def throughput_files_per_minute(self) -> float:
        return (self.files_processed / self.duration_seconds * 60) if self.duration_seconds > 0 else 0.0

class HealthChecker:
    """System health monitoring"""
    
    def __init__(self):
        self.health_status = "healthy"
        self.last_check = None
        self.checks: Dict[str, callable] = {}
        self.register_default_checks()
    
    def register_check(self, name: str, check_func: callable):
        """Register a health check function"""
        self.checks[name] = check_func
    
    def register_default_checks(self):
        """Register default health checks"""
        self.register_check("database", self._check_database)
        self.register_check("disk_space", self._check_disk_space)
        self.register_check("memory", self._check_memory)
        self.register_check("queue_health", self._check_queue_health)
    
    async def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        try:
            start_time = time.time()
            await db_manager.get_videos_by_status("PENDING")
            response_time = time.time() - start_time
            
            return {
                "status": "healthy" if response_time < 1.0 else "degraded",
                "response_time_ms": response_time * 1000,
                "message": f"Database response time: {response_time:.3f}s"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "message": "Database connection failed"
            }
    
    async def _check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space"""
        try:
            import shutil
            total, used, free = shutil.disk_usage(".")
            free_percent = (free / total) * 100
            
            status = "healthy"
            if free_percent < 10:
                status = "unhealthy"
            elif free_percent < 20:
                status = "degraded"
            
            return {
                "status": status,
                "free_space_gb": free / (1024**3),
                "free_percent": free_percent,
                "message": f"Free space: {free_percent:.1f}%"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "message": "Disk space check failed"
            }
    
    async def _check_memory(self) -> Dict[str, Any]:
        """Check memory usage"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            status = "healthy"
            if memory_percent > 90:
                status = "unhealthy"
            elif memory_percent > 80:
                status = "degraded"
            
            return {
                "status": status,
                "memory_percent": memory_percent,
                "available_gb": memory.available / (1024**3),
                "message": f"Memory usage: {memory_percent:.1f}%"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "message": "Memory check failed"
            }
    
    async def _check_queue_health(self) -> Dict[str, Any]:
        """Check processing queue health"""
        try:
            pending_tasks = await db_manager.get_next_task()
            queue_size = 0
            if pending_tasks:
                # This is a simplified check - in practice you'd count all pending tasks
                queue_size = 1
            
            status = "healthy"
            if queue_size > 100:
                status = "degraded"
            elif queue_size > 500:
                status = "unhealthy"
            
            return {
                "status": status,
                "queue_size": queue_size,
                "message": f"Queue size: {queue_size}"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "message": "Queue health check failed"
            }
    
    async def run_health_checks(self) -> Dict[str, Any]:
        """Run all health checks"""
        results = {}
        overall_status = "healthy"
        
        for check_name, check_func in self.checks.items():
            try:
                result = await check_func()
                results[check_name] = result
                
                if result["status"] == "unhealthy":
                    overall_status = "unhealthy"
                elif result["status"] == "degraded" and overall_status == "healthy":
                    overall_status = "degraded"
            except Exception as e:
                results[check_name] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "message": f"Health check {check_name} failed"
                }
                overall_status = "unhealthy"
        
        self.health_status = overall_status
        self.last_check = datetime.now()
        
        return {
            "overall_status": overall_status,
            "last_check": self.last_check.isoformat(),
            "checks": results
        }

class MetricsCollector:
    """Centralized metrics collection and reporting"""
    
    def __init__(self):
        self.metrics: List[Metric] = []
        self.processing_metrics: Optional[ProcessingMetrics] = None
        self.health_checker = HealthChecker()
    
    def record_metric(self, 
                     name: str, 
                     value: float, 
                     unit: str = "", 
                     tags: Dict[str, str] = None,
                     metric_type: MetricType = MetricType.GAUGE):
        """Record a metric"""
        if not settings.enable_metrics:
            return
        
        metric = Metric(
            name=name,
            value=value,
            unit=unit,
            tags=tags or {},
            metric_type=metric_type
        )
        self.metrics.append(metric)
        
        # Also store in database
        asyncio.create_task(self._store_metric_async(metric))
    
    async def _store_metric_async(self, metric: Metric):
        """Store metric in database asynchronously"""
        try:
            await db_manager.record_metric(
                name=metric.name,
                value=metric.value,
                unit=metric.unit,
                tags=metric.tags
            )
        except Exception as e:
            logger.log_error(f"Failed to store metric {metric.name}: {str(e)}")
    
    def start_processing_metrics(self) -> ProcessingMetrics:
        """Start tracking processing metrics"""
        self.processing_metrics = ProcessingMetrics(
            start_time=time.time(),
            end_time=0.0
        )
        return self.processing_metrics
    
    def finish_processing_metrics(self):
        """Finish tracking processing metrics"""
        if self.processing_metrics:
            self.processing_metrics.end_time = time.time()
            self._log_processing_metrics()
            self._record_processing_metrics()
    
    def _log_processing_metrics(self):
        """Log processing metrics summary"""
        if not self.processing_metrics:
            return
        
        metrics = self.processing_metrics
        logger.log_step("=== Processing Metrics Summary ===")
        logger.log_step(f"Duration: {metrics.duration_seconds:.2f} seconds")
        logger.log_step(f"Files processed: {metrics.files_processed}")
        logger.log_step(f"Videos processed: {metrics.videos_processed}")
        logger.log_step(f"Thumbnails processed: {metrics.thumbnails_processed}")
        logger.log_step(f"Uploads successful: {metrics.uploads_successful}")
        logger.log_step(f"Uploads failed: {metrics.uploads_failed}")
        logger.log_step(f"Success rate: {metrics.success_rate:.1f}%")
        logger.log_step(f"Cache hit rate: {metrics.cache_hit_rate:.1f}%")
        logger.log_step(f"Throughput: {metrics.throughput_files_per_minute:.1f} files/min")
        logger.log_step(f"Retries attempted: {metrics.retries_attempted}")
        logger.log_step(f"Errors encountered: {metrics.errors_encountered}")
        logger.log_step("================================")
    
    def _record_processing_metrics(self):
        """Record processing metrics as individual metrics"""
        if not self.processing_metrics:
            return
        
        metrics = self.processing_metrics
        
        # Record key metrics
        self.record_metric("processing.duration_seconds", metrics.duration_seconds, "seconds")
        self.record_metric("processing.files_processed", metrics.files_processed, "count")
        self.record_metric("processing.videos_processed", metrics.videos_processed, "count")
        self.record_metric("processing.thumbnails_processed", metrics.thumbnails_processed, "count")
        self.record_metric("processing.uploads_successful", metrics.uploads_successful, "count")
        self.record_metric("processing.uploads_failed", metrics.uploads_failed, "count")
        self.record_metric("processing.success_rate", metrics.success_rate, "percent")
        self.record_metric("processing.cache_hit_rate", metrics.cache_hit_rate, "percent")
        self.record_metric("processing.throughput_files_per_minute", metrics.throughput_files_per_minute, "files/min")
        self.record_metric("processing.retries_attempted", metrics.retries_attempted, "count")
        self.record_metric("processing.errors_encountered", metrics.errors_encountered, "count")
    
    def increment_counter(self, name: str, value: int = 1, tags: Dict[str, str] = None):
        """Increment a counter metric"""
        self.record_metric(name, value, "count", tags, MetricType.COUNTER)
    
    def set_gauge(self, name: str, value: float, unit: str = "", tags: Dict[str, str] = None):
        """Set a gauge metric"""
        self.record_metric(name, value, unit, tags, MetricType.GAUGE)
    
    def record_timer(self, name: str, duration_seconds: float, tags: Dict[str, str] = None):
        """Record a timer metric"""
        self.record_metric(name, duration_seconds, "seconds", tags, MetricType.TIMER)
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get current system health status"""
        return await self.health_checker.run_health_checks()
    
    async def get_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get metrics summary for the last N hours"""
        try:
            # Get key metrics from database
            duration_metrics = await db_manager.get_metrics("processing.duration_seconds", hours)
            success_rate_metrics = await db_manager.get_metrics("processing.success_rate", hours)
            throughput_metrics = await db_manager.get_metrics("processing.throughput_files_per_minute", hours)
            
            # Calculate averages
            avg_duration = sum(m['metric_value'] for m in duration_metrics) / len(duration_metrics) if duration_metrics else 0
            avg_success_rate = sum(m['metric_value'] for m in success_rate_metrics) / len(success_rate_metrics) if success_rate_metrics else 0
            avg_throughput = sum(m['metric_value'] for m in throughput_metrics) / len(throughput_metrics) if throughput_metrics else 0
            
            return {
                "time_range_hours": hours,
                "average_duration_seconds": avg_duration,
                "average_success_rate_percent": avg_success_rate,
                "average_throughput_files_per_minute": avg_throughput,
                "total_processing_sessions": len(duration_metrics)
            }
        except Exception as e:
            logger.log_error(f"Failed to get metrics summary: {str(e)}")
            return {"error": str(e)}
    
    async def cleanup_old_metrics(self):
        """Clean up old metrics"""
        try:
            await db_manager.cleanup_old_metrics()
            logger.log_step("Old metrics cleaned up successfully")
        except Exception as e:
            logger.log_error(f"Failed to cleanup old metrics: {str(e)}")

# Global metrics collector instance
metrics_collector = MetricsCollector()
