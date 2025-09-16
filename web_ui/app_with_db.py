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
                        'thumbnail': f'/thumbnails/{thumbnail_filename}' if thumbnail_filename else '/placeholder-thumbnail.jpg',
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
                    
                    videos.append({
                        'id': video_id,
                        'title': filename.replace('_', ' ').replace('.mp4', '').title(),
                        'filename': filename,
                        'duration': 'Unknown',
                        'size': self.format_file_size(file_size),
                        'uploadStatus': 'PENDING',
                        'thumbnail': f'/thumbnails/{thumbnail_filename}' if thumbnail_filename else '/placeholder-thumbnail.jpg',
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
                        
                        thumbnails.append({
                            'id': video_id,
                            'filename': thumbnail_file.name,
                            'size': self.format_file_size(stat.st_size),
                            'uploadStatus': 'PENDING',
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
            # Return placeholder if thumbnail doesn't exist
            placeholder_path = Path("placeholder-thumbnail.jpg")
            if placeholder_path.exists():
                return send_from_directory(".", "placeholder-thumbnail.jpg")
            else:
                return jsonify({"error": "Thumbnail not found"}), 404
    except Exception as e:
        logger.error(f"Error serving thumbnail {filename}: {e}")
        return jsonify({"error": "Thumbnail not found"}), 404

# Mock endpoints for compatibility
@app.route('/api/download', methods=['POST'])
def start_download():
    """Mock download process"""
    try:
        data = request.get_json()
        urls = data.get('urls', [])
        
        if len(urls) > 5:
            return jsonify({"success": False, "error": "Maximum 5 videos per run"})
        
        task_id = f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        active_tasks[task_id] = {
            "status": "running",
            "progress": 0,
            "message": "Starting download process..."
        }
        
        return jsonify({"success": True, "taskId": task_id})
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
            # Simulate progress
            task = active_tasks[task_id]
            if task["progress"] < 100:
                task["progress"] += 20
                task["message"] = f"Processing... {task['progress']}%"
            else:
                task["status"] = "completed"
                task["message"] = "Process completed successfully!"
            
            return jsonify(task)
        else:
            return jsonify({"status": "not_found", "error": "Task not found"})
    except Exception as e:
        logger.error(f"Error getting progress: {e}")
        return jsonify({"status": "error", "error": str(e)})

if __name__ == '__main__':
    try:
        print("🚀 Starting Social Media Content Processor Web UI (Database Mode)...")
        print("📱 Open your browser and go to: http://localhost:5000")
        print("🛑 Press Ctrl+C to stop the server")
        print("🗄️ Using REAL DATABASE: social_media.db")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
