#!/usr/bin/env python3
"""
Upload thumbnails folder to a specified Google Drive folder and track uploads in database

Usage:
  python upload-thumbnails-to-google.py

Config via .env (optional):
  THUMBNAILS_DIR - folder to watch (default: assets/downloads/thumbnails)
  THUMBNAILS_DRIVE_FOLDER_ID - target Drive folder id (default: provided by user)

This script mirrors the behavior of the video uploader but for image files.
"""
import os
import sys
import asyncio
import hashlib
import schedule
import argparse
from datetime import datetime
from typing import Dict
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from dotenv import load_dotenv

# Add parent directory to path to import system modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from system.database import db_manager

# Load environment
load_dotenv()

# Configuration
THUMBNAILS_DIR = os.getenv('THUMBNAILS_DIR', 'assets/downloads/thumbnails')
# Default Drive folder ID provided by user; can be overridden in .env
DEFAULT_THUMBNAILS_DRIVE_FOLDER_ID = os.getenv('THUMBNAILS_DRIVE_FOLDER_ID', '1iUmCVkX863MqyvJIZ_aWbi9toEI39X8Z')
SCOPES = ['https://www.googleapis.com/auth/drive.file']
CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'config/credentials.json')
TOKEN_FILE = os.getenv('GOOGLE_TOKEN_FILE', 'config/token.json')

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


async def load_state() -> Dict[str, Dict]:
    """
    Load the state from the database.
    """
    try:
        thumbnails = await db_manager.get_all_thumbnails()
        state = {}
        for thumbnail in thumbnails:
            file_path = thumbnail.get('file_path', '')
            if file_path:
                # Normalize path for consistent comparison
                normalized_path = os.path.normpath(file_path)
                state[normalized_path] = {
                    'filename': thumbnail.get('filename', ''),
                    'video_filename': thumbnail.get('video_filename', ''),
                    'drive_id': thumbnail.get('drive_id', ''),
                    'drive_url': thumbnail.get('drive_url', ''),
                    'upload_status': thumbnail.get('upload_status', 'PENDING'),
                    'file_hash': thumbnail.get('file_hash', ''),
                    'content_hash': thumbnail.get('file_hash', ''),  # For backward compatibility
                    'last_modified': thumbnail.get('updated_at', '')
                }
        return state
    except Exception as e:
        print(f"Error loading state from database: {e}")
        return {}


async def save_state(state: Dict[str, Dict]):
    """
    Save the state to the database.
    """
    try:
        # Update database with current state
        for file_path, data in state.items():
            await db_manager.upsert_thumbnail({
                'filename': data.get('filename', ''),
                'file_path': file_path,
                'video_filename': data.get('video_filename', ''),
                'drive_id': data.get('drive_id', ''),
                'drive_url': data.get('drive_url', ''),
                'upload_status': data.get('upload_status', 'PENDING'),
                'file_hash': data.get('file_hash', '')
            })
        print(f"State saved successfully to database: {len(state)} files tracked")
    except Exception as e:
        print(f"Error saving state to database: {e}")


def get_file_hash(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def get_drive_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Failed to refresh credentials: {e}")
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080, access_type='offline', prompt='consent')
        with open(TOKEN_FILE, 'w', encoding='utf-8') as f:
            f.write(creds.to_json())

    service = build('drive', 'v3', credentials=creds)
    return service


def get_file_by_name_in_folder(service, filename: str, folder_id: str):
    query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    files = results.get('files', [])
    return files[0] if files else None


