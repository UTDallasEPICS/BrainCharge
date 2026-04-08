import serial
import time
from cv_pipeline import CVPipeline

# Change SERIAL_PORT to '/dev/ttyUSB0' or '/dev/ttyACM0' for Jetson
SERIAL_PORT = 'COM3'
BAUD_RATE = 115200


def serialCom():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        
        time.sleep(2)

        print("The keyboard strokes go as follows:\n  F for forward\n  B for Backward\n  R for right\n"
            "  L for left\n  SL for strafe left \n  SR for strafe right")

        while True:
            # Get user input
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
        print("Check if the Arduino is plugged in or if the Serial Monitor is still open.")
    except KeyboardInterrupt:
        print("\nScript stopped by keyboard interrupt. Try again.")

if __name__ == "__main__":
    #serialCom()

    pipeline = CVPipeline()
    pipeline.turn_on_camera()
    pipeline.track_movement()
    pipeline.turn_off_camera()