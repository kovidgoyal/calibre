#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import struct
import unittest
from base64 import standard_b64decode as b64decode

from calibre.utils.imghdr import what

# An 8x8 image with four quadrants: red, green, blue and fully transparent
# white, in that order. Losslessly encoded, so the decoded pixels must match
# exactly. As a bare codestream and in the container format.
STILL_JXL = b64decode('/wpBwEoIABAAnABLGJOOg4MksQaql88BAACAXkAIAPn1+fn11MuXT/1wAAAAGB4AAAA=')
CONTAINER_JXL = b64decode('AAAADEpYTCANCocKAAAAFGZ0eXBqeGwgAAAAAGp4bCAAAAA6anhsY/8KQcBKCAAQAJwASxiTjoODJLEGqpfPAQAAgF5ACAD59fn59dTLl0/9cAAAABgeAAAA')

# A two frame, 2x2 animation where each frame lasts 250ms that loops forever.
# The first frame is red and the second blue.
ANIMATION_JXL = b64decode('/woIEMEAYgIIAOoLAAAsAEsYixXCSUFOfwAACADqBwAsAEsYixXCSUEOQH8A')

# A 4x2 image (top row red, red, green, green and bottom row blue, blue,
# white, white) with an orientation specifying a 90 degree anti-clockwise
# rotation, so it must decode as a 2x4 image. In the container format, with
# the codestream split into two jxlp boxes with an Exif box between them.
ROTATED_JXL = b64decode(
    'AAAADEpYTCANCocKAAAAFGZ0eXBqeGwgAAAAAGp4bCAAAAATanhscAAAAAD/CghwD8QEAAAAK2Jyb2JFeGlmGx0AAARUuTaT8QVPvh4kkVBiATdgw6CV1Mb/'
    'RY9MBQAAACZqeGxwgAAAAQgAAQBQAEsYixXCAWxccHeBAABCICCg4OYU'
)

# A 3x2 black grayscale image and a 3x2 grayscale image with alpha, every
# pixel having value 100 and alpha 128
GRAY_JXL = b64decode('/woIQBAUNwIIAAEAGABLGIsVggE=')
GRAY_ALPHA_JXL = b64decode('/woIQLAobgQIABAAMABLGIsVwkkC5oQEAwA=')

NOT_AN_IMAGE = b'\x89PNG\r\n\x1a\n' + bytes(64)


def split_into_parts(codestream: bytes, part_size: int = 3) -> bytes:
    "Put codestream into a JPEG-XL container, split into many jxlp boxes with other boxes between them"
    ans = [b'\x00\x00\x00\x0cJXL \x0d\x0a\x87\x0a', struct.pack('>L4s4sL4s', 20, b'ftyp', b'jxl ', 0, b'jxl ')]
    parts = [codestream[i : i + part_size] for i in range(0, len(codestream), part_size)]
    for i, part in enumerate(parts):
        index = i | (0x80000000 if i == len(parts) - 1 else 0)
        ans.append(struct.pack('>L4sL', 12 + len(part), b'jxlp', index) + part)
        ans.append(struct.pack('>L4s', 9, b'free') + b'x')
    return b''.join(ans)


def pixels(img):
    "The pixels of img as a list of rows of (r, g, b, a) tuples"
    return [[img.pixelColor(x, y).getRgb() for x in range(img.width())] for y in range(img.height())]


def pixels64(img):
    "The pixels of img as a list of rows of 16 bit (r, g, b, a) tuples"
    ans = []
    for y in range(img.height()):
        row = []
        for x in range(img.width()):
            c = img.pixelColor(x, y).rgba64()
            row.append((c.red(), c.green(), c.blue(), c.alpha()))
        ans.append(row)
    return ans


RED, GREEN, BLUE, WHITE = (255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 255, 255)
TRANSPARENT = (255, 255, 255, 0)
STILL_PIXELS = [[(RED if x < 4 else GREEN) if y < 4 else (BLUE if x < 4 else TRANSPARENT) for x in range(8)] for y in range(8)]


