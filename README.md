# AI Humanoid Robot Assistant - System Documentation

This repository contains the complete codebase, firmware, wiring configurations, and deployment guidelines for the **AI Humanoid Robot Assistant**. 

The system operates using a **split-controller architecture**:
- **ESP32 DevKit V1**: Acts as the internet-enabled "brain" and sensory hub. It captures audio input from an I2S digital microphone, streams it to a Django Cloud Server, downloads synthesized voice response streams, handles speaker playback, and issues UART motion commands.
- **Arduino UNO R3**: Acts as the dedicated "motion controller", executing non-blocking, smooth sweeps on SG90, MG90S, and MG945 servos to coordinate mouth, eye, and head movements.
- **Django Cloud Server**: Serves as the central AI engine, transcribing voice input, querying the Google Gemini API with context history memory, converting response text to natural neural speech (Edge TTS), resolving motion paths, and maintaining telemetry logs.

---

## 1. System Architecture Diagrams

### A. Block Diagram
```mermaid
graph TD
    User([User Voice Input]) -->|Acoustic Waves| Mic[INMP441 I2S Digital Mic]
    Mic -->|I2S Digital Audio| ESP32[ESP32 DevKit V1]
    Button[Push-To-Talk Button] -->|GPIO Interrupt| ESP32
    
    ESP32 <-->|WiFi / HTTPS POST| Django[Django Cloud Server]
    Django <-->|HTTPS API Calls| Gemini[Google Gemini API]
    
    ESP32 -->|I2S Built-In DAC| Amp[PAM8403 Amplifier]
    Amp -->|Analog Audio| Spk[3W Speaker] -->|Sound Waves| User
    
    ESP32 -->|UART Serial @ 9600 Baud| Uno[Arduino UNO R3]
    Power[External 5V Power Supply] -->|Shared GND| Uno
    
    Uno -->|PWM Pin 9| Servo1[Eye L/R Servo - SG90]
    Uno -->|PWM Pin 10| Servo2[Eye U/D Servo - SG90]
    Uno -->|PWM Pin 11| Servo3[Mouth Servo - MG90S]
    Uno -->|PWM Pin 12| Servo4[Head Yaw Servo - MG945]
```

### B. System Information Flow (Flowchart)
```mermaid
flowchart TD
    Start([User presses Record Button]) --> Record[ESP32 records audio from INMP441]
    Record --> SaveLocal[ESP32 saves WAV to SPIFFS]
    SaveLocal --> Upload[ESP32 uploads WAV via HTTP POST to Django]
    
    Upload --> ConvertWav[Django converts audio to 16kHz Mono PCM]
    ConvertWav --> STT[Speech-to-Text: Google STT / Whisper]
    STT --> QueryGemini[Django sends transcribed text to Gemini API]
    QueryGemini --> SaveDB[Django saves User & AI text in SQLite/PostgreSQL]
    
    SaveDB --> GenerateTTS[Django generates speech MP3 via Microsoft Edge TTS]
    GenerateTTS --> MapMoves[Django extracts intent keywords & maps motion flags]
    MapMoves --> ReturnJSON[Django returns reply, audio_url, and motion switches]
    
    ReturnJSON --> ParseJSON[ESP32 parses JSON response]
    ParseJSON --> TriggerMotion[ESP32 sends serial commands to Arduino UNO]
    ParseJSON --> StreamMP3[ESP32 downloads and plays MP3 via DAC Pin 25]
    
    TriggerMotion --> ServoMove[Arduino UNO sweeps servos smoothly]
    StreamMP3 --> Finished([Robot finishes speaking and returns to Idle])
```

