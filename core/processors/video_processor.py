#!/usr/bin/env python3
"""
Video Processor
Handles video download, transcription, and processing
Integrates real logic from full-rounded-url-download-transcription.py
"""

import asyncio
import os
import sys
import re
import time
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.processors.base_processor import BaseProcessor
from system.new_database import new_db_manager as db_manager
from system.config import settings

# Core libraries
import yt_dlp
import ffmpeg
import whisper
import requests
import torch
import gc
import psutil
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AlreadyDownloadedException(Exception):
    """Exception raised when video is already downloaded"""
    def __init__(self, message: str, file_path: str = None, video_data: dict = None):
        super().__init__(message)
        self.file_path = file_path
        self.video_data = video_data

class VideoProcessor(BaseProcessor):
    """Handles video processing and transcription with real logic"""
    
    def __init__(self):
        super().__init__("VideoProcessor")
        self.processed_count = 0
        self.failed_count = 0
        
        # Get project root directory (parent of core/processors/)
        project_root = Path(__file__).parent.parent.parent
        
        # Configuration - use absolute paths based on project root
        self.video_output_dir = str(project_root / "assets" / "downloads" / "videos")
        self.audio_output_dir = str(project_root / "assets" / "downloads" / "audio")
        self.thumbnails_dir = str(project_root / "assets" / "downloads" / "thumbnails")
        self.transcripts_dir = str(project_root / "assets" / "downloads" / "transcripts")
        
        # Processing configuration from settings
        self.whisper_model = settings.whisper_model
        self.max_audio_duration = settings.max_audio_duration
        self.chunk_duration = settings.chunk_duration
        self.keep_audio_files = settings.keep_audio_files
        
        # OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set. Please add it to your .env file.")
        self.openai_client = OpenAI(api_key=api_key)
        
        # Parallel processing configuration
        self.max_concurrent_videos = settings.max_concurrent_videos  # 0 = auto-detect
    
    async def initialize(self) -> bool:
        """Initialize video processor"""
        try:
            self.log_step("Initializing video processor")
            
            # Check GPU availability
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                cuda_version = torch.version.cuda
                self.log_step(f"GPU available: {gpu_name} (CUDA {cuda_version})")
            else:
                self.log_step("No GPU detected, will use CPU for transcription")
            
            # Ensure required directories exist
            os.makedirs(self.video_output_dir, exist_ok=True)
            os.makedirs(self.audio_output_dir, exist_ok=True)
            os.makedirs(self.thumbnails_dir, exist_ok=True)
            os.makedirs(self.transcripts_dir, exist_ok=True)
            
            self.initialized = True
            self.status = "ready"
            self.log_step("Video processor initialized successfully")
            return True
            
        except Exception as e:
            self.log_error("Failed to initialize video processor", e)
            return False
    
    async def process(self, urls: List[str]) -> bool:
        """Main processing method - alias for process_urls"""
        return await self.process_urls(urls)
    
    async def process_urls(self, urls: List[str]) -> bool:
        """Process a list of URLs for video download and transcription with parallel processing"""
        try:
            self.log_step(f"Processing {len(urls)} URLs")
            self.status = "processing"
            
            # Load existing videos from database to check for already downloaded videos
            existing_videos = await db_manager.get_all_videos()
            existing_urls = {video.get('url', '') for video in existing_videos if video.get('url')}
            existing_video_ids = {video.get('video_id', '') for video in existing_videos if video.get('video_id')}
            
            self.log_step(f"Found {len(existing_videos)} existing videos in database")
            self.log_step(f"Existing URLs: {len(existing_urls)}")
            self.log_step(f"Existing video IDs: {len(existing_video_ids)}")
            
            # Filter out already processed URLs (by URL or video ID)
            new_urls = []
            skipped_count = 0
            
            for url in urls:
                video_id = self._extract_video_id(url)
                
                # Check if URL or video ID already exists in database
                if url in existing_urls:
                    self.log_step(f"Skipping already processed video by URL: {url}")
                    skipped_count += 1
                    continue
                elif video_id and video_id in existing_video_ids:
                    self.log_step(f"Skipping already processed video by ID: {video_id}")
                    skipped_count += 1
                    continue
                    
                new_urls.append(url)
            
            if not new_urls:
                self.log_step(f"No new URLs to process - {skipped_count} already processed, {len(urls)} total")
                return True
            
            self.log_step(f"Found {len(new_urls)} new URLs to process ({skipped_count} already processed)")
            
            # Process URLs sequentially (one at a time)
            self.log_step(f"Using sequential processing - videos will be processed one at a time")
            
            # Process each URL sequentially
            results = []
            consecutive_failures = [0]  # Use list to allow modification in retry function
            max_consecutive_failures = 3  # Stop after 3 consecutive failures
            
            for i, url in enumerate(new_urls, 1):
                # Check if we should stop before starting this video
                if consecutive_failures[0] >= max_consecutive_failures:
                    self.log_step(f"Stopping download process after {consecutive_failures[0]} consecutive failures")
                    self.log_step("Moving to upload processing for already downloaded videos")
                    break
                
                try:
                    self.log_step(f"Starting sequential processing for video {i}")
                    success = await self._process_single_video_with_retry(url, i, consecutive_failures, max_consecutive_failures)
                    if success:
                        self.processed_count += 1
                    else:
                        self.failed_count += 1
                        
                    results.append(success)
                except Exception as e:
                    self.log_error(f"Error processing video {i}: {str(e)}")
                    self.failed_count += 1
                    consecutive_failures[0] += 1
                    results.append(False)
            
            self.status = "completed"
            self.log_step(f"Sequential video processing completed: {self.processed_count} successful, {self.failed_count} failed")
            return self.failed_count == 0
            
        except Exception as e:
            self.log_error("Error in process_urls", e)
            self.status = "error"
            return False
    
    def _get_optimal_concurrency(self) -> int:
        """Calculate optimal concurrency based on system resources and GPU availability"""
        if self.max_concurrent_videos > 0:
            return self.max_concurrent_videos
        
        # Auto-detect optimal concurrency
        import psutil
        
        # Base concurrency on CPU cores
        cpu_cores = psutil.cpu_count(logical=False)  # Physical cores
        
        # GPU availability affects optimal concurrency
        if torch.cuda.is_available():
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # GB
            if gpu_memory >= 8:  # High-end GPU
                optimal = min(cpu_cores * 2, 6)  # Up to 6 concurrent with high-end GPU
            elif gpu_memory >= 4:  # Mid-range GPU
                optimal = min(cpu_cores, 4)  # Up to 4 concurrent with mid-range GPU
            else:  # Low-end GPU
                optimal = min(cpu_cores // 2, 2)  # Conservative with low-end GPU
        else:
            # CPU-only processing - more conservative
            optimal = max(1, cpu_cores // 2)
        
        # Ensure minimum of 1 and maximum of 8
        optimal = max(1, min(optimal, 8))
        
        self.log_step(f"Auto-detected optimal concurrency: {optimal} (CPU cores: {cpu_cores}, GPU: {torch.cuda.is_available()})")
        return optimal
    
    async def _process_single_video_with_retry(self, url: str, index: int, consecutive_failures_ref: list, max_consecutive_failures: int) -> bool:
        """Process a single video with retry logic"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    self.log_step(f"Retry attempt {attempt + 1}/{max_retries} for video {index}")
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
                result = await self._process_single_video(url, index)
                if result:
                    consecutive_failures_ref[0] = 0  # Reset on success
                    return True
                else:
                    # Video processing failed, increment consecutive failures
                    consecutive_failures_ref[0] += 1
                    self.log_step(f"Video {index} failed, consecutive failures: {consecutive_failures_ref[0]}")
                    
                    # Check if we should stop after this failure
                    if consecutive_failures_ref[0] >= max_consecutive_failures:
                        self.log_step(f"Stopping download process after {consecutive_failures_ref[0]} consecutive failures")
                        self.log_step("Moving to upload processing for already downloaded videos")
                        return False
                    
                    # Continue to next attempt if we haven't reached max retries
                    if attempt < max_retries - 1:
                        continue
                    else:
                        self.log_step(f"Skipping video {index} after {max_retries} failed attempts")
                        return False
                
            except Exception as e:
                self.log_error(f"Attempt {attempt + 1}/{max_retries} failed for video {index}: {str(e)}")
                # Exception occurred, increment consecutive failures
                consecutive_failures_ref[0] += 1
                self.log_step(f"Video {index} failed with exception, consecutive failures: {consecutive_failures_ref[0]}")
                
                # Check if we should stop after this failure
                if consecutive_failures_ref[0] >= max_consecutive_failures:
                    self.log_step(f"Stopping download process after {consecutive_failures_ref[0]} consecutive failures")
                    self.log_step("Moving to upload processing for already downloaded videos")
                    return False
                
                # Continue to next attempt if we haven't reached max retries
                if attempt < max_retries - 1:
                    continue
                else:
                    self.log_step(f"Skipping video {index} after {max_retries} failed attempts")
                    return False
        
        return False

    async def _process_single_video(self, url: str, index: int) -> bool:
        """Process a single video through the complete pipeline"""
        start_time = time.time()
        
        try:
            self.log_step(f"Starting complete pipeline for video {index}")
            
            # Step 0: Check if already transcribed
            video_id = self._extract_video_id(url)
            if video_id:
                existing = await self._check_existing_transcription(video_id)
                if existing:
                    self.log_step(f"Video {video_id} already transcribed, skipping")
                    return True
            
            # Step 1: Download video and extract metadata
            video_path, metadata, raw_info = await self._download_video_and_metadata(url, index)
            
            # Step 2: Download thumbnail
            thumbnail_path = await self._download_thumbnail(
                metadata.get('thumbnail_url'), 
                metadata.get('video_id'), 
                metadata.get('username'),
                index
            )
            
            # Step 3: Generate smart video name
            generated_name = await self._generate_smart_video_name(
                metadata.get('title', ''), 
                metadata.get('description', ''),
                index
            )
            
            # Step 4: Convert to audio
            audio_path = await self._convert_video_to_audio(video_path, index)
            
            # Step 5: Transcribe
            transcript = await self._transcribe_audio_with_whisper(audio_path, index)
            
            # Step 6: Save transcript as separate file
            if transcript:
                transcript_path = await self._save_transcript_file(transcript, generated_name, metadata, index)
                
                # Step 7: Update database with transcription
                # Ensure all paths are absolute before saving to database
                abs_video_path = os.path.abspath(video_path) if video_path else ''
                abs_audio_path = os.path.abspath(audio_path) if audio_path else ''
                abs_transcript_path = os.path.abspath(transcript_path) if transcript_path else ''
                abs_thumbnail_path = os.path.abspath(thumbnail_path) if thumbnail_path else ''
                
                video_id = metadata.get('video_id', '')
                if video_id:
                    await self._update_video_transcription(
                        video_id, transcript, generated_name, 
                        abs_video_path, abs_thumbnail_path, metadata,
                        abs_audio_path, abs_transcript_path
                    )
                
                self.log_step(f"Complete pipeline successful: {generated_name}")
                return True
            else:
                self.log_error(f"Transcription failed for video {index}")
                return False
                
        except Exception as e:
            self.log_error(f"Error processing video {index}: {str(e)}")
            raise  # Re-raise the exception so retry logic can catch it
        finally:
            processing_time = time.time() - start_time
            self.log_step(f"Video {index} processing completed in {processing_time:.2f}s")
    
    # Real video processing methods from full-rounded script
    
    async def _download_video_and_metadata(self, url: str, index: int) -> tuple[str, dict, dict]:
        """Download video using yt_dlp and extract comprehensive metadata"""
        self.log_step(f"Extracting video information for video {index}")
        
        # Check if this is a YouTube URL
        is_youtube = 'youtube.com' in url or 'youtu.be' in url
        
        # First, extract info without downloading
        # Use YouTube-specific options if needed (per instructions: use ios client for better compatibility)
        if is_youtube:
            info_opts = {
                'quiet': True,
                'extractor_args': {
                    'youtube': {
                        'player_client': ['ios', 'web'],  # Use ios client first (no token needed), fallback to web
                    }
                },
            }
        else:
            info_opts = {'quiet': True}
        
        with yt_dlp.YoutubeDL(info_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                self.log_step(f"Extracted metadata for {info.get('title', 'Unknown')}")
            except Exception as e:
                self.log_error(f"Failed to extract video info: {str(e)}")
                raise Exception(f"Failed to extract video info: {str(e)}")
        
        # Extract and clean metadata
        video_id = info.get('id', 'unknown')
        username = info.get('uploader', info.get('channel', 'unknown'))
        username = re.sub(r'[^\w]+', '_', username.lower()) if username else 'unknown'
        title = info.get('title', video_id)
        description = info.get('description', '')
        
        # Check if already downloaded - use absolute path
        abs_video_output_dir = os.path.abspath(self.video_output_dir)
        if os.path.exists(abs_video_output_dir):
            for file in os.listdir(abs_video_output_dir):
                if video_id in file and file.endswith(('.mp4', '.webm', '.mkv')):
                    full_path = os.path.join(abs_video_output_dir, file)
                    self.log_step(f"Video already downloaded: {file}")
                    metadata = self._extract_comprehensive_metadata(info, full_path)
                    return full_path, metadata, info
        
        # Create filename with sequential numbering
        # Ensure video_output_dir is absolute and exists
        abs_video_output_dir = os.path.abspath(self.video_output_dir)
        os.makedirs(abs_video_output_dir, exist_ok=True)
        
        seq_num = self._get_video_number(abs_video_output_dir, username)
        # Use absolute path for filename template to avoid working directory issues
        filename_template = os.path.join(abs_video_output_dir, f"{seq_num:02d}_{username}_{video_id}.%(ext)s")
        
        self.log_step(f"Starting download: {title}")
        self.log_step(f"Download directory: {abs_video_output_dir}")
        
        # Download configuration - use absolute path
        # Per instructions: yt-dlp -f mp4 for video downloads
        # In Python API: 'format': 'mp4' or 'best[ext=mp4]/best' with fallback
        if is_youtube:
            # YouTube-specific: Use format selector matching instructions (-f mp4)
            # With fallbacks for when mp4 isn't available
            ydl_opts = {
                'outtmpl': filename_template,
                'format': 'mp4/best[ext=mp4]/best',  # Try mp4 first (per instructions), then fallback
                'writesubtitles': False,
                'writeautomaticsub': False,
                'ignoreerrors': True,  # Continue even if some formats fail
                'quiet': True,
                'extractor_args': {
                    'youtube': {
                        'player_client': ['ios', 'web'],  # Use ios client (no token needed), fallback to web
                    }
                },
                'retries': 3,
                'fragment_retries': 3,
            }
        else:
            # Standard options for other platforms
            ydl_opts = {
                'outtmpl': filename_template,
                'format': 'best[ext=mp4]/best',
                'writesubtitles': False,
                'writeautomaticsub': False,
                'ignoreerrors': False,
                'quiet': True
            }
        
        download_start = time.time()
        
        # Try download with format selector, fallback if format not available
        download_success = False
        downloaded_file = None
        
        if is_youtube:
            # Try multiple format selectors in order (matching the instructions approach)
            format_selectors = [
                'mp4',  # Direct mp4 format (matches instructions: -f mp4)
                'best[ext=mp4]/best',  # Best mp4, fallback to best
                'best',  # Any best format
            ]
            
            for format_selector in format_selectors:
                try:
                    ydl_opts['format'] = format_selector
                    self.log_step(f"Trying download with format: {format_selector} (matching instructions: yt-dlp -f mp4)")
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                        # Get the downloaded file path from the successful download
                        downloaded_file = ydl.prepare_filename(info)
                        download_success = True
                        break  # Success, exit loop
                except Exception as e:
                    error_msg = str(e)
                    if 'format is not available' in error_msg or 'Requested format' in error_msg:
                        self.log_step(f"Format '{format_selector}' not available, trying next option...")
                        continue
                    else:
                        # Different error, re-raise it
                        raise
            
            if not download_success:
                raise Exception("Failed to download video with any format selector")
        else:
            # Non-YouTube: use standard download
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                # Get the downloaded file path
                downloaded_file = ydl.prepare_filename(info)
                download_success = True
        
        # Ensure it's an absolute path
        if downloaded_file and not os.path.isabs(downloaded_file):
            downloaded_file = os.path.join(abs_video_output_dir, os.path.basename(downloaded_file))
        
        download_time = time.time() - download_start
        
        # If file not found, try to find it in the correct directory
        if not os.path.exists(downloaded_file):
            # Try with the actual extension from info
            ext = info.get('ext', 'mp4')
            template_file = os.path.join(abs_video_output_dir, f"{seq_num:02d}_{username}_{video_id}.{ext}")
            if os.path.exists(template_file):
                downloaded_file = template_file
            else:
                # Try to find the downloaded file with different extension in the correct directory
                base_name = os.path.join(abs_video_output_dir, f"{seq_num:02d}_{username}_{video_id}")
                for ext in ['.mp4', '.webm', '.mkv', '.mov']:
                    alt_path = base_name + ext
                    if os.path.exists(alt_path):
                        downloaded_file = alt_path
                        break
                else:
                    self.log_error(f"Downloaded file not found. Expected in: {abs_video_output_dir}")
                    self.log_error(f"Tried filename: {downloaded_file}")
                    # List files in directory for debugging
                    if os.path.exists(abs_video_output_dir):
                        files = os.listdir(abs_video_output_dir)
                        self.log_error(f"Files in directory: {files[:10]}")  # Show first 10
                    raise Exception(f"Downloaded file not found in {abs_video_output_dir}")
        
        file_size = os.path.getsize(downloaded_file)
        abs_path = os.path.abspath(downloaded_file)
        self.log_step(f"Downloaded successfully: {os.path.basename(downloaded_file)} ({file_size / (1024*1024):.2f} MB)")
        self.log_step(f"Full file path: {abs_path}")
        
        metadata = self._extract_comprehensive_metadata(info, downloaded_file)
        return downloaded_file, metadata, info
    
    def _extract_comprehensive_metadata(self, info: dict, file_path: str) -> dict:
        """Extract all available metadata from yt_dlp info"""
        return {
            'video_id': info.get('id', 'unknown'),
            'username': re.sub(r'[^\w]+', '_', (info.get('uploader', '') or 'unknown').lower()),
            'title': info.get('title', ''),
            'description': info.get('description', ''),
            'duration': info.get('duration', 0),
            'view_count': info.get('view_count'),
            'like_count': info.get('like_count'),
            'comment_count': info.get('comment_count'),
            'upload_date': info.get('upload_date', ''),
            'uploader_id': info.get('uploader_id', ''),
            'uploader_url': info.get('uploader_url', ''),
            'channel_id': info.get('channel_id', ''),
            'channel_url': info.get('channel_url', ''),
            'thumbnail_url': info.get('thumbnail', ''),
            'webpage_url': info.get('webpage_url', ''),
            'extractor': info.get('extractor', ''),
            'platform': info.get('extractor_key', ''),
            'format_id': info.get('format_id', ''),
            'width': info.get('width'),
            'height': info.get('height'),
            'fps': info.get('fps'),
            'filesize': os.path.getsize(file_path) if os.path.exists(file_path) else 0,
            'file_path': file_path
        }
    
    async def _download_thumbnail(self, thumbnail_url: str, video_id: str, username: str, index: int) -> Optional[str]:
        """Download thumbnail image to thumbnails directory"""
        if not thumbnail_url:
            self.log_step(f"No thumbnail URL available for video {index}")
            return None
        
        try:
            self.log_step(f"Downloading thumbnail for video {index}")
            
            response = requests.get(thumbnail_url, timeout=15, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            if response.status_code == 200:
                # Get sequential number for the username
                seq_num = self._get_video_number(self.thumbnails_dir, username)
                
                # Determine file extension from content type
                content_type = response.headers.get('content-type', '')
                if 'jpeg' in content_type or 'jpg' in content_type:
                    ext = '.jpg'
                elif 'png' in content_type:
                    ext = '.png'
                elif 'webp' in content_type:
                    ext = '.webp'
                else:
                    ext = '.jpg'
                
                filename = f"{seq_num:02d}_{username}_{video_id}{ext}"
                # Ensure thumbnails_dir is absolute
                abs_thumbnails_dir = os.path.abspath(self.thumbnails_dir)
                os.makedirs(abs_thumbnails_dir, exist_ok=True)
                filepath = os.path.join(abs_thumbnails_dir, filename)
                filepath = self._get_unique_filename(filepath)
                # Normalize path separators for consistency
                filepath = os.path.normpath(filepath)
                
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                self.log_step(f"Downloaded thumbnail: {os.path.basename(filepath)}")
                return filepath
            else:
                self.log_step(f"Thumbnail download failed: HTTP {response.status_code}")
                
        except Exception as e:
            self.log_error(f"Thumbnail download failed: {str(e)}")
        
        return None
    
    async def _convert_video_to_audio(self, video_file: str, index: int) -> str:
        """Convert video to high-quality audio for transcription"""
        # Ensure audio_output_dir is absolute
        abs_audio_output_dir = os.path.abspath(self.audio_output_dir)
        os.makedirs(abs_audio_output_dir, exist_ok=True)
        video_basename = os.path.splitext(os.path.basename(video_file))[0]
        audio_file = os.path.join(abs_audio_output_dir, f"{video_basename}.wav")
        audio_file = self._get_unique_filename(audio_file)
        
        self.log_step(f"Converting video to audio for video {index}")
        
        try:
            # Ensure ffmpeg binary is available to the Python process. If not found on PATH,
            # attempt to auto-discover common WinGet install locations or use FFMPEG_PATH env var.
            import shutil
            import glob

            ffmpeg_exe = shutil.which('ffmpeg')
            self.log_step(f"ffmpeg resolved to: {ffmpeg_exe}")

            if not ffmpeg_exe:
                # Check explicit env var first
                ffmpeg_path_env = os.environ.get('FFMPEG_PATH')
                if ffmpeg_path_env and os.path.exists(ffmpeg_path_env):
                    ffmpeg_dir = os.path.dirname(ffmpeg_path_env)
                    os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')
                    self.log_step(f"Prepended FFMPEG_PATH to PATH: {ffmpeg_dir}")
                else:
                    # Try to auto-discover ffmpeg installed by WinGet (Gyan FFmpeg) under LOCALAPPDATA
                    local_app = os.getenv('LOCALAPPDATA', '')
                    packages_dir = os.path.join(local_app, 'Microsoft', 'WinGet', 'Packages')
                    found = False
                    if packages_dir and os.path.exists(packages_dir):
                        matches = glob.glob(os.path.join(packages_dir, '**', 'bin', 'ffmpeg.exe'), recursive=True)
                        if matches:
                            ffmpeg_bin = matches[0]
                            ffmpeg_dir = os.path.dirname(ffmpeg_bin)
                            os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')
                            self.log_step(f"Found ffmpeg via WinGet at: {ffmpeg_bin}")
                            found = True

                    if not found:
                        # Last resort: try imageio-ffmpeg (if installed)
                        try:
                            import imageio_ffmpeg
                            ffmpeg_exe_from_imageio = imageio_ffmpeg.get_ffmpeg_exe()
                            if ffmpeg_exe_from_imageio and os.path.exists(ffmpeg_exe_from_imageio):
                                ffmpeg_dir = os.path.dirname(ffmpeg_exe_from_imageio)
                                os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')
                                self.log_step(f"Using imageio-ffmpeg binary at: {ffmpeg_exe_from_imageio}")
                                found = True
                        except Exception:
                            pass

            conversion_start = time.time()
            ffmpeg.input(video_file).output(
                audio_file,
                acodec='pcm_s16le',
                ac=1, # Mono
                ar='16000', # 16kHz sample rate (optimal for Whisper)
                loglevel='error'
            ).run(overwrite_output=True)

            conversion_time = time.time() - conversion_start
            audio_size = os.path.getsize(audio_file)

            self.log_step(f"Audio conversion completed: {os.path.basename(audio_file)} ({audio_size / (1024*1024):.2f} MB)")
            return audio_file
            
        except Exception as e:
            self.log_error(f"Audio conversion failed: {str(e)}")
            raise Exception(f"Audio conversion failed: {str(e)}")
    
    async def _transcribe_audio_with_whisper(self, audio_file: str, index: int) -> str:
        """Transcribe audio using Whisper with comprehensive logging and GPU optimization for parallel processing"""
        self.log_step(f"Starting transcription with {self.whisper_model} model for video {index}")
        
        try:
            # Check GPU availability and set device
            device = "cuda" if torch.cuda.is_available() else "cpu"
            if torch.cuda.is_available():
                # Clear GPU memory before transcription
                torch.cuda.empty_cache()
                # Get GPU memory info for parallel processing optimization
                gpu_memory_allocated = torch.cuda.memory_allocated() / (1024**3)
                gpu_memory_reserved = torch.cuda.memory_reserved() / (1024**3)
                self.log_step(f"GPU detected: {torch.cuda.get_device_name(0)} (CUDA {torch.version.cuda}) - Memory: {gpu_memory_allocated:.2f}GB allocated, {gpu_memory_reserved:.2f}GB reserved")
            else:
                self.log_step("No GPU detected, using CPU")
            
            transcription_start = time.time()
            
            # Load model with explicit device specification
            # For parallel processing, we load the model fresh each time to avoid conflicts
            model = whisper.load_model(self.whisper_model, device=device)
            self.log_step(f"Loaded {self.whisper_model} model on {device.upper()} for video {index}")
            
            # Check audio duration
            audio_duration = self._get_audio_duration(audio_file)
            if audio_duration > self.max_audio_duration:
                self.log_step(f"Audio is {audio_duration}s, will chunk")
                transcript = await self._transcribe_long_audio(audio_file, model, index)
            else:
                # Standard transcription
                result = model.transcribe(audio_file, verbose=False)
                transcript = result['text'].strip()
            
            transcription_time = time.time() - transcription_start
            
            # Cleanup
            del model
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                self.log_step(f"GPU memory cleared after transcription")
            
            if transcript:
                self.log_step(f"Transcription completed: {len(transcript)} chars, {len(transcript.split())} words")
            else:
                self.log_step("Transcription produced empty result")
            
            return transcript
            
        except Exception as e:
            self.log_error(f"Transcription failed: {str(e)}")
            return ""
    
    def _get_audio_duration(self, audio_file: str) -> float:
        """Get audio duration using ffmpeg"""
        try:
            probe = ffmpeg.probe(audio_file)
            duration = float(probe['streams'][0]['duration'])
            return duration
        except Exception:
            return 0
    
    async def _transcribe_long_audio(self, audio_file: str, model, index: int) -> str:
        """Handle long audio files by chunking"""
        self.log_step(f"Chunking long audio file for video {index}")
        
        try:
            # Use ffmpeg to split audio into chunks
            # Ensure audio_output_dir is absolute
            abs_audio_output_dir = os.path.abspath(self.audio_output_dir)
            os.makedirs(abs_audio_output_dir, exist_ok=True)
            
            chunks = []
            duration = self._get_audio_duration(audio_file)
            num_chunks = int(duration // self.chunk_duration) + 1
            
            for i in range(num_chunks):
                start_time = i * self.chunk_duration
                chunk_file = os.path.join(abs_audio_output_dir, f"chunk_{i}_{os.path.basename(audio_file)}")
                
                ffmpeg.input(audio_file, ss=start_time, t=self.chunk_duration).output(
                    chunk_file,
                    acodec='pcm_s16le',
                    ac=1,
                    ar='16000',
                    loglevel='error'
                ).run(overwrite_output=True)
                
                chunks.append(chunk_file)
            
            self.log_step(f"Created {len(chunks)} chunks")
            
            # Transcribe each chunk
            full_transcript = []
            for i, chunk in enumerate(chunks):
                try:
                    result = model.transcribe(chunk, verbose=False)
                    chunk_transcript = result['text'].strip()
                    full_transcript.append(chunk_transcript)
                    self.log_step(f"Transcribed chunk {i+1}/{len(chunks)}")
                except Exception as e:
                    self.log_error(f"Failed to transcribe chunk {i+1}: {str(e)}")
                finally:
                    # Clean up chunk file
                    try:
                        os.remove(chunk)
                    except Exception:
                        pass
            
            transcript = ' '.join(full_transcript)
            self.log_step(f"Completed chunked transcription: {len(transcript)} chars")
            return transcript
            
        except Exception as e:
            self.log_error(f"Chunked transcription failed: {str(e)}")
            return ""
    
    async def _generate_smart_video_name(self, title: str, description: str, index: int) -> str:
        """Generate intelligent video name using GPT-4o-mini"""
        date_str = datetime.now().strftime('%d.%m.%Y')
        
        self.log_step(f"Generating smart video name for video {index}")
        
        # Create context for naming
        context = f"Title: {title}\n\nDescription: {description[:500]}"
        
        prompt = f"""Based on this video content, generate a concise, descriptive name (1-3 words) that captures the main topic or tool mentioned:

{context}

Return only the name, no explanation. Make it suitable for a filename."""
        
        try:
            response = self.openai_client.chat.completions.create(
                model='gpt-4o-mini',
                messages=[
                    {'role': 'system', 'content': 'You generate concise, descriptive names for video content.'},
                    {'role': 'user', 'content': prompt}
                ],
                max_tokens=20,
                temperature=0.3
            )
            
            name = response.choices[0].message.content.strip()
            name = self._safe_filename(name.lower())
            generated_name = f"{name}_{date_str}"
            
            self.log_step(f"Generated name: {generated_name}")
            return generated_name
            
        except Exception as e:
            self.log_error(f"Name generation failed: {str(e)}")
            # Fallback to title-based naming
            title_safe = self._safe_filename(title.lower())[:30]
            fallback_name = f"{title_safe}_{date_str}"
            self.log_step(f"Using fallback name: {fallback_name}")
            return fallback_name
    
    async def _save_transcript_file(self, transcript: str, generated_name: str, metadata: dict, index: int) -> str:
        """Save transcript as separate text file with metadata header"""
        # Ensure transcripts_dir is absolute
        abs_transcripts_dir = os.path.abspath(self.transcripts_dir)
        os.makedirs(abs_transcripts_dir, exist_ok=True)
        transcript_filename = f"{generated_name}.txt"
        transcript_path = os.path.join(abs_transcripts_dir, transcript_filename)
        transcript_path = self._get_unique_filename(transcript_path)
        
        # Create transcript file with metadata header
        header = f"""# Video Transcript
Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Video Title: {metadata.get('title', 'Unknown')}
Platform: {metadata.get('platform', 'Unknown')}
Duration: {metadata.get('duration', 0)} seconds
Video ID: {metadata.get('video_id', 'Unknown')}
Username: {metadata.get('username', 'Unknown')}
Source URL: {metadata.get('webpage_url', 'Unknown')}

{'='*50}
TRANSCRIPT:
{'='*50}

{transcript}
"""
        
        try:
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(header)
            
            self.log_step(f"Saved transcript file: {os.path.basename(transcript_path)}")
            return transcript_path
            
        except Exception as e:
            self.log_error(f"Failed to save transcript: {str(e)}")
            return ""
    
    # Utility methods
    def _get_unique_filename(self, path):
        """Generate unique filename if file exists"""
        if not os.path.exists(path):
            return path
        base, ext = os.path.splitext(path)
        counter = 1
        while True:
            new_path = f"{base}_{counter}{ext}"
            if not os.path.exists(new_path):
                return new_path
            counter += 1
    
    def _safe_filename(self, text: str, max_length: int = 100) -> str:
        """Convert text to safe filename"""
        if not text:
            return "unknown"
        safe = re.sub(r'[<>:"/\\|?*]', '_', text)
        safe = re.sub(r'\s+', '_', safe).strip('_')
        return safe[:max_length] if len(safe) > max_length else safe
    
    def _get_video_number(self, output_dir: str, username: str) -> int:
        """Get next available number for a username - uses absolute path"""
        # Ensure we're using absolute path
        abs_output_dir = os.path.abspath(output_dir)
        pattern = re.compile(rf'\d+_{re.escape(username)}_.*')
        max_num = 0
        
        if os.path.exists(abs_output_dir):
            for filename in os.listdir(abs_output_dir):
                if pattern.match(filename):
                    try:
                        num = int(filename.split('_')[0])
                        max_num = max(max_num, num)
                    except (ValueError, IndexError):
                        continue
        return max_num + 1
    
    def _extract_video_id(self, url: str) -> str:
        """Extract video ID from various platform URLs"""
        try:
            # YouTube
            if 'youtube.com' in url or 'youtu.be' in url:
                if 'youtu.be/' in url:
                    return url.split('youtu.be/')[-1].split('?')[0]
                elif 'v=' in url:
                    return url.split('v=')[-1].split('&')[0]
            
            # Instagram
            elif 'instagram.com' in url:
                if '/p/' in url:
                    return url.split('/p/')[-1].split('/')[0]
                elif '/reel/' in url:
                    return url.split('/reel/')[-1].split('/')[0]
            
            # TikTok
            elif 'tiktok.com' in url:
                if '/video/' in url:
                    return url.split('/video/')[-1].split('?')[0]
            
            # Generic fallback - use last part of URL
            return url.split('/')[-1].split('?')[0]
        except Exception:
            return None
    
    # Database integration methods
    async def _load_transcription_state(self) -> Dict[str, Any]:
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
            self.log_error("Error loading transcription state", e)
            return {}
    
    async def _check_existing_transcription(self, video_id: str) -> bool:
        """Check if video is already transcribed"""
        try:
            videos = await db_manager.get_videos_by_video_id(video_id)
            return len(videos) > 0 and videos[0].get('transcription_status') == 'COMPLETED'
        except Exception as e:
            self.log_error(f"Error checking existing transcription for {video_id}", e)
            return False
    
    async def _update_video_transcription(self, video_id: str, transcript: str, smart_name: str, video_path: str, thumbnail_path: str = None, metadata: dict = None, audio_path: str = None, transcript_path: str = None):
        """Update video record with transcription data and metadata"""
        try:
            # Find existing video record
            videos = await db_manager.get_all_videos()
            video_record = None
            for video in videos:
                if video.get('video_id') == video_id or video_id in video.get('filename', ''):
                    video_record = video
                    break
            
            # Ensure all paths are absolute before saving to database
            abs_video_path = os.path.abspath(video_path) if video_path else ''
            abs_audio_path = os.path.abspath(audio_path) if audio_path else ''
            abs_transcript_path = os.path.abspath(transcript_path) if transcript_path else ''
            abs_thumbnail_path = os.path.abspath(thumbnail_path) if thumbnail_path else ''
            
            # Prepare video data with metadata
            video_data = {
                'filename': video_record.get('filename', f"{video_id}.mp4") if video_record else f"{video_id}.mp4",
                'file_path': abs_video_path,
                'url': video_record.get('url', '') if video_record else '',
                'drive_id': video_record.get('drive_id', '') if video_record else '',
                'drive_url': video_record.get('drive_url', '') if video_record else '',
                'upload_status': video_record.get('upload_status', 'PENDING') if video_record else 'PENDING',
                'transcription_status': 'COMPLETED',
                'transcription_text': transcript,
                'smart_name': smart_name,
                'file_hash': video_record.get('file_hash', '') if video_record else '',
                'audio_file_path': abs_audio_path,
                'transcript_file_path': abs_transcript_path
            }
            
            # Add metadata if available
            if metadata:
                video_data.update({
                    'video_id': metadata.get('video_id', video_id),
                    'title': metadata.get('title', ''),
                    'description': metadata.get('description', ''),
                    'username': metadata.get('username', ''),
                    'uploader_id': metadata.get('uploader_id', ''),
                    'channel_id': metadata.get('channel_id', ''),
                    'channel_url': metadata.get('channel_url', ''),
                    'platform': metadata.get('platform', ''),
                    'duration': metadata.get('duration', 0),
                    'width': metadata.get('width'),
                    'height': metadata.get('height'),
                    'fps': metadata.get('fps'),
                    'format_id': metadata.get('format_id', ''),
                    'view_count': metadata.get('view_count'),
                    'like_count': metadata.get('like_count'),
                    'comment_count': metadata.get('comment_count'),
                    'upload_date': metadata.get('upload_date', ''),
                    'thumbnail_url': metadata.get('thumbnail_url', ''),
                    'webpage_url': metadata.get('webpage_url', ''),
                    'extractor': metadata.get('extractor', '')
                })
            
            await db_manager.upsert_video(video_data)
            self.log_step(f"Updated video record with transcription and metadata")
            
            # Update URLs table to link video_id if URL exists
            video_url = video_data.get('url', '')
            if video_url:
                try:
                    # Check if URL exists in urls table
                    url_exists = await db_manager.url_exists(video_url)
                    if url_exists:
                        # Update the URL entry with video_id and transcription_status
                        update_success = await db_manager.update_url_status(
                            url=video_url,
                            video_id=video_id,
                            transcription_status='COMPLETED',
                            notes=f'Linked to transcribed video (ID: {video_id})'
                        )
                        if update_success:
                            self.log_step(f"Updated URLs table with video_id {video_id} for URL: {video_url}")
                        else:
                            self.log_error(f"Failed to update URLs table with video_id for URL: {video_url}")
                    else:
                        # URL doesn't exist in urls table - try to find by video_id and update URL
                        try:
                            async with db_manager.get_connection() as conn:
                                # Check if there's a URL entry with this video_id but different URL
                                cursor = await conn.execute("SELECT url FROM urls WHERE video_id = ?", (video_id,))
                                row = await cursor.fetchone()
                                if row:
                                    existing_url = row[0]
                                    self.log_step(f"Found URL entry with video_id {video_id} but different URL: {existing_url}")
                        except Exception as e:
                            self.log_error(f"Error checking URLs table by video_id: {e}")
                except Exception as e:
                    self.log_error(f"Error updating URLs table: {e}")
            
            # Also try to update by video_id if URL is not available
            if not video_url:
                try:
                    # Find URL entry by video_id
                    async with db_manager.get_connection() as conn:
                        cursor = await conn.execute("SELECT url FROM urls WHERE video_id = ?", (video_id,))
                        row = await cursor.fetchone()
                        if row:
                            url_from_db = row[0]
                            # URL entry already has video_id, so JOIN will work automatically
                            self.log_step(f"URL entry found with video_id {video_id}, transcription status will be visible via JOIN")
                        else:
                            self.log_step(f"No URL entry found with video_id {video_id}")
                except Exception as e:
                    self.log_error(f"Error checking URLs table by video_id: {e}")
            
            # Update thumbnail if provided
            if abs_thumbnail_path:
                await db_manager.upsert_thumbnail({
                    'filename': os.path.basename(abs_thumbnail_path),
                    'file_path': abs_thumbnail_path,
                    'video_filename': f"{video_id}.mp4",
                    'drive_id': '',
                    'drive_url': '',
                    'upload_status': 'PENDING',
                    'file_hash': ''
                })
                
        except Exception as e:
            self.log_error(f"Error updating video transcription: {str(e)}")
    
    def _clean_vtt_transcript(self, vtt_text: str) -> str:
        """Clean VTT transcript by removing timestamps and XML tags
        Example: 'Hello <00:00:00.377><c>everyone, </c><00:00:00.754><c>today </c>'
        Returns: 'Hello everyone, today'
        
        Handles:
        - Timestamps: <00:00:00.377>, <00:00:01.131>
        - XML tags: <c>, </c>, <v>, </v>, etc.
        - Any other XML-like tags"""
        import re
        if not vtt_text:
            return ''
        
        # Remove timestamp patterns like <00:00:00.377> or <00:00:01.131>
        # Pattern matches: <HH:MM:SS.mmm> where HH can be 00-99
        clean = re.sub(r'<\d{1,2}:\d{2}:\d{2}\.\d{3}>', '', vtt_text)
        
        # Remove XML tags like <c>, </c>, <v>, </v>, <i>, </i>, etc.
        # This handles both opening and closing tags
        clean = re.sub(r'</?[a-z]+[^>]*>', '', clean)
        
        # Clean up extra spaces (multiple spaces, tabs, newlines)
        clean = re.sub(r'\s+', ' ', clean)
        
        # Strip leading/trailing whitespace
        clean = clean.strip()
        
        return clean
    
    async def _extract_youtube_transcript_only(self, url: str, index: int) -> tuple[dict, str, str, str]:
        """Extract YouTube transcript directly without downloading video
        Returns: (metadata dict, transcript_text, transcript_file_path, clean_transcript)"""
        self.log_step(f"Extracting YouTube transcript only (no video download) for video {index}")
        
        video_id = self._extract_video_id(url)
        
        # Create output directory for transcripts
        abs_transcripts_dir = os.path.abspath(self.transcripts_dir)
        os.makedirs(abs_transcripts_dir, exist_ok=True)
        
        # Configure for subtitle extraction only (same options for both info and download)
        # This matches the working test script approach
        transcript_opts = {
            'quiet': True,
            'noplaylist': True,  # Extract only single video, not playlist
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'en-US', 'en-GB'],
            'subtitlesformat': 'vtt',
            'skip_download': True,  # Don't download video
            'ignoreerrors': True,  # Continue even if format extraction fails
            'outtmpl': os.path.join(abs_transcripts_dir, f"{video_id}.%(ext)s"),
        }
        
        transcript_text = ''
        transcript_file_path = ''
        info = None
        metadata = {}
        
        try:
            with yt_dlp.YoutubeDL(transcript_opts) as ydl:
                # Step 1: Extract video info (using same options as download)
                # This ensures we don't trigger format validation
                self.log_step(f"Extracting video metadata...")
                try:
                    info = ydl.extract_info(url, download=False)
                except Exception as e:
                    error_msg = str(e)
                    # If format error, try to continue - we only need transcripts
                    if 'format is not available' in error_msg or 'Requested format' in error_msg:
                        self.log_step(f"Format warning during info extraction (expected for transcript-only)")
                        # Try to get info anyway - sometimes it still works
                        try:
                            # Try with even more permissive options
                            minimal_opts = {
                                'quiet': True,
                                'noplaylist': True,
                                'skip_download': True,
                                'ignoreerrors': True,
                            }
                            with yt_dlp.YoutubeDL(minimal_opts) as ydl2:
                                info = ydl2.extract_info(url, download=False)
                        except:
                            pass
                    else:
                        raise  # Re-raise if it's a different error
                
                if not info:
                    raise Exception("Failed to extract video info - video may be restricted or unavailable")
                
                # Handle playlist results - extract first video if it's a playlist
                if info.get('_type') == 'playlist':
                    entries = info.get('entries', [])
                    if entries:
                        info = entries[0]  # Use first video from playlist
                        self.log_step(f"Extracted first video from playlist: {info.get('title', 'Unknown')}")
                    else:
                        raise Exception("Playlist has no available videos")
                
                # Extract metadata from info
                metadata = self._extract_comprehensive_metadata(info, '')  # No file path needed
                self.log_step(f"Metadata extracted: {metadata.get('title', 'Unknown')}")
                
                # Step 2: Download transcript
                self.log_step(f"Downloading transcript...")
                try:
                    ydl.download([url])
                except Exception as download_error:
                    error_msg = str(download_error)
                    # If it's a format error but we're only getting transcripts, try to continue
                    if 'format is not available' in error_msg or 'Requested format' in error_msg:
                        self.log_step(f"Format warning during download (expected for transcript-only)")
                        # Continue - transcript might still be available
                    else:
                        # Log but don't fail completely
                        self.log_error(f"Download error: {error_msg[:200]}")
                
                # Find the downloaded transcript file (yt-dlp adds language code: video_id.en.vtt)
                for file in os.listdir(abs_transcripts_dir):
                    if file.startswith(video_id) and file.endswith(('.vtt', '.srt', '.ttml')):
                        transcript_file_path = os.path.join(abs_transcripts_dir, file)
                        break
                
                if transcript_file_path and os.path.exists(transcript_file_path):
                    # Read and convert VTT to plain text
                    with open(transcript_file_path, 'r', encoding='utf-8') as f:
                        vtt_content = f.read()
                    
                    # Extract text from VTT (remove timestamps and formatting)
                    lines = vtt_content.split('\n')
                    text_lines = []
                    for line in lines:
                        line = line.strip()
                        # Skip WebVTT headers, timestamps, and empty lines
                        if (line and 
                            not line.startswith('WEBVTT') and 
                            '-->' not in line and 
                            not line.startswith('Kind:') and 
                            not line.startswith('Language:') and
                            not line.startswith('NOTE:')):
                            text_lines.append(line)
                    
                    transcript_text = ' '.join(text_lines)
                    self.log_step(f"Transcript extracted: {len(transcript_text)} characters, {len(transcript_text.split())} words")
                else:
                    # Check if transcript is available in the info but wasn't downloaded
                    subtitles = info.get('subtitles', {}) if info else {}
                    auto_captions = info.get('automatic_captions', {}) if info else {}
                    if subtitles or auto_captions:
                        self.log_step(f"Warning: Transcript file not found, but transcripts are available in video info")
                        self.log_step(f"Note: Video may have format restrictions preventing transcript download")
                    else:
                        self.log_step(f"Warning: No transcripts available for this video")
                    
        except Exception as e:
            error_msg = str(e)
            self.log_error(f"Error in transcript extraction: {error_msg}")
            # If we have metadata, continue with that
            if not metadata and info:
                try:
                    metadata = self._extract_comprehensive_metadata(info, '')
                except:
                    pass
        
        # Ensure we have at least basic metadata
        if not metadata:
            # Create minimal metadata from video_id
            metadata = {
                'video_id': video_id,
                'title': f"YouTube Video {video_id}",
                'description': '',
                'platform': 'youtube',
            }
        
        # Create clean transcript (remove timestamps and XML tags)
        clean_transcript = ''
        if transcript_text:
            clean_transcript = self._clean_vtt_transcript(transcript_text)
            self.log_step(f"Clean transcript created: {len(clean_transcript)} characters, {len(clean_transcript.split())} words")
        
        return metadata, transcript_text, transcript_file_path, clean_transcript
    
    async def download_video_only(self, url: str, index: int) -> bool:
        """Download video and extract metadata only (no transcription, no upload)
        For YouTube: Extract transcript directly without downloading video
        Returns True if downloaded, False if failed, or raises AlreadyDownloadedException if already exists"""
        try:
            # Check if this is a YouTube URL
            is_youtube = 'youtube.com' in url or 'youtu.be' in url
            
            if is_youtube:
                self.log_step(f"YOUTUBE DETECTED: Using transcript-only extraction (no video download) for video {index}")
            else:
                self.log_step(f"DOWNLOAD ONLY: Starting download-only processing for video {index} (NO transcription, NO upload)")
            
            # Check if video is already downloaded BEFORE attempting download
            video_id = self._extract_video_id(url)
            
            # Check 1: Check database by URL
            try:
                async with db_manager.get_connection() as conn:
                    cursor = await conn.execute("SELECT * FROM video_transcripts WHERE url = ?", (url,))
                    row = await cursor.fetchone()
                    if row:
                        cursor = await conn.execute("PRAGMA table_info(video_transcripts)")
                        columns = [col[1] for col in await cursor.fetchall()]
                        existing_video_by_url = dict(zip(columns, row))
                        
                        # For YouTube: check if transcript exists
                        # For others: check if video file exists
                        if is_youtube:
                            transcript_path = existing_video_by_url.get('transcript_file_path', '')
                            transcription_status = existing_video_by_url.get('transcription_status', '')
                            if (transcript_path and os.path.exists(transcript_path)) or transcription_status == 'COMPLETED':
                                self.log_step(f"SKIP: YouTube transcript already extracted (found in database by URL): {url}")
                                self.log_step(f"Existing transcript: {transcript_path if transcript_path else 'Status: COMPLETED'}")
                                raise AlreadyDownloadedException(f"YouTube transcript already extracted: {url}", transcript_path, existing_video_by_url)
                        else:
                            file_path = existing_video_by_url.get('file_path', '')
                            if file_path and os.path.exists(file_path):
                                self.log_step(f"SKIP: Video already downloaded (found in database by URL): {url}")
                                self.log_step(f"Existing file: {file_path}")
                                raise AlreadyDownloadedException(f"Video already downloaded: {url}", file_path, existing_video_by_url)
            except AlreadyDownloadedException:
                raise
            except Exception as e:
                self.log_error(f"Error checking database by URL: {e}")
            
            # Check 2: Check database by video_id
            if video_id:
                existing_video_by_id = await db_manager.get_video_transcript_by_id(video_id)
                if existing_video_by_id:
                    # For YouTube: check if transcript exists (transcript_file_path or transcription_status is COMPLETED)
                    # For others: check if video file exists
                    if is_youtube:
                        transcript_path = existing_video_by_id.get('transcript_file_path', '')
                        transcription_status = existing_video_by_id.get('transcription_status', '')
                        if (transcript_path and os.path.exists(transcript_path)) or transcription_status == 'COMPLETED':
                            self.log_step(f"SKIP: YouTube transcript already extracted (found in database by video_id): {video_id}")
                            self.log_step(f"Existing transcript: {transcript_path if transcript_path else 'Status: COMPLETED'}")
                            raise AlreadyDownloadedException(f"YouTube transcript already extracted (ID: {video_id})", transcript_path, existing_video_by_id)
                    else:
                        file_path = existing_video_by_id.get('file_path', '')
                        if file_path and os.path.exists(file_path):
                            self.log_step(f"SKIP: Video already downloaded (found in database by video_id): {video_id}")
                            self.log_step(f"Existing file: {file_path}")
                            raise AlreadyDownloadedException(f"Video already downloaded (ID: {video_id})", file_path, existing_video_by_id)
            
            # Check 3: Check file system
            if is_youtube:
                # For YouTube: Check transcripts directory for existing transcript files
                if video_id and os.path.exists(self.transcripts_dir):
                    for file in os.listdir(self.transcripts_dir):
                        if video_id in file and file.endswith(('.vtt', '.srt', '.ttml')):
                            full_path = os.path.join(self.transcripts_dir, file)
                            if os.path.exists(full_path):
                                self.log_step(f"SKIP: YouTube transcript file already exists on disk: {file}")
                                self.log_step(f"Existing transcript: {full_path}")
                                # Try to get metadata from database
                                existing_video = await db_manager.get_video_transcript_by_id(video_id)
                                raise AlreadyDownloadedException(f"YouTube transcript file already exists: {file}", full_path, existing_video)
            else:
                # For other platforms: Check video output directory for video files
                if video_id and os.path.exists(self.video_output_dir):
                    for file in os.listdir(self.video_output_dir):
                        if video_id in file and file.endswith(('.mp4', '.webm', '.mkv')):
                            full_path = os.path.join(self.video_output_dir, file)
                            if os.path.exists(full_path):
                                self.log_step(f"SKIP: Video file already exists on disk: {file}")
                                self.log_step(f"Existing file: {full_path}")
                                # Try to get metadata from database or extract from file
                                existing_video = await db_manager.get_video_transcript_by_id(video_id)
                                raise AlreadyDownloadedException(f"Video file already exists: {file}", full_path, existing_video)
            
            # Step 1: For YouTube, extract transcript only. For others, download video
            if is_youtube:
                # YouTube: Extract transcript directly (no video download)
                metadata, transcript_text, transcript_file_path, clean_transcript = await self._extract_youtube_transcript_only(url, index)
                video_path = ''  # No video file for YouTube transcript-only mode
                raw_info = None
            else:
                # Other platforms: Download video and extract metadata
                video_path, metadata, raw_info = await self._download_video_and_metadata(url, index)
                transcript_text = ''  # Empty for non-YouTube (will be transcribed later)
                transcript_file_path = ''
                clean_transcript = ''  # Empty for non-YouTube
            
            # Step 2: Download thumbnail
            thumbnail_path = await self._download_thumbnail(
                metadata.get('thumbnail_url'), 
                metadata.get('video_id'), 
                metadata.get('username'),
                index
            )
            
            # Log thumbnail path for debugging
            if thumbnail_path:
                self.log_step(f"Thumbnail downloaded to: {thumbnail_path}")
            else:
                self.log_step(f"No thumbnail downloaded for video {index}")
            
            # Step 3: Generate smart video name
            generated_name = await self._generate_smart_video_name(
                metadata.get('title', ''), 
                metadata.get('description', ''),
                index
            )
            
            # Step 4: Save to database
            # Ensure all paths are absolute before saving to database
            abs_video_path = os.path.abspath(video_path) if video_path else ''
            abs_thumbnail_path = os.path.abspath(thumbnail_path) if thumbnail_path else ''
            abs_transcript_path = os.path.abspath(transcript_file_path) if transcript_file_path else ''
            
            # For YouTube transcript-only: mark as COMPLETED with transcript
            # For other platforms: mark as PENDING (will be transcribed later)
            if is_youtube and transcript_text:
                transcription_status = 'COMPLETED'
                transcript_word_count = len(transcript_text.split())
                notes = 'YouTube transcript extracted (no video download)'
            else:
                transcription_status = 'PENDING'
                transcript_word_count = 0
                notes = 'Downloaded only - transcription pending'
            
            # Determine filename (for YouTube, use transcript filename; for others, use video filename)
            if is_youtube:
                filename = os.path.basename(abs_transcript_path) if abs_transcript_path else f"{video_id}_transcript.vtt"
            else:
                filename = os.path.basename(abs_video_path) if abs_video_path else f"{video_id}.mp4"
            
            # Calculate file size in MB (for non-YouTube: from metadata or actual file; for YouTube: 0)
            if is_youtube:
                video_file_size_mb = 0  # No video file for YouTube transcript-only
            else:
                # Try to get from metadata first (filesize is in bytes)
                filesize_bytes = metadata.get('filesize', 0)
                if filesize_bytes > 0:
                    video_file_size_mb = filesize_bytes / (1024 * 1024)  # Convert bytes to MB
                elif abs_video_path and os.path.exists(abs_video_path):
                    # Fallback: calculate from actual file
                    video_file_size_mb = os.path.getsize(abs_video_path) / (1024 * 1024)
                else:
                    video_file_size_mb = 0
            
            video_data = {
                'video_id': metadata.get('video_id', ''),
                'filename': filename,
                'file_path': abs_video_path,  # Empty for YouTube transcript-only, actual path for others
                'url': url,
                'title': metadata.get('title', ''),
                'description': metadata.get('description', ''),
                'username': metadata.get('username', ''),
                'uploader_id': metadata.get('uploader_id', ''),
                'channel_id': metadata.get('channel_id', ''),
                'channel_url': metadata.get('channel_url', ''),
                'platform': metadata.get('platform', ''),
                'duration': metadata.get('duration', 0),
                'width': metadata.get('width', 0),
                'height': metadata.get('height', 0),
                'fps': metadata.get('fps', 0),
                'format_id': metadata.get('format_id', ''),
                'view_count': metadata.get('view_count', 0),
                'like_count': metadata.get('like_count', 0),
                'comment_count': metadata.get('comment_count', 0),
                'upload_date': metadata.get('upload_date', ''),
                'thumbnail_url': metadata.get('thumbnail_url', ''),
                'webpage_url': metadata.get('webpage_url', ''),
                'extractor': metadata.get('extractor', ''),
                'transcription_text': transcript_text,  # For YouTube: transcript text (may contain timestamps/tags); for others: empty
                'transcription_status': transcription_status,  # COMPLETED for YouTube with transcript, PENDING for others
                'smart_name': generated_name,
                'thumbnail_file_path': abs_thumbnail_path if abs_thumbnail_path else '',
                'transcript_file_path': abs_transcript_path if abs_transcript_path else '',  # YouTube: transcript file path; others: empty
                'clean_transcript': clean_transcript if is_youtube and clean_transcript else '',  # YouTube: clean transcript without timestamps/tags; others: empty
                'video_file_size_mb': video_file_size_mb,  # Calculated above
                'transcript_word_count': transcript_word_count,
                'processing_time_seconds': 0,
                'notes': notes,
                'error_details': ''
            }
            
            # Debug: Log the data being saved (especially for YouTube)
            self.log_step(f"=== SAVING TO DATABASE ===")
            if is_youtube:
                self.log_step(f"YouTube video detected - transcript available: {bool(transcript_text)}")
                if transcript_text:
                    self.log_step(f"  - transcription_text length: {len(transcript_text)} characters")
                    self.log_step(f"  - transcript_file_path: {abs_transcript_path}")
                    self.log_step(f"  - transcription_status: {transcription_status}")
                    self.log_step(f"  - transcript_word_count: {transcript_word_count}")
                else:
                    self.log_error(f"  - WARNING: transcript_text is EMPTY for YouTube video!")
            self.log_step(f"Saving thumbnail path to database: {video_data.get('thumbnail_file_path', 'EMPTY')}")
            self.log_step(f"video_data keys: {list(video_data.keys())}")
            self.log_step(f"transcription_text in video_data: {'transcription_text' in video_data}")
            self.log_step(f"transcript_file_path in video_data: {'transcript_file_path' in video_data}")
            
            # Save to database
            self.log_step(f"Calling upsert_video_transcript with video_data...")
            success = await db_manager.upsert_video_transcript(video_data)
            if success:
                self.log_step(f"✅ Video {index} data saved to database successfully")
                
                # Verify what was actually saved (for YouTube)
                if is_youtube:
                    self.log_step(f"=== VERIFYING SAVED DATA (YouTube) ===")
                    try:
                        saved_video = await db_manager.get_video_transcript_by_index(index)
                        if saved_video:
                            saved_text = saved_video.get('transcription_text', '')
                            saved_path = saved_video.get('transcript_file_path', '')
                            saved_status = saved_video.get('transcription_status', '')
                            saved_platform = saved_video.get('platform', '')
                            self.log_step(f"Retrieved saved video from database:")
                            self.log_step(f"  - platform: {saved_platform}")
                            self.log_step(f"  - transcription_status: {saved_status}")
                            self.log_step(f"  - transcription_text length: {len(saved_text)} characters")
                            self.log_step(f"  - transcript_file_path: {saved_path}")
                            if not saved_text:
                                self.log_error(f"  - ❌ ERROR: transcription_text is EMPTY in database!")
                            if not saved_path:
                                self.log_error(f"  - ❌ ERROR: transcript_file_path is EMPTY in database!")
                            if saved_status != 'COMPLETED':
                                self.log_error(f"  - ❌ ERROR: transcription_status is '{saved_status}', expected 'COMPLETED'!")
                        else:
                            self.log_error(f"❌ Could not retrieve saved video data for verification")
                    except Exception as e:
                        self.log_error(f"❌ Error verifying saved data: {str(e)}")
                        import traceback
                        self.log_error(f"Traceback: {traceback.format_exc()}")
                
                # Update URL status in urls table
                video_id = metadata.get('video_id', '')
                from datetime import datetime
                
                # Check if URL exists in database, add it if not
                url_exists = await db_manager.url_exists(url)
                if not url_exists:
                    # Add URL to database if it doesn't exist
                    await db_manager.add_url(
                        url=url,
                        source='download',
                        status='DOWNLOADED',
                        download_status='DOWNLOADED',
                        notes=f'Added during download process'
                    )
                    self.log_step(f"Added URL to database: {url}")
                
                # Update URL status (update both status and download_status)
                if video_id:
                    update_success = await db_manager.update_url_status(
                        url=url,
                        status='DOWNLOADED',  # Also update status field
                        download_status='DOWNLOADED',
                        video_id=video_id,
                        downloaded_at=datetime.now().isoformat(),
                        notes=f'Downloaded as video_id: {video_id}'
                    )
                    if update_success:
                        self.log_step(f"URL status updated to DOWNLOADED for: {url} (video_id: {video_id})")
                    else:
                        self.log_error(f"Failed to update URL status for: {url}")
                else:
                    # Update without video_id if it's not available
                    update_success = await db_manager.update_url_status(
                        url=url,
                        status='DOWNLOADED',  # Also update status field
                        download_status='DOWNLOADED',
                        downloaded_at=datetime.now().isoformat(),
                        notes='Downloaded successfully'
                    )
                    if update_success:
                        self.log_step(f"URL status updated to DOWNLOADED for: {url} (no video_id)")
                    else:
                        self.log_error(f"Failed to update URL status for: {url}")
                
                self.processed_count += 1
                
                if is_youtube and transcript_text:
                    # YouTube transcript-only mode
                    self.log_step(f"YOUTUBE TRANSCRIPT: Video {index} processed successfully (transcript extracted, no video download)")
                    self.log_step(f"Transcript file: {abs_transcript_path}")
                    self.log_step(f"Transcript length: {len(transcript_text)} characters, {transcript_word_count} words")
                    print(f"\n{'='*60}")
                    print(f"YOUTUBE TRANSCRIPT COMPLETE: Video {index}")
                    print(f"Title: {metadata.get('title', 'Unknown')}")
                    print(f"Transcript saved to: {abs_transcript_path}")
                    print(f"Transcript: {transcript_word_count} words")
                    print(f"{'='*60}\n")
                else:
                    # Regular download mode
                    abs_video_path = os.path.abspath(video_path) if video_path else ''
                    self.log_step(f"DOWNLOAD ONLY: Video {index} downloaded successfully (NO transcription, NO upload performed)")
                    self.log_step(f"Downloaded file location: {abs_video_path}")
                    print(f"\n{'='*60}")
                    print(f"DOWNLOAD COMPLETE: Video {index}")
                    print(f"File saved to: {abs_video_path}")
                    print(f"{'='*60}\n")
                return True
            else:
                self.log_error(f"❌ Failed to save video {index} data to database")
                # Update URL status to FAILED
                from datetime import datetime
                await db_manager.update_url_status(
                    url=url,
                    download_status='FAILED',
                    notes='Failed to save video data to database'
                )
                return False
                
        except Exception as e:
            self.log_error(f"Error in download-only processing for video {index}: {str(e)}")
            self.failed_count += 1
            return False

    async def cleanup(self) -> None:
        """Cleanup video processor resources"""
        try:
            self.log_step("Cleaning up video processor")
            self.status = "idle"
            self.log_step("Video processor cleanup completed")
        except Exception as e:
            self.log_error("Error during cleanup", e)
