"""Map CV emotion labels to webapp face Expression values.

Used by the orchestrator (when wired) to turn VisionService inference into
WebAppEvents.send_expression(...) names that match reactApp face EXPRESSIONS.
"""

from app.webapp import Expression

# HSEmotion enet_b2_8 label → face Expression (string values must match EXPRESSIONS keys).
CV_TO_EXPRESSION = {
    "Anger": Expression.ANGRY,
    "Contempt": Expression.CONTEMPT,
    "Disgust": Expression.DISGUST,
    "Fear": Expression.FEAR,
    "Happiness": Expression.HAPPY,
    "Neutral": Expression.NEUTRAL,
    "Sadness": Expression.SAD,
    "Surprise": Expression.SURPRISED,
}


def emotion_to_expression(
    emotion: str,
    confidence: float,
    min_confidence: float = 0.55,
) -> Expression | None:
    if confidence < min_confidence:
        return None
    return CV_TO_EXPRESSION.get(emotion)
