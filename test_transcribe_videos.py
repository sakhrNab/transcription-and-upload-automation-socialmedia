#!/usr/bin/env python3
"""
Test the transcribe videos endpoint
"""

import requests

def test_transcribe_videos():
    """Test the transcribe videos endpoint"""
    try:
        print("Testing transcribe videos endpoint...")
        
        # Test videos endpoint
        r = requests.get('http://localhost:5000/api/videos')
        print(f"Status: {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            print(f"Success: {data.get('success')}")
            print(f"Videos count: {len(data.get('videos', []))}")
            
            # Show first 10 videos
            for i, video in enumerate(data.get('videos', [])[:10]):
                print(f"  {i+1}. {video.get('filename')} - Thumbnail: {video.get('thumbnail')}")
            
            if len(data.get('videos', [])) > 10:
                print(f"  ... and {len(data.get('videos', [])) - 10} more videos")
        else:
            print(f"Error: {r.text}")
            
    except Exception as e:
        print(f"Error testing transcribe videos: {e}")

if __name__ == "__main__":
    test_transcribe_videos()
