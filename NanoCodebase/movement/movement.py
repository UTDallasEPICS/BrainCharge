#!/usr/bin/env python3
"""
Two-motor control for Jetson Orin Nano + DRV8833 dual H-bridge, using Jetson.GPIO.

ASSUMED WIRING (change the constants below to match yours):

    Jetson header pin   DRV8833 pin    Purpose
    -----------------   -----------    ------------------------------
    32 (hardware PWM)   AIN1           Motor A speed (PWM)
    11                  AIN2           Motor A direction
    33 (hardware PWM)   BIN1           Motor B speed (PWM)
    13                  BIN2           Motor B direction
    15                  nSLEEP         High = chip enabled, low = sleep
    any GND pin         GND            Common ground (REQUIRED)

    Motor power supply (2.7-10.8 V) -> DRV8833 VM / GND. Do NOT power the
    motors from the Jetson. Motors connect to AOUT1/AOUT2 and BOUT1/BOUT2.

    If your breakout has nSLEEP tied to 3.3 V already (or a jumper), you can
    leave NSLEEP_PIN as None.

HOW SPEED/DIRECTION WORK WITH ONE PWM PIN PER MOTOR:
    Only pins 32 and 33 have hardware PWM, so PWM goes on IN1 and IN2 is a
    plain GPIO that selects direction:

      Forward:  IN2 = LOW,  IN1 = PWM(duty = speed)         (fast decay)
      Reverse:  IN2 = HIGH, IN1 = PWM(duty = 100 - speed)   (slow decay)
      Coast:    IN1 = LOW,  IN2 = LOW
      Brake:    IN1 = HIGH, IN2 = HIGH

    In reverse the PWM is inverted: IN1 low means the motor is driven, IN1
    high means brake. That's why reverse duty is (100 - speed).

    Trade-off: forward coasts during the PWM off-time, reverse brakes during
    it, so the motor can feel slightly different in the two directions. If
    that matters later, use a second hardware PWM pin per motor or an
    external PWM source.

PREREQUISITES (on the Jetson, not WSL):
  1. Enable PWM on pins 32 and 33 with jetson-io, then reboot.
  2. Jetson.GPIO installed, and user in the 'gpio' group (or run with sudo).

NOTES:
  - Jetson.GPIO takes duty cycle as a percentage (0-100). PWM resolution
    in bits is set by the hardware/driver, not by this script.
  - The DRV8833 is rated for PWM up to roughly 50 kHz, so 25 kHz should be
    fine. If you see odd behavior, lower PWM_FREQ_HZ to rule out the signal.
"""

import time
import Jetson.GPIO as GPIO

# ---------------------------------------------------------------- config ---
PWM_FREQ_HZ = 25_000

NSLEEP_PIN = 15  # set to None if nSLEEP is hard-wired high

MOTORS = {
    "A": {"pwm_pin": 32, "dir_pin": 11},  # AIN1 / AIN2
    "B": {"pwm_pin": 33, "dir_pin": 13},  # BIN1 / BIN2
}

RAMP_STEP_SECONDS = 0.02  # time between speed steps while ramping
RAMP_STEP_SIZE = 0.02     # speed change per step (speed range -1.0..1.0)


# ----------------------------------------------------------------- motor ---
class Motor:
    """One DC motor on a DRV8833 channel (IN1 = PWM, IN2 = direction)."""

    def __init__(self, pwm_pin, dir_pin, freq_hz=PWM_FREQ_HZ):
        self.dir_pin = dir_pin
        self.speed = 0.0  # -1.0 (full reverse) .. 1.0 (full forward)

        GPIO.setup(self.dir_pin, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(pwm_pin, GPIO.OUT, initial=GPIO.LOW)

        self.pwm = GPIO.PWM(pwm_pin, freq_hz)
        self.pwm.start(0)  # IN1 low + IN2 low = coast

    def set_speed(self, speed):
        """Set speed immediately. speed in [-1.0, 1.0]; sign sets direction."""
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
        """Short the motor terminals (IN1 = IN2 = HIGH) for a hard stop."""
        GPIO.output(self.dir_pin, GPIO.HIGH)
        self.pwm.ChangeDutyCycle(100.0)
        self.speed = 0.0

    def stop(self):
        """Coast to a stop."""
        self.set_speed(0.0)

    def close(self):
        self.stop()
        self.pwm.stop()


# ----------------------------------------------------------------- robot ---
class Robot:
    """Differential drive: motor A = left, motor B = right (swap if needed)."""

    def __init__(self):
        GPIO.setmode(GPIO.BOARD)
        GPIO.setwarnings(False)

        if NSLEEP_PIN is not None:
            GPIO.setup(NSLEEP_PIN, GPIO.OUT, initial=GPIO.HIGH)  # wake the driver
            time.sleep(0.002)  # DRV8833 needs a moment after wake-up

        self.left = Motor(**MOTORS["A"])
        self.right = Motor(**MOTORS["B"])

    def drive(self, left, right):
        self.left.set_speed(left)
        self.right.set_speed(right)

    def ramp_drive(self, left, right):
        """Ramp both motors together toward their targets."""
        left = max(-1.0, min(1.0, left))
        right = max(-1.0, min(1.0, right))
        while (abs(self.left.speed - left) > 1e-6
               or abs(self.right.speed - right) > 1e-6):
            for motor, target in ((self.left, left), (self.right, right)):
                delta = target - motor.speed
                step = max(-RAMP_STEP_SIZE, min(RAMP_STEP_SIZE, delta))
                motor.set_speed(motor.speed + step)
            time.sleep(RAMP_STEP_SECONDS)

    def stop(self):
        self.drive(0.0, 0.0)

    def brake(self):
        self.left.brake()
        self.right.brake()

    def shutdown(self):
        self.left.close()
        self.right.close()
        if NSLEEP_PIN is not None:
            GPIO.output(NSLEEP_PIN, GPIO.LOW)  # put the driver to sleep
        GPIO.cleanup()


# ------------------------------------------------------------------ demo ---
def main():
    robot = Robot()
    try:
        print("Forward (ramped) at 50%")
        robot.ramp_drive(0.5, 0.5)
        time.sleep(2)

        print("Pivot turn")
        robot.ramp_drive(0.4, -0.4)
        time.sleep(1)

        print("Reverse at 30%")
        robot.ramp_drive(-0.3, -0.3)
        time.sleep(2)

        print("Stop")
        robot.ramp_drive(0.0, 0.0)

    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        robot.shutdown()  # always zero outputs, sleep the driver, free pins


if __name__ == "__main__":
    main()