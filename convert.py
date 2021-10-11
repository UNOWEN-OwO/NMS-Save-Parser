import argparse
import json
import struct

import lz4.block as lb

from _mapping import _load

_, _, _DECODING, _ENCODING = _load(True)


def save_file(path, data):
    mode = SRC_MODE if SAVE_MODE == 0 else SAVE_MODE
    if mode < 3:
        map_keys(data, _ENCODING)

    if mode != 2:
        with open(path, 'wb') as file:
            file.write(json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode('utf-8'))
            if mode == 1:
                file.write(b'\x00')

    if mode == 2:
        with open(path, 'wb') as file:
            file.write(compress_file(json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode('utf-8')))


def map_keys(node, mapping):
    if isinstance(node, dict):
        for k in list(node.keys()):
            if k in mapping:
                node[mapping[k]] = node.pop(k)
            else:
                print('Key mapping not found: ', k)
        for k in node.keys():
            map_keys(node[k], mapping)
    elif isinstance(node, list):
        for k in node:
            map_keys(k, mapping)


def compress_file(data):
    ret = b''
    while block := data[:SLICE]:
        data = data[SLICE:]
        block += b'\x00' if len(block) < SLICE and block[-1] != b'\x00' else b''
        c = lb.compress(block, store_size=False)
        ret += b'\xE5\xA1\xED\xFE' + struct.pack('i', len(c)) + struct.pack('i', len(block)) + b'\x00' * 4 + c
    return ret


# return mapped json object
def load_file(file_path):
    global SRC_MODE
    with open(file_path, 'rb') as src:
        dest = b''
        while src.read(4) == b'\xE5\xA1\xED\xFE':
            block_size = struct.unpack('i', src.read(4))[0]
            dest_size = struct.unpack('i', src.read(4))[0]
            src.read(4)
            dest += lb.decompress(src.read(block_size), uncompressed_size=dest_size)
            # print('block_size:', block_size, 'dest_size:', dest_size, 'actual_size:', len(dest))

        if src.read(1):
            src.seek(0)
            dest = src.read().rstrip(b'\x00')
            SRC_MODE = 3
        else:
            dest = dest.rstrip(b'\x00')
            SRC_MODE = 2
        data = json.loads(dest.decode('utf-8'))
        if len([k for k in data.keys() if len(k) == 3]) > 3:
            map_keys(data, _DECODING)
            if SRC_MODE == 3:
                SRC_MODE = 1
        return data


parser = argparse.ArgumentParser()
parser.add_argument('-i', type=str, help='input path for NMS Save (*.hg) file')
parser.add_argument('-o', type=str, help='output path for NMS Save (*.hg) file')
parser.add_argument('-m', '--mode', type=int, default=0, help='0 for as input, 1 for uncompressed, 2 for compressed, 3 for mapped')
parser.add_argument('-s', '--slice', type=int, default=524288, help='save compress block size')
args, unknown = parser.parse_known_args()

SRC_MODE = 1
SAVE_MODE = args.mode
SLICE = args.slice

data = None
if src := args.i or unknown[0] if unknown else None:
    data = load_file(src)
if data:
    save_file(args.o or (unknown[1] if len(unknown) > 1 else None) or src, data)
