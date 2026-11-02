from pathlib import Path
from ultralytics import YOLO, settings

MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "yolo26n-depth.pt"
DATASET_PATH = Path(__file__).resolve().parent / "face_depth_dataset" / "calibration.yaml"
CALIBRATION_PATH = Path(__file__).resolve().parent / "runs"
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "models" / "yolo26n-depth-calibrated.pt"

settings.update({"runs_dir": str(CALIBRATION_PATH)})

print("Loading pretrained depth model...")

model = YOLO(MODEL_PATH)

print("Starting depth calibration...")

result = model.calibrate(
    data=DATASET_PATH,
    imgsz=768,
    batch=4
)

if result is None:
    print(
        "Calibration was not performed. "
        "Check that at least two images have valid depth labels."
    )
else:
    a, b = result

    print("\nCalibration completed.")
    print(f"Calibration parameter a: {a:.6f}")
    print(f"Calibration parameter b: {b:.6f}")

    model.save(OUTPUT_PATH)

    print(f"\nCalibrated model saved to: {OUTPUT_PATH}")