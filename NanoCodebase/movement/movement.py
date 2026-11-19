#!/usr/bin/env python3
"""
    Jetson header pin   DRV8833 pin    Purpose
    -----------------   -----------    ------------------------------
    32 (hardware PWM)   AIN1           Motor A speed (PWM)
    16                   AIN2           Motor A direction
    33 (hardware PWM)   BIN1           Motor B speed (PWM)
    22                  BIN2           Motor B direction
    18                  nSLEEP         High = chip enabled, low = sleep
    any GND pin         GND            Common ground (REQUIRED)
"""

import time
import Jetson.GPIO as GPIO

TARGET_Y = 100
Y_TOLERANCE = 5
X_TOLERANCE = 0.02
Z_TOLERANCE = 0.02

TURN_SPEED = 0.1
FORWARD_SPEED = 0.1

PWM_FREQ_HZ = 25_000

NSLEEP_PIN = 18  # set to None if nSLEEP is hard-wired high

MOTORS = {
    "A": {"pwm_pin": 32, "dir_pin": 16},  # AIN1 / AIN2
    "B": {"pwm_pin": 33, "dir_pin": 22},  # BIN1 / BIN2
}

RAMP_STEP_SECONDS = 0.02  # time between speed steps while ramping
RAMP_STEP_SIZE = 0.02     # speed change per step (speed range -1.0..1.0)


class Motor:
    def __init__(self, pwm_pin, dir_pin, freq_hz=PWM_FREQ_HZ):
        self.dir_pin = dir_pin
        self.speed = 0.0  # -1.0 (full reverse) .. 1.0 (full forward)

        GPIO.setup(self.dir_pin, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(pwm_pin, GPIO.OUT, initial=GPIO.LOW)

        self.pwm = GPIO.PWM(pwm_pin, freq_hz)
        self.pwm.start(0)  # IN1 low + IN2 low = coast

    def set_speed(self, speed):
        speed = max(-1.0, min(1.0, speed))
        magnitude = abs(speed) * 100.0

        if speed > 0:
            GPIO.output(self.dir_pin, GPIO.LOW)
            self.pwm.ChangeDutyCycle(magnitude)
        elif speed < 0:
            GPIO.output(self.dir_pin, GPIO.HIGH)
            self.pwm.ChangeDutyCycle(100.0 - magnitude)  # inverted for reverse
        else:
            GPIO.output(self.dir_pin, GPIO.LOW)
            self.pwm.ChangeDutyCycle(0)  # coast

        self.speed = speed

    def brake(self):
        GPIO.output(self.dir_pin, GPIO.HIGH)
        self.pwm.ChangeDutyCycle(100.0)
        self.speed = 0.0

    def stop(self):
        """Coast to a stop."""
        self.set_speed(0.0)

    def close(self):
        self.stop()


        

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

if NSLEEP_PIN is not None:
    GPIO.setup(NSLEEP_PIN, GPIO.OUT, initial=GPIO.HIGH)  # wake the driver
    time.sleep(0.002)  # DRV8833 needs a moment after wake-up

left = Motor(**MOTORS["A"])
right = Motor(**MOTORS["B"])

def drive(left_amt, right_amt):
    left.set_speed(left_amt)
    right.set_speed(right_amt)

def ramp_drive(left_amt, right_amt):
    """Ramp both motors together toward their targets."""
    left_amt = max(-1.0, min(1.0, left_amt))
    right_amt = max(-1.0, min(1.0, right_amt))
    while (abs(left.speed - left_amt) > 1e-6
            or abs(right.speed - right_amt) > 1e-6):
        for motor, target in ((left, left_amt), (right, right_amt)):
            delta = target - motor.speed
            step = max(-RAMP_STEP_SIZE, min(RAMP_STEP_SIZE, delta))
            motor.set_speed(motor.speed + step)
        time.sleep(RAMP_STEP_SECONDS)

def go_forward(speed):
    ramp_drive(speed, speed)

def turn_left(speed):
    ramp_drive(-1 * abs(speed), abs(speed))

def turn_right(speed):
    ramp_drive(abs(speed), -1 * abs(speed))

def stop():
    ramp_drive(0.0, 0.0)

def brake():
    left.brake()
    right.brake()

def pan_up():
    return

def pan_down():
    return

def shutdown():
    left.close()
    right.close()
    if NSLEEP_PIN is not None:
        GPIO.output(NSLEEP_PIN, GPIO.LOW)  # put the driver to sleep
    try:
        GPIO.cleanup()
    except OSError as e:
        print(f"GPIO cleanup warning: {e}")


# pass the target in cm and move toward it

# if the user is out of threshold, start
# if they are in range, stop the movement
# signal based movement

# with the orchestrator
def move_toward_user(x, y, z):
    # Turn first until aligned, then close or open the distance.
    # Re-checked on every call, so a moving user gets re-aligned.
    if abs(x) > X_TOLERANCE:
        if x < 0:
            turn_left(TURN_SPEED)
        else:
            turn_right(TURN_SPEED)
        in_position = False
    elif abs(y - TARGET_Y) > Y_TOLERANCE:
        if y > TARGET_Y:
            go_forward(FORWARD_SPEED)
        else:
            go_forward(-FORWARD_SPEED)
        in_position = False
    else:
        stop()
        in_position = True
 
    # Camera tilt is independent of the wheels.
    if abs(z) > Z_TOLERANCE:
        if z < 0:
            pan_down()
        else:
            pan_up()
 
    return in_position




def main():
    try:
        print("Forward (ramped) at 50%")
        ramp_drive(0.5, 0.5)
        time.sleep(2)

        print("Pivot turn")
        ramp_drive(0.4, -0.4)
        time.sleep(1)

        print("Reverse at 30%")
        ramp_drive(-0.3, -0.3)
        time.sleep(2)

        print("Stop")
        stop()

    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        shutdown()  # always zero outputs, sleep the driver, free pins


if __name__ == "__main__":
    main()