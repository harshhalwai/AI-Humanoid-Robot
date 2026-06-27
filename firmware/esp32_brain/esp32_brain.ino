/**
 * AI Humanoid Robot Assistant - ESP32 Brain Firmware
 * 
 * Hardware:
 * - ESP32 DevKit V1
 * - INMP441 I2S Digital Microphone
 * - PAM8403 Amplifier + 3W Speaker (Connected to ESP32 DAC Pin 25)
 * - Push Button on Pin 4 (Active LOW, internal pull-up) for recording
 * - Serial connection to Arduino UNO (TX2 Pin 17 -> Arduino RX, RX2 Pin 16 -> Arduino TX)
 * 
 * Libraries Required (Install via Arduino Library Manager):
 * - ArduinoJson (by Benoit Blanchon)
 * - ESP8266Audio (by Earle F. Philhower, III)
 * 
 * Pin Connections:
 * INMP441 I2S Mic:
 * - VCC -> 3.3V
 * - GND -> GND
 * - L/R -> GND (Left Channel)
 * - SCK -> GPIO 14
 * - WS  -> GPIO 15
 * - SD  -> GPIO 32
 * 
 * Speaker & Amp:
 * - PAM8403 L/R Input -> ESP32 GPIO 25 (DAC Channel 1)
 * - PAM8403 GND      -> ESP32 GND
 * - PAM8403 VCC      -> External 5V
 * 
 * Arduino Serial:
 * - ESP32 TX2 (GPIO 17) -> Arduino SoftwareSerial RX (Pin 2)
 * - ESP32 RX2 (GPIO 16) -> Arduino SoftwareSerial TX (Pin 3)
 * - ESP32 GND           -> Arduino GND (Common Ground is CRITICAL)
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <FS.h>
#include <SPIFFS.h>
#include <driver/i2s.h>
#include <ArduinoOTA.h>

// Audio Playback Libraries
#include "AudioFileSourceHTTPStream.h"
#include "AudioGeneratorMP3.h"
#include "AudioOutputI2S.h"

// Configuration
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* server_url = "http://192.168.1.100:8000/api/upload_audio/"; // Replace with Django Server IP
const char* status_url = "http://192.168.1.100:8000/api/status/";
const char* api_key = "robot-secret-api-key-987654321";

// Pin Configurations
#define RECORD_BUTTON_PIN 4
#define ARDUINO_TX_PIN 17
#define ARDUINO_RX_PIN 16

// I2S Microphone Pin Definitions
#define I2S_MIC_SCK 14
#define I2S_MIC_WS 15
#define I2S_MIC_SD 32
#define I2S_MIC_PORT I2S_NUM_0

// WAV Audio Constants
#define RECORD_TIME_SECONDS 5  // Maximum recording time in seconds
#define SAMPLE_RATE 16000      // 16kHz sample rate recommended for Speech APIs
#define BITS_PER_SAMPLE 16     // 16-bit PCM
#define AUDIO_BUFFER_SIZE (SAMPLE_RATE * RECORD_TIME_SECONDS * (BITS_PER_SAMPLE / 8))
#define WAV_FILE_PATH "/recorded_voice.wav"

// Audio Playback Globals
AudioGeneratorMP3 *mp3_decoder = nullptr;
AudioFileSourceHTTPStream *audio_stream = nullptr;
AudioOutputI2S *audio_out = nullptr;

bool is_recording = false;
bool is_speaking = false;
unsigned long last_status_ping = 0;
float simulated_battery = 98.0;

// Function Prototypes
void setupI2SMicrophone();
void recordWAVFile();
void writeWAVHeader(File &file);
void sendAudioToCloud();
void playMP3Speech(const char* url);
void sendSerialCommand(const char* cmd);
void checkAudioPlayback();
void handleWiFiReconnection();
void sendTelemetryUpdate(float battery, const char* mode, const char* log_msg);

void setup() {
  Serial.begin(115200);
  
  // Initialize Hardware Serial 2 for Arduino UNO communication
  // 9600 baud rate matches SoftwareSerial standard on Arduino
  Serial2.begin(9600, SERIAL_8N1, ARDUINO_RX_PIN, ARDUINO_TX_PIN);
  
  pinMode(RECORD_BUTTON_PIN, INPUT_PULLUP);
  
  // Initialize SPIFFS File System
  if (!SPIFFS.begin(true)) {
    Serial.println("SPIFFS Mount Failed! Formatting filesystem...");
  }
  
  // Connect to WiFi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  int timeout = 0;
  while (WiFi.status() != WL_CONNECTED && timeout < 30) {
    delay(500);
    Serial.print(".");
    timeout++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi Connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    sendSerialCommand("H0"); // Send "Center Head" to Arduino to confirm readiness
  } else {
    Serial.println("\nWiFi Connection Failed! Will retry in main loop.");
  }

  // Setup I2S Mic
  setupI2SMicrophone();
  
  // Setup OTA
  ArduinoOTA.setHostname("humanoid-brain");
  ArduinoOTA.begin();

  // Send initial startup telemetry to server
  if (WiFi.status() == WL_CONNECTED) {
    sendTelemetryUpdate(simulated_battery, "idle", "ESP32 Booted. Initialized I2S mic and Serial communication.");
  }
}

void loop() {
  // Handle OTA
  ArduinoOTA.handle();

  // Manage WiFi Connection
  handleWiFiReconnection();

  // Check and progress MP3 stream playback
  checkAudioPlayback();

  // Periodically send robot status telemetry (every 15 seconds)
  if (millis() - last_status_ping > 15000 && WiFi.status() == WL_CONNECTED && !is_recording && !is_speaking) {
    // Slowly discharge battery simulated values for testing
    simulated_battery -= 0.1;
    if (simulated_battery < 10) simulated_battery = 100.0;
    sendTelemetryUpdate(simulated_battery, "idle", "Periodic telemetry ping.");
    last_status_ping = millis();
  }

  // Check Record Button State (Active LOW)
  if (digitalRead(RECORD_BUTTON_PIN) == LOW && !is_recording && !is_speaking) {
    // Button pressed: trigger recording
    is_recording = true;
    sendTelemetryUpdate(simulated_battery, "listening", "User triggered speech recording.");
    recordWAVFile();
    sendAudioToCloud();
    is_recording = false;
  }
}

void setupI2SMicrophone() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = i2s_comm_format_t(I2S_COMM_FORMAT_I2S | I2S_COMM_FORMAT_I2S_MSB),
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 8,
    .dma_buf_len = 1024,
    .use_apll = false
  };

  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_MIC_SCK,
    .ws_io_num = I2S_MIC_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_MIC_SD
  };

  i2s_driver_install(I2S_MIC_PORT, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_MIC_PORT, &pin_config);
  Serial.println("I2S Digital Mic initialized.");
}

void recordWAVFile() {
  Serial.println(">>> Recording voice started...");
  sendSerialCommand("E1"); // Eyes look active/interested
  
  // Open audio file for writing
  File file = SPIFFS.open(WAV_FILE_PATH, FILE_WRITE);
  if (!file) {
    Serial.println("Failed to open file for writing WAV!");
    return;
  }

  // Write temporary WAV header (updated later)
  writeWAVHeader(file);

  int samples_to_read = SAMPLE_RATE * RECORD_TIME_SECONDS;
  size_t bytes_written = 0;
  
  // Allocate buffer for audio frames
  int16_t* audio_buffer = (int16_t*) malloc(1024 * sizeof(int16_t));
  if (!audio_buffer) {
    Serial.println("Failed to allocate memory buffer for recording!");
    file.close();
    return;
  }

  int samples_read = 0;
  unsigned long start_time = millis();

  // Record until time expires or button is released
  // Debounce/hold control: continues as long as button is held down OR up to max time
  while (samples_read < samples_to_read && (digitalRead(RECORD_BUTTON_PIN) == LOW || (millis() - start_time < 1500))) {
    size_t bytes_read = 0;
    i2s_read(I2S_MIC_PORT, audio_buffer, 1024 * sizeof(int16_t), &bytes_read, portMAX_DELAY);
    
    int read_samples = bytes_read / sizeof(int16_t);
    file.write((const uint8_t*)audio_buffer, bytes_read);
    bytes_written += bytes_read;
    samples_read += read_samples;
  }

  free(audio_buffer);
  
  // Rewind file and update WAV header fields with actual sizes
  file.seek(0);
  
  byte header[44];
  uint32_t totalDataLen = bytes_written;
  uint32_t totalAudioLen = totalDataLen + 36;
  uint16_t channels = 1;
  uint32_t byteRate = SAMPLE_RATE * channels * 2;
  
  header[0] = 'R'; header[1] = 'I'; header[2] = 'F'; header[3] = 'F';
  header[4] = (byte)(totalAudioLen & 0xff);
  header[5] = (byte)((totalAudioLen >> 8) & 0xff);
  header[6] = (byte)((totalAudioLen >> 16) & 0xff);
  header[7] = (byte)((totalAudioLen >> 24) & 0xff);
  header[8] = 'W'; header[9] = 'A'; header[10] = 'V'; header[11] = 'E';
  header[12] = 'f'; header[13] = 'm'; header[14] = 't'; header[15] = ' ';
  header[16] = 16; header[17] = 0; header[18] = 0; header[19] = 0; // Sub-chunk size
  header[20] = 1; header[21] = 0; // PCM format
  header[22] = channels; header[23] = 0;
  header[24] = (byte)(SAMPLE_RATE & 0xff);
  header[25] = (byte)((SAMPLE_RATE >> 8) & 0xff);
  header[26] = (byte)((SAMPLE_RATE >> 16) & 0xff);
  header[27] = (byte)((SAMPLE_RATE >> 24) & 0xff);
  header[28] = (byte)(byteRate & 0xff);
  header[29] = (byte)((byteRate >> 8) & 0xff);
  header[30] = (byte)((byteRate >> 16) & 0xff);
  header[31] = (byte)((byteRate >> 24) & 0xff);
  header[32] = 2; header[33] = 0; // Block align
  header[34] = BITS_PER_SAMPLE; header[35] = 0;
  header[36] = 'd'; header[37] = 'a'; header[38] = 't'; header[39] = 'a';
  header[40] = (byte)(totalDataLen & 0xff);
  header[41] = (byte)((totalDataLen >> 8) & 0xff);
  header[42] = (byte)((totalDataLen >> 16) & 0xff);
  header[43] = (byte)((totalDataLen >> 24) & 0xff);
  
  file.write(header, 44);
  file.close();
  
  Serial.printf("<<< Recording finished. Saved %d bytes to file.\n", bytes_written);
}

void writeWAVHeader(File &file) {
  // Placeholder header, overwritten at the end of recording
  byte header[44] = {0};
  file.write(header, 44);
}

void sendAudioToCloud() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Cannot upload: WiFi disconnected!");
    sendSerialCommand("HS"); // Shake head to indicate error
    return;
  }

  Serial.println("Uploading audio to Django cloud server...");
  sendTelemetryUpdate(simulated_battery, "speaking", "Uploading voice audio file.");
  
  File file = SPIFFS.open(WAV_FILE_PATH, FILE_READ);
  if (!file) {
    Serial.println("Recorded audio file missing!");
    return;
  }

  HTTPClient http;
  http.begin(server_url);
  http.addHeader("X-Robot-API-Key", api_key);
  
  // Set up boundary for multipart data
  String boundary = "----ESP32Boundary" + String(millis(), HEX);
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);

  // Read entire file content to send
  size_t fileSize = file.size();
  
  // Build boundary headers
  String head = "--" + boundary + "\r\n";
  head += "Content-Disposition: form-data; name=\"audio\"; filename=\"recorded_voice.wav\"\r\n";
  head += "Content-Type: audio/wav\r\n\r\n";
  
  String tail = "\r\n--" + boundary + "--\r\n";
  
  // Calculate total payload length
  size_t totalLength = head.length() + fileSize + tail.length();
  
  // Create buffer for streaming upload
  uint8_t *buffer = (uint8_t *)malloc(2048);
  if (!buffer) {
    Serial.println("Buffer allocation failed!");
    file.close();
    http.end();
    return;
  }

  // Stream data out over HTTP POST
  int httpCode = http.sendRequest("POST", 
    [head, &file, tail, buffer, fileSize](WiFiClient *stream) -> int {
      // 1. Write header boundary
      stream->write((const uint8_t*)head.c_str(), head.length());
      
      // 2. Stream WAV body
      size_t remaining = fileSize;
      while (remaining > 0) {
        size_t toRead = remaining > 2048 ? 2048 : remaining;
        file.read(buffer, toRead);
        stream->write(buffer, toRead);
        remaining -= toRead;
      }
      
      // 3. Write closing boundary
      stream->write((const uint8_t*)tail.c_str(), tail.length());
      return 0;
    }, 
    totalLength
  );

  file.close();
  free(buffer);

  if (httpCode > 0) {
    String response = http.getString();
    Serial.printf("Server Response Code: %d\n", httpCode);
    
    if (httpCode == 200) {
      DynamicJsonDocument doc(1024);
      DeserializationError error = deserializeJson(doc, response);
      
      if (!error) {
        const char* reply = doc["reply"];
        const char* audio_url = doc["audio_url"];
        bool mouth = doc["mouth"];
        bool eye = doc["eye"];
        bool head = doc["head"];
        
        Serial.printf("AI Reply: '%s'\n", reply);
        Serial.printf("Audio URL: '%s'\n", audio_url);
        
        // Execute dynamic reaction commands on Arduino
        if (head) {
          // If response is positive/agreeable, Nod. Otherwise, Shake
          String reply_str = String(reply);
          reply_str.toLowerCase();
          if (reply_str.indexOf("yes") >= 0 || reply_str.indexOf("sure") >= 0 || reply_str.indexOf("agree") >= 0) {
            sendSerialCommand("HN"); // Head Nod
          } else if (reply_str.indexOf("no") >= 0 || reply_str.indexOf("not") >= 0 || reply_str.indexOf("sorry") >= 0) {
            sendSerialCommand("HS"); // Head Shake
          } else {
            sendSerialCommand("H1"); // Gentle movement
          }
        }
        
        if (eye) {
          sendSerialCommand("E1"); // Dynamic random shifting
        }
        
        // Download and play MP3 voice file
        if (audio_url && strlen(audio_url) > 0) {
          playMP3Speech(audio_url);
        }
      } else {
        Serial.print("JSON parsing failed: ");
        Serial.println(error.c_str());
        sendSerialCommand("HS");
      }
    } else {
      Serial.println("Upload failed: Check status logs.");
      sendSerialCommand("HS");
    }
  } else {
    Serial.printf("POST connection failed, error: %s\n", http.errorToString(httpCode).c_str());
    sendSerialCommand("HS");
  }
  
  http.end();
}

void playMP3Speech(const char* url) {
  // Clean up any running playback
  if (mp3_decoder) {
    mp3_decoder->stop();
    delete mp3_decoder;
    mp3_decoder = nullptr;
  }
  if (audio_stream) {
    delete audio_stream;
    audio_stream = nullptr;
  }
  if (audio_out) {
    delete audio_out;
    audio_out = nullptr;
  }

  Serial.printf("Streaming response audio from: %s\n", url);
  
  // Set speaking state
  is_speaking = true;
  sendTelemetryUpdate(simulated_battery, "speaking", "Playing synthesized response audio.");
  sendSerialCommand("M1"); // Tell Arduino to begin moving mouth in sync with speaking

  // Initialize ESP8266Audio generators
  audio_stream = new AudioFileSourceHTTPStream(url);
  audio_out = new AudioOutputI2S();
  
  // Set ESP32 I2S output mode to internal 8-bit DAC on Pin 25 and 26
  audio_out->SetOutputMode(AudioOutputI2S::DAC_BUILTIN);
  
  mp3_decoder = new AudioGeneratorMP3();
  mp3_decoder->begin(audio_stream, audio_out);
}

void checkAudioPlayback() {
  if (is_speaking && mp3_decoder) {
    if (mp3_decoder->isRunning()) {
      if (!mp3_decoder->loop()) {
        // Playback finished naturally
        mp3_decoder->stop();
        Serial.println("Audio playback finished.");
        
        // Clean up stream variables
        delete mp3_decoder;
        mp3_decoder = nullptr;
        delete audio_stream;
        audio_stream = nullptr;
        delete audio_out;
        audio_out = nullptr;
        
        // Update state and notify Arduino
        is_speaking = false;
        sendSerialCommand("M0"); // Turn mouth movement off (close jaw)
        sendTelemetryUpdate(simulated_battery, "idle", "Speech playback complete.");
      }
    } else {
      // Stopped/Ended unexpectedly
      is_speaking = false;
      sendSerialCommand("M0");
      sendTelemetryUpdate(simulated_battery, "idle", "Speech playback halted unexpectedly.");
    }
  }
}

void sendSerialCommand(const char* cmd) {
  Serial.printf("Sending Serial Command to Arduino: '%s'\n", cmd);
  Serial2.printf("%s\n", cmd);
}

void handleWiFiReconnection() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi connection lost! Reconnecting...");
    WiFi.disconnect();
    WiFi.begin(ssid, password);
    
    int wait_counter = 0;
    while (WiFi.status() != WL_CONNECTED && wait_counter < 10) {
      delay(1000);
      Serial.print(".");
      wait_counter++;
    }
    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("\nWiFi Reconnected!");
    }
  }
}

void sendTelemetryUpdate(float battery, const char* mode, const char* log_msg) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(status_url);
  http.addHeader("X-Robot-API-Key", api_key);
  http.addHeader("Content-Type", "application/json");

  // Create JSON payload
  DynamicJsonDocument doc(256);
  doc["battery_level"] = battery;
  doc["current_mode"] = mode;
  doc["is_online"] = true;
  if (log_msg) {
    doc["log_message"] = log_msg;
  }

  String payload;
  serializeJson(doc, payload);

  int httpCode = http.POST(payload);
  if (httpCode <= 0) {
    Serial.printf("Telemetry ping failed: %s\n", http.errorToString(httpCode).c_str());
  }
  http.end();
}
