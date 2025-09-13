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
from system.database import db_manager
from system.config import settings

# Core libraries
import yt_dlp
import ffmpeg
import whisper
import requests
import torch
import gc
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class VideoProcessor(BaseProcessor):
    """Handles video processing and transcription with real logic"""
    
    def __init__(self):
        super().__init__("VideoProcessor")
        self.processed_count = 0
        self.failed_count = 0
        
        # Configuration
        self.video_output_dir = "assets/downloads/videos"
        self.audio_output_dir = "assets/downloads/audio"
        self.thumbnails_dir = "assets/downloads/thumbnails"
        self.transcripts_dir = "assets/downloads/transcripts"
        
        # Processing configuration
        self.whisper_model = os.getenv("WHISPER_MODEL", "base")
        self.max_audio_duration = int(os.getenv("MAX_AUDIO_DURATION", "1800"))
        self.chunk_duration = int(os.getenv("CHUNK_DURATION", "30"))
        self.keep_audio_files = os.getenv("KEEP_AUDIO_FILES", "true").lower() == "true"
        
        # OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set. Please add it to your .env file.")
        self.openai_client = OpenAI(api_key=api_key)
    
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
        """Process a list of URLs for video download and transcription"""
        try:
            self.log_step(f"Processing {len(urls)} URLs")
            self.status = "processing"
            
            # Load existing transcription state
            transcription_state = await self._load_transcription_state()
            
            # Filter out already processed URLs
            new_urls = []
            for url in urls:
                video_id = self._extract_video_id(url)
                if video_id and transcription_state.get(video_id, {}).get('status') != 'completed':
                    new_urls.append(url)
            
            if not new_urls:
                self.log_step("No new URLs to process - all have been transcribed")
                return True
            
            # Process each URL
            for i, url in enumerate(new_urls, 1):
                try:
                    success = await self._process_single_video(url, i)
                    if success:
                        self.processed_count += 1
                    else:
                        self.failed_count += 1
                except Exception as e:
                    self.log_error(f"Error processing URL {url}", e)
                    self.failed_count += 1
            
            self.status = "completed"
            self.log_step(f"Video processing completed: {self.processed_count} successful, {self.failed_count} failed")
            return self.failed_count == 0
            
        except Exception as e:
            self.log_error("Error in process_urls", e)
            self.status = "error"
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
                video_id = metadata.get('video_id', '')
                if video_id:
                    await self._update_video_transcription(video_id, transcript, generated_name, video_path, thumbnail_path, metadata)
                
                self.log_step(f"Complete pipeline successful: {generated_name}")
                return True
            else:
                self.log_error(f"Transcription failed for video {index}")
                return False
                
        except Exception as e:
            self.log_error(f"Error processing video {index}: {str(e)}")
            return False
        finally:
            processing_time = time.time() - start_time
            self.log_step(f"Video {index} processing completed in {processing_time:.2f}s")
    
    # Real video processing methods from full-rounded script
    
    async def _download_video_and_metadata(self, url: str, index: int) -> tuple[str, dict, dict]:
        """Download video using yt_dlp and extract comprehensive metadata"""
        self.log_step(f"Extracting video information for video {index}")
        
        # First, extract info without downloading
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
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
        
        # Check if already downloaded
        for file in os.listdir(self.video_output_dir):
            if video_id in file and file.endswith(('.mp4', '.webm', '.mkv')):
                full_path = os.path.join(self.video_output_dir, file)
                self.log_step(f"Video already downloaded: {file}")
                metadata = self._extract_comprehensive_metadata(info, full_path)
                return full_path, metadata, info
        
        # Create filename with sequential numbering
        seq_num = self._get_video_number(self.video_output_dir, username)
        filename_template = os.path.join(self.video_output_dir, f"{seq_num:02d}_{username}_{video_id}.%(ext)s")
        
        self.log_step(f"Starting download: {title}")
        
        # Download configuration
        ydl_opts = {
            'outtmpl': filename_template,
            'format': 'best[ext=mp4]/best',
            'writesubtitles': False,
            'writeautomaticsub': False,
            'ignoreerrors': False,
            'quiet': True
        }
        
        download_start = time.time()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            downloaded_file = ydl.prepare_filename(info)
        
        download_time = time.time() - download_start
        
        if not os.path.exists(downloaded_file):
            # Try to find the downloaded file with different extension
            base_name = os.path.splitext(downloaded_file)[0]
            for ext in ['.mp4', '.webm', '.mkv', '.mov']:
                alt_path = base_name + ext
                if os.path.exists(alt_path):
                    downloaded_file = alt_path
                    break
            else:
                self.log_error("Downloaded file not found")
                raise Exception("Downloaded file not found")
        
        file_size = os.path.getsize(downloaded_file)
        self.log_step(f"Downloaded successfully: {os.path.basename(downloaded_file)} ({file_size / (1024*1024):.2f} MB)")
        
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
                filepath = os.path.join(self.thumbnails_dir, filename)
                filepath = self._get_unique_filename(filepath)
                
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
        video_basename = os.path.splitext(os.path.basename(video_file))[0]
        audio_file = os.path.join(self.audio_output_dir, f"{video_basename}.wav")
        audio_file = self._get_unique_filename(audio_file)
        
        self.log_step(f"Converting video to audio for video {index}")
        
        try:
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
        """Transcribe audio using Whisper with comprehensive logging and GPU optimization"""
        self.log_step(f"Starting transcription with {self.whisper_model} model for video {index}")
        
        try:
            # Check GPU availability and set device
            device = "cuda" if torch.cuda.is_available() else "cpu"
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                self.log_step(f"GPU detected: {torch.cuda.get_device_name(0)} (CUDA {torch.version.cuda})")
            else:
                self.log_step("No GPU detected, using CPU")
            
            transcription_start = time.time()
            
            # Load model with explicit device specification
            model = whisper.load_model(self.whisper_model, device=device)
            self.log_step(f"Loaded {self.whisper_model} model on {device.upper()}")
            
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
            chunks = []
            duration = self._get_audio_duration(audio_file)
            num_chunks = int(duration // self.chunk_duration) + 1
            
            for i in range(num_chunks):
                start_time = i * self.chunk_duration
                chunk_file = os.path.join(self.audio_output_dir, f"chunk_{i}_{os.path.basename(audio_file)}")
                
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
        transcript_filename = f"{generated_name}.txt"
        transcript_path = os.path.join(self.transcripts_dir, transcript_filename)
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
        """Get next available number for a username"""
        pattern = re.compile(rf'\d+_{re.escape(username)}_.*')
        max_num = 0
        
        if os.path.exists(output_dir):
            for filename in os.listdir(output_dir):
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
    
    async def _update_video_transcription(self, video_id: str, transcript: str, smart_name: str, video_path: str, thumbnail_path: str = None, metadata: dict = None):
        """Update video record with transcription data and metadata"""
        try:
            # Find existing video record
            videos = await db_manager.get_all_videos()
            video_record = None
            for video in videos:
                if video.get('video_id') == video_id or video_id in video.get('filename', ''):
                    video_record = video
                    break
            
            # Prepare video data with metadata
            video_data = {
                'filename': video_record.get('filename', f"{video_id}.mp4") if video_record else f"{video_id}.mp4",
                'file_path': video_path,
                'url': video_record.get('url', '') if video_record else '',
                'drive_id': video_record.get('drive_id', '') if video_record else '',
                'drive_url': video_record.get('drive_url', '') if video_record else '',
                'upload_status': video_record.get('upload_status', 'PENDING') if video_record else 'PENDING',
                'transcription_status': 'COMPLETED',
                'transcription_text': transcript,
                'smart_name': smart_name,
                'file_hash': video_record.get('file_hash', '') if video_record else ''
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
            
            # Update thumbnail if provided
            if thumbnail_path:
                await db_manager.upsert_thumbnail({
                    'filename': os.path.basename(thumbnail_path),
                    'file_path': thumbnail_path,
                    'video_filename': f"{video_id}.mp4",
                    'drive_id': '',
                    'drive_url': '',
                    'upload_status': 'PENDING',
                    'file_hash': ''
                })
                
        except Exception as e:
            self.log_error(f"Error updating video transcription: {str(e)}")
    
    async def cleanup(self) -> None:
        """Cleanup video processor resources"""
        try:
            self.log_step("Cleaning up video processor")
            self.status = "idle"
            self.log_step("Video processor cleanup completed")
        except Exception as e:
            self.log_error("Error during cleanup", e)
