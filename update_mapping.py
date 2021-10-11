#!/usr/bin/env python3
from _mapping import _fetch, _save

if __name__ == "__main__":
    _save(*_fetch())
