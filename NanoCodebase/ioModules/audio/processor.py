"""Streaming noise suppression and acoustic echo cancellation.

Applied to 16 kHz mono int16 PCM. Echo cancellation uses an NLMS adaptive
filter with the TTS playback signal as the far-end reference. Noise
suppression uses a high-pass filter plus overlap-add Wiener gain.
"""
from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Any

import numpy as np

PROCESS_SAMPLE_RATE = 16000


def int16_to_float(pcm: bytes) -> np.ndarray:
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


def float_to_int16(samples: np.ndarray) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    return (clipped * 32767.0).astype(np.int16).tobytes()


def resample_linear(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate or samples.size == 0:
        return samples.astype(np.float32, copy=False)

    n_out = int(round(samples.size * target_rate / source_rate))
    if n_out <= 0:
        return np.zeros(0, dtype=np.float32)

    x_old = np.linspace(0.0, 1.0, num=samples.size, endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    return np.interp(x_new, x_old, samples).astype(np.float32)


class AudioEnhancer:
    """Near-end processor: optional AEC, then noise suppression."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        self.noise_suppression = bool(cfg.get("noise_suppression", True))
        self.echo_cancellation = bool(cfg.get("echo_cancellation", True))
        self.enabled = bool(cfg.get("enabled", True)) and (
            self.noise_suppression or self.echo_cancellation
        )

        self._ns_strength = float(cfg.get("noise_reduction_strength", 0.8))
        self._gain_floor = float(cfg.get("gain_floor", 0.08))
        self._filter_length = max(64, int(cfg.get("aec_filter_length", 512)))
        self._nlms_mu = float(cfg.get("aec_step_size", 0.25))

        self._hp_x1 = 0.0
        self._hp_y1 = 0.0
        self._hp_r = 0.995

        self._fft_size = 512
        self._hop = 256
        self._window = np.hanning(self._fft_size).astype(np.float32)
        self._ns_input_tail = np.zeros(self._fft_size - self._hop, dtype=np.float32)
        self._ns_output_overlap = np.zeros(self._fft_size - self._hop, dtype=np.float32)
        self._noise_psd = np.full(self._fft_size // 2 + 1, 1e-6, dtype=np.float32)
        self._noise_frames = 0

        self._w = np.zeros(self._filter_length, dtype=np.float32)
        # 2x delay line so a far-end vector is always a contiguous slice
        self._x = np.zeros(self._filter_length * 2, dtype=np.float32)
        self._x_pos = self._filter_length

        self._farend: deque[float] = deque()
        self._farend_lock = Lock()

    def reset(self) -> None:
        self._hp_x1 = 0.0
        self._hp_y1 = 0.0
        self._ns_input_tail[:] = 0.0
        self._ns_output_overlap[:] = 0.0
        self._noise_psd[:] = 1e-6
        self._noise_frames = 0
        self._w[:] = 0.0
        self._x[:] = 0.0
        self._x_pos = self._filter_length
        with self._farend_lock:
            self._farend.clear()

    def feed_farend_int16(self, pcm: bytes, sample_rate: int) -> None:
        """Queue TTS samples as the AEC far-end reference, resampled to 16 kHz."""
        if not self.enabled or not self.echo_cancellation or not pcm:
            return

        samples = int16_to_float(pcm)
        resampled = resample_linear(samples, sample_rate, PROCESS_SAMPLE_RATE)
        with self._farend_lock:
            self._farend.extend(float(s) for s in resampled)
            overflow = len(self._farend) - PROCESS_SAMPLE_RATE
            if overflow > 0:
                for _ in range(overflow):
                    self._farend.popleft()

    def process_nearend(self, pcm: bytes, apply_aec: bool = False) -> bytes:
        if not self.enabled or not pcm:
            return pcm

        samples = int16_to_float(pcm)
        samples = self._highpass(samples)

        if apply_aec and self.echo_cancellation:
            farend = self._consume_farend(samples.size)
            samples = self._nlms_aec(samples, farend)

        if self.noise_suppression:
            samples = self._wiener_ns(samples)

        return float_to_int16(samples)

    def _consume_farend(self, n: int) -> np.ndarray:
        with self._farend_lock:
            available = min(n, len(self._farend))
            if available:
                head = np.fromiter(
                    (self._farend.popleft() for _ in range(available)),
                    dtype=np.float32,
                    count=available,
                )
            else:
                head = np.zeros(0, dtype=np.float32)

        if available == n:
            return head
        padded = np.zeros(n, dtype=np.float32)
        if available:
            padded[:available] = head
        return padded

    def _highpass(self, samples: np.ndarray) -> np.ndarray:
        x1 = self._hp_x1
        y1 = self._hp_y1
        r = self._hp_r
        out = np.empty_like(samples)
        for i, x0 in enumerate(samples):
            y0 = x0 - x1 + r * y1
            out[i] = y0
            x1 = x0
            y1 = y0
        self._hp_x1 = x1
        self._hp_y1 = y1
        return out

    def _nlms_aec(self, near: np.ndarray, far: np.ndarray) -> np.ndarray:
        w = self._w
        x = self._x
        pos = self._x_pos
        m = self._filter_length
        mu = self._nlms_mu
        err = np.empty_like(near)
        eps = 1e-6

        for i in range(near.size):
            pos -= 1
            if pos == 0:
                x[m:] = x[:m]
                pos = m
            x[pos] = far[i]
            x_vec = x[pos : pos + m]

            y = float(np.dot(w, x_vec))
            e = near[i] - y
            err[i] = e

            far_power = far[i] * far[i]
            # Adapt only while the speaker is active and the residual looks like echo
            if far_power > 1e-4 and (e * e) < (4.0 * far_power):
                power = float(np.dot(x_vec, x_vec)) + eps
                w += (mu / power) * e * x_vec

        self._x_pos = pos
        np.clip(w, -5.0, 5.0, out=w)
        return err

    def _wiener_ns(self, samples: np.ndarray) -> np.ndarray:
        hop = self._hop
        n_fft = self._fft_size
        overlap = n_fft - hop

        if samples.size == 0:
            return samples

        work = np.concatenate((self._ns_input_tail, samples))
        n_frames = (work.size - n_fft) // hop + 1 if work.size >= n_fft else 0
        if n_frames <= 0:
            if work.size >= overlap:
                self._ns_input_tail = work[-overlap:].copy()
            else:
                self._ns_input_tail = np.pad(work, (overlap - work.size, 0))
            return samples

        out = np.zeros(n_frames * hop + overlap, dtype=np.float32)
        out[:overlap] = self._ns_output_overlap

        strength = self._ns_strength
        gain_floor = self._gain_floor
        oversub = 1.0 + strength

        for frame_i in range(n_frames):
            start = frame_i * hop
            frame = work[start : start + n_fft] * self._window
            spectrum = np.fft.rfft(frame)
            mag2 = (spectrum.real * spectrum.real + spectrum.imag * spectrum.imag).astype(
                np.float32
            )
            energy = float(np.mean(mag2))

            quiet = energy < 2e-4 or self._noise_frames < 8
            if quiet:
                alpha = 0.15 if self._noise_frames < 8 else 0.05
                self._noise_psd = (1.0 - alpha) * self._noise_psd + alpha * mag2
                self._noise_frames += 1

            gain = 1.0 - oversub * (self._noise_psd / (mag2 + 1e-8))
            gain = np.clip(gain, gain_floor, 1.0).astype(np.float32)
            denoised = np.fft.irfft(spectrum * gain, n=n_fft).astype(np.float32)
            out[start : start + n_fft] += denoised * self._window

        produced = n_frames * hop
        kept = work[produced:]
        if kept.size >= overlap:
            self._ns_input_tail = kept[-overlap:].copy()
        else:
            self._ns_input_tail = np.pad(kept, (overlap - kept.size, 0))
        self._ns_output_overlap = out[produced : produced + overlap].copy()

        result = out[:produced]
        # Streaming OLA emits hop-aligned samples; leftover input stays in the tail.
        if result.size >= samples.size:
            return result[: samples.size]
        return np.pad(result, (0, samples.size - result.size))
