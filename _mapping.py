#!/usr/bin/env python3
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Tuple

import spookyhash
from lz4.block import compress, decompress
from requests import Session

_MASK = (1 << 64) - 1
_ORD_0 = ord(b'0')
_ORD_Z = ord(b'Z')


# rewritten as per https://github.com/monkeyman192/MBINCompiler/blob/development/SaveFileMapping/Program.cs
def _hash(s: str) -> str:
    hashed = spookyhash.hash128(s.encode("utf-8"), 8268756125562466087, 8268756125562466087) & _MASK
    return "".join(
        chr(av if av <= _ORD_Z else av + 6)
        for av in (
            v % 68 + _ORD_0
            for v in (
                hashed,
                hashed >> 21,
                hashed >> 42
            )
        )
    )


def _fetch() -> Tuple[str, str, Dict[str, str]]:
    (tmp := Path("tmp")).mkdir(0o755, True, True)

    with Session() as session:
        version = Path(session.head(
            "https://github.com/monkeyman192/MBINCompiler/releases/latest",
            allow_redirects=False
        ).headers["Location"]).name
        json_content = session.get(
            f"https://github.com/monkeyman192/MBINCompiler/releases/download/{version}/mapping.json"
        ).text

        jar_res = session.get("https://github.com/goatfungus/NMSSaveEditor/raw/master/NMSSaveEditor.jar")

    loaded_json = json.loads(json_content)

    json_version = loaded_json["libMBIN_version"]
    mapping = {
        m["Key"]: m["Value"]
        for m in loaded_json["Mapping"]
    }

    with open(tmp / "NMSSaveEditor.jar", "wb") as f:
        f.write(jar_res.content)
    subprocess.run(["jar", "-xf", "NMSSaveEditor.jar"], cwd=tmp)

    with open(tmp / "nomanssave/db/jsonmap.txt", "r") as f:
        mapping.update(
            line.split()
            for line in f.read().splitlines()
            if line
        )
    with open(tmp / "META-INF/MANIFEST.MF", "r") as f:
        meta = {
            k: v
            for k, v in (
                line.split(": ")
                for line in f.read().splitlines()
                if line
            )
        }
        jar_version = meta["Implementation-Version"]

    for k, v in mapping.items():
        if k != (hv := _hash(v)):
            raise RuntimeError(f"{v} has inconsistent hash: {k} vs {hv}")

    shutil.rmtree(tmp)

    return json_version, jar_version, mapping


def _save(json_version: str, jar_version: str, mapping: Dict[str, str]):
    with open("mapping.bin", "wb") as f:
        f.write(compress(f"""{json_version}
{jar_version}
{'|'.join(f"{k},{v}" for k, v in mapping.items())}""".encode("ascii"), mode="high_compression", compression=12))


def _load(missing_ok=False) -> Tuple[str, str, Dict[str, str], Dict[str, str]]:
    path = Path("mapping.bin")
    if path.exists():
        with open(path, "rb") as f:
            json_version, jar_version, data = decompress(f.read()).decode("ascii").split()
            decoding = {}
            for line in data.split('|'):
                k, v = line.split(',')
                decoding[k] = v
            data = decoding
    elif missing_ok:
        json_version, jar_version, data = _fetch()
        _save(json_version, jar_version, data)
    else:
        raise RuntimeError("mapping.bin not found")
    return json_version, jar_version, data, {
        v: k
        for k, v in data.items()
    }
