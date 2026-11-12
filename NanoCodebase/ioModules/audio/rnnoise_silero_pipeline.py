"""Standalone RNNoise denoising and Silero VAD streaming processor.

This module is intentionally not wired into ``AudioService`` yet. It provides a
small, testable integration point for a future microphone pipeline without
changing the current application behavior.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import soxr
import torch
from pyrnnoise.rnnoise import create as create_rnnoise
from pyrnnoise.rnnoise import destroy as destroy_rnnoise
from pyrnnoise.rnnoise import process_mono_frame
from silero_vad import load_silero_vad


INPUT_SAMPLE_RATE = 48_000
OUTPUT_SAMPLE_RATE = 16_000
RNNOISE_FRAME_SAMPLES = 480
SILERO_FRAME_SAMPLES = 512


class RNNoiseSileroPipeline:
    """Denoise 48 kHz mono PCM and emit Silero speech probabilities.

    RNNoise operates on 480-sample (10 ms) frames at 48 kHz. The cleaned audio
    is stream-resampled to 16 kHz for Whisper and Silero, which requires
    sequential 512-sample windows. Call :meth:`reset` between utterances.
    """

    def __init__(self, speech_threshold: float = 0.5) -> None:
        if not 0.0 < speech_threshold < 1.0:
            raise ValueError("speech_threshold must be between 0 and 1")

        self.speech_threshold = speech_threshold
        self._model = load_silero_vad(onnx=True)
        self._rnnoise_state = None
        self._resampler: soxr.ResampleStream | None = None
        self._vad_buffer = np.empty(0, dtype=np.int16)
        self.reset()

    def reset(self) -> None:
        """Discard buffered audio and start fresh RNNoise and Silero state."""
        self.close()
        self._rnnoise_state = create_rnnoise()
        self._resampler = soxr.ResampleStream(
            INPUT_SAMPLE_RATE,
            OUTPUT_SAMPLE_RATE,
            1,
            dtype="int16",
            quality="HQ",
        )
        self._vad_buffer = np.empty(0, dtype=np.int16)
        self._model.reset_states()

    def process(self, pcm: bytes) -> tuple[np.ndarray, list[float]]:
        """Process one 48 kHz, mono, 16-bit PCM RNNoise frame.

        Returns the cleaned 16 kHz samples and zero or more Silero speech
        probabilities. A probability at or above ``speech_threshold`` is speech.
        """
        samples = np.frombuffer(pcm, dtype=np.int16)
        if samples.size != RNNOISE_FRAME_SAMPLES:
            raise ValueError(
                f"Expected {RNNOISE_FRAME_SAMPLES} int16 samples, got {samples.size}"
            )
        if self._rnnoise_state is None or self._resampler is None:
            raise RuntimeError("Pipeline is closed; call reset() before processing audio")

        denoised, _rnnoise_speech_probability = process_mono_frame(
            self._rnnoise_state, samples
        )
        cleaned = self._resampler.resample_chunk(denoised)
        self._vad_buffer = np.concatenate((self._vad_buffer, cleaned))
        return cleaned, list(self._speech_probabilities())

    def finish(self) -> np.ndarray:
        """Flush and return the final resampler samples for the output WAV."""
        if self._resampler is None:
            return np.empty(0, dtype=np.int16)
        return self._resampler.resample_chunk(
            np.empty(0, dtype=np.int16), last=True
        )

    def is_speech(self, probability: float) -> bool:
        """Return whether a Silero probability meets this pipeline's threshold."""
        return probability >= self.speech_threshold

    def close(self) -> None:
        """Release the native RNNoise state."""
        if self._rnnoise_state is not None:
            destroy_rnnoise(self._rnnoise_state)
            self._rnnoise_state = None
        self._resampler = None

    def _speech_probabilities(self) -> Iterator[float]:
        while self._vad_buffer.size >= SILERO_FRAME_SAMPLES:
            window = self._vad_buffer[:SILERO_FRAME_SAMPLES]
            self._vad_buffer = self._vad_buffer[SILERO_FRAME_SAMPLES:]
            normalized = torch.from_numpy(window.astype(np.float32) / 32768.0)
            yield float(self._model(normalized, OUTPUT_SAMPLE_RATE).item())

    def __enter__(self) -> "RNNoiseSileroPipeline":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
