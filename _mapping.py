_ENCODING = {}
_DECODING = {}

with open("mapping.txt", "r", encoding="utf-8") as f:
    for line in f:
        hv, v = line.split()
        _ENCODING[v] = hv
        _DECODING[hv] = v
