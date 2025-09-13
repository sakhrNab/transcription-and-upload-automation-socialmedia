#!/usr/bin/env python3
"""
Update video metadata from transcript files
Extracts metadata from transcript file headers and updates the database
"""

import asyncio
import os
import re
import sys
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from system.database import db_manager

async def extract_metadata_from_transcript(transcript_path: str) -> dict:
    """Extract metadata from transcript file header"""
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract metadata from header
        metadata = {}
        
        # Video Title
        title_match = re.search(r'Video Title: (.+)', content)
        if title_match:
            metadata['title'] = title_match.group(1).strip()
        
        # Platform
        platform_match = re.search(r'Platform: (.+)', content)
        if platform_match:
            metadata['platform'] = platform_match.group(1).strip()
        
        # Duration
        duration_match = re.search(r'Duration: ([\d.]+) seconds', content)
        if duration_match:
            metadata['duration'] = float(duration_match.group(1))
        
        # Video ID
        video_id_match = re.search(r'Video ID: (.+)', content)
        if video_id_match:
            metadata['video_id'] = video_id_match.group(1).strip()
        
        # Username
        username_match = re.search(r'Username: (.+)', content)
        if username_match:
            metadata['username'] = username_match.group(1).strip()
        
        # Source URL
        url_match = re.search(r'Source URL: (.+)', content)
        if url_match:
            metadata['webpage_url'] = url_match.group(1).strip()
        
        return metadata
        
    except Exception as e:
        print(f"Error extracting metadata from {transcript_path}: {e}")
        return {}

async def update_video_metadata():
    """Update video metadata from transcript files"""
    try:
        # Initialize database
        await db_manager.initialize()
        print("Database initialized")
        
        # Get all videos from database
        videos = await db_manager.get_all_videos()
        print(f"Found {len(videos)} videos in database")
        
        # Get transcript files
        transcript_dir = Path("assets/downloads/transcripts")
        transcript_files = list(transcript_dir.glob("*.txt"))
        print(f"Found {len(transcript_files)} transcript files")
        
        updated_count = 0
        
        for video in videos:
            video_id = video.get('video_id', '')
            filename = video.get('filename', '')
            
            if not video_id and not filename:
                continue
            
            # Find matching transcript file by checking content
            matching_transcript = None
            for transcript_file in transcript_files:
                try:
                    with open(transcript_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Extract video ID from transcript content
                    video_id_match = re.search(r'Video ID: (.+)', content)
                    if video_id_match:
                        transcript_video_id = video_id_match.group(1).strip()
                        
                        # Check if this matches our video
                        if video_id and video_id == transcript_video_id:
                            matching_transcript = transcript_file
                            break
                        elif filename and transcript_video_id in filename:
                            matching_transcript = transcript_file
                            break
                except Exception as e:
                    continue
            
            if not matching_transcript:
                print(f"No transcript found for video {video_id or filename}")
                continue
            
            # Extract metadata from transcript
            metadata = await extract_metadata_from_transcript(str(matching_transcript))
            if not metadata:
                print(f"No metadata extracted from {matching_transcript.name}")
                continue
            
            # Update video record
            video_data = {
                'filename': video.get('filename', ''),
                'file_path': video.get('file_path', ''),
                'url': video.get('url', ''),
                'drive_id': video.get('drive_id', ''),
                'drive_url': video.get('drive_url', ''),
                'upload_status': video.get('upload_status', 'PENDING'),
                'transcription_status': video.get('transcription_status', 'PENDING'),
                'transcription_text': video.get('transcription_text', ''),
                'smart_name': video.get('smart_name', ''),
                'aiwaverider_status': video.get('aiwaverider_status', 'PENDING'),
                'file_hash': video.get('file_hash', ''),
                # Add extracted metadata
                'video_id': metadata.get('video_id', video_id),
                'title': metadata.get('title', ''),
                'platform': metadata.get('platform', ''),
                'duration': metadata.get('duration', 0),
                'username': metadata.get('username', ''),
                'webpage_url': metadata.get('webpage_url', ''),
            }
            
            await db_manager.upsert_video(video_data)
            updated_count += 1
            print(f"Updated video: {metadata.get('title', 'Unknown')} ({metadata.get('video_id', 'Unknown')})")
        
        print(f"Updated {updated_count} videos with metadata")
        
        # Close database
        await db_manager.close()
        
    except Exception as e:
        print(f"Error updating video metadata: {e}")

if __name__ == "__main__":
    asyncio.run(update_video_metadata())