async def upload_file(service, file_path: str, folder_id: str, state: Dict[str, Dict]):
    filename = os.path.basename(file_path)
    current_hash = get_file_hash(file_path)
    
    # Normalize path for comparison with database state
    normalized_path = os.path.normpath(file_path)

    if normalized_path in state and state[normalized_path].get('file_hash') == current_hash and state[normalized_path].get('upload_status') == 'COMPLETED':
        print(f"Skipping (unchanged): {filename}")
        return None

    # Check existing in Drive
    existing = get_file_by_name_in_folder(service, filename, folder_id)
    media = MediaFileUpload(file_path, resumable=True)

    if existing:
        try:
            service.files().update(fileId=existing['id'], media_body=media).execute()
            file_id = existing['id']
            print(f"Updated thumbnail in Drive: {filename} (ID: {file_id})")
        except Exception as e:
            print(f"Failed to update {filename}: {e}")
            return None
    else:
        try:
            meta = {'name': filename, 'parents': [folder_id]}
            uploaded = service.files().create(body=meta, media_body=media, fields='id, name').execute()
            file_id = uploaded.get('id')
            print(f"Uploaded thumbnail to Drive: {filename} (ID: {file_id})")
        except Exception as e:
            print(f"Failed to upload {filename}: {e}")
            return None

    # Update state
    state_entry = state.get(normalized_path, {})
    state_entry.update({
        'file_path': normalized_path,
        'filename': filename,
        'file_hash': current_hash,
        'content_hash': current_hash,  # For backward compatibility
        'drive_id': file_id,
        'drive_url': f"https://drive.google.com/file/d/{file_id}/view",
        'upload_status': 'COMPLETED',
        'last_upload': datetime.now().isoformat()
    })
    state[normalized_path] = state_entry
    
    # Update database with successful upload
    try:
        await db_manager.upsert_thumbnail({
            'filename': filename,
            'file_path': normalized_path,
            'video_filename': '',  # Will be updated later if needed
            'drive_id': file_id,
            'drive_url': f"https://drive.google.com/file/d/{file_id}/view",
            'upload_status': 'COMPLETED',
            'file_hash': current_hash
        })
        print(f"✅ Database updated for: {filename}")
    except Exception as e:
        print(f"❌ Error updating database for {filename}: {e}")
    return file_id


def find_image_files(folder: str):
    files = []
    if not os.path.exists(folder):
        return files
    for root, dirs, filenames in os.walk(folder):
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                files.append(os.path.join(root, name))
    return files


async def check_and_upload():
    """
    Scan the thumbnails directory and upload new/modified image files.
    """
    print(f"\n[{datetime.now()}] Starting thumbnail scan in: {THUMBNAILS_DIR}")
    print(f"Target Drive folder ID: {DEFAULT_THUMBNAILS_DRIVE_FOLDER_ID}")
    
    state = await load_state()
    files = find_image_files(THUMBNAILS_DIR)
    
    if not files:
        print("No image files found to upload.")
        return

    service = get_drive_service()
    uploaded = 0
    
    for f in sorted(files):
        try:
            res = await upload_file(service, f, DEFAULT_THUMBNAILS_DRIVE_FOLDER_ID, state)
            if res:
                uploaded += 1
        except Exception as e:
            print(f"Error uploading {f}: {e}")

    if uploaded > 0:
        await save_state(state)
        print(f"Done. Uploaded/updated: {uploaded} file(s)")
    else:
        print("No new or updated files to upload")

async def main(single_run=False):
    """
    Run thumbnail uploader in either single-run or continuous mode.
    Args:
        single_run (bool): If True, run once and exit. If False, run continuously.
    """
    print(f"Thumbnail uploader starting.")
    print(f"Watching directory: {THUMBNAILS_DIR}")
    print(f"Target Drive folder ID: {DEFAULT_THUMBNAILS_DRIVE_FOLDER_ID}")
    print(f"Mode: {'single-run' if single_run else 'continuous'}")
    
    # Initialize database
    await db_manager.initialize()
    print("Database initialized successfully")
    
    # Do initial check
    await check_and_upload()
    
    if not single_run:
        # Schedule periodic checks only in continuous mode
        schedule.every(1).minutes.do(lambda: asyncio.run(check_and_upload()))
        
        print("\nThumbnail monitor is running in continuous mode. Press Ctrl+C to exit.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nExiting thumbnail monitor...")
    else:
        print("\nThumbnail check completed (single run mode)")
    
    await db_manager.close()


if __name__ == '__main__':
    # Add command line argument parsing
    parser = argparse.ArgumentParser(description='Upload thumbnails to Google Drive')
    parser.add_argument('--single-run', action='store_true', help='Run once and exit (default: continuous mode)')
    args = parser.parse_args()
    
    asyncio.run(main(single_run=args.single_run))
