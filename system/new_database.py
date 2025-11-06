#!/usr/bin/env python3
"""
New Database Management System with Separated Concerns
video_transcripts table: Tracks downloads and transcripts
upload_tracking table: Tracks uploads to Google Drive and AIWaverider
"""

import aiosqlite
import json
import asyncio
import threading
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from .config import settings
from .processor_logger import processor_logger as logger

class NewDatabaseManager:
    """Database manager with separated concerns for video transcripts and upload tracking"""
    
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
                    timeout=30.0,
                    check_same_thread=False
                )
                await self._connection_pool.put(conn)
            
            # Create tables
            await self._create_tables()
            self._initialized = True
            logger.log_step("New database initialized successfully")
    
    async def _create_tables(self):
        """Create database tables with new schema"""
        import os
        from pathlib import Path
        
        # Find schema file - try multiple locations
        schema_paths = [
            'new_database_schema.sql',  # Current directory
            '../new_database_schema.sql',  # Parent directory
            Path(__file__).parent.parent / 'new_database_schema.sql',  # Project root
        ]
        
        schema_sql = None
        for schema_path in schema_paths:
            try:
                with open(schema_path, 'r') as f:
                    schema_sql = f.read()
                    logger.log_step(f"Found schema file at: {schema_path}")
                    break
            except FileNotFoundError:
                continue
        
        if not schema_sql:
            # If schema file not found, create tables manually
            logger.log_step("Schema file not found, creating tables manually")
            await self._create_tables_manually()
            return
        
        conn = await aiosqlite.connect(self.db_path)
        await conn.executescript(schema_sql)
        await conn.commit()
        await conn.close()
    
    async def _create_tables_manually(self):
        """Create tables manually if schema file is not found"""
        conn = await aiosqlite.connect(self.db_path)
        
        # Create video_transcripts table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS video_transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                url TEXT,
                title TEXT,
                description TEXT,
                username TEXT,
                uploader_id TEXT,
                channel_id TEXT,
                channel_url TEXT,
                platform TEXT,
                duration INTEGER,
                width INTEGER,
                height INTEGER,
                fps REAL,
                format_id TEXT,
                view_count INTEGER,
                like_count INTEGER,
                comment_count INTEGER,
                upload_date TEXT,
                thumbnail_url TEXT,
                webpage_url TEXT,
                extractor TEXT,
                transcription_text TEXT,
                transcription_status TEXT DEFAULT 'PENDING',
                smart_name TEXT,
                transcript_file_path TEXT,
                audio_file_path TEXT,
                thumbnail_file_path TEXT,
                video_file_size_mb REAL,
                transcript_word_count INTEGER,
                processing_time_seconds REAL,
                notes TEXT,
                error_details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create upload_tracking table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS upload_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_hash TEXT,
                gdrive_id TEXT,
                gdrive_url TEXT,
                gdrive_upload_status TEXT DEFAULT 'PENDING',
                gdrive_upload_date TIMESTAMP,
                gdrive_folder_id TEXT,
                aiwaverider_id TEXT,
                aiwaverider_url TEXT,
                aiwaverider_upload_status TEXT DEFAULT 'PENDING',
                aiwaverider_upload_date TIMESTAMP,
                aiwaverider_folder_path TEXT,
                upload_attempts INTEGER DEFAULT 0,
                last_upload_attempt TIMESTAMP,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(video_id, file_type)
            )
        """)
        
        # Create processing_queue table
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
        
        # Create urls table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                source TEXT DEFAULT 'manual',
                status TEXT DEFAULT 'PENDING',
                download_status TEXT DEFAULT 'PENDING',
                video_id TEXT,
                downloaded_at TIMESTAMP,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES video_transcripts(video_id)
            )
        """)
        
        # Create index for urls
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_urls_url ON urls(url);
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_urls_status ON urls(status);
        """)
        
        await conn.commit()
        await conn.close()
        logger.log_step("Tables created manually")
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool"""
        if self._closed:
            raise RuntimeError("Database manager is closed")
        
        conn = await self._connection_pool.get()
        try:
            yield conn
        finally:
            await self._connection_pool.put(conn)
    
    # Video Transcripts Methods
    async def upsert_video_transcript(self, video_data: Dict[str, Any]) -> bool:
        """Insert or update video transcript data"""
        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    INSERT OR REPLACE INTO video_transcripts (
                        video_id, filename, file_path, url, title, description,
                        username, uploader_id, channel_id, channel_url, platform,
                        duration, width, height, fps, format_id, view_count,
                        like_count, comment_count, upload_date, thumbnail_url,
                        webpage_url, extractor, transcription_text, transcription_status,
                        smart_name, transcript_file_path, audio_file_path, thumbnail_file_path,
                        video_file_size_mb, transcript_word_count, processing_time_seconds,
                        notes, error_details, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    video_data.get('video_id', ''),
                    video_data.get('filename', ''),
                    video_data.get('file_path', ''),
                    video_data.get('url', ''),
                    video_data.get('title', ''),
                    video_data.get('description', ''),
                    video_data.get('username', ''),
                    video_data.get('uploader_id', ''),
                    video_data.get('channel_id', ''),
                    video_data.get('channel_url', ''),
                    video_data.get('platform', ''),
                    video_data.get('duration', 0),
                    video_data.get('width'),
                    video_data.get('height'),
                    video_data.get('fps'),
                    video_data.get('format_id', ''),
                    video_data.get('view_count'),
                    video_data.get('like_count'),
                    video_data.get('comment_count'),
                    video_data.get('upload_date', ''),
                    video_data.get('thumbnail_url', ''),
                    video_data.get('webpage_url', ''),
                    video_data.get('extractor', ''),
                    video_data.get('transcription_text', ''),
                    video_data.get('transcription_status', 'PENDING'),
                    video_data.get('smart_name', ''),
                    video_data.get('transcript_file_path', ''),
                    video_data.get('audio_file_path', ''),
                    video_data.get('thumbnail_file_path', ''),
                    video_data.get('video_file_size_mb'),
                    video_data.get('transcript_word_count'),
                    video_data.get('processing_time_seconds'),
                    video_data.get('notes', ''),
                    video_data.get('error_details', ''),
                    datetime.now().isoformat()
                ))
                await conn.commit()
                return True
        except Exception as e:
            logger.log_error(f"Error upserting video transcript: {str(e)}")
            return False
    
    async def get_all_video_transcripts(self) -> List[Dict[str, Any]]:
        """Get all video transcripts"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("SELECT * FROM video_transcripts")
                rows = await cursor.fetchall()
                
                # Get column names
                cursor = await conn.execute("PRAGMA table_info(video_transcripts)")
                columns = [col[1] for col in await cursor.fetchall()]
                
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.log_error(f"Error getting video transcripts: {str(e)}")
            return []
    
    async def get_video_transcript_by_id(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get video transcript by video_id"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("SELECT * FROM video_transcripts WHERE video_id = ?", (video_id,))
                row = await cursor.fetchone()
                
                if row:
                    cursor = await conn.execute("PRAGMA table_info(video_transcripts)")
                    columns = [col[1] for col in await cursor.fetchall()]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            logger.log_error(f"Error getting video transcript by ID: {str(e)}")
            return None
    
    # Upload Tracking Methods
    async def upsert_upload_tracking(self, upload_data: Dict[str, Any]) -> bool:
        """Insert or update upload tracking data"""
        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    INSERT OR REPLACE INTO upload_tracking (
                        video_id, filename, file_path, file_type, file_hash,
                        gdrive_id, gdrive_url, gdrive_upload_status, gdrive_upload_date, gdrive_folder_id,
                        aiwaverider_id, aiwaverider_url, aiwaverider_upload_status, aiwaverider_upload_date, aiwaverider_folder_path,
                        upload_attempts, last_upload_attempt, error_message, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    upload_data.get('video_id', ''),
                    upload_data.get('filename', ''),
                    upload_data.get('file_path', ''),
                    upload_data.get('file_type', 'video'),
                    upload_data.get('file_hash', ''),
                    upload_data.get('gdrive_id', ''),
                    upload_data.get('gdrive_url', ''),
                    upload_data.get('gdrive_upload_status', 'PENDING'),
                    upload_data.get('gdrive_upload_date'),
                    upload_data.get('gdrive_folder_id', ''),
                    upload_data.get('aiwaverider_id', ''),
                    upload_data.get('aiwaverider_url', ''),
                    upload_data.get('aiwaverider_upload_status', 'PENDING'),
                    upload_data.get('aiwaverider_upload_date'),
                    upload_data.get('aiwaverider_folder_path', ''),
                    upload_data.get('upload_attempts', 0),
                    upload_data.get('last_upload_attempt'),
                    upload_data.get('error_message', ''),
                    datetime.now().isoformat()
                ))
                await conn.commit()
                return True
        except Exception as e:
            logger.log_error(f"Error upserting upload tracking: {str(e)}")
            return False
    
    async def get_upload_tracking_by_video_id(self, video_id: str, file_type: str = None) -> List[Dict[str, Any]]:
        """Get upload tracking by video_id and optionally file_type"""
        try:
            async with self.get_connection() as conn:
                if file_type:
                    cursor = await conn.execute(
                        "SELECT * FROM upload_tracking WHERE video_id = ? AND file_type = ?", 
                        (video_id, file_type)
                    )
                else:
                    cursor = await conn.execute("SELECT * FROM upload_tracking WHERE video_id = ?", (video_id,))
                
                rows = await cursor.fetchall()
                
                # Get column names
                cursor = await conn.execute("PRAGMA table_info(upload_tracking)")
                columns = [col[1] for col in await cursor.fetchall()]
                
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.log_error(f"Error getting upload tracking: {str(e)}")
            return []
    
    async def get_all_upload_tracking(self) -> List[Dict[str, Any]]:
        """Get all upload tracking data"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("SELECT * FROM upload_tracking")
                rows = await cursor.fetchall()
                
                # Get column names
                cursor = await conn.execute("PRAGMA table_info(upload_tracking)")
                columns = [col[1] for col in await cursor.fetchall()]
                
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.log_error(f"Error getting all upload tracking: {str(e)}")
            return []
    
    async def update_upload_status(self, video_id: str, file_type: str, 
                                 gdrive_status: str = None, aiwaverider_status: str = None,
                                 gdrive_id: str = None, gdrive_url: str = None,
                                 aiwaverider_id: str = None, aiwaverider_url: str = None) -> bool:
        """Update upload status for a specific file"""
        try:
            async with self.get_connection() as conn:
                update_fields = []
                update_values = []
                
                if gdrive_status:
                    update_fields.append("gdrive_upload_status = ?")
                    update_values.append(gdrive_status)
                    if gdrive_status == 'COMPLETED':
                        update_fields.append("gdrive_upload_date = ?")
                        update_values.append(datetime.now().isoformat())
                
                if aiwaverider_status:
                    update_fields.append("aiwaverider_upload_status = ?")
                    update_values.append(aiwaverider_status)
                    if aiwaverider_status == 'COMPLETED':
                        update_fields.append("aiwaverider_upload_date = ?")
                        update_values.append(datetime.now().isoformat())
                
                if gdrive_id:
                    update_fields.append("gdrive_id = ?")
                    update_values.append(gdrive_id)
                
                if gdrive_url:
                    update_fields.append("gdrive_url = ?")
                    update_values.append(gdrive_url)
                
                if aiwaverider_id:
                    update_fields.append("aiwaverider_id = ?")
                    update_values.append(aiwaverider_id)
                
                if aiwaverider_url:
                    update_fields.append("aiwaverider_url = ?")
                    update_values.append(aiwaverider_url)
                
                if update_fields:
                    update_fields.append("updated_at = ?")
                    update_values.append(datetime.now().isoformat())
                    update_values.extend([video_id, file_type])
                    
                    query = f"UPDATE upload_tracking SET {', '.join(update_fields)} WHERE video_id = ? AND file_type = ?"
                    await conn.execute(query, update_values)
                    await conn.commit()
                    return True
                
                return False
        except Exception as e:
            logger.log_error(f"Error updating upload status: {str(e)}")
            return False
    
    async def is_file_uploaded(self, video_id: str, file_type: str, platform: str = 'both') -> bool:
        """Check if a file has been uploaded to the specified platform(s)"""
        try:
            async with self.get_connection() as conn:
                if platform == 'both':
                    cursor = await conn.execute("""
                        SELECT * FROM upload_tracking 
                        WHERE video_id = ? AND file_type = ? 
                        AND gdrive_upload_status = 'COMPLETED' 
                        AND aiwaverider_upload_status = 'COMPLETED'
                    """, (video_id, file_type))
                elif platform == 'gdrive':
                    cursor = await conn.execute("""
                        SELECT * FROM upload_tracking 
                        WHERE video_id = ? AND file_type = ? 
                        AND gdrive_upload_status = 'COMPLETED'
                    """, (video_id, file_type))
                elif platform == 'aiwaverider':
                    cursor = await conn.execute("""
                        SELECT * FROM upload_tracking 
                        WHERE video_id = ? AND file_type = ? 
                        AND aiwaverider_upload_status = 'COMPLETED'
                    """, (video_id, file_type))
                else:
                    return False
                
                row = await cursor.fetchone()
                return row is not None
        except Exception as e:
            logger.log_error(f"Error checking upload status: {str(e)}")
            return False
    
    # Queue management methods (for compatibility with queue processor)
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

    async def close(self):
        """Close all database connections"""
        async with self._lock:
            if self._closed:
                return
            
            self._closed = True
            
            # Close all connections in pool
            while not self._connection_pool.empty():
                try:
                    conn = await asyncio.wait_for(self._connection_pool.get(), timeout=1.0)
                    await conn.close()
                except asyncio.TimeoutError:
                    break
                except Exception:
                    pass
            
            logger.log_step("Database connections closed")

    # Compatibility methods for old database interface
    async def upsert_video(self, video_data: Dict[str, Any]) -> int:
        """Compatibility method - maps to video_transcripts table"""
        success = await self.upsert_video_transcript(video_data)
        return 1 if success else 0
    
    async def get_video(self, filename: str) -> Optional[Dict[str, Any]]:
        """Compatibility method - get video by filename"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("SELECT * FROM video_transcripts WHERE filename = ?", (filename,))
                row = await cursor.fetchone()
                
                if row:
                    cursor = await conn.execute("PRAGMA table_info(video_transcripts)")
                    columns = [col[1] for col in await cursor.fetchall()]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            logger.log_error(f"Error getting video by filename: {str(e)}")
            return None
    
    async def get_videos_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Compatibility method - get videos by transcription status"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("SELECT * FROM video_transcripts WHERE transcription_status = ?", (status,))
                rows = await cursor.fetchall()
                
                cursor = await conn.execute("PRAGMA table_info(video_transcripts)")
                columns = [col[1] for col in await cursor.fetchall()]
                
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.log_error(f"Error getting videos by status: {str(e)}")
            return []
    
    async def get_all_videos(self) -> List[Dict[str, Any]]:
        """Compatibility method - get all videos"""
        return await self.get_all_video_transcripts()
    
    async def upsert_thumbnail(self, thumbnail_data: Dict[str, Any]) -> int:
        """Compatibility method - maps to upload_tracking table"""
        # Extract video_id from filename or video_filename
        video_id = thumbnail_data.get('video_id', '')
        if not video_id:
            filename = thumbnail_data.get('filename', '')
            if '_' in filename:
                video_id = filename.split('_')[-1].replace('.jpg', '').replace('.png', '')
            else:
                video_id = filename.replace('.jpg', '').replace('.png', '')
        
        upload_data = {
            'video_id': video_id,
            'filename': thumbnail_data.get('filename', ''),
            'file_path': thumbnail_data.get('file_path', ''),
            'file_type': 'thumbnail',
            'file_hash': thumbnail_data.get('file_hash', ''),
            'gdrive_id': thumbnail_data.get('drive_id', ''),
            'gdrive_url': thumbnail_data.get('drive_url', ''),
            'gdrive_upload_status': thumbnail_data.get('upload_status', 'PENDING'),
            'aiwaverider_upload_status': thumbnail_data.get('aiwaverider_status', 'PENDING')
        }
        
        success = await self.upsert_upload_tracking(upload_data)
        return 1 if success else 0
    
    async def get_thumbnail(self, filename: str) -> Optional[Dict[str, Any]]:
        """Compatibility method - get thumbnail by filename"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("SELECT * FROM upload_tracking WHERE filename = ? AND file_type = 'thumbnail'", (filename,))
                row = await cursor.fetchone()
                
                if row:
                    cursor = await conn.execute("PRAGMA table_info(upload_tracking)")
                    columns = [col[1] for col in await cursor.fetchall()]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            logger.log_error(f"Error getting thumbnail by filename: {str(e)}")
            return None
    
    async def get_thumbnails_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Compatibility method - get thumbnails by upload status"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("SELECT * FROM upload_tracking WHERE file_type = 'thumbnail' AND gdrive_upload_status = ?", (status,))
                rows = await cursor.fetchall()
                
                cursor = await conn.execute("PRAGMA table_info(upload_tracking)")
                columns = [col[1] for col in await cursor.fetchall()]
                
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.log_error(f"Error getting thumbnails by status: {str(e)}")
            return []
    
    async def get_all_thumbnails(self) -> List[Dict[str, Any]]:
        """Compatibility method - get all thumbnails"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("SELECT * FROM upload_tracking WHERE file_type = 'thumbnail'")
                rows = await cursor.fetchall()
                
                cursor = await conn.execute("PRAGMA table_info(upload_tracking)")
                columns = [col[1] for col in await cursor.fetchall()]
                
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.log_error(f"Error getting all thumbnails: {str(e)}")
            return []
    
    async def update_video_status(self, video_id: int, status: str, drive_id: str = None):
        """Compatibility method - update video upload status"""
        # This is a bit tricky since we need to map video_id to filename
        # For now, we'll update the upload_tracking table
        try:
            async with self.get_connection() as conn:
                if drive_id:
                    await conn.execute("""
                        UPDATE upload_tracking 
                        SET gdrive_upload_status = ?, gdrive_id = ?, updated_at = ?
                        WHERE video_id = ? AND file_type = 'video'
                    """, (status, drive_id, datetime.now().isoformat(), str(video_id)))
                else:
                    await conn.execute("""
                        UPDATE upload_tracking 
                        SET gdrive_upload_status = ?, updated_at = ?
                        WHERE video_id = ? AND file_type = 'video'
                    """, (status, datetime.now().isoformat(), str(video_id)))
                await conn.commit()
        except Exception as e:
            logger.log_error(f"Error updating video status: {str(e)}")
    
    async def update_thumbnail_status(self, thumbnail_id: int, status: str, drive_id: str = None):
        """Compatibility method - update thumbnail upload status"""
        try:
            async with self.get_connection() as conn:
                if drive_id:
                    await conn.execute("""
                        UPDATE upload_tracking 
                        SET gdrive_upload_status = ?, gdrive_id = ?, updated_at = ?
                        WHERE id = ? AND file_type = 'thumbnail'
                    """, (status, drive_id, datetime.now().isoformat(), thumbnail_id))
                else:
                    await conn.execute("""
                        UPDATE upload_tracking 
                        SET gdrive_upload_status = ?, updated_at = ?
                        WHERE id = ? AND file_type = 'thumbnail'
                    """, (status, datetime.now().isoformat(), thumbnail_id))
                await conn.commit()
        except Exception as e:
            logger.log_error(f"Error updating thumbnail status: {str(e)}")
    
    async def update_video_aiwaverider_status(self, video_id: int, status: str):
        """Compatibility method - update video AIWaverider status"""
        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    UPDATE upload_tracking 
                    SET aiwaverider_upload_status = ?, updated_at = ?
                    WHERE video_id = ? AND file_type = 'video'
                """, (status, datetime.now().isoformat(), str(video_id)))
                await conn.commit()
        except Exception as e:
            logger.log_error(f"Error updating video AIWaverider status: {str(e)}")
    
    async def update_thumbnail_aiwaverider_status(self, thumbnail_id: int, status: str):
        """Compatibility method - update thumbnail AIWaverider status"""
        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    UPDATE upload_tracking 
                    SET aiwaverider_upload_status = ?, updated_at = ?
                    WHERE id = ? AND file_type = 'thumbnail'
                """, (status, datetime.now().isoformat(), thumbnail_id))
                await conn.commit()
        except Exception as e:
            logger.log_error(f"Error updating thumbnail AIWaverider status: {str(e)}")
    
    async def get_videos_by_video_id(self, video_id: str) -> List[Dict[str, Any]]:
        """Compatibility method - get videos by video_id"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("SELECT * FROM video_transcripts WHERE video_id = ?", (video_id,))
                rows = await cursor.fetchall()
                
                cursor = await conn.execute("PRAGMA table_info(video_transcripts)")
                columns = [col[1] for col in await cursor.fetchall()]
                
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            logger.log_error(f"Error getting videos by video_id: {str(e)}")
            return []
    
    async def get_video_transcript_by_index(self, video_index: int) -> Optional[Dict[str, Any]]:
        """Get video transcript by processing index"""
        try:
            async with self.get_connection() as conn:
                # Get the most recently added video (for download-only mode, this should be the current video)
                cursor = await conn.execute("""
                    SELECT * FROM video_transcripts 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """)
                row = await cursor.fetchone()
                
                if row:
                    cursor = await conn.execute("PRAGMA table_info(video_transcripts)")
                    columns = [col[1] for col in await cursor.fetchall()]
                    result = dict(zip(columns, row))
                    # Debug logging
                    logger.log_step(f"Retrieved most recent video: {result.get('title', 'NO_TITLE')} - Thumbnail: {result.get('thumbnail_file_path', 'NO_THUMBNAIL')}")
                    return result
                else:
                    logger.log_step(f"No videos found in database")
                    return None
        except Exception as e:
            logger.log_error(f"Error getting video transcript by index: {str(e)}")
            return None
    
    async def update_thumbnail_status_by_video_index(self, video_index: int, status: str) -> bool:
        """Update thumbnail status by video index"""
        try:
            async with self.get_connection() as conn:
                # Update the most recently added video's thumbnail status
                await conn.execute("""
                    UPDATE video_transcripts 
                    SET thumbnail_status = ?, updated_at = ?
                    WHERE id = (
                        SELECT id FROM video_transcripts 
                        ORDER BY created_at DESC 
                        LIMIT 1
                    )
                """, (status, datetime.now().isoformat()))
                await conn.commit()
                return True
        except Exception as e:
            logger.log_error(f"Error updating thumbnail status by video index: {str(e)}")
            return False
    
    async def get_video_transcript_by_filename(self, filename: str) -> Optional[Dict[str, Any]]:
        """Get video transcript by filename"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("SELECT * FROM video_transcripts WHERE filename = ?", (filename,))
                row = await cursor.fetchone()
                
                if row:
                    cursor = await conn.execute("PRAGMA table_info(video_transcripts)")
                    columns = [col[1] for col in await cursor.fetchall()]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            logger.log_error(f"Error getting video transcript by filename: {str(e)}")
            return None
    
    async def get_upload_tracking_by_filename(self, filename: str) -> Optional[Dict[str, Any]]:
        """Get upload tracking by filename"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("SELECT * FROM upload_tracking WHERE filename = ?", (filename,))
                row = await cursor.fetchone()
                
                if row:
                    cursor = await conn.execute("PRAGMA table_info(upload_tracking)")
                    columns = [col[1] for col in await cursor.fetchall()]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            logger.log_error(f"Error getting upload tracking by filename: {str(e)}")
            return None
    
    async def get_all_videos_with_transcripts(self) -> List[Dict[str, Any]]:
        """Get all videos that have transcripts"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT * FROM video_transcripts 
                    WHERE transcription_text IS NOT NULL 
                    AND transcription_text != '' 
                    AND transcription_status = 'COMPLETED'
                    ORDER BY created_at DESC
                """)
                rows = await cursor.fetchall()
                
                if rows:
                    cursor = await conn.execute("PRAGMA table_info(video_transcripts)")
                    columns = [col[1] for col in await cursor.fetchall()]
                    return [dict(zip(columns, row)) for row in rows]
                return []
        except Exception as e:
            logger.log_error(f"Error getting videos with transcripts: {str(e)}")
            return []
    
    # URLs Methods
    async def _ensure_urls_table_exists(self):
        """Ensure URLs table exists with all required columns, create or migrate if needed"""
        try:
            async with self.get_connection() as conn:
                # Check if table exists
                cursor = await conn.execute("""
                    SELECT name FROM sqlite_master WHERE type='table' AND name='urls'
                """)
                exists = await cursor.fetchone()
                
                if not exists:
                    # Create the table with all columns
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS urls (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            url TEXT UNIQUE NOT NULL,
                            source TEXT DEFAULT 'manual',
                            status TEXT DEFAULT 'PENDING',
                            download_status TEXT DEFAULT 'PENDING',
                            video_id TEXT,
                            downloaded_at TIMESTAMP,
                            transcription_status TEXT DEFAULT 'PENDING',
                            notes TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (video_id) REFERENCES video_transcripts(video_id)
                        )
                    """)
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_urls_url ON urls(url)")
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_urls_status ON urls(status)")
                    await conn.commit()
                    logger.log_step("URLs table created")
                else:
                    # Table exists, check for missing columns and add them
                    cursor = await conn.execute("PRAGMA table_info(urls)")
                    columns = [col[1] for col in await cursor.fetchall()]
                    
                    # Add missing columns
                    if 'download_status' not in columns:
                        await conn.execute("ALTER TABLE urls ADD COLUMN download_status TEXT DEFAULT 'PENDING'")
                        logger.log_step("Added download_status column to urls table")
                    
                    if 'video_id' not in columns:
                        await conn.execute("ALTER TABLE urls ADD COLUMN video_id TEXT")
                        logger.log_step("Added video_id column to urls table")
                    
                    if 'downloaded_at' not in columns:
                        await conn.execute("ALTER TABLE urls ADD COLUMN downloaded_at TIMESTAMP")
                        logger.log_step("Added downloaded_at column to urls table")
                    
                    if 'transcription_status' not in columns:
                        await conn.execute("ALTER TABLE urls ADD COLUMN transcription_status TEXT DEFAULT 'PENDING'")
                        logger.log_step("Added transcription_status column to urls table")
                    
                    await conn.commit()
        except Exception as e:
            logger.log_error(f"Error ensuring URLs table exists: {str(e)}")
    
    async def add_url(self, url: str, source: str = 'manual', status: str = 'PENDING', download_status: str = 'PENDING', notes: str = None) -> bool:
        """Add a URL to the database"""
        try:
            # Ensure table exists first
            await self._ensure_urls_table_exists()
            
            async with self.get_connection() as conn:
                await conn.execute("""
                    INSERT OR IGNORE INTO urls (url, source, status, download_status, notes, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (url, source, status, download_status, notes, datetime.now().isoformat()))
                await conn.commit()
                return True
        except Exception as e:
            logger.log_error(f"Error adding URL: {str(e)}")
            return False
    
    async def get_all_urls(self, status: str = None) -> List[Dict[str, Any]]:
        """Get all URLs from database with video transcript info, optionally filtered by status"""
        try:
            # Ensure table exists and has all columns
            await self._ensure_urls_table_exists()
            
            async with self.get_connection() as conn:
                # Check if video_id column exists
                cursor = await conn.execute("PRAGMA table_info(urls)")
                columns_info = await cursor.fetchall()
                url_columns = [col[1] for col in columns_info]
                has_video_id = 'video_id' in url_columns
                
                # Check if transcription_status column exists in urls table
                has_transcription_status = 'transcription_status' in url_columns
                
                if has_video_id:
                    # Use JOIN if video_id column exists
                    # Prefer transcription_status from urls table, fallback to video_transcripts
                    if status:
                        if has_transcription_status:
                            # Use transcription_status from urls table directly, sync with video_transcripts if needed
                            cursor = await conn.execute("""
                                SELECT 
                                    u.id, u.url, u.source, u.status, u.download_status, u.video_id, 
                                    u.downloaded_at, u.transcription_status, u.notes, u.created_at, u.updated_at,
                                    COALESCE(u.transcription_status, v.transcription_status, v2.transcription_status) as transcription_status,
                                    COALESCE(v.filename, v2.filename) as video_filename,
                                    COALESCE(v.smart_name, v2.smart_name) as video_name
                                FROM urls u
                                LEFT JOIN video_transcripts v ON u.video_id = v.video_id AND u.video_id IS NOT NULL
                                LEFT JOIN video_transcripts v2 ON u.url = v2.url AND (u.video_id IS NULL OR v.transcription_status IS NULL)
                                WHERE u.status = ? 
                                ORDER BY u.created_at DESC
                            """, (status,))
                        else:
                            # Fallback to old JOIN method if column doesn't exist
                            cursor = await conn.execute("""
                                SELECT 
                                    u.id, u.url, u.source, u.status, u.download_status, u.video_id, 
                                    u.downloaded_at, u.notes, u.created_at, u.updated_at,
                                    COALESCE(v.transcription_status, v2.transcription_status) as transcription_status,
                                    COALESCE(v.filename, v2.filename) as video_filename,
                                    COALESCE(v.smart_name, v2.smart_name) as video_name
                                FROM urls u
                                LEFT JOIN video_transcripts v ON u.video_id = v.video_id AND u.video_id IS NOT NULL
                                LEFT JOIN video_transcripts v2 ON u.url = v2.url AND (u.video_id IS NULL OR v.transcription_status IS NULL)
                                WHERE u.status = ? 
                                ORDER BY u.created_at DESC
                            """, (status,))
                    else:
                        if has_transcription_status:
                            # Use transcription_status from urls table directly
                            cursor = await conn.execute("""
                                SELECT 
                                    u.id, u.url, u.source, u.status, u.download_status, u.video_id, 
                                    u.downloaded_at, u.notes, u.created_at, u.updated_at,
                                    COALESCE(u.transcription_status, v.transcription_status, v2.transcription_status) as transcription_status,
                                    COALESCE(v.filename, v2.filename) as video_filename,
                                    COALESCE(v.smart_name, v2.smart_name) as video_name
                                FROM urls u
                                LEFT JOIN video_transcripts v ON u.video_id = v.video_id AND u.video_id IS NOT NULL
                                LEFT JOIN video_transcripts v2 ON u.url = v2.url AND (u.video_id IS NULL OR v.transcription_status IS NULL)
                                ORDER BY u.created_at DESC
                            """)
                        else:
                            # Fallback to old JOIN method if column doesn't exist
                            cursor = await conn.execute("""
                                SELECT 
                                    u.id, u.url, u.source, u.status, u.download_status, u.video_id, 
                                    u.downloaded_at, u.notes, u.created_at, u.updated_at,
                                    COALESCE(v.transcription_status, v2.transcription_status) as transcription_status,
                                    COALESCE(v.filename, v2.filename) as video_filename,
                                    COALESCE(v.smart_name, v2.smart_name) as video_name
                                FROM urls u
                                LEFT JOIN video_transcripts v ON u.video_id = v.video_id AND u.video_id IS NOT NULL
                                LEFT JOIN video_transcripts v2 ON u.url = v2.url AND (u.video_id IS NULL OR v.transcription_status IS NULL)
                                ORDER BY u.created_at DESC
                            """)
                else:
                    # Fallback: get URLs without JOIN if video_id doesn't exist
                    if status:
                        cursor = await conn.execute("""
                            SELECT * FROM urls WHERE status = ? ORDER BY created_at DESC
                        """, (status,))
                    else:
                        cursor = await conn.execute("""
                            SELECT * FROM urls ORDER BY created_at DESC
                        """)
                
                rows = await cursor.fetchall()
                
                # Get column names from the actual query result (cursor.description)
                # This is the correct way to get column names from a SELECT query
                if cursor.description:
                    all_columns = [col[0] for col in cursor.description]
                else:
                    # Fallback: use table_info
                    url_columns = [col[1] for col in columns_info]
                    if has_video_id:
                        all_columns = url_columns + ['transcription_status', 'video_filename', 'video_name']
                    else:
                        all_columns = url_columns + ['transcription_status', 'video_filename', 'video_name']
                        # Pad rows with None for missing join columns
                        rows = [row + (None, None, None) for row in rows]
                
                # Convert rows to dictionaries
                result = []
                for row in rows:
                    row_dict = dict(zip(all_columns, row))
                    # Ensure transcription_status is set (might be None from JOIN)
                    if row_dict.get('transcription_status') is None:
                        # Try to get it directly from video_transcripts if we have video_id or url
                        video_id = row_dict.get('video_id')
                        url = row_dict.get('url')
                        if video_id or url:
                            try:
                                async with self.get_connection() as conn:
                                    if video_id:
                                        cursor = await conn.execute(
                                            "SELECT transcription_status FROM video_transcripts WHERE video_id = ?",
                                            (video_id,)
                                        )
                                    elif url:
                                        cursor = await conn.execute(
                                            "SELECT transcription_status FROM video_transcripts WHERE url = ?",
                                            (url,)
                                        )
                                    else:
                                        cursor = None
                                    
                                    if cursor:
                                        status_row = await cursor.fetchone()
                                        if status_row:
                                            row_dict['transcription_status'] = status_row[0]
                            except Exception as e:
                                logger.log_error(f"Error fetching transcription_status: {e}")
                    result.append(row_dict)
                
                return result
        except Exception as e:
            logger.log_error(f"Error getting URLs: {str(e)}")
            return []
    
    async def update_url_status(self, url: str, status: str = None, download_status: str = None, video_id: str = None, downloaded_at: str = None, transcription_status: str = None, notes: str = None) -> bool:
        """Update URL status and download info"""
        try:
            # Ensure table exists with all columns
            await self._ensure_urls_table_exists()
            
            async with self.get_connection() as conn:
                # Check which columns exist
                cursor = await conn.execute("PRAGMA table_info(urls)")
                columns_info = await cursor.fetchall()
                existing_columns = [col[1] for col in columns_info]
                
                updates = []
                values = []
                
                if status is not None and 'status' in existing_columns:
                    updates.append("status = ?")
                    values.append(status)
                if download_status is not None and 'download_status' in existing_columns:
                    updates.append("download_status = ?")
                    values.append(download_status)
                if video_id is not None and 'video_id' in existing_columns:
                    updates.append("video_id = ?")
                    values.append(video_id)
                if downloaded_at is not None and 'downloaded_at' in existing_columns:
                    updates.append("downloaded_at = ?")
                    values.append(downloaded_at)
                if transcription_status is not None and 'transcription_status' in existing_columns:
                    updates.append("transcription_status = ?")
                    values.append(transcription_status)
                if notes is not None and 'notes' in existing_columns:
                    updates.append("notes = ?")
                    values.append(notes)
                
                if 'updated_at' in existing_columns:
                    updates.append("updated_at = ?")
                    values.append(datetime.now().isoformat())
                
                values.append(url)
                
                if updates:
                    query = f"UPDATE urls SET {', '.join(updates)} WHERE url = ?"
                    await conn.execute(query, values)
                    await conn.commit()
                    logger.log_step(f"Updated URL status for: {url} (download_status={download_status}, video_id={video_id})")
                    return True
                return False
        except Exception as e:
            logger.log_error(f"Error updating URL status: {str(e)}")
            return False
    
    async def url_exists(self, url: str) -> bool:
        """Check if URL exists in database"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("SELECT COUNT(*) FROM urls WHERE url = ?", (url,))
                count = await cursor.fetchone()
                return count[0] > 0 if count else False
        except Exception as e:
            logger.log_error(f"Error checking URL existence: {str(e)}")
            return False

# Global instance
# Use db/social_media.db if it exists, otherwise fall back to social_media.db
# Try to find the database file relative to the project root
# Try multiple possible locations for the database
_db_path = None
_possible_paths = [
    "db/social_media.db",  # Project root/db/
    Path(__file__).parent.parent / "db" / "social_media.db",  # Absolute path from this file
    "social_media.db",  # Current directory fallback
]

for path in _possible_paths:
    if isinstance(path, Path):
        if path.exists():
            _db_path = str(path)
            break
    elif os.path.exists(path):
        _db_path = path
        break

# If none found, default to social_media.db in current directory
if _db_path is None:
    _db_path = "social_media.db"

new_db_manager = NewDatabaseManager(db_path=_db_path)
