/**
 * AI Humanoid Robot Assistant - Arduino UNO Motion Controller
 * 
 * Hardware:
 * - Arduino UNO R3
 * - Servos:
 *   - SG90 Eye Left Right -> Pin 9
 *   - SG90 Eye Up Down    -> Pin 10
 *   - MG90S Mouth         -> Pin 11
 *   - MG945 Head Rotation -> Pin 12
 * - External 5V Power Supply for Servos (Common Ground with Arduino & ESP32 is MANDATORY)
 * - Serial Link to ESP32: SoftwareSerial RX (Pin 2) and TX (Pin 3)
 */

#include <Servo.h>
#include <SoftwareSerial.h>

// Pin Definitions
#define EYE_LR_PIN 9
#define EYE_UD_PIN 10
#define MOUTH_PIN 11
#define HEAD_ROT_PIN 12
#define RX_PIN 2
#define TX_PIN 3

// Software Serial to communicate with ESP32 (to avoid blocking USB programming port)
SoftwareSerial espSerial(RX_PIN, TX_PIN);

// Struct for non-blocking smooth servo movement
struct SmoothServo {
  int pin;
  int currentPos;
  int targetPos;
  float stepSize;       // Angle change per update tick
  unsigned long lastTick;
  int minAngle;
  int maxAngle;
  Servo servoObj;
  
  void attachServo(int p, int initPos, int minA, int maxA) {
    pin = p;
    currentPos = initPos;
    targetPos = initPos;
    minAngle = minA;
    maxAngle = maxA;
    lastTick = 0;
    stepSize = 1.0;
    servoObj.attach(pin);
    servoObj.write(initPos);
  }
  
  void setTarget(int target, float speed) {
    targetPos = constrain(target, minAngle, maxAngle);
    stepSize = speed;
  }
  
  void update() {
    if (currentPos == targetPos) return;
    
    unsigned long now = millis();
    if (now - lastTick >= 15) { // 15ms tick rate (~66Hz updates)
      lastTick = now;
      if (currentPos < targetPos) {
        currentPos += ceil(stepSize);
        if (currentPos > targetPos) currentPos = targetPos;
      } else {
        currentPos -= ceil(stepSize);
        if (currentPos < targetPos) currentPos = targetPos;
      }
      servoObj.write(currentPos);
    }
  }
  
  bool isMoving() {
    return currentPos != targetPos;
  }
};

// Instantiating Servos
SmoothServo eyeLR;
SmoothServo eyeUD;
SmoothServo mouth;
SmoothServo headRot;

// State Variables
bool mouthActive = false;
bool eyeActive = true;
bool headActive = true;

// Timers for Random Idle Movements
unsigned long lastBlinkTime = 0;
unsigned long nextBlinkInterval = 4000;

unsigned long lastEyeShiftTime = 0;
unsigned long nextEyeShiftInterval = 2500;

unsigned long lastHeadMoveTime = 0;
unsigned long nextHeadMoveInterval = 5000;

unsigned long lastMouthMoveTime = 0;
unsigned long nextMouthMoveInterval = 150;

// Gesture sequence states
enum Gesture { GESTURE_NONE, GESTURE_NOD, GESTURE_SHAKE };
Gesture activeGesture = GESTURE_NONE;
unsigned long gestureStartTime = 0;
int gestureStep = 0;

void handleSerialCommand(String cmd);
void performIdleMovement();
void handleGestureSequences();

void setup() {
  Serial.begin(115200);   // USB Debug Serial
  espSerial.begin(9600);  // Serial Link to ESP32 (matches ESP32 Serial2)
  
  // Attach servos with physical operating angle constraints
  eyeLR.attachServo(EYE_LR_PIN, 90, 45, 135);     // Center: 90, Range: 45-135
  eyeUD.attachServo(EYE_UD_PIN, 90, 60, 120);     // Center: 90, Range: 60-120
  mouth.attachServo(MOUTH_PIN, 10, 10, 50);       // Center/Closed: 10, Open: 50
  headRot.attachServo(HEAD_ROT_PIN, 90, 45, 135); // Center: 90, Range: 45-135

  randomSeed(analogRead(0)); // Seed random generator with floating analog pin noise
  
  lastBlinkTime = millis();
  lastEyeShiftTime = millis();
  lastHeadMoveTime = millis();
  
  Serial.println("Arduino Humanoid Motion Controller initialized.");
}

void loop() {
  // Update servo positions (non-blocking tick)
  eyeLR.update();
  eyeUD.update();
  mouth.update();
  headRot.update();

  // 1. Check for incoming Serial commands from ESP32
  if (espSerial.available() > 0) {
    String cmd = espSerial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() > 0) {
      handleSerialCommand(cmd);
    }
  }

  // 2. Perform background/idle gestures
  performIdleMovement();

  // 3. Update active nod/shake gesture sequences
  handleGestureSequences();
}

