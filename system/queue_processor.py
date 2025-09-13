#!/usr/bin/env python3
"""
Queue-Based Processing System
Implements background workers and task queues for parallel processing
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum
from .config import settings
from .new_database import new_db_manager as db_manager
from .error_recovery import retry_async, RetryConfig, AIWAVERIDER_RETRY_CONFIG, GOOGLE_API_RETRY_CONFIG
from .health_metrics import metrics_collector
from .processor_logger import processor_logger as logger

class TaskType(Enum):
    DOWNLOAD_VIDEO = "download_video"
    UPLOAD_GOOGLE_DRIVE = "upload_google_drive"
    UPLOAD_AIWAVERIDER = "upload_aiwaverider"
    UPDATE_SHEETS = "update_sheets"
    PROCESS_THUMBNAIL = "process_thumbnail"
    TRANSCRIBE_AUDIO = "transcribe_audio"

class TaskStatus(Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"

@dataclass
class Task:
    id: int
    task_type: TaskType
    data: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    retry_count: int = 0
    max_retries: int = 3
    created_at: float = None
    updated_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.updated_at is None:
            self.updated_at = time.time()

class Worker:
    """Base worker class for processing tasks"""
    
    def __init__(self, worker_id: str, task_types: List[TaskType]):
        self.worker_id = worker_id
        self.task_types = task_types
        self.is_running = False
        self.current_task: Optional[Task] = None
        self.processed_count = 0
        self.error_count = 0
    
    async def start(self):
        """Start the worker"""
        self.is_running = True
        logger.log_step(f"Worker {self.worker_id} started")
        
        while self.is_running:
            try:
                task = await self._get_next_task()
                if task:
                    await self._process_task(task)
                else:
                    # No tasks available, wait a bit
                    await asyncio.sleep(1)
            except Exception as e:
                logger.log_error(f"Worker {self.worker_id} error: {str(e)}")
                self.error_count += 1
                await asyncio.sleep(5)  # Wait before retrying
    
    async def stop(self):
        """Stop the worker"""
        self.is_running = False
        logger.log_step(f"Worker {self.worker_id} stopped")
    
    async def _get_next_task(self) -> Optional[Task]:
        """Get next task from database"""
        task_data = await db_manager.get_next_task()
        if task_data:
            return Task(
                id=task_data['id'],
                task_type=TaskType(task_data['task_type']),
                data=task_data['task_data'],
                status=TaskStatus(task_data['status']),
                priority=task_data['priority'],
                retry_count=task_data['retry_count'],
                max_retries=task_data['max_retries'],
                created_at=task_data['created_at'],
                updated_at=task_data['updated_at']
            )
        return None
    
    async def _process_task(self, task: Task):
        """Process a single task"""
        self.current_task = task
        logger.log_step(f"Worker {self.worker_id} processing task {task.id}: {task.task_type.value}")
        
        try:
            # Update task status to processing
            await db_manager.update_task_status(task.id, TaskStatus.PROCESSING.value)
            
            # Process based on task type
            result = await self._execute_task(task)
            
            # Mark as completed
            await db_manager.update_task_status(task.id, TaskStatus.COMPLETED.value)
            self.processed_count += 1
            
            logger.log_step(f"Worker {self.worker_id} completed task {task.id}")
            
        except Exception as e:
            logger.log_error(f"Worker {self.worker_id} failed task {task.id}: {str(e)}")
            
            # Handle retry logic
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                await db_manager.update_task_status(task.id, TaskStatus.RETRYING.value, task.retry_count)
                logger.log_step(f"Worker {self.worker_id} will retry task {task.id} (attempt {task.retry_count})")
            else:
                await db_manager.update_task_status(task.id, TaskStatus.FAILED.value, task.retry_count)
                self.error_count += 1
        
        finally:
            self.current_task = None
    
    async def _execute_task(self, task: Task) -> Any:
        """Execute the actual task - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement _execute_task")

