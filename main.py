#!/usr/bin/env python3
"""
Main Entry Point for Social Media Processor
Now using the new modular architecture
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


async def main(urls: List[str] = None, skip_download: bool = False):
    """Main function using the new modular orchestrator"""
    print("🚀 Starting Social Media Processor (Modular Architecture)")
    print("=" * 60)
    print("📁 New modular structure:")
    print("   • core/orchestrator.py - Main coordinator")
    print("   • core/processors/ - Individual processors")
    print("   • system/ - Database, config, and utilities")
    print("   • assets/ - Downloaded content")
    if skip_download:
        print("⚠️  Download step SKIPPED - processing existing videos only")
    print()
    
    try:
        # Initialize database
        print("📊 Initializing database...")
        await db_manager.initialize()
        print("✅ Database initialized")
        
        # Create orchestrator
        print("🎯 Creating orchestrator...")
        orchestrator = SocialMediaOrchestrator()
        
        # Initialize all processors
        print("🔧 Initializing processors...")
        init_results = await asyncio.gather(
            orchestrator.video_processor.initialize(),
            orchestrator.upload_processor.initialize(),
            orchestrator.thumbnail_processor.initialize(),
            orchestrator.aiwaverider_processor.initialize(),
            orchestrator.sheets_processor.initialize(),
            return_exceptions=True
        )
        
        # Check initialization results
        processor_names = ["Video", "Upload", "Thumbnail", "AIWaverider", "Sheets"]
        for i, result in enumerate(init_results):
            if isinstance(result, Exception):
                print(f"❌ {processor_names[i]} processor failed: {result}")
                return False
            elif not result:
                print(f"⚠️ {processor_names[i]} processor initialization returned False")
                return False
            else:
                print(f"✅ {processor_names[i]} processor ready")
        
        print("\n🎬 Starting processing pipeline...")
        
        # Use provided URLs or fallback
        if urls:
            sample_urls = urls
        else:
            # Fallback to urls.txt or default
            if os.path.exists("urls.txt"):
                with open("urls.txt", 'r', encoding='utf-8') as f:
                    all_urls = [line.strip() for line in f if line.strip()]
                # Process all URLs (no limit for transcription)
                sample_urls = all_urls
                print(f"📝 Loaded {len(all_urls)} URLs from urls.txt, processing all {len(all_urls)} videos")
            else:
                sample_urls = [
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Fallback sample URL
                ]
                print("📝 Using fallback sample URL")
        
        if skip_download:
            print(f"📝 Processing existing videos (skipping download) with GPU-accelerated parallel transcription...")
            success = await orchestrator.process_existing_videos()
        else:
            print(f"📝 Processing {len(sample_urls)} URLs with GPU-accelerated parallel transcription...")
            success = await orchestrator.process_urls(sample_urls)
        
        if success:
            print("\n✅ Processing completed successfully!")
        else:
            print("\n❌ Processing completed with errors")
        
        # Show final status
        print("\n📊 Final Status:")
        print(f"Video Processor: {orchestrator.video_processor.status}")
        print(f"Upload Processor: {orchestrator.upload_processor.status}")
        print(f"Thumbnail Processor: {orchestrator.thumbnail_processor.status}")
        print(f"AIWaverider Processor: {orchestrator.aiwaverider_processor.status}")
        print(f"Sheets Processor: {orchestrator.sheets_processor.status}")
        
        # Cleanup
        print("\n🧹 Cleaning up...")
        await asyncio.gather(
            orchestrator.video_processor.cleanup(),
            orchestrator.upload_processor.cleanup(),
            orchestrator.thumbnail_processor.cleanup(),
            orchestrator.aiwaverider_processor.cleanup(),
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Social Media Processor - Modular Architecture')
    parser.add_argument('--urls', nargs='+', help='URLs to process directly')
    parser.add_argument('--urls-file', help='Text file containing URLs (one per line)')
    parser.add_argument('--download', action='store_true', help='Include download step (default: skip download)')
    parser.add_argument('--test', action='store_true', help='Run test mode')
    args = parser.parse_args()
    
    if args.test:
        print("🧪 Running in test mode...")
        # Import and run the test
        from test_modular_system import main as test_main
        asyncio.run(test_main())
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
                    # Process all URLs (no limit for transcription)
                    urls = all_urls
                    print(f"📝 Loaded {len(all_urls)} URLs from {args.urls_file}, processing all {len(all_urls)} videos")
                else:
                    print(f"❌ URLs file not found: {args.urls_file}")
                    sys.exit(1)
            else:
                # Default to urls.txt if it exists
                if os.path.exists('urls.txt'):
                    with open('urls.txt', 'r', encoding='utf-8') as f:
                        all_urls = [line.strip() for line in f if line.strip()]
                    # Process all URLs (no limit for transcription)
                    urls = all_urls
                    print(f"📝 Loaded {len(all_urls)} URLs from urls.txt, processing all {len(all_urls)} videos")
                else:
                    print("❌ No URLs provided. Use --urls, --urls-file, or create urls.txt")
                    sys.exit(1)
            
            # Determine if download should be skipped
            skip_download = not args.download
            if skip_download:
                print("⚠️  Download step will be SKIPPED (use --download to include download)")
            else:
                print("✅ Download step will be INCLUDED")
            
            # Run main with URLs
            asyncio.run(main(urls, skip_download))
        except KeyboardInterrupt:
            print("\n⏹️  Process interrupted by user")
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            sys.exit(1)
