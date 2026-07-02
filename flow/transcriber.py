"""faster-whisper-Wrapper: Hintergrund-Load, CUDA→CPU-Fallback, VAD-Filter."""

import logging
import os
import threading

import numpy as np

log = logging.getLogger(__name__)


def _add_cuda_dll_dirs():
    """DLL-Ordner der pip-Pakete nvidia-cublas-cu12 / nvidia-cudnn-cu12 registrieren.

    ctranslate2 findet cuBLAS/cuDNN sonst nur über PATH; die pip-Wheels legen die
    DLLs unter site-packages/nvidia/<paket>/bin ab.
    """
    import importlib.util

    for pkg in ("nvidia.cublas", "nvidia.cudnn"):
        try:
            spec = importlib.util.find_spec(pkg)
        except (ImportError, ValueError):
            spec = None
        if not spec or not spec.submodule_search_locations:
            continue
        for loc in spec.submodule_search_locations:
            for sub in ("bin", "lib"):
                p = os.path.join(loc, sub)
                if os.path.isdir(p):
                    os.add_dll_directory(p)
                    log.debug("DLL-Pfad registriert: %s", p)


class Transcriber:
    """Lädt das Whisper-Modell asynchron; transcribe() wartet bis es bereit ist."""

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
        want = self.cfg["device"]
        candidates = []
        if want in ("auto", "cuda"):
            candidates.append(("cuda", self.cfg["model_gpu"], self.cfg["compute_type_gpu"]))
        if want in ("auto", "cpu"):
            candidates.append(("cpu", self.cfg["model_cpu"], self.cfg["compute_type_cpu"]))

        from faster_whisper import WhisperModel

        for device, model_name, compute_type in candidates:
            try:
                self.on_status(f"Lade Modell {model_name} ({device}) …")
                log.info("Lade Modell %s auf %s (%s)", model_name, device, compute_type)
                if device == "cuda":
                    _add_cuda_dll_dirs()
                model = WhisperModel(model_name, device=device, compute_type=compute_type)
                # Warmup deckt CUDA-Fehler auf, die erst bei der ersten Inferenz auftreten
                warmup = np.zeros(int(0.5 * 16000), dtype=np.float32)
                list(model.transcribe(warmup, language=self.cfg["language"])[0])
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
        segments, _info = self.model.transcribe(
            audio,
            language=self.cfg["language"],
            beam_size=self.cfg["beam_size"],
            vad_filter=True,
            initial_prompt=self.cfg["initial_prompt"] or None,
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        log.info("Transkribiert: %d Zeichen", len(text))
        return text
