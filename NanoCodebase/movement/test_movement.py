#!/usr/bin/env python3
"""
Tests for movement.py (move_toward_user and the drive functions).

HOW TO RUN (put this file in the same folder as movement.py):
    python3 test_movement.py -v

No hardware needed. A fake Jetson.GPIO is installed BEFORE movement.py is
imported, so nothing touches real pins (safe to run on the Jetson, in WSL,
or anywhere else) and time.sleep is patched out so tests finish instantly.

User position vectors are (x, y, z), with the "perfect" base at (0, 100, 0):
    x: horizontal offset  (x < 0 -> turn left, x > 0 -> turn right)
    y: distance           (95..105 is the acceptable band)
    z: vertical offset    (z < 0 -> pan down, z > 0 -> pan up)
"""

import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------ fake GPIO ---
class FakePWM:
    def __init__(self, pin, freq):
        self.pin = pin
        self.freq = freq
        self.duty = None

    def start(self, duty):
        self.duty = duty

    def ChangeDutyCycle(self, duty):
        self.duty = duty

    def stop(self):
        pass


fake_gpio = types.ModuleType("Jetson.GPIO")
fake_gpio.BOARD = "BOARD"
fake_gpio.OUT = "OUT"
fake_gpio.LOW = 0
fake_gpio.HIGH = 1
fake_gpio.pin_state = {}
fake_gpio.setmode = lambda mode: None
fake_gpio.setwarnings = lambda flag: None
fake_gpio.setup = lambda pin, mode, initial=0: fake_gpio.pin_state.__setitem__(pin, initial)
fake_gpio.output = lambda pin, value: fake_gpio.pin_state.__setitem__(pin, value)
fake_gpio.cleanup = lambda: None
fake_gpio.PWM = FakePWM

fake_jetson = types.ModuleType("Jetson")
fake_jetson.GPIO = fake_gpio
sys.modules["Jetson"] = fake_jetson
sys.modules["Jetson.GPIO"] = fake_gpio

import movement  # noqa: E402  (must come after the fake GPIO is installed)


# --------------------------------------------------------------- helpers ---
# Reference ranges written out literally (not read from movement.py), so the
# tests also catch a wrong constant in the code.
REF_X_TOL = 0.02
REF_Y_MIN, REF_Y_MAX = 95, 105
REF_Z_TOL = 0.02

ACTION_FUNCS = ["turn_left", "turn_right", "go_forward", "stop",
                "pan_up", "pan_down"]


def run_vector(x, y, z):
    """
    Call move_toward_user once with the action functions mocked out.
    Returns (drive_action, pan_action, in_position) where
      drive_action in {"turn_left", "turn_right", "forward", "backward", "stop"}
      pan_action   in {"pan_up", "pan_down", None}
    """
    with mock.patch.multiple(movement, **{n: mock.DEFAULT for n in ACTION_FUNCS}) as m:
        in_position = movement.move_toward_user(x, y, z)

    drive_calls = []
    if m["turn_left"].called:
        drive_calls.append("turn_left")
    if m["turn_right"].called:
        drive_calls.append("turn_right")
    if m["go_forward"].called:
        speed = m["go_forward"].call_args[0][0]
        drive_calls.append("forward" if speed > 0 else "backward")
    if m["stop"].called:
        drive_calls.append("stop")

    assert len(drive_calls) == 1, f"expected exactly one drive action, got {drive_calls}"

    pan = None
    if m["pan_up"].called and m["pan_down"].called:
        raise AssertionError("both pan_up and pan_down were called")
    if m["pan_up"].called:
        pan = "pan_up"
    elif m["pan_down"].called:
        pan = "pan_down"

    return drive_calls[0], pan, in_position


def reference_drive(x, y):
    """Independent model of what the drive action should be."""
    if abs(x) > REF_X_TOL:
        return "turn_left" if x < 0 else "turn_right"
    if y > REF_Y_MAX:
        return "forward"
    if y < REF_Y_MIN:
        return "backward"
    return "stop"


def reference_pan(z):
    if abs(z) > REF_Z_TOL:
        return "pan_down" if z < 0 else "pan_up"
    return None


