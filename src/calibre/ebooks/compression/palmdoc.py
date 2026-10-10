#!/usr/bin/env python
# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>

import io
from struct import pack

from calibre_extensions import cPalmdoc


def decompress_doc(data):
    return cPalmdoc.decompress(data)


def compress_doc(data):
    return cPalmdoc.compress(data) if data else b''


def py_compress_doc(data):
    out = io.BytesIO()
    i = 0
    ldata = len(data)
    while i < ldata:
        if i > 10 and (ldata - i) > 10:
            chunk = b''
            match = -1
            for j in range(10, 2, -1):
                chunk = data[i : i + j]
                try:
                    match = data.rindex(chunk, 0, i)
                except ValueError:
                    continue
                if (i - match) <= 2047:
                    break
                match = -1
            if match >= 0:
                n = len(chunk)
                m = i - match
                code = 0x8000 + ((m << 3) & 0x3FF8) + (n - 3)
                out.write(pack('>H', code))
                i += n
                continue
        ch = data[i : i + 1]
        och = ord(ch)
        i += 1
        if ch == b' ' and i < ldata:
            onch = ord(data[i : i + 1])
            if onch >= 0x40 and onch < 0x80:
                out.write(pack('>B', onch ^ 0x80))
                i += 1
                continue
        if och == 0 or (och > 8 and och < 0x80):
            out.write(ch)
        else:
            j = i
            binseq = [ch]
            while j < ldata and len(binseq) < 8:
                ch = data[j : j + 1]
                och = ord(ch)
                if och == 0 or (och > 8 and och < 0x80):
                    break
                binseq.append(ch)
                j += 1
            out.write(pack('>B', len(binseq)))
            out.write(b''.join(binseq))
            i += len(binseq) - 1
    return out.getvalue()


def find_tests():
    import unittest

    class Test(unittest.TestCase):
        def test_palmdoc_compression(self):
            for test in [
                b'abc\x03\x04\x05\x06ms',  # Test binary writing
                b'a b c \xfed ',  # Test encoding of spaces
                b'0123456789axyz2bxyz2cdfgfo9iuyerh',
                b'0123456789asd0123456789asd|yyzzxxffhhjjkk',
                (b'ciewacnaq eiu743 r787q 0w%  ; sa fd\xef\ffdxosac wocjp acoiecowei owaic jociowapjcivcjpoivjporeivjpoavca; p9aw8743y6r74%$^$^%8 '),
            ]:
                x = compress_doc(test)
                self.assertEqual(py_compress_doc(test), x)
                self.assertEqual(decompress_doc(x), test)

        def test_palmdoc_compression_matches_reference(self):
            # The match finder in the C implementation must find the same
            # matches as the simple search in py_compress_doc, in particular
            # for repeated data and for repeats near the maximum distance.
            import random

            rnd = random.Random(0)
            tests = []
            for alphabet in (2, 3, 4, 16, 200):
                for size in (50, 500, 2500, 4096):
                    tests.append(bytes(rnd.randrange(1, alphabet + 1) for _ in range(size)))
            for gap in range(2040, 2056):
                base = bytes(rnd.randrange(32, 127) for _ in range(12))
                filler = bytes(rnd.randrange(128, 255) for _ in range(gap - 12))
                tests.append(base + filler + base + b'tail')
            tests.append(b'abcdefghij' * 700)
            tests.append(b'\0' * 5000)
            for test in tests:
                x = compress_doc(test)
                self.assertEqual(py_compress_doc(test), x)
                self.assertEqual(decompress_doc(x), test)

        def test_palmdoc_space_and_char_at_end(self):
            # A space followed by a character in 0x40-0x7F is packed into a
            # single byte, also when that character is the last byte of the input
            for test, expected in [
                (b' A', b'\xc1'),
                (b' @', b'\xc0'),
                (b' \x7f', b'\xff'),
                (b' ?', b' ?'),  # not in 0x40-0x7F
                (b' \x80', b' \x01\x80'),
                (b' ', b' '),
                (b'abc  A', b'abc \xc1'),
            ]:
                x = compress_doc(test)
                self.assertEqual(x, expected, f'compress_doc({test!r})')
                self.assertEqual(py_compress_doc(test), x, f'py_compress_doc({test!r})')
                self.assertEqual(decompress_doc(x), test)

    return unittest.defaultTestLoader.loadTestsFromTestCase(Test)
