#!/usr/bin/env python3
"""
Advanced Transcribe-Specific Script for Social Media Processor
Advanced filtering and selection options for video transcription
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path
from typing import List

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.orchestrator import SocialMediaOrchestrator
from system.new_database import new_db_manager as db_manager


async def transcribe_specific(
    video_ids: List[str] = None, 
    max_videos: int = None, 
    all_pending: bool = False,
    status_filter: str = None,
    pattern: str = None,
    recent: bool = False,
    list_only: bool = False
):
    """Advanced transcription with filtering options"""
    print("🎤 Starting Advanced Transcribe Mode")
    print("=" * 60)
    
    try:
        # Initialize database
        print("📊 Initializing database...")
        await db_manager.initialize()
        print("✅ Database initialized")
        
        if list_only:
            # Just list videos and exit
            await list_videos_for_transcription(video_ids, status_filter, pattern, recent, max_videos)
            return True
        
        # Create orchestrator
        print("🎯 Creating orchestrator...")
        orchestrator = SocialMediaOrchestrator()
        
        # Initialize processors
        print("🔧 Initializing processors...")
        init_results = await asyncio.gather(
            orchestrator.video_processor.initialize(),
            orchestrator.sheets_processor.initialize(),
            orchestrator.transcripts_sheets_processor.initialize(),
            return_exceptions=True
        )
        
        # Check initialization results
        processor_names = ["Video", "Sheets", "TranscriptsSheets"]
        for i, result in enumerate(init_results):
            if isinstance(result, Exception):
                print(f"❌ {processor_names[i]} processor failed: {result}")
                return False
            elif not result:
                print(f"⚠️ {processor_names[i]} processor initialization returned False")
                return False
            else:
                print(f"✅ {processor_names[i]} processor ready")
        
        print("\n🎤 Starting transcription pipeline...")
        
        # Get videos to transcribe with filtering
        videos_to_transcribe = await get_filtered_videos_for_transcription(
            video_ids, max_videos, all_pending, status_filter, pattern, recent
        )
        
        if not videos_to_transcribe:
            print("📭 No videos found for transcription")
            return True
        
        print(f"📝 Found {len(videos_to_transcribe)} videos to transcribe")
        
        # Process transcriptions
        success = await process_transcriptions_only(orchestrator, videos_to_transcribe)
        
        if success:
            print("\n✅ Transcription processing completed successfully!")
        else:
            print("\n❌ Transcription processing completed with errors")
        
        # Cleanup
        print("\n🧹 Cleaning up...")
        await asyncio.gather(
            orchestrator.video_processor.cleanup(),
            orchestrator.sheets_processor.cleanup(),
            orchestrator.transcripts_sheets_processor.cleanup(),
            return_exceptions=True
        )
        
        await db_manager.close()
        print("✅ Cleanup completed")
        
        return success
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def list_videos_for_transcription(
    video_ids: List[str] = None, 
    status_filter: str = None, 
    pattern: str = None, 
    recent: bool = False, 
    max_videos: int = None
):
    """List videos that would be transcribed"""
    try:
        print("📋 Listing videos for transcription...")
        
        # Get all videos
        all_videos = await db_manager.get_all_video_transcripts()
        
        # Apply filters
        filtered_videos = []
        
        for video in all_videos:
            # Status filter
            if status_filter and video.get('transcription_status') != status_filter:
                continue
            
            # Pattern filter
            if pattern and pattern.lower() not in video.get('filename', '').lower():
                continue
            
            # Video ID filter
            if video_ids and video.get('video_id') not in video_ids:
                continue
            
            filtered_videos.append(video)
        
        # Sort by recent if requested
        if recent:
            filtered_videos.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Apply max limit
        if max_videos:
            filtered_videos = filtered_videos[:max_videos]
        
        # Display results
        print(f"\n📊 Found {len(filtered_videos)} videos:")
        print("-" * 80)
        print(f"{'#':<3} {'Status':<12} {'Filename':<30} {'Video ID':<15} {'Title':<20}")
        print("-" * 80)
        
        for i, video in enumerate(filtered_videos, 1):
            status = video.get('transcription_status', 'UNKNOWN')
            filename = video.get('filename', 'Unknown')[:30]
            video_id = video.get('video_id', 'Unknown')[:15]
            title = video.get('title', 'Unknown')[:20]
            
            print(f"{i:<3} {status:<12} {filename:<30} {video_id:<15} {title:<20}")
        
        print("-" * 80)
        
    except Exception as e:
        print(f"❌ Error listing videos: {str(e)}")


async def get_filtered_videos_for_transcription(
    video_ids: List[str] = None, 
    max_videos: int = None, 
    all_pending: bool = False,
    status_filter: str = None,
    pattern: str = None,
    recent: bool = False
) -> List[dict]:
    """Get filtered videos for transcription"""
    try:
        # Get all videos
        all_videos = await db_manager.get_all_video_transcripts()
        
        # Apply filters
        filtered_videos = []
        
        for video in all_videos:
            # Status filter
            if status_filter and video.get('transcription_status') != status_filter:
                continue
            
            # Pattern filter
            if pattern and pattern.lower() not in video.get('filename', '').lower():
                continue
            
            # Video ID filter
            if video_ids and video.get('video_id') not in video_ids:
                continue
            
            # Skip completed if not specifically requested
            if not all_pending and video.get('transcription_status') == 'COMPLETED':
                continue
            
            filtered_videos.append(video)
        
        # Sort by recent if requested
        if recent:
            filtered_videos.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Apply max limit
        if max_videos:
            filtered_videos = filtered_videos[:max_videos]
        
        return filtered_videos
        
    except Exception as e:
        print(f"❌ Error getting filtered videos: {str(e)}")
        return []


async def process_transcriptions_only(orchestrator, videos_to_transcribe: List[dict]) -> bool:
    """Process transcriptions using the real video processor logic"""
    try:
        print(f"\n🎤 Starting transcription processing for {len(videos_to_transcribe)} videos...")
        
        # Process each video individually for better control
        successful_transcriptions = 0
        failed_transcriptions = 0
        
        for i, video_data in enumerate(videos_to_transcribe, 1):
            video_id = video_data.get('video_id', '')
            filename = video_data.get('filename', '')
            file_path = video_data.get('file_path', '')
            
            print(f"\n🎤 Processing video {i}/{len(videos_to_transcribe)}: {filename}")
            
            try:
                # Check if video file exists
                if not os.path.exists(file_path):
                    print(f"  ❌ Video file not found: {file_path}")
                    failed_transcriptions += 1
                    continue
                
                # Check if already transcribed
                if video_data.get('transcription_status') == 'COMPLETED':
                    print(f"  ⚠️ Video already transcribed, skipping")
                    continue
                
                print(f"  🎤 Starting transcription for video {i}...")
                
                # Use the real transcription logic from video_processor
                success = await transcribe_single_video(
                    orchestrator.video_processor, 
                    video_data, 
                    i
                )
                
                if success:
                    print(f"  ✅ Video {i} transcribed successfully")
                    successful_transcriptions += 1
                    
                    # Update sheets after transcription
                    print(f"  📊 Updating sheets for video {i}...")
                    sheets_success = await orchestrator.sheets_processor.update_master_sheet()
                    transcripts_success = await orchestrator.transcripts_sheets_processor.update_transcripts_sheet()
                    
                    if sheets_success and transcripts_success:
                        print(f"  ✅ Sheets updated for video {i}")
                    else:
                        print(f"  ⚠️ Sheets update failed for video {i}")
                        
                else:
                    print(f"  ❌ Video {i} transcription failed")
                    failed_transcriptions += 1
                    
            except Exception as e:
                print(f"  ❌ Error processing video {i}: {str(e)}")
                failed_transcriptions += 1
                continue
        
        # Summary
        print(f"\n📊 Transcription Summary:")
        print(f"  ✅ Successful transcriptions: {successful_transcriptions}")
        print(f"  ❌ Failed transcriptions: {failed_transcriptions}")
        print(f"  📈 Success rate: {(successful_transcriptions / len(videos_to_transcribe)) * 100:.1f}%")
        
        return successful_transcriptions > 0
        
    except Exception as e:
        print(f"❌ Error in transcription processing: {str(e)}")
        return False


async def transcribe_single_video(video_processor, video_data: dict, index: int) -> bool:
    """Transcribe a single video using the real video processor logic"""
    try:
        file_path = video_data.get('file_path', '')
        video_id = video_data.get('video_id', '')
        filename = video_data.get('filename', '')
        
        print(f"    🎬 Converting video to audio...")
        
        # Step 1: Convert video to audio
        audio_path = await video_processor._convert_video_to_audio(file_path, index)
        if not audio_path or not os.path.exists(audio_path):
            print(f"    ❌ Audio conversion failed")
            return False
        
        print(f"    🎤 Transcribing audio with GPU acceleration...")
        
        # Step 2: Transcribe audio
        transcript = await video_processor._transcribe_audio_with_whisper(audio_path, index)
        if not transcript:
            print(f"    ❌ Transcription failed")
            return False
        
        print(f"    📝 Generating smart name...")
        
        # Step 3: Generate smart name
        smart_name = await video_processor._generate_smart_video_name(
            video_data.get('title', ''), 
            video_data.get('description', ''),
            index
        )
        
        print(f"    💾 Updating database...")
        
        # Step 4: Update database with transcription
        await video_processor._update_video_transcription(
            video_id, 
            transcript, 
            smart_name, 
            file_path, 
            video_data.get('thumbnail_file_path', ''),
            video_data
        )
        
        print(f"    🧹 Cleaning up audio file...")
        
        # Step 5: Clean up audio file
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
                print(f"    ✅ Cleaned up audio file")
        except Exception as e:
            print(f"    ⚠️ Error cleaning up audio file: {e}")
        
        return True
        
    except Exception as e:
        print(f"    ❌ Error transcribing video: {str(e)}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Advanced Transcribe Mode - Social Media Processor')
    parser.add_argument('--video-ids', nargs='+', help='Specific video IDs to transcribe')
    parser.add_argument('--max-videos', type=int, help='Maximum number of videos to process')
    parser.add_argument('--all-pending', action='store_true', help='Transcribe all videos with PENDING status')
    parser.add_argument('--status', choices=['PENDING', 'COMPLETED', 'FAILED'], help='Filter by transcription status')
    parser.add_argument('--pattern', help='Filter by filename pattern (case-insensitive)')
    parser.add_argument('--recent', action='store_true', help='Process most recent videos first')
    parser.add_argument('--list', action='store_true', help='List videos that would be processed (dry run)')
    parser.add_argument('--test', action='store_true', help='Run test mode with a single video')
    args = parser.parse_args()
    
    if args.test:
        print("🧪 Running in test mode...")
        # Test with a single video ID
        test_video_ids = ["dQw4w9WgXcQ"]
        asyncio.run(transcribe_specific(video_ids=test_video_ids, max_videos=1))
    else:
        try:
            # Run transcription with specified options
            asyncio.run(transcribe_specific(
                video_ids=args.video_ids,
                max_videos=args.max_videos,
                all_pending=args.all_pending,
                status_filter=args.status,
                pattern=args.pattern,
                recent=args.recent,
                list_only=args.list
            ))
                
        except KeyboardInterrupt:
            print("\n⏹️  Process interrupted by user")
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            sys.exit(1)