def lerp_path(waypoints, ticks_per_segment=10):
    """Turn a list of (x, y, z) waypoints into a smooth stream of vectors."""
    for (x0, y0, z0), (x1, y1, z1) in zip(waypoints, waypoints[1:]):
        for i in range(ticks_per_segment):
            t = i / ticks_per_segment
            yield (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, z0 + (z1 - z0) * t)
    yield waypoints[-1]


def reset_robot():
    movement.left.set_speed(0.0)
    movement.right.set_speed(0.0)


def setUpModule():
    # Patch time.sleep (ramps and settling delays) so tests run instantly.
    patcher = mock.patch.object(movement.time, "sleep", lambda s: None)
    patcher.start()
    unittestcase_patchers.append(patcher)


def tearDownModule():
    for p in unittestcase_patchers:
        p.stop()


unittestcase_patchers = []


# ----------------------------------------------- scripted user movements ---
# Each step: (x, y, z, expected_drive, expected_pan, expected_in_position)
SCENARIOS = {
    "holding the base position, small jitter inside tolerance": [
        (0, 100, 0, "stop", None, True),
        (0.01, 102, 0.01, "stop", None, True),
        (-0.02, 98, -0.02, "stop", None, True),
        (0.02, 105, 0.02, "stop", None, True),      # exactly on the edges
        (0, 95, 0, "stop", None, True),
        (-0.02, 95, 0.02, "stop", None, True),
    ],
    "just outside each tolerance edge": [
        (0.021, 100, 0, "turn_right", None, False),
        (-0.021, 100, 0, "turn_left", None, False),
        (0, 105.1, 0, "forward", None, False),
        (0, 94.9, 0, "backward", None, False),
        (0, 100, 0.021, "stop", "pan_up", True),    # tilt doesn't affect in_position
        (0, 100, -0.021, "stop", "pan_down", True),
    ],
    "user walks away, robot follows, then user is in band": [
        (0, 160, 0, "forward", None, False),
        (0, 140, 0, "forward", None, False),
        (0, 120, 0, "forward", None, False),
        (0, 106, 0, "forward", None, False),
        (0, 105, 0, "stop", None, True),
        (0, 100, 0, "stop", None, True),
    ],
    "user steps toward the robot (too close)": [
        (0, 60, 0, "backward", None, False),
        (0, 80, 0, "backward", None, False),
        (0, 94, 0, "backward", None, False),
        (0, 95, 0, "stop", None, True),
    ],
    "user sidesteps right, then left, then re-centres": [
        (0.20, 100, 0, "turn_right", None, False),
        (0.10, 100, 0, "turn_right", None, False),
        (0.03, 100, 0, "turn_right", None, False),
        (0.02, 100, 0, "stop", None, True),
        (-0.10, 100, 0, "turn_left", None, False),
        (-0.03, 100, 0, "turn_left", None, False),
        (0.00, 100, 0, "stop", None, True),
    ],
    "turning takes priority over distance": [
        (0.20, 160, 0, "turn_right", None, False),
        (-0.20, 60, 0, "turn_left", None, False),
        (0.05, 200, 0, "turn_right", None, False),
        (0.01, 200, 0, "forward", None, False),     # aligned now, so it drives
    ],
    "user looks up and down (pan is independent of the wheels)": [
        (0, 100, 0.10, "stop", "pan_up", True),
        (0, 100, -0.10, "stop", "pan_down", True),
        (0, 150, 0.10, "forward", "pan_up", False),
        (0.2, 100, -0.10, "turn_right", "pan_down", False),
        (0, 100, 0.00, "stop", None, True),
    ],
}


class TestScriptedMovements(unittest.TestCase):
    def test_scenarios(self):
        for name, steps in SCENARIOS.items():
            with self.subTest(scenario=name):
                for i, (x, y, z, drive, pan, in_pos) in enumerate(steps):
                    with self.subTest(step=i, vector=(x, y, z)):
                        self.assertEqual(run_vector(x, y, z), (drive, pan, in_pos))


