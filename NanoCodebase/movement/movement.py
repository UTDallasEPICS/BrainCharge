#!/usr/bin/env python3
"""
Two-motor control for Jetson Orin Nano using Jetson.GPIO.

ASSUMED WIRING (change the constants below to match yours):
  H-bridge driver with one PWM "enable" pin and two direction pins per motor
  (L298N / TB6612 / similar):

    Motor A: PWM -> header pin 32, IN1 -> pin 11, IN2 -> pin 13
    Motor B: PWM -> header pin 33, IN1 -> pin 15, IN2 -> pin 16

  Common ground between the Jetson and the motor driver is required.

PREREQUISITES (on the Jetson, not WSL):
  1. Enable PWM on pins 32 and 33:   sudo /opt/nvidia/jetson-io/jetson-io.py
     (Configure Jetson 40pin Header -> Configure header pins manually
      -> select the PWM pins -> Save and reboot)
  2. pip install Jetson.GPIO   (usually preinstalled with JetPack)
  3. User must be in the 'gpio' group, or run the script with sudo.

NOTES:
  - Jetson.GPIO takes duty cycle as a percentage (0-100, float). You can't
    choose the PWM resolution bit-depth; it's set by the hardware/driver.
    Test how finely duty cycle steps actually register on a scope.
  - 25 kHz is silent, but check your driver can handle it. An L298N is
    slow and gets inefficient at high frequencies; if the motors behave
    badly, lower PWM_FREQ_HZ (e.g. 1000-5000) to test.
"""

import time
import Jetson.GPIO as GPIO

PWM_FREQ_HZ = 25_000

MOTORS = {
    "A": {"pwm": 32, "in1": 11, "in2": 13},
    "B": {"pwm": 33, "in1": 15, "in2": 16},
}

RAMP_STEP_SECONDS = 0.02   # time between speed steps while ramping
RAMP_STEP_SIZE = 0.02      # speed change per step (speed range is -1.0..1.0)


class Motor:
    """One DC motor: PWM speed pin plus two direction pins."""

    def __init__(self, pwm_pin, in1_pin, in2_pin, freq_hz=PWM_FREQ_HZ):
        self.in1 = in1_pin
        self.in2 = in2_pin
        self.speed = 0.0  # current speed, -1.0 (full reverse) .. 1.0 (full forward)

        GPIO.setup(self.in1, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(self.in2, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(pwm_pin, GPIO.OUT, initial=GPIO.LOW)

        self.pwm = GPIO.PWM(pwm_pin, freq_hz)
        self.pwm.start(0)

    def set_speed(self, speed):
        """Set speed immediately. speed in [-1.0, 1.0]; sign sets direction."""
        speed = max(-1.0, min(1.0, speed))

        if speed > 0:
            GPIO.output(self.in1, GPIO.HIGH)
            GPIO.output(self.in2, GPIO.LOW)
        elif speed < 0:
            GPIO.output(self.in1, GPIO.LOW)
            GPIO.output(self.in2, GPIO.HIGH)
        else:
            GPIO.output(self.in1, GPIO.LOW)
            GPIO.output(self.in2, GPIO.LOW)

        self.pwm.ChangeDutyCycle(abs(speed) * 100.0)
        self.speed = speed

    def ramp_to(self, target, step_size=RAMP_STEP_SIZE, step_seconds=RAMP_STEP_SECONDS):
        """Smoothly change speed to target in small steps (avoids jerky starts)."""
        target = max(-1.0, min(1.0, target))
        while abs(self.speed - target) > 1e-6:
            delta = target - self.speed
            step = max(-step_size, min(step_size, delta))
            self.set_speed(self.speed + step)
            time.sleep(step_seconds)

    def stop(self):
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

    def shutdown(self):
        self.left.close()
        self.right.close()
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
        robot.shutdown()  # always release the pins and zero the outputs


if __name__ == "__main__":
    main()