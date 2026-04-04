#include <AFMotor.h>
#include <Wire.h>

// Initialize all 4 motors
AF_DCMotor motorBL(1); // Back Left
AF_DCMotor motorFL(2); // Front Left
AF_DCMotor motorFR(3); // Front Right
AF_DCMotor motorBR(4); // Back Right

//line following sensor
#define SENSOR_ADDR 0x48
char cmd = 's'; //this is how we will control movement for now

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
  Wire.begin();
  Serial.begin(115200);

  int startSpeed = 200;
  motorFL.setSpeed(startSpeed);
  motorFR.setSpeed(startSpeed);
  motorBL.setSpeed(startSpeed);
  motorBR.setSpeed(startSpeed);

  //brief pause
  delay(1000);

  //get rid of any weird initial readings
  getLineStop();
}

void loop() {
  bool stopStatus = getLineStop();

  if (stopStatus) { //if stop is triggered
    stop_movement(); //stop immediately
    delay(300);

    //some logic to choose the best way to move
    if (cmd == 'q') { 
      strafe_left();
    }  else if (cmd == 't') { 
      strafe_right();
    } else {
      move_backward();
    }

    delay(750); //let leaving movement run this long

    stop_movement();
    cmd = 's'; //set command to stop
  }

  // if serial communication available
  if (Serial.available() > 0) {
    cmd = Serial.read(); //read it and execute

    if (cmd == 'f') {
      move_forward();
    } else if (cmd == 'b') {
      move_backward();
    }  else if (cmd == 'r') {
      turn_right();
    }  else if (cmd == 'l') {
      turn_left();
    } else if (cmd == 'q') { 
      strafe_right();
    }  else if (cmd == 't') { 
      strafe_left();
    } else {
      stop_movement();
    }
  }
}

bool getLineStop() {
  //protocol for telling wire we want a signal
  Wire.beginTransmission(SENSOR_ADDR);
  Wire.write(0x01); 
  Wire.endTransmission();

  //get back info from wire, just need the 1 byte
  Wire.requestFrom(SENSOR_ADDR, 1);
  
  //if we got something
  if (Wire.available()) {
    byte raw = Wire.read();
    
    //for each sensor, 1 means nothing triggered, zero means boundary triggered (senses something)
    //so 0 means everything is triggered (0 0 0 0)
    //each combination has its own binary number, and therefore its own normal number
    if (raw != 0) {
      return true;  //stop the robot if see any light
    }
  }
  return false; 

}