#include <Wire.h>
#include <AFMotor.h>

void setup() {
  Serial.begin(9600);
  pinMode(A4, INPUT_PULLUP); 
  pinMode(A5, INPUT_PULLUP);
  Wire.begin();
  Wire.setClock(5000); // Ultra-slow to beat the motor shield noise
}

void loop() {
  Wire.beginTransmission(0x77); //address
  Wire.write(0x01); // Trigger to send output
  Wire.endTransmission();

  // Give it a solid window to "hear"
  delay(100); 

  Wire.requestFrom(0x77, 3);
  if (Wire.available() >= 3) { //if there are bytes of information, read them
    byte status = Wire.read();
    byte high = Wire.read();
    byte low = Wire.read();

    int distance = (high << 8) | low; //shifts the high so it's a big number and adds the low
      
    Serial.print("--- DETECTED ---");
    Serial.print(" Status: "); Serial.print(status);
    Serial.print(" | Dist: "); Serial.print(distance);
    Serial.println(" cm");
    Serial.print("High: "); Serial.print(high); Serial.print(", Low: "); Serial.println(low); 
  }
  delay(200); 
}