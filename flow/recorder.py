"""Mikrofonaufnahme: dauerhaft offener sounddevice-Stream mit Pre-Roll-Ringpuffer."""

import collections
import logging
import threading

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)


class Recorder:
    """Hält den Input-Stream dauerhaft offen; start()/stop() kippen nur ein Sammel-Flag.

    Der Callback läuft permanent und füttert einen Ringpuffer von pre_roll_seconds
    Länge. Beim Start der Aufnahme wird dessen Inhalt übernommen — so beginnt die
    Aufnahme ohne Geräte-Öffnungslatenz und erfasst sogar Sprache, die minimal vor
    dem Tastendruck begonnen hat. on_limit wird (einmalig, aus dem Audio-Thread)
    gerufen, wenn max_seconds erreicht ist.
    """

    def __init__(self, sample_rate=16000, input_device=None, max_seconds=120,
                 pre_roll_seconds=0.4, on_limit=None):
        self.sample_rate = sample_rate
        self.input_device = input_device
        self.max_frames = int(max_seconds * sample_rate)
        self.pre_roll_frames = int(pre_roll_seconds * sample_rate)
        self.on_limit = on_limit
        self._stream = None
        self._pre_roll = collections.deque()
        self._pre_roll_held = 0
        self._chunks = []
        self._frames = 0
        self._collecting = False
        self._limit_fired = False
        self._lock = threading.Lock()

    @property
    def is_recording(self):
        return self._collecting

    def open(self):
        """Öffnet den dauerhaften Input-Stream (beim App-Start bzw. Reopen)."""
        if self._stream is not None:
            return
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            device=self.input_device,
            callback=self._callback,
        )
        self._stream.start()
        device = self.input_device if self.input_device is not None else "Standard"
        log.info("Mikrofon-Stream geöffnet (Gerät: %s)", device)

    def close(self):
        with self._lock:
            self._collecting = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
            log.info("Mikrofon-Stream geschlossen")

    def _ensure_stream(self):
        """Öffnet den Stream neu, falls er fehlt oder tot ist (z. B. Gerät abgezogen)."""
        if self._stream is not None:
            if self._stream.active:
                return
            log.warning("Mikrofon-Stream inaktiv – öffne neu")
            try:
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self.open()

    def start(self):
        self._ensure_stream()
        self._begin_collect()

    def _begin_collect(self):
        with self._lock:
            if self._collecting:
                return
            self._chunks = list(self._pre_roll)
            self._frames = sum(len(c) for c in self._chunks)
            self._limit_fired = False
            self._collecting = True
        log.info("Aufnahme gestartet (Pre-Roll: %.2f s)", self._frames / self.sample_rate)

    def stop(self):
        """Beendet das Sammeln und liefert das Audio; der Stream bleibt offen."""
        with self._lock:
            self._collecting = False
            chunks, self._chunks = self._chunks, []
        audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
        log.info("Aufnahme beendet: %.1f s", len(audio) / self.sample_rate)
        return audio

    def _callback(self, indata, frames, time_info, status):
        if status:
            log.warning("Audio-Status: %s", status)
        chunk = indata[:, 0].copy()
        fire_limit = False
        with self._lock:
            self._pre_roll.append(chunk)
            self._pre_roll_held += len(chunk)
            # trimmen, solange der Puffer auch ohne den ältesten Block lang genug bleibt
            while self._pre_roll and self._pre_roll_held - len(self._pre_roll[0]) >= self.pre_roll_frames:
                self._pre_roll_held -= len(self._pre_roll.popleft())
            if self._collecting:
                if self._frames >= self.max_frames:
                    if not self._limit_fired:
                        self._limit_fired = True
                        fire_limit = True
                else:
                    self._chunks.append(chunk)
                    self._frames += len(chunk)
        if fire_limit:
            log.info("Zeitlimit erreicht (%d s)", self.max_frames // self.sample_rate)
            if self.on_limit:
                self.on_limit()
