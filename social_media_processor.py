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
import asyncio
import subprocess
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Load environment variables
load_dotenv()

# Configuration
SCOPES = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/spreadsheets']
CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')
TOKEN_FILE = os.getenv('GOOGLE_TOKEN_FILE', 'token.json')
MASTER_SHEET_ID = os.getenv('MASTER_SHEET_ID')  # Must be set in .env
MASTER_SHEET_NAME = 'Content Tracking'

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
    'thumbnail_image'
]

class MasterSheetManager:
    def __init__(self):
        self.service = self._get_service()
        self._ensure_sheet_exists()
        
    def _get_service(self):
        creds = None
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        
        return build('sheets', 'v4', credentials=creds)
    
    def _ensure_sheet_exists(self):
        try:
            result = self.service.spreadsheets().get(
                spreadsheetId=MASTER_SHEET_ID,
                ranges=[MASTER_SHEET_NAME],
                includeGridData=False
            ).execute()
            
            # Check if our sheet exists
            sheet_exists = any(sheet['properties']['title'] == MASTER_SHEET_NAME 
                             for sheet in result['sheets'])
            
            if not sheet_exists:
                # Add the sheet with headers
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=MASTER_SHEET_ID,
                    body={
                        'requests': [{
                            'addSheet': {
                                'properties': {
                                    'title': MASTER_SHEET_NAME
                                }
                            }
                        }]
                    }
                ).execute()
                
                # Add headers
                self.service.spreadsheets().values().update(
                    spreadsheetId=MASTER_SHEET_ID,
                    range=f'{MASTER_SHEET_NAME}!A1:R1',
                    valueInputOption='RAW',
                    body={'values': [SHEET_COLUMNS]}
                ).execute()
                
                print(f"Created sheet '{MASTER_SHEET_NAME}' with headers")
            
        except Exception as e:
            print(f"Error ensuring sheet exists: {e}")
            raise
    
    def update_content_status(self, content_info: Dict[str, Any]):
        """Update or append content information to the master sheet"""
        try:
            # First, check if entry exists
            result = self.service.spreadsheets().values().get(
                spreadsheetId=MASTER_SHEET_ID,
                range=f'{MASTER_SHEET_NAME}!A:B'
            ).execute()
            
            values = result.get('values', [])
            if not values:
                row_number = 2  # First data row
            else:
                # Look for matching filename
                found = False
                for idx, row in enumerate(values[1:], start=2):
                    if row and row[1] == content_info['filename']:
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
            range_name = f'{MASTER_SHEET_NAME}!A{row_number}:R{row_number}'
            self.service.spreadsheets().values().update(
                spreadsheetId=MASTER_SHEET_ID,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body={'values': [row_data]}
            ).execute()
            
            print(f"Updated sheet row {row_number} for {content_info['filename']}")
            
        except Exception as e:
            print(f"Error updating master sheet: {e}")
            raise

async def run_full_rounded(urls_file: str):
    """Run the full-rounded script and wait for completion"""
    try:
        print("Starting full-rounded processing...")
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            'full-rounded-url-download-transcription.py',
            '--urls-file', urls_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            print(f"Error in full-rounded: {stderr.decode()}")
            return False
            
        print("Full-rounded processing complete")
        return True
        
    except Exception as e:
        print(f"Error running full-rounded: {e}")
        return False

async def run_uploaders():
    """Run video and thumbnail uploaders in parallel"""
    try:
        print("Starting uploaders...")
        video_uploader = await asyncio.create_subprocess_exec(
            sys.executable,
            'upload-new-video-to-google.py',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        thumbnail_uploader = await asyncio.create_subprocess_exec(
            sys.executable,
            'upload-thumbnails-to-google.py',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Wait for both to finish initial upload
        await asyncio.gather(
            video_uploader.communicate(),
            thumbnail_uploader.communicate()
        )
        
        print("Initial uploads complete")
        return True
        
    except Exception as e:
        print(f"Error running uploaders: {e}")
        return False

def update_master_sheet(state_file: str, thumbnails_state_file: str):
    """Update master sheet with latest upload status"""
    sheet_manager = MasterSheetManager()
    
    # Load state files
    with open(state_file) as f:
        video_state = json.load(f)
    with open(thumbnails_state_file) as f:
        thumb_state = json.load(f)
    
    # Process each video and its thumbnail
    for video_path, video_info in video_state.items():
        video_name = video_info['file_name']
        base_name = os.path.splitext(video_name)[0]
        
        # Find matching thumbnail
        thumb_info = None
        for thumb_path, info in thumb_state.items():
            if base_name in thumb_path:
                thumb_info = info
                break
        
        # Prepare content info
        content_info = {
            'drive_id': video_info.get('drive_id', ''),
            'filename': video_name,
            'video_name': video_name,
            'thumbnail_name': thumb_info['file_name'] if thumb_info else '',
            'file_path_drive': f"https://drive.google.com/file/d/{video_info.get('drive_id', '')}/view",
            'upload_time': video_info.get('last_upload', ''),
            'upload_status_thumbnail': STATUS_UPLOADED if thumb_info else STATUS_PENDING,
            'thumbnail_image': f"=IMAGE(\"https://drive.google.com/uc?id={thumb_info['drive_id']}\")" if thumb_info else ''
        }
        
        # Update sheet
        sheet_manager.update_content_status(content_info)

async def main():
    if not MASTER_SHEET_ID:
        print("ERROR: MASTER_SHEET_ID must be set in .env file")
        return
    
    urls_file = 'urls.txt'
    if not os.path.exists(urls_file):
        print(f"Error: {urls_file} not found")
        return
    
    # Step 1: Run full-rounded
    if not await run_full_rounded(urls_file):
        return
    
    # Step 2: Run uploaders in parallel
    if not await run_uploaders():
        return
    
    # Step 3: Update master sheet
    print("Updating master tracking sheet...")
    update_master_sheet('state.json', 'state-thumbnails.json')
    
    print("\nProcessing complete! Check the master sheet for status.")

if __name__ == '__main__':
    asyncio.run(main())