class VideoDownloadWorker(Worker):
    """Worker for downloading videos"""
    
    def __init__(self, worker_id: str = "video_downloader"):
        super().__init__(worker_id, [TaskType.DOWNLOAD_VIDEO])
    
    async def _execute_task(self, task: Task) -> Any:
        """Download video from URL"""
        url = task.data.get('url')
        if not url:
            raise ValueError("No URL provided for video download")
        
        # This would integrate with your existing download logic
        # For now, we'll simulate the download
        logger.log_step(f"Downloading video from {url}")
        
        # Simulate download time
        await asyncio.sleep(2)
        
        # Return download result
        return {
            'video_path': f"downloads/videos/video_{task.id}.mp4",
            'filename': f"video_{task.id}.mp4",
            'status': 'completed'
        }

class GoogleDriveUploadWorker(Worker):
    """Worker for uploading to Google Drive"""
    
    def __init__(self, worker_id: str = "google_uploader"):
        super().__init__(worker_id, [TaskType.UPLOAD_GOOGLE_DRIVE])
    
    @retry_async(GOOGLE_API_RETRY_CONFIG, "google_drive")
    async def _execute_task(self, task: Task) -> Any:
        """Upload file to Google Drive"""
        file_path = task.data.get('file_path')
        if not file_path:
            raise ValueError("No file path provided for Google Drive upload")
        
        logger.log_step(f"Uploading {file_path} to Google Drive")
        
        # This would integrate with your existing Google Drive upload logic
        # For now, we'll simulate the upload
        await asyncio.sleep(1)
        
        # Return upload result
        return {
            'drive_id': f"google_drive_id_{task.id}",
            'drive_url': f"https://drive.google.com/file/d/google_drive_id_{task.id}/view",
            'status': 'completed'
        }

class AIWaveriderUploadWorker(Worker):
    """Worker for uploading to AIWaverider Drive"""
    
    def __init__(self, worker_id: str = "aiwaverider_uploader"):
        super().__init__(worker_id, [TaskType.UPLOAD_AIWAVERIDER])
    
    @retry_async(AIWAVERIDER_RETRY_CONFIG, "aiwaverider")
    async def _execute_task(self, task: Task) -> Any:
        """Upload file to AIWaverider Drive"""
        file_path = task.data.get('file_path')
        folder_path = task.data.get('folder_path', '/videos/instagram/ai.uprise')
        file_type = task.data.get('file_type', 'video')
        
        if not file_path:
            raise ValueError("No file path provided for AIWaverider upload")
        
        logger.log_step(f"Uploading {file_path} to AIWaverider Drive ({folder_path})")
        
        # This would integrate with your existing AIWaverider upload logic
        # For now, we'll simulate the upload
        await asyncio.sleep(0.5)
        
        # Return upload result
        return {
            'aiwaverider_id': f"aiwaverider_id_{task.id}",
            'status': 'completed'
        }

class SheetsUpdateWorker(Worker):
    """Worker for updating Google Sheets"""
    
    def __init__(self, worker_id: str = "sheets_updater"):
        super().__init__(worker_id, [TaskType.UPDATE_SHEETS])
    
    @retry_async(GOOGLE_API_RETRY_CONFIG, "google_sheets")
    async def _execute_task(self, task: Task) -> Any:
        """Update Google Sheets with data"""
        sheet_data = task.data.get('sheet_data', {})
        if not sheet_data:
            raise ValueError("No sheet data provided for update")
        
        logger.log_step(f"Updating Google Sheets with data for {sheet_data.get('filename', 'unknown')}")
        
        # This would integrate with your existing Google Sheets update logic
        # For now, we'll simulate the update
        await asyncio.sleep(0.2)
        
        # Return update result
        return {
            'row_updated': True,
            'status': 'completed'
        }

