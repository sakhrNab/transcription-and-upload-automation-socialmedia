#!/usr/bin/env python3
"""
Download-Only Script for Social Media Processor
Downloads videos, extracts metadata, generates thumbnails, and updates database/sheets
Does NOT perform transcription or uploads
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


async def download_only(urls: List[str] = None, max_videos: int = None):
    """Download-only function that follows the same flow but skips transcription and uploads"""
    print("📥 Starting Download-Only Mode")
    print("=" * 60)
    print("📁 This mode will:")
    print("   • Download videos from URLs")
    print("   • Extract metadata")
    print("   • Generate thumbnails")
    print("   • Update database and sheets")
    print("   • Skip transcription and uploads")
    print()
    
    try:
        # Initialize database
        print("📊 Initializing database...")
        await db_manager.initialize()
        print("✅ Database initialized")
        
        # Create orchestrator
        print("🎯 Creating orchestrator...")
        orchestrator = SocialMediaOrchestrator()
        
        # Initialize only the processors we need for download-only mode
        print("🔧 Initializing processors...")
        init_results = await asyncio.gather(
            orchestrator.video_processor.initialize(),
            orchestrator.thumbnail_processor.initialize(),
            orchestrator.sheets_processor.initialize(),
            return_exceptions=True
        )
        
        # Check initialization results
        processor_names = ["Video", "Thumbnail", "Sheets"]
        for i, result in enumerate(init_results):
            if isinstance(result, Exception):
                print(f"❌ {processor_names[i]} processor failed: {result}")
                return False
            elif not result:
                print(f"⚠️ {processor_names[i]} processor initialization returned False")
                return False
            else:
                print(f"✅ {processor_names[i]} processor ready")
        
        print("\n📥 Starting download pipeline...")
        
        # Use provided URLs or fallback
        if urls:
            sample_urls = urls
        else:
            # Fallback to urls.txt or default
            if os.path.exists("urls.txt"):
                with open("urls.txt", 'r', encoding='utf-8') as f:
                    all_urls = [line.strip() for line in f if line.strip()]
                # Apply max_videos limit if specified
                if max_videos:
                    sample_urls = all_urls[:max_videos]
                    print(f"📝 Loaded {len(all_urls)} URLs from urls.txt, processing first {max_videos}")
                else:
                    sample_urls = all_urls
                    print(f"📝 Loaded {len(sample_urls)} URLs from urls.txt")
            else:
                sample_urls = [
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Fallback sample URL
                ]
                print("📝 Using fallback sample URL")
        
        print(f"📝 Processing {len(sample_urls)} URLs...")
        
        # Process URLs with download-only mode
        success = await process_downloads_only(orchestrator, sample_urls)
        
        if success:
            print("\n✅ Download processing completed successfully!")
        else:
            print("\n❌ Download processing completed with errors")
        
        # Show final status
        print("\n📊 Final Status:")
        print(f"Video Processor: {orchestrator.video_processor.status}")
        print(f"Thumbnail Processor: {orchestrator.thumbnail_processor.status}")
        print(f"Sheets Processor: {orchestrator.sheets_processor.status}")
        
        # Cleanup
        print("\n🧹 Cleaning up...")
        await asyncio.gather(
            orchestrator.video_processor.cleanup(),
            orchestrator.thumbnail_processor.cleanup(),
            orchestrator.sheets_processor.cleanup(),
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


async def process_downloads_only(orchestrator, urls: List[str]) -> bool:
    """Process URLs in download-only mode (no transcription, no uploads)"""
    try:
        print(f"\n📥 Starting download-only processing for {len(urls)} URLs...")
        
        # Process each URL individually for better control
        successful_downloads = 0
        failed_downloads = 0
        
        for i, url in enumerate(urls, 1):
            print(f"\n📥 Processing URL {i}/{len(urls)}: {url}")
            
            try:
                # Step 1: Download video and extract metadata
                print(f"  📥 Downloading video {i}...")
                video_success = await orchestrator.video_processor.download_video_only(url, i)
                
                if video_success:
                    print(f"  ✅ Video {i} downloaded successfully")
                    successful_downloads += 1
                    
                    # Step 2: Generate thumbnail
                    print(f"  🖼️ Generating thumbnail for video {i}...")
                    thumbnail_success = await orchestrator.thumbnail_processor.process_thumbnail_for_video(i)
                    
                    if thumbnail_success:
                        print(f"  ✅ Thumbnail {i} generated successfully")
                    else:
                        print(f"  ⚠️ Thumbnail {i} generation failed")
                    
                    # Step 3: Update sheets with download status
                    print(f"  📊 Updating sheets for video {i}...")
                    sheets_success = await orchestrator.sheets_processor.update_sheets_after_download(i)
                    
                    if sheets_success:
                        print(f"  ✅ Sheets updated for video {i}")
                    else:
                        print(f"  ⚠️ Sheets update failed for video {i}")
                        
                else:
                    print(f"  ❌ Video {i} download failed")
                    failed_downloads += 1
                    
            except Exception as e:
                print(f"  ❌ Error processing video {i}: {str(e)}")
                failed_downloads += 1
                continue
        
        # Summary
        print(f"\n📊 Download Summary:")
        print(f"  ✅ Successful downloads: {successful_downloads}")
        print(f"  ❌ Failed downloads: {failed_downloads}")
        print(f"  📈 Success rate: {(successful_downloads / len(urls)) * 100:.1f}%")
        
        return successful_downloads > 0
        
    except Exception as e:
        print(f"❌ Error in download processing: {str(e)}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Download-Only Mode - Social Media Processor')
    parser.add_argument('--urls', nargs='+', help='URLs to process directly')
    parser.add_argument('--urls-file', help='Text file containing URLs (one per line)')
    parser.add_argument('--max-videos', type=int, help='Maximum number of videos to process (default: no limit)')
    parser.add_argument('--test', action='store_true', help='Run test mode')
    args = parser.parse_args()
    
    if args.test:
        print("🧪 Running in test mode...")
        # Test with a single URL
        test_urls = ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]
        asyncio.run(download_only(test_urls, max_videos=1))
    else:
        try:
            # Determine URLs source
            if args.urls:
                # URLs provided directly via command line
                urls = args.urls
                print(f"📝 Processing {len(urls)} URLs from command line")
            elif args.urls_file:
                # URLs from file
                if os.path.exists(args.urls_file):
                    with open(args.urls_file, 'r', encoding='utf-8') as f:
                        all_urls = [line.strip() for line in f if line.strip()]
                    # Apply max_videos limit if specified
                    if args.max_videos:
                        urls = all_urls[:args.max_videos]
                        print(f"📝 Loaded {len(all_urls)} URLs from {args.urls_file}, processing first {args.max_videos}")
                    else:
                        urls = all_urls
                        print(f"📝 Loaded {len(urls)} URLs from {args.urls_file}")
                else:
                    print(f"❌ URLs file not found: {args.urls_file}")
                    sys.exit(1)
            else:
                # Default to urls.txt if it exists
                if os.path.exists('urls.txt'):
                    with open('urls.txt', 'r', encoding='utf-8') as f:
                        all_urls = [line.strip() for line in f if line.strip()]
                    # Apply max_videos limit if specified
                    if args.max_videos:
                        urls = all_urls[:args.max_videos]
                        print(f"📝 Loaded {len(all_urls)} URLs from urls.txt, processing first {args.max_videos}")
                    else:
                        urls = all_urls
                        print(f"📝 Loaded {len(urls)} URLs from urls.txt")
                else:
                    print("❌ No URLs provided. Use --urls, --urls-file, or create urls.txt")
                    sys.exit(1)
            
            # Run download-only with URLs
            asyncio.run(download_only(urls, max_videos=args.max_videos))
        except KeyboardInterrupt:
            print("\n⏹️  Process interrupted by user")
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            sys.exit(1)
