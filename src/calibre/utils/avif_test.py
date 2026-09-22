#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import unittest
from base64 import standard_b64decode as b64decode

from calibre.utils.imghdr import what

# An 8x8 image with four quadrants: red, green, blue and fully transparent
# white, in that order. Losslessly encoded, so the decoded pixels must match
# exactly.

STILL_AVIF = b64decode(
    'AAAAIGZ0eXBhdmlmAAAAAGF2aWZtaWYxbWlhZk1BMUEAAAGGbWV0YQAAAAAAAAAhaGRscgAAAAAAAAAAcGljdAAAAAAAAAAAAAAAAAAAAAAOcGl0'
    'bQAAAAAAAQAAACxpbG9jAAAAAEQAAAIAAQAAAAEAAAHFAAAAMwACAAAAAQAAAa4AAAAXAAAAQmlpbmYAAAAAAAIAAAAaaW5mZQIAAAAAAQAAYXYw'
    'MUNvbG9yAAAAABppbmZlAgAAAAACAABhdjAxQWxwaGEAAAAAGmlyZWYAAAAAAAAADmF1eGwAAgABAAEAAADDaXBycAAAAJ1pcGNvAAAAFGlzcGUA'
    'AAAAAAAACAAAAAgAAAAQcGl4aQAAAAADCAgIAAAADGF2MUOBIAAAAAAAE2NvbHJuY2x4AAEADQAAgAAAAA5waXhpAAAAAAEIAAAADGF2MUOBABwA'
    'AAAAOGF1eEMAAAAAdXJuOm1wZWc6bXBlZ0I6Y2ljcDpzeXN0ZW1zOmF1eGlsaWFyeTphbHBoYQAAAAAeaXBtYQAAAAAAAAACAAEEAQKDBAACBAEF'
    'hgcAAABSbWRhdBIACgUYCL/lUDIMEAAAGN6ilT++hIiaEgAKCDgIv+UBDQAgMiUQAACLo9NLhQNgoG9TG3biNo6kANMzUgH0LNYijsz1LRyaynEw'
)

# A two frame, 2x2 image sequence at 4fps that loops forever. The first frame
# is red and the second blue.
ANIMATION_AVIF = b64decode(
    'AAAALGZ0eXBhdmlzAAAAAGF2aWZhdmlzbXNmMWlzbzhtaWYxbWlhZk1BMUEAAADrbWV0YQAAAAAAAAAhaGRscgAAAAAAAAAAcGljdAAAAAAAAAAA'
    'AAAAAAAAAAAOcGl0bQAAAAAAAQAAAB5pbG9jAAAAAEQAAAEAAQAAAAEAAAPlAAAAJQAAAChpaW5mAAAAAAABAAAAGmluZmUCAAAAAAEAAGF2MDFD'
    'b2xvcgAAAABqaXBycAAAAEtpcGNvAAAAFGlzcGUAAAAAAAAAAgAAAAIAAAAQcGl4aQAAAAADCAgIAAAADGF2MUOBIAAAAAAAE2NvbHJuY2x4AAEA'
    'DQAAgAAAABdpcG1hAAAAAAAAAAEAAQQBAoMEAAACxm1vb3YAAAB4bXZoZAEAAAAAAAAA5thguQAAAADm2GC5AAAABP//////////AAEAAAEAAAAA'
    'AAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAAJGdHJhawAAAGh0'
    'a2hkAQAAAQAAAADm2GC5AAAAAObYYLkAAAABAAAAAP//////////AAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAA'
    'AAAAQAAAAAACAAAAAgAAAAAALGVkdHMAAAAkZWxzdAEAAAEAAAABAAAAAAAAAAIAAAAAAAAAAAABAAAAAAGqbWRpYQAAACxtZGhkAQAAAAAAAADm'
    '2GC5AAAAAObYYLkAAAAEAAAAAAAAAAJVxAAAAAAAIWhkbHIAAAAAAAAAAHBpY3QAAAAAAAAAAAAAAAAAAAABVW1pbmYAAAAUdm1oZAAAAAEAAAAA'
    'AAAAAAAAACRkaW5mAAAAHGRyZWYAAAAAAAAAAQAAAAx1cmwgAAAAAQAAARVzdGJsAAAAlXN0c2QAAAAAAAAAAQAAAIVhdjAxAAAAAAAAAAEAAAAA'
    'AAAAAAAAAAAAAAAAAAIAAgBIAAAASAAAAAAAAAABCkFPTSBDb2RpbmcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGP//AAAADGF2MUOBIAAAAAAAE2Nv'
    'bHJuY2x4AAEADQAAgAAAABBjY3N0AAAAAHwAAAAAAAAYc3R0cwAAAAAAAAABAAAAAgAAAAEAAAAcc3RzYwAAAAAAAAABAAAAAQAAAAIAAAABAAAA'
    'HHN0c3oAAAAAAAAAAAAAAAIAAAAlAAAAGgAAABRzdGNvAAAAAAAAAAEAAAPlAAAAFHN0c3MAAAAAAAAAAQAAAAEAAABHbWRhdBIACgsgAAAABv38'
    '0BDQAjIUEACAAGrAmGgjeepLCO7qLir+6KgSADIWMAPAgAAAVoABAB+VmNAe0dGlfhx1kA=='
)

