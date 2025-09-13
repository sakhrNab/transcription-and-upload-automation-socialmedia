#!/usr/bin/env python3
"""
Social Media Content Processor and Tracker
Orchestrates the entire workflow:
1. Downloads videos and generates thumbnails
2. Uploads content to Google Drive
3. Maintains master tracking sheet
4. Tracks upload status across platforms
"""

import os
import sys
import json
import time
import re
import asyncio
import subprocess
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from system.processor_logger import processor_logger as logger
from dotenv import load_dotenv

# Import new systems
from system.config import settings
from system.database import db_manager
from system.error_recovery import retry_async, RetryConfig, GOOGLE_API_RETRY_CONFIG, AIWAVERIDER_RETRY_CONFIG
from system.health_metrics import metrics_collector, ProcessingMetrics
from system.queue_processor import queue_processor, TaskType
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Load environment variables
load_dotenv()

# Configuration - now using centralized config
SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/spreadsheets']
CREDENTIALS_FILE = os.path.abspath(settings.google_credentials_file)
TOKEN_FILE = os.path.abspath(settings.google_token_file)
MASTER_SHEET_ID = settings.master_sheet_id
MASTER_SHEET_NAME = settings.master_sheet_name

# AIWaverider Drive Configuration
AIWAVERIDER_UPLOAD_URL = settings.aiwaverider_upload_url
AIWAVERIDER_TOKEN = settings.aiwaverider_token
CACHE_DURATION_HOURS = settings.cache_duration_hours

# Global session for connection pooling
_http_session = None

def get_http_session():
    """Get or create HTTP session with connection pooling and retry strategy"""
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        _http_session.mount("http://", adapter)
        _http_session.mount("https://", adapter)
    return _http_session

# Status Constants
STATUS_PENDING = 'PENDING'
STATUS_UPLOADED = 'UPLOADED'
STATUS_POSTED = 'POSTED'

# Column definitions for master sheet
SHEET_COLUMNS = [
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
    'transcription_status'
]

async def load_transcription_state_from_db() -> Dict[str, Any]:
    """Load transcription state from database"""
    try:
        videos = await db_manager.get_all_videos()
        transcription_state = {}
        for video in videos:
            video_id = video.get('video_id', '')
            if video_id:
                transcription_state[video_id] = {
                    'status': 'completed' if video.get('transcription_status') == 'COMPLETED' else 'pending',
                    'url': video.get('url', ''),
                    'timestamp': video.get('updated_at', ''),
                    'transcript': video.get('transcription_text', ''),
                    'smart_name': video.get('smart_name', '')
                }
        return transcription_state
    except Exception as e:
        logger.log_error(f"Error loading transcription state from database: {str(e)}")
        return {}

async def save_transcription_state_to_db(video_id: str, status: str, url: str, transcript: str = '', smart_name: str = ''):
    """Save transcription state to database"""
    try:
        await db_manager.upsert_video({
            'filename': f"{video_id}.mp4",
            'file_path': '',
            'url': url,
            'drive_id': '',
            'drive_url': '',
            'upload_status': 'PENDING',
            'transcription_status': 'COMPLETED' if status == 'completed' else 'PENDING',
            'transcription_text': transcript,
            'smart_name': smart_name,
            'file_hash': ''
        })
    except Exception as e:
        logger.log_error(f"Error saving transcription state to database: {str(e)}")

def extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from YouTube URL"""
    try:
        patterns = [
            r'(?:youtube\.com\/(?:[^\/\n\r]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    except Exception as e:
        logger.log_error(f"Error extracting video ID: {str(e)}")
        return None

class MasterSheetManager:
    def __init__(self):
        """Initialize the MasterSheetManager"""
        global MASTER_SHEET_ID  # Declare at start of method
        
        try:
            logger.log_step("Initializing MasterSheetManager")
            self.local_backup_file = 'master_sheet_backup.json'
            self.offline_updates = []
            self.service = None
            self.offline_mode = True
            
            # First get the service
            self.service = self._get_service()
            self.offline_mode = False
            
            # Then try to get or create the sheet
            sheet_id = self._get_or_create_sheet()
            
            # If we created a new sheet, update our global ID
            if sheet_id and sheet_id != MASTER_SHEET_ID:
                MASTER_SHEET_ID = sheet_id
                
            self._load_local_backup()
            
        except Exception as e:
            logger.log_error(f"Failed to initialize MasterSheetManager: {str(e)}", 
                           error_type="InitializationError")
            logger.log_step("Running in offline mode - changes will be saved locally")
            self.service = None
            self.offline_mode = True
            self._load_local_backup()
    
    def _get_or_create_sheet(self):
        """Get existing sheet or create a new one if it doesn't exist"""
        global MASTER_SHEET_NAME
        try:
            # Try to get the existing sheet if we have an ID
            if MASTER_SHEET_ID:
                try:
                    sheet_info = self.service.spreadsheets().get(spreadsheetId=MASTER_SHEET_ID).execute()
                    logger.log_step("Found existing master tracking sheet")
                    
                    # Log available sheet names for debugging
                    sheet_names = [sheet['properties']['title'] for sheet in sheet_info.get('sheets', [])]
                    logger.log_step(f"Available sheet names: {sheet_names}")
                    
                    # Check if our target sheet exists
                    if MASTER_SHEET_NAME not in sheet_names:
                        logger.log_step(f"Sheet '{MASTER_SHEET_NAME}' not found. Available sheets: {sheet_names}")
                        # Use the first available sheet if our target doesn't exist
                        if sheet_names:
                            MASTER_SHEET_NAME = sheet_names[0]
                            logger.log_step(f"Using first available sheet: {MASTER_SHEET_NAME}")
                    
                    # Check if headers exist and add them if missing
                    self._ensure_headers_exist()
                    
                    return MASTER_SHEET_ID
                except Exception as e:
                    if "404" not in str(e):
                        raise
                    logger.log_step("Sheet with provided ID not found, creating new one...")
            else:
                logger.log_step("No sheet ID configured, creating new one...")
            
            # Create new spreadsheet
            spreadsheet = {
                'properties': {
                    'title': 'Video Processing Master Tracking Sheet'
                },
                'sheets': [{
                    'properties': {
                        'title': 'socialmedia_tracker',
                        'gridProperties': {
                            'frozenRowCount': 1  # Freeze header row
                        }
                    }
                }]
            }
            
            created_sheet = self.service.spreadsheets().create(body=spreadsheet).execute()
            new_sheet_id = created_sheet['spreadsheetId']
            
            # Update the MASTER_SHEET_ID in .env
            self._update_env_sheet_id(new_sheet_id)
            
            # Initialize the sheet with headers
            values = [SHEET_COLUMNS]  # Use our existing column definitions
            body = {'values': values}
            self.service.spreadsheets().values().update(
                spreadsheetId=new_sheet_id,
                range='socialmedia_tracker!A1',
                valueInputOption='RAW',
                body=body
            ).execute()
            
            # Apply formatting to header row
            requests = [{
                'repeatCell': {
                    'range': {
                        'sheetId': 0,
                        'startRowIndex': 0,
                        'endRowIndex': 1
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
                spreadsheetId=new_sheet_id,
                body={'requests': requests}
            ).execute()
            
            logger.log_step(f"Created new master tracking sheet with ID: {new_sheet_id}")
            return new_sheet_id
            
        except Exception as e:
            logger.log_error(f"Failed to get/create sheet: {str(e)}")
            raise
    
    def _update_env_sheet_id(self, new_sheet_id):
        """Update the MASTER_SHEET_ID in .env file"""
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                lines = f.readlines()
            
            updated = False
            for i, line in enumerate(lines):
                if line.startswith('MASTER_SHEET_ID='):
                    lines[i] = f'MASTER_SHEET_ID={new_sheet_id}\n'
                    updated = True
                    break
            
            if not updated:
                lines.append(f'MASTER_SHEET_ID={new_sheet_id}\n')
            
            with open(env_path, 'w') as f:
                f.writelines(lines)
            
            global MASTER_SHEET_ID
            MASTER_SHEET_ID = new_sheet_id
            logger.log_step("Updated MASTER_SHEET_ID in .env file")
        
    def _get_service(self) -> Any:
        """Get authenticated Google Sheets service with error handling"""
        try:
            creds = None
            if os.path.exists(TOKEN_FILE):
                try:
                    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
                    logger.log_step("Loaded existing credentials from token file")
                except Exception as e:
                    logger.log_error(f"Error reading token file: {str(e)}", 
                                   error_type="TokenError")
                    creds = None  # Reset creds if there's an error reading the file
                    
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        with open(TOKEN_FILE, 'w') as token:
                            token.write(creds.to_json())
                        logger.log_step("Successfully refreshed credentials")
                    except Exception as e:
                        logger.log_error(f"Error refreshing credentials: {str(e)}", 
                                       error_type="AuthError")
                        creds = None  # Reset creds if refresh fails
                
                # If we still don't have valid creds, start fresh OAuth flow
                if not creds:
                    try:
                        logger.log_step("Starting OAuth flow for new authentication")
                        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                        creds = flow.run_local_server(
                            port=8080,
                            access_type='offline',
                            prompt='consent'  # Only show consent screen when needed
                        )
                        # Save the new credentials
                        with open(TOKEN_FILE, 'w') as token:
                            token.write(creds.to_json())
                        logger.log_step("New authentication tokens obtained and saved")
                    except Exception as e:
                        logger.log_error(f"Error in OAuth flow: {str(e)}", 
                                       error_type="OAuthError")
                        raise
            
            service = build('sheets', 'v4', credentials=creds)
            logger.log_step("Google Sheets service initialized successfully")
            
            # Only verify sheet access if we have a sheet ID
            if MASTER_SHEET_ID:
                try:
                    # Try a simple API call to verify credentials
                    service.spreadsheets().get(spreadsheetId=MASTER_SHEET_ID).execute()
                    logger.log_step("Successfully verified sheet access")
                except Exception as e:
                    logger.log_error(f"Sheet access verification failed: {str(e)}")
                    # Don't delete token file here - let the calling code handle it
                    raise
                
            return service
            
        except Exception as e:
            logger.log_error(f"Failed to initialize Google Sheets service: {str(e)}", 
                           error_type="ServiceError")
            raise
    

    
    def _ensure_headers_exist(self):
        """Ensure headers exist in the sheet"""
        try:
            # Check if first row has headers
            result = self.service.spreadsheets().values().get(
                spreadsheetId=MASTER_SHEET_ID,
                range=f'{MASTER_SHEET_NAME}!A1:S1'
            ).execute()
            
            values = result.get('values', [])
            if not values or len(values[0]) < len(SHEET_COLUMNS):
                logger.log_step("Adding headers to existing sheet")
                # Add headers
                header_values = [SHEET_COLUMNS]
                body = {'values': header_values}
                self.service.spreadsheets().values().update(
                    spreadsheetId=MASTER_SHEET_ID,
                    range=f'{MASTER_SHEET_NAME}!A1',
                    valueInputOption='RAW',
                    body=body
                ).execute()
                
                # Apply formatting to header row
                requests = [{
                    'repeatCell': {
                        'range': {
                            'sheetId': 0,
                            'startRowIndex': 0,
                            'endRowIndex': 1
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
                    spreadsheetId=MASTER_SHEET_ID,
                    body={'requests': requests}
                ).execute()
                logger.log_step("Headers added and formatted successfully")
            else:
                logger.log_step("Headers already exist in sheet")
        except Exception as e:
            logger.log_error(f"Error ensuring headers exist: {str(e)}")
    
    def _load_local_backup(self):
        """Load local backup data"""
        try:
            if os.path.exists(self.local_backup_file):
                with open(self.local_backup_file, 'r') as f:
                    self.local_data = json.load(f)
            else:
                self.local_data = {'rows': {}, 'last_sync': None}
        except Exception as e:
            logger.log_error(f"Error loading local backup: {str(e)}")
            self.local_data = {'rows': {}, 'last_sync': None}
            
    def _save_local_backup(self):
        """Save local backup data"""
        try:
            with open(self.local_backup_file, 'w') as f:
                json.dump(self.local_data, f, indent=2)
            logger.log_step("Local backup saved successfully")
        except Exception as e:
            logger.log_error(f"Error saving local backup: {str(e)}")
    
    def cleanup_duplicates(self):
        """Remove duplicate entries from the sheet based on filename"""
        try:
            if not self.service:
                logger.log_step("Cannot cleanup duplicates - no Google Sheets service")
                return
            
            # Get all data from the sheet
            result = self.service.spreadsheets().values().get(
                spreadsheetId=MASTER_SHEET_ID,
                range=f'{MASTER_SHEET_NAME}!A1:S1000'
            ).execute()
            
            values = result.get('values', [])
            if len(values) <= 1:  # Only headers or empty
                logger.log_step("No data to cleanup")
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
                        logger.log_step(f"Found duplicate: {filename} at row {idx}")
                    else:
                        seen_filenames[filename] = idx
                        rows_to_keep.append(row)
            
            if not duplicates_found:
                logger.log_step("No duplicates found")
                return
            
            # Clear the sheet and write back only unique rows
            # First, clear all data
            self.service.spreadsheets().values().clear(
                spreadsheetId=MASTER_SHEET_ID,
                range=f'{MASTER_SHEET_NAME}!A1:S1000'
            ).execute()
            
            # Write back unique rows
            if rows_to_keep:
                body = {'values': rows_to_keep}
                self.service.spreadsheets().values().update(
                    spreadsheetId=MASTER_SHEET_ID,
                    range=f'{MASTER_SHEET_NAME}!A1',
                    valueInputOption='USER_ENTERED',
                    body=body
                ).execute()
                
                logger.log_step(f"Cleaned up {len(duplicates_found)} duplicate entries")
                logger.log_step(f"Sheet now has {len(rows_to_keep)-1} unique entries")
            
        except Exception as e:
            logger.log_error(f"Error cleaning up duplicates: {str(e)}")

    def _upload_thumbnail_image(self, content_info: Dict[str, Any], row_number: int):
        """Upload thumbnail image to Google Sheets using Drive API"""
        try:
            thumbnail_name = content_info.get('thumbnail_name', '')
            if not thumbnail_name:
                return
                
            # Find the thumbnail file locally
            thumbnail_path = None
            for root, dirs, files in os.walk('assets/downloads/thumbnails'):
                if thumbnail_name in files:
                    thumbnail_path = os.path.join(root, thumbnail_name)
                    break
            
            if not thumbnail_path or not os.path.exists(thumbnail_path):
                logger.log_step(f"Thumbnail file not found locally: {thumbnail_name}")
                return
            
            # Get the Drive service for image upload
            from googleapiclient.discovery import build
            drive_service = build('drive', 'v3', credentials=self.service._http.credentials)
            
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
            image_url = f"https://drive.google.com/uc?id={image_id}"
            
            # Find the thumbnail_image column index
            thumbnail_col_index = SHEET_COLUMNS.index('thumbnail_image')
            
            # Make the image publicly accessible first
            try:
                # Update file permissions to make it publicly viewable
                drive_service.permissions().create(
                    fileId=image_id,
                    body={'role': 'reader', 'type': 'anyone'}
                ).execute()
                
                # Use a more reliable image URL format
                image_url = f"https://drive.google.com/uc?export=view&id={image_id}"
                
                # Try different IMAGE formula formats for better compatibility
                image_formula = f'=IMAGE("{image_url}", 1)'  # Add mode parameter for better compatibility
                
                # Update the cell with the IMAGE formula
                range_name = f'{MASTER_SHEET_NAME}!{chr(65 + thumbnail_col_index)}{row_number}'
                self.service.spreadsheets().values().update(
                    spreadsheetId=MASTER_SHEET_ID,
                    range=range_name,
                    valueInputOption='USER_ENTERED',
                    body={'values': [[image_formula]]}
                ).execute()
                
                logger.log_step(f"Uploaded thumbnail image for {content_info.get('filename', '')} with formula: {image_formula}")
                
            except Exception as permission_error:
                logger.log_error(f"Error setting image permissions: {str(permission_error)}")
                
                # Fallback to original URL format
                image_formula = f'=IMAGE("{image_url}", 1)'
                
                # Update the cell with the IMAGE formula
                range_name = f'{MASTER_SHEET_NAME}!{chr(65 + thumbnail_col_index)}{row_number}'
                self.service.spreadsheets().values().update(
                    spreadsheetId=MASTER_SHEET_ID,
                    range=range_name,
                    valueInputOption='USER_ENTERED',
                    body={'values': [[image_formula]]}
                ).execute()
                
                logger.log_step(f"Uploaded thumbnail image for {content_info.get('filename', '')} with formula: {image_formula}")
            
        except Exception as e:
            logger.log_error(f"Error uploading thumbnail image: {str(e)}")

    def update_content_status(self, content_info: Dict[str, Any]):
        """Update or append content information to the master sheet"""
        try:
            # Always update local backup first
            filename = content_info['filename']
            self.local_data['rows'][filename] = content_info
            self._save_local_backup()
            
            if not self.service:
                logger.log_step(f"Saved update for {filename} to local backup")
                self.offline_updates.append(content_info)
                return
                
            # Try to update online sheet
            try:
                # First, check if entry exists
                result = self.service.spreadsheets().values().get(
                    spreadsheetId=MASTER_SHEET_ID,
                    range=f'{MASTER_SHEET_NAME}!A1:B1000'
                ).execute()
                
                values = result.get('values', [])
                if not values:
                    row_number = 2  # First data row
                else:
                    # Look for matching filename
                    found = False
                    for idx, row in enumerate(values[1:], start=2):
                        if row and row[1] == filename:
                            row_number = idx
                            found = True
                            break
                    if not found:
                        row_number = len(values) + 1
                
                # Prepare row data
                row_data = []
                for col in SHEET_COLUMNS:
                    value = content_info.get(col, '')
                    if col.startswith('upload_status_') and not value:
                        value = STATUS_PENDING
                    row_data.append(value)
                
                # Update the row
                range_name = f'{MASTER_SHEET_NAME}!A{row_number}:S{row_number}'
                self.service.spreadsheets().values().update(
                    spreadsheetId=MASTER_SHEET_ID,
                    range=range_name,
                    valueInputOption='USER_ENTERED',
                    body={'values': [row_data]}
                ).execute()
                
                # Handle thumbnail image upload if available
                if content_info.get('thumbnail_image') and content_info.get('thumbnail_name'):
                    self._upload_thumbnail_image(content_info, row_number)
                
                logger.log_step(f"Updated sheet row {row_number} for {filename}")
                
            except Exception as e:
                logger.log_error(f"Error updating online sheet: {str(e)}")
                # Even if online update fails, we already have local backup
                
        except Exception as e:
            logger.log_error(f"Error in update_content_status: {str(e)}")
            raise

    def batch_update_content_status(self, content_list: List[Dict[str, Any]]):
        """Batch update multiple content entries to the master sheet using values API"""
        try:
            if not content_list:
                return
                
            # Always update local backup first
            for content_info in content_list:
                filename = content_info['filename']
                self.local_data['rows'][filename] = content_info
            
            self._save_local_backup()
            
            if not self.service:
                logger.log_step(f"Saved {len(content_list)} updates to local backup")
                self.offline_updates.extend(content_list)
                return
                
            # Try to update online sheet using values API (more reliable than batch update)
            try:
                # First, check existing entries
                result = self.service.spreadsheets().values().get(
                    spreadsheetId=MASTER_SHEET_ID,
                    range=f'{MASTER_SHEET_NAME}!A1:B1000'
                ).execute()
                
                values = result.get('values', [])
                existing_filenames = {}
                if values:
                    for idx, row in enumerate(values[1:], start=2):
                        if row and len(row) > 1:
                            existing_filenames[row[1]] = idx
                
                # Separate existing and new entries
                updates_to_make = []
                new_entries = []
                
                for content_info in content_list:
                    filename = content_info['filename']
                    
                    # Prepare row data
                    row_data = []
                    for col in SHEET_COLUMNS:
                        value = content_info.get(col, '')
                        if col.startswith('upload_status_') and not value:
                            value = STATUS_PENDING
                        row_data.append(value)
                    
                    if filename in existing_filenames:
                        # Update existing row
                        row_number = existing_filenames[filename]
                        updates_to_make.append((row_number, row_data, filename))
                    else:
                        # New entry
                        new_entries.append(row_data)
                
                # Update existing entries individually
                for row_number, row_data, filename in updates_to_make:
                    range_name = f'{MASTER_SHEET_NAME}!A{row_number}:S{row_number}'
                    self.service.spreadsheets().values().update(
                        spreadsheetId=MASTER_SHEET_ID,
                        range=range_name,
                        valueInputOption='USER_ENTERED',
                        body={'values': [row_data]}
                    ).execute()
                    logger.log_step(f"Updated existing row {row_number} for {filename}")
                
                # Add new entries in batch
                if new_entries:
                    next_row = len(values) + 1 if values else 2
                    end_row = next_row + len(new_entries) - 1
                    range_name = f'{MASTER_SHEET_NAME}!A{next_row}:S{end_row}'
                    
                    body = {'values': new_entries}
                    self.service.spreadsheets().values().update(
                        spreadsheetId=MASTER_SHEET_ID,
                        range=range_name,
                        valueInputOption='USER_ENTERED',
                        body=body
                    ).execute()
                    logger.log_step(f"Added {len(new_entries)} new entries to Google Sheets")
                
                total_updates = len(updates_to_make) + len(new_entries)
                logger.log_step(f"Processed {total_updates} total entries: {len(updates_to_make)} updates, {len(new_entries)} new")
                
            except Exception as e:
                logger.log_error(f"Error batch updating online sheet: {str(e)}")
                # Fallback to individual updates
                logger.log_step("Falling back to individual updates...")
                for content_info in content_list:
                    try:
                        self.update_content_status(content_info)
                    except Exception as individual_error:
                        logger.log_error(f"Error updating individual entry {content_info.get('filename', 'unknown')}: {str(individual_error)}")
                
        except Exception as e:
            logger.log_error(f"Error in batch_update_content_status: {str(e)}")
            raise

async def run_full_rounded(urls_file: str):
    """Run the full-rounded script and wait for completion"""
    try:
        logger.log_step("Starting full-rounded processing")
        
        # Load transcription state from database
        transcription_state = await load_transcription_state_from_db()
        
        # Read URLs and filter already transcribed ones
        with open(urls_file, 'r', encoding='utf-8') as f:
            original_urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        # Filter out already transcribed URLs
        new_urls = []
        for url in original_urls:
            video_id = extract_video_id(url)
            if video_id and transcription_state.get(video_id, {}).get('status') != 'completed':
                new_urls.append(url)
        
        if not new_urls:
            logger.log_step("No new URLs to process - all have been transcribed")
            return True
            
        # Write new URLs to temporary file
        temp_urls_file = 'temp_urls.txt'
        with open(temp_urls_file, 'w', encoding='utf-8') as f:
            for url in new_urls:
                f.write(f"{url}\n")
        
        # Set environment variables for proper encoding
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            'core/full-rounded-url-download-transcription.py',
            '--urls-file', temp_urls_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            try:
                logger.logger.info(line.decode('utf-8').strip())
            except UnicodeDecodeError:
                logger.logger.info(line.decode('cp1252', errors='ignore').strip())
        
        # Get any remaining output
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            if stderr:
                try:
                    error_msg = stderr.decode('utf-8')
                except UnicodeDecodeError:
                    error_msg = stderr.decode('cp1252', errors='ignore')
                logger.log_error(f"Error in full-rounded: {error_msg}")
            return False
            
        # Update transcription state for successful transcriptions in database
        for url in new_urls:
            video_id = extract_video_id(url)
            if video_id:
                await save_transcription_state_to_db(video_id, 'completed', url)
        
        # Clean up temporary file
        try:
            os.remove(temp_urls_file)
        except Exception as e:
            logger.log_error(f"Error removing temporary URL file: {str(e)}")
            
        logger.log_step("Full-rounded processing complete")
        return True
        
    except Exception as e:
        logger.log_error(f"Error running full-rounded: {str(e)}")
        return False
    finally:
        # Always try to clean up temp file
        try:
            if os.path.exists('temp_urls.txt'):
                os.remove('temp_urls.txt')
        except Exception:
            pass

async def run_uploaders():
    """Run video and thumbnail uploaders sequentially with timeouts"""
    try:
        logger.log_step("Starting uploaders")
        
        # Run video uploader first with a timeout
        logger.log_step("Starting video upload")
        video_uploader = await asyncio.create_subprocess_exec(
            sys.executable,
            'scripts/upload-new-video-to-google.py',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                "PYTHONUNBUFFERED": "1", 
                "FOLDER_TO_WATCH": "assets/finished_videos",
                **os.environ
            }  # Enable unbuffered output and set correct path
        )
        
        # Process video uploader output with timeout
        try:
            # Use asyncio.wait_for for Python 3.9 compatibility
            async def process_video_output():
                while True:
                    line = await video_uploader.stdout.readline()
                    if not line:
                        break
                    try:
                        output = line.decode('utf-8').strip()
                        if output:
                            logger.log_step(f"Video Upload: {output}")
                    except UnicodeDecodeError:
                        output = line.decode('cp1252', errors='ignore').strip()
                        if output:
                            logger.log_step(f"Video Upload: {output}")
                            
                # Get final status
                stdout, stderr = await video_uploader.communicate()
                return stdout, stderr
            
            stdout, stderr = await asyncio.wait_for(process_video_output(), timeout=30)
                
        except asyncio.TimeoutError:
            logger.log_step("Video upload check completed (timed out)")
            video_uploader.terminate()  # Gracefully terminate the process
            await video_uploader.wait()  # Wait for process to actually terminate
        except Exception as e:
            logger.log_error(f"Error during video upload: {str(e)}")
            return False
            
        logger.log_step("Video upload completed")
            
        # Then run thumbnail uploader
        logger.log_step("Starting thumbnail upload")
        thumbnail_uploader = await asyncio.create_subprocess_exec(
            sys.executable,
            'scripts/upload-thumbnails-to-google.py',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                "PYTHONUNBUFFERED": "1", 
                "THUMBNAILS_DIR": "assets/downloads/thumbnails",
                **os.environ
            }  # Enable unbuffered output and set correct path
        )
        
        # Process thumbnail uploader output with timeout
        try:
            # Use asyncio.wait_for for Python 3.9 compatibility
            async def process_thumbnail_output():
                while True:
                    line = await thumbnail_uploader.stdout.readline()
                    if not line:
                        break
                    try:
                        output = line.decode('utf-8').strip()
                        if output:
                            logger.log_step(f"Thumbnail Upload: {output}")
                    except UnicodeDecodeError:
                        output = line.decode('cp1252', errors='ignore').strip()
                        if output:
                            logger.log_step(f"Thumbnail Upload: {output}")
                            
                # Get final status
                stdout, stderr = await thumbnail_uploader.communicate()
                return stdout, stderr
            
            stdout, stderr = await asyncio.wait_for(process_thumbnail_output(), timeout=30)
                
        except asyncio.TimeoutError:
            logger.log_step("Thumbnail upload check completed (timed out)")
            thumbnail_uploader.terminate()  # Gracefully terminate the process
            await thumbnail_uploader.wait()  # Wait for process to actually terminate
        except Exception as e:
            logger.log_error(f"Error during thumbnail upload: {str(e)}")
            return False
            
        logger.log_step("Thumbnail upload completed")
        
        logger.log_step("All uploads completed successfully")
        return True
        
    except Exception as e:
        logger.log_error(f"Error running uploaders: {str(e)}")
        return False
    except asyncio.CancelledError:
        logger.log_error("Upload process was cancelled")
        return False

def save_tracking_data_locally(tracking_data: list, local_dir: str = 'assets/downloads/socialmedia/tracking'):
    """Save tracking data locally as JSON and CSV"""
    try:
        # Create directory if it doesn't exist
        os.makedirs(local_dir, exist_ok=True)
        
        # Save as JSON
        json_file = os.path.join(local_dir, 'tracking_data.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(tracking_data, f, indent=2, ensure_ascii=False)
        
        # Save as CSV
        csv_file = os.path.join(local_dir, 'tracking_data.csv')
        if tracking_data:
            import pandas as pd
            df = pd.DataFrame(tracking_data)
            df.to_csv(csv_file, index=False, encoding='utf-8')
        
        logger.log_step(f"Tracking data saved locally to {local_dir}")
        
    except Exception as e:
        logger.log_error(f"Error saving tracking data locally: {str(e)}")

async def update_master_sheet_from_database():
    """Update master sheet using database data instead of JSON files"""
    try:
        # Get all videos and thumbnails from database
        videos = await db_manager.get_all_videos()
        thumbnails = await db_manager.get_all_thumbnails()
        
        # Convert to the format expected by the sheet manager
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
            
            # Prepare content info with proper sheet columns
            content_info = {
                'drive_id': video.get('drive_id', ''),
                'filename': video_filename,
                'video_name': video.get('smart_name', video_filename),
                'thumbnail_name': matching_thumbnail.get('filename', '') if matching_thumbnail else '',
                'file_path_drive': f"https://drive.google.com/file/d/{video.get('drive_id', '')}/view" if video.get('drive_id') else '',
                'upload_time': video.get('updated_at', ''),
                'upload_status_youtube1': STATUS_PENDING,
                'upload_status_youtube_aiwaverider1': STATUS_PENDING,
                'upload_status_youtube_aiwaverider8': STATUS_PENDING,
                'upload_status_youtube1_aiwaverider8_2': STATUS_PENDING,
                'upload_status_insta_ai.waverider': STATUS_PENDING,
                'upload_status_insta_ai.wave.rider': STATUS_PENDING,
                'upload_status_insta_ai.uprise': STATUS_PENDING,
                'upload_status_tiktok_ai.wave.rider': STATUS_PENDING,
                'upload_status_tiktok_ai.waverider': STATUS_PENDING,
                'upload_status_tiktok_aiwaverider9': STATUS_PENDING,
                'upload_status_thumbnail': STATUS_UPLOADED if matching_thumbnail and matching_thumbnail.get('drive_id') else STATUS_PENDING,
                'thumbnail_image': f"https://drive.google.com/uc?id={matching_thumbnail['drive_id']}" if matching_thumbnail and matching_thumbnail.get('drive_id') else '',
                'transcription_status': video.get('transcription_status', 'PENDING')
            }
            content_list.append(content_info)
        
        # Update the master sheet
        if content_list:
            sheet_manager = MasterSheetManager()
            
            # First, cleanup any existing duplicates
            logger.log_step("Cleaning up duplicate entries in Google Sheets...")
            sheet_manager.cleanup_duplicates()
            
            # Then update with current data
            sheet_manager.batch_update_content_status(content_list)
            logger.log_step(f"Updated master sheet with {len(content_list)} entries from database")
            
            # Save tracking data locally
            save_tracking_data_locally(content_list)
        else:
            logger.log_step("No data found in database to update master sheet")
            
    except Exception as e:
        logger.log_error(f"Error updating master sheet from database: {str(e)}")

# Removed old JSON-based update_master_sheet function - now using database-based update_master_sheet_from_database()

async def _sync_offline_updates(sheet_manager):
    """Try to sync any pending offline updates"""
    if not sheet_manager.service or not sheet_manager.offline_updates:
        return
        
    logger.log_step(f"Attempting to sync {len(sheet_manager.offline_updates)} offline updates")
    successful_updates = []
    
    for update in sheet_manager.offline_updates:
        try:
            # Try to update online sheet
            sheet_manager.update_content_status(update)
            successful_updates.append(update)
        except Exception as e:
            logger.log_error(f"Failed to sync update for {update.get('filename', 'unknown')}: {str(e)}")
            
    # Remove successful updates from the pending list
    for update in successful_updates:
        sheet_manager.offline_updates.remove(update)
    
    if successful_updates:
        logger.log_step(f"Successfully synced {len(successful_updates)} updates")
    if sheet_manager.offline_updates:
        logger.log_step(f"{len(sheet_manager.offline_updates)} updates still pending sync")

def check_file_exists_on_aiwaverider(filename: str, folder_path: str) -> bool:
    """Check if file already exists on AIWaverider Drive"""
    try:
        if not AIWAVERIDER_TOKEN:
            logger.log_error("AIWAVERIDER_DRIVE_TOKEN not found in environment variables")
            return False
        
        # Prepare headers
        headers = {
            'Authorization': f'Bearer {AIWAVERIDER_TOKEN}'
        }
        
        # Prepare the list files request
        list_url = AIWAVERIDER_UPLOAD_URL.replace('/webhook/files/upload', '/api/files/list')
        params = {
            'folder_path': folder_path
        }
        
        logger.log_step(f"Checking if file exists on AIWaverider Drive: {filename}")
        logger.log_step(f"Folder path: {folder_path}")
        
        # Make the request
        response = requests.get(
            list_url,
            headers=headers,
            params=params,
            timeout=30  # 30 second timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            files = data.get('files', [])
            
            # Check if our file exists - the API returns 'name' field, not 'filename'
            for file_info in files:
                if file_info.get('name') == filename:
                    logger.log_step(f"File already exists on AIWaverider Drive: {filename}")
                    return True
            
            logger.log_step(f"File not found on AIWaverider Drive: {filename}")
            return False
        else:
            logger.log_error(f"Failed to check file existence. Status: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        logger.log_error(f"Error checking file existence on AIWaverider Drive: {str(e)}")
        return False

async def upload_to_aiwaverider_drive_async(file_path: str, folder_path: str, file_type: str = "video") -> bool:
    """Async upload file to AIWaverider Drive with support for chunked uploads for large files"""
    try:
        if not AIWAVERIDER_TOKEN:
            logger.log_error("AIWAVERIDER_DRIVE_TOKEN not found in environment variables")
            return False
            
        if not os.path.exists(file_path):
            logger.log_error(f"File not found: {file_path}")
            return False
        
        # Check file size to determine upload method
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)  # Convert to MB
        
        logger.log_step(f"File size: {file_size_mb:.2f} MB")
        
        if file_size_mb < 10:
            # Use regular upload for files under 10MB
            return await _upload_small_file_async(file_path, folder_path, file_type)
        else:
            # Use chunked upload for files 10MB and above
            return await _upload_large_file_chunked_async(file_path, folder_path, file_type)
                
    except Exception as e:
        logger.log_error(f"Error uploading {file_type} to AIWaverider Drive: {str(e)}")
        return False

def upload_to_aiwaverider_drive(file_path: str, folder_path: str, file_type: str = "video") -> bool:
    """Upload file to AIWaverider Drive with support for chunked uploads for large files (sync version)"""
    try:
        if not AIWAVERIDER_TOKEN:
            logger.log_error("AIWAVERIDER_DRIVE_TOKEN not found in environment variables")
            return False
            
        if not os.path.exists(file_path):
            logger.log_error(f"File not found: {file_path}")
            return False
        
        # Check file size to determine upload method
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)  # Convert to MB
        
        logger.log_step(f"File size: {file_size_mb:.2f} MB")
        
        if file_size_mb < 10:
            # Use regular upload for files under 10MB
            return _upload_small_file(file_path, folder_path, file_type)
        else:
            # Use chunked upload for files 10MB and above
            return _upload_large_file_chunked(file_path, folder_path, file_type)
                
    except Exception as e:
        logger.log_error(f"Error uploading {file_type} to AIWaverider Drive: {str(e)}")
        return False

async def _upload_small_file_async(file_path: str, folder_path: str, file_type: str) -> bool:
    """Async upload small files (< 10MB) using regular upload endpoint"""
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        return await loop.run_in_executor(executor, _upload_small_file, file_path, folder_path, file_type)

def _upload_small_file(file_path: str, folder_path: str, file_type: str) -> bool:
    """Upload small files (< 10MB) using regular upload endpoint"""
    try:
        headers = {
            'Authorization': f'Bearer {AIWAVERIDER_TOKEN}'
        }
        
        # Prepare files and data
        with open(file_path, 'rb') as file:
            files = {
                'file': (os.path.basename(file_path), file, 'application/octet-stream')
            }
            data = {
                'folder_path': folder_path
            }
            
            logger.log_step(f"Uploading small {file_type} to AIWaverider Drive: {os.path.basename(file_path)}")
            logger.log_step(f"Folder path: {folder_path}")
            
            # Use connection pooling
            session = get_http_session()
            response = session.post(
                AIWAVERIDER_UPLOAD_URL,
                headers=headers,
                files=files,
                data=data,
                timeout=300  # 5 minute timeout
            )
            
            if response.status_code == 200:
                logger.log_step(f"Successfully uploaded small {file_type} to AIWaverider Drive: {os.path.basename(file_path)}")
                return True
            else:
                logger.log_error(f"Failed to upload small {file_type} to AIWaverider Drive. Status: {response.status_code}, Response: {response.text}")
                return False
                
    except Exception as e:
        logger.log_error(f"Error uploading small {file_type} to AIWaverider Drive: {str(e)}")
        return False

async def _upload_large_file_chunked_async(file_path: str, folder_path: str, file_type: str) -> bool:
    """Async upload large files (>= 10MB) using chunked upload endpoint"""
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        return await loop.run_in_executor(executor, _upload_large_file_chunked, file_path, folder_path, file_type)

def _upload_large_file_chunked(file_path: str, folder_path: str, file_type: str) -> bool:
    """Upload large files (>= 10MB) using chunked upload endpoint"""
    try:
        import uuid
        
        # Generate unique upload ID
        upload_id = str(uuid.uuid4())
        filename = os.path.basename(file_path)
        
        # Calculate chunk size (5MB chunks)
        chunk_size = 5 * 1024 * 1024  # 5MB
        file_size = os.path.getsize(file_path)
        total_chunks = (file_size + chunk_size - 1) // chunk_size  # Ceiling division
        
        logger.log_step(f"Starting chunked upload for large {file_type}: {filename}")
        logger.log_step(f"File size: {file_size / (1024 * 1024):.2f} MB")
        logger.log_step(f"Total chunks: {total_chunks}")
        logger.log_step(f"Upload ID: {upload_id}")
        
        # Step 1: Upload file chunks
        if not _upload_file_chunks(file_path, upload_id, chunk_size, total_chunks):
            logger.log_error(f"Failed to upload chunks for {filename}")
            return False
        
        # Step 2: Complete the chunked upload
        if not _complete_chunked_upload(upload_id, filename, total_chunks, folder_path):
            logger.log_error(f"Failed to complete chunked upload for {filename}")
            return False
        
        logger.log_step(f"Successfully uploaded large {file_type} using chunked upload: {filename}")
        return True
            
    except Exception as e:
        logger.log_error(f"Error uploading large {file_type} to AIWaverider Drive: {str(e)}")
        return False

def _upload_file_chunks(file_path: str, upload_id: str, chunk_size: int, total_chunks: int) -> bool:
    """Upload file in chunks to the chunked upload endpoint"""
    try:
        headers = {
            'Authorization': f'Bearer {AIWAVERIDER_TOKEN}'
        }
        
        # Get the chunked upload URL
        chunked_upload_url = AIWAVERIDER_UPLOAD_URL.replace('/webhook/files/upload', '/webhook/files/upload-chunk')
        
        # Use connection pooling
        session = get_http_session()
        
        with open(file_path, 'rb') as file:
            for chunk_number in range(1, total_chunks + 1):
                # Read chunk data
                chunk_data = file.read(chunk_size)
                if not chunk_data:
                    break
                
                logger.log_step(f"Uploading chunk {chunk_number}/{total_chunks} for upload_id: {upload_id}")
                
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
                response = session.post(
                    chunked_upload_url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=60  # 1 minute timeout per chunk
                )
                
                if response.status_code != 200:
                    logger.log_error(f"Failed to upload chunk {chunk_number}. Status: {response.status_code}, Response: {response.text}")
                    return False
                
                logger.log_step(f"Successfully uploaded chunk {chunk_number}/{total_chunks}")
        
        return True
        
    except Exception as e:
        logger.log_error(f"Error uploading file chunks: {str(e)}")
        return False

def _complete_chunked_upload(upload_id: str, filename: str, total_chunks: int, folder_path: str) -> bool:
    """Complete the chunked upload process"""
    try:
        headers = {
            'Authorization': f'Bearer {AIWAVERIDER_TOKEN}',
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
        chunked_upload_url = AIWAVERIDER_UPLOAD_URL.replace('/webhook/files/upload', '/webhook/files/complete-chunked-upload')
        
        logger.log_step(f"Completing chunked upload for: {filename}")
        logger.log_step(f"Request data: {chunked_upload_data}")
        
        # Use connection pooling
        session = get_http_session()
        response = session.post(
            chunked_upload_url,
            headers=headers,
            json=chunked_upload_data,
            timeout=300  # 5 minute timeout
        )
        
        if response.status_code == 200:
            logger.log_step(f"Successfully completed chunked upload for: {filename}")
            logger.log_step(f"Response: {response.text}")
            return True
        else:
            logger.log_error(f"Failed to complete chunked upload for {filename}. Status: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        logger.log_error(f"Error completing chunked upload: {str(e)}")
        return False

def get_cached_file_list(folder_path: str) -> set:
    """Get cached file list or fetch fresh data if cache is expired"""
    cache_file = f"data/cache/cache_{folder_path.replace('/', '_').replace('\\', '_')}.json"
    
    try:
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
                cache_age = time.time() - cache_data.get('timestamp', 0)
                if cache_age < CACHE_DURATION_HOURS * 3600:
                    logger.log_step(f"Using cached file list for {folder_path} (age: {cache_age/60:.1f} minutes)")
                    return set(cache_data.get('files', []))
    except Exception as e:
        logger.log_step(f"Cache read error: {str(e)}, fetching fresh data")
    
    # Get fresh data
    files = get_aiwaverider_file_list_fresh(folder_path)
    
    # Cache the result
    try:
        with open(cache_file, 'w') as f:
            json.dump({'files': list(files), 'timestamp': time.time()}, f)
        logger.log_step(f"Cached file list for {folder_path}")
    except Exception as e:
        logger.log_step(f"Cache write error: {str(e)}")
    
    return files

def get_aiwaverider_file_list_fresh(folder_path: str) -> set:
    """Get fresh list of files from AIWaverider Drive for a specific folder"""
    try:
        if not AIWAVERIDER_TOKEN:
            logger.log_error("AIWAVERIDER_DRIVE_TOKEN not found in environment variables")
            return set()
        
        # Prepare headers
        headers = {
            'Authorization': f'Bearer {AIWAVERIDER_TOKEN}'
        }
        
        # Prepare the list files request
        list_url = AIWAVERIDER_UPLOAD_URL.replace('/webhook/files/upload', '/api/files/list')
        params = {
            'folder_path': folder_path
        }
        
        logger.log_step(f"Getting fresh file list from AIWaverider Drive for folder: {folder_path}")
        
        # Use connection pooling
        session = get_http_session()
        response = session.get(
            list_url,
            headers=headers,
            params=params,
            timeout=30  # 30 second timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            files = data.get('files', [])
            
            # Extract filenames - the API returns 'name' field, not 'filename'
            filenames = {file_info.get('name') for file_info in files if file_info.get('name')}
            logger.log_step(f"Found {len(filenames)} files in AIWaverider Drive folder: {folder_path}")
            return filenames
        else:
            logger.log_error(f"Failed to get file list. Status: {response.status_code}, Response: {response.text}")
            return set()
            
    except Exception as e:
        logger.log_error(f"Error getting file list from AIWaverider Drive: {str(e)}")
        return set()

def get_aiwaverider_file_list(folder_path: str) -> set:
    """Get list of files from AIWaverider Drive for a specific folder (with caching)"""
    return get_cached_file_list(folder_path)

async def upload_video_to_aiwaverider(video_path: str) -> bool:
    """Upload video to AIWaverider Drive with /videos/instagram/ai.uprise path"""
    return await upload_to_aiwaverider_drive_async(video_path, "/videos/instagram/ai.uprise", "video")

async def upload_thumbnail_to_aiwaverider(thumbnail_path: str) -> bool:
    """Upload thumbnail to AIWaverider Drive with /thumbnails/instagram path"""
    return await upload_to_aiwaverider_drive_async(thumbnail_path, "/thumbnails/instagram", "thumbnail")

def upload_video_to_aiwaverider_sync(video_path: str) -> bool:
    """Synchronous wrapper for video upload"""
    return upload_to_aiwaverider_drive(video_path, "/videos/instagram/ai.uprise", "video")

def upload_thumbnail_to_aiwaverider_sync(thumbnail_path: str) -> bool:
    """Synchronous wrapper for thumbnail upload"""
    return upload_to_aiwaverider_drive(thumbnail_path, "/thumbnails/instagram", "thumbnail")

async def upload_to_aiwaverider():
    """Upload all videos and thumbnails to AIWaverider Drive"""
    try:
        logger.log_step("Starting AIWaverider Drive uploads")
        
        # Get videos and thumbnails from database instead of JSON files
        videos = await db_manager.get_videos_by_status('COMPLETED')
        thumbnails = await db_manager.get_thumbnails_by_status('COMPLETED')
        
        if not videos and not thumbnails:
            logger.log_step("No completed videos or thumbnails found in database")
            return True
        
        # Get existing files from AIWaverider Drive to avoid duplicates
        logger.log_step("Checking existing files on AIWaverider Drive...")
        existing_videos = get_aiwaverider_file_list("/videos/instagram/ai.uprise")
        existing_thumbnails = get_aiwaverider_file_list("/thumbnails/instagram")
        
        # Upload videos
        logger.log_step("Uploading videos to AIWaverider Drive...")
        video_uploads = []
        for video in videos:
            # Check if video has been uploaded to Google Drive (has drive_id)
            if video.get('drive_id'):
                file_path = video.get('file_path', '')
                if os.path.exists(file_path):
                    filename = os.path.basename(file_path)
                    if filename in existing_videos:
                        logger.log_step(f"Skipping video - already exists on AIWaverider Drive: {filename}")
                    else:
                        video_uploads.append(file_path)
                        logger.log_step(f"Found video for AIWaverider upload: {filename}")
                else:
                    logger.log_step(f"Video file not found locally: {file_path}")
        
        # Upload videos and thumbnails in parallel
        logger.log_step("Uploading videos and thumbnails to AIWaverider Drive in parallel...")
        
        # Prepare thumbnail uploads
        thumbnail_uploads = []
        for thumbnail in thumbnails:
            # Check if thumbnail has been uploaded to Google Drive (has drive_id)
            if thumbnail.get('drive_id'):
                file_path = thumbnail.get('file_path', '')
                if os.path.exists(file_path):
                    filename = os.path.basename(file_path)
                    if filename in existing_thumbnails:
                        logger.log_step(f"Skipping thumbnail - already exists on AIWaverider Drive: {filename}")
                    else:
                        thumbnail_uploads.append(file_path)
                        logger.log_step(f"Found thumbnail for AIWaverider upload: {filename}")
                else:
                    logger.log_step(f"Thumbnail file not found locally: {file_path}")
        
        # Create upload tasks
        upload_tasks = []
        
        # Add video upload tasks
        for video_path in video_uploads:
            upload_tasks.append(('video', video_path))
        
        # Add thumbnail upload tasks
        for thumb_path in thumbnail_uploads:
            upload_tasks.append(('thumbnail', thumb_path))
        
        # Execute uploads in parallel with progress tracking
        if upload_tasks:
            logger.log_step(f"Starting parallel upload of {len(upload_tasks)} files...")
            
            # Create semaphore to limit concurrent uploads (max 3 at a time)
            semaphore = asyncio.Semaphore(3)
            
            async def upload_with_semaphore(file_type: str, file_path: str, progress_callback=None):
                async with semaphore:
                    if progress_callback:
                        progress_callback(f"Uploading {file_type}: {os.path.basename(file_path)}")
                    if file_type == 'video':
                        return await upload_video_to_aiwaverider(file_path)
                    else:
                        return await upload_thumbnail_to_aiwaverider(file_path)
            
            # Progress tracking
            completed = 0
            total = len(upload_tasks)
            
            def progress_callback(message):
                nonlocal completed
                completed += 1
                if TQDM_AVAILABLE:
                    logger.log_step(f"[{completed}/{total}] {message}")
                else:
                    logger.log_step(f"[{completed}/{total}] {message}")
            
            # Execute all uploads concurrently
            results = await asyncio.gather(
                *[upload_with_semaphore(file_type, file_path, progress_callback) for file_type, file_path in upload_tasks],
                return_exceptions=True
            )
            
            # Process results
            successful_uploads = 0
            failed_uploads = 0
            
            for i, (file_type, file_path) in enumerate(upload_tasks):
                result = results[i]
                filename = os.path.basename(file_path)
                
                if isinstance(result, Exception):
                    logger.log_error(f"Failed to upload {file_type}: {filename} - {str(result)}")
                    failed_uploads += 1
                elif result:
                    logger.log_step(f"Successfully uploaded {file_type}: {filename}")
                    successful_uploads += 1
                else:
                    logger.log_error(f"Failed to upload {file_type}: {filename}")
                    failed_uploads += 1
            
            logger.log_step(f"Upload completed: {successful_uploads} successful, {failed_uploads} failed")
        else:
            logger.log_step("No files to upload to AIWaverider Drive")
        
        logger.log_step("AIWaverider Drive uploads completed")
        return True
        
    except Exception as e:
        logger.log_error(f"Error during AIWaverider uploads: {str(e)}")
        return False

async def main():
    try:
        logger.log_step("Starting social media processor with advanced features")
        
        # Initialize database
        await db_manager.initialize()
        logger.log_step("Database initialized")
        
        # Start metrics collection
        processing_metrics = metrics_collector.start_processing_metrics()
        logger.log_step("Metrics collection started")
        
        # Start queue processor
        await queue_processor.start()
        logger.log_step("Queue processor started")
        
        # Verify required files exist
        required_files = [
            'scripts/upload-new-video-to-google.py',
            'scripts/upload-thumbnails-to-google.py',
            'core/full-rounded-url-download-transcription.py'
        ]
        for file in required_files:
            if not os.path.exists(file):
                logger.log_error(f"Required file not found: {file}", error_type="FileNotFoundError")
                return
                
    except Exception as e:
        logger.log_error(f"Initialization error: {str(e)}")
        return
    
    # Check for urls.txt and create if needed
    urls_file = 'data/urls.txt'
    if not os.path.exists(urls_file):
        logger.log_step(f"Creating empty {urls_file}")
        try:
            with open(urls_file, 'w', encoding='utf-8') as f:
                f.write("# Add your URLs here, one per line\n")
            logger.log_error(f"{urls_file} created. Please add URLs before running again.", error_type="SetupRequired")
            return
        except Exception as e:
            logger.log_error(f"Failed to create {urls_file}: {str(e)}", error_type="FileError")
            return
            
    # Check if urls.txt has content
    try:
        with open(urls_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        if not lines:
            logger.log_error(f"{urls_file} is empty. Please add URLs before running.", error_type="SetupRequired")
            return
    except Exception as e:
        logger.log_error(f"Failed to read {urls_file}: {str(e)}", error_type="FileError")
        return
    
    # Step 1: Run full-rounded
    if not await run_full_rounded(urls_file):
        return
    
    # Step 2: Run uploaders in parallel
    if not await run_uploaders():
        return
    
    # Step 3: Upload to AIWaverider Drive
    print("Uploading to AIWaverider Drive...")
    await upload_to_aiwaverider()
    
    # Step 4: Update master sheet
    print("Updating master tracking sheet...")
    # Update master sheet using database data
    await update_master_sheet_from_database()
    
    # Step 5: Finish metrics collection
    metrics_collector.finish_processing_metrics()
    
    # Step 6: Get health status
    health_status = await metrics_collector.get_health_status()
    logger.log_step(f"System health: {health_status['overall_status']}")
    
    # Step 7: Get queue status
    queue_status = await queue_processor.get_queue_status()
    logger.log_step(f"Queue status: {queue_status['pending_tasks']} pending tasks")
    
    # Step 8: Cleanup
    try:
        await queue_processor.stop()
        logger.log_step("Queue processor stopped")
    except Exception as e:
        logger.log_error(f"Error stopping queue processor: {str(e)}")
    
    # Give a moment for any pending database operations to complete
    await asyncio.sleep(0.5)
    
    try:
        await db_manager.close()
        logger.log_step("Database connections closed")
    except Exception as e:
        logger.log_error(f"Error closing database: {str(e)}")
    
    # Final cleanup delay
    await asyncio.sleep(0.5)
    
    print("\nProcessing complete! Check the master sheet for status.")
    print(f"System health: {health_status['overall_status']}")
    print(f"Queue status: {queue_status['pending_tasks']} pending tasks")

if __name__ == '__main__':
    asyncio.run(main())