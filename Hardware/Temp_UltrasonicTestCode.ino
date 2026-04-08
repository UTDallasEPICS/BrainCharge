//this is just the temporary code for testing the ultrasonic without the built in library. 
// Next steps: incorporate into robot movement code, test. Then wire, test.

#include <Wire.h>

#define ULTRASOUND_ADDR 0x77 

void setup() {
  Wire.begin();
  Serial.begin(115200);
}

void loop() {
  int distance = readDistance();
  Serial.println(distance);
  delay(500);
}

int readDistance() {
  Wire.beginTransmission(ULTRASOUND_ADDR);
  Wire.write(0x00); 
  Wire.endTransmission();

  //get back info from wire, just need the 1 byte
  Wire.requestFrom(ULTRASOUND_ADDR, 2);

  uint8_t low = Wire.read(); //low integer
  uint8_t high = Wire.read(); //high integer

  return (high << 8) | low;

}