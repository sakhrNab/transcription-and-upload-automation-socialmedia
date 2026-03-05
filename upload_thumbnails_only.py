#!/usr/bin/env python3
"""
Upload Thumbnails Only Script
Uploads thumbnails to both Google Drive and AIWaverider Drive
"""

import sys
import os
import asyncio
from pathlib import Path

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.processors.upload_processor import UploadProcessor
from core.processors.aiwaverider_processor import AIWaveriderProcessor
from system.new_database import new_db_manager as db_manager
from system.processor_logger import processor_logger as logger


async def upload_thumbnails_to_aiwaverider(aiwaverider_processor):
    """Upload thumbnails to AIWaverider Drive following the same pattern as video_processor"""
    try:
        print("🖼️ Starting AIWaverider thumbnail upload process...")
        
        # Get thumbnails from file system (like video_processor does)
        thumbnails_dir = Path("assets/downloads/thumbnails")
        if not thumbnails_dir.exists():
            print("ℹ️ No thumbnails directory found")
            return True
        
        # Find all image files
        image_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
        thumbnail_files = []
        for ext in image_extensions:
            thumbnail_files.extend(thumbnails_dir.glob(f"*{ext}"))
        
        if not thumbnail_files:
            print("ℹ️ No thumbnail files found in directory")
            return True
        
        print(f"📁 Found {len(thumbnail_files)} thumbnail files in directory")
        
        # Get existing files from AIWaverider Drive to avoid duplicates
        existing_thumbnails = await aiwaverider_processor._get_existing_files(aiwaverider_processor.thumbnail_folder_path)
        print(f"📁 Found {len(existing_thumbnails)} existing thumbnails on AIWaverider Drive")
        
        # Prepare upload tasks for thumbnails only
        upload_tasks = []
        uploaded_count = 0
        failed_count = 0
        
        for file_path in thumbnail_files:
            filename = file_path.name
            
            if not file_path.exists():
                print(f"⚠️ Thumbnail file not found: {filename}")
                failed_count += 1
                continue
            
            # Extract video_id from filename (last part before extension)
            video_id = filename.split('_')[-1].replace('.webp', '').replace('.jpg', '').replace('.png', '').replace('.jpeg', '')
            
            # Check if already uploaded to AIWaverider by looking in database
            upload_records = await db_manager.get_upload_tracking_by_video_id(video_id, 'thumbnail')
            
            # Check if already uploaded to AIWaverider
            already_uploaded = any(
                record.get('aiwaverider_upload_status') == 'COMPLETED' 
                for record in upload_records
            )
            
            if filename not in existing_thumbnails and not already_uploaded:
                upload_tasks.append(('thumbnail', str(file_path), {'video_id': video_id, 'filename': filename}))
                print(f"📤 Queued for upload: {filename}")
            else:
                print(f"⏭️ Skipping duplicate: {filename}")
        
        if not upload_tasks:
            print("ℹ️ No new thumbnails to upload to AIWaverider Drive")
            return True
        
        print(f"📤 Uploading {len(upload_tasks)} thumbnails to AIWaverider Drive in parallel...")
        
        # Upload thumbnails in parallel with controlled concurrency
        optimal_concurrency = min(5, len(upload_tasks))  # Limit concurrent uploads
        semaphore = asyncio.Semaphore(optimal_concurrency)
        
        async def upload_single_aiwaverider_thumbnail(file_type, file_path, file_data):
            async with semaphore:
                try:
                    filename = os.path.basename(file_path)
                    print(f"📤 Uploading thumbnail: {filename}")
                    
                    # Use the existing upload method from aiwaverider_processor
                    result = await aiwaverider_processor._upload_thumbnail_to_aiwaverider(file_path)
                    
                    if result:
                        print(f"✅ AIWaverider thumbnail upload successful: {filename}")
                        
                        # Update database with upload status
                        video_id = file_data.get('video_id', '')
                        if video_id:
                            await db_manager.upsert_upload_tracking({
                                'video_id': video_id,
                                'filename': filename,
                                'file_path': file_path,
                                'file_type': 'thumbnail',
                                'aiwaverider_upload_status': 'COMPLETED',
                                'upload_attempts': 1
                            })
                        return True
                    else:
                        print(f"❌ AIWaverider thumbnail upload failed: {filename}")
                        return False
                        
                except Exception as e:
                    print(f"❌ Error uploading thumbnail {filename}: {str(e)}")
                    return False
        
        # Execute all uploads in parallel
        print(f"Starting parallel AIWaverider uploads with {optimal_concurrency} concurrent workers")
        results = await asyncio.gather(*[upload_single_aiwaverider_thumbnail(file_type, file_path, file_data) for file_type, file_path, file_data in upload_tasks])
        
        # Count results
        uploaded_count = sum(1 for result in results if result)
        failed_count = len(results) - uploaded_count
        
        print(f"\n📊 AIWaverider thumbnail upload summary:")
        print(f"  ✅ Successful: {uploaded_count}")
        print(f"  ❌ Failed: {failed_count}")
        
        return failed_count == 0
        
    except Exception as e:
        print(f"❌ Error in AIWaverider thumbnail upload: {str(e)}")
        return False


