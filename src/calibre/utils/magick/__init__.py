#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid@kovidgoyal.net>

from calibre.utils.magick.legacy import Image, PixelWand  # ruff: ignore[unused-import]


def create_canvas(width: float, height: float, bgcolor: str = '#ffffff') -> Image:
    canvas = Image()
    canvas.create_canvas(int(width), int(height), str(bgcolor))
    return canvas
