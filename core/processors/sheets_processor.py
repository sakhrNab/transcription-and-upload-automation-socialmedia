#!/usr/bin/env python3
"""
Sheets Processor
Handles Google Sheets updates and tracking
Integrates real logic from social_media_processor.py
"""

import asyncio
import os
import sys
import json
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.processors.base_processor import BaseProcessor
from system.new_database import new_db_manager as db_manager
from system.config import settings
from system.error_recovery import retry_async, RetryConfig, GOOGLE_API_RETRY_CONFIG, CircuitBreaker

# Google Sheets API
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class SheetsProcessor(BaseProcessor):
    """Handles Google Sheets updates and tracking with real functionality"""
    
    def __init__(self):
        super().__init__("SheetsProcessor")
        self.updated_count = 0
        self.failed_count = 0
        
        # Configuration
        self.scopes = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/spreadsheets']
        self.credentials_file = settings.google_credentials_file
        self.token_file = settings.google_token_file
        self.master_sheet_id = settings.master_sheet_id
        self.master_sheet_name = settings.master_sheet_name
        
        # Google Sheets service
        self.service = None
        self.offline_mode = True
        self.local_backup_file = 'master_sheet_backup.json'
        self.local_data = {'rows': {}, 'last_sync': None}
        
        # Circuit breaker for Google Sheets API
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            timeout=30,
            expected_exception=Exception
        )
        
        # Status constants
        self.STATUS_PENDING = 'PENDING'
        self.STATUS_UPLOADED = 'UPLOADED'
        self.STATUS_POSTED = 'POSTED'
        
        # Column definitions for master sheet
        self.SHEET_COLUMNS = [
            'drive_id', 'filename', 'video_name', 'thumbnail_name',
            'file_path_drive', 'upload_time',
            'upload_status_youtube1',
            'upload_status_youtube_aiwaverider1',
            'upload_status_youtube_aiwaverider8',
            'upload_status_youtube1_aiwaverider8_2',
            'upload_status_insta_ai.waverider',
            'upload_status_insta_ai.wave.rider',
            'upload_status_insta_ai.uprise',
            'upload_status_tiktok_ai.wave.rider',
            'upload_status_tiktok_ai.waverider',
            'upload_status_tiktok_aiwaverider9',
            'upload_status_thumbnail',
            'thumbnail_image',
            'transcription_status',
            'transcript'
        ]
    
    async def initialize(self) -> bool:
        """Initialize sheets processor"""
        try:
            self.log_step("Initializing sheets processor")
            
            # Check for required configuration
            if not self.master_sheet_id:
                self.log_error("Master sheet ID not found in configuration")
                return False
            
            # Initialize Google Sheets service
            self.service = await self._get_service()
            if not self.service:
                self.log_error("Failed to initialize Google Sheets service")
                return False
            
            # Ensure sheet exists or create it
            await self._ensure_sheet_exists()
            
            self.offline_mode = False
            self._load_local_backup()
            
            self.initialized = True
            self.status = "ready"
            self.log_step("Sheets processor initialized successfully")
            return True
            
        except Exception as e:
            self.log_error("Failed to initialize sheets processor", e)
            self.offline_mode = True
            self._load_local_backup()
            return True  # Allow offline mode
    
    async def _get_service(self) -> Optional[Any]:
        """Get authenticated Google Sheets service"""
        try:
            creds = None
            if os.path.exists(self.token_file):
                try:
                    creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)
                    self.log_step("Loaded existing credentials from token file")
                except Exception as e:
                    self.log_error(f"Error reading token file: {str(e)}")
                    creds = None
                    
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        with open(self.token_file, 'w') as token:
                            token.write(creds.to_json())
                        self.log_step("Successfully refreshed credentials")
                    except Exception as e:
                        self.log_error(f"Error refreshing credentials: {str(e)}")
                        creds = None
                
                # If we still don't have valid creds, start fresh OAuth flow
                if not creds:
                    try:
                        self.log_step("Starting OAuth flow for new authentication")
                        flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, self.scopes)
                        creds = flow.run_local_server(
                            port=8080,
                            access_type='offline',
                            prompt='consent'
                        )
                        # Save the new credentials
                        with open(self.token_file, 'w') as token:
                            token.write(creds.to_json())
                        self.log_step("New authentication tokens obtained and saved")
                    except Exception as e:
                        self.log_error(f"Error in OAuth flow: {str(e)}")
                        return None
            
            service = build('sheets', 'v4', credentials=creds)
            self.log_step("Google Sheets service initialized successfully")
            
            # Verify sheet access
            try:
                service.spreadsheets().get(spreadsheetId=self.master_sheet_id).execute()
                self.log_step("Successfully verified sheet access")
            except Exception as e:
                self.log_error(f"Sheet access verification failed: {str(e)}")
                return None
                
            return service
            
        except Exception as e:
            self.log_error(f"Failed to initialize Google Sheets service: {str(e)}")
            return None
    
    def _load_local_backup(self):
        """Load local backup data"""
        try:
            if os.path.exists(self.local_backup_file):
                with open(self.local_backup_file, 'r') as f:
                    self.local_data = json.load(f)
            else:
                self.local_data = {'rows': {}, 'last_sync': None}
        except Exception as e:
            self.log_error(f"Error loading local backup: {str(e)}")
            self.local_data = {'rows': {}, 'last_sync': None}
    
    def _save_local_backup(self):
        """Save local backup data"""
        try:
            with open(self.local_backup_file, 'w') as f:
                json.dump(self.local_data, f, indent=2)
            self.log_step("Local backup saved successfully")
        except Exception as e:
            self.log_error(f"Error saving local backup: {str(e)}")
    
    async def process(self, urls: List[str] = None) -> bool:
        """Main processing method - alias for update_master_sheet"""
        return await self.update_master_sheet()
    
    async def update_master_sheet(self) -> bool:
        """Update the master tracking sheet with current data"""
        try:
            self.log_step("Starting master sheet update")
            self.status = "processing"
            
            # Get all videos and thumbnails from database
            videos = await db_manager.get_all_videos()
            thumbnails = await db_manager.get_all_thumbnails()
            
            if not videos:
                self.log_step("No videos found to update in master sheet")
                return True
            
            # Convert to sheet format
            content_list = await self._prepare_sheet_data(videos, thumbnails)
            
            if not content_list:
                self.log_step("No data to update in master sheet")
                return True
            
            # Update the sheet
            success = await self._update_sheet_with_data(content_list)
            
            if success:
                self.updated_count = len(content_list)
                self.status = "completed"
                self.log_step(f"Master sheet updated successfully with {self.updated_count} entries")
                return True
            else:
                self.failed_count = len(content_list)
                self.status = "error"
                self.log_error("Failed to update master sheet")
                return False
            
        except Exception as e:
            self.log_error("Error in update_master_sheet", e)
            self.status = "error"
            return False
    
    async def _prepare_sheet_data(self, videos: List[Dict], thumbnails: List[Dict]) -> List[Dict]:
        """Prepare data for sheet update"""
        try:
            content_list = []
            
            # Process videos
            for video in videos:
                # Find matching thumbnail
                video_filename = video.get('filename', '')
                base_name = os.path.splitext(video_filename)[0]
                matching_thumbnail = None
                
                for thumbnail in thumbnails:
                    if base_name in thumbnail.get('filename', '') or base_name in thumbnail.get('video_filename', ''):
                        matching_thumbnail = thumbnail
                        break
                
                # Prepare content info
                content_info = {
                    'drive_id': video.get('drive_id', ''),
                    'filename': video_filename,
                    'video_name': video.get('smart_name', video_filename),
                    'thumbnail_name': matching_thumbnail.get('filename', '') if matching_thumbnail else '',
                    'file_path_drive': f"https://drive.google.com/file/d/{video.get('drive_id', '')}/view" if video.get('drive_id') else '',
                    'upload_time': video.get('updated_at', ''),
                    'upload_status_youtube1': self.STATUS_PENDING,
                    'upload_status_youtube_aiwaverider1': self.STATUS_PENDING,
                    'upload_status_youtube_aiwaverider8': self.STATUS_PENDING,
                    'upload_status_youtube1_aiwaverider8_2': self.STATUS_PENDING,
                    'upload_status_insta_ai.waverider': self.STATUS_PENDING,
                    'upload_status_insta_ai.wave.rider': self.STATUS_PENDING,
                    'upload_status_insta_ai.uprise': self.STATUS_PENDING,
                    'upload_status_tiktok_ai.wave.rider': self.STATUS_PENDING,
                    'upload_status_tiktok_ai.waverider': self.STATUS_PENDING,
                    'upload_status_tiktok_aiwaverider9': self.STATUS_PENDING,
                    'upload_status_thumbnail': self.STATUS_UPLOADED if matching_thumbnail and matching_thumbnail.get('drive_id') else self.STATUS_PENDING,
                    'thumbnail_image': '',  # Will be populated after image upload
                    'transcription_status': video.get('transcription_status', 'PENDING'),
                    'transcript': video.get('transcription_text', '')
                }
                content_list.append(content_info)
            
            return content_list
            
        except Exception as e:
            self.log_error("Error preparing sheet data", e)
            return []
    
    @retry_async(GOOGLE_API_RETRY_CONFIG)
    async def _update_sheet_with_data(self, content_list: List[Dict]) -> bool:
        """Update the Google Sheet with the prepared data with retry logic and circuit breaker"""
        try:
            # Use circuit breaker to protect against API failures
            return await self.circuit_breaker.call_async(self._perform_sheet_update, content_list)
        except Exception as e:
            self.log_error(f"Error updating sheet with circuit breaker: {str(e)}")
            return False
    
    async def _perform_sheet_update(self, content_list: List[Dict]) -> bool:
        """Perform the actual sheet update operation (called by circuit breaker)"""
        try:
            if not self.service:
                self.log_step("No Google Sheets service available, saving to local backup")
                for content_info in content_list:
                    filename = content_info['filename']
                    self.local_data['rows'][filename] = content_info
                self._save_local_backup()
                return True
            
            # First, cleanup any existing duplicates
            self.log_step("Cleaning up duplicate entries in Google Sheets...")
            await self._cleanup_duplicates()
            
            # Update the sheet with new data
            self.log_step(f"Updating Google Sheet with {len(content_list)} entries")
            
            # Upload thumbnail images and update content_list
            await self._upload_thumbnail_images(content_list)
            
            # Separate existing and new entries
            existing_entries = []
            new_entries = []
            
            for content_info in content_list:
                filename = content_info['filename']
                if filename in self.local_data['rows']:
                    existing_entries.append(content_info)
                else:
                    new_entries.append(content_info)
            
            # Update existing entries individually
            for content_info in existing_entries:
                await self._update_single_entry(content_info)
            
            # Add new entries in batch
            if new_entries:
                await self._add_new_entries(new_entries)
            
            # Save tracking data locally
            await self._save_tracking_data_locally(content_list)
            
            self.log_step("Google Sheet updated successfully")
            return True
            
        except Exception as e:
            self.log_error("Error updating sheet with data", e)
            return False
    
    async def _cleanup_duplicates(self):
        """Remove duplicate entries from the sheet based on filename"""
        try:
            if not self.service:
                self.log_step("Cannot cleanup duplicates - no Google Sheets service")
                return
            
            # Get all data from the sheet
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.master_sheet_id,
                range=f'{self.master_sheet_name}!A1:S1000'
            ).execute()
            
            values = result.get('values', [])
            if len(values) <= 1:  # Only headers or empty
                self.log_step("No data to cleanup")
                return
            
            # Find duplicates by filename (column B)
            seen_filenames = {}
            rows_to_keep = [values[0]]  # Keep header row
            duplicates_found = []
            
            for idx, row in enumerate(values[1:], start=2):
                if row and len(row) > 1:
                    filename = row[1]  # Column B is filename
                    if filename in seen_filenames:
                        duplicates_found.append(idx)
                        self.log_step(f"Found duplicate: {filename} at row {idx}")
                    else:
                        seen_filenames[filename] = idx
                        rows_to_keep.append(row)
            
            if not duplicates_found:
                self.log_step("No duplicates found")
                return
            
            # Clear the sheet and write back only unique rows
            self.service.spreadsheets().values().clear(
                spreadsheetId=self.master_sheet_id,
                range=f'{self.master_sheet_name}!A1:S1000'
            ).execute()
            
            # Write back unique rows
            if rows_to_keep:
                body = {'values': rows_to_keep}
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.master_sheet_id,
                    range=f'{self.master_sheet_name}!A1',
                    valueInputOption='USER_ENTERED',
                    body=body
                ).execute()
                
                self.log_step(f"Cleaned up {len(duplicates_found)} duplicate entries")
                self.log_step(f"Sheet now has {len(rows_to_keep)-1} unique entries")
            
        except Exception as e:
            self.log_error(f"Error cleaning up duplicates: {str(e)}")
    
    async def _update_single_entry(self, content_info: Dict[str, Any]):
        """Update a single entry in the sheet"""
        try:
            filename = content_info['filename']
            
            # Update local backup
            self.local_data['rows'][filename] = content_info
            self._save_local_backup()
            
            if not self.service:
                self.log_step(f"Saved update for {filename} to local backup")
                return
            
            # Find the row number for this filename
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.master_sheet_id,
                range=f'{self.master_sheet_name}!A1:B1000'
            ).execute()
            
            values = result.get('values', [])
            row_number = None
            
            for idx, row in enumerate(values[1:], start=2):
                if row and len(row) > 1 and row[1] == filename:
                    row_number = idx
                    break
            
            if not row_number:
                self.log_step(f"Entry not found for {filename}, adding as new")
                # Add as new entry
                await self._add_new_entries([content_info])
                return
            
            # Prepare row data
            row_data = []
            for col in self.SHEET_COLUMNS:
                value = content_info.get(col, '')
                if col.startswith('upload_status_') and not value:
                    value = self.STATUS_PENDING
                row_data.append(value)
            
            # Update the row
            range_name = f'{self.master_sheet_name}!A{row_number}:T{row_number}'
            self.service.spreadsheets().values().update(
                spreadsheetId=self.master_sheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body={'values': [row_data]}
            ).execute()
            
            self.log_step(f"Updated entry for {filename}")
            
        except Exception as e:
            self.log_error(f"Error updating single entry for {content_info.get('filename', 'unknown')}", e)
    
    async def _add_new_entries(self, new_entries: List[Dict[str, Any]]):
        """Add new entries to the sheet in batch"""
        try:
            if not self.service:
                self.log_step("No Google Sheets service available for adding new entries")
                return
            
            # Prepare batch data
            batch_data = []
            for content_info in new_entries:
                row_data = []
                for col in self.SHEET_COLUMNS:
                    value = content_info.get(col, '')
                    if col.startswith('upload_status_') and not value:
                        value = self.STATUS_PENDING
                    row_data.append(value)
                batch_data.append(row_data)
            
            # Get current sheet size to determine where to append
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.master_sheet_id,
                range=f'{self.master_sheet_name}!A1:A1000'
            ).execute()
            
            values = result.get('values', [])
            start_row = len(values) + 1
            
            # Append new entries
            range_name = f'{self.master_sheet_name}!A{start_row}'
            body = {'values': batch_data}
            self.service.spreadsheets().values().update(
                spreadsheetId=self.master_sheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            self.log_step(f"Added {len(new_entries)} new entries to sheet")
            
        except Exception as e:
            self.log_error(f"Error adding new entries to sheet", e)
    
    async def update_sheets_after_download(self, video_index: int) -> bool:
        """Update sheets after download-only processing"""
        try:
            self.log_step(f"Updating sheets for video {video_index}")
            
            # Get video data from database
            video_data = await db_manager.get_video_transcript_by_index(video_index)
            if not video_data:
                self.log_error(f"Video data not found for index {video_index}")
                return False
            
            # Prepare content info for sheets
            content_info = {
                'filename': video_data.get('filename', ''),
                'title': video_data.get('title', ''),
                'description': video_data.get('description', ''),
                'username': video_data.get('username', ''),
                'platform': video_data.get('platform', ''),
                'duration': video_data.get('duration', 0),
                'view_count': video_data.get('view_count', 0),
                'like_count': video_data.get('like_count', 0),
                'comment_count': video_data.get('comment_count', 0),
                'upload_date': video_data.get('upload_date', ''),
                'video_path': video_data.get('file_path', ''),
                'thumbnail_path': video_data.get('thumbnail_file_path', ''),
                'transcript_path': '',  # Empty for download-only
                'transcript': '',  # Empty for download-only
                'word_count': 0,  # Empty for download-only
                'source_url': video_data.get('webpage_url', ''),
                'status': 'Downloaded',  # Status for download-only
                'processing_time': 0,  # Empty for download-only
                'notes': 'Downloaded only - transcription pending',
                'error_details': ''
            }
            
            # Update the sheet
            await self._update_single_entry(content_info)
            
            self.log_step(f"Successfully updated sheets for video {video_index}")
            self.updated_count += 1
            return True
            
        except Exception as e:
            self.log_error(f"Error updating sheets for video {video_index}", e)
            self.failed_count += 1
            return False
    
    async def _save_tracking_data_locally(self, content_list: List[Dict]) -> None:
        """Save tracking data locally as backup"""
        try:
            # Create directory if it doesn't exist
            local_dir = 'assets/downloads/socialmedia/tracking'
            os.makedirs(local_dir, exist_ok=True)
            
            # Save as JSON
            json_file = os.path.join(local_dir, 'tracking_data.json')
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(content_list, f, indent=2, ensure_ascii=False)
            
            # Save as CSV
            csv_file = os.path.join(local_dir, 'tracking_data.csv')
            if content_list:
                df = pd.DataFrame(content_list)
                df.to_csv(csv_file, index=False, encoding='utf-8')
            
            self.log_step(f"Tracking data saved locally to {local_dir}")
            
        except Exception as e:
            self.log_error("Error saving tracking data locally", e)
    
    async def _upload_thumbnail_images(self, content_list: List[Dict]) -> None:
        """Upload thumbnail images to Google Drive and update content_list with image URLs"""
        try:
            if not self.service:
                self.log_step("No Google Sheets service available, skipping thumbnail image uploads")
                return
            
            # Get Drive service for image uploads
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
            
            drive_service = build('drive', 'v3', credentials=self.service._http.credentials)
            
            # Get existing thumbnail images from Google Drive to avoid duplicates
            existing_images = await self._get_existing_thumbnail_images(drive_service)
            
            for content_info in content_list:
                thumbnail_name = content_info.get('thumbnail_name', '')
                if not thumbnail_name:
                    continue
                
                # Check if thumbnail image already exists in Google Drive
                image_filename = f"thumbnail_{thumbnail_name}"
                if image_filename in existing_images:
                    content_info['thumbnail_image'] = existing_images[image_filename]
                    self.log_step(f"Thumbnail image already exists in Drive for {content_info.get('filename', '')}. Skipping upload.")
                    continue
                
                # Find the thumbnail file locally
                thumbnail_path = await self._find_thumbnail_file(thumbnail_name)
                if not thumbnail_path:
                    self.log_step(f"Thumbnail file not found locally: {thumbnail_name}")
                    continue
                
                # Upload image to Drive
                image_url = await self._upload_thumbnail_to_drive(drive_service, thumbnail_path, thumbnail_name)
                if image_url:
                    content_info['thumbnail_image'] = image_url
                    self.log_step(f"Uploaded thumbnail image for {content_info.get('filename', '')}")
                else:
                    self.log_error(f"Failed to upload thumbnail image for {content_info.get('filename', '')}")
                    
        except Exception as e:
            self.log_error(f"Error uploading thumbnail images: {str(e)}")
    
    async def _find_thumbnail_file(self, thumbnail_name: str) -> Optional[str]:
        """Find thumbnail file in the thumbnails directory"""
        try:
            thumbnails_dir = "assets/downloads/thumbnails"
            for root, dirs, files in os.walk(thumbnails_dir):
                if thumbnail_name in files:
                    return os.path.join(root, thumbnail_name)
            return None
        except Exception as e:
            self.log_error(f"Error finding thumbnail file {thumbnail_name}: {str(e)}")
            return None
    
    async def _upload_thumbnail_to_drive(self, drive_service, thumbnail_path: str, thumbnail_name: str) -> Optional[str]:
        """Upload thumbnail to Google Drive and return the image URL"""
        try:
            # Upload image to Drive first
            file_metadata = {
                'name': f"thumbnail_{thumbnail_name}",
                'parents': ['1iUmCVkX863MqyvJIZ_aWbi9toEI39X8Z']  # Thumbnails folder
            }
            
            media = MediaFileUpload(thumbnail_path, mimetype='image/jpeg')
            file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            image_id = file.get('id')
            if not image_id:
                return None
            
            # Make the image publicly accessible
            try:
                drive_service.permissions().create(
                    fileId=image_id,
                    body={'role': 'reader', 'type': 'anyone'}
                ).execute()
                
                # Return the image URL for use in IMAGE formula
                return f"https://drive.google.com/uc?export=view&id={image_id}"
                
            except Exception as permission_error:
                self.log_error(f"Error setting image permissions: {str(permission_error)}")
                # Fallback to original URL format
                return f"https://drive.google.com/uc?id={image_id}"
                
        except Exception as e:
            self.log_error(f"Error uploading thumbnail to Drive: {str(e)}")
            return None
    
    async def _get_existing_thumbnail_images(self, drive_service) -> Dict[str, str]:
        """Get existing thumbnail images from Google Drive to avoid duplicates"""
        try:
            # Search for files in the thumbnails folder
            results = drive_service.files().list(
                q="'1iUmCVkX863MqyvJIZ_aWbi9toEI39X8Z' in parents and name contains 'thumbnail_'",
                fields="files(id, name, webViewLink)"
            ).execute()
            
            existing_images = {}
            for file_info in results.get('files', []):
                filename = file_info.get('name', '')
                file_id = file_info.get('id', '')
                if filename and file_id:
                    # Create the image URL for use in IMAGE formula
                    image_url = f"https://drive.google.com/uc?export=view&id={file_id}"
                    existing_images[filename] = image_url
            
            self.log_step(f"Found {len(existing_images)} existing thumbnail images in Google Drive")
            return existing_images
            
        except Exception as e:
            self.log_error(f"Error getting existing thumbnail images: {str(e)}")
            return {}
    
    async def _ensure_sheet_exists(self) -> None:
        """Ensure the master sheet exists or create it if it doesn't"""
        try:
            if not self.service:
                self.log_step("No Google Sheets service available, cannot check sheet existence")
                return
            
            # Try to get the existing sheet
            try:
                sheet_info = self.service.spreadsheets().get(spreadsheetId=self.master_sheet_id).execute()
                self.log_step("Found existing master tracking sheet")
                
                # Check if our target sheet exists
                sheet_names = [sheet['properties']['title'] for sheet in sheet_info.get('sheets', [])]
                if self.master_sheet_name not in sheet_names:
                    self.log_step(f"Sheet '{self.master_sheet_name}' not found. Available sheets: {sheet_names}")
                    # Use the first available sheet if our target doesn't exist
                    if sheet_names:
                        self.master_sheet_name = sheet_names[0]
                        self.log_step(f"Using first available sheet: {self.master_sheet_name}")
                
                # Ensure headers exist
                await self._ensure_headers_exist()
                
            except Exception as e:
                if "404" not in str(e):
                    raise
                self.log_step("Sheet with provided ID not found, creating new one...")
                await self._create_new_sheet()
                
        except Exception as e:
            self.log_error(f"Error ensuring sheet exists: {str(e)}")
            raise
    
    async def _create_new_sheet(self) -> None:
        """Create a new master tracking sheet"""
        try:
            # Create new spreadsheet
            spreadsheet = {
                'properties': {
                    'title': 'Video Processing Master Tracking Sheet'
                },
                'sheets': [{
                    'properties': {
                        'title': self.master_sheet_name,
                        'gridProperties': {
                            'frozenRowCount': 1  # Freeze header row
                        }
                    }
                }]
            }
            
            created_sheet = self.service.spreadsheets().create(body=spreadsheet).execute()
            new_sheet_id = created_sheet['spreadsheetId']
            
            # Update the master_sheet_id in settings
            self.master_sheet_id = new_sheet_id
            self.log_step(f"Created new master tracking sheet with ID: {new_sheet_id}")
            
            # Initialize the sheet with headers
            await self._ensure_headers_exist()
            
        except Exception as e:
            self.log_error(f"Error creating new sheet: {str(e)}")
            raise
    
    async def _ensure_headers_exist(self) -> None:
        """Ensure headers exist in the sheet"""
        try:
            if not self.service:
                return
            
            # Check if first row has headers
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.master_sheet_id,
                range=f'{self.master_sheet_name}!A1:T1'
            ).execute()
            
            values = result.get('values', [])
            if not values or len(values[0]) < len(self.SHEET_COLUMNS):
                self.log_step("Adding headers to sheet")
                # Add headers
                header_values = [self.SHEET_COLUMNS]
                body = {'values': header_values}
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.master_sheet_id,
                    range=f'{self.master_sheet_name}!A1',
                    valueInputOption='RAW',
                    body=body
                ).execute()
                
                # Apply formatting to header row
                try:
                    requests = [{
                        'repeatCell': {
                            'range': {
                                'sheetId': 0,
                                'startRowIndex': 0,
                                'endRowIndex': 1,
                                'startColumnIndex': 0,
                                'endColumnIndex': len(self.SHEET_COLUMNS)
                            },
                            'cell': {
                                'userEnteredFormat': {
                                    'backgroundColor': {
                                        'red': 0.8,
                                        'green': 0.8,
                                        'blue': 0.8
                                    },
                                    'textFormat': {
                                        'bold': True
                                    }
                                }
                            },
                            'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                        }
                    }]
                    self.service.spreadsheets().batchUpdate(
                        spreadsheetId=self.master_sheet_id,
                        body={'requests': requests}
                    ).execute()
                    self.log_step("Headers added and formatted successfully")
                except Exception as format_error:
                    self.log_step(f"Header formatting skipped (non-critical): {str(format_error)}")
            else:
                self.log_step("Headers already exist in sheet")
                
        except Exception as e:
            self.log_error(f"Error ensuring headers exist: {str(e)}")
    
    async def sync_transcripts_to_master_sheet(self) -> bool:
        """Sync existing transcripts from transcripts sheet to master sheet"""
        try:
            self.log_step("Starting transcript synchronization to master sheet")
            
            if not self.service:
                self.log_error("Google Sheets service not initialized")
                return False
            
            # Get all videos from database with transcripts
            videos_with_transcripts = await db_manager.get_all_videos_with_transcripts()
            
            if not videos_with_transcripts:
                self.log_step("No videos with transcripts found in database")
                return True
            
            self.log_step(f"Found {len(videos_with_transcripts)} videos with transcripts to sync")
            
            # First, ensure all videos are in the master sheet
            for video in videos_with_transcripts:
                filename = video.get('filename', '')
                transcript = video.get('transcription_text', '')
                
                if not filename or not transcript:
                    continue
                
                # Prepare video data for master sheet
                video_data = {
                    'drive_id': video.get('drive_id', ''),
                    'filename': filename,
                    'video_name': video.get('smart_name', filename),
                    'thumbnail_name': video.get('thumbnail_path', '').split('/')[-1] if video.get('thumbnail_path') else '',
                    'file_path_drive': f"https://drive.google.com/file/d/{video.get('drive_id', '')}/view" if video.get('drive_id') else '',
                    'upload_time': video.get('updated_at', ''),
                    'transcription_status': video.get('transcription_status', 'PENDING'),
                    'transcript': transcript
                }
                
                # Add/update video in master sheet
                await self._update_single_entry(video_data)
                self.log_step(f"Added/updated video {filename} with transcript in master sheet")
            
            self.log_step("Transcript synchronization completed successfully")
            return True
            
        except Exception as e:
            self.log_error(f"Error syncing transcripts to master sheet: {str(e)}")
            return False
    
    async def cleanup(self) -> None:
        """Cleanup sheets processor resources"""
        try:
            self.log_step("Cleaning up sheets processor")
            self.status = "idle"
            self.log_step("Sheets processor cleanup completed")
        except Exception as e:
            self.log_error("Error during cleanup", e)