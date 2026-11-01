#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid@kovidgoyal.net>


def base64_decode(raw: str | bytes) -> bytes:
    from io import BytesIO

    from polyglot.binary import from_base64_bytes

    # First try the python implementation as it is faster
    try:
        return from_base64_bytes(raw)
    except Exception:
        pass

    # Try a more robust version (adapted from FBReader sources)
    A, Z, a, z, zero, nine, plus, slash, equal = bytearray(b'AZaz09+/=')
    # Non-ASCII characters are not valid base64 and would be ignored below anyway
    data = bytearray(raw.encode('ascii', 'ignore') if isinstance(raw, str) else raw)
    out = BytesIO()
    pos = 0
    while pos < len(data):
        tot = 0
        i = 0
        while i < 4 and pos < len(data):
            byt = data[pos]
            pos += 1
            num = 0
            if A <= byt <= Z:
                num = byt - A
            elif a <= byt <= z:
                num = byt - a + 26
            elif zero <= byt <= nine:
                num = byt - zero + 52
            else:
                num = {plus: 62, slash: 63, equal: 64}.get(byt, None)
                if num is None:
                    # Ignore this byte
                    continue
            tot += num << (6 * (3 - i))
            i += 1
        triple = bytearray(3)
        for j in (2, 1, 0):
            triple[j] = tot & 0xFF
            tot >>= 8
        out.write(bytes(triple))
    return out.getvalue()