### C. Sequence Diagram
```mermaid
sequenceDiagram
    autonumber
    actor User
    participant ESP32 as ESP32 Brain
    participant Django as Django Cloud Brain
    participant Gemini as Google Gemini API
    participant Uno as Arduino UNO Motion

    User->>ESP32: Press Button & Speak
    ESP32->>ESP32: Capture Audio from INMP441
    ESP32->>Django: POST /api/upload_audio/ (WAV file)
    Note over Django: Run Audio Normalization & STT
    Django->>Gemini: Request response (with chat history)
    Gemini-->>Django: Return reply text (brief, conversational)
    Note over Django: Run TTS (Edge TTS) & Map Movement Flags
    Django-->>ESP32: Return JSON {reply, audio_url, mouth, eye, head}
    
    par Stream Speech Audio
        ESP32->>Django: GET /api/audio/<filename>.mp3
        Django-->>ESP32: Stream MP3 stream
        ESP32->>User: Play voice via PAM8403 & Speaker
    and Sync Movements
        ESP32->>Uno: Send Serial "M1" (Start speaking)
        ESP32->>Uno: Send Serial "HN" (Nod head)
        Note over Uno: Flap mouth servo in sync with speaking
        Note over Uno: Perform smooth agreement nod
    end
    
    Note over ESP32: Audio stream terminates
    ESP32->>Uno: Send Serial "M0" (Stop speaking)
    Note over Uno: Close mouth jaw & resume Idle movement
```

---

## 2. Hardware Connections and Wiring Sheet

A **Common Ground Connection** between the external 5V power supply, the ESP32, and the Arduino UNO is **CRITICAL** to prevent servo jitter, logic failures, and voltage level discrepancies.

### A. ESP32 Pin Connections
| Component | INMP441 Digital Mic Pin | ESP32 Pin | Description |
| :--- | :--- | :--- | :--- |
| Microphone | VCC | 3.3V | Power Supply (Mic) |
| Microphone | GND | GND | Shared Ground |
| Microphone | L/R | GND | Selects Left Audio Channel |
| Microphone | SCK | GPIO 14 | I2S Serial Clock |
| Microphone | WS | GPIO 15 | I2S Word Select / LR Clock |
| Microphone | SD | GPIO 32 | I2S Serial Data Out |

| Component | PAM8403 Amp Pin | ESP32 Pin | Description |
| :--- | :--- | :--- | :--- |
| Amplifier | L or R Input | GPIO 25 | Built-in DAC Channel 1 (Audio Out) |
| Amplifier | GND | GND | Shared Ground |
| Amplifier | VCC | External 5V (+) | Amplifier Power Supply |

| Component | Interface / Button Pin | ESP32 Pin | Description |
| :--- | :--- | :--- | :--- |
| Push Button | Lead A | GPIO 4 | Record Trigger Pin (internal pull-up) |
| Push Button | Lead B | GND | Active-low ground connection |
| Serial Link | RX2 (Data In) | GPIO 16 | Connects to Arduino Software TX |
| Serial Link | TX2 (Data Out) | GPIO 17 | Connects to Arduino Software RX |

### B. Arduino UNO Pin Connections
All servos **MUST** be powered from an external 5V regulated power source (capable of delivering at least 2A-3A peak current). Connecting servos directly to the Arduino's 5V pin will brown-out and damage the microcontroller.

| Servo Motor | Signal Pin (PWM) | Power Pin (+) | Ground Pin (-) | Servo Model | Function |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Eye L/R | Pin 9 | External 5V (+) | Common GND | SG90 | Shifts eye gaze left/right |
| Eye U/D | Pin 10 | External 5V (+) | Common GND | SG90 | Shifts eye gaze up/down |
| Mouth | Pin 11 | External 5V (+) | Common GND | MG90S | Flaps jaw open/closed |
| Head Rotation | Pin 12 | External 5V (+) | Common GND | MG945 | Rotates head (yaw) |

| Communication Interface | Arduino UNO Pin | Connected To | Description |
| :--- | :--- | :--- | :--- |
| Software Serial RX | Pin 2 | ESP32 GPIO 17 (TX2) | Receives Serial Commands |
| Software Serial TX | Pin 3 | ESP32 GPIO 16 (RX2) | Sends Telemetry Logs |
| Common Ground | GND | ESP32 GND & Power GND | Establishes shared electrical reference |

---

## 3. Database Schema

The database defaults to **SQLite** for zero-configuration local development and automatically switches to **PostgreSQL** when a `DATABASE_URL` is configured in the `.env` settings.

### Table: `robot_conversation`
Records chat histories for Gemini context memory and diagnostics.
- `id` (BigInt, PK, Auto-Increment)
- `session_id` (VarChar(100), Indexed): Grouping token for conversation turns.
- `user_message` (Text, Nullable): Text transcribed from user speech.
- `ai_response` (Text, Nullable): Concise text returned by Gemini.
- `timestamp` (DateTime): Date and time when the interaction took place.

