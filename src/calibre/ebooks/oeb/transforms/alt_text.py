#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>


from io import BytesIO

from PIL import Image

from calibre.ebooks.oeb.base import SVG_MIME, urlnormalize, xpath
from calibre.utils.img import read_alt_text


def process_spine_item(item, hrefs, log):
    html = item.data
    for elem in xpath(html, '//h:img[@src]'):
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

    def __call__(self, oeb, opts):
        oeb.logger.info('Add alt text to images...')
        hrefs = oeb.manifest.hrefs
        for item in oeb.spine:
            process_spine_item(item, hrefs, oeb.log)
