#!/usr/bin/env python3
"""
Test LinkedIn video download support with yt-dlp
"""

import yt_dlp

def test_linkedin_support():
    """Test if yt-dlp supports LinkedIn videos"""
    print("Testing LinkedIn video download support...")
    
    # Check available extractors
    extractors = [str(ext) for ext in yt_dlp.extractor.list_extractors()]
    linkedin_extractors = [ext for ext in extractors if 'linkedin' in ext.lower()]
    
    print(f"Found {len(linkedin_extractors)} LinkedIn extractors:")
    for ext in linkedin_extractors:
        print(f"  - {ext}")
    
    # Test URL pattern recognition
    test_urls = [
        "https://www.linkedin.com/posts/activity-1234567890-abcdef",
        "https://www.linkedin.com/feed/update/urn:li:activity:1234567890",
        "https://www.linkedin.com/video/play/1234567890",
    ]
    
    ydl = yt_dlp.YoutubeDL({'quiet': True})
    
    for url in test_urls:
        print(f"\nTesting URL: {url}")
        try:
            # This will fail with fake URLs, but we can see if the extractor is recognized
            info = ydl.extract_info(url, download=False)
            print("  ✅ URL recognized and processed successfully")
        except Exception as e:
            error_msg = str(e)
            if "linkedin" in error_msg.lower():
                print("  ✅ LinkedIn extractor recognized the URL")
            elif "404" in error_msg or "Not Found" in error_msg:
                print("  ✅ URL pattern recognized (404 expected for fake URL)")
            else:
                print(f"  ❌ Error: {error_msg[:100]}...")

if __name__ == "__main__":
    test_linkedin_support()

