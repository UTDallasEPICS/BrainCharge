# Jetson microphone setup (Adafruit SPH0645LM4H)

Step-by-step guide for new users on a **Jetson Orin Nano** (also works on classic Jetson Nano). You will wire the mic, enable I2S once, run the setup script, prove a WAV has speech, then point BrainCharge at the device.

BrainCharge captures audio with **PyAudio at 16 kHz mono S16** (for VAD + Whisper). The Adafruit I2S mic often prefers **48 kHz / S32** at the hardware. The setup script installs an ALSA plug device (`braincharge_mic`) that converts for you.

| Board | ALSA card (short id) | Header I2S |
|-------|----------------------|------------|
| **Jetson Orin Nano** (primary) | `APE` | `I2S2` |
| Jetson Nano (T210) | `tegrasndt210ref` | `I2S4` |

`scripts/jetson_i2s_mic_setup.sh` auto-detects the card (`APE` preferred when present).

---

## What you need

- Jetson Orin Nano (or classic Nano) with SSH or a local terminal
- Adafruit I2S MEMS mic (SPH0645LM4H breakout)
- This repo checked out on the Jetson under something like `~/NanoCodebase`
- Packages: `alsa-utils` (`arecord`, `amixer`, `alsactl`) — usually already installed on JetPack

---

## 1. Wire the microphone

| Mic pin | Jetson 40-pin header |
|---------|----------------------|
| 3V      | 1 (3.3V)             |
| GND     | 39                   |
| BCLK    | 12                   |
| LRCL    | 35                   |
| DOUT    | 38                   |
| SEL     | leave open, or GND (left channel) |

Power alone is not enough: pinmux (next step) must enable I2S on those pins.

---

## 2. Enable I2S pinmux (once per board)

On the Jetson:

```bash
sudo /opt/nvidia/jetson-io/config-by-hardware.py -n "Adafruit SPH0645LM4H"
sudo reboot
```

After reboot, confirm the card exists:

```bash
arecord -l
```

On Orin you should see a line like:

```text
card 1: APE [NVIDIA Jetson Orin Nano APE], device 0: ...
```

Many `ADMAIF…` devices under `APE` is normal. The setup script uses card **`APE`** (short id), not the long name in brackets.

Optional pin check:

```bash
sudo /opt/nvidia/jetson-io/config-by-pin.py | grep -i i2s
```

You want pins 12 / 35 / 38 showing `i2s2_*` on Orin.

---

## 3. Run the setup script

From the **NanoCodebase** directory on the Jetson:

```bash
cd /path/to/NanoCodebase
chmod +x scripts/jetson_i2s_mic_setup.sh

# Route ALSA muxes, write ~/.asoundrc (braincharge_mic), and record a 3s test
./scripts/jetson_i2s_mic_setup.sh --verify
```

**Speak clearly into the mic** during the 3-second capture.

### What the script does

1. Detects `APE` + `I2S2` (Orin) or `tegrasndt210ref` + `I2S4` (classic Nano)
2. Maps capture: `ADMAIF1 Mux` ← I2S, sets frame mode `i2s` on Orin
3. Installs/updates `~/.asoundrc` with plug PCM `braincharge_mic` (16 kHz mono S16)
4. With `--verify`, records `/tmp/braincharge_i2s_test.wav`

### Useful flags

```bash
./scripts/jetson_i2s_mic_setup.sh           # route + asoundrc only
./scripts/jetson_i2s_mic_setup.sh --verify  # also record test WAV
./scripts/jetson_i2s_mic_setup.sh --status  # show card / mux / named PCMs
./scripts/jetson_i2s_mic_setup.sh --help
```

Force Orin if auto-detect is wrong:

```bash
CARD=APE I2S_IF=I2S2 ./scripts/jetson_i2s_mic_setup.sh --verify
```

Classic Nano:

```bash
CARD=tegrasndt210ref I2S_IF=I2S4 ./scripts/jetson_i2s_mic_setup.sh --verify
```

---

## 4. Prove audio was recorded

```bash
ls -l /tmp/braincharge_i2s_test.wav
```

The file should be **thousands of bytes**, not tiny. Then either:

- Copy it to your PC and play it (Audacity / VLC):
  ```bash
  scp user@JETSON_IP:/tmp/braincharge_i2s_test.wav .
  ```
- Or on the Jetson (if you have speakers/headphones):
  ```bash
  aplay /tmp/braincharge_i2s_test.wav
  ```

