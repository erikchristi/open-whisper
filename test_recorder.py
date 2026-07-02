"""Recorder-Test ohne Audiogerät: der Callback wird direkt mit synthetischen
Chunks gefüttert (100-ms-Blöcke mit eindeutigen Werten), sodass Pre-Roll,
Ringpuffer-Trimmung und Zeitlimit ohne Mikrofon prüfbar sind."""

import sys

import numpy as np

from flow.recorder import Recorder

SR = 16000
CHUNK = 1600  # 100 ms


def feed(rec, value, n=1):
    for _ in range(n):
        rec._callback(np.full((CHUNK, 1), float(value), dtype=np.float32), CHUNK, None, None)
        value += 1
    return value


def test_pre_roll_and_collect():
    rec = Recorder(sample_rate=SR, pre_roll_seconds=0.4, max_seconds=120)
    # 1 s "Vorlauf" (Werte 1..10), dann Aufnahme mit Werten 100..104
    feed(rec, 1, n=10)
    rec._begin_collect()
    feed(rec, 100, n=5)
    audio = rec.stop()

    assert len(audio) == 4 * CHUNK + 5 * CHUNK, f"Länge falsch: {len(audio)}"
    assert audio[0] == 7, f"Pre-Roll beginnt falsch: {audio[0]} (erwartet 7 = letzte 0,4 s)"
    assert audio.min() == 7, "Älteres als 0,4 s Pre-Roll enthalten"
    assert audio[-1] == 104, "Aufnahme-Ende fehlt"
    print("OK  Pre-Roll wird übernommen und korrekt auf 0,4 s getrimmt")


def test_ring_buffer_trim():
    rec = Recorder(sample_rate=SR, pre_roll_seconds=0.4, max_seconds=120)
    feed(rec, 1, n=100)  # 10 s Dauerbetrieb ohne Aufnahme
    held = rec._pre_roll_held
    assert held == 4 * CHUNK, f"Ringpuffer hält {held} Frames statt {4 * CHUNK}"
    print("OK  Ringpuffer wächst im Dauerbetrieb nicht")


def test_limit_fires_once():
    fired = []
    rec = Recorder(sample_rate=SR, pre_roll_seconds=0.0, max_seconds=0.5,
                   on_limit=lambda: fired.append(1))
    rec._begin_collect()
    feed(rec, 1, n=10)  # 1 s einspeisen, Limit ist 0,5 s
    audio = rec.stop()

    assert len(fired) == 1, f"on_limit feuerte {len(fired)}x statt 1x"
    assert len(audio) == 5 * CHUNK, f"Es wurden {len(audio)} Frames gesammelt statt {5 * CHUNK}"
    print("OK  Zeitlimit stoppt das Sammeln und feuert genau einmal")


def test_stop_without_recording():
    rec = Recorder(sample_rate=SR)
    audio = rec.stop()
    assert len(audio) == 0
    print("OK  stop() ohne Aufnahme liefert leeres Audio")


def main():
    test_pre_roll_and_collect()
    test_ring_buffer_trim()
    test_limit_fires_once()
    test_stop_without_recording()
    print("Alle Recorder-Tests bestanden.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"FEHLER: {exc}")
        sys.exit(1)
