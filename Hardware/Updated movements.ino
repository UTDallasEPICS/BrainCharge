#include <AFMotor.h>

// Initialize all 4 motors
AF_DCMotor motorBL(1); // Back Left
AF_DCMotor motorFL(2); // Front Left
AF_DCMotor motorFR(3); // Front Right
AF_DCMotor motorBR(4); // Back Right

void setup() {
  //run once

  Serial.begin(9600);

  // Set speed for all motors (0 is off, 255 is max)
  int startSpeed = 200;
  motorFL.setSpeed(startSpeed);
  motorFR.setSpeed(startSpeed);
  motorBL.setSpeed(startSpeed);
  motorBR.setSpeed(startSpeed);
}

void loop() {

  motorBR.run(BACKWARD);
  delay(1000);

  //stop
  motorFL.run(RELEASE);
  motorFR.run(RELEASE);
  motorBL.run(RELEASE);
  motorBR.run(RELEASE);
  delay(1000);
  

  /*
  //forward
  motorFL.run(FORWARD);
  motorFR.run(FORWARD);
  motorBL.run(FORWARD);
  motorBR.run(FORWARD);
  delay(2000);

  //stop
  motorFL.run(RELEASE);
  motorFR.run(RELEASE);
  motorBL.run(RELEASE);
  motorBR.run(RELEASE);
  delay(1000);


  //turn right
  motorFL.run(FORWARD);
  motorFR.run(BACKWARD);
  motorBL.run(FORWARD);
  motorBR.run(BACKWARD);
  delay(700);

  //turn left
  motorFL.run(BACKWARD);
  motorFR.run(FORWARD);
  motorBL.run(BACKWARD);
  motorBR.run(FORWARD);
  delay(700);

  //strafe left
  motorFL.run(BACKWARD);
  motorFR.run(FORWARD);
  motorBL.run(FORWARD);
  motorBR.run(BACKWARD);
  delay(1000);

  //strafe right
  motorFL.run(FORWARD);
  motorFR.run(BACKWARD);
  motorBL.run(BACKWARD);
  motorBR.run(FORWARD);
  delay(1000);

  */

}