You should hear your speech (it may be quiet). **Silence here means fix hardware/mux before worrying about `main.py`.**

Raw capture fallback (Orin), if the plug path failed:

```bash
amixer -c 1 cset name='ADMAIF1 Mux' 'I2S2'
amixer -c 1 cset name='I2S2 Mux' 'ADMAIF1'
amixer -c 1 cset name='I2S2 codec frame mode' 'i2s'
arecord -D hw:APE,0 -c 2 -r 48000 -f S32_LE -d 3 /tmp/raw.wav
```

Use single quotes around control names (spaces). Prefer card number `1` if `amixer -c APE` misbehaves.

---

## 5. Point BrainCharge at the mic

List PortAudio devices:

```bash
cd /path/to/NanoCodebase
uv run python scripts/list_audio_devices.py
```

Set `audio.input_device` in **`userConfig.json`** (created next to `main.py` on first run; not overwritten by defaults):

```json
"audio": {
  "input_device": "APE"
}
```

Good options:

| Value | When to use |
|-------|-------------|
| `"APE"` | Orin default (linux defaultConfigs); matches names containing APE |
| `"braincharge_mic"` | After setup script, if PortAudio lists that plug |
| `2` (example index) | If several devices match `"APE"` and levels stay at `-100` dBFS |

On Orin, many APE devices appear — if the app stays at **-100.0 dBFS** while you talk, pick the **numeric index** for the real capture device (usually tied to `ADMAIF1` / `hw:APE,0`) instead of the substring `"APE"`.

---

## 6. Run the app and watch levels

```bash
uv run python main.py
```

When listening, you should see a live line like:

```text
 -12.3 dBFS  |  SPEECH                 | 1.2s
```

Talking should push dBFS **well above `-30`**. Flat `-100` means all-zero samples (wrong device or no mic data).

---

## Healthy checklist

- [ ] `arecord -l` shows `APE` (Orin) or `tegrasndt210ref` (classic Nano)
- [ ] Setup script prints `Detected platform=orin card=APE i2s=I2S2` (or nano-t210)
- [ ] `/tmp/braincharge_i2s_test.wav` contains audible speech
- [ ] `list_audio_devices.py` shows a device; app log marks one `<-- selected`
- [ ] VAD dBFS rises when you speak

---

## Troubleshooting

| Symptom | Likely fix |
|---------|------------|
| No known ALSA card / card missing | Re-run jetson-io Adafruit profile + reboot; confirm `arecord -l` |
| Script said no card but `APE [NVIDIA Jetson Orin Nano APE]` exists | Update to latest script (matches short id `card N: APE`, not `[APE]` in brackets) |
| `amixer: Cannot find the given element` | List controls: `amixer -c 1 controls \| grep -iE 'ADMAIF\|I2S2'`; enable overlay if empty; use `amixer -c 1 cset name='…'` |
| WAV is silence | Check wiring; re-run setup; try native `arecord -D hw:APE,0 …` |
| App stuck at `-100.0 dBFS` | Wrong PortAudio device — use index from `list_audio_devices.py` |
| PyAudio cannot open 16 kHz | Re-run setup so `plug:braincharge_mic` exists |
| Mux/settings lost after reboot | Re-run `./scripts/jetson_i2s_mic_setup.sh`; ensure `alsactl store` succeeded |
| Orin still silent after mux | `I2S2 codec frame mode` should be `i2s`; do **not** set master mode to `cbs-cfs` for this mic |

### Manual Orin mux (if you need it without the script)

```bash
amixer -c 1 cset name='ADMAIF1 Mux' 'I2S2'
amixer -c 1 cset name='I2S2 Mux' 'ADMAIF1'
amixer -c 1 cset name='I2S2 codec frame mode' 'i2s'
alsactl store || true
```

---

## Repo pieces (reference)

| Piece | Role |
|-------|------|
| `scripts/jetson_i2s_mic_setup.sh` | ALSA routing + `~/.asoundrc` plug PCM |
| `scripts/list_audio_devices.py` | Lists PortAudio inputs for `input_device` |
| `app/defaultConfigs/linux.json` → `audio.input_device` | Default `"APE"` for Orin |
| `ioModules/audio/service.py` | Opens the configured input at 16 kHz mono S16 |

---

## Related

- Broader Jetson bring-up (packages, Whisper, Vosk): [old/JETSON_SETUP.md](old/JETSON_SETUP.md)
- PC testing without Jetson hardware: [../README.md](../README.md)
