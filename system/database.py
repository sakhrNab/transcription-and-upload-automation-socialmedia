#!/usr/bin/env python3
"""
Database Management System
SQLite-based state management with async support
"""

import aiosqlite
import json
import asyncio
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from .config import settings
from .processor_logger import processor_logger as logger

class DatabaseManager:
    """Async SQLite database manager for state management"""
    
    def __init__(self, db_path: str = "social_media.db"):
        self.db_path = db_path
        self.pool_size = settings.database_pool_size
        self._connection_pool = asyncio.Queue(maxsize=self.pool_size)
        self._initialized = False
        self._lock = asyncio.Lock()
        self._closed = False
    
    async def initialize(self):
        """Initialize database and create tables"""
        async with self._lock:
            if self._initialized or self._closed:
                return
            
            # Create connection pool
            for _ in range(self.pool_size):
                conn = await aiosqlite.connect(
                    self.db_path,
                    timeout=30.0,  # 30 second timeout
                    check_same_thread=False
                )
                await self._connection_pool.put(conn)
            
            # Create tables
            await self._create_tables()
            self._initialized = True
            logger.log_step("Database initialized successfully")
    
    async def _create_tables(self):
        """Create database tables"""
        async with self.get_connection() as conn:
            # Videos table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE NOT NULL,
                    file_path TEXT NOT NULL,
                    url TEXT,
                    drive_id TEXT,
                    drive_url TEXT,
                    upload_status TEXT DEFAULT 'PENDING',
                    transcription_status TEXT DEFAULT 'PENDING',
                    transcription_text TEXT,
                    smart_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Thumbnails table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS thumbnails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE NOT NULL,
                    file_path TEXT NOT NULL,
                    video_filename TEXT,
                    drive_id TEXT,
                    drive_url TEXT,
                    upload_status TEXT DEFAULT 'PENDING',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # AIWaverider uploads table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS aiwaverider_uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    folder_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    upload_status TEXT DEFAULT 'PENDING',
                    upload_id TEXT,
                    total_chunks INTEGER,
                    uploaded_chunks INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Processing queue table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS processing_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    task_data TEXT NOT NULL,
                    status TEXT DEFAULT 'PENDING',
                    priority INTEGER DEFAULT 0,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Metrics table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    metric_unit TEXT,
                    tags TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for better performance
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_videos_filename ON videos(filename)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_videos_drive_id ON videos(drive_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_thumbnails_filename ON thumbnails(filename)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_queue_status ON processing_queue(status)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp)")
            
            await conn.commit()
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool"""
        if self._closed:
            raise RuntimeError("Database manager is closed")
        
        conn = None
        try:
            conn = await asyncio.wait_for(self._connection_pool.get(), timeout=10.0)
            yield conn
        except asyncio.TimeoutError:
            # If pool is empty, create a new connection
            conn = await aiosqlite.connect(
                self.db_path,
                timeout=30.0,
                check_same_thread=False
            )
            try:
                yield conn
            finally:
                await conn.close()
        finally:
            if conn and not self._closed:
                try:
                    await self._connection_pool.put(conn)
                except asyncio.QueueFull:
                    # Pool is full, close the connection
                    await conn.close()
    
    # Video management methods
    async def upsert_video(self, video_data: Dict[str, Any]) -> int:
        """Insert or update video record"""
        async with self.get_connection() as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO videos 
                (filename, file_path, url, drive_id, drive_url, upload_status, 
                 transcription_status, transcription_text, smart_name, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                video_data.get('filename'),
                video_data.get('file_path'),
                video_data.get('url'),
                video_data.get('drive_id'),
                video_data.get('drive_url'),
                video_data.get('upload_status', 'PENDING'),
                video_data.get('transcription_status', 'PENDING'),
                video_data.get('transcription_text'),
                video_data.get('smart_name'),
                datetime.now().isoformat()
            ))
            await conn.commit()
            cursor = await conn.execute("SELECT last_insert_rowid()")
            result = await cursor.fetchone()
            return result[0] if result else None
    
    async def get_video(self, filename: str) -> Optional[Dict[str, Any]]:
        """Get video record by filename"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM videos WHERE filename = ?", (filename,)
            )
            row = await cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
    
    async def get_videos_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get videos by upload status"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM videos WHERE upload_status = ?", (status,)
            )
            rows = await cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    # Thumbnail management methods
    async def upsert_thumbnail(self, thumbnail_data: Dict[str, Any]) -> int:
        """Insert or update thumbnail record"""
        async with self.get_connection() as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO thumbnails 
                (filename, file_path, video_filename, drive_id, drive_url, upload_status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                thumbnail_data.get('filename'),
                thumbnail_data.get('file_path'),
                thumbnail_data.get('video_filename'),
                thumbnail_data.get('drive_id'),
                thumbnail_data.get('drive_url'),
                thumbnail_data.get('upload_status', 'PENDING'),
                datetime.now().isoformat()
            ))
            await conn.commit()
            cursor = await conn.execute("SELECT last_insert_rowid()")
            result = await cursor.fetchone()
            return result[0] if result else None
    
    async def get_thumbnail(self, filename: str) -> Optional[Dict[str, Any]]:
        """Get thumbnail record by filename"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM thumbnails WHERE filename = ?", (filename,)
            )
            row = await cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
    
    # AIWaverider upload management
    async def upsert_aiwaverider_upload(self, upload_data: Dict[str, Any]) -> int:
        """Insert or update AIWaverider upload record"""
        async with self.get_connection() as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO aiwaverider_uploads 
                (filename, file_path, folder_path, file_type, upload_status, 
                 upload_id, total_chunks, uploaded_chunks, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                upload_data.get('filename'),
                upload_data.get('file_path'),
                upload_data.get('folder_path'),
                upload_data.get('file_type'),
                upload_data.get('upload_status', 'PENDING'),
                upload_data.get('upload_id'),
                upload_data.get('total_chunks'),
                upload_data.get('uploaded_chunks', 0),
                datetime.now().isoformat()
            ))
            await conn.commit()
            cursor = await conn.execute("SELECT last_insert_rowid()")
            result = await cursor.fetchone()
            return result[0] if result else None
    
    async def get_aiwaverider_uploads_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get AIWaverider uploads by status"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM aiwaverider_uploads WHERE upload_status = ?", (status,)
            )
            rows = await cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    # Queue management methods
    async def add_task(self, task_type: str, task_data: Dict[str, Any], priority: int = 0) -> int:
        """Add task to processing queue"""
        async with self.get_connection() as conn:
            await conn.execute("""
                INSERT INTO processing_queue (task_type, task_data, priority)
                VALUES (?, ?, ?)
            """, (task_type, json.dumps(task_data), priority))
            await conn.commit()
            cursor = await conn.execute("SELECT last_insert_rowid()")
            result = await cursor.fetchone()
            return result[0] if result else None
    
    async def get_next_task(self, task_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get next task from queue"""
        async with self.get_connection() as conn:
            if task_type:
                cursor = await conn.execute("""
                    SELECT * FROM processing_queue 
                    WHERE status = 'PENDING' AND task_type = ?
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                """, (task_type,))
            else:
                cursor = await conn.execute("""
                    SELECT * FROM processing_queue 
                    WHERE status = 'PENDING'
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                """)
            
            row = await cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                task = dict(zip(columns, row))
                task['task_data'] = json.loads(task['task_data'])
                return task
            return None
    
    async def update_task_status(self, task_id: int, status: str, retry_count: int = 0):
        """Update task status"""
        async with self.get_connection() as conn:
            await conn.execute("""
                UPDATE processing_queue 
                SET status = ?, retry_count = ?, updated_at = ?
                WHERE id = ?
            """, (status, retry_count, datetime.now().isoformat(), task_id))
            await conn.commit()
    
    # Metrics management
    async def record_metric(self, name: str, value: float, unit: str = "", tags: Dict[str, str] = None):
        """Record a metric"""
        if not settings.enable_metrics:
            return
        
        async with self.get_connection() as conn:
            await conn.execute("""
                INSERT INTO metrics (metric_name, metric_value, metric_unit, tags)
                VALUES (?, ?, ?, ?)
            """, (name, value, unit, json.dumps(tags or {})))
            await conn.commit()
    
    async def get_metrics(self, name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get metrics for a specific name within time range"""
        async with self.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT * FROM metrics 
                WHERE metric_name = ? AND timestamp > datetime('now', '-{} hours')
                ORDER BY timestamp DESC
            """.format(hours), (name,))
            rows = await cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    async def cleanup_old_metrics(self, days: int = None):
        """Clean up old metrics"""
        if days is None:
            days = settings.metrics_retention_days
        
        async with self.get_connection() as conn:
            await conn.execute("""
                DELETE FROM metrics 
                WHERE timestamp < datetime('now', '-{} days')
            """.format(days))
            await conn.commit()
    
    async def upsert_thumbnail(self, thumbnail_data: dict) -> int:
        """Upsert thumbnail record"""
        async with self.get_connection() as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO thumbnails 
                (filename, file_path, video_filename, drive_id, drive_url, upload_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                thumbnail_data.get('filename', ''),
                thumbnail_data.get('file_path', ''),
                thumbnail_data.get('video_filename', ''),
                thumbnail_data.get('drive_id'),
                thumbnail_data.get('drive_url'),
                thumbnail_data.get('upload_status', 'PENDING'),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            await conn.commit()
            cursor = await conn.execute("SELECT last_insert_rowid()")
            result = await cursor.fetchone()
            return result[0] if result else None

    async def upsert_aiwaverider_upload(self, upload_data: dict) -> int:
        """Upsert AIWaverider upload record"""
        async with self.get_connection() as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO aiwaverider_uploads 
                (filename, file_path, folder_path, file_type, upload_status, upload_id, total_chunks, uploaded_chunks, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                upload_data.get('filename', ''),
                upload_data.get('file_path', ''),
                upload_data.get('folder_path', ''),
                upload_data.get('file_type', ''),
                upload_data.get('upload_status', 'PENDING'),
                upload_data.get('upload_id'),
                upload_data.get('total_chunks', 0),
                upload_data.get('uploaded_chunks', 0),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            await conn.commit()
            cursor = await conn.execute("SELECT last_insert_rowid()")
            result = await cursor.fetchone()
            return result[0] if result else None

    async def store_cache_data(self, folder_path: str, cache_data: dict):
        """Store cache data in database"""
        # For now, we'll just log that cache data was stored
        # In a full implementation, you might want to store this in a cache table
        logger.log_step(f"Cache data stored for {folder_path}: {len(cache_data)} items")

    async def get_videos_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get videos by status"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM videos WHERE upload_status = ?", (status,)
            )
            rows = await cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    async def get_all_videos(self) -> List[Dict[str, Any]]:
        """Get all videos"""
        async with self.get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM videos")
            rows = await cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    async def get_thumbnails_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get thumbnails by status"""
        async with self.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM thumbnails WHERE upload_status = ?", (status,)
            )
            rows = await cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
    
    async def get_all_thumbnails(self) -> List[Dict[str, Any]]:
        """Get all thumbnails"""
        async with self.get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM thumbnails")
            rows = await cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

    async def close(self):
        """Close all database connections"""
        async with self._lock:
            if self._closed:
                return
                
            self._closed = True
            
            try:
                # Close all connections in the pool
                connections_to_close = []
                while not self._connection_pool.empty():
                    try:
                        conn = await asyncio.wait_for(self._connection_pool.get(), timeout=0.5)
                        connections_to_close.append(conn)
                    except asyncio.TimeoutError:
                        break
                
                # Close all connections
                for conn in connections_to_close:
                    try:
                        await conn.close()
                    except Exception as e:
                        logger.log_error(f"Error closing individual connection: {str(e)}")
                
                self._initialized = False
                logger.log_step("Database connections closed successfully")
                
            except Exception as e:
                logger.log_error(f"Error closing database connections: {str(e)}")
                self._initialized = False

# Global database instance
db_manager = DatabaseManager()
