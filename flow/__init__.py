"""Lokales Diktat – Wispr-Flow-artige Diktier-App, komplett offline."""

__version__ = "1.0.0"


def hard_exit(code=0):
    """Prozess sofort beenden, ohne DLL-Teardown.

    ctranslate2/cuDNN crashen beim regulären Prozessende unter Windows
    (0xC0000409 im DLL-Unload) – TerminateProcess überspringt das und
    liefert den korrekten Exit-Code.
    """
    import ctypes
    import sys

    sys.stdout.flush()
    sys.stderr.flush()
    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    kernel32.TerminateProcess(kernel32.GetCurrentProcess(), code)