void handleSerialCommand(String cmd) {
  Serial.print("Received Command: '");
  Serial.print(cmd);
  Serial.println("'");

  if (cmd.startsWith("M")) {
    // Mouth command: M1 = speaking (flapping), M0 = silent (closed)
    if (cmd.charAt(1) == '1') {
      mouthActive = true;
    } else {
      mouthActive = false;
      mouth.setTarget(10, 4.0); // Close mouth immediately
    }
  } 
  else if (cmd.startsWith("E")) {
    // Eye state: E1 = enable random shifting, E0 = center
    if (cmd.charAt(1) == '1') {
      eyeActive = true;
    } else {
      eyeActive = false;
      eyeLR.setTarget(90, 3.0);
      eyeUD.setTarget(90, 3.0);
    }
  } 
  else if (cmd.startsWith("H")) {
    // Head state: H1 = look around, H0 = center head
    if (cmd.charAt(1) == '1') {
      headActive = true;
    } else if (cmd.charAt(1) == '0') {
      headActive = false;
      headRot.setTarget(90, 2.0); // Center head
    } 
    else if (cmd.charAt(1) == 'N') {
      // Trigger Head Nod gesture
      activeGesture = GESTURE_NOD;
      gestureStartTime = millis();
      gestureStep = 0;
    } 
    else if (cmd.charAt(1) == 'S') {
      // Trigger Head Shake gesture
      activeGesture = GESTURE_SHAKE;
      gestureStartTime = millis();
      gestureStep = 0;
    }
  }
}

void performIdleMovement() {
  unsigned long now = millis();

  // 1. Natural Blinking: blink eyes by shifting Up-Down servo quickly down then up
  if (now - lastBlinkTime > nextBlinkInterval) {
    lastBlinkTime = now;
    nextBlinkInterval = random(3000, 8000); // Set next blink time between 3-8s
    
    // Quick blink motion (gaze down quickly, return to center)
    eyeUD.setTarget(110, 8.0);
    delay(80); // Quick delay okay since blinking is extremely short
    eyeUD.setTarget(90, 8.0);
  }

  // 2. Idle Eye Shifts: shift eyes to look around randomly when eyeActive is true
  if (eyeActive && (activeGesture == GESTURE_NONE) && (now - lastEyeShiftTime > nextEyeShiftInterval)) {
    lastEyeShiftTime = now;
    nextEyeShiftInterval = random(1500, 4000);
    
    int targetX = random(70, 110);
    int targetY = random(80, 100);
    eyeLR.setTarget(targetX, 3.0);
    eyeUD.setTarget(targetY, 3.0);
  }

  // 3. Idle Head Panning: pan head slowly when headActive is true
  if (headActive && (activeGesture == GESTURE_NONE) && (now - lastHeadMoveTime > nextHeadMoveInterval)) {
    lastHeadMoveTime = now;
    nextHeadMoveInterval = random(4000, 9000);
    
    int targetPan = random(75, 105);
    headRot.setTarget(targetPan, 0.6); // Very slow speed for realistic head panning
  }

  // 4. Speech Mouth Flapping: flap mouth between closed (10) and open (15-45) while mouthActive is true
  if (mouthActive && (now - lastMouthMoveTime > nextMouthMoveInterval)) {
    lastMouthMoveTime = now;
    nextMouthMoveInterval = random(100, 250); // Set speech rhythm speed
    
    int mouthOpenAngle = random(20, 48); // Vary open angle for organic look
    if (mouth.currentPos <= 15) {
      mouth.setTarget(mouthOpenAngle, 5.0); // Open jaw
    } else {
      mouth.setTarget(10, 5.0); // Close jaw
    }
  }
}

void handleGestureSequences() {
  if (activeGesture == GESTURE_NONE) return;
  
  unsigned long elapsed = millis() - gestureStartTime;
  
  if (activeGesture == GESTURE_NOD) {
    // Simulating head nod by shifting eyes down/up and slightly wiggling head
    if (gestureStep == 0) {
      eyeUD.setTarget(110, 4.0);
      headRot.setTarget(95, 2.0);
      gestureStep = 1;
      gestureStartTime = millis();
    } 
    else if (gestureStep == 1 && elapsed > 250) {
      eyeUD.setTarget(70, 4.0);
      headRot.setTarget(85, 2.0);
      gestureStep = 2;
      gestureStartTime = millis();
    } 
    else if (gestureStep == 2 && elapsed > 250) {
      eyeUD.setTarget(90, 4.0);
      headRot.setTarget(90, 2.0);
      gestureStep = 3;
      gestureStartTime = millis();
    }
    else if (gestureStep == 3 && elapsed > 250) {
      activeGesture = GESTURE_NONE; // Nod completed
    }
  } 
  
  else if (activeGesture == GESTURE_SHAKE) {
    // Shake Head: rotate head yaw left, then right, then left, then center
    if (gestureStep == 0) {
      headRot.setTarget(70, 4.0);
      gestureStep = 1;
      gestureStartTime = millis();
    } 
    else if (gestureStep == 1 && elapsed > 250) {
      headRot.setTarget(110, 4.0);
      gestureStep = 2;
      gestureStartTime = millis();
    } 
    else if (gestureStep == 2 && elapsed > 250) {
      headRot.setTarget(70, 4.0);
      gestureStep = 3;
      gestureStartTime = millis();
    } 
    else if (gestureStep == 3 && elapsed > 250) {
      headRot.setTarget(90, 4.0);
      gestureStep = 4;
      gestureStartTime = millis();
    } 
    else if (gestureStep == 4 && elapsed > 250) {
      activeGesture = GESTURE_NONE; // Shake completed
    }
  }
}