# A 4x2 image (top row red, red, green, green and bottom row blue, blue,
# white, white) with an irot property specifying a 90 degree anti-clockwise
# rotation, so it must decode as a 2x4 image.
ROTATED_AVIF = b64decode(
    'AAAAIGZ0eXBhdmlmAAAAAGF2aWZtaWYxbWlhZk1BMUEAAAD1bWV0YQAAAAAAAAAhaGRscgAAAAAAAAAAcGljdAAAAAAAAAAAAAAAAAAAAAAOcGl0'
    'bQAAAAAAAQAAAB5pbG9jAAAAAEQAAAEAAQAAAAEAAAEdAAAAMwAAAChpaW5mAAAAAAABAAAAGmluZmUCAAAAAAEAAGF2MDFDb2xvcgAAAAB0aXBy'
    'cAAAAFRpcGNvAAAAFGlzcGUAAAAAAAAABAAAAAIAAAAQcGl4aQAAAAADCAgIAAAADGF2MUOBIAAAAAAAE2NvbHJuY2x4AAEADQAAgAAAAAlpcm90'
    'AQAAABhpcG1hAAAAAAAAAAEAAQUBAoMEhQAAADttZGF0EgAKBzgEPygIaAEyJhAAAIulLeRLqoT6d9ll6ZMMuwc/Bz8lUv4QiAzBc4Ptx8HYkvRg'
)

NOT_AN_IMAGE = b'\x89PNG\r\n\x1a\n' + bytes(64)


def pixels(img):
    "The pixels of img as a list of rows of (r, g, b, a) tuples"
    return [[img.pixelColor(x, y).getRgb() for x in range(img.width())] for y in range(img.height())]


RED, GREEN, BLUE, WHITE = (255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 255, 255)
TRANSPARENT = (255, 255, 255, 0)


class TestAVIF(unittest.TestCase):
    def test_avif_header_detection(self):
        for data in (STILL_AVIF, ANIMATION_AVIF, ROTATED_AVIF):
            self.assertEqual('avif', what(None, data))
        self.assertEqual('png', what(None, NOT_AN_IMAGE))
        # must not blow up on truncated data
        for i in range(32):
            what(None, STILL_AVIF[:i])

    def test_avif_plugin_is_registered_with_qt(self):
        from qt.core import QImageReader

        from calibre_extensions import avif

        self.assertTrue(avif.is_avif(STILL_AVIF))
        self.assertFalse(avif.is_avif(NOT_AN_IMAGE))
        fmts = {bytes(x).decode('utf-8') for x in QImageReader.supportedImageFormats()}
        self.assertIn('avif', fmts, f'The AVIF image format plugin was not loaded. Available plugins: {fmts}')

    def test_reading_avif_images(self):
        from calibre.utils.img import image_and_format_from_data

        img, fmt = image_and_format_from_data(STILL_AVIF)
        self.assertEqual('avif', fmt)
        self.assertEqual((8, 8), (img.width(), img.height()))
        q = pixels(img)
        for y in range(8):
            for x in range(8):
                expected = (RED if x < 4 else GREEN) if y < 4 else (BLUE if x < 4 else TRANSPARENT)
                self.assertEqual(expected, q[y][x], f'Pixel at ({x}, {y}) is incorrect')

    def test_reading_avif_images_applies_transforms(self):
        from calibre.utils.img import image_from_data

        img = image_from_data(ROTATED_AVIF)
        self.assertEqual((2, 4), (img.width(), img.height()))
        self.assertEqual([[GREEN, WHITE], [GREEN, WHITE], [RED, BLUE], [RED, BLUE]], pixels(img))

    def test_reading_avif_animations(self):
        from qt.core import QBuffer, QByteArray, QImageReader, QIODevice

        ba = QByteArray(ANIMATION_AVIF)  # must outlive buf
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        try:
            r = QImageReader(buf)
            self.assertEqual('avif', bytes(r.format()).decode('utf-8'))
            self.assertTrue(r.supportsAnimation())
            self.assertEqual(2, r.imageCount())
            self.assertEqual(-1, r.loopCount(), 'The animation should loop forever')
            frames = []
            for i in range(r.imageCount()):
                self.assertEqual(250, r.nextImageDelay())
                img = r.read()
                self.assertFalse(img.isNull(), f'Failed to read frame {i}: {r.errorString()}')
                frames.append(pixels(img)[0][0])
            self.assertEqual([RED, BLUE], frames)
            self.assertTrue(r.read().isNull(), 'Reading past the last frame should fail')
        finally:
            buf.close()

    def test_reading_corrupted_avif_images(self):
        from calibre.utils.img import NotImage, image_from_data

        for data in (STILL_AVIF[:200], STILL_AVIF[:32] + bytes(64), STILL_AVIF[:12]):
            self.assertRaises(NotImage, image_from_data, data)


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestAVIF)


if __name__ == '__main__':
    from calibre.utils.run_tests import run_cli

    run_cli(find_tests(), verbosity=4)
