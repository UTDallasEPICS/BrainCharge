#include <AFMotor.h>

// Initialize all 4 motors
AF_DCMotor motorFL(1); // Front Left
AF_DCMotor motorFR(2); // Front Right
AF_DCMotor motorRL(3); // Rear Left
AF_DCMotor motorRR(4); // Rear Right

void setup() {
  //run once
  // Set speed for all motors (0 is off, 255 is max)
  int startSpeed = 200;
  motorFL.setSpeed(startSpeed);
  motorFR.setSpeed(startSpeed);
  motorRL.setSpeed(startSpeed);
  motorRR.setSpeed(startSpeed);
}

void loop() {
  // --- Move Forward ---
  //run constantly
  /*
  motorFL.run(FORWARD);
  motorFR.run(FORWARD);
  motorRL.run(FORWARD);
  motorRR.run(FORWARD);
  delay(2000);
  */

  motorFL.run(FORWARD);
  motorFR.run(FORWARD);
  motorRL.run(FORWARD);
  motorRR.run(FORWARD);
  delay(2000);



  // --- Stop ---
  motorFL.run(RELEASE);
  motorFR.run(RELEASE);
  motorRL.run(RELEASE);
  motorRR.run(RELEASE);
  delay(1000);

  // --- Move Backward ---
  motorFL.run(BACKWARD);
  motorFR.run(BACKWARD);
  motorRL.run(BACKWARD);
  motorRR.run(BACKWARD);
  delay(2000);
}