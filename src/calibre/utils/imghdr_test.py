#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import unittest
from base64 import standard_b64decode as b64decode
from io import BytesIO

from calibre.utils.avif_test import ANIMATION_AVIF, ROTATED_AVIF, STILL_AVIF
from calibre.utils.imghdr import identify
from calibre.utils.jxl_test import ANIMATION_JXL, CONTAINER_JXL, GRAY_JXL, ROTATED_JXL, STILL_JXL, split_into_parts

# 3x5 images in each of the three kinds of WebP file, distinguished by their
# first chunk: lossy (VP8), lossless (VP8L) and extended (VP8X), the last
# being lossy with an alpha channel
LOSSY_WEBP = b64decode('UklGRjwAAABXRUJQVlA4IDAAAADQAQCdASoDAAUAAUAmJaACdLoB+AADsAD+8ut//NgVzXPv9//S4P0uD9Lg/9KQAAA=')
LOSSLESS_WEBP = b64decode('UklGRhwAAABXRUJQVlA4TA8AAAAvAgABAAcQ/Y/+ByKi/wEA')
EXTENDED_WEBP = b64decode(
    'UklGRmAAAABXRUJQVlA4WAoAAAAQAAAAAgAABAAAQUxQSAoAAAARB1DAiAhERP8DVlA4IDAAAADQAQCdASoDAAUAAUAmJaACdLoB+AADsAD+8ut//NgVzXPv9//S4P0uD9Lg/9KQAAA='
)


class TestIdentify(unittest.TestCase):
    def test_identify_webp(self) -> None:
        for data in (LOSSY_WEBP, LOSSLESS_WEBP, EXTENDED_WEBP):
            self.assertEqual(identify(data), ('webp', 3, 5), data[12:16])
            # Truncated data must not fail or give the wrong dimensions
            for i in range(30):
                fmt, width, height = identify(data[:i])
                if fmt == 'webp':
                    self.assertIn((width, height), ((-1, -1), (3, 5)), i)

    def test_identify_avif(self) -> None:
        self.assertEqual(identify(STILL_AVIF), ('avif', 8, 8))
        self.assertEqual(identify(ANIMATION_AVIF), ('avif', 2, 2))
        # Rotated by 90 degrees, so the dimensions are those it is displayed at
        self.assertEqual(identify(ROTATED_AVIF), ('avif', 2, 4))
        # From a stream, which is left where it was
        stream = BytesIO(STILL_AVIF)
        self.assertEqual(identify(stream), ('avif', 8, 8))
        self.assertEqual(stream.tell(), 0)
        for i in range(len(STILL_AVIF)):
            fmt, width, height = identify(STILL_AVIF[:i])
            if fmt == 'avif':
                self.assertIn((width, height), ((-1, -1), (8, 8)), i)

    def test_identify_jxl(self) -> None:
        self.assertEqual(identify(STILL_JXL), ('jxl', 8, 8))
        self.assertEqual(identify(CONTAINER_JXL), ('jxl', 8, 8))
        self.assertEqual(identify(ANIMATION_JXL), ('jxl', 2, 2))
        self.assertEqual(identify(GRAY_JXL), ('jxl', 3, 2))
        # Rotated by 90 degrees, so the dimensions are those it is displayed at
        self.assertEqual(identify(ROTATED_JXL), ('jxl', 2, 4))
        # The codestream header split over many jxlp boxes
        self.assertEqual(identify(split_into_parts(STILL_JXL, 1)), ('jxl', 8, 8))
        # Only the start of the codestream is needed, these exercise all the
        # different ways of encoding the size
        for header, size in (
            (b'/woggdAHiAQIAgEAlAIAAA==', (1001, 37)),  # explicit width and height
            (b'/wpCH4AEiAQIAgEAlAIAAA==', (37, 1001)),
            (b'/wq6XQORCAIBAJQCAAAAAA==', (4000, 3000)),  # height and a 4:3 aspect ratio
            (b'/woxQSQIAgEAlAIAAMABHA==', (300, 200)),  # small height and a 3:2 aspect ratio
        ):
            data = b64decode(header)
            self.assertEqual(identify(data), ('jxl',) + size)
            self.assertEqual(identify(split_into_parts(data)), ('jxl',) + size)
        # From a stream, which is left where it was
        stream = BytesIO(ROTATED_JXL)
        self.assertEqual(identify(stream), ('jxl', 2, 4))
        self.assertEqual(stream.tell(), 0)
        # Truncated data must not fail or give the wrong dimensions
        for data, size in ((STILL_JXL, (8, 8)), (ROTATED_JXL, (2, 4))):
            for i in range(len(data)):
                fmt, width, height = identify(data[:i])
                if fmt == 'jxl':
                    self.assertIn((width, height), ((-1, -1), size), i)
        # Nor must garbage
        self.assertEqual(identify(ROTATED_JXL[:12] + bytes(64)), ('jxl', -1, -1))
        self.assertEqual(identify(ROTATED_JXL[:12] + b'\xff' * 64), ('jxl', -1, -1))


def find_tests() -> unittest.TestSuite:
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestIdentify)


if __name__ == '__main__':
    from calibre.utils.run_tests import run_cli

    run_cli(find_tests(), verbosity=4)