### Table: `robot_robotstatus`
Stores hardware status logs, allowing cloud dashboard tracking of the robot.
- `id` (BigInt, PK, Auto-Increment)
- `robot_id` (VarChar(100), Unique): Hardware identification token (e.g. `humanoid_v1`).
- `is_online` (Boolean): Current network activity indicator.
- `battery_level` (Double Precision): Battery percentage (0.0 to 100.0).
- `last_ping` (DateTime): Auto-updating timestamp of the last status packet.
- `current_mode` (VarChar(50)): Active robot state (`idle`, `speaking`, `listening`).

### Table: `robot_robotlog`
Records runtime logs transmitted directly by the microcontroller firmware.
- `id` (BigInt, PK, Auto-Increment)
- `robot_id` (VarChar(100)): Telemetry source ID.
- `level` (VarChar(20)): Log category (`INFO`, `WARNING`, `DEBUG`).
- `message` (Text): The raw log string.
- `timestamp` (DateTime): Timestamp of when the log was recorded.

### Table: `robot_errorlog`
Saves exception reports, call stacks, and errors for remote auditing.
- `id` (BigInt, PK, Auto-Increment)
- `module` (VarChar(100)): The file, view, or service where the exception was caught.
- `error_message` (Text): Short exception string.
- `stack_trace` (Text, Nullable): Detailed python call stack output.
- `timestamp` (DateTime): Exception timestamp.

---

## 4. REST API Documentation

All API requests (except for media file downloads and the GET health status) require the API key to be passed via headers.
- **API Key Header**: `X-Robot-API-Key: robot-secret-api-key-987654321`

### 1. Upload Audio
* **Endpoint**: `POST /api/upload_audio/`
* **Content-Type**: `multipart/form-data`
* **Request Body**:
  * `audio`: Binary Audio File (`WAV` or `MP3`, maximum size 10MB).
  * `session_id` (optional, default="default"): Conversation tracking session.
* **Headers**: `X-Robot-API-Key: <key>`
* **Success Response (200 OK)**:
```json
{
  "reply": "Hello! I am doing well, thank you for asking.",
  "audio_url": "http://127.0.0.1:8000/api/audio/response_8a4b3d11c7.mp3",
  "mouth": true,
  "eye": true,
  "head": true
}
```

### 2. Text Chat
* **Endpoint**: `POST /api/chat/`
* **Content-Type**: `application/json`
* **Request Body**:
```json
{
  "text": "Tell me a joke.",
  "session_id": "session_user_abc"
}
```
* **Success Response (200 OK)**:
```json
{
  "reply": "Why did the robot go on a diet? It had too many bytes!",
  "audio_url": "http://127.0.0.1:8000/api/audio/response_49ffc12901.mp3",
  "mouth": true,
  "eye": true,
  "head": true
}
```

### 3. Text-To-Speech (TTS)
* **Endpoint**: `POST /api/tts/`
* **Content-Type**: `application/json`
* **Request Body**:
```json
{
  "text": "Testing the motor system."
}
```
* **Success Response (200 OK)**:
```json
{
  "audio_url": "http://127.0.0.1:8000/api/audio/tts_7c1d32ba98.mp3"
}
```

### 4. Telemetry Status & Logs
* **Endpoint**: `GET /api/status/`
  * **Description**: Retrieves current robot battery, state, and last ping. No parameters required.
  * **Success Response (200 OK)**:
```json
{
  "status": "online",
  "version": "1.0",
  "battery_level": 88.5,
  "is_online": true,
  "current_mode": "speaking",
  "last_ping": "2026-06-28T03:15:00Z"
}
```
* **Endpoint**: `POST /api/status/`
  * **Description**: Allows the ESP32 to submit telemetry updates and run logs.
  * **Request Body**:
```json
{
  "battery_level": 85.2,
  "current_mode": "idle",
  "is_online": true,
  "log_message": "Battery charging completed."
}
```
  * **Success Response (200 OK)**: (Returns updated status)

---

## 5. Completed Folder Structure

