#!/usr/bin/env python3
"""
Upload Processor
Handles Google Drive uploads for videos and thumbnails
Integrates real logic from upload scripts
"""

import asyncio
import os
import sys
import hashlib
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.processors.base_processor import BaseProcessor
from system.new_database import new_db_manager as db_manager
from system.config import settings

# Google Drive API
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from tqdm import tqdm


class UploadProcessor(BaseProcessor):
    """Handles Google Drive uploads with real functionality"""
    
    def __init__(self):
        super().__init__("UploadProcessor")
        self.uploaded_count = 0
        self.failed_count = 0
        
        # Configuration
        self.video_folder = "assets/finished_videos"
        self.thumbnails_folder = "assets/downloads/thumbnails"
        self.drive_folder = "AIWaverider"
        self.thumbnails_drive_folder_id = "1iUmCVkX863MqyvJIZ_aWbi9toEI39X8Z"
        
        # Google Drive API
        self.scopes = ['https://www.googleapis.com/auth/drive.file']
        self.credentials_file = 'config/credentials.json'
        self.token_file = 'config/token.json'
        
        # Image extensions
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
        
        # Excluded folders
        self.excluded_folders = {
            'temp', '.temp', 'tmp', '.tmp', 
            '.__capcut_export_temp_folder__', 
            '.venv', 'venv',
            '__pycache__',
            'node_modules',
            'downloaded_videos'
        }
        
        # Drive service cache
        self._drive_service = None
        self._drive_folder_id = None
    
    async def initialize(self) -> bool:
        """Initialize upload processor"""
        try:
            self.log_step("Initializing upload processor")
            
            # Ensure required directories exist
            os.makedirs(self.video_folder, exist_ok=True)
            os.makedirs(self.thumbnails_folder, exist_ok=True)
            
            # Initialize Google Drive service
            self._drive_service = self._get_drive_service()
            if not self._drive_service:
                self.log_error("Failed to initialize Google Drive service")
                return False
            
            self.initialized = True
            self.status = "ready"
            self.log_step("Upload processor initialized successfully")
            return True
            
        except Exception as e:
            self.log_error("Failed to initialize upload processor", e)
            return False
    
    # Real Google Drive upload methods
    
    def _get_drive_service(self):
        """Get authenticated Google Drive service"""
        try:
            creds = None
            if os.path.exists(self.token_file):
                creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, self.scopes)
                    creds = flow.run_local_server(port=8080, access_type='offline', prompt='consent')
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
            
            return build('drive', 'v3', credentials=creds)
        except Exception as e:
            self.log_error(f"Failed to get Drive service: {str(e)}")
            return None
    
    def _get_drive_folder_id(self, service, folder_name: str) -> Optional[str]:
        """Get or create Drive folder ID"""
        try:
            # Check if folder exists
            results = service.files().list(
                q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces='drive',
                fields='files(id, name)',
                orderBy='createdTime'
            ).execute()
            
            if results['files']:
                folder_id = results['files'][0]['id']
                self.log_step(f"Using existing folder '{folder_name}' (ID: {folder_id})")
                return folder_id
            
            # Create folder if it doesn't exist
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = service.files().create(body=folder_metadata, fields='id, name').execute()
            folder_id = folder['id']
            self.log_step(f"Created new folder '{folder_name}' (ID: {folder_id})")
            return folder_id
            
        except Exception as e:
            self.log_error(f"Failed to get/create folder '{folder_name}': {str(e)}")
            return None
    
    def _get_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file content"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _get_file_by_name(self, service, filename: str, folder_id: str) -> Optional[Dict]:
        """Find a file by name in a specific folder"""
        try:
            query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
            results = service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, modifiedTime)'
            ).execute()
            
            files = results.get('files', [])
            return files[0] if files else None
        except Exception as e:
            self.log_error(f"Error checking existing file {filename}: {str(e)}")
            return None
    
    async def _check_duplicate_by_name(self, service, filename: str, folder_id: str) -> Optional[Dict[str, Any]]:
        """Check if file with same name already exists in Drive folder"""
        try:
            # Search for files with the same name in the specific folder
            query = f"name='{filename}' and parents in '{folder_id}' and trashed=false"
            results = service.files().list(
                q=query,
                fields="files(id, name, size, modifiedTime, parents)",
                pageSize=10
            ).execute()
            
            files = results.get('files', [])
            if files:
                # Return the first match (most recent if multiple)
                return files[0]
            return None
            
        except Exception as e:
            self.log_error(f"Error checking for duplicate by name: {str(e)}")
            return None
    
    async def _check_duplicate_by_content(self, service, file_hash: str, folder_id: str) -> Optional[Dict[str, Any]]:
        """Check if file with same content hash already exists in Drive folder"""
        try:
            # Search for files with the same content hash (stored in description or custom property)
            query = f"parents in '{folder_id}' and trashed=false"
            results = service.files().list(
                q=query,
                fields="files(id, name, size, modifiedTime, parents, description)",
                pageSize=100
            ).execute()
            
            files = results.get('files', [])
            for file in files:
                # Check if description contains our hash
                description = file.get('description', '')
                if f"hash:{file_hash}" in description:
                    return file
            return None
            
        except Exception as e:
            self.log_error(f"Error checking for duplicate by content: {str(e)}")
            return None
    
    async def _check_database_duplicate(self, filename: str, file_path: str) -> Dict[str, Any]:
        """Check if file already exists in database with upload status"""
        try:
            # Check video_transcripts table
            video_data = await db_manager.get_video_transcript_by_filename(filename)
            if video_data:
                return {
                    'exists': True,
                    'table': 'video_transcripts',
                    'data': video_data,
                    'status': 'Found in video transcripts'
                }
            
            # Check upload_tracking table
            upload_data = await db_manager.get_upload_tracking_by_filename(filename)
            if upload_data:
                return {
                    'exists': True,
                    'table': 'upload_tracking',
                    'data': upload_data,
                    'status': 'Found in upload tracking'
                }
            
            return {
                'exists': False,
                'status': 'No duplicate found in database'
            }
            
        except Exception as e:
            self.log_error(f"Error checking database duplicate: {str(e)}")
            return {
                'exists': False,
                'status': f'Database check failed: {str(e)}'
            }
    
    def _generate_duplicate_filename(self, original_filename: str, counter: int = 1) -> str:
        """Generate a unique filename for duplicate files"""
        name, ext = os.path.splitext(original_filename)
        return f"{name}_duplicate_{counter}{ext}"
    
    async def _upload_video_file(self, service, file_path: str, state: Dict) -> Optional[str]:
        """Upload video file with comprehensive duplicate prevention"""
        try:
            filename = os.path.basename(file_path)
            folder_id = self._get_drive_folder_id(service, self.drive_folder)
            if not folder_id:
                self.log_error(f"No Drive folder ID available for {filename}")
                return None
            
            current_hash = self._get_file_hash(file_path)
            normalized_path = os.path.normpath(file_path)
            
            # Step 1: Check database for existing uploads
            self.log_step(f"Checking database for duplicates: {filename}")
            db_check = await self._check_database_duplicate(filename, file_path)
            if db_check['exists']:
                self.log_step(f"SKIP: {filename} - {db_check['status']}")
                return None
            
            # Step 2: Check Drive for files with same name
            self.log_step(f"Checking Drive for filename duplicates: {filename}")
            name_duplicate = await self._check_duplicate_by_name(service, filename, folder_id)
            if name_duplicate:
                self.log_step(f"SKIP: {filename} - File with same name already exists in Drive (ID: {name_duplicate['id']})")
                return None
            
            # Step 3: Check Drive for files with same content hash
            self.log_step(f"Checking Drive for content duplicates: {filename}")
            content_duplicate = await self._check_duplicate_by_content(service, current_hash, folder_id)
            if content_duplicate:
                self.log_step(f"SKIP: {filename} - File with same content already exists in Drive (ID: {content_duplicate['id']})")
                return None
            
            # Step 4: Check if file already exists in state (recent upload)
            if (normalized_path in state and 
                state[normalized_path].get('file_hash') == current_hash and 
                state[normalized_path].get('upload_status') == 'COMPLETED'):
                self.log_step(f"SKIP: {filename} - Already uploaded in current session")
                return state[normalized_path].get('drive_id')
            
            # Step 5: All checks passed, proceed with upload
            self.log_step(f"UPLOAD: {filename} - No duplicates found, proceeding with upload")
            
            # Upload the file
            file_id = self._upload_new_file(service, file_path, filename, folder_id)
            
            # Only update state and database if upload was successful
            if file_id:
                # Update state
                state[normalized_path] = {
                    'filename': filename,
                    'file_path': normalized_path,
                    'drive_id': file_id,
                    'drive_url': f"https://drive.google.com/file/d/{file_id}/view",
                    'upload_status': 'COMPLETED',
                    'file_hash': current_hash,
                    'last_upload': datetime.now().isoformat()
                }
                
                # Update database
                await db_manager.upsert_video({
                    'filename': filename,
                    'file_path': normalized_path,
                    'drive_id': file_id,
                    'drive_url': f"https://drive.google.com/file/d/{file_id}/view",
                    'upload_status': 'COMPLETED',
                    'file_hash': current_hash,
                    'url': '',
                    'transcription_status': 'PENDING',
                    'transcription_text': '',
                    'smart_name': ''
                })
                
                self.log_step(f"SUCCESS: {filename} uploaded successfully (ID: {file_id})")
                return file_id
            else:
                self.log_error(f"FAILED: {filename} - Upload failed, no file ID returned")
                return None
                
        except Exception as e:
            self.log_error(f"ERROR: {filename} - Upload failed: {str(e)}")
            return None
    
    def _update_existing_file(self, service, file_id: str, file_path: str) -> Optional[str]:
        """Update existing file in Drive"""
        try:
            media = MediaFileUpload(file_path, resumable=True)
            file = service.files().update(
                fileId=file_id,
                media_body=media
            ).execute()
            self.log_step(f"Updated existing file: {file.get('name')}")
            return file.get('id')
        except Exception as e:
            self.log_error(f"Error updating file: {str(e)}")
            return None
    
    def _upload_new_file(self, service, file_path: str, filename: str, folder_id: str) -> Optional[str]:
        """Upload new file to Drive"""
        try:
            # Check if file exists and has content
            if not os.path.exists(file_path):
                self.log_error(f"File does not exist: {file_path}")
                return None
            
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                self.log_error(f"File is empty: {file_path}")
                return None
            
            media = MediaFileUpload(file_path, resumable=True)
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            file_id = file.get('id')
            if not file_id:
                self.log_error(f"No file ID returned from Google Drive for: {filename}")
                return None
                
            self.log_step(f"Uploaded new file: {filename} (ID: {file_id})")
            return file_id
        except Exception as e:
            self.log_error(f"Error uploading new file: {str(e)}")
            return None
    
    async def _upload_thumbnail_file(self, service, file_path: str, state: Dict) -> Optional[str]:
        """Upload thumbnail file with comprehensive duplicate prevention"""
        try:
            filename = os.path.basename(file_path)
            current_hash = self._get_file_hash(file_path)
            normalized_path = os.path.normpath(file_path)
            
            # Step 1: Check database for existing uploads
            self.log_step(f"Checking database for thumbnail duplicates: {filename}")
            db_check = await self._check_database_duplicate(filename, file_path)
            if db_check['exists']:
                self.log_step(f"SKIP: {filename} - {db_check['status']}")
                return None
            
            # Step 2: Check Drive for files with same name
            self.log_step(f"Checking Drive for thumbnail filename duplicates: {filename}")
            name_duplicate = await self._check_duplicate_by_name(service, filename, self.thumbnails_drive_folder_id)
            if name_duplicate:
                self.log_step(f"SKIP: {filename} - Thumbnail with same name already exists in Drive (ID: {name_duplicate['id']})")
                return None
            
            # Step 3: Check Drive for files with same content hash
            self.log_step(f"Checking Drive for thumbnail content duplicates: {filename}")
            content_duplicate = await self._check_duplicate_by_content(service, current_hash, self.thumbnails_drive_folder_id)
            if content_duplicate:
                self.log_step(f"SKIP: {filename} - Thumbnail with same content already exists in Drive (ID: {content_duplicate['id']})")
                return None
            
            # Step 4: Check if file already exists in state (recent upload)
            if (normalized_path in state and 
                state[normalized_path].get('file_hash') == current_hash and 
                state[normalized_path].get('upload_status') == 'COMPLETED'):
                self.log_step(f"SKIP: {filename} - Thumbnail already uploaded in current session")
                return state[normalized_path].get('drive_id')
            
            # Step 5: All checks passed, proceed with upload
            self.log_step(f"UPLOAD: {filename} - No duplicates found, proceeding with thumbnail upload")
            
            # Upload the thumbnail
            media = MediaFileUpload(file_path, resumable=True)
            meta = {'name': filename, 'parents': [self.thumbnails_drive_folder_id]}
            uploaded = service.files().create(body=meta, media_body=media, fields='id, name').execute()
            file_id = uploaded.get('id')
            
            if file_id:
                # Update state
                state[normalized_path] = {
                    'filename': filename,
                    'file_path': normalized_path,
                    'video_filename': '',
                    'drive_id': file_id,
                    'drive_url': f"https://drive.google.com/file/d/{file_id}/view",
                    'upload_status': 'COMPLETED',
                    'file_hash': current_hash,
                    'last_upload': datetime.now().isoformat()
                }
                
                # Update database
                await db_manager.upsert_thumbnail({
                    'filename': filename,
                    'file_path': normalized_path,
                    'video_filename': '',
                    'drive_id': file_id,
                    'drive_url': f"https://drive.google.com/file/d/{file_id}/view",
                    'upload_status': 'COMPLETED',
                    'file_hash': current_hash
                })
                
                self.log_step(f"SUCCESS: {filename} thumbnail uploaded successfully (ID: {file_id})")
                return file_id
            else:
                self.log_error(f"FAILED: {filename} - Thumbnail upload failed, no file ID returned")
                return None
            
        except Exception as e:
            self.log_error(f"ERROR: {filename} - Thumbnail upload failed: {str(e)}")
            return None
    
    def _find_mp4_files(self, folder: str) -> List[str]:
        """Find all MP4 files in folder and subfolders"""
        mp4_files = []
        for root, dirs, files in os.walk(folder):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if not any(excluded in d.lower() for excluded in self.excluded_folders)]
            for file in files:
                if file.lower().endswith('.mp4'):
                    mp4_files.append(os.path.join(root, file))
        return mp4_files
    
    def _find_image_files(self, folder: str) -> List[str]:
        """Find all image files in folder"""
        files = []
        if not os.path.exists(folder):
            return files
        for root, dirs, filenames in os.walk(folder):
            for name in filenames:
                ext = os.path.splitext(name)[1].lower()
                if ext in self.image_extensions:
                    files.append(os.path.join(root, name))
        return files
    
    async def process_transcripts(self) -> bool:
        """Process transcript file uploads to Google Drive"""
        try:
            self.log_step("Starting transcript upload processing")
            
            # Find transcript files
            transcript_files = self._find_transcript_files()
            if not transcript_files:
                self.log_step("No transcript files found to upload")
                return True
            
            service = self._get_drive_service()
            if not service:
                return False
            
            folder_id = self._get_drive_folder_id(service, "Transcripts")
            if not folder_id:
                return False
            
            successful_uploads = 0
            failed_uploads = 0
            
            for file_path in transcript_files:
                try:
                    filename = os.path.basename(file_path)
                    
                    # Check if file already exists
                    existing_file = self._get_file_by_name(service, filename, folder_id)
                    if existing_file:
                        self.log_step(f"Transcript {filename} already exists in Drive. Skipping.")
                        successful_uploads += 1
                        continue
                    
                    # Upload new transcript file
                    file_id = self._upload_new_file(service, file_path, filename, folder_id)
                    if file_id:
                        self.log_step(f"Successfully uploaded transcript: {filename}")
                        successful_uploads += 1
                    else:
                        self.log_error(f"Failed to upload transcript: {filename}")
                        failed_uploads += 1
                        
                except Exception as e:
                    self.log_error(f"Error uploading transcript {file_path}: {str(e)}")
                    failed_uploads += 1
            
            self.log_step(f"Transcript upload completed: {successful_uploads} successful, {failed_uploads} failed")
            return failed_uploads == 0
            
        except Exception as e:
            self.log_error(f"Error in transcript processing: {str(e)}")
            return False
    
    async def process_tracking_data(self) -> bool:
        """Process tracking data file uploads to Google Drive"""
        try:
            self.log_step("Starting tracking data upload processing")
            
            # Find tracking data files
            tracking_files = self._find_tracking_files()
            if not tracking_files:
                self.log_step("No tracking data files found to upload")
                return True
            
            service = self._get_drive_service()
            if not service:
                return False
            
            folder_id = self._get_drive_folder_id(service, "Tracking Data")
            if not folder_id:
                return False
            
            successful_uploads = 0
            failed_uploads = 0
            
            for file_path in tracking_files:
                try:
                    filename = os.path.basename(file_path)
                    
                    # Check if file already exists
                    existing_file = self._get_file_by_name(service, filename, folder_id)
                    if existing_file:
                        self.log_step(f"Tracking data {filename} already exists in Drive. Skipping.")
                        successful_uploads += 1
                        continue
                    
                    # Upload new tracking data file
                    file_id = self._upload_new_file(service, file_path, filename, folder_id)
                    if file_id:
                        self.log_step(f"Successfully uploaded tracking data: {filename}")
                        successful_uploads += 1
                    else:
                        self.log_error(f"Failed to upload tracking data: {filename}")
                        failed_uploads += 1
                        
                except Exception as e:
                    self.log_error(f"Error uploading tracking data {file_path}: {str(e)}")
                    failed_uploads += 1
            
            self.log_step(f"Tracking data upload completed: {successful_uploads} successful, {failed_uploads} failed")
            return failed_uploads == 0
            
        except Exception as e:
            self.log_error(f"Error in tracking data processing: {str(e)}")
            return False
    
    def _find_transcript_files(self) -> List[str]:
        """Find all transcript files to upload"""
        files = []
        for root, dirs, filenames in os.walk(self.transcripts_dir):
            # Skip excluded folders
            dirs[:] = [d for d in dirs if d not in self.excluded_folders]
            
            for name in filenames:
                if name.endswith('.txt') and 'transcript' in name.lower():
                    files.append(os.path.join(root, name))
        return files
    
    def _find_tracking_files(self) -> List[str]:
        """Find all tracking data files to upload"""
        files = []
        tracking_dirs = [
            'assets/downloads/socialmedia/tracking',
            'data/tracking',
            'tracking_data'
        ]
        
        for tracking_dir in tracking_dirs:
            if os.path.exists(tracking_dir):
                for root, dirs, filenames in os.walk(tracking_dir):
                    for name in filenames:
                        if name.endswith(('.json', '.csv')) and 'tracking' in name.lower():
                            files.append(os.path.join(root, name))
        return files
    
    async def process(self, urls: List[str] = None) -> bool:
        """Main processing method"""
        # Process videos, thumbnails, transcripts, and tracking data
        video_success = await self.process_videos()
        thumbnail_success = await self.process_thumbnails()
        transcript_success = await self.process_transcripts()
        tracking_success = await self.process_tracking_data()
        return video_success and thumbnail_success and transcript_success and tracking_success
    
    async def process_videos(self) -> bool:
        """Process video uploads to Google Drive"""
        try:
            self.log_step("Starting video upload processing")
            self.status = "processing"
            
            # Load state from database
            state = await self._load_video_state()
            
            # Find all .mp4 files in assets/finished_videos and its subfolders
            files_to_upload = []
            finished_videos_dir = Path(self.video_folder)
            
            if not finished_videos_dir.exists():
                self.log_step(f"Finished videos directory {self.video_folder} does not exist")
                return True
            
            # Recursively find all .mp4 files
            for mp4_file in finished_videos_dir.rglob("*.mp4"):
                file_path = str(mp4_file)
                filename = mp4_file.name
                
                # Check if already uploaded by looking for this specific file path in database
                existing_videos = await db_manager.get_all_videos()
                video_data = next((v for v in existing_videos if v.get('file_path') == file_path), None)
                
                if video_data and (video_data.get('upload_status') == 'COMPLETED' and video_data.get('drive_id')):
                    self.log_step(f"Video {filename} already uploaded to Google Drive. Skipping.")
                    continue
                
                files_to_upload.append((file_path, {'filename': filename, 'file_path': file_path}))
            
            if not files_to_upload:
                self.log_step("No new videos to upload")
                return True
            
            self.log_step(f"Found {len(files_to_upload)} new videos to upload")
            
            # Upload each file
            for file_path, video_data in files_to_upload:
                try:
                    file_id = await self._upload_video_file(self._drive_service, file_path, state)
                    if file_id:
                        # Update database with upload status
                        await db_manager.update_video_status(video_data['id'], 'COMPLETED', file_id)
                        self.uploaded_count += 1
                    else:
                        self.failed_count += 1
                except Exception as e:
                    self.log_error(f"Error uploading video {file_path}", e)
                    self.failed_count += 1
            
            # Save state to database
            await self._save_video_state(state)
            
            self.status = "completed"
            self.log_step(f"Video upload completed: {self.uploaded_count} successful, {self.failed_count} failed")
            return self.failed_count == 0
            
        except Exception as e:
            self.log_error("Error in process_videos", e)
            self.status = "error"
            return False
    
    async def process_thumbnails(self) -> bool:
        """Process thumbnail uploads to Google Drive"""
        try:
            self.log_step("Starting thumbnail upload processing")
            self.status = "processing"
            
            # Load state from database
            state = await self._load_thumbnail_state()
            
            # Find image files to upload
            all_files = self._find_image_files(self.thumbnails_folder)
            
            # Filter out already uploaded files
            files_to_upload = []
            for file_path in all_files:
                normalized_path = os.path.normpath(file_path)
                if normalized_path in state:
                    thumbnail_data = state[normalized_path]
                    if (thumbnail_data.get('upload_status') == 'COMPLETED' and 
                        thumbnail_data.get('drive_id')):
                        self.log_step(f"Thumbnail {os.path.basename(file_path)} already uploaded. Skipping.")
                        continue
                files_to_upload.append(file_path)
            
            if not files_to_upload:
                self.log_step("No new thumbnails to upload")
                return True
            
            self.log_step(f"Found {len(files_to_upload)} new thumbnails to upload")
            
            # Upload each file
            for file_path in files_to_upload:
                try:
                    file_id = await self._upload_thumbnail_file(self._drive_service, file_path, state)
                    if file_id:
                        self.uploaded_count += 1
                    else:
                        self.failed_count += 1
                except Exception as e:
                    self.log_error(f"Error uploading thumbnail {file_path}", e)
                    self.failed_count += 1
            
            # Save state to database
            await self._save_thumbnail_state(state)
            
            self.status = "completed"
            self.log_step(f"Thumbnail upload completed: {self.uploaded_count} successful, {self.failed_count} failed")
            return self.failed_count == 0
            
        except Exception as e:
            self.log_error("Error in process_thumbnails", e)
            self.status = "error"
            return False
    
    # State management methods
    async def _load_video_state(self) -> Dict[str, Dict]:
        """Load video state from database"""
        try:
            videos = await db_manager.get_all_videos()
            state = {}
            for video in videos:
                file_path = video.get('file_path', '')
                if file_path:
                    normalized_path = os.path.normpath(file_path)
                    state[normalized_path] = {
                        'filename': video.get('filename', ''),
                        'file_path': normalized_path,
                        'drive_id': video.get('drive_id', ''),
                        'drive_url': video.get('drive_url', ''),
                        'upload_status': video.get('upload_status', 'PENDING'),
                        'file_hash': video.get('file_hash', ''),
                        'last_modified': video.get('updated_at', '')
                    }
            return state
        except Exception as e:
            self.log_error(f"Error loading video state: {str(e)}")
            return {}
    
    async def _save_video_state(self, state: Dict[str, Dict]):
        """Save video state to database"""
        try:
            for file_path, video_data in state.items():
                await db_manager.upsert_video({
                    'filename': video_data.get('filename', ''),
                    'file_path': file_path,
                    'drive_id': video_data.get('drive_id', ''),
                    'drive_url': video_data.get('drive_url', ''),
                    'upload_status': video_data.get('upload_status', 'PENDING'),
                    'file_hash': video_data.get('file_hash', ''),
                    'url': video_data.get('url', ''),
                    'transcription_status': video_data.get('transcription_status', 'PENDING'),
                    'transcription_text': video_data.get('transcription_text', ''),
                    'smart_name': video_data.get('smart_name', '')
                })
            self.log_step(f"Video state saved to database: {len(state)} files tracked")
        except Exception as e:
            self.log_error(f"Error saving video state: {str(e)}")
    
    async def _load_thumbnail_state(self) -> Dict[str, Dict]:
        """Load thumbnail state from database"""
        try:
            thumbnails = await db_manager.get_all_thumbnails()
            state = {}
            for thumbnail in thumbnails:
                file_path = thumbnail.get('file_path', '')
                if file_path:
                    normalized_path = os.path.normpath(file_path)
                    state[normalized_path] = {
                        'filename': thumbnail.get('filename', ''),
                        'file_path': normalized_path,
                        'video_filename': thumbnail.get('video_filename', ''),
                        'drive_id': thumbnail.get('drive_id', ''),
                        'drive_url': thumbnail.get('drive_url', ''),
                        'upload_status': thumbnail.get('upload_status', 'PENDING'),
                        'file_hash': thumbnail.get('file_hash', ''),
                        'last_modified': thumbnail.get('updated_at', '')
                    }
            return state
        except Exception as e:
            self.log_error(f"Error loading thumbnail state: {str(e)}")
            return {}
    
    async def _save_thumbnail_state(self, state: Dict[str, Dict]):
        """Save thumbnail state to database"""
        try:
            for file_path, thumbnail_data in state.items():
                await db_manager.upsert_thumbnail({
                    'filename': thumbnail_data.get('filename', ''),
                    'file_path': file_path,
                    'video_filename': thumbnail_data.get('video_filename', ''),
                    'drive_id': thumbnail_data.get('drive_id', ''),
                    'drive_url': thumbnail_data.get('drive_url', ''),
                    'upload_status': thumbnail_data.get('upload_status', 'PENDING'),
                    'file_hash': thumbnail_data.get('file_hash', '')
                })
            self.log_step(f"Thumbnail state saved to database: {len(state)} files tracked")
        except Exception as e:
            self.log_error(f"Error saving thumbnail state: {str(e)}")
    
    async def cleanup(self) -> None:
        """Cleanup upload processor resources"""
        try:
            self.log_step("Cleaning up upload processor")
            self.status = "idle"
            self.log_step("Upload processor cleanup completed")
        except Exception as e:
            self.log_error("Error during cleanup", e)