class TestPropertyGrid(unittest.TestCase):
    """Check every vector on a grid against the independent reference model."""

    def test_grid(self):
        xs = [-0.5, -0.1, -0.0201, -0.02, -0.01, 0, 0.01, 0.02, 0.0201, 0.1, 0.5]
        ys = [0, 60, 94.9, 95, 100, 105, 105.1, 150, 300]
        zs = [-0.5, -0.0201, -0.02, 0, 0.02, 0.0201, 0.5]
        for x in xs:
            for y in ys:
                for z in zs:
                    with self.subTest(vector=(x, y, z)):
                        drive, pan, in_pos = run_vector(x, y, z)
                        self.assertEqual(drive, reference_drive(x, y))
                        self.assertEqual(pan, reference_pan(z))
                        self.assertEqual(in_pos, drive == "stop")

    def test_continuous_user_path(self):
        """User walks a path away from and back to the base position."""
        path = [
            (0, 100, 0),        # base
            (0.3, 100, 0.15),   # steps right and looks up
            (0.3, 150, 0.15),   # then walks away
            (-0.2, 150, -0.1),  # swings left, looks down
            (0, 100, 0),        # returns to base
        ]
        last = None
        for x, y, z in lerp_path(path):
            with self.subTest(vector=(round(x, 3), round(y, 1), round(z, 3))):
                drive, pan, in_pos = run_vector(x, y, z)
                self.assertEqual(drive, reference_drive(x, y))
                self.assertEqual(pan, reference_pan(z))
                last = (drive, pan, in_pos)
        self.assertEqual(last, ("stop", None, True))


# ---------------------------------------- real motor outputs (not mocked) ---
class TestMotorOutputs(unittest.TestCase):
    def setUp(self):
        reset_robot()
        self.dir_left = movement.MOTORS["A"]["dir_pin"]
        self.dir_right = movement.MOTORS["B"]["dir_pin"]

    def test_in_band_leaves_motors_stopped(self):
        movement.move_toward_user(0, 100, 0)
        self.assertEqual((movement.left.speed, movement.right.speed), (0.0, 0.0))

    def test_forward_drives_both_sides_forward(self):
        movement.move_toward_user(0, 150, 0)
        self.assertAlmostEqual(movement.left.speed, movement.FORWARD_SPEED)
        self.assertAlmostEqual(movement.right.speed, movement.FORWARD_SPEED)
        self.assertAlmostEqual(movement.left.pwm.duty, movement.FORWARD_SPEED * 100)
        self.assertEqual(fake_gpio.pin_state[self.dir_left], fake_gpio.LOW)
        self.assertEqual(fake_gpio.pin_state[self.dir_right], fake_gpio.LOW)

    def test_backward_uses_inverted_duty_and_high_direction_pin(self):
        movement.move_toward_user(0, 60, 0)
        self.assertAlmostEqual(movement.left.speed, -movement.FORWARD_SPEED)
        self.assertAlmostEqual(movement.right.speed, -movement.FORWARD_SPEED)
        self.assertAlmostEqual(movement.left.pwm.duty, 100 - movement.FORWARD_SPEED * 100)
        self.assertEqual(fake_gpio.pin_state[self.dir_left], fake_gpio.HIGH)
        self.assertEqual(fake_gpio.pin_state[self.dir_right], fake_gpio.HIGH)

    def test_turns_drive_sides_in_opposite_directions(self):
        for x in (0.3, -0.3):
            with self.subTest(x=x):
                reset_robot()
                movement.move_toward_user(x, 100, 0)
                self.assertAlmostEqual(movement.left.speed, -movement.right.speed)
                self.assertAlmostEqual(abs(movement.left.speed), movement.TURN_SPEED)

    def test_stops_after_motion_when_user_returns_to_band(self):
        movement.move_toward_user(0, 150, 0)
        movement.move_toward_user(0, 100, 0)
        self.assertEqual((movement.left.speed, movement.right.speed), (0.0, 0.0))

    def test_ramp_reaches_target_in_small_steps(self):
        speeds = []
        real_set = movement.left.set_speed

        def spy(speed):
            speeds.append(speed)
            real_set(speed)

        with mock.patch.object(movement.left, "set_speed", spy):
            movement.ramp_drive(0.5, 0.5)

        self.assertAlmostEqual(movement.left.speed, 0.5)
        self.assertAlmostEqual(movement.right.speed, 0.5)
        previous = 0.0
        for s in speeds:
            self.assertLessEqual(abs(s - previous), movement.RAMP_STEP_SIZE + 1e-9)
            previous = s

    def test_speed_is_clamped(self):
        movement.ramp_drive(5.0, -5.0)
        self.assertAlmostEqual(movement.left.speed, 1.0)
        self.assertAlmostEqual(movement.right.speed, -1.0)

    def test_constants_match_spec(self):
        self.assertEqual(movement.TARGET_Y, 100)
        self.assertEqual(movement.Y_TOLERANCE, 5)
        self.assertEqual(movement.X_TOLERANCE, 0.02)
        self.assertEqual(movement.Z_TOLERANCE, 0.02)


