import requests
import json
import time
import os
from pathlib import Path

# Local server URL
BASE_URL = "http://localhost:8000"

# Set up environment variables
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(Path("credentials/google_credentials.json").absolute())

def test_health():
    """Test the health check endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/health")
        print("\n🏥 Testing Health Endpoint:")
        print(f"Status Code: {response.status_code}")
        print("Response:", json.dumps(response.json(), indent=2))
        return response.status_code == 200
    except Exception as e:
        print(f"Health check error: {str(e)}")
        return False

def process_video(video_url, style="news", language="en", model="gpt-4o-mini", voice_gender="MALE"):
    """Start video processing and return job ID"""
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    data = {
        "video_url": video_url,
        "style": style,
        "language": language,
        "model": model,
        "voice_gender": voice_gender
    }

    try:
        print("\n🎬 Starting Video Processing:")
        print("Request Data:", json.dumps(data, indent=2))
        
        response = requests.post(f"{BASE_URL}/process_video", headers=headers, json=data)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("Response:", json.dumps(result, indent=2))
            return result.get("job_id")
        else:
            print("Error Response:", response.text)
            return None
            
    except Exception as e:
        print(f"Process video error: {str(e)}")
        return None

def check_job_status(job_id):
    """Check the status of a processing job"""
    try:
        response = requests.get(f"{BASE_URL}/job_status/{job_id}")
        result = response.json()
        print(f"\n📊 Job Status ({job_id}):")
        print(json.dumps(result, indent=2))
        return result
    except Exception as e:
        print(f"Status check error: {str(e)}")
        return None

def main():
    """Main test function"""
    print("🚀 Starting API Tests\n")
    
    # Test 1: Health Check
    if not test_health():
        print("❌ Health check failed. Make sure the server is running.")
        return
    
    # Test 2: Process Video
    test_video_url = "https://x.com/AMAZlNGNATURE/status/1889692194459496827"
    job_id = process_video(
        video_url=test_video_url,
        style="funny",
        language="en",
        model="gpt-4o-mini",
        voice_gender="MALE"
    )
    
    if not job_id:
        print("❌ Failed to start video processing")
        return
    
    # Test 3: Monitor Job Status
    print("\n⏳ Monitoring job status...")
    max_checks = 30  # Maximum number of status checks
    check_interval = 10  # Seconds between checks
    
    for i in range(max_checks):
        status = check_job_status(job_id)
        if not status:
            print("❌ Failed to get job status")
            break
            
        if status["status"] == "completed":
            print("\n✅ Video processing completed!")
            print(f"Result: {status.get('result')}")
            break
        elif status["status"] == "error":
            print(f"\n❌ Error processing video: {status.get('message')}")
            break
        elif i == max_checks - 1:
            print("\n⚠️ Timeout waiting for video processing")
            break
            
        print(f"Status: {status['status']} - {status.get('message', '')}")
        time.sleep(check_interval)

if __name__ == "__main__":
    main() 