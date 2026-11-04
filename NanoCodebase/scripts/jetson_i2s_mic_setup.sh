#!/usr/bin/env bash
# Configure ALSA for the Adafruit SPH0645LM4H I2S MEMS mic on Jetson Nano.
#
# Prerequisites:
#   - jetson-io already enabled "Adafruit SPH0645LM4H" (pinmux) and rebooted
#   - Mic wired: 3V->pin1, GND->39, BCLK->12, LRCL->35, DOUT->38
#
# Usage (on the Jetson):
#   chmod +x scripts/jetson_i2s_mic_setup.sh
#   ./scripts/jetson_i2s_mic_setup.sh           # route + install plug pcm
#   ./scripts/jetson_i2s_mic_setup.sh --verify  # record 3s test WAV
#   ./scripts/jetson_i2s_mic_setup.sh --status  # show card / mux state
set -euo pipefail

CARD="${CARD:-tegrasndt210ref}"
ASOUND_MARKER="# BrainCharge Adafruit I2S mic"
ASOUND_FILE="${HOME}/.asoundrc"
VERIFY=0
STATUS=0

for arg in "$@"; do
  case "$arg" in
    --verify) VERIFY=1 ;;
    --status) STATUS=1 ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing command: $1 (try: sudo apt install alsa-utils)" >&2
    exit 1
  fi
}

print_status() {
  echo "=== arecord -l ==="
  arecord -l || true
  echo
  echo "=== amixer mux (card=${CARD}) ==="
  amixer -c "$CARD" sget "ADMAIF1 Mux" 2>/dev/null || echo "(ADMAIF1 Mux unavailable)"
  amixer -c "$CARD" sget "I2S4 Mux" 2>/dev/null || echo "(I2S4 Mux unavailable)"
  echo
  echo "=== named PCMs (braincharge / tegra / default) ==="
  arecord -L 2>/dev/null | grep -Ei 'braincharge|tegra|^default' || true
}

install_asoundrc() {
  local fragment
  fragment=$(cat <<EOF
${ASOUND_MARKER}
# Converts Jetson I2S capture (often 48 kHz / S32 / stereo) to 16 kHz mono S16
# for BrainCharge VAD + Whisper (PyAudio).
pcm.braincharge_mic {
    type plug
    slave {
        pcm "hw:${CARD},0"
        channels 1
        rate 16000
        format S16_LE
    }
}

ctl.braincharge_mic {
    type hw
    card ${CARD}
}
EOF
)

  mkdir -p "$(dirname "$ASOUND_FILE")"
  if [[ -f "$ASOUND_FILE" ]] && grep -qF "$ASOUND_MARKER" "$ASOUND_FILE"; then
    # Replace previous BrainCharge block (from marker through ctl.braincharge_mic closing brace)
    local tmp
    tmp="$(mktemp)"
    awk -v marker="$ASOUND_MARKER" '
      $0 == marker {skip=1}
      skip && /^ctl\.braincharge_mic/ {in_ctl=1}
      skip && in_ctl && /^}/ {skip=0; in_ctl=0; next}
      skip {next}
      {print}
    ' "$ASOUND_FILE" > "$tmp"
    printf '%s\n' "$fragment" >> "$tmp"
    mv "$tmp" "$ASOUND_FILE"
    echo "Updated BrainCharge block in ${ASOUND_FILE}"
  else
    {
      echo
      printf '%s\n' "$fragment"
    } >> "$ASOUND_FILE"
    echo "Appended BrainCharge plug PCM to ${ASOUND_FILE}"
  fi
}

route_i2s() {
  echo "Initializing ALSA card: ${CARD}"
  # alsactl init can return non-zero on some L4T builds even when usable
  alsactl init "$CARD" || true

  echo "Mapping ADMAIF1 <- I2S4"
  amixer -c "$CARD" cset name="ADMAIF1 Mux" "I2S4" >/dev/null

  # Optional soft volume path — ignore failures on boards without MVC widgets
  if amixer -c "$CARD" cset name="MVC1 Mux" "I2S4" >/dev/null 2>&1; then
    amixer -c "$CARD" cset name="ADMAIF1 Mux" "MVC1" >/dev/null 2>&1 || true
    amixer -c "$CARD" cset name="MVC1 Vol" 13500 >/dev/null 2>&1 || true
    amixer -c "$CARD" cset name="MVC1 Channels" 0 >/dev/null 2>&1 || true
    echo "MVC volume path enabled (boosted)"
  fi

  amixer -c "$CARD" cset name="I2S4 codec bit format" 32 >/dev/null 2>&1 || true

  if alsactl store >/dev/null 2>&1; then
    echo "Stored ALSA state (alsactl store)"
  else
    echo "Warning: alsactl store failed; re-run this script after reboot if capture breaks."
  fi
}

verify_capture() {
  local out="/tmp/braincharge_i2s_test.wav"
  echo "Recording 3s via plug:braincharge_mic -> ${out}"
  if arecord -D plug:braincharge_mic -d 3 -f S16_LE -r 16000 -c 1 "$out"; then
    echo "OK: wrote ${out} ($(wc -c < "$out") bytes)"
    echo "Copy/play this file to confirm speech is present (mic must be attached)."
  else
    echo "plug:braincharge_mic failed; trying native hw:${CARD},0 at 48 kHz S32 stereo"
    arecord -D "hw:${CARD},0" -d 3 -f S32_LE -r 48000 -c 2 "$out"
    echo "OK: wrote native capture ${out} ($(wc -c < "$out") bytes)"
    echo "If this has audio but plug failed, check ~/.asoundrc and arecord -L."
  fi
}

require_cmd arecord
require_cmd amixer
require_cmd alsactl

if [[ "$STATUS" -eq 1 ]]; then
  print_status
  exit 0
fi

if ! arecord -l 2>/dev/null | grep -q "$CARD"; then
  echo "ALSA card '${CARD}' not found. Is jetson-io configured for Adafruit SPH0645LM4H?" >&2
  arecord -l || true
  exit 1
fi

route_i2s
install_asoundrc
echo
print_status

if [[ "$VERIFY" -eq 1 ]]; then
  echo
  verify_capture
fi

cat <<EOF

Next steps:
  1. Attach the mic if you have not already (pinmux alone is not enough).
  2. uv run python scripts/list_audio_devices.py
  3. Set audio.input_device in userConfig.json to "tegra", "braincharge_mic", or the index.
  4. uv run python main.py  — watch VAD dBFS while speaking.

Docs: docs/JETSON_I2S_MIC.md
EOF
