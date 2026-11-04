#!/usr/bin/env python3
"""List PortAudio input (and optionally output) devices.

Run on the Jetson after the Adafruit I2S mic is attached:

    uv run python scripts/list_audio_devices.py

Then set audio.input_device in userConfig.json to the device index or a
unique name substring (linux default is "tegra").
"""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--outputs",
        action="store_true",
        help="Also list output (playback) devices",
    )
    args = parser.parse_args()

    try:
        from pyaudio import PyAudio
    except ImportError:
        print("pyaudio is not installed. On Jetson: sudo apt install portaudio19-dev && uv sync", file=sys.stderr)
        return 1

    pa = PyAudio()
    try:
        print("Input devices:")
        found_input = False
        for index in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(index)
            channels = int(info.get("maxInputChannels", 0))
            if channels <= 0:
                continue
            found_input = True
            rate = float(info.get("defaultSampleRate", 0))
            print(f"  [{index}] {info.get('name')}  (ch={channels}, {rate:.0f} Hz)")
        if not found_input:
            print("  (none)")

        if args.outputs:
            print("\nOutput devices:")
            found_output = False
            for index in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(index)
                channels = int(info.get("maxOutputChannels", 0))
                if channels <= 0:
                    continue
                found_output = True
                rate = float(info.get("defaultSampleRate", 0))
                print(f"  [{index}] {info.get('name')}  (ch={channels}, {rate:.0f} Hz)")
            if not found_output:
                print("  (none)")
    finally:
        pa.terminate()

    print(
        "\nSet audio.input_device in userConfig.json to an index (e.g. 2) "
        "or a name substring (e.g. \"tegra\" or \"braincharge_mic\")."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
