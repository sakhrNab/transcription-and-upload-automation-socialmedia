#!/usr/bin/env python3
"""
Transcripts Sheets Processor
Handles Google Sheets updates for video transcripts with comprehensive data
Follows the same pattern as socialmedia_tracker sheet
"""

import asyncio
import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.processors.base_processor import BaseProcessor
from system.database import DatabaseManager
from system.config import settings
from system.error_recovery import retry_async, RetryConfig, GOOGLE_API_RETRY_CONFIG, CircuitBreaker

# Google Sheets API
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

class TranscriptsSheetsProcessor(BaseProcessor):
    """Handles Google Sheets updates for video transcripts with comprehensive data"""
    
    def __init__(self):
        super().__init__("TranscriptsSheetsProcessor")
        self.updated_count = 0
        self.failed_count = 0
        
        # Configuration
        self.scopes = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/spreadsheets']
        self.credentials_file = settings.google_credentials_file
        self.token_file = settings.google_token_file
        self.transcripts_sheet_id = settings.transcripts_sheet_id
        self.transcripts_sheet_name = settings.transcripts_sheet_name
        
        # Google Sheets service
        self.service = None
        self.offline_mode = True
        self.local_backup_file = 'transcripts_sheet_backup.json'
        self.local_data = {'rows': {}, 'last_sync': None}
        
        # Database manager
        self.db_manager = DatabaseManager()
        
        # Circuit breaker for Google Sheets API
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            timeout=30,
            expected_exception=Exception
        )
        
        # Column definitions for transcripts sheet (same as Excel)
        self.SHEET_COLUMNS = [
            # Basic Info
            "Index", "Generated Name", "Original Title", "Description", "Date Processed",
            
            # Creator Info  
            "Username", "Uploader ID", "Channel ID", "Channel URL",
            
            # Video Details
            "Video ID", "Platform", "Duration (seconds)", "Resolution", "FPS", "Format",
            
            # Engagement Metrics
            "View Count", "Like Count", "Comment Count", "Upload Date",
            
            # File Information
            "Video File Size (MB)", "Video Path", "Thumbnail Path", "Transcript Path", "Audio Path",
            
            # Content
            "Transcript", "Transcript Word Count",
            
            # Processing Info
            "Source URL", "Status", "Processing Time (seconds)", "Notes", "Error Details"
        ]
    
    async def initialize(self) -> bool:
        """Initialize transcripts sheets processor"""
        try:
            self.log_step("Initializing transcripts sheets processor")
            
            # Initialize Google Sheets service
            self.service = await self._get_service()
            if not self.service:
                self.log_error("Failed to initialize Google Sheets service")
                return False
            
            # Ensure sheet exists
            await self._ensure_sheet_exists()
            
            self.log_step("Transcripts sheets processor initialized successfully")
            return True
            
        except Exception as e:
            self.log_error("Error initializing transcripts sheets processor", e)
            return False
    
    async def process(self, urls: List[str] = None) -> bool:
        """Main processing method - update transcripts sheet"""
        return await self.update_transcripts_sheet()
    
    async def update_transcripts_sheet(self) -> bool:
        """Update the transcripts sheet with video data"""
        try:
            self.log_step("Starting transcripts sheet update")
            self.status = "processing"
            
            # Ensure service is initialized
            if not self.service:
                self.service = await self._get_service()
                if not self.service:
                    self.log_error("Failed to initialize Google Sheets service")
                    return False
            
            # Ensure sheet exists and ID is set
            if not self.transcripts_sheet_id:
                await self._ensure_sheet_exists()
            
            # Initialize database manager if needed
            if not hasattr(self.db_manager, '_initialized') or not self.db_manager._initialized:
                await self.db_manager.initialize()
            
            # Get all videos and thumbnails from database
            videos = await self.db_manager.get_all_videos()
            thumbnails = await self.db_manager.get_all_thumbnails()
            
            if not videos:
                self.log_step("No videos found to update in transcripts sheet")
                return True
            
            # Prepare transcript data
            transcript_data = await self._prepare_transcript_data(videos, thumbnails)
            
            # Save local backup first
            await self._save_local_backup(transcript_data)
            
            # Update the sheet
            success = await self._update_sheet_with_data(transcript_data)
            
            if success:
                self.updated_count = len(transcript_data)
                self.status = "completed"
                self.log_step(f"Transcripts sheet updated successfully with {self.updated_count} entries")
                return True
            else:
                self.failed_count = 1
                self.status = "error"
                self.log_error("Failed to update transcripts sheet")
                return False
                
        except Exception as e:
            self.log_error("Error updating transcripts sheet", e)
            self.status = "error"
            return False
    
    async def _save_local_backup(self, transcript_data: List[List[str]]) -> None:
        """Save transcript data locally as CSV and JSON (offline mode)"""
        try:
            import os
            import json
            import pandas as pd
            
            # Create local directory following the same pattern as tracking_data
            local_dir = os.path.join("assets", "downloads", "socialmedia", "transcripts")
            os.makedirs(local_dir, exist_ok=True)
            
            # Convert to list of dictionaries for JSON
            if transcript_data:
                # Create headers from SHEET_COLUMNS
                headers = self.SHEET_COLUMNS
                
                # Convert to list of dictionaries
                data_dicts = []
                for row in transcript_data:
                    if len(row) == len(headers):
                        data_dicts.append(dict(zip(headers, row)))
                
                # Save as JSON
                json_file = os.path.join(local_dir, 'video_transcripts.json')
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(data_dicts, f, indent=2, ensure_ascii=False)
                
                # Save as CSV
                csv_file = os.path.join(local_dir, 'video_transcripts.csv')
                df = pd.DataFrame(data_dicts)
                df.to_csv(csv_file, index=False, encoding='utf-8')
                
                self.log_step(f"Transcript data saved locally to {local_dir}")
            
        except Exception as e:
            self.log_error("Error saving local backup", e)
    
    async def _prepare_transcript_data(self, videos: List[Dict], thumbnails: List[Dict]) -> List[Dict]:
        """Prepare transcript data for sheet update"""
        try:
            self.log_step(f"Preparing transcript data for {len(videos)} videos")
            
            # Create thumbnail lookup
            thumbnail_lookup = {}
            for thumb in thumbnails:
                video_filename = thumb.get('video_filename', '')
                if video_filename:
                    thumbnail_lookup[video_filename] = thumb
            
            transcript_data = []
            
            for i, video in enumerate(videos, 1):
                # Get corresponding thumbnail
                video_filename = video.get('filename', '')
                thumbnail = thumbnail_lookup.get(video_filename, {})
                
                # Calculate file sizes
                video_size_mb = 0
                if video.get('file_path') and os.path.exists(video['file_path']):
                    video_size_mb = os.path.getsize(video['file_path']) / (1024 * 1024)
                
                # Calculate transcript word count
                transcript_text = video.get('transcription_text', '')
                word_count = len(transcript_text.split()) if transcript_text else 0
                
                # Format resolution
                width = video.get('width', 0)
                height = video.get('height', 0)
                resolution = f"{width}x{height}" if width and height else "Unknown"
                
                # Prepare row data
                row_data = {
                    'Index': i,
                    'Generated Name': video.get('smart_name', ''),
                    'Original Title': video.get('title', ''),
                    'Description': video.get('description', ''),
                    'Date Processed': video.get('created_at', ''),
                    'Username': video.get('username', ''),
                    'Uploader ID': video.get('uploader_id', ''),
                    'Channel ID': video.get('channel_id', ''),
                    'Channel URL': video.get('channel_url', ''),
                    'Video ID': video.get('video_id', ''),
                    'Platform': video.get('platform', ''),
                    'Duration (seconds)': video.get('duration', 0),
                    'Resolution': resolution,
                    'FPS': video.get('fps', 0),
                    'Format': video.get('format_id', ''),
                    'View Count': video.get('view_count', 0),
                    'Like Count': video.get('like_count', 0),
                    'Comment Count': video.get('comment_count', 0),
                    'Upload Date': video.get('upload_date', ''),
                    'Video File Size (MB)': round(video_size_mb, 2),
                    'Video Path': video.get('file_path', ''),
                    'Thumbnail Path': thumbnail.get('file_path', ''),
                    'Transcript Path': f"assets/downloads/transcripts/{video.get('video_id', '')}_transcript.txt",
                    'Audio Path': f"assets/downloads/audio/{os.path.splitext(video_filename)[0]}.wav",
                    'Transcript': transcript_text,
                    'Transcript Word Count': word_count,
                    'Source URL': video.get('url', ''),
                    'Status': video.get('transcription_status', 'PENDING'),
                    'Processing Time (seconds)': 0,  # Could be calculated if needed
                    'Notes': '',
                    'Error Details': ''
                }
                
                transcript_data.append(row_data)
            
            self.log_step(f"Prepared {len(transcript_data)} transcript entries")
            return transcript_data
            
        except Exception as e:
            self.log_error("Error preparing transcript data", e)
            return []
    
    async def _update_sheet_with_data(self, transcript_data: List[Dict]) -> bool:
        """Update the sheet with transcript data using the same pattern as socialmedia_tracker"""
        try:
            if not self.service:
                self.log_error("Google Sheets service not initialized")
                return False
            
            # Get existing data from sheet
            existing_data = await self._get_existing_sheet_data()
            
            # Prepare new entries (avoid duplicates based on Video ID or filename)
            new_entries = []
            existing_video_ids = {row.get('Video ID', '') for row in existing_data}
            existing_filenames = {row.get('Video Path', '').split('/')[-1] for row in existing_data if row.get('Video Path')}
            
            for entry in transcript_data:
                video_id = entry.get('Video ID', '')
                filename = entry.get('Video Path', '').split('/')[-1] if entry.get('Video Path') else ''
                
                # Check if this entry already exists (by video ID or filename)
                if (video_id and video_id not in existing_video_ids) or (filename and filename not in existing_filenames):
                    new_entries.append(entry)
            
            if not new_entries:
                self.log_step("No new transcript entries to add")
                return True
            
            # Add new entries to sheet
            await self._add_new_entries(new_entries)
            
            # Save local backup
            await self._save_local_backup(transcript_data)
            
            self.log_step(f"Successfully updated transcripts sheet with {len(new_entries)} new entries")
            return True
            
        except Exception as e:
            self.log_error("Error updating sheet with transcript data", e)
            return False
    
    async def _get_existing_sheet_data(self) -> List[Dict]:
        """Get existing data from the transcripts sheet"""
        try:
            if not self.transcripts_sheet_id:
                return []
            
            # Get all data from the sheet
            range_name = f"{self.transcripts_sheet_name}!A:AE"  # All columns (31 columns)
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.transcripts_sheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            if len(values) <= 1:  # Only headers or empty
                return []
            
            # Convert to list of dictionaries
            headers = values[0]
            existing_data = []
            
            for row in values[1:]:  # Skip header row
                row_dict = {}
                for i, value in enumerate(row):
                    if i < len(headers):
                        row_dict[headers[i]] = value
                existing_data.append(row_dict)
            
            return existing_data
            
        except Exception as e:
            self.log_error("Error getting existing sheet data", e)
            return []
    
    async def _add_new_entries(self, new_entries: List[Dict]) -> None:
        """Add new entries to the transcripts sheet"""
        try:
            if not new_entries:
                return
            
            
            # Convert entries to rows
            rows = []
            for entry in new_entries:
                row = []
                for column in self.SHEET_COLUMNS:
                    value = entry.get(column, '')
                    # Convert to string and handle special characters
                    if isinstance(value, (int, float)):
                        row.append(str(value))
                    else:
                        row.append(str(value) if value else '')
                rows.append(row)
            
            # Append to sheet
            range_name = f"{self.transcripts_sheet_name}!A:AE"
            body = {'values': rows}
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.transcripts_sheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            self.log_step(f"Added {len(new_entries)} new entries to transcripts sheet")
            
        except Exception as e:
            self.log_error("Error adding new entries to sheet", e)
            raise
    
    async def _ensure_sheet_exists(self) -> None:
        """Ensure the transcripts sheet exists, create if necessary"""
        try:
            if self.transcripts_sheet_id:
                # Check if sheet exists and is accessible
                try:
                    sheet_info = self.service.spreadsheets().get(spreadsheetId=self.transcripts_sheet_id).execute()
                    self.log_step(f"Using existing transcripts sheet: {self.transcripts_sheet_id}")
                    self.log_step(f"Sheet title: {sheet_info.get('properties', {}).get('title', 'Unknown')}")
                    await self._ensure_headers_exist()
                    return
                except Exception as e:
                    self.log_step(f"Existing transcripts sheet not accessible: {str(e)}")
                    self.log_step("Will create new sheet")
                    # Reset sheet ID so we create a new one
                    self.transcripts_sheet_id = ""
            
            # Create new sheet only if we don't have a valid one
            if not self.transcripts_sheet_id:
                await self._create_new_sheet()
            
        except Exception as e:
            self.log_error(f"Error ensuring sheet exists: {str(e)}")
            raise
    
    async def _create_new_sheet(self) -> None:
        """Create a new transcripts sheet"""
        try:
            # Create new spreadsheet
            spreadsheet = {
                'properties': {
                    'title': 'Video Transcripts - Comprehensive Data'
                },
                'sheets': [{
                    'properties': {
                        'title': self.transcripts_sheet_name,
                        'gridProperties': {
                            'frozenRowCount': 1  # Freeze header row
                        }
                    }
                }]
            }
            
            created_sheet = self.service.spreadsheets().create(body=spreadsheet).execute()
            new_sheet_id = created_sheet['spreadsheetId']
            
            # Update the transcripts_sheet_id
            self.transcripts_sheet_id = new_sheet_id
            self.log_step(f"Created new transcripts sheet with ID: {new_sheet_id}")
            
            # Initialize the sheet with headers
            await self._ensure_headers_exist()
            
            # Update settings (this would need to be persisted)
            settings.transcripts_sheet_id = new_sheet_id
            
            # Also update the instance variable to ensure it's available
            self.transcripts_sheet_id = new_sheet_id
            
        except Exception as e:
            self.log_error(f"Error creating new sheet: {str(e)}")
            raise
    
    async def _ensure_headers_exist(self) -> None:
        """Ensure headers exist in the transcripts sheet"""
        try:
            if not self.transcripts_sheet_id:
                return
            
            # Check if headers exist
            range_name = f"{self.transcripts_sheet_name}!A1:AE1"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.transcripts_sheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            
            if not values or not values[0]:
                # Add headers
                headers_range = f"{self.transcripts_sheet_name}!A1:AE1"
                headers_body = {'values': [self.SHEET_COLUMNS]}
                
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.transcripts_sheet_id,
                    range=headers_range,
                    valueInputOption='RAW',
                    body=headers_body
                ).execute()
                
                self.log_step("Added headers to transcripts sheet")
            
        except Exception as e:
            self.log_error(f"Error ensuring headers exist: {str(e)}")
            raise
    
    async def _save_local_backup(self, data: List[Dict]) -> None:
        """Save local backup of transcript data"""
        try:
            backup_data = {
                'rows': {str(i): row for i, row in enumerate(data)},
                'last_sync': datetime.now().isoformat(),
                'sheet_id': self.transcripts_sheet_id
            }
            
            with open(self.local_backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            self.log_error("Error saving local backup", e)
    
    async def _get_service(self):
        """Get Google Sheets service with authentication"""
        try:
            creds = None
            
            # Load existing token
            if os.path.exists(self.token_file):
                creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)
            
            # If no valid credentials, get new ones
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not os.path.exists(self.credentials_file):
                        self.log_error(f"Credentials file not found: {self.credentials_file}")
                        return None
                    
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, self.scopes)
                    creds = flow.run_local_server(port=0)
                
                # Save credentials for next run
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
            
            # Build service
            service = build('sheets', 'v4', credentials=creds)
            self.offline_mode = False
            return service
            
        except Exception as e:
            self.log_error(f"Error getting Google Sheets service: {str(e)}")
            return None
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        try:
            self.log_step("Cleaning up transcripts sheets processor")
            # No specific cleanup needed for this processor
        except Exception as e:
            self.log_error("Error during cleanup", e)
