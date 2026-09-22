#!/usr/bin/env python3
"""
Social Media Content Processor - Web UI Backend with Real Database Integration
Flask API server that uses the actual migrated database instead of mock data
"""

import os
import sys
import json
import asyncio
import threading
import time
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import logging

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from system.new_database import NewDatabaseManager
from system.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Initialize database manager
db_manager = NewDatabaseManager()

# Global variables
active_tasks = {}

class DatabaseAPI:
    def __init__(self):
        self.db_manager = db_manager
        self.initialized = False
    
    async def initialize(self):
        """Initialize database connection"""
        if not self.initialized:
            await self.db_manager.initialize()
            self.initialized = True
    
    def format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    async def get_urls_from_file(self):
        """Load URLs from actual urls.txt file"""
        try:
            urls_file = Path("../urls.txt")
            if not urls_file.exists():
                return []
            
            with open(urls_file, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip()]
            
            return urls
        except Exception as e:
            logger.error(f"Error loading URLs: {e}")
            return []
    
    async def get_downloaded_videos(self):
        """Get videos from file system for transcription (assets/downloads/videos)"""
        try:
            # Scan videos directory for downloaded videos
            videos_dir = Path("../assets/downloads/videos")
            if not videos_dir.exists():
                return []
            
            # Get all available thumbnails for matching
            thumbnails_dir = Path("../assets/downloads/thumbnails")
            available_thumbnails = set()
            if thumbnails_dir.exists():
                for thumb_file in thumbnails_dir.rglob("*.webp"):
                    available_thumbnails.add(thumb_file.stem)
                for thumb_file in thumbnails_dir.rglob("*.jpg"):
                    available_thumbnails.add(thumb_file.stem)
            
            videos = []
            for video_file in videos_dir.rglob("*.mp4"):
                try:
                    filename = video_file.name
                    video_id = filename.split('_')[-1].replace('.mp4', '') if '_' in filename else filename.replace('.mp4', '')
                    
                    # Check for matching thumbnail by exact filename match
                    thumbnail_base = filename.replace('.mp4', '')
                    thumbnail_exists = thumbnail_base in available_thumbnails
                    
                    # Try .webp first, then .jpg
                    thumbnail_filename = None
                    if thumbnail_exists:
                        # Check for exact match first
                        if f"{thumbnail_base}.webp" in [f.name for f in thumbnails_dir.glob("*.webp")]:
                            thumbnail_filename = f"{thumbnail_base}.webp"
                        elif f"{thumbnail_base}.jpg" in [f.name for f in thumbnails_dir.glob("*.jpg")]:
                            thumbnail_filename = f"{thumbnail_base}.jpg"
                        else:
                            # If no exact match, try to find the first available thumbnail with the same base name
                            # This handles cases where there are multiple versions (01_, 02_, etc.)
                            for thumb_file in thumbnails_dir.glob(f"{thumbnail_base.split('_')[0]}_*_{thumbnail_base.split('_')[-1]}.webp"):
                                thumbnail_filename = thumb_file.name
                                break
                            if not thumbnail_filename:
                                for thumb_file in thumbnails_dir.glob(f"{thumbnail_base.split('_')[0]}_*_{thumbnail_base.split('_')[-1]}.jpg"):
                                    thumbnail_filename = thumb_file.name
                                    break
                    
                    # Get file size
                    file_size = video_file.stat().st_size
                    
                    # Check if video is already transcribed by looking in database
                    transcription_status = 'PENDING'
                    transcript = ''
                    try:
                        await self.initialize()
                        video_data = await self.db_manager.get_video_transcript_by_filename(filename)
                        if video_data and video_data.get('transcription_status') == 'COMPLETED':
                            transcription_status = 'COMPLETED'
                            transcript = video_data.get('transcription_text', '')
                    except:
                        pass  # If database check fails, default to PENDING
                    
                    videos.append({
                        'id': video_id,
                        'title': filename.replace('_', ' ').replace('.mp4', '').title(),
                        'filename': filename,
                        'duration': 'Unknown',
                        'size': self.format_file_size(file_size),
                        'status': 'Ready for Transcription',
                        'transcriptionStatus': transcription_status,
                        'thumbnail': f'/thumbnails/{thumbnail_filename}' if thumbnail_filename else 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgZmlsbD0iI2YwZjBmMCIvPjx0ZXh0IHg9IjUwIiB5PSI1MCIgZm9udC1mYW1pbHk9IkFyaWFsIiBmb250LXNpemU9IjEyIiBmaWxsPSIjNjY2IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSI+Tm8gSW1hZ2U8L3RleHQ+PC9zdmc+',
                        'created_at': datetime.fromtimestamp(video_file.stat().st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                        'transcript': transcript,
                        'processingTime': 'N/A'
                    })
                except Exception as e:
                    logger.error(f"Error processing video file {video_file}: {e}")
                    continue
            
            return videos
        except Exception as e:
            logger.error(f"Error getting videos for transcription: {e}")
            return []
    
    async def get_finished_videos(self):
        """Get finished videos from file system for upload (since they're manually edited)"""
        try:
            # Scan finished videos directory for manually edited videos
            finished_dir = Path("../assets/finished_videos")
            if not finished_dir.exists():
                return []
            
            # Get all available thumbnails for matching
            thumbnails_dir = Path("../assets/downloads/thumbnails")
            available_thumbnails = set()
            if thumbnails_dir.exists():
                for thumb_file in thumbnails_dir.rglob("*.webp"):
                    available_thumbnails.add(thumb_file.stem)
                for thumb_file in thumbnails_dir.rglob("*.jpg"):
                    available_thumbnails.add(thumb_file.stem)
            
            videos = []
            for video_file in finished_dir.rglob("*.mp4"):
                try:
                    filename = video_file.name
                    video_id = filename.split('_')[-1].replace('.mp4', '') if '_' in filename else filename.replace('.mp4', '')
                    
                    # Check for matching thumbnail by exact filename match
                    thumbnail_base = filename.replace('.mp4', '')
                    thumbnail_exists = thumbnail_base in available_thumbnails
                    
                    # Try .webp first, then .jpg
                    thumbnail_filename = None
                    if thumbnail_exists:
                        # Check for exact match first
                        if f"{thumbnail_base}.webp" in [f.name for f in thumbnails_dir.glob("*.webp")]:
                            thumbnail_filename = f"{thumbnail_base}.webp"
                        elif f"{thumbnail_base}.jpg" in [f.name for f in thumbnails_dir.glob("*.jpg")]:
                            thumbnail_filename = f"{thumbnail_base}.jpg"
                        else:
                            # If no exact match, try to find the first available thumbnail with the same base name
                            # This handles cases where there are multiple versions (01_, 02_, etc.)
                            for thumb_file in thumbnails_dir.glob(f"{thumbnail_base.split('_')[0]}_*_{thumbnail_base.split('_')[-1]}.webp"):
                                thumbnail_filename = thumb_file.name
                                break
                            if not thumbnail_filename:
                                for thumb_file in thumbnails_dir.glob(f"{thumbnail_base.split('_')[0]}_*_{thumbnail_base.split('_')[-1]}.jpg"):
                                    thumbnail_filename = thumb_file.name
                                    break
                    
                    # Get file size
                    file_size = video_file.stat().st_size
                    
                    # Check upload status from database
                    # Since we're scanning the folder, we know the video exists locally
                    # Now check if it has been uploaded to determine the status
                    upload_status = 'EDITED_LOCAL'  # Default: folder scanned, video found locally
                    gdrive_status = 'PENDING'
                    aiwaverider_status = 'PENDING'
                    
                    try:
                        await self.initialize()
                        # Check if video exists in upload_tracking table
                        upload_records = await self.db_manager.get_upload_tracking_by_video_id(video_id)
                        if upload_records:
                            for record in upload_records:
                                if record.get('file_type') == 'video':
                                    gdrive_status = record.get('gdrive_upload_status', 'PENDING')
                                    aiwaverider_status = record.get('aiwaverider_upload_status', 'PENDING')
                                    
                                    # Determine overall status based on upload records
                                    if gdrive_status == 'COMPLETED' and aiwaverider_status == 'COMPLETED':
                                        upload_status = 'EDITED_UPLOADED'  # Uploaded to both platforms
                                    elif gdrive_status == 'COMPLETED' or aiwaverider_status == 'COMPLETED':
                                        upload_status = 'EDITED_PARTIAL'   # Uploaded to one platform
                                    else:
                                        upload_status = 'EDITED_LOCAL'     # Not uploaded to any platform
                                    break
                        # If no upload records found, status remains 'EDITED_LOCAL'
                        # This means: folder scanned + video found locally + not uploaded
                    except Exception as e:
                        logger.error(f"Error checking upload status for {filename}: {e}")
                        # On error, assume EDITED_LOCAL (folder scanned, video found locally)
                    
                    videos.append({
                        'id': video_id,
                        'title': filename.replace('_', ' ').replace('.mp4', '').title(),
                        'filename': filename,
                        'duration': 'Unknown',
                        'size': self.format_file_size(file_size),
                        'uploadStatus': upload_status,
                        'gdriveStatus': gdrive_status,
                        'aiwaveriderStatus': aiwaverider_status,
                        'thumbnail': f'/thumbnails/{thumbnail_filename}' if thumbnail_filename else 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgZmlsbD0iI2YwZjBmMCIvPjx0ZXh0IHg9IjUwIiB5PSI1MCIgZm9udC1mYW1pbHk9IkFyaWFsIiBmb250LXNpemU9IjEyIiBmaWxsPSIjNjY2IiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSI+Tm8gSW1hZ2U8L3RleHQ+PC9zdmc+',
                        'path': str(video_file),
                        'thumbnailPath': f"../assets/downloads/thumbnails/{thumbnail_filename}" if thumbnail_filename else None,
                        'created_at': datetime.fromtimestamp(video_file.stat().st_ctime).strftime('%Y-%m-%d %H:%M:%S')
                    })
                except Exception as e:
                    logger.error(f"Error processing video file {video_file}: {e}")
                    continue
            
            return videos
        except Exception as e:
            logger.error(f"Error getting finished videos: {e}")
            return []
    
    async def get_thumbnails(self):
        """Get thumbnails for upload"""
        try:
            thumbnails_dir = Path("../assets/downloads/thumbnails")
            if not thumbnails_dir.exists():
                return []
            
            thumbnails = []
            # Get all image files (.webp, .jpg, .jpeg, .png)
            for thumbnail_file in thumbnails_dir.rglob("*"):
                if thumbnail_file.suffix.lower() in ['.webp', '.jpg', '.jpeg', '.png']:
                    try:
                        stat = thumbnail_file.stat()
                        # Extract video ID from filename
                        video_id = thumbnail_file.stem.split('__')[-1] if '__' in thumbnail_file.stem else thumbnail_file.stem
                        
                        # Check upload status from database
                        # Since we're scanning the folder, we know the thumbnail exists locally
                        # Now check if it has been uploaded to determine the status
                        upload_status = 'LOCAL'  # Default: folder scanned, thumbnail found locally
                        gdrive_status = 'PENDING'
                        aiwaverider_status = 'PENDING'
                        
                        try:
                            await self.initialize()
                            # Check if thumbnail exists in upload_tracking table
                            upload_records = await self.db_manager.get_upload_tracking_by_video_id(video_id)
                            if upload_records:
                                for record in upload_records:
                                    if record.get('file_type') == 'thumbnail':
                                        gdrive_status = record.get('gdrive_upload_status', 'PENDING')
                                        aiwaverider_status = record.get('aiwaverider_upload_status', 'PENDING')
                                        
                                        # Determine overall status based on upload records
                                        if gdrive_status == 'COMPLETED' and aiwaverider_status == 'COMPLETED':
                                            upload_status = 'UPLOADED'  # Uploaded to both platforms
                                        elif gdrive_status == 'COMPLETED' or aiwaverider_status == 'COMPLETED':
                                            upload_status = 'PARTIAL'   # Uploaded to one platform
                                        else:
                                            upload_status = 'LOCAL'     # Not uploaded to any platform
                                        break
                            # If no upload records found, status remains 'LOCAL'
                            # This means: folder scanned + thumbnail found locally + not uploaded
                        except Exception as e:
                            logger.error(f"Error checking upload status for thumbnail {thumbnail_file.name}: {e}")
                            # On error, assume LOCAL (folder scanned, thumbnail found locally)
                        
                        thumbnails.append({
                            'id': video_id,
                            'filename': thumbnail_file.name,
                            'size': self.format_file_size(stat.st_size),
                            'uploadStatus': upload_status,
                            'gdriveStatus': gdrive_status,
                            'aiwaveriderStatus': aiwaverider_status,
                            'path': str(thumbnail_file),
                            'thumbnail': f'/thumbnails/{thumbnail_file.name}'
                        })
                    except Exception as e:
                        logger.error(f"Error processing thumbnail file {thumbnail_file}: {e}")
                        continue
            
            return thumbnails
        except Exception as e:
            logger.error(f"Error getting thumbnails: {e}")
            return []
    
    async def get_system_status(self):
        """Get system status from database"""
        try:
            await self.initialize()
            
            # Get counts from database
            video_count = await self.db_manager.get_video_count()
            transcript_count = await self.db_manager.get_transcript_count()
            
            return {
                "database": "connected",
                "gpu": "available",
                "videos_processed": video_count,
                "transcripts_created": transcript_count,
                "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "database": "error",
                "gpu": "unknown",
                "videos_processed": 0,
                "transcripts_created": 0,
                "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

# Initialize API
api = DatabaseAPI()

# API Routes
@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory('.', filename)

@app.route('/api/urls', methods=['GET'])
def get_urls():
    """Get URLs from file"""
    try:
        urls = asyncio.run(api.get_urls_from_file())
        return jsonify({"success": True, "urls": urls})
    except Exception as e:
        logger.error(f"Error getting URLs: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/urls', methods=['POST'])
def add_url():
    """Add URL to file"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({"success": False, "error": "No URL provided"})
        
        # Add URL to file
        with open('urls.txt', 'a', encoding='utf-8') as f:
            f.write(f"{url}\n")
        
        return jsonify({"success": True, "message": "URL added successfully"})
    except Exception as e:
        logger.error(f"Error adding URL: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/videos', methods=['GET'])
def get_videos():
    """Get videos for transcription"""
    try:
        videos = asyncio.run(api.get_downloaded_videos())
        return jsonify({"success": True, "videos": videos})
    except Exception as e:
        logger.error(f"Error getting videos: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/finished-videos', methods=['GET'])
def get_finished_videos():
    """Get finished videos ready for upload"""
    try:
        videos = asyncio.run(api.get_finished_videos())
        return jsonify({"success": True, "videos": videos})
    except Exception as e:
        logger.error(f"Error getting finished videos: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/thumbnails', methods=['GET'])
def get_thumbnails():
    """Get thumbnails for upload"""
    try:
        thumbnails = asyncio.run(api.get_thumbnails())
        return jsonify({"success": True, "thumbnails": thumbnails})
    except Exception as e:
        logger.error(f"Error getting thumbnails: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/upload-thumbnails', methods=['POST'])
def upload_thumbnails():
    """Upload selected thumbnails to both Google Drive and AIWaverider"""
    try:
        data = request.get_json()
        thumbnail_ids = data.get('thumbnail_ids', [])
        
        if not thumbnail_ids:
            return jsonify({"success": False, "error": "No thumbnails selected"})
        
        # Start thumbnail upload in background
        task_id = f"thumbnails_{int(time.time())}"
        thread = threading.Thread(target=start_thumbnail_upload, args=(task_id, thumbnail_ids))
        thread.daemon = True
        thread.start()
        
        return jsonify({"success": True, "task_id": task_id, "message": "Thumbnail upload started"})
    except Exception as e:
        logger.error(f"Error starting thumbnail upload: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get system status"""
    try:
        status = asyncio.run(api.get_system_status())
        return jsonify({"success": True, "status": status})
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/thumbnails/<filename>')
def get_thumbnail(filename):
    """Serve thumbnail images"""
    try:
        thumbnails_dir = Path("../assets/downloads/thumbnails")
        thumbnail_path = thumbnails_dir / filename

        if thumbnail_path.exists():
            return send_from_directory(str(thumbnails_dir), filename)
        else:
            # Return SVG data URI instead of serving a file
            svg_data = '''<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
                <rect width="100" height="100" fill="#f0f0f0"/>
                <text x="50" y="50" font-family="Arial" font-size="12" fill="#666" text-anchor="middle" dy=".3em">No Image</text>
            </svg>'''
            from flask import Response
            return Response(svg_data, mimetype='image/svg+xml')
    except Exception as e:
        logger.error(f"Error serving thumbnail {filename}: {e}")
        # Return SVG data URI for errors too
        svg_data = '''<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
            <rect width="100" height="100" fill="#f0f0f0"/>
            <text x="50" y="50" font-family="Arial" font-size="12" fill="#666" text-anchor="middle" dy=".3em">Error</text>
        </svg>'''
        from flask import Response
        return Response(svg_data, mimetype='image/svg+xml')

# Real download endpoint with video processor
@app.route('/api/download', methods=['POST'])
def start_download():
    """Real download process using video processor"""
    try:
        data = request.get_json()
        urls = data.get('urls', [])
        
        if not urls:
            return jsonify({"success": False, "error": "No URLs provided"})
        
        if len(urls) > 10:  # Increased limit for web UI
            return jsonify({"success": False, "error": "Maximum 10 videos per run"})
        
        # Start real download process in background
        task_id = f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        thread = threading.Thread(target=start_real_download, args=(task_id, urls))
        thread.daemon = True
        thread.start()
        
        return jsonify({"success": True, "taskId": task_id, "message": "Download process started"})
    except Exception as e:
        logger.error(f"Error starting download: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/transcribe', methods=['POST'])
def start_transcribe():
    """Mock transcription process"""
    try:
        data = request.get_json()
        video_ids = data.get('videoIds', [])
        
        task_id = f"transcribe_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        active_tasks[task_id] = {
            "status": "running",
            "progress": 0,
            "message": "Starting transcription process..."
        }
        
        return jsonify({"success": True, "taskId": task_id})
    except Exception as e:
        logger.error(f"Error starting transcription: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/upload', methods=['POST'])
def start_upload():
    """Mock upload process"""
    try:
        data = request.get_json()
        video_ids = data.get('videoIds', [])
        
        task_id = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        active_tasks[task_id] = {
            "status": "running",
            "progress": 0,
            "message": "Starting upload process..."
        }
        
        return jsonify({"success": True, "taskId": task_id})
    except Exception as e:
        logger.error(f"Error starting upload: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/progress/<task_id>', methods=['GET'])
def get_progress(task_id):
    """Get progress for a specific task"""
    try:
        if task_id in active_tasks:
            task = active_tasks[task_id]
            
            # For real tasks, return actual progress
            if task["status"] in ["processing", "running"]:
                # Simulate gradual progress for running tasks
                if task["progress"] < 90:
                    task["progress"] += 5
                    if task["progress"] > 90:
                        task["progress"] = 90
            elif task["status"] == "completed":
                task["progress"] = 100
            
            return jsonify(task)
        else:
            return jsonify({"status": "not_found", "error": "Task not found"})
    except Exception as e:
        logger.error(f"Error getting progress: {e}")
        return jsonify({"status": "error", "error": str(e)})

def start_real_download(task_id, urls):
    """Background function to download videos using real video processor"""
    try:
        # Initialize database in the thread
        asyncio.run(db_manager.initialize())
        
        # Import video processor
        from core.processors.video_processor import VideoProcessor
        
        # Initialize video processor
        video_processor = VideoProcessor()
        asyncio.run(video_processor.initialize())
        
        # Update task status
        active_tasks[task_id] = {
            "status": "processing",
            "progress": 0,
            "message": "Starting video download...",
            "items": []
        }
        
        # Process URLs with real video processor
        active_tasks[task_id]["message"] = f"Downloading {len(urls)} videos..."
        active_tasks[task_id]["progress"] = 10
        
        # Use the real video processor (this includes LinkedIn support!)
        success = asyncio.run(video_processor.process_urls(urls))
        
        # Update final status
        if success:
            active_tasks[task_id] = {
                "status": "completed",
                "progress": 100,
                "message": f"Successfully downloaded {len(urls)} videos!",
                "items": []
            }
        else:
            active_tasks[task_id] = {
                "status": "error",
                "progress": 100,
                "message": "Download completed with some errors",
                "items": []
            }
            
    except Exception as e:
        active_tasks[task_id] = {
            "status": "error",
            "progress": 0,
            "message": f"Error: {str(e)}",
            "items": []
        }

def start_thumbnail_upload(task_id, thumbnail_ids):
    """Background function to upload selected thumbnails"""
    try:
        # Initialize database in the thread
        asyncio.run(db_manager.initialize())
        
        # Import processors
        from core.processors.upload_processor import UploadProcessor
        from core.processors.aiwaverider_processor import AIWaveriderProcessor
        
        # Initialize processors
        upload_processor = UploadProcessor()
        aiwaverider_processor = AIWaveriderProcessor()
        
        # Initialize processors
        asyncio.run(upload_processor.initialize())
        asyncio.run(aiwaverider_processor.initialize())
        
        # Update task status
        active_tasks[task_id] = {
            "status": "processing",
            "progress": 0,
            "message": "Starting thumbnail upload...",
            "items": []
        }
        
        # Get thumbnail files from IDs
        thumbnails_dir = Path("../assets/downloads/thumbnails")
        thumbnail_files = []
        
        for thumbnail_id in thumbnail_ids:
            # Find thumbnail file by ID (assuming ID is the filename)
            for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                file_path = thumbnails_dir / f"{thumbnail_id}{ext}"
                if file_path.exists():
                    thumbnail_files.append(str(file_path))
                    break
        
        if not thumbnail_files:
            active_tasks[task_id] = {
                "status": "error",
                "progress": 0,
                "message": "No thumbnail files found",
                "items": []
            }
            return
        
        # Upload to Google Drive
        active_tasks[task_id]["message"] = "Uploading to Google Drive..."
        active_tasks[task_id]["progress"] = 25
        
        gdrive_success = asyncio.run(upload_processor.process_thumbnails())
        
        # Upload to AIWaverider
        active_tasks[task_id]["message"] = "Uploading to AIWaverider Drive..."
        active_tasks[task_id]["progress"] = 75
        
        aiwaverider_success = asyncio.run(aiwaverider_processor.upload_all())
        
        # Update final status
        if gdrive_success and aiwaverider_success:
            active_tasks[task_id] = {
                "status": "completed",
                "progress": 100,
                "message": "Thumbnail upload completed successfully!",
                "items": []
            }
        else:
            active_tasks[task_id] = {
                "status": "error",
                "progress": 100,
                "message": "Thumbnail upload completed with errors",
                "items": []
            }
            
    except Exception as e:
        active_tasks[task_id] = {
            "status": "error",
            "progress": 0,
            "message": f"Error: {str(e)}",
            "items": []
        }

if __name__ == '__main__':
    try:
        print("🚀 Starting Social Media Content Processor Web UI (Database Mode)...")
        print("📱 Open your browser and go to: http://localhost:5000")
        print("🛑 Press Ctrl+C to stop the server")
        print("🗄️ Using REAL DATABASE: social_media.db")
        
        # Run with better error handling
        app.run(
            host='0.0.0.0', 
            port=5000, 
            debug=False,  # Disable debug mode to prevent crashes
            threaded=True,  # Enable threading for better stability
            use_reloader=False  # Disable auto-reload to prevent issues
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        import traceback
        traceback.print_exc()
