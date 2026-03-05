#!/usr/bin/env python3
"""
Test script for the Social Media Content Processor Web UI
"""

import requests
import time
import json

def test_web_ui():
    """Test the web UI endpoints"""
    base_url = "http://localhost:5000"
    
    print("🧪 Testing Social Media Content Processor Web UI...")
    print("=" * 50)
    
    # Test 1: Check if server is running
    print("1. Testing server connection...")
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("   ✅ Server is running!")
        else:
            print(f"   ❌ Server returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Server is not running: {e}")
        print("   💡 Start the server with: python app_simple.py")
        return False
    
    # Test 2: Test API endpoints
    print("\n2. Testing API endpoints...")
    
    # Test URLs endpoint
    try:
        response = requests.get(f"{base_url}/api/urls")
        data = response.json()
        if data.get('success'):
            print(f"   ✅ URLs endpoint: {len(data['urls'])} URLs loaded")
        else:
            print(f"   ❌ URLs endpoint failed: {data.get('error')}")
    except Exception as e:
        print(f"   ❌ URLs endpoint error: {e}")
    
    # Test videos endpoint
    try:
        response = requests.get(f"{base_url}/api/videos")
        data = response.json()
        if data.get('success'):
            print(f"   ✅ Videos endpoint: {len(data['videos'])} videos loaded")
        else:
            print(f"   ❌ Videos endpoint failed: {data.get('error')}")
    except Exception as e:
        print(f"   ❌ Videos endpoint error: {e}")
    
    # Test finished videos endpoint
    try:
        response = requests.get(f"{base_url}/api/finished-videos")
        data = response.json()
        if data.get('success'):
            print(f"   ✅ Finished videos endpoint: {len(data['videos'])} videos loaded")
        else:
            print(f"   ❌ Finished videos endpoint failed: {data.get('error')}")
    except Exception as e:
        print(f"   ❌ Finished videos endpoint error: {e}")
    
    # Test status endpoint
    try:
        response = requests.get(f"{base_url}/api/status")
        data = response.json()
        if data.get('success'):
            status = data['status']
            print(f"   ✅ Status endpoint: Database={status.get('database')}, GPU={status.get('gpu')}")
        else:
            print(f"   ❌ Status endpoint failed: {data.get('error')}")
    except Exception as e:
        print(f"   ❌ Status endpoint error: {e}")
    
    # Test 3: Test download process
    print("\n3. Testing download process...")
    try:
        test_urls = ["https://example.com/video1", "https://example.com/video2"]
        response = requests.post(f"{base_url}/api/download", 
                               json={"urls": test_urls},
                               headers={"Content-Type": "application/json"})
        data = response.json()
        if data.get('success'):
            task_id = data.get('taskId')
            print(f"   ✅ Download started: Task ID {task_id}")
            
            # Test progress tracking
            print("   🔄 Testing progress tracking...")
            for i in range(3):
                time.sleep(1)
                try:
                    progress_response = requests.get(f"{base_url}/api/progress/{task_id}")
                    progress_data = progress_response.json()
                    print(f"      Progress: {progress_data.get('progress', 0)}% - {progress_data.get('status', 'unknown')}")
                except Exception as e:
                    print(f"      Progress error: {e}")
        else:
            print(f"   ❌ Download failed: {data.get('error')}")
    except Exception as e:
        print(f"   ❌ Download test error: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Web UI testing completed!")
    print("📱 Open your browser and go to: http://localhost:5000")
    print("🛑 Press Ctrl+C in the server terminal to stop")
    
    return True

if __name__ == "__main__":
    test_web_ui()
