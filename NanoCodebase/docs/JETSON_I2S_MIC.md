# Jetson — Adafruit I2S MEMS mic (SPH0645LM4H)

BrainCharge captures audio with **PyAudio at 16 kHz mono S16**, then runs Whisper. The Adafruit I2S mic on Jetson often prefers **48 kHz / S32** at the hardware PCM. This doc bridges that gap.

| Board | ALSA card | Header I2S |
|-------|-----------|------------|
| **Jetson Orin Nano** (primary) | `APE` | `I2S2` |
| Jetson Nano (T210) | `tegrasndt210ref` | `I2S4` |

`scripts/jetson_i2s_mic_setup.sh` auto-detects the card (`APE` preferred when both appear) and routes the correct mux.

## Hardware

| Mic pin | Jetson 40-pin |
|---------|----------------|
| 3V      | 1 (3.3V)       |
| GND     | 39             |
| BCLK    | 12             |
| LRCL    | 35             |
| DOUT    | 38             |
| SEL     | open / GND (left) |

Enable pinmux once (already done on your board if I2S was configured):

```bash
sudo /opt/nvidia/jetson-io/config-by-hardware.py -n "Adafruit SPH0645LM4H"
sudo reboot
```

Pinmux without the breakout attached does **not** produce usable audio.

## Software in this repo

| Piece | Role |
|-------|------|
| `app/defaultConfigs/linux.json` → `audio.input_device` | Default `"tegra"`; on Orin prefer `"APE"` or `"braincharge_mic"` |
| `ioModules/audio/service.py` | Resolves `input_device` (index or name substring) and opens that PortAudio device |
| `scripts/jetson_i2s_mic_setup.sh` | ALSA routing + `~/.asoundrc` plug PCM `braincharge_mic` (16 kHz S16 mono) |
| `scripts/list_audio_devices.py` | Lists PortAudio input indices after the mic is live |

`userConfig.json` is created from the linux default on first run. On Orin Nano, set:

```json
"audio": {
  "input_device": "APE"
}
```

Or `"braincharge_mic"` once the ALSA plug profile is installed and PortAudio lists it. Use a numeric index (from `list_audio_devices.py`) if name matching is ambiguous.

## After the mic is attached (SSH is fine)

```bash
cd /path/to/NanoCodebase
chmod +x scripts/jetson_i2s_mic_setup.sh
./scripts/jetson_i2s_mic_setup.sh --verify

uv run python scripts/list_audio_devices.py
# set audio.input_device if needed, then:
uv run python main.py
```

Force a board if auto-detect is wrong:

```bash
CARD=APE I2S_IF=I2S2 ./scripts/jetson_i2s_mic_setup.sh --verify
# classic Nano:
CARD=tegrasndt210ref I2S_IF=I2S4 ./scripts/jetson_i2s_mic_setup.sh --verify
```

`--verify` writes `/tmp/braincharge_i2s_test.wav`. Copy it off the Jetson or check that the file is non-silent; hearing `aplay` live is optional.

### Expected healthy signs

- `arecord -l` shows `APE` (Orin) or `tegrasndt210ref` (classic Nano)
- Verify WAV is much larger than a few KB and contains speech when inspected
- App log lists an input device marked `<-- selected`
- VAD dBFS rises well above `-30` while you talk

## Troubleshooting

| Symptom | Likely fix |
|---------|------------|
| Card missing | Re-run jetson-io Adafruit profile + reboot |
| WAV is silence | Confirm wiring; re-run setup script; try native `arecord -D hw:APE,0 -c 2 -r 48000 -f S32_LE` (Orin) or `hw:tegrasndt210ref,0` (Nano) |
| PyAudio cannot open 16 kHz | Run `jetson_i2s_mic_setup.sh` so `plug:braincharge_mic` exists; point `input_device` at that PCM if listed |
| Wrong device selected | `list_audio_devices.py` then set `input_device` to `"APE"`, `"braincharge_mic"`, or the exact index |
| Settings lost after reboot | Re-run setup script; ensure `alsactl store` succeeded |
| Orin still silent after mux | Confirm `I2S2 codec frame mode` is `i2s`; do **not** set master mode to `cbs-cfs` for this mic |

## Related

- Broader Jetson bring-up (packages, Whisper): [old/JETSON_SETUP.md](old/JETSON_SETUP.md)