```text
robot_ai/
├── config/                  # Django project configuration folder
│   ├── __init__.py
│   ├── settings.py          # Django databases, logging, and security settings
│   ├── urls.py              # Root routing mapping API endpoints
│   ├── wsgi.py              # WSGI entry point
│   └── asgi.py              # ASGI entry point
├── assistant/               # Google Gemini API integration app
│   ├── __init__.py
│   ├── apps.py
│   └── services.py          # GeminiClient with memory caching
├── voice/                   # Speech-To-Text and Text-To-Speech app
│   ├── __init__.py
│   ├── apps.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── stt.py           # Whisper & Google Speech transcription engines
│   │   └── tts.py           # Microsoft Edge Neural & Google Translate speech engines
│   ├── utils.py             # Audio WAV converters and directory file purgers
│   └── tasks.py             # Asynchronous thread triggers for cleanup
├── robot/                   # Telemetry database models and command app
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py            # Conversation, RobotStatus, RobotLog, and ErrorLog tables
│   ├── commands.py          # Regex/Keyword parser that resolves movement flags
│   └── migrations/          # Auto-generated database migration files
├── api/                     # REST API implementation app
│   ├── __init__.py
│   ├── apps.py
│   ├── authentication.py    # Custom API Key validation middleware
│   ├── serializers.py       # Serializers for validating requests
│   ├── urls.py              # API endpoint path declarations
│   └── views.py             # Upload, Chat, TTS, Status, and Serve views
├── firmware/                # Microcontroller firmware files
│   ├── esp32_brain/
│   │   └── esp32_brain.ino  # ESP32 main controller source code
│   └── arduino_motion/
│       └── arduino_motion.ino # Arduino UNO servo controller source code
├── media/                   # Media directory for audio files
│   └── audio/               # Stores generated MP3 files
├── static/                  # Static assets directory
├── logs/                    # Application and request log files
├── db.sqlite3               # Local SQLite database
├── requirements.txt         # Python package dependencies
├── .env                     # Local environment settings file
├── .env.example             # Environment template reference
├── test_api.py              # Python integration testing script
└── README.md                # Main documentation markdown (this file)
```

---

## 6. Installation & Setup Guide

### A. Server Installation
1. **Clone/Copy Project**: Navigate to the `robot_ai` directory.
2. **Install Python**: Make sure Python 3.10+ is installed on the host system.
3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Install FFmpeg**:
   * FFmpeg is required for converting incoming voice streams to standard WAV format.
   * **Windows**: Download FFmpeg binaries from gyan.dev, add the `bin` folder path to system Environment Variables.
   * **Linux/Ubuntu**: `sudo apt update && sudo apt install ffmpeg -y`
   * **Mac**: `brew install ffmpeg`
5. **Configure Keys**:
   * Open `.env` and set your `GEMINI_API_KEY` (obtained from Google AI Studio).
   * Update `ROBOT_API_KEY` to secure the communications between the robot and server.
6. **Initialize Database**:
   ```bash
   python manage.py migrate
   ```
7. **Start Server**:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

### B. Microcontroller Installation

#### Arduino UNO
1. Open the Arduino IDE.
2. Open the file `firmware/arduino_motion/arduino_motion.ino`.
3. Select board **Arduino Uno** and configure the correct COM Port.
4. Verify and **Upload** the sketch.

#### ESP32
1. Open the Arduino IDE.
2. Add ESP32 boards to the IDE by adding `https://dl.espressif.com/dl/package_esp32_index.json` to **Preferences -> Additional Boards Manager URLs**.
3. Install the **ESP32** board package under **Boards Manager**.
4. Install libraries under **Sketch -> Include Library -> Manage Libraries**:
   - **ArduinoJson** (by Benoit Blanchon)
   - **ESP8266Audio** (by Earle F. Philhower, III)
5. Open `firmware/esp32_brain/esp32_brain.ino`.
6. Update WiFi Credentials:
   ```cpp
   const char* ssid = "YOUR_WIFI_SSID";
   const char* password = "YOUR_WIFI_PASSWORD";
   ```
7. Update Server IP to point to your running Django Cloud Server:
   ```cpp
   const char* server_url = "http://<YOUR_DJANGO_SERVER_IP>:8000/api/upload_audio/";
   const char* status_url = "http://<YOUR_DJANGO_SERVER_IP>:8000/api/status/";
   ```
