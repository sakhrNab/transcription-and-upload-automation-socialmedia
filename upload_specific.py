#!/usr/bin/env python3
"""
Upload Specific Videos Script
Uploads specific videos with advanced options and filtering
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path
from typing import List, Optional

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from upload_only import UploadOnlyOrchestrator
from system.new_database import new_db_manager as db_manager


async def upload_by_status(status: str = "PENDING"):
    """Upload videos by their current status"""
    print(f"📤 Uploading videos with status: {status}")
    
    # Get videos from database by status
    all_videos = await db_manager.get_all_videos()
    filtered_videos = [v for v in all_videos if v.get('upload_status', 'PENDING') == status]
    
    if not filtered_videos:
        print(f"ℹ️ No videos found with status: {status}")
        return
    
    print(f"📁 Found {len(filtered_videos)} videos with status: {status}")
    
    # Get file paths
    video_paths = []
    for video in filtered_videos:
        file_path = video.get('file_path', '')
        if file_path and os.path.exists(file_path):
            video_paths.append(file_path)
        else:
            print(f"⚠️ Video file not found: {video.get('filename', 'Unknown')}")
    
    if not video_paths:
        print("❌ No valid video files found")
        return
    
    # Upload videos
    orchestrator = UploadOnlyOrchestrator()
    if await orchestrator.initialize():
        await orchestrator.upload_videos(video_paths)
        await orchestrator.cleanup()


async def upload_by_filename_pattern(pattern: str):
    """Upload videos matching filename pattern"""
    print(f"📤 Uploading videos matching pattern: {pattern}")
    
    # Scan finished_videos folder
    finished_videos_dir = Path("assets/finished_videos")
    if not finished_videos_dir.exists():
        print(f"❌ Finished videos directory not found: {finished_videos_dir}")
        return
    
    # Find matching files
    video_files = []
    for video_path in finished_videos_dir.rglob("*.mp4"):
        if pattern.lower() in video_path.name.lower():
            video_files.append(str(video_path))
    
    if not video_files:
        print(f"ℹ️ No videos found matching pattern: {pattern}")
        return
    
    print(f"📁 Found {len(video_files)} videos matching pattern")
    
    # Upload videos
    orchestrator = UploadOnlyOrchestrator()
    if await orchestrator.initialize():
        await orchestrator.upload_videos(video_files)
        await orchestrator.cleanup()


async def upload_recent_videos(hours: int = 24):
    """Upload videos modified in the last N hours"""
    import time
    from datetime import datetime, timedelta
    
    print(f"📤 Uploading videos modified in the last {hours} hours")
    
    # Calculate cutoff time
    cutoff_time = time.time() - (hours * 3600)
    
    # Scan finished_videos folder
    finished_videos_dir = Path("assets/finished_videos")
    if not finished_videos_dir.exists():
        print(f"❌ Finished videos directory not found: {finished_videos_dir}")
        return
    
    # Find recent files
    video_files = []
    for video_path in finished_videos_dir.rglob("*.mp4"):
        if video_path.stat().st_mtime > cutoff_time:
            video_files.append(str(video_path))
    
    if not video_files:
        print(f"ℹ️ No videos found modified in the last {hours} hours")
        return
    
    print(f"📁 Found {len(video_files)} recent videos")
    
    # Upload videos
    orchestrator = UploadOnlyOrchestrator()
    if await orchestrator.initialize():
        await orchestrator.upload_videos(video_files)
        await orchestrator.cleanup()


async def list_uploadable_videos():
    """List all videos that can be uploaded"""
    print("📋 Listing uploadable videos...")
    
    # Get all videos from database
    all_videos = await db_manager.get_all_videos()
    
    print(f"\n📊 Database contains {len(all_videos)} videos:")
    print("-" * 80)
    print(f"{'Filename':<40} {'Status':<15} {'File Exists':<12} {'Path'}")
    print("-" * 80)
    
    for video in all_videos:
        filename = video.get('filename', 'Unknown')
        status = video.get('upload_status', 'PENDING')
        file_path = video.get('file_path', '')
        file_exists = "✅ Yes" if file_path and os.path.exists(file_path) else "❌ No"
        path_display = file_path if file_path else "N/A"
        
        print(f"{filename:<40} {status:<15} {file_exists:<12} {path_display}")
    
    # Also check finished_videos folder
    finished_videos_dir = Path("assets/finished_videos")
    if finished_videos_dir.exists():
        folder_videos = list(finished_videos_dir.rglob("*.mp4"))
        print(f"\n📁 Finished videos folder contains {len(folder_videos)} videos:")
        print("-" * 80)
        for video_path in folder_videos:
            print(f"  {video_path}")


async def main():
    """Main function for specific upload operations"""
    parser = argparse.ArgumentParser(description="Upload specific videos with advanced options")
    parser.add_argument("--status", help="Upload videos with specific status (PENDING, COMPLETED, FAILED)")
    parser.add_argument("--pattern", help="Upload videos matching filename pattern")
    parser.add_argument("--recent", type=int, help="Upload videos modified in the last N hours")
    parser.add_argument("--list", action="store_true", help="List all uploadable videos")
    parser.add_argument("--videos", nargs="+", help="Specific video files to upload")
    
    args = parser.parse_args()
    
    print("📤 Upload Specific Videos")
    print("=" * 60)
    
    try:
        # Initialize database
        print("📊 Initializing database...")
        await db_manager.initialize()
        print("✅ Database initialized")
        
        if args.list:
            await list_uploadable_videos()
        elif args.status:
            await upload_by_status(args.status)
        elif args.pattern:
            await upload_by_filename_pattern(args.pattern)
        elif args.recent:
            await upload_recent_videos(args.recent)
        elif args.videos:
            # Use the main upload script for specific videos
            from upload_only import main as upload_main
            import sys
            sys.argv = ['upload_only.py', '--videos'] + args.videos
            await upload_main()
        else:
            print("❌ Please specify an upload option:")
            print("  --status PENDING     Upload videos with PENDING status")
            print("  --pattern 'rick'     Upload videos with 'rick' in filename")
            print("  --recent 24          Upload videos modified in last 24 hours")
            print("  --list               List all uploadable videos")
            print("  --videos file1.mp4   Upload specific video files")
        
        # Cleanup
        await db_manager.close()
        
    except KeyboardInterrupt:
        print("\n⏹️ Upload process interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during upload process: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
