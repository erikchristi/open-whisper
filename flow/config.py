"""Konfiguration aus config.json laden und mit Defaults zusammenführen."""

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_DIR / "config.json"

DEFAULTS = {
    "hotkey_ptt": "f8",
    "hotkey_toggle": "f9",
    "language": "de",
    "device": "auto",
    "model_gpu": "large-v3-turbo",
    "model_cpu": "small",
    "compute_type_gpu": "int8_float16",
    "compute_type_cpu": "int8",
    "sample_rate": 16000,
    "input_device": None,
    "paste_method": "clipboard",
    "max_seconds": 120,
    "pre_roll_seconds": 0.4,
    "beam_size": 5,
    "initial_prompt": "",
}


def save_config(cfg, path=None):
    path = Path(path) if path else CONFIG_PATH
    data = {k: cfg[k] for k in DEFAULTS if k in cfg}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_config(path=None):
    path = Path(path) if path else CONFIG_PATH
    cfg = dict(DEFAULTS)
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                user_cfg = json.load(f)
            unknown = set(user_cfg) - set(DEFAULTS)
            if unknown:
                log.warning("Unbekannte Optionen in %s: %s", path.name, ", ".join(sorted(unknown)))
            cfg.update({k: v for k, v in user_cfg.items() if k in DEFAULTS})
        except (json.JSONDecodeError, OSError) as exc:
            log.error("config.json konnte nicht gelesen werden (%s) – nutze Defaults.", exc)
    return cfg
