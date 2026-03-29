void setup() {
  Serial.begin(115200); // Higher baud rate for faster communication
  pinMode(13, OUTPUT);
  
  // Optional: Set a shorter timeout if you still want to use readString()
  // Serial.setTimeout(50); 
}

void loop() {
  if (Serial.available() > 0) {
    // Faster: stops reading as soon as it sees the end of the line
    String command = Serial.readStringUntil('\n'); 
    command.trim();

    if (command == "on") {
      digitalWrite(13, HIGH);
      Serial.println("LED is ON");
    } else if (command == "off") {
      digitalWrite(13, LOW);
      Serial.println("LED is OFF");
    }
  }
}
