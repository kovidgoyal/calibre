#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

from io import BytesIO
from typing import TYPE_CHECKING

from lxml import etree
from PIL import Image

from calibre.ebooks.oeb.base import SVG_MIME, is_element_list, urlnormalize, xpath
from calibre.utils.img import read_alt_text

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.conversion.plumber import OptionValues
    from calibre.ebooks.oeb.base import Manifest, OEBBook
    from calibre.utils.logging import Log


def process_spine_item(item: Manifest.Item, hrefs: dict[str, Manifest.Item], log: Log) -> None:
    html = item.data
    assert isinstance(html, etree._Element)  # spine items are always (X)HTML documents
    imgs = xpath(html, '//h:img[@src]')
    assert is_element_list(imgs)
    for elem in imgs:
        src = urlnormalize(elem.attrib['src'])
        image = hrefs.get(item.abshref(src), None)
        if image and image.media_type != SVG_MIME and not elem.attrib.get('alt'):
            data = image.bytes_representation
            try:
                with Image.open(BytesIO(data)) as im:
                    alt = read_alt_text(im)
            except Exception as err:
                log.warn(f'Failed to read alt text from image {src} with error: {err}')
            else:
                if alt:
                    elem.set('alt', alt)


class AddAltText:
    def __call__(self, oeb: OEBBook, opts: Values | OptionValues) -> None:
        oeb.logger.info('Add alt text to images...')
        hrefs = oeb.manifest.hrefs
        for item in oeb.spine:
            process_spine_item(item, hrefs, oeb.log)