8. Select board **ESP32 Dev Module** (or your specific ESP32 board) and select correct COM port.
9. Connect button and I2S microphone (as listed in wiring sheet) and **Upload** the sketch.

---

## 7. Testing Guide

### A. API Integration Testing
Ensure your Django server is running locally before calling the test script.
1. Run the test script in a terminal window:
   ```bash
   python test_api.py
   ```
2. The script will perform a complete verification of all API hooks:
   - Telemetry fetch (`GET /api/status/`)
   - Telemetry update (`POST /api/status/`)
   - Gemini query and response formatting (`POST /api/chat/`)
   - Direct Text-to-Speech conversion (`POST /api/tts/`)
   - Multipart audio transcription pipeline (`POST /api/upload_audio/`)
3. A final status summary will print on your console indicating whether each test has passed or failed.

### B. Hardware Verification
1. Open the Arduino Serial Monitor (115200 baud) to monitor incoming serial commands.
2. Open the ESP32 Serial Monitor (115200 baud).
3. Verify that the ESP32 connects to the WiFi network and sends a status telemetry update to the Django server.
4. Press and hold the Record Button (GPIO 4). Speak clearly in English or Hindi, then release.
5. Watch the logs:
   * The ESP32 records audio, outputs `>>> Recording voice started...`, and uploads the WAV file.
   * The Django server transcribes the text, retrieves the Gemini response, creates the TTS response, and returns the JSON payload.
   * The ESP32 downloads and decodes the MP3 file, outputting the speech through the speaker.
   * The ESP32 sends the serial command `M1` to the Arduino. The Arduino begins flapping the mouth servo in sync with the speech.
   * The Arduino nod/shake sequences activate depending on the keywords contained in the response.
   * The ESP32 sends `M0` once the audio ends, closing the robot's mouth.

---

## 8. Production Deployment Guide

To deploy the cloud-based Django server for production:

### A. Environment Configuration
Update `.env` values for production:
- Set `DEBUG=False` to prevent tracebacks from leaking to users.
- Add your domain or public IP to `ALLOWED_HOSTS`.
- Configure a strong `SECRET_KEY`.

### B. PostgreSQL Setup
For high volume logging, replace SQLite with PostgreSQL:
1. Spin up a Postgres database instance.
2. Update `.env` to include:
   ```env
   DATABASE_URL=postgres://db_user:db_password@postgres_host:5432/robot_db
   ```
3. Run `python manage.py migrate` to create Postgres tables.

### C. Gunicorn & Nginx Reverse Proxy
In production, use **Gunicorn** to run the Django WSGI process, and **Nginx** to serve static/media files and act as a reverse proxy:

#### Gunicorn Systemd Configuration (`/etc/systemd/system/gunicorn.service`)
```ini
[Unit]
Description=gunicorn daemon
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/robot_ai
ExecStart=/home/ubuntu/robot_ai/venv/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind unix:/run/gunicorn.sock \
          config.wsgi:application

[Install]
WantedBy=multi-user.target
```

#### Nginx Site Server Block Configuration (`/etc/nginx/sites-available/robot_ai`)
```nginx
server {
    listen 80;
    server_name your_domain_or_ip;

    # Exclude media files from authorization checks for ESP32 easy download
    location /media/ {
        alias /home/ubuntu/robot_ai/media/;
    }

    location /static/ {
        alias /home/ubuntu/robot_ai/static/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn.sock;
    }
}
```

### D. Production Security Checkpoints
1. **SSL/HTTPS**: Enable HTTPS using Let's Encrypt (`certbot --nginx`) to encrypt the communication of audio data and keys. Update the ESP32 `server_url` to use `https://`.
2. **API Keys**: Change the `ROBOT_API_KEY` to a 32-character secure random token.
3. **CORS**: Avoid using `CORS_ALLOW_ALL_ORIGINS = True` in production. Specifically list allowed domain sources in `CORS_ALLOWED_ORIGINS` if web clients will access the APIs.
4. **Log Rotation**: Ensure the logging rotating handler settings in `settings.py` (`maxBytes` and `backupCount`) are configured appropriately to prevent the server storage from filling up with log files.
