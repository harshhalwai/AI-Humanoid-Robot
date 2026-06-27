import os
import requests
import json

BASE_URL = "http://127.0.0.1:8000/api"
API_KEY = "robot-secret-api-key-987654321"

HEADERS = {
    "X-Robot-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def print_divider(title):
    print("\n" + "=" * 50)
    print(f" TESTING: {title}")
    print("=" * 50)

def test_status_get():
    print_divider("GET /api/status/")
    url = f"{BASE_URL}/status/"
    try:
        response = requests.get(url, headers=HEADERS)
        print(f"Status Code: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        return response.status_code == 200
    except Exception as e:
        print(f"Error connecting: {e}")
        return False

def test_status_post():
    print_divider("POST /api/status/")
    url = f"{BASE_URL}/status/"
    payload = {
        "battery_level": 88.5,
        "current_mode": "speaking",
        "is_online": True,
        "log_message": "ESP32 started successfully. Connecting to sensors."
    }
    try:
        response = requests.post(url, headers=HEADERS, json=payload)
        print(f"Status Code: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        return response.status_code == 200
    except Exception as e:
        print(f"Error connecting: {e}")
        return False

def test_chat():
    print_divider("POST /api/chat/")
    url = f"{BASE_URL}/chat/"
    payload = {
        "text": "Hello, how are you today?",
        "session_id": "test_session_123"
    }
    try:
        response = requests.post(url, headers=HEADERS, json=payload)
        print(f"Status Code: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        return response.status_code == 200
    except Exception as e:
        print(f"Error connecting: {e}")
        return False

def test_tts():
    print_divider("POST /api/tts/")
    url = f"{BASE_URL}/tts/"
    payload = {
        "text": "Please move your head left and look at the camera."
    }
    try:
        response = requests.post(url, headers=HEADERS, json=payload)
        print(f"Status Code: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        return response.status_code == 200
    except Exception as e:
        print(f"Error connecting: {e}")
        return False

def test_upload_audio():
    print_divider("POST /api/upload_audio/")
    url = f"{BASE_URL}/upload_audio/"
    
    # Create a small dummy WAV file for testing if it doesn't exist
    dummy_audio_path = "dummy_test.wav"
    if not os.path.exists(dummy_audio_path):
        import wave
        import struct
        # Write 0.5s of silence
        with wave.open(dummy_audio_path, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            for _ in range(8000):
                w.writeframes(struct.pack('<h', 0))
                
    multipart_headers = {
        "X-Robot-API-Key": API_KEY
    }
    
    try:
        with open(dummy_audio_path, 'rb') as f:
            files = {'audio': (dummy_audio_path, f, 'audio/wav')}
            data = {'session_id': 'test_session_123'}
            response = requests.post(url, headers=multipart_headers, files=files, data=data)
            
        print(f"Status Code: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        
        # Clean up dummy file
        if os.path.exists(dummy_audio_path):
            os.remove(dummy_audio_path)
            
        return response.status_code in [200, 422]  # 422 is acceptable if speech recognition can't find audio in silence
    except Exception as e:
        print(f"Error connecting: {e}")
        return False

if __name__ == "__main__":
    print("AI Humanoid Robot Server - Integration Tests")
    print("Make sure your Django server is running locally (python manage.py runserver)")
    
    # Run tests
    s1 = test_status_get()
    s2 = test_status_post()
    s3 = test_chat()
    s4 = test_tts()
    s5 = test_upload_audio()
    
    print("\n" + "=" * 50)
    print(" TEST RESULTS SUMMARY")
    print("=" * 50)
    print(f"GET /api/status/:       {'PASSED' if s1 else 'FAILED'}")
    print(f"POST /api/status/:      {'PASSED' if s2 else 'FAILED'}")
    print(f"POST /api/chat/:        {'PASSED' if s3 else 'FAILED'}")
    print(f"POST /api/tts/:         {'PASSED' if s4 else 'FAILED'}")
    print(f"POST /api/upload_audio: {'PASSED' if s5 else 'FAILED'}")
