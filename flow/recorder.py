"""Mikrofonaufnahme über sounddevice (16 kHz mono, float32)."""

import logging
import threading

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)


class Recorder:
    """Nimmt Mono-Audio auf, bis stop() gerufen wird oder max_seconds erreicht ist.

    on_limit wird (einmalig, aus dem Audio-Thread) gerufen, wenn das Zeitlimit
    erreicht ist – der Controller stoppt die Aufnahme dann regulär.
    """

    def __init__(self, sample_rate=16000, input_device=None, max_seconds=120, on_limit=None):
        self.sample_rate = sample_rate
        self.input_device = input_device
        self.max_frames = int(max_seconds * sample_rate)
        self.on_limit = on_limit
        self._stream = None
        self._chunks = []
        self._frames = 0
        self._limit_fired = False
        self._lock = threading.Lock()

    @property
    def is_recording(self):
        return self._stream is not None

    def start(self):
        with self._lock:
            if self._stream is not None:
                return
            self._chunks = []
            self._frames = 0
            self._limit_fired = False
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                device=self.input_device,
                callback=self._callback,
            )
            self._stream.start()
        log.info("Aufnahme gestartet")

    def _callback(self, indata, frames, time_info, status):
        if status:
            log.warning("Audio-Status: %s", status)
        if self._frames >= self.max_frames:
            if not self._limit_fired:
                self._limit_fired = True
                log.info("Zeitlimit erreicht (%d s)", self.max_frames // self.sample_rate)
                if self.on_limit:
                    self.on_limit()
            return
        self._chunks.append(indata[:, 0].copy())
        self._frames += frames

    def stop(self):
        """Stoppt die Aufnahme und liefert das Audio als float32-Array (mono)."""
        with self._lock:
            if self._stream is None:
                return np.zeros(0, dtype=np.float32)
            self._stream.stop()
            self._stream.close()
            self._stream = None
        audio = np.concatenate(self._chunks) if self._chunks else np.zeros(0, dtype=np.float32)
        self._chunks = []
        log.info("Aufnahme beendet: %.1f s", len(audio) / self.sample_rate)
        return audio
