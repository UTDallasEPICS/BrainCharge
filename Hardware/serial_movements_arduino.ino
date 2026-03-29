#include <AFMotor.h>

// Initialize all 4 motors
AF_DCMotor motorBL(1); // Back Left
AF_DCMotor motorFL(2); // Front Left
AF_DCMotor motorFR(3); // Front Right
AF_DCMotor motorBR(4); // Back Right

void move_forward() {
  motorFL.run(FORWARD);
  motorFR.run(FORWARD);
  motorBL.run(FORWARD);
  motorBR.run(FORWARD);
}

void move_backward() {
  motorFL.run(BACKWARD);
  motorFR.run(BACKWARD);
  motorBL.run(BACKWARD);
  motorBR.run(BACKWARD);
}

void stop_movement() {
  motorFL.run(RELEASE);
  motorFR.run(RELEASE);
  motorBL.run(RELEASE);
  motorBR.run(RELEASE);
}


void turn_right() {
  motorFL.run(FORWARD);
  motorFR.run(BACKWARD);
  motorBL.run(FORWARD);
  motorBR.run(BACKWARD);
}

void turn_left() {
  motorFL.run(BACKWARD);
  motorFR.run(FORWARD);
  motorBL.run(BACKWARD);
  motorBR.run(FORWARD);
}

void strafe_left() {
  motorFL.run(BACKWARD);
  motorFR.run(FORWARD);
  motorBL.run(FORWARD);
  motorBR.run(BACKWARD);
}

void strafe_right() {
  motorFL.run(FORWARD);
  motorFR.run(BACKWARD);
  motorBL.run(BACKWARD);
  motorBR.run(FORWARD);
}

void setup() {
  Serial.begin(115200);
  
  int startSpeed = 200;
  motorFL.setSpeed(startSpeed);
  motorFR.setSpeed(startSpeed);
  motorBL.setSpeed(startSpeed);
  motorBR.setSpeed(startSpeed);
}

void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n'); 
    command.trim();

    if (command == "forward") {
      //Serial.println("LED is ON");
      move_forward();
    } else if (command == "backward") {
      move_backward();
    }  else if (command == "right") {
      turn_right();
    }  else if (command == "left") {
      turn_left();
    } else if (command == "strafe right") {
      strafe_right();
    }  else if (command == "strafe left") {
      strafe_left();
    } else {
      stop_movement();
    }
  }
}