async def upload_thumbnails_only():
    """Upload thumbnails to both Google Drive and AIWaverider Drive"""
    print("🖼️ Starting Thumbnail Upload Process")
    print("=" * 50)
    
    try:
        # Initialize database
        print("📊 Initializing database...")
        await db_manager.initialize()
        print("✅ Database initialized")
        
        # Initialize processors
        print("🔧 Initializing processors...")
        upload_processor = UploadProcessor()
        aiwaverider_processor = AIWaveriderProcessor()
        
        # Initialize processors
        upload_init = await upload_processor.initialize()
        aiwaverider_init = await aiwaverider_processor.initialize()
        
        if not upload_init:
            print("❌ Failed to initialize Google Drive upload processor")
            return False
            
        if not aiwaverider_init:
            print("❌ Failed to initialize AIWaverider upload processor")
            return False
        
        print("✅ All processors initialized")
        
        # Step 1 & 2: Upload to both platforms in parallel
        print("\n📤 Step 1 & 2: Uploading thumbnails to both platforms in parallel...")
        
        # Run both uploads simultaneously
        gdrive_task = upload_processor.process_thumbnails()
        aiwaverider_task = upload_thumbnails_to_aiwaverider(aiwaverider_processor)
        
        # Wait for both to complete
        gdrive_success, aiwaverider_success = await asyncio.gather(gdrive_task, aiwaverider_task)
        
        if gdrive_success:
            print("✅ Google Drive thumbnail upload completed successfully")
        else:
            print("❌ Google Drive thumbnail upload had issues")
        
        if aiwaverider_success:
            print("✅ AIWaverider Drive thumbnail upload completed successfully")
        else:
            print("❌ AIWaverider Drive thumbnail upload had issues")
        
        # Step 3: Update sheets
        print("\n📊 Step 3: Updating Google Sheets...")
        from core.processors.sheets_processor import SheetsProcessor
        sheets_processor = SheetsProcessor()
        await sheets_processor.initialize()
        
        sheets_success = await sheets_processor.update_master_sheet()
        if sheets_success:
            print("✅ Google Sheets updated successfully")
        else:
            print("❌ Google Sheets update failed")
        
        # Cleanup
        print("\n🧹 Cleaning up...")
        await upload_processor.cleanup()
        await aiwaverider_processor.cleanup()
        await sheets_processor.cleanup()
        await db_manager.close()
        
        # Final summary
        print("\n" + "=" * 50)
        print("📊 Thumbnail Upload Summary:")
        print(f"  Google Drive: {'✅ Success' if gdrive_success else '❌ Failed'}")
        print(f"  AIWaverider Drive: {'✅ Success' if aiwaverider_success else '❌ Failed'}")
        print(f"  Google Sheets: {'✅ Success' if sheets_success else '❌ Failed'}")
        
        overall_success = gdrive_success and aiwaverider_success and sheets_success
        if overall_success:
            print("\n🎉 All thumbnail uploads completed successfully!")
        else:
            print("\n⚠️ Some thumbnail uploads had issues. Check the logs above.")
        
        return overall_success
        
    except Exception as e:
        print(f"\n❌ Error during thumbnail upload: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main function"""
    print("🚀 Thumbnail Upload Only Script")
    print("This script will upload thumbnails to both Google Drive and AIWaverider Drive")
    print()
    
    print("🔍 Debug: Starting main function...")
    
    # Check if thumbnails folder exists
    thumbnails_dir = Path("assets/downloads/thumbnails")
    if not thumbnails_dir.exists():
        print(f"❌ Thumbnails directory not found: {thumbnails_dir}")
        print("Please ensure thumbnails are in the correct location.")
        return False
    
    # Count thumbnails
    thumbnail_files = list(thumbnails_dir.glob("*"))
    image_files = [f for f in thumbnail_files if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.gif']]
    
    print(f"📁 Found {len(image_files)} thumbnail files in {thumbnails_dir}")
    
    if not image_files:
        print("❌ No thumbnail files found to upload")
        return False
    
    print(f"📋 Thumbnail files to upload:")
    for i, file in enumerate(image_files[:10], 1):  # Show first 10
        print(f"  {i}. {file.name}")
    if len(image_files) > 10:
        print(f"  ... and {len(image_files) - 10} more files")
    
    print()
    
    # Confirm before proceeding
    try:
        confirm = input("Do you want to proceed with thumbnail upload? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("❌ Upload cancelled by user")
            return False
    except KeyboardInterrupt:
        print("\n❌ Upload cancelled by user")
        return False
    
    # Run the upload process
    success = await upload_thumbnails_only()
    
    if success:
        print("\n🎉 Thumbnail upload process completed successfully!")
        return True
    else:
        print("\n❌ Thumbnail upload process failed. Check the logs above for details.")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️ Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        sys.exit(1)
