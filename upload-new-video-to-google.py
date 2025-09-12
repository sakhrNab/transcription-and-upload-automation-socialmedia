import os
import json
import time
import schedule
import hashlib
from datetime import datetime
from tqdm import tqdm
from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# The purpose of this class is to upload videos (.mp4) to GDrive and tracks the status of uploaded videos
# to avoid duplicated uploads

# ---------------------------
# Configuration Variables
# ---------------------------
load_dotenv()

# Path to watch for new/updated .mp4 files. Can be set in a .env file as FOLDER_TO_WATCH
# Example .env entry: FOLDER_TO_WATCH=E:/AIWaverider/videos
FOLDER_TO_WATCH = os.getenv('FOLDER_TO_WATCH', os.getcwd())  # Default to current working directory
STATE_FILE = 'state.json'       # File to store state info for each MP4 file
SCOPES = ['https://www.googleapis.com/auth/drive.file']
CREDENTIALS_FILE = 'credentials.json'  # Your Google API credentials file
TOKEN_FILE = 'token.json'              # Stores the user's access and refresh tokens
DRIVE_FOLDER = 'AIWaverider'
EXCLUDED_FOLDERS = {
    'temp', '.temp', 'tmp', '.tmp', 
    '.__capcut_export_temp_folder__', 
    '.venv', 'venv',       # Exclude both .venv and venv
    '__pycache__',         # Exclude Python cache
    'node_modules',        # Exclude node modules if any
    'downloaded_videos'    # Exclude downloaded videos folder
}

class DriveFolder:
    def __init__(self):
        self.id = None
        self.name = None

_drive_folder = DriveFolder()  # Global folder cache

# ---------------------------
# Google Drive API Functions
# ---------------------------
def get_drive_service():
    """
    Authenticate with Google Drive using OAuth and return a service object.
    NOTE: We include access_type='offline' and prompt='consent' to ensure we receive a refresh token.
    """
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # The following parameters are added to request offline access and force consent.
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=8080, access_type='offline', prompt='consent')
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    
    return build('drive', 'v3', credentials=creds)

