import serial
import time
import sys

# Change SERIAL_PORT to '/dev/ttyUSB0' or '/dev/ttyACM0' for Jetson
SERIAL_PORT = 'COM3'
BAUD_RATE = 115200

def led_controller():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        
        time.sleep(2)
        print("Connected! Commands: '1' for ON, '0' for OFF, 'q' to QUIT")

        while True:
            # Get user input
            val = input("Enter Command: ").strip().lower()

            if val == 'forward':
                ser.write(b"forward\n")
            elif val == 'backward':
                ser.write(b"backward\n")
            elif val == 'right':
                ser.write(b"right\n")
            elif val == 'left':
                ser.write(b"left\n")
            elif val == 'strafe left':
                ser.write(b"strafe left\n")
            elif val == 'strafe right':
                ser.write(b"strafe right\n")
            else:
                ser.write(b"stop\n")

            # Confirmation from the Arduino
            
            # time.sleep(0.1)
            # if ser.in_waiting > 0:
            #     response = ser.readline().decode('utf-8').strip()
            #     print(f"Arduino says: {response}")

        ser.close()

    except serial.SerialException as e:
        print(f"\n[ERROR] Could not connect to {SERIAL_PORT}.")
        print("Check if the Arduino is plugged in or if the Serial Monitor is still open.")
    except KeyboardInterrupt:
        print("\nScript stopped by user.")

if __name__ == "__main__":
    led_controller()