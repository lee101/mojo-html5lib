from __future__ import annotations

import ctypes
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIB = os.environ.get("MOJO_HTML5LIB_LIB", os.path.join(ROOT, "dist", "libmojo-html5lib.so"))

I = ctypes.c_int64
_loaded: ctypes.CDLL | None = None
_RECORD_WIDTH = 5
_UNSUPPORTED = -1


def lib() -> ctypes.CDLL:
    global _loaded
    if _loaded is None:
        if not os.path.exists(LIB):
            raise RuntimeError("Mojo library is not built; run `pixi run build`")
        _loaded = ctypes.CDLL(LIB)
        _loaded.mh5_scan.argtypes = [I, I, I, I]
        _loaded.mh5_scan.restype = I
    return _loaded


def scan(source: str) -> tuple[bytes, np.ndarray] | None:
    try:
        data = source.encode("ascii")
    except UnicodeEncodeError:
        return None
    if not data:
        return data, np.empty((0, _RECORD_WIDTH), dtype=np.int64)
    buf = np.frombuffer(data, dtype=np.uint8)
    if not buf.flags.c_contiguous or buf.itemsize != 1:
        raise RuntimeError("internal source buffer is not contiguous bytes")
    count = lib().mh5_scan(buf.ctypes.data, buf.size, 0, 0)
    if count == _UNSUPPORTED:
        return None
    if count < 0 or count > buf.size:
        raise RuntimeError(f"Mojo tokenizer returned invalid record count {count}")
    records = np.empty((count, _RECORD_WIDTH), dtype=np.int64, order="C")
    if records.dtype.itemsize != ctypes.sizeof(I) or not records.flags.c_contiguous:
        raise RuntimeError("internal record buffer does not match the Mojo Int ABI")
    written = lib().mh5_scan(buf.ctypes.data, buf.size, records.ctypes.data, count)
    # Both NumPy arrays stay strongly referenced until the synchronous FFI call returns.
    if written == _UNSUPPORTED:
        raise RuntimeError("Mojo tokenizer rejected input after a successful count pass")
    if written != count:
        raise RuntimeError(f"Mojo tokenizer count changed from {count} to {written}")
    return data, records
