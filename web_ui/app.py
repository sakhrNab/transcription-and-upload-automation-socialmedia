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
import re
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
            # Get the project root directory (parent of web_ui)
            project_root = Path(__file__).parent.parent
            urls_file = project_root / "data" / "urls.txt"
            if not urls_file.exists():
                return []
            
            with open(urls_file, 'r', encoding='utf-8') as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            return urls
        except Exception as e:
            logger.error(f"Error loading URLs: {e}")
            return []
    
    async def get_downloaded_videos(self):
        """Get videos from file system for transcription (assets/downloads/videos)"""
        try:
            # Get the project root directory (parent of web_ui)
            project_root = Path(__file__).parent.parent
            # Scan videos directory for downloaded videos
            videos_dir = project_root / "assets" / "downloads" / "videos"
            if not videos_dir.exists():
                logger.warning(f"Videos directory not found: {videos_dir}")
                return []
            
            # Get all available thumbnails for matching
            thumbnails_dir = project_root / "assets" / "downloads" / "thumbnails"
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
                    # Extract video ID from filename
                    # Format can be: 01_nick_saraev_DPgT4fVD8BK.mp4 or 01_sabrina_ramonov__DN_yYVTiQvz.mp4
                    # Try double underscore first, then fall back to extracting YouTube ID pattern
                    if '__' in filename:
                        # Format: 01_name__VIDEO_ID.mp4
                        video_id = filename.split('__')[-1].replace('.mp4', '')
                    else:
                        # Format: 01_name_VIDEO_ID.mp4 - extract the last part (YouTube ID)
                        # YouTube IDs are typically 11 characters, alphanumeric with hyphens/underscores
                        name_parts = filename.replace('.mp4', '').split('_')
                        # The video ID is usually the last part after the number prefix
                        # Try to find a part that looks like a YouTube ID (11 chars or longer alphanumeric)
                        video_id = name_parts[-1] if len(name_parts) > 1 else filename.replace('.mp4', '')
                        # If it's still the full filename, try to extract just the ID part
                        if video_id == filename.replace('.mp4', ''):
                            # Look for pattern like DPgT4fVD8BK (11 chars, alphanumeric)
                            id_match = re.search(r'([A-Za-z0-9_-]{11,})$', filename.replace('.mp4', ''))
                            if id_match:
                                video_id = id_match.group(1)
                            else:
                                video_id = filename.replace('.mp4', '')
                    
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
                        # Try multiple lookup strategies
                        video_data = None
                        db_status = 'PENDING'
                        
                        logger.info(f"🔍 Looking up video: filename='{filename}', extracted video_id='{video_id}'")
                        
                        # Strategy 1: Try exact filename match
                        video_data = await self.db_manager.get_video_transcript_by_filename(filename)
                        if video_data:
                            db_status = video_data.get('transcription_status', 'PENDING')
                            db_video_id = video_data.get('video_id', '')
                            transcription_status = db_status
                            if db_status == 'COMPLETED':
                                transcript = video_data.get('transcription_text', '')
                            logger.info(f"✅ Video '{filename}': Found by filename (DB video_id='{db_video_id}'), status = {db_status}")
                        else:
                            # Strategy 2: Try by video_id
                            logger.info(f"⚠️ No video found by filename '{filename}', trying by video_id '{video_id}'")
                            try:
                                video_data = await self.db_manager.get_video_transcript_by_id(video_id)
                                if video_data:
                                    db_status = video_data.get('transcription_status', 'PENDING')
                                    db_filename = video_data.get('filename', '')
                                    transcription_status = db_status
                                    if db_status == 'COMPLETED':
                                        transcript = video_data.get('transcription_text', '')
                                    logger.info(f"✅ Video '{filename}' (ID: {video_id}): Found by video_id (DB filename='{db_filename}'), status = {db_status}")
                                else:
                                    # Strategy 3: Try partial filename match (in case DB has different format)
                                    logger.info(f"⚠️ No video found by video_id '{video_id}', trying partial filename match")
                                    # Get all videos and search for matching filename
                                    all_videos = await self.db_manager.get_all_videos()
                                    logger.info(f"🔍 Searching through {len(all_videos)} videos in database...")
                                    found_match = False
                                    for db_video in all_videos:
                                        db_filename = db_video.get('filename', '')
                                        db_video_id = db_video.get('video_id', '')
                                        db_status_check = db_video.get('transcription_status', 'PENDING')
                                        
                                        # Check if filenames match (case-insensitive, ignore path differences)
                                        if filename.lower() == db_filename.lower() or filename in db_filename or db_filename in filename:
                                            db_status = db_status_check
                                            transcription_status = db_status
                                            if db_status == 'COMPLETED':
                                                transcript = db_video.get('transcription_text', '')
                                            logger.info(f"✅ Video '{filename}': Found by partial filename match (DB filename='{db_filename}', video_id='{db_video_id}'), status = {db_status}")
                                            video_data = db_video
                                            found_match = True
                                            break
                                        # Also check if video_id matches (case-insensitive)
                                        # Check if extracted video_id (e.g., "DOgcMQLiBSz") is contained in DB video_id (e.g., "01_sirio_berati_DOgcMQLiBSz")
                                        elif video_id.lower() == db_video_id.lower() or video_id.lower() in db_video_id.lower() or db_video_id.lower() in video_id.lower():
                                            db_status = db_status_check
                                            transcription_status = db_status
                                            if db_status == 'COMPLETED':
                                                transcript = db_video.get('transcription_text', '')
                                            logger.info(f"✅ Video '{filename}' (ID: {video_id}): Found by video_id partial match (DB filename='{db_filename}', video_id='{db_video_id}'), status = {db_status}")
                                            video_data = db_video
                                            found_match = True
                                            break
                                    
                                    if not found_match:
                                        logger.warning(f"❌ No video found in DB for filename '{filename}' or ID '{video_id}' - defaulting to PENDING")
                                        # Log all video_ids and filenames for debugging (first 10)
                                        sample_videos = [(v.get('video_id', ''), v.get('filename', ''), v.get('transcription_status', '')) for v in all_videos[:10]]
                                        logger.info(f"📋 Sample DB entries (first 10): {sample_videos}")
                                        # Also log what we're looking for vs what's in DB
                                        logger.info(f"🔍 Looking for video_id '{video_id}' in DB. Available video_ids: {[v.get('video_id', '') for v in all_videos[:10]]}")
                            except Exception as e2:
                                logger.warning(f"❌ Error looking up by video_id {video_id}: {e2}")
                    except Exception as e:
                        logger.warning(f"❌ Error checking transcription status for {filename}: {e}")
                        # Default to PENDING if check fails
                    
                    # Determine display status
                    if transcription_status == 'COMPLETED':
                        display_status = 'COMPLETED'
                        status_text = 'Transcribed'
                    else:
                        display_status = transcription_status
                        status_text = 'Ready for Transcription'
                    
                    videos.append({
                        'id': video_id,
                        'title': filename.replace('_', ' ').replace('.mp4', '').title(),
                        'filename': filename,
                        'file_path': str(video_file),  # Full path for transcription
                        'duration': 'Unknown',
                        'size': self.format_file_size(file_size),
                        'status': status_text,
                        'transcriptionStatus': display_status,  # This is what the frontend uses
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
        """Get list of finished videos from assets/finished_videos/"""
        try:
            # Get the project root directory (parent of web_ui)
            project_root = Path(__file__).parent.parent
            finished_videos_dir = project_root / "assets" / "finished_videos"
            if not finished_videos_dir.exists():
                logger.warning(f"Finished videos directory not found: {finished_videos_dir}")
                return []
            
            # Get all available thumbnails for matching
            thumbnails_dir = project_root / "assets" / "downloads" / "thumbnails"
            available_thumbnails = set()
            if thumbnails_dir.exists():
                for thumb_file in thumbnails_dir.rglob("*.webp"):
                    available_thumbnails.add(thumb_file.stem)
                for thumb_file in thumbnails_dir.rglob("*.jpg"):
                    available_thumbnails.add(thumb_file.stem)
            
            videos = []
            for video_file in finished_videos_dir.rglob("*.mp4"):
                try:
                    filename = video_file.name
                    # Extract video ID from filename
                    video_id = filename.split('__')[-1].replace('.mp4', '') if '__' in filename else filename.replace('.mp4', '')
                    
                    # Check for matching thumbnail
                    thumbnail_base = filename.replace('.mp4', '')
                    thumbnail_exists = thumbnail_base in available_thumbnails
                    
                    # Try .webp first, then .jpg
                    thumbnail_filename = None
                    if thumbnail_exists:
                        if f"{thumbnail_base}.webp" in [f.name for f in thumbnails_dir.glob("*.webp")]:
                            thumbnail_filename = f"{thumbnail_base}.webp"
                        elif f"{thumbnail_base}.jpg" in [f.name for f in thumbnails_dir.glob("*.jpg")]:
                            thumbnail_filename = f"{thumbnail_base}.jpg"
                        else:
                            for thumb_file in thumbnails_dir.glob(f"{thumbnail_base.split('_')[0]}_*_{thumbnail_base.split('_')[-1]}.webp"):
                                thumbnail_filename = thumb_file.name
                                break
                            if not thumbnail_filename:
                                for thumb_file in thumbnails_dir.glob(f"{thumbnail_base.split('_')[0]}_*_{thumbnail_base.split('_')[-1]}.jpg"):
                                    thumbnail_filename = thumb_file.name
                                    break
                    
                    stat = video_file.stat()
                    videos.append({
                        'id': video_id,
                        'title': filename.replace('_', ' ').replace('.mp4', '').title(),
                        'filename': filename,
                        'duration': 'Unknown',
                        'size': self.format_file_size(stat.st_size),
                        'uploadStatus': 'PENDING',
                        'thumbnail': f'/thumbnails/{thumbnail_filename}' if thumbnail_filename else '/placeholder-thumbnail.jpg',
                        'path': str(video_file)  # Full path for upload
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
        """Start transcription process for selected videos from assets/downloads/videos/"""
        try:
            task_id = f"transcribe_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Start transcription in background thread
            def run_transcribe():
                try:
                    asyncio.run(self._transcribe_videos_real(video_ids, task_id))
                except Exception as e:
                    logger.error(f"Transcription process error: {e}")
                    active_tasks[task_id] = {"status": "failed", "error": str(e)}
            
            thread = threading.Thread(target=run_transcribe)
            thread.start()
            
            active_tasks[task_id] = {
                "status": "running", 
                "progress": 0,
                "items": [{"title": f"Video {vid}", "status": "pending", "progress": 0} for vid in video_ids]
            }
            
            return {"success": True, "taskId": task_id}
        except Exception as e:
            logger.error(f"Error starting transcription process: {e}")
            return {"success": False, "error": str(e)}
    
    async def _transcribe_videos_real(self, video_ids, task_id):
        """Real transcription implementation"""
        try:
            # Get all videos from filesystem
            all_videos = await self.get_downloaded_videos()
            
            # Map video_ids to video objects with file paths
            videos_to_transcribe = []
            skipped_count = 0
            for video_id in video_ids:
                video = next((v for v in all_videos if v.get('id') == video_id), None)
                if video and video.get('file_path'):
                    # Check if already transcribed
                    if video.get('transcriptionStatus') == 'COMPLETED':
                        filename = video.get('filename', video_id)
                        logger.info(f"⏭️  SKIP: Video '{filename}' (ID: {video_id}) is already transcribed - skipping transcription")
                        print(f"⏭️  SKIP: Video '{filename}' (ID: {video_id}) is already transcribed - skipping transcription")
                        skipped_count += 1
                        continue
                    videos_to_transcribe.append(video)
            
            if skipped_count > 0:
                logger.info(f"📊 Skipped {skipped_count} video(s) that were already transcribed")
                print(f"📊 Skipped {skipped_count} video(s) that were already transcribed")
            
            if not videos_to_transcribe:
                if skipped_count > 0:
                    logger.info(f"✅ All {skipped_count} selected video(s) were already transcribed - nothing to process")
                    print(f"✅ All {skipped_count} selected video(s) were already transcribed - nothing to process")
                    active_tasks[task_id] = {
                        "status": "completed", 
                        "progress": 100, 
                        "items": [],
                        "message": f"All {skipped_count} video(s) were already transcribed - skipped",
                        "skipped": skipped_count
                    }
                else:
                    active_tasks[task_id] = {"status": "completed", "progress": 100, "items": []}
                return
            
            # Initialize processors if needed
            if not self.orchestrator.video_processor.initialized:
                await self.orchestrator.video_processor.initialize()
            if not self.orchestrator.sheets_processor.initialized:
                await self.orchestrator.sheets_processor.initialize()
            if not self.orchestrator.transcripts_sheets_processor.initialized:
                await self.orchestrator.transcripts_sheets_processor.initialize()
            
            successful = 0
            failed = 0
            sheets_errors = []
            
            for i, video in enumerate(videos_to_transcribe):
                try:
                    file_path = video.get('file_path')
                    filename = video.get('filename')
                    video_id = video.get('id')
                    
                    if not os.path.exists(file_path):
                        logger.error(f"Video file not found: {file_path}")
                        failed += 1
                        continue
                    
                    # Update progress
                    progress = int((i / len(videos_to_transcribe)) * 90)
                    active_tasks[task_id] = {
                        "status": "running",
                        "progress": progress,
                        "items": [
                            {"title": v.get('filename', 'Unknown'), "status": "processing" if j == i else "pending", "progress": progress if j == i else 0}
                            for j, v in enumerate(videos_to_transcribe)
                        ]
                    }
                    
                    logger.info(f"Transcribing video {i+1}/{len(videos_to_transcribe)}: {filename}")
                    
                    # Step 1: Convert to audio
                    audio_path = await self.orchestrator.video_processor._convert_video_to_audio(file_path, i+1)
                    if not audio_path or not os.path.exists(audio_path):
                        logger.error(f"Audio conversion failed for {filename}")
                        failed += 1
                        continue
                    
                    # Step 2: Transcribe
                    transcript = await self.orchestrator.video_processor._transcribe_audio_with_whisper(audio_path, i+1)
                    if not transcript:
                        logger.error(f"Transcription failed for {filename}")
                        failed += 1
                        continue
                    
                    # Step 3: Generate smart name
                    smart_name = await self.orchestrator.video_processor._generate_smart_video_name(
                        video.get('title', ''),
                        '',  # Description not available from filesystem
                        i+1
                    )
                    
                    # Step 4: Get or create video data for database update
                    video_data = await self.db_manager.get_video_transcript_by_filename(filename)
                    if not video_data:
                        # Also try by video_id
                        video_data = await self.db_manager.get_video_transcript_by_id(video_id)
                    
                    if not video_data:
                        # Create minimal video data if not in database
                        logger.info(f"Creating new video entry for '{filename}' with video_id '{video_id}'")
                        video_data = {
                            'video_id': video_id,
                            'filename': filename,
                            'title': video.get('title', ''),
                            'description': '',
                            'thumbnail_file_path': ''
                        }
                    else:
                        # Ensure video_id is set correctly
                        if not video_data.get('video_id'):
                            video_data['video_id'] = video_id
                        logger.info(f"Updating existing video entry: filename='{filename}', video_id='{video_data.get('video_id', video_id)}'")
                    
                    # Step 5: Update database with transcription
                    # Use the video_id from video_data if available, otherwise use extracted one
                    db_video_id = video_data.get('video_id', video_id)
                    await self.orchestrator.video_processor._update_video_transcription(
                        db_video_id,
                        transcript,
                        smart_name,
                        file_path,
                        video_data.get('thumbnail_file_path', ''),
                        video_data
                    )
                    
                    # Step 6: Clean up audio file
                    try:
                        if os.path.exists(audio_path):
                            os.remove(audio_path)
                    except Exception as e:
                        logger.warning(f"Error cleaning up audio file: {e}")
                    
                    # Step 7: Update sheets (optional - skip on error)
                    sheets_success = False
                    sheets_error = None
                    try:
                        sheets_success = await self.orchestrator.sheets_processor.update_master_sheet()
                        transcripts_success = await self.orchestrator.transcripts_sheets_processor.update_transcripts_sheet()
                        if not sheets_success or not transcripts_success:
                            sheets_error = "Sheets update returned False"
                    except Exception as e:
                        sheets_error = str(e)
                        logger.error(f"Sheets update failed (non-fatal): {e}")
                    
                    if sheets_error:
                        sheets_errors.append(f"{filename}: {sheets_error}")
                    
                    successful += 1
                    logger.info(f"Successfully transcribed {filename}")
                    
                except Exception as e:
                    logger.error(f"Error transcribing video {video.get('filename', 'Unknown')}: {e}")
                    failed += 1
                    continue
            
            # Final status
            result = {
                "status": "completed" if successful > 0 else "failed",
                "progress": 100,
                "items": [
                    {"title": v.get('filename', 'Unknown'), "status": "completed", "progress": 100}
                    for v in videos_to_transcribe[:successful]
                ],
                "transcribed": successful,
                "failed": failed,
                "skipped": skipped_count
            }
            
            if skipped_count > 0:
                result["message"] = f"Transcribed {successful} video(s), skipped {skipped_count} already transcribed video(s)"
                logger.info(f"📊 Transcription Summary: {successful} transcribed, {failed} failed, {skipped_count} skipped")
                print(f"📊 Transcription Summary: {successful} transcribed, {failed} failed, {skipped_count} skipped")
            
            if sheets_errors:
                result["sheets_error"] = "; ".join(sheets_errors)
                result["sheets_updated"] = False
            else:
                result["sheets_updated"] = True
            
            active_tasks[task_id] = result
            
        except Exception as e:
            logger.error(f"Error in transcription process: {e}")
            active_tasks[task_id] = {"status": "failed", "error": str(e)}
    
    async def start_upload_process(self, video_ids):
        """Start upload process for selected videos from assets/finished_videos/"""
        try:
            task_id = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Start upload in background thread
            def run_upload():
                try:
                    asyncio.run(self._upload_videos_real(video_ids, task_id))
                except Exception as e:
                    logger.error(f"Upload process error: {e}")
                    active_tasks[task_id] = {"status": "failed", "error": str(e)}
            
            thread = threading.Thread(target=run_upload)
            thread.start()
            
            active_tasks[task_id] = {
                "status": "running",
                "progress": 0,
                "items": [{"title": f"Video {vid}", "status": "pending", "progress": 0} for vid in video_ids]
            }
            
            return {"success": True, "taskId": task_id}
        except Exception as e:
            logger.error(f"Error starting upload process: {e}")
            return {"success": False, "error": str(e)}
    
    async def _upload_videos_real(self, video_ids, task_id):
        """Real upload implementation"""
        try:
            # Get all finished videos
            all_videos = await self.get_finished_videos()
            
            # Map video_ids to video objects with file paths
            videos_to_upload = []
            for video_id in video_ids:
                video = next((v for v in all_videos if v.get('id') == video_id), None)
                if video and video.get('path'):
                    videos_to_upload.append(video)
            
            if not videos_to_upload:
                active_tasks[task_id] = {"status": "completed", "progress": 100, "items": []}
                return
            
            # Initialize processors if needed
            if not self.orchestrator.upload_processor.initialized:
                await self.orchestrator.upload_processor.initialize()
            if not self.orchestrator.aiwaverider_processor.initialized:
                await self.orchestrator.aiwaverider_processor.initialize()
            if not self.orchestrator.sheets_processor.initialized:
                await self.orchestrator.sheets_processor.initialize()
            if not self.orchestrator.transcripts_sheets_processor.initialized:
                await self.orchestrator.transcripts_sheets_processor.initialize()
            
            successful = 0
            failed = 0
            sheets_errors = []
            
            for i, video in enumerate(videos_to_upload):
                try:
                    video_path = video.get('path')
                    filename = video.get('filename')
                    video_id = video.get('id')
                    
                    if not os.path.exists(video_path):
                        logger.error(f"Video file not found: {video_path}")
                        failed += 1
                        continue
                    
                    # Update progress
                    progress = int((i / len(videos_to_upload)) * 90)
                    active_tasks[task_id] = {
                        "status": "running",
                        "progress": progress,
                        "items": [
                            {"title": v.get('filename', 'Unknown'), "status": "processing" if j == i else "pending", "progress": progress if j == i else 0}
                            for j, v in enumerate(videos_to_upload)
                        ]
                    }
                    
                    logger.info(f"Uploading video {i+1}/{len(videos_to_upload)}: {filename}")
                    
                    # Check if already uploaded
                    is_uploaded = await self.db_manager.is_file_uploaded(video_id, 'video')
                    if is_uploaded:
                        logger.info(f"Video {filename} already uploaded, skipping")
                        successful += 1
                        continue
                    
                    upload_success = True
                    
                    # 1. Upload to Google Drive
                    drive_service = self.orchestrator.upload_processor._get_drive_service()
                    if not drive_service:
                        logger.error(f"Failed to initialize Google Drive service for {filename}")
                        upload_success = False
                    else:
                        drive_result = await self.orchestrator.upload_processor._upload_video_file(
                            drive_service, video_path, {}
                        )
                        if not drive_result:
                            logger.error(f"Google Drive upload failed for {filename}")
                            upload_success = False
                        else:
                            logger.info(f"Google Drive upload successful for {filename}")
                    
                    # 2. Upload to AIWaverider
                    aiwaverider_result = await self.orchestrator.aiwaverider_processor._upload_video_to_aiwaverider(video_path)
                    if not aiwaverider_result:
                        logger.error(f"AIWaverider upload failed for {filename}")
                        upload_success = False
                    else:
                        logger.info(f"AIWaverider upload successful for {filename}")
                    
                    if not upload_success:
                        failed += 1
                        continue
                    
                    # 3. Update sheets (optional - skip on error)
                    sheets_success = False
                    sheets_error = None
                    try:
                        sheets_success = await self.orchestrator.sheets_processor.update_master_sheet()
                        transcripts_success = await self.orchestrator.transcripts_sheets_processor.update_transcripts_sheet()
                        if not sheets_success or not transcripts_success:
                            sheets_error = "Sheets update returned False"
                    except Exception as e:
                        sheets_error = str(e)
                        logger.error(f"Sheets update failed (non-fatal): {e}")
                    
                    if sheets_error:
                        sheets_errors.append(f"{filename}: {sheets_error}")
                    
                    successful += 1
                    logger.info(f"Successfully uploaded {filename}")
                    
                except Exception as e:
                    logger.error(f"Error uploading video {video.get('filename', 'Unknown')}: {e}")
                    failed += 1
                    continue
            
            # Final status
            result = {
                "status": "completed" if successful > 0 else "failed",
                "progress": 100,
                "items": [
                    {"title": v.get('filename', 'Unknown'), "status": "completed", "progress": 100}
                    for v in videos_to_upload[:successful]
                ]
            }
            
            if sheets_errors:
                result["sheets_error"] = "; ".join(sheets_errors)
                result["sheets_updated"] = False
            else:
                result["sheets_updated"] = True
            
            active_tasks[task_id] = result
            
        except Exception as e:
            logger.error(f"Error in upload process: {e}")
            active_tasks[task_id] = {"status": "failed", "error": str(e)}
    
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
    
    async def get_thumbnails(self):
        """Get thumbnails for upload"""
        try:
            # Get the project root directory (parent of web_ui)
            project_root = Path(__file__).parent.parent
            thumbnails_dir = project_root / "assets" / "downloads" / "thumbnails"
            if not thumbnails_dir.exists():
                logger.warning(f"Thumbnails directory not found: {thumbnails_dir}")
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
    
    async def upload_thumbnails(self, thumbnail_ids):
        """Upload selected thumbnails to Google Drive and AIWaverider"""
        try:
            # Get all thumbnails
            all_thumbnails = await self.get_thumbnails()
            
            # Map thumbnail_ids to thumbnail objects with file paths
            thumbnails_to_upload = []
            for thumbnail_id in thumbnail_ids:
                thumbnail = next((t for t in all_thumbnails if t.get('id') == thumbnail_id), None)
                if thumbnail and thumbnail.get('path'):
                    thumbnails_to_upload.append(thumbnail)
            
            if not thumbnails_to_upload:
                return {"success": False, "error": "No thumbnails found to upload"}
            
            # Initialize processors if needed
            if not self.orchestrator.upload_processor.initialized:
                await self.orchestrator.upload_processor.initialize()
            if not self.orchestrator.aiwaverider_processor.initialized:
                await self.orchestrator.aiwaverider_processor.initialize()
            if not self.orchestrator.sheets_processor.initialized:
                await self.orchestrator.sheets_processor.initialize()
            
            successful = 0
            failed = 0
            sheets_errors = []
            
            for thumbnail in thumbnails_to_upload:
                try:
                    thumbnail_path = thumbnail.get('path')
                    filename = thumbnail.get('filename')
                    
                    if not os.path.exists(thumbnail_path):
                        logger.error(f"Thumbnail file not found: {thumbnail_path}")
                        failed += 1
                        continue
                    
                    logger.info(f"Uploading thumbnail: {filename}")
                    
                    upload_success = True
                    
                    # 1. Upload to Google Drive
                    drive_service = self.orchestrator.upload_processor._get_drive_service()
                    if not drive_service:
                        logger.error(f"Failed to initialize Google Drive service for {filename}")
                        upload_success = False
                    else:
                        # Load state for thumbnail upload
                        state = await self.orchestrator.upload_processor._load_thumbnail_state()
                        drive_result = await self.orchestrator.upload_processor._upload_thumbnail_file(
                            drive_service, thumbnail_path, state
                        )
                        if not drive_result:
                            logger.error(f"Google Drive upload failed for {filename}")
                            upload_success = False
                        else:
                            logger.info(f"Google Drive upload successful for {filename}")
                            # Save state
                            await self.orchestrator.upload_processor._save_thumbnail_state(state)
                    
                    # 2. Upload to AIWaverider
                    aiwaverider_result = await self.orchestrator.aiwaverider_processor._upload_thumbnail_to_aiwaverider(thumbnail_path)
                    if not aiwaverider_result:
                        logger.error(f"AIWaverider upload failed for {filename}")
                        upload_success = False
                    else:
                        logger.info(f"AIWaverider upload successful for {filename}")
                    
                    if not upload_success:
                        failed += 1
                        continue
                    
                    # 3. Update sheets (optional - skip on error)
                    sheets_success = False
                    sheets_error = None
                    try:
                        sheets_success = await self.orchestrator.sheets_processor.update_master_sheet()
                        if not sheets_success:
                            sheets_error = "Sheets update returned False"
                    except Exception as e:
                        sheets_error = str(e)
                        logger.error(f"Sheets update failed (non-fatal): {e}")
                    
                    if sheets_error:
                        sheets_errors.append(f"{filename}: {sheets_error}")
                    
                    successful += 1
                    logger.info(f"Successfully uploaded thumbnail {filename}")
                    
                except Exception as e:
                    logger.error(f"Error uploading thumbnail {thumbnail.get('filename', 'Unknown')}: {e}")
                    failed += 1
                    continue
            
            result = {
                "success": successful > 0,
                "uploaded": successful,
                "failed": failed
            }
            
            if sheets_errors:
                result["sheets_error"] = "; ".join(sheets_errors)
                result["sheets_updated"] = False
            else:
                result["sheets_updated"] = True
            
            return result
            
        except Exception as e:
            logger.error(f"Error in thumbnail upload process: {e}")
            return {"success": False, "error": str(e)}
    
    async def save_urls_to_file(self, urls):
        """Save URLs to urls.txt file"""
        try:
            # Get the project root directory (parent of web_ui)
            project_root = Path(__file__).parent.parent
            urls_file = project_root / "data" / "urls.txt"
            urls_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Read existing URLs to avoid duplicates
            existing_urls = set()
            if urls_file.exists():
                with open(urls_file, 'r', encoding='utf-8') as f:
                    existing_urls = {line.strip() for line in f if line.strip() and not line.startswith('#')}
            
            # Append new URLs
            new_urls_count = 0
            with open(urls_file, 'a', encoding='utf-8') as f:
                for url in urls:
                    url = url.strip()
                    if url and url not in existing_urls:
                        f.write(f"{url}\n")
                        existing_urls.add(url)
                        new_urls_count += 1
            
            return {"success": True, "added": new_urls_count, "total": len(existing_urls)}
        except Exception as e:
            logger.error(f"Error saving URLs: {e}")
            return {"success": False, "error": str(e)}
    
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

@app.route('/api/urls', methods=['POST'])
def add_urls():
    """Save URLs to urls.txt file"""
    try:
        data = request.get_json()
        urls = data.get('urls', [])
        
        if not urls:
            return jsonify({"success": False, "error": "No URLs provided"})
        
        result = asyncio.run(api.save_urls_to_file(urls))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error saving URLs: {e}")
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

@app.route('/api/thumbnails', methods=['GET'])
def get_thumbnails():
    """Get thumbnails for upload"""
    try:
        thumbnails = asyncio.run(api.get_thumbnails())
        return jsonify({"success": True, "thumbnails": thumbnails})
    except Exception as e:
        logger.error(f"Error getting thumbnails: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/thumbnails/upload', methods=['POST'])
def upload_thumbnails():
    """Upload selected thumbnails"""
    try:
        data = request.get_json()
        thumbnail_ids = data.get('thumbnailIds', [])
        
        if not thumbnail_ids:
            return jsonify({"success": False, "error": "No thumbnails selected"})
        
        result = asyncio.run(api.upload_thumbnails(thumbnail_ids))
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error uploading thumbnails: {e}")
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
        # Get the project root directory (parent of web_ui)
        project_root = Path(__file__).parent.parent
        thumbnail_dir = project_root / "assets" / "downloads" / "thumbnails"
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
            use_reloader=False,  # Disable auto-reloader to avoid Windows socket issues
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)
