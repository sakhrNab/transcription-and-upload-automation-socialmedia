#!/usr/bin/env python3
"""
Social Media Content Processor - Web UI Backend (Simplified Version)
Flask API server for the web interface - Testing version without complex imports
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Global variables for testing
active_tasks = {}
mock_data = {
    'urls': [
        'https://instagram.com/p/example1',
        'https://instagram.com/p/example2',
        'https://instagram.com/p/example3',
        'https://tiktok.com/@user/video/123',
        'https://youtube.com/watch?v=example'
    ],
    'videos': [
        {
            'id': 'video_1',
            'title': 'Sample Video 1',
            'filename': 'sample_video_1.mp4',
            'duration': '2:30',
            'size': '15.2 MB',
            'status': 'Downloaded',
            'transcriptionStatus': 'PENDING',
            'thumbnail': '/placeholder-thumbnail.jpg',
            'created_at': '2024-01-15 10:30:00'
        },
        {
            'id': 'video_2',
            'title': 'Sample Video 2',
            'filename': 'sample_video_2.mp4',
            'duration': '1:45',
            'size': '12.8 MB',
            'status': 'Downloaded',
            'transcriptionStatus': 'COMPLETED',
            'thumbnail': '/placeholder-thumbnail.jpg',
            'created_at': '2024-01-15 11:15:00'
        }
    ],
    'finished_videos': [
        {
            'id': 'finished_1',
            'title': 'Finished Video 1',
            'filename': 'finished_video_1.mp4',
            'duration': '3:20',
            'size': '25.6 MB',
            'uploadStatus': 'PENDING',
            'thumbnail': '/placeholder-thumbnail.jpg',
            'path': 'assets/finished_videos/finished_video_1.mp4'
        },
        {
            'id': 'finished_2',
            'title': 'Finished Video 2',
            'filename': 'finished_video_2.mp4',
            'duration': '2:15',
            'size': '18.3 MB',
            'uploadStatus': 'COMPLETED',
            'thumbnail': '/placeholder-thumbnail.jpg',
            'path': 'assets/finished_videos/finished_video_2.mp4'
        }
    ]
}

class MockAPI:
    def __init__(self):
        self.tasks = {}
    
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
                return mock_data['urls']
            
            with open(urls_file, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            return urls
        except Exception as e:
            logger.error(f"Error loading URLs: {e}")
            return mock_data['urls']
    
    async def get_downloaded_videos(self):
        """Get videos from assets/downloads/videos/ for transcription"""
        try:
            videos_dir = Path("../assets/downloads/videos")
            if not videos_dir.exists():
                return mock_data['videos']
            
            # Get all available thumbnails for matching
            thumbnails_dir = Path("../assets/downloads/thumbnails")
            available_thumbnails = set()
            if thumbnails_dir.exists():
                for thumb_file in thumbnails_dir.rglob("*.webp"):
                    available_thumbnails.add(thumb_file.stem)
            
            videos = []
            for video_file in videos_dir.rglob("*.mp4"):
                try:
                    stat = video_file.stat()
                    # Extract video ID from filename (e.g., 01_sabrina_ramonov__DN_yYVTiQvz.mp4 -> DN_yYVTiQvz)
                    video_id = video_file.stem.split('__')[-1] if '__' in video_file.stem else video_file.stem
                    
                    # Check for matching thumbnail by exact filename match
                    thumbnail_exists = video_file.stem in available_thumbnails
                    
                    videos.append({
                        'id': video_id,
                        'title': video_file.stem.replace('_', ' ').title(),
                        'filename': video_file.name,
                        'duration': 'Unknown',
                        'size': self.format_file_size(stat.st_size),
                        'status': 'Ready for Transcription',
                        'transcriptionStatus': 'PENDING',
                        'thumbnail': f'/thumbnails/{video_file.stem}.webp' if thumbnail_exists else '/placeholder-thumbnail.jpg',
                        'created_at': datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
                    })
                except Exception as e:
                    logger.error(f"Error processing video file {video_file}: {e}")
                    continue
            
            return videos
        except Exception as e:
            logger.error(f"Error getting videos for transcription: {e}")
            return mock_data['videos']
    
    async def get_finished_videos(self):
        """Get finished videos from assets/finished_videos/ for upload"""
        try:
            videos_dir = Path("../assets/finished_videos")
            if not videos_dir.exists():
                return mock_data['finished_videos']
            
            # Get all available thumbnails for matching
            thumbnails_dir = Path("../assets/downloads/thumbnails")
            available_thumbnails = set()
            if thumbnails_dir.exists():
                for thumb_file in thumbnails_dir.rglob("*.webp"):
                    available_thumbnails.add(thumb_file.stem)
            
            videos = []
            for video_file in videos_dir.rglob("*.mp4"):
                try:
                    stat = video_file.stat()
                    # Extract video ID from filename (e.g., 01_sabrina_ramonov__DN_yYVTiQvz.mp4 -> DN_yYVTiQvz)
                    video_id = video_file.stem.split('__')[-1] if '__' in video_file.stem else video_file.stem
                    
                    # Check for matching thumbnail by exact filename match
                    thumbnail_exists = video_file.stem in available_thumbnails
                    
                    videos.append({
                        'id': video_id,
                        'title': video_file.stem.replace('_', ' ').title(),
                        'filename': video_file.name,
                        'duration': 'Unknown',
                        'size': self.format_file_size(stat.st_size),
                        'uploadStatus': 'PENDING',
                        'thumbnail': f'/thumbnails/{video_file.stem}.webp' if thumbnail_exists else '/placeholder-thumbnail.jpg',
                        'path': str(video_file),
                        'thumbnailPath': f"../assets/downloads/thumbnails/{video_file.stem}.webp" if thumbnail_exists else None
                    })
                except Exception as e:
                    logger.error(f"Error processing video file {video_file}: {e}")
                    continue
            
            return videos
        except Exception as e:
            logger.error(f"Error getting finished videos: {e}")
            return mock_data['finished_videos']
    
    async def start_download_process(self, urls):
        """Mock download process"""
        if len(urls) > 5:
            return {"success": False, "error": "Maximum 5 videos per run"}
        
        task_id = f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Simulate download process
        def simulate_download():
            import time
            time.sleep(2)  # Simulate download time
            active_tasks[task_id] = {
                "status": "completed", 
                "progress": 100,
                "items": [
                    {"title": url, "status": "completed", "progress": 100}
                    for url in urls
                ]
            }
        
        thread = threading.Thread(target=simulate_download)
        thread.start()
        
        active_tasks[task_id] = {"status": "running", "progress": 0}
        return {"success": True, "taskId": task_id}
    
    async def start_transcribe_process(self, video_ids):
        """Mock transcription process"""
        task_id = f"transcribe_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        def simulate_transcribe():
            import time
            time.sleep(3)  # Simulate transcription time
            active_tasks[task_id] = {
                "status": "completed", 
                "progress": 100,
                "items": [
                    {"title": f"Video {vid}", "status": "completed", "progress": 100}
                    for vid in video_ids
                ]
            }
        
        thread = threading.Thread(target=simulate_transcribe)
        thread.start()
        
        active_tasks[task_id] = {"status": "running", "progress": 0}
        return {"success": True, "taskId": task_id}
    
    async def start_upload_process(self, video_ids):
        """Mock upload process"""
        task_id = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        def simulate_upload():
            import time
            time.sleep(4)  # Simulate upload time
            active_tasks[task_id] = {
                "status": "completed", 
                "progress": 100,
                "items": [
                    {"title": f"Video {vid}", "status": "completed", "progress": 100}
                    for vid in video_ids
                ]
            }
        
        thread = threading.Thread(target=simulate_upload)
        thread.start()
        
        active_tasks[task_id] = {"status": "running", "progress": 0}
        return {"success": True, "taskId": task_id}
    
    async def get_task_progress(self, task_id):
        """Get progress for a specific task"""
        task = active_tasks.get(task_id, {"status": "not_found"})
        
        if task["status"] == "running":
            # Simulate progress updates
            current_progress = task.get("progress", 0)
            if current_progress < 90:
                task["progress"] = min(current_progress + 20, 90)
                task["items"] = [
                    {"title": f"Item {i+1}", "status": "processing", "progress": task["progress"]}
                    for i in range(3)
                ]
        
        return task
    
    async def get_system_status(self):
        """Mock system status"""
        return {
            "database": "connected",
            "google_sheets": "connected", 
            "aiwaverider": "connected",
            "gpu": "available"
        }

# Initialize the mock API
api = MockAPI()

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

@app.route('/api/thumbnails', methods=['GET'])
def get_thumbnails():
    """Get thumbnails for upload"""
    try:
        thumbnails_dir = Path("../assets/downloads/thumbnails")
        if not thumbnails_dir.exists():
            return jsonify({"success": True, "thumbnails": []})
        
        thumbnails = []
        for thumbnail_file in thumbnails_dir.rglob("*.webp"):
            try:
                stat = thumbnail_file.stat()
                # Extract video ID from filename (e.g., 01_sabrina_ramonov__DN_yYVTiQvz.webp -> DN_yYVTiQvz)
                video_id = thumbnail_file.stem.split('__')[-1] if '__' in thumbnail_file.stem else thumbnail_file.stem
                
                thumbnails.append({
                    'id': video_id,
                    'filename': thumbnail_file.name,
                    'size': api.format_file_size(stat.st_size),
                    'uploadStatus': 'PENDING',
                    'path': str(thumbnail_file),
                    'thumbnail': f'/thumbnails/{thumbnail_file.name}'
                })
            except Exception as e:
                logger.error(f"Error processing thumbnail file {thumbnail_file}: {e}")
                continue
        
        return jsonify({"success": True, "thumbnails": thumbnails})
    except Exception as e:
        logger.error(f"Error getting thumbnails: {e}")
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

if __name__ == '__main__':
    try:
        print("🚀 Starting Social Media Content Processor Web UI (Test Mode)...")
        print("📱 Open your browser and go to: http://localhost:5000")
        print("🛑 Press Ctrl+C to stop the server")
        print("🧪 Running in TEST MODE with mock data")
        
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
