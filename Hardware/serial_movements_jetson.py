import serial
import os
import time
from cv_pipeline import CVPipeline

# --- Serial port auto-detection for Jetson ---
# Arduino Uno / Mega (CDC ACM)     → /dev/ttyACM0
# USB-to-serial adapters (CH340 etc) → /dev/ttyUSB0
def _find_serial_port() -> str:
    for port in ["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0", "/dev/ttyUSB1"]:
        if os.path.exists(port):
            return port
    return "/dev/ttyACM0"   # default; will raise if not present

SERIAL_PORT = _find_serial_port()
BAUD_RATE   = 115200


def serialCom():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

        time.sleep(2)   # wait for Arduino reset

        print(f"Connected to Arduino on {SERIAL_PORT}")
        print("Keyboard commands:\n  F  – forward\n  B  – backward\n  R  – right\n"
              "  L  – left\n  SL – strafe left\n  SR – strafe right\n  S  – stop")

        while True:
            val = input("Enter Command: ").strip().lower()

            if val == 'f':
                ser.write(b'f')
            elif val == 'b':
                ser.write(b'b')
            elif val == 'r':
                ser.write(b'r')
            elif val == 'l':
                ser.write(b'l')
            elif val == 'sl':
                ser.write(b't')
            elif val == 'sr':
                ser.write(b'q')
            else:
                ser.write(b's')

    except serial.SerialException as e:
        print(f"\n[ERROR] Could not connect to {SERIAL_PORT}.")
        print("  – Check USB cable is plugged in")
        print("  – Run: ls /dev/tty{USB,ACM}*")
        print("  – Add yourself to dialout group: sudo usermod -aG dialout $USER")
        print(f"  – Details: {e}")
    except KeyboardInterrupt:
        print("\nStopped by keyboard interrupt.")


if __name__ == "__main__":
    # Uncomment to run manual serial control:
    # serialCom()

    wakeWord = ""
    while wakeWord != "companion":
        wakeWord = input("Enter wake word: ").strip().lower()
        if wakeWord == "companion":
            pipeline = CVPipeline()
            pipeline.turn_on_camera()
            pipeline.track_movement()
            pipeline.turn_off_camera()
