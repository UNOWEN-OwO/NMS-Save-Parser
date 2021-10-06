import gc
import json
import logging
import mmap
import shutil
from pathlib import Path
from typing import Any, Dict

import lz4.block

_LOGGER = logging.getLogger(__name__)


class _NMSSave:
    __slots__ = "_path", "_tree"

    from _mapping import _DECODING, _ENCODING
    _BINARY_SEPARATOR = b'\x00' * 4
    _BINARY_START = b"\xE5\xA1\xED\xFE"
    _MISSING = set()

    @classmethod
    def _decoding_dict(cls, d: Dict[str, Any], method: str):
        rd = {}
        for k, v in d.items():
            kn = cls._DECODING.get(k, k)
            if kn == k:
                cls._MISSING.add(k)
                _LOGGER.warning(f"Cannot decode key {k}")
            rd[kn] = cls._transform_values(v, method)
        return rd

    @classmethod
    def _encoding_dict(cls, d: Dict[str, Any], method: str):
        rd = {}
        for k, v in d.items():
            if k not in cls._ENCODING and k not in cls._MISSING:
                raise RuntimeError(f"Unknown key {k}")
            rd[cls._ENCODING[k]] = cls._transform_values(v, method)
        return rd

    @classmethod
    def _transform_values(cls, v, method: str):
        if v is None or isinstance(v, (int, float, bool, str)):
            return v
        if isinstance(v, list):
            return [cls._transform_values(iv, method) for iv in v]
        if isinstance(v, dict):
            return getattr(cls, f"_{method}_dict")(v, method)
        raise RuntimeError(f"Unrecognised field value type ({type(v)})")

    @classmethod
    def load_from(cls, path: Path) -> bytes:
        with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            if mm[:4] == cls._BINARY_START:
                dest = b''
                while mm.read(4) == cls._BINARY_START:
                    compressed_size = int.from_bytes(mm.read(4), "little")
                    actual_size = int.from_bytes(mm.read(4), "little")
                    if mm.read(4) != cls._BINARY_SEPARATOR:
                        raise RuntimeError("corrupted save file (invalid separator)")
                    dest += lz4.block.decompress(mm.read(compressed_size), uncompressed_size=actual_size)
                if mm.read():
                    raise RuntimeError("corrupted save file (unknown trailing data)")
                return dest.rstrip(b'\x00')
            return mm.rstrip(b'\x00')

    @classmethod
    def save_to(cls, data: bytes, path: Path):
        data += b'\x00'
        compressed = lz4.block.compress(data, store_size=False)
        with open(path, "wb") as f, mmap.mmap(f.fileno(), 16 + len(compressed), access=mmap.ACCESS_WRITE) as mm:
            mm.write(cls._BINARY_START)
            mm.write(len(compressed).to_bytes(4, "little", signed=False))
            mm.write(len(data).to_bytes(4, "little", signed=False))
            mm.write(cls._BINARY_SEPARATOR)
            mm.write(compressed)

    def __init__(self, path: Path):
        self._path = path
        self._tree = self._transform_values(json.loads(self.load_from(path)), "decoding")

    def backup(self):
        self._path.rename(f"{self._path}.bak")

    def save(self):
        self.save_to(
            json.dumps(self._transform_values(self._tree, "encoding"), separators=(',', ':')).encode("utf-8"),
            self._path
        )
