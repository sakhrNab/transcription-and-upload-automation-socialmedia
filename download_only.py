#!/usr/bin/env python3
"""
Download Only Script - Downloads videos without transcription or upload
Perfect for bulk downloading or testing
"""

import sys
import os
import asyncio
import argparse
from pathlib import Path
from typing import List

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.processors.video_processor import VideoProcessor
from system.new_database import new_db_manager as db_manager


async def download_videos_only(urls: List[str]):
    """Download videos only - no transcription, no upload, no sheets"""
    print("🎬 Starting Download-Only Mode")
    print("=" * 50)
    print("📥 Will download videos and extract metadata")
    print("❌ Will NOT transcribe, upload, or update sheets")
    print()
    
    try:
        # Initialize database
        print("📊 Initializing database...")
        await db_manager.initialize()
        print("✅ Database initialized")
        
        # Initialize ONLY video processor
        print("🎥 Initializing video processor...")
        video_processor = VideoProcessor()
        await video_processor.initialize()
        print("✅ Video processor ready")
        
        # Download videos only
        print(f"\n📥 Downloading {len(urls)} videos...")
        print("=" * 50)
        
        success = await video_processor.process_urls(urls)
        
        if success:
            print("\n✅ Download completed successfully!")
            print(f"📁 Videos saved to: assets/downloads/videos/")
            print(f"🖼️ Thumbnails saved to: assets/downloads/thumbnails/")
        else:
            print("\n❌ Download completed with errors")
        
        # Show final status
        print(f"\n📊 Final Status:")
        print(f"Processed: {video_processor.processed_count}")
        print(f"Failed: {video_processor.failed_count}")
        
        # Cleanup
        print("\n🧹 Cleaning up...")
        await video_processor.cleanup()
        await db_manager.close()
        print("✅ Cleanup completed")
        
        return success
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Download Videos Only - No Transcription or Upload')
    parser.add_argument('--urls', nargs='+', help='URLs to download directly')
    parser.add_argument('--urls-file', help='Text file containing URLs (one per line)')
    parser.add_argument('--linkedin', help='Single LinkedIn URL to download')
    args = parser.parse_args()
    
    try:
        # Determine URLs source
        urls = []
        
        if args.linkedin:
            # Single LinkedIn URL
            urls = [args.linkedin]
            print(f"🔗 LinkedIn URL: {args.linkedin}")
        elif args.urls:
            # URLs provided directly via command line
            urls = args.urls
            print(f"📝 Processing {len(urls)} URLs from command line")
        elif args.urls_file:
            # URLs from file
            if os.path.exists(args.urls_file):
                with open(args.urls_file, 'r', encoding='utf-8') as f:
                    all_urls = [line.strip() for line in f if line.strip()]
                urls = all_urls
                print(f"📝 Loaded {len(all_urls)} URLs from {args.urls_file}")
            else:
                print(f"❌ URLs file not found: {args.urls_file}")
                sys.exit(1)
        else:
            # Default to urls.txt if it exists
            if os.path.exists('urls.txt'):
                with open('urls.txt', 'r', encoding='utf-8') as f:
                    all_urls = [line.strip() for line in f if line.strip()]
                urls = all_urls
                print(f"📝 Loaded {len(all_urls)} URLs from urls.txt")
            else:
                print("❌ No URLs provided. Use --urls, --urls-file, --linkedin, or create urls.txt")
                sys.exit(1)
        
        # Run download only
        asyncio.run(download_videos_only(urls))
        
    except KeyboardInterrupt:
        print("\n⏹️ Process interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)