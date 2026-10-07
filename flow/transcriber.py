"""Parakeet-Wrapper (onnx-asr): Hintergrund-Load, CUDA→CPU-Fallback."""

import logging
import os
import threading

import numpy as np

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
MIN_SECONDS = 0.3  # kürzere Aufnahmen sind versehentliche Tastendrücke


def _add_cuda_dll_dirs():
    """DLL-Ordner der pip-Pakete von onnxruntime-gpu[cuda,cudnn] registrieren.

    onnxruntime-gpu braucht CUDA 13 (Runtime, cuBLAS, cuFFT, cuRAND, nvrtc, nvJitLink) und
    cuDNN 9. Die pip-Wheels legen die DLLs je nach Paket unter site-packages/nvidia/cu13/bin/x86_64
    oder nvidia/cudnn/bin ab – deshalb werden alle Ordner unter nvidia/ mit DLLs eingesammelt.
    Fehlt eine transitive Abhängigkeit, meldet Windows nur irreführend "Modul nicht gefunden".

    os.add_dll_directory() allein reicht nicht immer: manche DLLs werden erst zur Laufzeit
    über die klassische Windows-DLL-Suche (u.a. PATH) nachgeladen. Deshalb zusätzlich in
    PATH voranstellen.
    """
    import importlib.util

    try:
        spec = importlib.util.find_spec("nvidia")
    except (ImportError, ValueError):
        spec = None
    if not spec or not spec.submodule_search_locations:
        return

    dirs = []
    for root in spec.submodule_search_locations:
        for path, _subdirs, files in os.walk(root):
            if any(f.lower().endswith(".dll") for f in files):
                os.add_dll_directory(path)
                dirs.append(path)
                log.debug("DLL-Pfad registriert: %s", path)

    if dirs:
        os.environ["PATH"] = os.pathsep.join(dirs) + os.pathsep + os.environ["PATH"]


def _sessions(obj, depth=4, seen=None):
    """Sammelt alle onnxruntime-Sessions, die im onnx-asr-Modellobjekt stecken."""
    import onnxruntime as ort

    seen = seen if seen is not None else set()
    if depth < 0 or id(obj) in seen:
        return []
    seen.add(id(obj))
    if isinstance(obj, ort.InferenceSession):
        return [obj]
    found = []
    children = obj.values() if isinstance(obj, dict) else getattr(obj, "__dict__", {}).values()
    for child in children:
        found += _sessions(child, depth - 1, seen)
    return found


class Transcriber:
    """Lädt das Parakeet-Modell asynchron; transcribe() wartet bis es bereit ist."""

    def __init__(self, cfg, on_status=None):
        self.cfg = cfg
        self.on_status = on_status or (lambda text: None)
        self.model = None
        self.device = None
        self.model_name = None
        self.load_error = None
        self.ready = threading.Event()

    def load_async(self):
        threading.Thread(target=self._load, name="model-load", daemon=True).start()

    def _load(self):
        import onnx_asr
        import onnxruntime as ort

        ort.set_default_logger_severity(3)  # nur Fehler; Warnungen gehen sonst ungefiltert auf stderr
        want = self.cfg["device"]
        candidates = []
        if want in ("auto", "cuda"):
            if "CUDAExecutionProvider" in ort.get_available_providers():
                candidates.append(("cuda", "CUDAExecutionProvider", self.cfg["quantization_gpu"]))
            else:
                log.info("onnxruntime ohne CUDA-Unterstützung – überspringe GPU.")
        if want in ("auto", "cpu"):
            candidates.append(("cpu", "CPUExecutionProvider", self.cfg["quantization_cpu"]))

        model_name = self.cfg["model"]
        for device, provider, quantization in candidates:
            try:
                self.on_status(f"Lade Modell {model_name} ({device}) …")
                log.info("Lade Modell %s auf %s (Quantisierung: %s)", model_name, device, quantization)
                if device == "cuda":
                    _add_cuda_dll_dirs()
                    ort.preload_dlls()
                model = onnx_asr.load_model(model_name, quantization=quantization, providers=[provider])
                # onnxruntime fällt still auf die CPU zurück, wenn CUDA-DLLs fehlen
                if device == "cuda" and not any(
                    provider in s.get_providers() for s in _sessions(model)
                ):
                    raise RuntimeError("CUDA-Provider nicht aktiv (CUDA 13 / cuDNN 9 fehlen?)")
                # Warmup deckt CUDA-Fehler auf, die erst bei der ersten Inferenz auftreten
                model.recognize(np.zeros(int(0.5 * SAMPLE_RATE), dtype=np.float32), sample_rate=SAMPLE_RATE)
                self.model = model
                self.device = device
                self.model_name = model_name
                self.load_error = None
                self.ready.set()
                log.info("Modell bereit: %s auf %s", model_name, device)
                self.on_status(f"Bereit – {model_name} ({device})")
                return
            except Exception as exc:
                log.warning("Modell-Load auf %s fehlgeschlagen: %s", device, exc)
                self.load_error = exc

        self.ready.set()  # Wartende nicht ewig blockieren
        log.error("Kein Modell geladen: %s", self.load_error)
        self.on_status("Fehler: Modell konnte nicht geladen werden")

    def transcribe(self, audio):
        """Transkribiert float32-Mono-Audio (16 kHz) zu Text."""
        self.ready.wait()
        if self.model is None:
            raise RuntimeError(f"Modell nicht geladen: {self.load_error}")
        if len(audio) < MIN_SECONDS * SAMPLE_RATE:
            return ""
        text = self.model.recognize(audio.astype(np.float32, copy=False), sample_rate=SAMPLE_RATE).strip()
        log.info("Transkribiert: %d Zeichen", len(text))
        return text
