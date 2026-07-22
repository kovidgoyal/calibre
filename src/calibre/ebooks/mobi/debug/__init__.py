#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid@kovidgoyal.net>


def format_bytes(byts):
    byts = bytearray(byts)
    byts = [f'{b:x}' for b in byts]
    return ' '.join(byts)
