# CVPipeline – Exposed Methods

## Methods

| Method | Description | Usage Example |
|--------|------------|---------------|
| `turn_on_camera()` | Turns on the camera and warms it up | `cv_pipeline.turn_on_camera()` |
| `turn_off_camera()` | Turns off the camera and releases resources | `cv_pipeline.turn_off_camera()` |
| `camera_on()` | Returns `True` if camera is on | `if cv_pipeline.camera_on(): ...` |
| `camera_off()` | Returns `True` if camera is off | `if cv_pipeline.camera_off(): ...` |
| `track_movement()` | Tracks the first detected person and computes turn/move signals. Displays live feed. Press `q` to stop | `cv_pipeline.track_movement()` |
| `execute()` | Captures a frame, detects face, predicts top 3 emotions, annotates and saves image. Returns a list of emotion/confidence dicts | `emotions = cv_pipeline.execute()` |

## Usage Example

```python
from CVPipeline import CVPipeline

cv_pipeline = CVPipeline()

# Turn on camera
cv_pipeline.turn_on_camera()

# Capture emotions
emotions = cv_pipeline.execute()
print([e["emotion"] for e in emotions])

# Track person for movement commands
cv_pipeline.track_movement()

# Turn off camera
cv_pipeline.turn_off_camera()