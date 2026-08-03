import math
import pygame

pygame.init()

#dimensions of the display
screenWidth = 1024
screenHeight = 600
x_center = screenWidth/2
y_center = screenHeight/2
BACKGROUND = (0, 0, 0)
ACCENT_COLOR = (0, 220, 255)

screen = pygame.display.set_mode((screenWidth, screenHeight))#set window size to fit the display
clock = pygame.time.Clock()

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

    pass

def draw_eyebrow(screen, x_center, y_center, angle_degree, eye_height, color):
    length = 70
    thickness = 5
    gap = 15
    y_offset = (eye_height / 2) + gap

    angle = math.radians(angle_degree)
    half_length = length//2
    x = half_length * math.cos(angle)
    y = half_length * math.sin(angle)

    eyebrow_y_center = y_center - y_offset
    start = (x_center - x, eyebrow_y_center - y)
    stop = (x_center + x, eyebrow_y_center + y)
    pygame.draw.line(screen, color, start, stop, thickness)

    pass

def draw_mouth(screen, x_center, y_center, mouth_type, color):
    if mouth_type == "flat":
        half = 60
        start = (x_center - half, y_center)
        stop = (x_center + half, y_center)
        pygame.draw.line(screen, color, start, stop, 5)
        pass
    elif mouth_type == "smile":
        radius = 200
        x = x_center - radius
        y = y_center - radius
        box = (x, y, radius * 2, radius * 2)
        start_arc = math.radians(180)
        stop_arc = math.radians(0)
        pygame.draw.arc(screen, ACCENT_COLOR, box, start_arc, stop_arc, 10)
        pass
    elif mouth_type == "open":
        width, height = 70, 100
        rect = pygame.Rect(0, 0, width, height)
        rect.center = (x_center, y_center)
        pygame.draw.ellipse(screen, color,rect)
        pass
    elif mouth_type == "frown":
        radius = 200
        x = x_center - radius
        y = y_center - radius
        box = (x, y, radius * 2, radius * 2)
        start_arc = math.radians(0)
        stop_arc = math.radians(180)
        pygame.draw.arc(screen, ACCENT_COLOR, box, start_arc, stop_arc, 10)
        pass

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


curr_emotion = ("Happy")
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key in KEY_TO_EXPRESSION:
                curr_emotion = KEY_TO_EXPRESSION[event.key]

    screen.fill(BACKGROUND)
    draw_face(screen, curr_emotion, screenWidth/2, screenHeight/2 )
    pygame.display.flip()
    clock.tick(60)


pygame.quit()