#!/usr/bin/env python3
"""
Upload-Only Script for Social Media Processor
Uploads videos from assets/finished_videos/ to Google Drive and AIWaverider
Updates sheets and database with upload status
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path
from typing import List, Optional

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.processors.upload_processor import UploadProcessor
from core.processors.aiwaverider_processor import AIWaveriderProcessor
from core.processors.sheets_processor import SheetsProcessor
from core.processors.transcripts_sheets_processor import TranscriptsSheetsProcessor
from system.new_database import new_db_manager as db_manager


class UploadOnlyOrchestrator:
    """Orchestrator for upload-only operations"""
    
    def __init__(self):
        self.upload_processor = UploadProcessor()
        self.aiwaverider_processor = AIWaveriderProcessor()
        self.sheets_processor = SheetsProcessor()
        self.transcripts_processor = TranscriptsSheetsProcessor()
        
        self.uploaded_count = 0
        self.failed_count = 0
        
    async def initialize(self) -> bool:
        """Initialize all processors"""
        print("🔧 Initializing upload processors...")
        
        # Initialize processors
        upload_success = await self.upload_processor.initialize()
        aiwaverider_success = await self.aiwaverider_processor.initialize()
        sheets_success = await self.sheets_processor.initialize()
        transcripts_success = await self.transcripts_processor.initialize()
        
        if not all([upload_success, aiwaverider_success, sheets_success, transcripts_success]):
            print("❌ Failed to initialize some processors")
            return False
        
        print("✅ All upload processors initialized successfully")
        return True
    
    async def upload_videos(self, video_paths: Optional[List[str]] = None) -> bool:
        """Upload videos from specified paths or scan finished_videos folder"""
        try:
            print("📤 Starting video upload process...")
            
            if video_paths:
                # Upload specific videos
                print(f"📁 Uploading {len(video_paths)} specified videos...")
                for video_path in video_paths:
                    if os.path.exists(video_path):
                        await self._upload_single_video(video_path)
                    else:
                        print(f"❌ Video not found: {video_path}")
                        self.failed_count += 1
            else:
                # Scan finished_videos folder
                finished_videos_dir = Path("assets/finished_videos")
                if not finished_videos_dir.exists():
                    print(f"❌ Finished videos directory not found: {finished_videos_dir}")
                    return False
                
                # Find all MP4 files recursively
                video_files = list(finished_videos_dir.rglob("*.mp4"))
                print(f"📁 Found {len(video_files)} videos in finished_videos folder...")
                
                if not video_files:
                    print("ℹ️ No videos found to upload")
                    return True
                
                # Upload each video
                for video_path in video_files:
                    await self._upload_single_video(str(video_path))
            
            # Print summary
            print(f"\n📊 Upload Summary:")
            print(f"  ✅ Successful uploads: {self.uploaded_count}")
            print(f"  ❌ Failed uploads: {self.failed_count}")
            print(f"  📈 Success rate: {(self.uploaded_count / (self.uploaded_count + self.failed_count) * 100):.1f}%" if (self.uploaded_count + self.failed_count) > 0 else "N/A")
            
            return self.failed_count == 0
            
        except Exception as e:
            print(f"❌ Error during upload process: {str(e)}")
            return False
    
    async def _upload_single_video(self, video_path: str) -> bool:
        """Upload a single video through all processors"""
        try:
            video_name = os.path.basename(video_path)
            print(f"\n📤 Processing: {video_name}")
            
            # Check if already uploaded
            filename = os.path.basename(video_path)
            # Extract video ID from filename (remove extension and any prefixes)
            video_id = os.path.splitext(filename)[0]
            # Remove common prefixes like "01_", "02_", etc.
            if '_' in video_id and video_id[0].isdigit():
                video_id = '_'.join(video_id.split('_')[1:])
            
            is_uploaded = await db_manager.is_file_uploaded(video_id, 'video')
            
            if is_uploaded:
                print(f"⏭️ Skipping {video_name} - already uploaded")
                return True
            
            success = True
            
            # 1. Upload to Google Drive
            print(f"  📤 Uploading to Google Drive...")
            # Get Google Drive service
            drive_service = self.upload_processor._get_drive_service()
            if not drive_service:
                print(f"  ❌ Failed to initialize Google Drive service")
                success = False
            else:
                # Use the individual video upload method
                drive_result = await self.upload_processor._upload_video_file(
                    drive_service, video_path, {}
                )
                if not drive_result:
                    print(f"  ❌ Google Drive upload failed for {video_name}")
                    success = False
                else:
                    print(f"  ✅ Google Drive upload successful: {drive_result}")
            
            # 2. Upload to AIWaverider
            print(f"  📤 Uploading to AIWaverider...")
            aiwaverider_result = await self.aiwaverider_processor._upload_video_to_aiwaverider(video_path)
            if not aiwaverider_result:
                print(f"  ❌ AIWaverider upload failed for {video_name}")
                success = False
            else:
                print(f"  ✅ AIWaverider upload successful")
            
            # 3. Update sheets
            print(f"  📊 Updating sheets...")
            sheets_result = await self.sheets_processor.update_master_sheet()
            if not sheets_result:
                print(f"  ❌ Sheets update failed for {video_name}")
                success = False
            
            # 4. Update transcripts sheet
            print(f"  📝 Updating transcripts sheet...")
            transcripts_result = await self.transcripts_processor.update_transcripts_sheet()
            if not transcripts_result:
                print(f"  ❌ Transcripts sheet update failed for {video_name}")
                success = False
            
            if success:
                print(f"  ✅ {video_name} uploaded successfully!")
                self.uploaded_count += 1
            else:
                print(f"  ❌ {video_name} upload had issues")
                self.failed_count += 1
            
            return success
            
        except Exception as e:
            print(f"  ❌ Error uploading {video_name}: {str(e)}")
            self.failed_count += 1
            return False
    
    async def cleanup(self):
        """Cleanup all processors"""
        print("🧹 Cleaning up upload processors...")
        await self.upload_processor.cleanup()
        await self.aiwaverider_processor.cleanup()
        await self.sheets_processor.cleanup()
        await self.transcripts_processor.cleanup()
        await db_manager.close()
        print("✅ Cleanup completed")


async def main():
    """Main function for upload-only operations"""
    parser = argparse.ArgumentParser(description="Upload videos to Google Drive and AIWaverider")
    parser.add_argument("--videos", nargs="+", help="Specific video files to upload")
    parser.add_argument("--folder", help="Specific folder to scan for videos")
    parser.add_argument("--test", action="store_true", help="Run in test mode (dry run)")
    
    args = parser.parse_args()
    
    print("📤 Upload-Only Mode")
    print("=" * 60)
    print("📁 This mode will:")
    print("   • Upload videos to Google Drive")
    print("   • Upload videos to AIWaverider")
    print("   • Update master tracking sheet")
    print("   • Update transcripts sheet")
    print("   • Update database with upload status")
    print()
    
    if args.test:
        print("🧪 Running in test mode...")
        print("ℹ️ No actual uploads will be performed")
        return
    
    try:
        # Initialize database
        print("📊 Initializing database...")
        await db_manager.initialize()
        print("✅ Database initialized")
        
        # Create orchestrator
        print("🎯 Creating upload orchestrator...")
        orchestrator = UploadOnlyOrchestrator()
        
        # Initialize processors
        if not await orchestrator.initialize():
            print("❌ Failed to initialize upload orchestrator")
            return
        
        print("✅ Upload orchestrator ready")
        
        # Determine video paths
        video_paths = None
        if args.videos:
            video_paths = args.videos
            print(f"📁 Uploading specified videos: {len(video_paths)} files")
        elif args.folder:
            folder_path = Path(args.folder)
            if folder_path.exists():
                video_files = list(folder_path.rglob("*.mp4"))
                video_paths = [str(f) for f in video_files]
                print(f"📁 Uploading videos from folder: {args.folder} ({len(video_paths)} files)")
            else:
                print(f"❌ Folder not found: {args.folder}")
                return
        else:
            print("📁 Scanning assets/finished_videos/ for videos...")
        
        # Upload videos
        success = await orchestrator.upload_videos(video_paths)
        
        if success:
            print("\n🎉 Upload process completed successfully!")
        else:
            print("\n⚠️ Upload process completed with some issues")
        
        # Cleanup
        await orchestrator.cleanup()
        
    except KeyboardInterrupt:
        print("\n⏹️ Upload process interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during upload process: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
