#include <SPI.h>
#include <MFRC522.h>
#include <Servo.h>

// Pin Definitions
#define SS_PIN 10
#define RST_PIN 9
#define RELAY_PIN 7  // Controls 12V Solenoid via Relay Module
#define SERVO_PIN 6  // Controls Gate/Latch mechanism

MFRC522 rfid(SS_PIN, RST_PIN);
Servo doorServo;

void setup() {
  Serial.begin(9600); // Serial link to Python server
  SPI.begin();
  rfid.PCD_Init();

  // Configure Relay (Most 5V relay modules are Active LOW)
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, HIGH); // Default state: OFF (Door Locked)

  // Configure Servo
  doorServo.attach(SERVO_PIN);
  doorServo.write(0); // Locked position (0 degrees)
}

void loop() {
  // Listen for authentication decision from Python backend
  if (Serial.available() > 0) {
    char response = Serial.read();
    if (response == '1') {
      grantAccess();
    } else if (response == '0') {
      denyAccess();
    }
  }

  // Look for new RFID tags
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
    return;
  }

  // Format UID bytes into a single HEX String
  String uidString = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) {
      uidString += "0";
    }
    uidString += String(rfid.uid.uidByte[i], HEX);
  }
  uidString.toUpperCase();

  // Send UID over Serial to Python
  Serial.println(uidString);

  // Stop reading current card
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();

  delay(1000); // Cooldown to prevent duplicate reads
}

void grantAccess() {
  digitalWrite(RELAY_PIN, LOW);  // Energize solenoid (Unlock)
  doorServo.write(90);           // Rotate servo to open position
  delay(3000);                   // Keep door unlocked for 3 seconds

  doorServo.write(0);            // Return servo to locked position
  digitalWrite(RELAY_PIN, HIGH); // De-energize solenoid (Relay OFF)
}

void denyAccess() {
  digitalWrite(RELAY_PIN, HIGH);
  doorServo.write(0);
}