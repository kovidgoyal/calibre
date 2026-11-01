#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

from io import BytesIO
from typing import TYPE_CHECKING

from PIL import Image

from calibre import as_unicode
from calibre.ebooks.oeb.polish.check.base import WARN, BaseError
from calibre.ebooks.oeb.polish.check.parsing import EmptyFile
from calibre.utils.localization import _
from polyglot.builtins import error_message

if TYPE_CHECKING:
    from calibre.ebooks.oeb.polish.container import Container


class InvalidImage(BaseError):
    RULE_NAME = _('Invalid image')
    HELP = _('An invalid image is an image that could not be loaded, typically because it is corrupted. You should replace it with a good image or remove it.')

    def __init__(self, msg: str, name: str, line: int | None = None, col: int | None = None) -> None:
        BaseError.__init__(self, 'Invalid image: ' + msg, name, line, col)


class CMYKImage(BaseError):
    HELP = _(
        'Reader devices based on Adobe Digital Editions cannot display images whose'
        ' colors are specified in the CMYK colorspace. You should convert this image'
        ' to the RGB colorspace, for maximum compatibility.'
    )
    INDIVIDUAL_FIX = _('Convert image to RGB automatically')
    level = WARN

    def __call__(self, container: Container) -> bool:
        from qt.core import QImage

        from calibre.gui2 import pixmap_to_data
        from calibre_extensions.imageops import load_from_data_without_gil

        ext = container.mime_map[self.name].split('/')[-1].upper()
        if ext == 'JPG':
            ext = 'JPEG'
        if ext not in ('PNG', 'JPEG', 'GIF'):
            return False
        with container.open(self.name, 'r+b') as f:
            raw = f.read()
            i = QImage()
            load_from_data_without_gil(i, raw)
            if i.isNull():
                return False
            raw = pixmap_to_data(i, format=ext, quality=95)
            f.seek(0)
            f.truncate()
            f.write(raw)
        return True


def check_raster_images(name: str, mt: str, raw: bytes) -> list[BaseError]:
    if not raw:
        return [EmptyFile(name)]
    errors: list[BaseError] = []
    try:
        i = Image.open(BytesIO(raw))
    except Exception as e:
        errors.append(InvalidImage(as_unicode(error_message(e)), name))
    else:
        if i.mode == 'CMYK':
            errors.append(CMYKImage(_('Image is in the CMYK colorspace'), name))

    return errors
