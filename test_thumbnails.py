#!/usr/bin/env python3
"""
Test the thumbnails endpoint
"""

import requests

def test_thumbnails():
    """Test the thumbnails endpoint"""
    try:
        print("Testing thumbnails endpoint...")
        
        # Test thumbnails endpoint
        r = requests.get('http://localhost:5000/api/thumbnails')
        print(f"Status: {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            print(f"Success: {data.get('success')}")
            print(f"Thumbnails count: {len(data.get('thumbnails', []))}")
            
            # Show first 10 thumbnails
            for i, thumb in enumerate(data.get('thumbnails', [])[:10]):
                print(f"  {i+1}. {thumb.get('filename')} ({thumb.get('size')})")
            
            if len(data.get('thumbnails', [])) > 10:
                print(f"  ... and {len(data.get('thumbnails', [])) - 10} more thumbnails")
        else:
            print(f"Error: {r.text}")
            
    except Exception as e:
        print(f"Error testing thumbnails: {e}")

if __name__ == "__main__":
    test_thumbnails()