# ------------------------------------------------ physical assumptions -----
class TestBenchAssumptions(unittest.TestCase):
    """
    Encodes an ASSUMPTION about the real robot: motor A (pin 32) is the
    physical LEFT side and positive speed spins that wheel forward. If that's
    true, turning left means the left side goes slower/backward than the right.
    Confirm on the bench, then fix the sign in turn_left/turn_right, or fix
    this test if your wiring is the other way round.
    """

    def setUp(self):
        reset_robot()

    def test_turn_left_makes_right_side_faster_than_left(self):
        movement.turn_left(0.1)
        self.assertGreater(movement.right.speed, movement.left.speed,
                           "turn_left spins the robot clockwise if motor A is the left side")

    def test_turn_right_makes_left_side_faster_than_right(self):
        movement.turn_right(0.1)
        self.assertGreater(movement.left.speed, movement.right.speed,
                           "turn_right spins the robot anticlockwise if motor A is the left side")


# ----------------------------------------------- closed-loop simulation ----
class TestClosedLoop(unittest.TestCase):
    """
    The user stands still at an offset and the simulated robot reacts to
    each command, so we can check the controller actually converges.
    Per call: a turn changes x by 0.01, a drive step changes y by 2, a pan
    step changes z by 0.01 (all smaller than the tolerance band width).
    """

    X_STEP, Y_STEP, Z_STEP = 0.01, 2.0, 0.01

    def simulate(self, x, y, z, user_dy=0.0, max_steps=300):
        history = []
        for step in range(max_steps):
            drive, pan, in_pos = run_vector(x, y, z)
            history.append((drive, pan, in_pos))
            if drive == "turn_left":
                x += self.X_STEP
            elif drive == "turn_right":
                x -= self.X_STEP
            elif drive == "forward":
                y -= self.Y_STEP
            elif drive == "backward":
                y += self.Y_STEP
            if pan == "pan_up":
                z -= self.Z_STEP
            elif pan == "pan_down":
                z += self.Z_STEP
            y += user_dy  # the user may keep moving
            if in_pos and pan is None and user_dy == 0:
                return step, (x, y, z), history
        return None, (x, y, z), history

    def test_converges_from_far_away_and_misaligned(self):
        step, final, _ = self.simulate(0.30, 160, 0.20)
        self.assertIsNotNone(step, "never reached the target band")
        x, y, z = final
        self.assertLessEqual(abs(x), REF_X_TOL)
        self.assertTrue(REF_Y_MIN <= y <= REF_Y_MAX)
        self.assertLessEqual(abs(z), REF_Z_TOL)

    def test_converges_from_too_close(self):
        step, final, history = self.simulate(-0.15, 40, -0.10)
        self.assertIsNotNone(step)
        self.assertNotIn("forward", [h[0] for h in history])  # never overshoots

    def test_no_oscillation_once_in_position(self):
        step, final, history = self.simulate(0.12, 130, 0.05)
        self.assertIsNotNone(step)
        # After the first in-position tick, the robot must hold still.
        x, y, z = final
        for _ in range(20):
            self.assertEqual(run_vector(x, y, z), ("stop", None, True))

    def test_chases_user_walking_away_without_reversing(self):
        # User walks away at 1 cm per tick; the robot closes at 2 cm per tick.
        _, _, history = self.simulate(0, 130, 0, user_dy=1.0, max_steps=80)
        drives = [h[0] for h in history]
        self.assertNotIn("backward", drives)
        self.assertTrue(any(h[2] for h in history), "never caught up with the user")


if __name__ == "__main__":
    unittest.main()