import json
import math
import threading

import pygame
import requests

from ollama_client import call_ollama

#dimensions of the display
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 600
BACKGROUND = (0, 0, 0)
ACCENT_COLOR = (0, 220, 255)

EXPRESSIONS = {
    "Neutral":   {"eye_w": 80, "eye_h": 55, "eyebrow_angle": 0,   "mouth": "flat"},
    "Happy":     {"eye_w": 90, "eye_h": 40, "eyebrow_angle": 0,   "mouth": "smile"},
    "Sad":       {"eye_w": 70, "eye_h": 45, "eyebrow_angle": -15, "mouth": "frown"},
    "Surprised": {"eye_w": 60, "eye_h": 90, "eyebrow_angle": 20,  "mouth": "open"},
    "Angry":     {"eye_w": 90, "eye_h": 35, "eyebrow_angle": -25, "mouth": "flat"},
}

KEY_TO_EXPRESSION = {
    pygame.K_1: "Neutral",
    pygame.K_2: "Happy",
    pygame.K_3: "Sad",
    pygame.K_4: "Surprised",
    pygame.K_5: "Angry",
}


def draw_eye(screen, x_center, y_center, width, height, color):
    rect = pygame.Rect(0, 0, width, height)
    rect.center = (x_center, y_center)
    radius = min(width, height) // 2
    pygame.draw.rect(screen, color, rect, border_radius=radius)


def draw_eyebrow(screen, x_center, y_center, angle_degree, eye_height, color):
    length = 70
    thickness = 5
    gap = 15
    y_offset = (eye_height / 2) + gap

    angle = math.radians(angle_degree)
    half_length = length // 2
    x = half_length * math.cos(angle)
    y = half_length * math.sin(angle)

    eyebrow_y_center = y_center - y_offset
    start = (x_center - x, eyebrow_y_center - y)
    stop = (x_center + x, eyebrow_y_center + y)
    pygame.draw.line(screen, color, start, stop, thickness)


def draw_mouth(screen, x_center, y_center, mouth_type, color):
    if mouth_type == "flat":
        half = 60
        start = (x_center - half, y_center)
        stop = (x_center + half, y_center)
        pygame.draw.line(screen, color, start, stop, 5)
    elif mouth_type == "smile":
        radius = 200
        x = x_center - radius
        y = y_center - radius
        box = (x, y, radius * 2, radius * 2)
        start_arc = math.radians(180)
        stop_arc = math.radians(0)
        pygame.draw.arc(screen, ACCENT_COLOR, box, start_arc, stop_arc, 10)
    elif mouth_type == "open":
        width, height = 70, 100
        rect = pygame.Rect(0, 0, width, height)
        rect.center = (x_center, y_center)
        pygame.draw.ellipse(screen, color, rect)
    elif mouth_type == "frown":
        radius = 200
        x = x_center - radius
        y = y_center - radius
        box = (x, y, radius * 2, radius * 2)
        start_arc = math.radians(0)
        stop_arc = math.radians(180)
        pygame.draw.arc(screen, ACCENT_COLOR, box, start_arc, stop_arc, 10)


def draw_face(screen, expression, x_center, y_center):
    emo = EXPRESSIONS[expression]
    x_eye_offset = 150
    y_eye_offset = -150

    x_left_eye = x_center - x_eye_offset
    x_right_eye = x_center + x_eye_offset
    y_eye = y_center + y_eye_offset

    draw_eye(screen, x_left_eye, y_eye, emo["eye_w"], emo["eye_h"], ACCENT_COLOR)
    draw_eye(screen, x_right_eye, y_eye, emo["eye_w"], emo["eye_h"], ACCENT_COLOR)
    draw_eyebrow(screen, x_left_eye, y_eye, emo["eyebrow_angle"], emo["eye_h"], ACCENT_COLOR)
    draw_eyebrow(screen, x_right_eye, y_eye, -emo["eyebrow_angle"], emo["eye_h"], ACCENT_COLOR)
    draw_mouth(screen, x_center, y_center + 100, emo["mouth"], ACCENT_COLOR)


class RobotFaceDisplay:
    """
    Runs the pygame face window in its own thread.

    main.py's conversation loop blocks for long stretches at a time --
    recording while the user talks, waiting on Ollama, playing TTS. A window
    that isn't pumping its event queue during that gets marked "Not
    Responding" by Windows and never redraws. Running the window and its
    event loop in a dedicated thread keeps it alive regardless of what the
    conversation loop is doing; the conversation loop only ever touches
    `set_expression`, never pygame itself.

    `_expression` is read in one thread and written in another with no lock:
    CPython's GIL makes a single attribute assignment atomic, so this is
    safe as long as it stays a plain reference swap, never a
    read-modify-write.
    """

    def __init__(self):
        self._expression = "Neutral"
        self._running = False
        self._thread = None

    def set_expression(self, expression):
        self._expression = expression if expression in EXPRESSIONS else "Neutral"

    def start(self):
        if self._thread is not None:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _run(self):
        pygame.init()
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("BrainCharge")
        clock = pygame.time.Clock()

        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self._running = False
                    elif event.key in KEY_TO_EXPRESSION:
                        self._expression = KEY_TO_EXPRESSION[event.key]

            screen.fill(BACKGROUND)
            draw_face(screen, self._expression, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
            pygame.display.flip()
            clock.tick(60)

        pygame.quit()


def classify_reply_expression(reply_text):
    """
    Classify the tone of the assistant's own reply into one of the five face
    expressions -- the display reflects what the robot is saying, not what
    it detects on the user's face. Returns "Neutral" on any failure.
    """
    labels = list(EXPRESSIONS.keys())
    prompt = (
        "A gentle, compassionate companion robot is about to say the statement below out loud "
        "to the person it's talking with. Pick the facial expression it should show while saying it. "
        "Most ordinary conversation -- greetings, small talk, plain answers -- should be Neutral or "
        "Happy. Only choose Sad if the statement is specifically offering comfort or sympathy for "
        "something difficult the user is going through -- not just because the topic is calm or plain. "
        f"Choose exactly one label from this list: {labels}\n\n"
        'Respond ONLY with valid JSON in this exact format: {"expression": "<one label from the list>"}\n\n'
        f"Statement: {reply_text}"
    )
    try:
        result_text = call_ollama(prompt, model="gemma3:1b", json_mode=True, timeout=30)
        expression = json.loads(result_text).get("expression")
        if expression in EXPRESSIONS:
            return expression
    except requests.exceptions.Timeout:
        print("Expression classification timed out")
    except Exception as e:
        print(f"Error classifying reply expression: {e}")
    return "Neutral"


if __name__ == "__main__":
    # Manual test -- keys 1-5 switch expressions directly, same as the
    # original standalone script. Esc or closing the window exits.
    display = RobotFaceDisplay()
    display.start()
    display._thread.join()
