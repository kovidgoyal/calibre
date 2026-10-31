#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import os
from io import BytesIO
from typing import IO, TYPE_CHECKING

from calibre.utils.img import (
    add_borders_to_image,
    clone_image,
    create_canvas,
    despeckle_image,
    flip_image,
    gaussian_blur_image,
    gaussian_sharpen_image,
    grayscale_image,
    image_and_format_from_data,
    image_has_transparent_pixels,
    image_to_data,
    null_image,
    overlay_image,
    quantize_image,
    remove_borders_from_image,
    resize_image,
    rotate_image,
    set_image_opacity,
    texture_image,
)
from calibre.utils.imghdr import identify

if TYPE_CHECKING:
    from qt.core import QImage


class PixelWand:
    def __init__(self) -> None:
        self.color = '#ffffff'


class Image:
    def __init__(self) -> None:
        self.read_format: str | None = None
        self.write_format: str | None = None
        self.img: QImage = null_image()

    @property
    def clone(self) -> Image:
        ans = Image()
        ans.img = clone_image(self.img)
        ans.read_format = self.read_format
        ans.write_format = self.write_format
        return ans

    def open(self, path_or_file: str | IO[bytes]) -> None:
        if not isinstance(path_or_file, str) and hasattr(path_or_file, 'read'):
            self.load(path_or_file.read())
        else:
            with open(path_or_file, 'rb') as f:
                self.load(f.read())

    def load(self, data: bytes) -> None:
        if not data:
            raise ValueError('No image data present')
        self.img, self.read_format = image_and_format_from_data(data)

    read = load

    def from_qimage(self, img: QImage) -> None:
        self.img = clone_image(img)

    def to_qimage(self) -> QImage:
        return clone_image(self.img)

    @property
    def type(self) -> str:
        if len(self.img.colorTable()) > 0:
            return 'PaletteType'
        return 'TrueColorType'

    @type.setter
    def type(self, t: str) -> None:
        if t == 'GrayscaleType':
            self.img = grayscale_image(self.img)
        elif t == 'PaletteType':
            self.img = quantize_image(self.img)

    @property
    def format(self) -> str | None:
        return self.write_format or self.read_format

    @format.setter
    def format(self, val: str | None) -> None:
        self.write_format = val

    @property
    def colorspace(self) -> str:
        return 'RGBColorspace'

    @colorspace.setter
    def colorspace(self, val: str) -> None:
        raise NotImplementedError('Changing image colorspace is not supported')

    @property
    def size(self) -> tuple[int, int]:
        return self.img.width(), self.img.height()

    @size.setter
    def size(self, val: tuple[int, int]) -> None:
        w, h = val[:2]
        self.img = resize_image(self.img, w, h)

    def save(self, path: str, format: str | None = None) -> None:
        if format is None:
            ext = os.path.splitext(path)[1]
            if len(ext) < 2:
                raise ValueError('No format specified')
            format = ext[1:]
        format = format.upper()

        with open(path, 'wb') as f:
            f.write(self.export(format))

    def compose(self, img: Image, left: int = 0, top: int = 0, operation: str = 'OverCompositeOp') -> None:
        bounds = self.size
        if left < 0 or top < 0 or left >= bounds[0] or top >= bounds[1]:
            raise ValueError('left and/or top out of bounds')
        self.img = overlay_image(img.img, self.img, left=left, top=top)

    def rotate(self, background_pixel_wand: PixelWand, degrees: float) -> None:
        self.img = rotate_image(self.img, degrees)

    def quantize(self, number_colors: int, colorspace: str = 'RGBColorspace', treedepth: int = 0, dither: bool = True, measure_error: bool = False) -> None:
        self.img = quantize_image(self.img, max_colors=number_colors, dither=dither)

    def identify(self, data: bytes | IO[bytes]) -> tuple[int, int, str | None]:
        fmt, width, height = identify(data)
        return width, height, fmt

    def remove_border(self, fuzz: int | None = None) -> None:
        if fuzz is not None and (fuzz < 0 or fuzz > 255):
            fuzz = None
        self.img = remove_borders_from_image(self.img, fuzz)

    trim = remove_border

    def add_border(self, pixel_wand: PixelWand, dx: int, dy: int) -> None:
        self.img = add_borders_to_image(self.img, left=dx, top=dy, right=dx, bottom=dy, border_color=pixel_wand.color)

    def blur(self, radius: float = -1, sigma: float = 3.0) -> None:
        self.img = gaussian_blur_image(self.img, radius, sigma)

    def copy(self, img: Image) -> None:
        self.img = clone_image(img.img)

    def create_canvas(self, width: float, height: float, background_pixel_wand: str) -> None:
        self.img = create_canvas(width, height, background_pixel_wand)

    def despeckle(self) -> None:
        self.img = despeckle_image(self.img)

    def export(self, fmt: str = 'JPEG') -> bytes:
        if fmt.lower() == 'gif':
            data = image_to_data(self.img, fmt='PNG', png_compression_level=0)
            from PIL import Image

            i = Image.open(BytesIO(data))
            buf = BytesIO()
            i.save(buf, 'gif')
            return buf.getvalue()
        return image_to_data(self.img, fmt=fmt)

    def flip(self, vertical: bool = True) -> None:
        self.img = flip_image(self.img, horizontal=not vertical, vertical=vertical)

    def has_transparent_pixels(self) -> bool:
        return image_has_transparent_pixels(self.img)

    def set_border_color(self, *args: object, **kw: object) -> None:
        pass  # no-op

    def set_compression_quality(self, *args: object, **kw: object) -> None:
        pass  # no-op

    def set_opacity(self, alpha: float = 0.5) -> None:
        self.img = set_image_opacity(self.img, alpha)

    def set_page(self, *args: object, **kw: object) -> None:
        pass  # no-op

    def sharpen(self, radius: float = 0, sigma: float = 3) -> None:
        self.img = gaussian_sharpen_image(self.img, radius, sigma)

    def texture(self, img: Image) -> None:
        self.img = texture_image(self.img, img.img)

    def thumbnail(self, width: int, height: int) -> None:
        self.img = resize_image(self.img, width, height)
