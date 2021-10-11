#!/usr/bin/env python3
import gc
import json
import shutil
import subprocess
import sys
from pathlib import Path

import spookyhash
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


def _main():
    (tmp := Path("tmp")).mkdir(0o755, True, True)

    with Session() as session:
        version = Path(session.head(
            "https://github.com/monkeyman192/MBINCompiler/releases/latest",
            allow_redirects=False
        ).headers["Location"]).name
        json_content = session.get(
            f"https://github.com/monkeyman192/MBINCompiler/releases/download/{version}/mapping.json"
        ).text
        del version

        jar_res = session.get("https://github.com/goatfungus/NMSSaveEditor/raw/master/NMSSaveEditor.jar")

    loaded_json = json.loads(json_content)
    del json_content

    json_version = loaded_json["libMBIN_version"]
    mapping = {
        m["Key"]: m["Value"]
        for m in loaded_json["Mapping"]
    }
    del loaded_json

    gc.collect()

    with open(tmp / "NMSSaveEditor.jar", "wb") as f:
        f.write(jar_res.content)
    del jar_res
    subprocess.run(["jar", "-xf", "NMSSaveEditor.jar"], cwd=tmp)

    with open(tmp / "nomanssave/db/jsonmap.txt", "r") as f:
        mapping.update(
            it
            for it in (
                line.split()
                for line in f.read().splitlines()
                if line
            )
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
        del meta

    decoding = {}
    encoding = {}
    for k, v in mapping.items():
        if k != (hv := _hash(v)):
            print(f"{v} has inconsistent hash: {k} vs {hv}", file=sys.stderr)
        decoding[hv] = v
        encoding[v] = hv
    del mapping

    gc.collect()

    with open("_mapping.py", "w", encoding="utf-8", newline='\n') as f:
        print(f"""# Generated Automatically
# DO NOT EDIT!

_LIBMBIN_VERSION = "{json_version}"

_NMSSAVEEDITOR_VERSION = "{jar_version}"

_DECODING = {json.dumps(decoding, indent=4)}

_ENCODING = {json.dumps(encoding, indent=4)}""", file=f)

    shutil.rmtree(tmp)


if __name__ == "__main__":
    _main()
