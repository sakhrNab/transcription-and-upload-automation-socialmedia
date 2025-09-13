#!/usr/bin/env python3
"""
AIWaverider Processor
Handles uploads to AIWaverider Drive
Integrates real logic from social_media_processor.py
"""

import asyncio
import os
import sys
import json
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.processors.base_processor import BaseProcessor
from system.new_database import new_db_manager as db_manager
from system.config import settings
from system.error_recovery import retry_async, RetryConfig, AIWAVERIDER_RETRY_CONFIG, CircuitBreaker

# HTTP requests
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class AIWaveriderProcessor(BaseProcessor):
    """Handles AIWaverider Drive uploads with real functionality"""
    
    def __init__(self):
        super().__init__("AIWaveriderProcessor")
        self.uploaded_count = 0
        self.failed_count = 0
        
        # Configuration
        self.upload_url = settings.aiwaverider_upload_url
        self.token = settings.aiwaverider_token
        self.cache_duration_hours = settings.cache_duration_hours
        
        # Upload paths
        self.video_folder_path = "/videos/instagram/ai.uprise"
        self.thumbnail_folder_path = "/thumbnails/instagram"
        
        # HTTP session for connection pooling
        self._session = None
        
        # Cache directory
        self.cache_dir = "data/cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Circuit breaker for AIWaverider API
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            timeout=60,
            expected_exception=Exception
        )
    
    async def initialize(self) -> bool:
        """Initialize AIWaverider processor"""
        try:
            self.log_step("Initializing AIWaverider processor")
            
            # Check if token is available
            if not self.token:
                self.log_error("AIWaverider token not found in configuration")
                return False
            
            # Initialize HTTP session with connection pooling
            self._session = self._get_http_session()
            
            self.initialized = True
            self.status = "ready"
            self.log_step("AIWaverider processor initialized successfully")
            return True
            
        except Exception as e:
            self.log_error("Failed to initialize AIWaverider processor", e)
            return False
    
    def _get_http_session(self):
        """Get HTTP session with connection pooling and retry strategy"""
        if self._session is None:
            session = requests.Session()
            
            # Configure retry strategy
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
            )
            
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            self._session = session
        
        return self._session
    
    async def process(self, urls: List[str] = None) -> bool:
        """Main processing method - alias for upload_all"""
        return await self.upload_all()
    
    async def upload_all(self) -> bool:
        """Upload all completed videos and thumbnails to AIWaverider Drive"""
        try:
            self.log_step("Starting AIWaverider Drive uploads")
            self.status = "processing"
            
            # Find all .mp4 files in assets/finished_videos and its subfolders
            finished_videos_dir = Path("assets/finished_videos")
            videos = []
            
            if finished_videos_dir.exists():
                for mp4_file in finished_videos_dir.rglob("*.mp4"):
                    file_path = str(mp4_file)
                    filename = mp4_file.name
                    videos.append({
                        'filename': filename,
                        'file_path': file_path,
                        'transcription_status': 'COMPLETED'  # Assume completed since it's in finished_videos
                    })
            
            # Get thumbnails from database
            thumbnails = await db_manager.get_all_thumbnails()
            thumbnails = [t for t in thumbnails if t.get('video_filename')]  # Thumbnails with video association
            
            if not videos and not thumbnails:
                self.log_step("No completed videos or thumbnails found")
                return True
            
            # Get existing files from AIWaverider Drive to avoid duplicates
            existing_videos = await self._get_existing_files(self.video_folder_path)
            existing_thumbnails = await self._get_existing_files(self.thumbnail_folder_path)
            
            self.log_step(f"Found {len(existing_videos)} existing videos and {len(existing_thumbnails)} existing thumbnails on AIWaverider Drive")
            
            # Prepare upload tasks
            upload_tasks = []
            
            # Add video upload tasks
            for video in videos:
                filename = video.get('filename', '')
                file_path = video.get('file_path', '')
                
                # Check if already uploaded to AIWaverider by looking in database
                existing_videos_db = await db_manager.get_all_videos()
                video_data = next((v for v in existing_videos_db if v.get('file_path') == file_path), None)
                
                if (filename not in existing_videos and 
                    file_path and os.path.exists(file_path) and
                    (not video_data or video_data.get('aiwaverider_status') != 'COMPLETED')):
                    upload_tasks.append(('video', file_path, video))
            
            # Add thumbnail upload tasks
            for thumbnail in thumbnails:
                filename = thumbnail.get('filename', '')
                file_path = thumbnail.get('file_path', '')
                
                if filename not in existing_thumbnails and file_path and os.path.exists(file_path):
                    upload_tasks.append(('thumbnail', file_path, thumbnail))
            
            if not upload_tasks:
                self.log_step("No new files to upload to AIWaverider Drive")
                return True
            
            self.log_step(f"Starting parallel upload of {len(upload_tasks)} files...")
            
            # Create semaphore to limit concurrent uploads (max 3 at a time)
            semaphore = asyncio.Semaphore(3)
            
            async def upload_with_semaphore(file_type: str, file_path: str, file_data: Dict):
                async with semaphore:
                    self.log_step(f"Uploading {file_type}: {os.path.basename(file_path)}")
                    if file_type == 'video':
                        return await self._upload_video_to_aiwaverider(file_path)
                    else:
                        return await self._upload_thumbnail_to_aiwaverider(file_path)
            
            # Execute uploads in parallel
            results = await asyncio.gather(
                *[upload_with_semaphore(file_type, file_path, file_data) 
                  for file_type, file_path, file_data in upload_tasks],
                return_exceptions=True
            )
            
            # Process results
            for i, result in enumerate(results):
                file_type, file_path, file_data = upload_tasks[i]
                if isinstance(result, Exception):
                    self.log_error(f"Upload task {i} failed: {str(result)}")
                    self.failed_count += 1
                elif result:
                    self.uploaded_count += 1
                    # Update database status
                    if file_type == 'video':
                        await db_manager.update_video_aiwaverider_status(file_data['id'], 'COMPLETED')
                    else:
                        await db_manager.update_thumbnail_aiwaverider_status(file_data['id'], 'COMPLETED')
                else:
                    self.failed_count += 1
            
            self.status = "completed"
            self.log_step(f"AIWaverider upload completed: {self.uploaded_count} successful, {self.failed_count} failed")
            return self.failed_count == 0
            
        except Exception as e:
            self.log_error("Error in upload_all", e)
            self.status = "error"
            return False
    
    async def _get_existing_files(self, folder_path: str) -> Set[str]:
        """Get list of existing files in AIWaverider Drive folder"""
        try:
            # Check cache first
            cache_file = os.path.join(self.cache_dir, f"cache_{folder_path.replace('/', '_').replace('\\', '_')}.json")
            
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                    cache_age = time.time() - cache_data.get('timestamp', 0)
                    if cache_age < self.cache_duration_hours * 3600:
                        self.log_step(f"Using cached file list for {folder_path} (age: {cache_age/60:.1f} minutes)")
                        return set(cache_data.get('files', []))
            
            # Get fresh data
            files = await self._get_fresh_file_list(folder_path)
            
            # Cache the result
            try:
                with open(cache_file, 'w') as f:
                    json.dump({'files': list(files), 'timestamp': time.time()}, f)
                self.log_step(f"Cached file list for {folder_path}")
            except Exception as e:
                self.log_step(f"Cache write error: {str(e)}")
            
            return files
            
        except Exception as e:
            self.log_error(f"Error getting existing files for {folder_path}: {str(e)}")
            return set()
    
    async def _get_fresh_file_list(self, folder_path: str) -> Set[str]:
        """Get fresh list of files from AIWaverider Drive"""
        try:
            headers = {
                'Authorization': f'Bearer {self.token}'
            }
            
            list_url = self.upload_url.replace('/webhook/files/upload', '/api/files/list')
            params = {
                'folder_path': folder_path
            }
            
            self.log_step(f"Getting fresh file list from AIWaverider Drive for folder: {folder_path}")
            
            response = self._session.get(
                list_url,
                headers=headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                files = data.get('files', [])
                filenames = {file_info.get('name') for file_info in files if file_info.get('name')}
                self.log_step(f"Found {len(filenames)} files in AIWaverider Drive folder: {folder_path}")
                return filenames
            else:
                self.log_error(f"Failed to get file list. Status: {response.status_code}, Response: {response.text}")
                return set()
                
        except Exception as e:
            self.log_error(f"Error getting fresh file list from AIWaverider Drive: {str(e)}")
            return set()
    
    async def _check_file_exists_on_aiwaverider(self, filename: str, folder_path: str) -> bool:
        """Check if file already exists on AIWaverider Drive"""
        try:
            if not self.token:
                self.log_error("AIWaverider token not found")
                return False
            
            # Get existing files for the folder
            existing_files = await self._get_existing_files(folder_path)
            
            # Check if our file exists
            exists = filename in existing_files
            if exists:
                self.log_step(f"File {filename} already exists on AIWaverider Drive")
            else:
                self.log_step(f"File {filename} not found on AIWaverider Drive")
            
            return exists
            
        except Exception as e:
            self.log_error(f"Error checking file existence on AIWaverider Drive: {str(e)}")
            return False
    
    async def _upload_video_to_aiwaverider(self, video_path: str) -> bool:
        """Upload video to AIWaverider Drive with existence checking"""
        filename = os.path.basename(video_path)
        
        # Check if file already exists on AIWaverider Drive
        if await self._check_file_exists_on_aiwaverider(filename, self.video_folder_path):
            self.log_step(f"Video {filename} already exists on AIWaverider Drive. Skipping.")
            return True
        
        return await self._upload_to_aiwaverider_drive_async(video_path, self.video_folder_path, "video")
    
    async def _upload_thumbnail_to_aiwaverider(self, thumbnail_path: str) -> bool:
        """Upload thumbnail to AIWaverider Drive with existence checking"""
        filename = os.path.basename(thumbnail_path)
        
        # Check if file already exists on AIWaverider Drive
        if await self._check_file_exists_on_aiwaverider(filename, self.thumbnail_folder_path):
            self.log_step(f"Thumbnail {filename} already exists on AIWaverider Drive. Skipping.")
            return True
        
        return await self._upload_to_aiwaverider_drive_async(thumbnail_path, self.thumbnail_folder_path, "thumbnail")
    
    @retry_async(AIWAVERIDER_RETRY_CONFIG)
    async def _upload_to_aiwaverider_drive_async(self, file_path: str, folder_path: str, file_type: str) -> bool:
        """Async upload file to AIWaverider Drive with support for chunked uploads, retry logic, and circuit breaker"""
        try:
            # Use circuit breaker to protect against API failures
            return await self.circuit_breaker.call_async(self._perform_upload, file_path, folder_path, file_type)
                
        except Exception as e:
            self.log_error(f"Error uploading {file_type} to AIWaverider Drive: {str(e)}")
            return False
    
    async def _perform_upload(self, file_path: str, folder_path: str, file_type: str) -> bool:
        """Perform the actual upload operation (called by circuit breaker)"""
        try:
            if not self.token:
                self.log_error("AIWaverider token not found")
                return False
                
            if not os.path.exists(file_path):
                self.log_error(f"File not found: {file_path}")
                return False
            
            # Check file size to determine upload method
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            
            self.log_step(f"File size: {file_size_mb:.2f} MB")
            
            if file_size_mb < 10:
                # Use regular upload for files under 10MB
                return await self._upload_small_file_async(file_path, folder_path, file_type)
            else:
                # Use chunked upload for files 10MB and above
                return await self._upload_large_file_chunked_async(file_path, folder_path, file_type)
                
        except Exception as e:
            self.log_error(f"Error in upload operation: {str(e)}")
            raise
    
    async def _upload_small_file_async(self, file_path: str, folder_path: str, file_type: str) -> bool:
        """Async upload small files (< 10MB) using regular upload endpoint"""
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, self._upload_small_file, file_path, folder_path, file_type)
    
    def _upload_small_file(self, file_path: str, folder_path: str, file_type: str) -> bool:
        """Upload small files (< 10MB) using regular upload endpoint"""
        try:
            headers = {
                'Authorization': f'Bearer {self.token}'
            }
            
            with open(file_path, 'rb') as file:
                files = {
                    'file': (os.path.basename(file_path), file, 'application/octet-stream')
                }
                data = {
                    'folder_path': folder_path
                }
                
                self.log_step(f"Uploading small {file_type} to AIWaverider Drive: {os.path.basename(file_path)}")
                self.log_step(f"Folder path: {folder_path}")
                
                response = self._session.post(
                    self.upload_url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=300
                )
                
                if response.status_code == 200:
                    self.log_step(f"Successfully uploaded small {file_type} to AIWaverider Drive: {os.path.basename(file_path)}")
                    return True
                else:
                    self.log_error(f"Failed to upload small {file_type} to AIWaverider Drive. Status: {response.status_code}, Response: {response.text}")
                    return False
                    
        except Exception as e:
            self.log_error(f"Error uploading small {file_type} to AIWaverider Drive: {str(e)}")
            return False
    
    async def _upload_large_file_chunked_async(self, file_path: str, folder_path: str, file_type: str) -> bool:
        """Async upload large files (>= 10MB) using chunked upload endpoint"""
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, self._upload_large_file_chunked, file_path, folder_path, file_type)
    
    def _upload_large_file_chunked(self, file_path: str, folder_path: str, file_type: str) -> bool:
        """Upload large files (>= 10MB) using chunked upload endpoint"""
        try:
            # Generate unique upload ID
            upload_id = str(uuid.uuid4())
            filename = os.path.basename(file_path)
            
            # Calculate chunk size (5MB chunks)
            chunk_size = 5 * 1024 * 1024  # 5MB
            file_size = os.path.getsize(file_path)
            total_chunks = (file_size + chunk_size - 1) // chunk_size  # Ceiling division
            
            self.log_step(f"Starting chunked upload for large {file_type}: {filename}")
            self.log_step(f"File size: {file_size / (1024 * 1024):.2f} MB")
            self.log_step(f"Total chunks: {total_chunks}")
            self.log_step(f"Upload ID: {upload_id}")
            
            # Step 1: Upload file chunks
            if not self._upload_file_chunks(file_path, upload_id, chunk_size, total_chunks):
                self.log_error(f"Failed to upload chunks for {filename}")
                return False
            
            # Step 2: Complete the chunked upload
            if not self._complete_chunked_upload(upload_id, filename, total_chunks, folder_path):
                self.log_error(f"Failed to complete chunked upload for {filename}")
                return False
            
            self.log_step(f"Successfully uploaded large {file_type} using chunked upload: {filename}")
            return True
            
        except Exception as e:
            self.log_error(f"Error uploading large {file_type} to AIWaverider Drive: {str(e)}")
            return False
    
    def _upload_file_chunks(self, file_path: str, upload_id: str, chunk_size: int, total_chunks: int) -> bool:
        """Upload file in chunks to the chunked upload endpoint"""
        try:
            headers = {
                'Authorization': f'Bearer {self.token}'
            }
            
            # Get the chunked upload URL
            chunked_upload_url = self.upload_url.replace('/webhook/files/upload', '/webhook/files/upload-chunk')
            
            with open(file_path, 'rb') as file:
                for chunk_number in range(1, total_chunks + 1):
                    # Read chunk data
                    chunk_data = file.read(chunk_size)
                    if not chunk_data:
                        break
                    
                    self.log_step(f"Uploading chunk {chunk_number}/{total_chunks} for upload_id: {upload_id}")
                    
                    # Prepare chunk upload data
                    files = {
                        'file': (f'chunk_{chunk_number}', chunk_data, 'application/octet-stream')
                    }
                    data = {
                        'upload_id': upload_id,
                        'chunk_number': str(chunk_number),
                        'total_chunks': str(total_chunks)
                    }
                    
                    # Upload chunk
                    response = self._session.post(
                        chunked_upload_url,
                        headers=headers,
                        files=files,
                        data=data,
                        timeout=60
                    )
                    
                    if response.status_code != 200:
                        self.log_error(f"Failed to upload chunk {chunk_number}. Status: {response.status_code}, Response: {response.text}")
                        return False
                    
                    self.log_step(f"Successfully uploaded chunk {chunk_number}/{total_chunks}")
            
            return True
            
        except Exception as e:
            self.log_error(f"Error uploading file chunks: {str(e)}")
            return False
    
    def _complete_chunked_upload(self, upload_id: str, filename: str, total_chunks: int, folder_path: str) -> bool:
        """Complete the chunked upload process"""
        try:
            headers = {
                'Authorization': f'Bearer {self.token}',
                'Content-Type': 'application/json'
            }
            
            # Prepare the complete chunked upload request body
            chunked_upload_data = {
                "upload_id": upload_id,
                "filename": filename,
                "total_chunks": total_chunks,
                "folder_path": folder_path
            }
            
            # Make the chunked upload request
            chunked_upload_url = self.upload_url.replace('/webhook/files/upload', '/webhook/files/complete-chunked-upload')
            
            self.log_step(f"Completing chunked upload for: {filename}")
            self.log_step(f"Request data: {chunked_upload_data}")
            
            response = self._session.post(
                chunked_upload_url,
                headers=headers,
                json=chunked_upload_data,
                timeout=300
            )
            
            if response.status_code == 200:
                self.log_step(f"Successfully completed chunked upload for: {filename}")
                self.log_step(f"Response: {response.text}")
                return True
            else:
                self.log_error(f"Failed to complete chunked upload for {filename}. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            self.log_error(f"Error completing chunked upload: {str(e)}")
            return False
    
    async def cleanup(self) -> None:
        """Cleanup AIWaverider processor resources"""
        try:
            self.log_step("Cleaning up AIWaverider processor")
            if self._session:
                self._session.close()
            self.status = "idle"
            self.log_step("AIWaverider processor cleanup completed")
        except Exception as e:
            self.log_error("Error during cleanup", e)