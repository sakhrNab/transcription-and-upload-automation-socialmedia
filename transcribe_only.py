#!/usr/bin/env python3
"""
Transcribe-Only Script for Social Media Processor
Transcribes downloaded videos using GPU acceleration and updates database/sheets
Does NOT perform downloads or uploads - only transcription
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path
from typing import List
from datetime import datetime

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.orchestrator import SocialMediaOrchestrator
from system.new_database import new_db_manager as db_manager


async def transcribe_only(video_ids: List[str] = None, max_videos: int = None, all_pending: bool = False):
    """Transcribe-only function that follows the same flow but skips downloads and uploads"""
    print("🎤 Starting Transcribe-Only Mode")
    print("=" * 60)
    print("📁 This mode will:")
    print("   • Find downloaded videos in database")
    print("   • Transcribe using GPU acceleration")
    print("   • Generate smart names")
    print("   • Update database and sheets")
    print("   • Skip downloads and uploads")
    print()
    
    try:
        # Initialize database
        print("📊 Initializing database...")
        await db_manager.initialize()
        print("✅ Database initialized")
        
        # Create orchestrator
        print("🎯 Creating orchestrator...")
        orchestrator = SocialMediaOrchestrator()
        
        # Initialize only the processors we need for transcribe-only mode
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
        
        # Get videos to transcribe
        videos_to_transcribe = await get_videos_for_transcription(video_ids, max_videos, all_pending)
        
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
        
        # Show final status
        print("\n📊 Final Status:")
        print(f"Video Processor: {orchestrator.video_processor.status}")
        print(f"Sheets Processor: {orchestrator.sheets_processor.status}")
        print(f"Transcripts Sheets Processor: {orchestrator.transcripts_sheets_processor.status}")
        
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


async def find_video_in_file_system(video_id: str) -> dict:
    """Find video in file system by video_id and create database entry"""
    try:
        # Check the downloads/videos directory
        videos_dir = Path("assets/downloads/videos")
        if not videos_dir.exists():
            print(f"  📁 Videos directory not found: {videos_dir}")
            return None
        
        # Look for video files containing the video_id
        video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.webm']
        found_files = []
        
        for ext in video_extensions:
            # Look for files that contain the video_id in the filename
            pattern = f"*{video_id}*{ext}"
            matching_files = list(videos_dir.glob(pattern))
            found_files.extend(matching_files)
        
        if not found_files:
            print(f"  ❌ No video files found with ID: {video_id}")
            return None
        
        # Use the first matching file
        video_file = found_files[0]
        print(f"  📁 Found video file: {video_file.name}")
        
        # Extract metadata from filename
        filename = video_file.name
        file_path = str(video_file)
        
        # Try to extract title and other info from filename
        # Format is usually: "number_title_videoID.ext"
        parts = filename.replace(ext, '').split('_')
        if len(parts) >= 3:
            title = '_'.join(parts[1:-1])  # Everything between first and last part
        else:
            title = filename.replace(ext, '')
        
        # Get file size
        file_size_mb = video_file.stat().st_size / (1024 * 1024)
        
        # Create video data structure
        video_data = {
            'video_id': video_id,
            'filename': filename,
            'file_path': file_path,
            'title': title,
            'description': f'Video found in file system: {filename}',
            'username': 'unknown',
            'platform': 'unknown',
            'duration': 0,  # Will be updated during processing
            'video_file_size_mb': round(file_size_mb, 2),
            'transcription_status': 'PENDING',
            'transcription_text': '',
            'smart_name': '',
            'transcript_file_path': '',
            'audio_file_path': '',
            'thumbnail_file_path': '',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        print(f"  ✅ Created video data for: {filename}")
        return video_data
        
    except Exception as e:
        print(f"  ❌ Error finding video in file system: {str(e)}")
        return None


async def get_videos_for_transcription(video_ids: List[str] = None, max_videos: int = None, all_pending: bool = False) -> List[dict]:
    """Get videos that need transcription from database and file system"""
    try:
        if all_pending:
            # Get all videos with PENDING transcription status
            print("🔍 Finding all videos with PENDING transcription status...")
            all_videos = await db_manager.get_all_video_transcripts()
            pending_videos = [
                video for video in all_videos 
                if video.get('transcription_status') == 'PENDING'
            ]
            
            if max_videos:
                pending_videos = pending_videos[:max_videos]
                print(f"📝 Limited to first {max_videos} pending videos")
            
            return pending_videos
            
        elif video_ids:
            # Get specific videos by video_id - check both database and file system
            print(f"🔍 Finding specific videos: {video_ids}")
            videos_to_transcribe = []
            for video_id in video_ids:
                # First check database
                video_data = await db_manager.get_video_transcript_by_id(video_id)
                if video_data:
                    if video_data.get('transcription_status') != 'COMPLETED':
                        videos_to_transcribe.append(video_data)
                        print(f"✅ Found video in database for transcription: {video_data.get('filename')} (ID: {video_id})")
                    else:
                        print(f"⚠️ Video {video_id} already transcribed (status: {video_data.get('transcription_status')})")
                else:
                    # Video not in database, check file system
                    print(f"🔍 Video {video_id} not found in database, checking file system...")
                    file_system_video = await find_video_in_file_system(video_id)
                    if file_system_video:
                        # Add to database first
                        print(f"📝 Adding video to database: {file_system_video.get('filename')} (ID: {video_id})")
                        await db_manager.upsert_video_transcript(file_system_video)
                        videos_to_transcribe.append(file_system_video)
                        print(f"✅ Found video in file system for transcription: {file_system_video.get('filename')} (ID: {video_id})")
                    else:
                        print(f"❌ Video {video_id} not found in database or file system")
            
            return videos_to_transcribe
            
        else:
            # Get all videos that need transcription
            print("🔍 Finding all videos that need transcription...")
            all_videos = await db_manager.get_all_video_transcripts()
            videos_to_transcribe = [
                video for video in all_videos 
                if video.get('transcription_status') != 'COMPLETED'
            ]
            
            if max_videos:
                videos_to_transcribe = videos_to_transcribe[:max_videos]
                print(f"📝 Limited to first {max_videos} videos")
            
            return videos_to_transcribe
            
    except Exception as e:
        print(f"❌ Error getting videos for transcription: {str(e)}")
        return []


async def update_sheets_without_uploads(sheets_processor) -> bool:
    """Update sheets without uploading any files - transcription only mode"""
    try:
        print("  📊 Updating sheets without uploads...")
        
        # Get all videos and thumbnails from database
        videos = await db_manager.get_all_video_transcripts()
        thumbnails = await db_manager.get_all_thumbnails()
        
        if not videos:
            print("  📭 No videos found to update in master sheet")
            return True
        
        # Convert to sheet format (without uploads)
        content_list = await prepare_sheet_data_without_uploads(videos, thumbnails)
        
        if not content_list:
            print("  📭 No data to update in master sheet")
            return True
        
        # Update the sheet (without uploads)
        success = await update_sheet_without_uploads(sheets_processor, content_list)
        
        if success:
            print(f"  ✅ Sheets updated successfully with {len(content_list)} entries")
            return True
        else:
            print("  ❌ Failed to update master sheet")
            return False
        
    except Exception as e:
        print(f"  ❌ Error updating sheets: {str(e)}")
        return False


async def prepare_sheet_data_without_uploads(videos: List[dict], thumbnails: List[dict]) -> List[dict]:
    """Prepare data for sheet update without uploads"""
    try:
        content_list = []
        
        # Process videos
        for video in videos:
            # Find matching thumbnail
            video_filename = video.get('filename', '')
            base_name = os.path.splitext(video_filename)[0]
            matching_thumbnail = None
            
            for thumbnail in thumbnails:
                if base_name in thumbnail.get('filename', '') or base_name in thumbnail.get('video_filename', ''):
                    matching_thumbnail = thumbnail
                    break
            
            # Prepare content info (NO UPLOADS)
            content_info = {
                'drive_id': video.get('drive_id', ''),
                'filename': video_filename,
                'video_name': video.get('smart_name', video_filename),
                'thumbnail_name': matching_thumbnail.get('filename', '') if matching_thumbnail else '',
                'file_path_drive': f"https://drive.google.com/file/d/{video.get('drive_id', '')}/view" if video.get('drive_id') else '',
                'upload_time': video.get('updated_at', ''),
                'upload_status_youtube1': 'PENDING',
                'upload_status_youtube_aiwaverider1': 'PENDING',
                'upload_status_youtube_aiwaverider8': 'PENDING',
                'upload_status_youtube1_aiwaverider8_2': 'PENDING',
                'upload_status_insta_ai.waverider': 'PENDING',
                'upload_status_insta_ai.wave.rider': 'PENDING',
                'upload_status_insta_ai.uprise': 'PENDING',
                'upload_status_tiktok_ai.wave.rider': 'PENDING',
                'upload_status_tiktok_ai.waverider': 'PENDING',
                'upload_status_tiktok_aiwaverider9': 'PENDING',
                'upload_status_thumbnail': 'UPLOADED' if matching_thumbnail and matching_thumbnail.get('drive_id') else 'PENDING',
                'thumbnail_image': '',  # NO IMAGE UPLOADS
                'transcription_status': video.get('transcription_status', 'PENDING'),
                'transcript': video.get('transcription_text', '')
            }
            content_list.append(content_info)
        
        return content_list
        
    except Exception as e:
        print(f"  ❌ Error preparing sheet data: {str(e)}")
        return []


async def update_sheet_without_uploads(sheets_processor, content_list: List[dict]) -> bool:
    """Update the Google Sheet with the prepared data without uploads"""
    try:
        if not sheets_processor.service:
            print("  📝 No Google Sheets service available, saving to local backup")
            for content_info in content_list:
                filename = content_info['filename']
                sheets_processor.local_data['rows'][filename] = content_info
            sheets_processor._save_local_backup()
            return True
        
        # First, cleanup any existing duplicates
        print("  🧹 Cleaning up duplicate entries in Google Sheets...")
        await sheets_processor._cleanup_duplicates()
        
        # Update the sheet with new data (NO UPLOADS)
        print(f"  📊 Updating Google Sheet with {len(content_list)} entries")
        
        # Separate existing and new entries
        existing_entries = []
        new_entries = []
        
        for content_info in content_list:
            filename = content_info['filename']
            if filename in sheets_processor.local_data['rows']:
                existing_entries.append(content_info)
            else:
                new_entries.append(content_info)
        
        # Update existing entries individually
        for content_info in existing_entries:
            await sheets_processor._update_single_entry(content_info)
        
        # Add new entries in batch
        if new_entries:
            await sheets_processor._add_new_entries(new_entries)
        
        # Save tracking data locally
        await sheets_processor._save_tracking_data_locally(content_list)
        
        print("  ✅ Google Sheet updated successfully")
        return True
        
    except Exception as e:
        print(f"  ❌ Error updating sheet: {str(e)}")
        return False


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
                    
                    # Update sheets after transcription (NO UPLOADS)
                    print(f"  📊 Updating sheets for video {i}...")
                    sheets_success = await update_sheets_without_uploads(orchestrator.sheets_processor)
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
    parser = argparse.ArgumentParser(description='Transcribe-Only Mode - Social Media Processor')
    parser.add_argument('--video-ids', nargs='+', help='Specific video IDs to transcribe')
    parser.add_argument('--max-videos', type=int, help='Maximum number of videos to process (default: no limit)')
    parser.add_argument('--all-pending', action='store_true', help='Transcribe all videos with PENDING status')
    parser.add_argument('--test', action='store_true', help='Run test mode with a single video')
    args = parser.parse_args()
    
    if args.test:
        print("🧪 Running in test mode...")
        # Test with a single video ID
        test_video_ids = ["dQw4w9WgXcQ"]
        asyncio.run(transcribe_only(video_ids=test_video_ids, max_videos=1))
    else:
        try:
            # Determine transcription mode
            if args.video_ids:
                # Specific video IDs provided
                print(f"📝 Processing specific video IDs: {args.video_ids}")
                asyncio.run(transcribe_only(video_ids=args.video_ids, max_videos=args.max_videos))
            elif args.all_pending:
                # All pending videos
                print("📝 Processing all videos with PENDING transcription status")
                asyncio.run(transcribe_only(all_pending=True, max_videos=args.max_videos))
            else:
                # All videos that need transcription
                print("📝 Processing all videos that need transcription")
                asyncio.run(transcribe_only(max_videos=args.max_videos))
                
        except KeyboardInterrupt:
            print("\n⏹️  Process interrupted by user")
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            sys.exit(1)

