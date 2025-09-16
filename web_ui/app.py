#!/usr/bin/env python3
"""
Social Media Content Processor - Web UI Backend
Flask API server for the web interface
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

# Add the parent directory to the path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrator import SocialMediaOrchestrator
from system.new_database import new_db_manager
from system.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Global variables
orchestrator = None
db_manager = None
active_tasks = {}

class WebAPI:
    def __init__(self):
        self.orchestrator = None
        self.db_manager = None
        self.initialize_components()
    
    def initialize_components(self):
        """Initialize the orchestrator and database manager"""
        try:
            self.db_manager = new_db_manager
            asyncio.run(self.db_manager.initialize())
            
            self.orchestrator = SocialMediaOrchestrator()
            logger.info("Components initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing components: {e}")
            raise
    
    async def get_urls_from_file(self):
        """Load URLs from urls.txt file"""
        try:
            urls_file = Path("data/urls.txt")
            if not urls_file.exists():
                return []
            
            with open(urls_file, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            return urls
        except Exception as e:
            logger.error(f"Error loading URLs: {e}")
            return []
    
    async def get_downloaded_videos(self):
        """Get list of downloaded videos from database"""
        try:
            videos = await self.db_manager.get_all_videos()
            return [
                {
                    'id': video.get('video_id', ''),
                    'title': video.get('title', 'Unknown'),
                    'filename': video.get('filename', ''),
                    'duration': video.get('duration', 'Unknown'),
                    'size': self.format_file_size(video.get('file_size', 0)),
                    'status': video.get('transcription_status', 'PENDING'),
                    'transcriptionStatus': video.get('transcription_status', 'PENDING'),
                    'thumbnail': self.get_thumbnail_path(video.get('thumbnail_path', '')),
                    'created_at': video.get('created_at', '')
                }
                for video in videos
            ]
        except Exception as e:
            logger.error(f"Error getting downloaded videos: {e}")
            return []
    
    async def get_finished_videos(self):
        """Get list of finished videos from assets/finished_videos/"""
        try:
            finished_videos_dir = Path("assets/finished_videos")
            if not finished_videos_dir.exists():
                return []
            
            videos = []
            for video_file in finished_videos_dir.rglob("*.mp4"):
                try:
                    stat = video_file.stat()
                    videos.append({
                        'id': str(video_file),
                        'title': video_file.stem,
                        'filename': video_file.name,
                        'duration': 'Unknown',
                        'size': self.format_file_size(stat.st_size),
                        'uploadStatus': 'PENDING',
                        'thumbnail': self.get_thumbnail_path(str(video_file)),
                        'path': str(video_file)
                    })
                except Exception as e:
                    logger.error(f"Error processing video file {video_file}: {e}")
                    continue
            
            return videos
        except Exception as e:
            logger.error(f"Error getting finished videos: {e}")
            return []
    
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
    
    def get_thumbnail_path(self, thumbnail_path):
        """Get thumbnail path or return placeholder"""
        if thumbnail_path and Path(thumbnail_path).exists():
            return f"/thumbnails/{Path(thumbnail_path).name}"
        return "/placeholder-thumbnail.jpg"
    
    async def start_download_process(self, urls):
        """Start download process for selected URLs"""
        try:
            # Limit to 5 videos as per requirements
            if len(urls) > 5:
                return {"success": False, "error": "Maximum 5 videos per run"}
            
            # Create a task ID
            task_id = f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Start download in background thread
            def run_download():
                try:
                    asyncio.run(self.orchestrator.process_urls(urls))
                    active_tasks[task_id] = {"status": "completed", "progress": 100}
                except Exception as e:
                    logger.error(f"Download process error: {e}")
                    active_tasks[task_id] = {"status": "failed", "error": str(e)}
            
            thread = threading.Thread(target=run_download)
            thread.start()
            
            active_tasks[task_id] = {"status": "running", "progress": 0}
            
            return {"success": True, "taskId": task_id}
        except Exception as e:
            logger.error(f"Error starting download process: {e}")
            return {"success": False, "error": str(e)}
    
    async def start_transcribe_process(self, video_ids):
        """Start transcription process for selected videos"""
        try:
            task_id = f"transcribe_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Start transcription in background thread
            def run_transcribe():
                try:
                    # This would integrate with the existing transcription system
                    # For now, we'll simulate the process
                    active_tasks[task_id] = {"status": "running", "progress": 50}
                    # TODO: Implement actual transcription logic
                    active_tasks[task_id] = {"status": "completed", "progress": 100}
                except Exception as e:
                    logger.error(f"Transcription process error: {e}")
                    active_tasks[task_id] = {"status": "failed", "error": str(e)}
            
            thread = threading.Thread(target=run_transcribe)
            thread.start()
            
            active_tasks[task_id] = {"status": "running", "progress": 0}
            
            return {"success": True, "taskId": task_id}
        except Exception as e:
            logger.error(f"Error starting transcription process: {e}")
            return {"success": False, "error": str(e)}
    
    async def start_upload_process(self, video_ids):
        """Start upload process for selected videos"""
        try:
            task_id = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Start upload in background thread
            def run_upload():
                try:
                    # This would integrate with the existing upload system
                    # For now, we'll simulate the process
                    active_tasks[task_id] = {"status": "running", "progress": 50}
                    # TODO: Implement actual upload logic
                    active_tasks[task_id] = {"status": "completed", "progress": 100}
                except Exception as e:
                    logger.error(f"Upload process error: {e}")
                    active_tasks[task_id] = {"status": "failed", "error": str(e)}
            
            thread = threading.Thread(target=run_upload)
            thread.start()
            
            active_tasks[task_id] = {"status": "running", "progress": 0}
            
            return {"success": True, "taskId": task_id}
        except Exception as e:
            logger.error(f"Error starting upload process: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_task_progress(self, task_id):
        """Get progress for a specific task"""
        try:
            task = active_tasks.get(task_id, {"status": "not_found"})
            
            if task["status"] == "running":
                # Simulate progress updates
                task["progress"] = min(task.get("progress", 0) + 10, 90)
            
            return task
        except Exception as e:
            logger.error(f"Error getting task progress: {e}")
            return {"status": "error", "error": str(e)}
    
    async def get_system_status(self):
        """Get overall system status"""
        try:
            # Check database connection
            db_status = "connected" if self.db_manager else "disconnected"
            
            # Check Google Sheets (simplified)
            sheets_status = "connected"  # TODO: Implement actual check
            
            # Check AIWaverider (simplified)
            aiwaverider_status = "connected"  # TODO: Implement actual check
            
            # Check GPU (simplified)
            gpu_status = "available"  # TODO: Implement actual check
            
            return {
                "database": db_status,
                "google_sheets": sheets_status,
                "aiwaverider": aiwaverider_status,
                "gpu": gpu_status
            }
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "database": "error",
                "google_sheets": "error",
                "aiwaverider": "error",
                "gpu": "error"
            }

# Initialize the API
api = WebAPI()

# API Routes
@app.route('/')
def index():
    """Serve the main HTML file"""
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    """Serve static files"""
    return send_from_directory('.', filename)

@app.route('/api/urls', methods=['GET'])
def get_urls():
    """Get URLs from urls.txt file"""
    try:
        urls = asyncio.run(api.get_urls_from_file())
        return jsonify({"success": True, "urls": urls})
    except Exception as e:
        logger.error(f"Error getting URLs: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/videos', methods=['GET'])
def get_videos():
    """Get downloaded videos"""
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

@app.route('/api/download', methods=['POST'])
def start_download():
    """Start download process"""
    try:
        data = request.get_json()
        urls = data.get('urls', [])
        
        result = asyncio.run(api.start_download_process(urls))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error starting download: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/transcribe', methods=['POST'])
def start_transcribe():
    """Start transcription process"""
    try:
        data = request.get_json()
        video_ids = data.get('videoIds', [])
        
        result = asyncio.run(api.start_transcribe_process(video_ids))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error starting transcription: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/upload', methods=['POST'])
def start_upload():
    """Start upload process"""
    try:
        data = request.get_json()
        video_ids = data.get('videoIds', [])
        
        result = asyncio.run(api.start_upload_process(video_ids))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error starting upload: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/progress/<task_id>', methods=['GET'])
def get_progress(task_id):
    """Get progress for a specific task"""
    try:
        progress = asyncio.run(api.get_task_progress(task_id))
        return jsonify(progress)
    except Exception as e:
        logger.error(f"Error getting progress: {e}")
        return jsonify({"status": "error", "error": str(e)})

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
        thumbnail_dir = Path("assets/downloads/thumbnails")
        return send_from_directory(thumbnail_dir, filename)
    except Exception as e:
        logger.error(f"Error serving thumbnail {filename}: {e}")
        return jsonify({"error": "Thumbnail not found"}), 404

if __name__ == '__main__':
    try:
        print("🚀 Starting Social Media Content Processor Web UI...")
        print("📱 Open your browser and go to: http://localhost:5000")
        print("🛑 Press Ctrl+C to stop the server")
        
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=True,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)