def encode(img, quality=100, fmt=b'jxl'):
    "Encode img with QImageWriter, returning the encoded bytes and the error string if it failed"
    from qt.core import QBuffer, QByteArray, QImageWriter, QIODevice

    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    try:
        w = QImageWriter(buf, fmt)
        w.setQuality(quality)
        if not w.write(img):
            return b'', w.errorString()
    finally:
        buf.close()
    return bytes(ba), ''


def make_image(fmt, width=7, height=5):
    "An image with a different color for every pixel, with varying alpha if the format has alpha"
    from qt.core import QColor, QImage

    img = QImage(width, height, fmt)
    has_alpha = img.hasAlphaChannel()
    for y in range(height):
        for x in range(width):
            r, g, b = (x * 4099 + y * 997) % 65536, (y * 9973 + x * 31) % 65536, (x * y * 1013) % 65536
            a = (x * 7919 + y * 4001) % 65536 if has_alpha else 65535
            img.setPixelColor(x, y, QColor.fromRgba64(r, g, b, a))
    return img


class TestJXL(unittest.TestCase):
    def test_jxl_header_detection(self):
        for data in (STILL_JXL, CONTAINER_JXL, ANIMATION_JXL, ROTATED_JXL, GRAY_JXL, GRAY_ALPHA_JXL, split_into_parts(STILL_JXL)):
            self.assertEqual('jxl', what(None, data))
        self.assertEqual('png', what(None, NOT_AN_IMAGE))
        # JPEG 2000 uses a similar signature box
        self.assertEqual('jpeg2000', what(None, b'\x00\x00\x00\x0cjP  \r\n\x87\n' + bytes(64)))
        # must not blow up on truncated data
        for i in range(32):
            what(None, CONTAINER_JXL[:i])

    def test_jxl_plugin_is_registered_with_qt(self):
        from qt.core import QImageReader, QImageWriter

        from calibre_extensions import jxl

        self.assertTrue(jxl.register_jxl_image_format())
        self.assertTrue(jxl.is_jxl(STILL_JXL))
        self.assertTrue(jxl.is_jxl(CONTAINER_JXL))
        self.assertFalse(jxl.is_jxl(NOT_AN_IMAGE))
        self.assertFalse(jxl.is_jxl(b''))
        fmts = {bytes(x).decode('utf-8') for x in QImageReader.supportedImageFormats()}
        self.assertIn('jxl', fmts, f'The JPEG-XL image format plugin was not loaded. Available plugins: {fmts}')
        fmts = {bytes(x).decode('utf-8') for x in QImageWriter.supportedImageFormats()}
        self.assertIn('jxl', fmts, f'The JPEG-XL image format plugin cannot write. Available plugins: {fmts}')
        self.assertIn('image/jxl', {bytes(x).decode('utf-8') for x in QImageReader.supportedMimeTypes()})

    def test_reading_jxl_images(self):
        from qt.core import QImage

        from calibre.utils.img import image_and_format_from_data

        for data in (STILL_JXL, CONTAINER_JXL, split_into_parts(STILL_JXL)):
            img, fmt = image_and_format_from_data(data)
            self.assertEqual('jxl', fmt)
            self.assertEqual(QImage.Format.Format_RGBA8888, img.format())
            self.assertEqual((8, 8), (img.width(), img.height()))
            self.assertEqual(STILL_PIXELS, pixels(img))
            self.assertTrue(img.colorSpace().isValid())

    def test_reading_jxl_images_applies_orientation(self):
        from qt.core import QBuffer, QByteArray, QImageReader, QIODevice, QSize

        from calibre.utils.img import image_from_data

        img = image_from_data(ROTATED_JXL)
        self.assertEqual((2, 4), (img.width(), img.height()))
        self.assertEqual([[GREEN, WHITE], [GREEN, WHITE], [RED, BLUE], [RED, BLUE]], pixels(img))
        ba = QByteArray(ROTATED_JXL)  # must outlive buf
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        try:
            self.assertEqual(QSize(2, 4), QImageReader(buf).size())
        finally:
            buf.close()

    def test_reading_grayscale_jxl_images(self):
        from qt.core import QImage

        from calibre.utils.img import image_from_data

        img = image_from_data(GRAY_JXL)
        self.assertEqual(QImage.Format.Format_Grayscale8, img.format())
        self.assertEqual([[(0, 0, 0, 255)] * 3] * 2, pixels(img))
        # Qt has no grayscale with alpha format
        img = image_from_data(GRAY_ALPHA_JXL)
        self.assertEqual(QImage.Format.Format_RGBA8888, img.format())
        self.assertEqual([[(100, 100, 100, 128)] * 3] * 2, pixels(img))

    def test_reading_jxl_animations(self):
        from qt.core import QBuffer, QByteArray, QImageReader, QIODevice

        ba = QByteArray(ANIMATION_JXL)  # must outlive buf
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        try:
            r = QImageReader(buf)
            self.assertEqual('jxl', bytes(r.format()).decode('utf-8'))
            self.assertTrue(r.supportsAnimation())
            self.assertEqual(2, r.imageCount())
            self.assertEqual(-1, r.loopCount(), 'The animation should loop forever')
            frames = []
            for i in range(r.imageCount()):
                self.assertEqual(i, r.currentImageNumber())
                img = r.read()
                self.assertFalse(img.isNull(), f'Failed to read frame {i}: {r.errorString()}')
                self.assertEqual(250, r.nextImageDelay())
                frames.append(pixels(img)[0][0])
            self.assertEqual([RED, BLUE], frames)
            self.assertTrue(r.read().isNull(), 'Reading past the last frame should fail')
            # Jumping around needs the decoder to restart
            for frame, expected in ((1, BLUE), (0, RED), (1, BLUE), (1, BLUE)):
                self.assertTrue(r.jumpToImage(frame))
                img = r.read()
                self.assertFalse(img.isNull(), f'Failed to read frame {frame} after jumping: {r.errorString()}')
                self.assertEqual(expected, pixels(img)[0][0])
            self.assertFalse(r.jumpToImage(2))
            self.assertFalse(r.jumpToImage(-1))
        finally:
            buf.close()

    def test_reading_corrupted_jxl_images(self):
        from calibre.utils.img import NotImage, image_from_data

        for data in (STILL_JXL[:20], STILL_JXL[:2] + bytes(64), CONTAINER_JXL[:12], CONTAINER_JXL[:60], ROTATED_JXL[:-10]):
            self.assertRaises(NotImage, image_from_data, data)

    def test_reading_damaged_jxl_images_is_safe(self):
        # Every truncation and a flip of every bit of the fixtures must fail
        # or produce some image, never crash
        from qt.core import QImage

        for data in (STILL_JXL, CONTAINER_JXL, ANIMATION_JXL, ROTATED_JXL, GRAY_ALPHA_JXL):
            for i in range(len(data)):
                QImage.fromData(data[:i], 'jxl')
                for bit in range(8):
                    damaged = bytearray(data)
                    damaged[i] ^= 1 << bit
                    QImage.fromData(bytes(damaged), 'jxl')

    def test_reading_respects_allocation_limit(self):
        from qt.core import QBuffer, QByteArray, QImage, QImageReader, QIODevice

        img = QImage(1024, 1024, QImage.Format.Format_RGBA8888)
        img.fill(0xFF00FF00)
        data, err = encode(img)
        self.assertFalse(err)
        before = QImageReader.allocationLimit()
        QImageReader.setAllocationLimit(1)  # megabytes
        ba = QByteArray(data)  # must outlive buf
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.ReadOnly)
        try:
            r = QImageReader(buf, b'jxl')
            self.assertTrue(r.read().isNull())
        finally:
            buf.close()
            QImageReader.setAllocationLimit(before)
        self.assertEqual((1024, 1024), (QImage.fromData(data).width(), QImage.fromData(data).height()))

    def test_writing_jxl_images_losslessly(self):
        from qt.core import QImage

        F = QImage.Format
        for src_fmt, decoded_fmt in (
            (F.Format_RGBA8888, F.Format_RGBA8888),
            (F.Format_ARGB32, F.Format_RGBA8888),
            (F.Format_RGB888, F.Format_RGBX8888),
            (F.Format_RGB32, F.Format_RGBX8888),
            (F.Format_Grayscale8, F.Format_Grayscale8),
            (F.Format_Grayscale16, F.Format_Grayscale16),
            (F.Format_RGBA64, F.Format_RGBA64),
            (F.Format_RGBX64, F.Format_RGBX64),
        ):
            src = make_image(src_fmt)
            data, err = encode(src)
            self.assertFalse(err, f'Failed to encode {src_fmt}: {err}')
            self.assertEqual('jxl', what(None, data))
            img = QImage.fromData(data)
            self.assertFalse(img.isNull(), f'Failed to decode {src_fmt}')
            self.assertEqual(decoded_fmt, img.format(), f'Decoding {src_fmt} gave the wrong format')
            expected = src.convertToFormat(decoded_fmt)
            if decoded_fmt in (F.Format_RGBA64, F.Format_RGBX64, F.Format_Grayscale16):
                self.assertEqual(pixels64(expected), pixels64(img), f'Pixels for {src_fmt} differ')
            else:
                self.assertEqual(pixels(expected), pixels(img), f'Pixels for {src_fmt} differ')

    def test_writing_jxl_images_lossily(self):
        from qt.core import QColor, QImage

        src = QImage(64, 48, QImage.Format.Format_ARGB32)
        src.fill(QColor(200, 50, 30, 128))
        for quality in (-1, 30, 60, 90):
            data, err = encode(src, quality)
            self.assertFalse(err)
            img = QImage.fromData(data)
            self.assertEqual((64, 48), (img.width(), img.height()))
            for actual, expected in zip(img.pixelColor(10, 10).getRgb(), (200, 50, 30, 128)):
                self.assertLess(abs(actual - expected), 8, f'Quality: {quality}')
        # The quality setting must actually be used
        src = make_image(QImage.Format.Format_RGB888, 64, 48)
        low, high = (len(encode(src, quality)[0]) for quality in (30, 95))
        self.assertLess(low, high)

    def test_writing_jxl_images_preserves_color_space(self):
        from qt.core import QColor, QColorSpace, QImage

        src = QImage(8, 8, QImage.Format.Format_RGB888)
        src.fill(QColor(200, 50, 30))
        src.setColorSpace(QColorSpace(QColorSpace.NamedColorSpace.DisplayP3))
        srgb = QColorSpace(QColorSpace.NamedColorSpace.SRgb)
        expected = src.convertedToColorSpace(srgb).pixelColor(1, 1).getRgb()
        for quality in (100, 90):
            data, err = encode(src, quality)
            self.assertFalse(err)
            img = QImage.fromData(data)
            self.assertTrue(img.colorSpace().isValid())
            if quality == 100:
                self.assertEqual(src.colorSpace(), img.colorSpace())
                self.assertEqual((200, 50, 30, 255), img.pixelColor(1, 1).getRgb())
            # Whatever color space the pixels are in, they must be the same color
            actual = img.convertedToColorSpace(srgb).pixelColor(1, 1).getRgb()
            for a, e in zip(actual, expected):
                self.assertLess(abs(a - e), 6, f'Quality: {quality} {actual} != {expected}')

    def test_writing_jxl_images_with_image_to_data(self):
        from calibre.utils.img import image_from_data, image_to_data

        img = image_from_data(STILL_JXL)
        data = image_to_data(img, compression_quality=100, fmt='JXL')
        self.assertEqual('jxl', what(None, data))
        self.assertEqual(STILL_PIXELS, pixels(image_from_data(data)))
        data = image_to_data(img, compression_quality=80, fmt='jxl')
        self.assertEqual('jxl', what(None, data))

    def test_writing_jxl_image_failures(self):
        from qt.core import QBuffer, QByteArray, QImage, QImageWriter, QIODevice

        _, err = encode(QImage())
        self.assertTrue(err)
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.ReadOnly)  # writing to it fails
        try:
            self.assertFalse(QImageWriter(buf, b'jxl').write(make_image(QImage.Format.Format_RGB888)))
        finally:
            buf.close()


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestJXL)


if __name__ == '__main__':
    from calibre.utils.run_tests import run_cli

    run_cli(find_tests(), verbosity=4)
