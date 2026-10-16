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
        def check(self, data):
            x = compress_doc(data)
            self.assertEqual(py_compress_doc(data), x, f'len(data)={len(data)}')
            self.assertEqual(decompress_doc(x), data)

        def test_palmdoc_compression(self):
            for test in [
                b'abc\x03\x04\x05\x06ms',  # Test binary writing
                b'a b c \xfed ',  # Test encoding of spaces
                b'0123456789axyz2bxyz2cdfgfo9iuyerh',
                b'0123456789asd0123456789asd|yyzzxxffhhjjkk',
                (b'ciewacnaq eiu743 r787q 0w%  ; sa fd\xef\ffdxosac wocjp acoiecowei owaic jociowapjcivcjpoivjporeivjpoavca; p9aw8743y6r74%$^$^%8 '),
            ]:
                self.check(test)

        def test_palmdoc_compression_matches_reference(self):
            # The match finder in the C implementation must find the same
            # matches as the simple search in py_compress_doc, in particular
            # for repeated data and for repeats near the maximum distance.
            import random

            rnd = random.Random(0)
            for alphabet in (2, 3, 4, 16, 200):
                self.check(bytes(rnd.randrange(1, alphabet + 1) for _ in range(400)))
            words = [bytes(rnd.randrange(97, 123) for _ in range(rnd.randrange(1, 9))) for _ in range(50)]
            self.check(b' '.join(rnd.choice(words) for _ in range(150)))
            self.check(bytes(rnd.randrange(0, 256) for _ in range(300)))
            for gap in range(2045, 2050):  # repeat distance of 2047 is the maximum
                base = bytes(rnd.randrange(32, 127) for _ in range(12))
                filler = bytes(rnd.randrange(128, 255) for _ in range(gap - 12))
                self.check(base + filler + base + b'tail')
            self.check(b'abcdefghij' * 50)
            self.check(b'\0' * 500)

        def test_palmdoc_compression_edge_cases(self):
            self.assertEqual(cPalmdoc.compress(b''), b'')
            self.assertEqual(compress_doc(b''), b'')
            for size in range(1, 25):  # around the 10 byte margins at either end
                self.check(b'x' * size)
                self.check(bytes(range(1, size + 1)))
                self.check(b'ab ' * size)
            # control and high bytes are written as binary runs of at most 8 bytes
            self.check(bytes(range(1, 9)) * 3 + bytes(range(0x80, 0x100)) + b'end')
            self.check(b'abc\x01' + b'\x80' * 20 + b'abc\x01' + b'\x80' * 20)

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
