#!/usr/bin/env python3
"""
Test script for the continuous scanner
"""

import asyncio
import os
import shutil
from pathlib import Path
from continuous_scanner import ContinuousScannerService

async def test_scanner():
    """Test the continuous scanner with a sample video"""
    
    print("🧪 Testing Continuous Scanner Service")
    print("=" * 50)
    
    # Initialize scanner
    scanner = ContinuousScannerService()
    
    try:
        print("🔧 Initializing scanner...")
        if not await scanner.initialize():
            print("❌ Failed to initialize scanner")
            return False
        
        print("✅ Scanner initialized successfully")
        
        # Create test video file
        test_video_path = Path("assets/finished_videos/test_video.mp4")
        test_video_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create a dummy video file (just for testing)
        with open(test_video_path, 'w') as f:
            f.write("dummy video content for testing")
        
        print(f"📹 Created test video: {test_video_path}")
        
        # Process the test video
        print("🎬 Processing test video...")
        result = await scanner.process_video(str(test_video_path))
        
        if result:
            print("✅ Test video processed successfully")
        else:
            print("❌ Test video processing failed")
        
        # Cleanup test file
        if test_video_path.exists():
            test_video_path.unlink()
            print("🧹 Cleaned up test file")
        
        return result
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return False
    finally:
        await scanner.stop()

if __name__ == "__main__":
    asyncio.run(test_scanner())