def get_folder_id(service):
    """
    Get the folder ID for the DRIVE_FOLDER.
    """
    global _drive_folder
    
    if _drive_folder.id and _drive_folder.name == DRIVE_FOLDER:
        try:
            service.files().get(fileId=_drive_folder.id, fields='id, name, trashed').execute()
            return _drive_folder.id
        except Exception as e:
            _drive_folder.id = None
    
    results = service.files().list(
        q=f"name='{DRIVE_FOLDER}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        spaces='drive',
        fields='files(id, name)',
        orderBy='createdTime'
    ).execute()
    
    if results['files']:
        _drive_folder.id = results['files'][0]['id']
        _drive_folder.name = DRIVE_FOLDER
        if len(results['files']) > 1:
            print(f"Warning: Found {len(results['files'])} folders named '{DRIVE_FOLDER}'. Using the oldest one.")
        else:
            print(f"Using existing folder '{DRIVE_FOLDER}' (ID: {_drive_folder.id})")
        return _drive_folder.id
    
    folder_metadata = {
        'name': DRIVE_FOLDER,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    folder = service.files().create(body=folder_metadata, fields='id, name').execute()
    _drive_folder.id = folder['id']
    _drive_folder.name = DRIVE_FOLDER
    print(f"Created new folder '{DRIVE_FOLDER}' (ID: {_drive_folder.id})")
    return _drive_folder.id

def get_file_hash(file_path):
    """Calculate SHA256 hash of file content"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def upload_file(service, file_path, state):
    """Upload file with state tracking and duplicate handling"""
    file_name = os.path.basename(file_path)
    folder_id = get_folder_id(service)
    
    current_hash = get_file_hash(file_path)
    # Only skip if file has been uploaded before and its hash matches.
    if file_path in state and state[file_path].get('content_hash') == current_hash:
        print(f"File {file_name} already uploaded with same content. Skipping.")
        return None
    
    # Check if file exists in Drive
    existing_file = get_file_by_name(service, file_name, folder_id)
    if existing_file:
        print(f"Updating existing file in Drive: {file_name}")
        file_id = update_existing_file(service, existing_file['id'], file_path)
    else:
        # Upload new file
        file_size = os.path.getsize(file_path)
        media = MediaFileUpload(file_path, resumable=True, chunksize=1024*1024)
        
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        
        request = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name'
        )
        
        print(f"\n[{datetime.now()}] Uploading: {file_name}")
        response = None
        progress_bar = tqdm(total=file_size, unit='B', unit_scale=True)
        
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress_bar.update(status.resumable_progress - progress_bar.n)
        
        progress_bar.close()
        file_id = response.get('id')
        print(f"[{datetime.now()}] Completed uploading: {response.get('name')} (ID: {file_id})")
    
    # Update state with new file hash after successful upload/update.
    state[file_path]['content_hash'] = current_hash
    state[file_path]['drive_id'] = file_id
    state[file_path]['last_upload'] = datetime.now().isoformat()
    
    return file_id

def update_existing_file(service, file_id, file_path):
    """Update existing file in Drive"""
    media = MediaFileUpload(file_path, resumable=True)
    
    try:
        file = service.files().update(
            fileId=file_id,
            media_body=media
        ).execute()
        print(f"Updated existing file: {file.get('name')}")
        return file.get('id')
    except Exception as e:
        print(f"Error updating file: {e}")
        return None

def get_file_by_name(service, filename, folder_id):
    """
    Find a file by name (exact match) in a specific folder.
    """
    query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
    results = service.files().list(
        q=query,
        spaces='drive',
        fields='files(id, name, modifiedTime)'
    ).execute()
    
    files = results.get('files', [])
    return files[0] if files else None

# ---------------------------
# Folder Monitoring Functions
# ---------------------------
def load_state():
    """
    Load the state from the JSON file.
    """
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print("Warning: Corrupted state file. Starting fresh.")
                return {}
    return {}

def save_state(state):
    """
    Save the state to the JSON file.
    """
    try:
        temp_file = STATE_FILE + '.tmp'
        with open(temp_file, 'w') as f:
            json.dump(state, f, indent=2)
        os.replace(temp_file, STATE_FILE)
        print(f"State saved successfully: {len(state)} files tracked")
    except Exception as e:
        print(f"Error saving state file: {e}")

def find_mp4_files_in_subfolder(subfolder_path):
    """
    Walk the subfolder and return a list of .mp4 file paths,
    excluding any directories whose names match the EXCLUDED_FOLDERS.
    """
    mp4_files = []
    for root, dirs, files in os.walk(subfolder_path):
        # Filter out directories we want to exclude
        dirs[:] = [d for d in dirs if not any(excluded in d.lower() for excluded in EXCLUDED_FOLDERS)]
        for file in files:
            if file.lower().endswith('.mp4'):
                mp4_files.append(os.path.join(root, file))
    return mp4_files

def scan_folder(folder, state):
    """
    Scan the main folder and its subfolders for new or modified MP4 files.
    State is tracked per file (by full path).
    """
    files_to_upload = []
    current_files = set()
    
    print(f"\nScanning directory: {folder}")
    
    # Check MP4 files directly in the main folder
    for item in os.listdir(folder):
        item_path = os.path.join(folder, item)
        if os.path.isfile(item_path) and item.lower().endswith('.mp4'):
            current_files.add(item_path)
            file_name = os.path.basename(item_path)
            current_hash = get_file_hash(item_path)
            # Only queue for upload if it hasn't been uploaded or has changed
            if not (item_path in state and state[item_path].get('content_hash') == current_hash):
                state[item_path] = {
                    'file_path': item_path,
                    'file_name': file_name,
                    'last_check': datetime.now().isoformat()
                }
                files_to_upload.append(item_path)
                print(f"Queued for upload (main folder): {file_name}")
            else:
                print(f"No changes in (main folder): {file_name}")
    
    # Now, check each subfolder
    for item in os.listdir(folder):
        # Skip excluded folders at top level
        if any(excluded in item.lower() for excluded in EXCLUDED_FOLDERS):
            print(f"Skipping excluded folder: {item}")
            continue
            
        subfolder_path = os.path.join(folder, item)
        if not os.path.isdir(subfolder_path):
            continue
        
        print(f"Checking subfolder: {item}")
        mp4_files = find_mp4_files_in_subfolder(subfolder_path)
        if not mp4_files:
            print(f"No MP4 file found in: {item}")
            continue
        
        for mp4_file in mp4_files:
            current_files.add(mp4_file)
            file_name = os.path.basename(mp4_file)
            current_hash = get_file_hash(mp4_file)
            
            if not (mp4_file in state and state[mp4_file].get('content_hash') == current_hash):
                state[mp4_file] = {
                    'file_path': mp4_file,
                    'file_name': file_name,
                    'last_check': datetime.now().isoformat()
                }
                files_to_upload.append(mp4_file)
                print(f"Queued for upload (subfolder): {file_name}")
            else:
                print(f"No changes in: {file_name}")
    
    # Remove state entries for files that no longer exist
    removed_files = set(state.keys()) - current_files
    for file in removed_files:
        print(f"Removing state for deleted file: {file}")
        del state[file]
    
    return files_to_upload

def check_and_upload():
    """
    Scan the directory and upload new/modified MP4 files.
    """
    print(f"\n[{datetime.now()}] Starting folder scan in: {FOLDER_TO_WATCH}")
    state = load_state()
    files_to_upload = scan_folder(FOLDER_TO_WATCH, state)
    
    if files_to_upload:
        service = get_drive_service()
        print(f"\nFound {len(files_to_upload)} new/updated file(s) to upload:")
        for mp4_file in files_to_upload:
            try:
                upload_file(service, mp4_file, state)
            except Exception as e:
                print(f"Error uploading {mp4_file}: {str(e)}")
        
        save_state(state)
    else:
        print("No new or updated files to upload")

# ---------------------------
# Scheduler Setup
# ---------------------------
def main():
    check_and_upload()
    schedule.every(1).minutes.do(check_and_upload)
    
    print("Folder monitor is running. Press Ctrl+C to exit.")
    try:
        while True:
            next_run = schedule.next_run()
            now = datetime.now()
            if next_run:
                sleep_duration = (next_run - now).total_seconds()
                if sleep_duration > 0:
                    time.sleep(sleep_duration)
            schedule.run_pending()
    except KeyboardInterrupt:
        print("Exiting...")

if __name__ == '__main__':
    main()