class QueueProcessor:
    """Main queue processor that manages workers and tasks"""
    
    def __init__(self):
        self.workers: List[Worker] = []
        self.is_running = False
        self.task_handlers: Dict[TaskType, Callable] = {}
        self._worker_tasks: List[asyncio.Task] = []
    
    def add_worker(self, worker: Worker):
        """Add a worker to the processor"""
        self.workers.append(worker)
        logger.log_step(f"Added worker: {worker.worker_id}")
    
    async def start(self):
        """Start all workers"""
        if self.is_running:
            logger.log_step("Queue processor is already running")
            return
        
        self.is_running = True
        logger.log_step("Starting queue processor...")
        
        # Start all workers
        for worker in self.workers:
            task = asyncio.create_task(worker.start())
            self._worker_tasks.append(task)
        
        logger.log_step(f"Started {len(self.workers)} workers")
    
    async def stop(self):
        """Stop all workers"""
        if not self.is_running:
            return
        
        logger.log_step("Stopping queue processor...")
        self.is_running = False
        
        # Stop all workers
        for worker in self.workers:
            await worker.stop()
        
        # Cancel all worker tasks
        for task in self._worker_tasks:
            task.cancel()
        
        # Wait for all tasks to complete
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        
        logger.log_step("Queue processor stopped")
    
    async def add_task(self, 
                      task_type: TaskType, 
                      data: Dict[str, Any], 
                      priority: int = 0) -> int:
        """Add a task to the queue"""
        task_id = await db_manager.add_task(task_type.value, data, priority)
        logger.log_step(f"Added task {task_id}: {task_type.value}")
        return task_id
    
    async def add_video_processing_pipeline(self, video_url: str, priority: int = 0) -> List[int]:
        """Add a complete video processing pipeline"""
        task_ids = []
        
        # 1. Download video
        download_task_id = await self.add_task(
            TaskType.DOWNLOAD_VIDEO,
            {'url': video_url},
            priority
        )
        task_ids.append(download_task_id)
        
        # 2. Upload to Google Drive (depends on download)
        google_task_id = await self.add_task(
            TaskType.UPLOAD_GOOGLE_DRIVE,
            {'depends_on': download_task_id, 'url': video_url},
            priority
        )
        task_ids.append(google_task_id)
        
        # 3. Upload to AIWaverider (depends on download)
        aiwaverider_task_id = await self.add_task(
            TaskType.UPLOAD_AIWAVERIDER,
            {'depends_on': download_task_id, 'url': video_url, 'folder_path': '/videos/instagram/ai.uprise'},
            priority
        )
        task_ids.append(aiwaverider_task_id)
        
        # 4. Update sheets (depends on all uploads)
        sheets_task_id = await self.add_task(
            TaskType.UPDATE_SHEETS,
            {'depends_on': [google_task_id, aiwaverider_task_id], 'url': video_url},
            priority
        )
        task_ids.append(sheets_task_id)
        
        logger.log_step(f"Added video processing pipeline for {video_url} with {len(task_ids)} tasks")
        return task_ids
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        try:
            # Get pending tasks count
            pending_tasks = await db_manager.get_next_task()
            pending_count = 1 if pending_tasks else 0
            
            # Get worker status
            worker_status = []
            for worker in self.workers:
                worker_status.append({
                    'worker_id': worker.worker_id,
                    'is_running': worker.is_running,
                    'current_task': worker.current_task.id if worker.current_task else None,
                    'processed_count': worker.processed_count,
                    'error_count': worker.error_count
                })
            
            return {
                'is_running': self.is_running,
                'pending_tasks': pending_count,
                'active_workers': len([w for w in self.workers if w.is_running]),
                'total_workers': len(self.workers),
                'workers': worker_status
            }
        except Exception as e:
            logger.log_error(f"Failed to get queue status: {str(e)}")
            return {'error': str(e)}

# Global queue processor instance
queue_processor = QueueProcessor()

# Initialize with default workers
queue_processor.add_worker(VideoDownloadWorker())
queue_processor.add_worker(GoogleDriveUploadWorker())
queue_processor.add_worker(AIWaveriderUploadWorker())
queue_processor.add_worker(SheetsUpdateWorker())
