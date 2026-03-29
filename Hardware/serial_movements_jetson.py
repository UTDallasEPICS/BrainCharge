import serial
import time
import sys

# --- CONFIGURATION ---
# For Jetson/Linux: '/dev/ttyACM0' or '/dev/ttyUSB0'
# For Windows: 'COM3', 'COM4', etc.      '/dev/ttyACM0' 
SERIAL_PORT = 'COM3'
BAUD_RATE = 115200

def led_controller():
    try:
        # Initialize Serial Connection
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        
        # Arduinos often reset when the serial port opens. 
        # We wait 2 seconds for the bootloader to finish.
        print(f"Initializing connection on {SERIAL_PORT}...")
        time.sleep(2)
        print("Connected! Commands: '1' for ON, '0' for OFF, 'q' to QUIT")

        while True:
            # Get user input
            val = input("Enter Command: ").strip().lower()

            if val == '1':
                ser.write(b"on\n")
                print(">> Sent 'on' command")
            elif val == '0':
                ser.write(b"off\n")
                print(">> Sent 'off' command")
            elif val == 'q':
                print("Closing connection...")
                break
            else:
                print("Invalid input. Use 1, 0, or q.")

            # Read back the Arduino's confirmation
            # We give it a tiny moment to process and reply
            time.sleep(0.1)
            if ser.in_waiting > 0:
                response = ser.readline().decode('utf-8').strip()
                print(f"Arduino says: {response}")

        ser.close()

    except serial.SerialException as e:
        print(f"\n[ERROR] Could not connect to {SERIAL_PORT}.")
        print("Check if the Arduino is plugged in or if the Serial Monitor is still open.")
    except KeyboardInterrupt:
        print("\nScript stopped by user.")

if __name__ == "__main__":
    led_controller()