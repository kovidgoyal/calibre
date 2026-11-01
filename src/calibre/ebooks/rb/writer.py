# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

import io
import struct
from compression import zlib
from typing import IO, TYPE_CHECKING

from PIL import Image

from calibre.constants import __appname__, __version__
from calibre.ebooks.rb import HEADER, unique_name
from calibre.ebooks.rb.rbml import RBMLizer

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.oeb.base import Manifest, OEBBook
    from calibre.ebooks.oeb.base import Metadata as OEBMetadata
    from calibre.utils.logging import Log

TEXT_RECORD_SIZE = 4096


class TocItem:
    def __init__(self, name: str, size: int, flags: int) -> None:
        self.name = name
        self.size = size
        self.flags = flags


class RBWriter:
    def __init__(self, opts: Values, log: Log) -> None:
        self.opts = opts
        self.log = log
        self.name_map: dict[str, str] = {}

    def write_content(self, oeb_book: OEBBook, out_stream: IO[bytes], metadata: OEBMetadata | None = None) -> None:
        info = [('info.info', self._info_section(metadata))]
        images = self._images(oeb_book.manifest)
        text_size, chunks = self._text(oeb_book)
        chunck_sizes = [len(x) for x in chunks]
        text = [('index.html', chunks)]
        hidx = [('index.hidx', ' ')]

        toc_items = []
        page_count = 0
        for name, data in info + text + hidx + images:
            page_count += 1
            size = len(data)
            if (name, data) in text:
                flags = 8
                size = 0
                for c in chunck_sizes:
                    size += c
                size += 8 + (len(chunck_sizes) * 4)
            elif (name, data) in info:
                flags = 2
            else:
                flags = 0
            toc_items.append(TocItem(name.ljust(32, '\x00')[:32], size, flags))

        self.log.debug('Writing file header...')
        out_stream.write(HEADER)
        out_stream.write(struct.pack('<I', 0))
        out_stream.write(struct.pack('<IH', 0, 0))
        out_stream.write(struct.pack('<I', 0x128))
        out_stream.write(struct.pack('<I', 0))
        for i in range(0x20, 0x128, 4):
            out_stream.write(struct.pack('<I', 0))
        out_stream.write(struct.pack('<I', page_count))
        offset = out_stream.tell() + (len(toc_items) * 44)
        for item in toc_items:
            out_stream.write(item.name.encode('utf-8'))
            out_stream.write(struct.pack('<I', item.size))
            out_stream.write(struct.pack('<I', offset))
            out_stream.write(struct.pack('<I', item.flags))
            offset += item.size

        out_stream.write(info[0][1].encode('utf-8'))

        self.log.debug('Writing compressed RB HTHML...')
        # Compressed text with proper heading
        out_stream.write(struct.pack('<I', len(text[0][1])))
        out_stream.write(struct.pack('<I', text_size))
        for size in chunck_sizes:
            out_stream.write(struct.pack('<I', size))
        for chunk in text[0][1]:
            out_stream.write(chunk)

        self.log.debug('Writing images...')
        for item in hidx + images:
            w = item[1]
            if not isinstance(w, bytes):
                w = w.encode('utf-8')
            out_stream.write(w)

        total_size = out_stream.tell()
        out_stream.seek(0x1C)
        out_stream.write(struct.pack('<I', total_size))

    def _text(self, oeb_book: OEBBook) -> tuple[int, list[bytes]]:
        rbmlizer = RBMLizer(self.log, name_map=self.name_map)
        text = rbmlizer.extract_content(oeb_book, self.opts).encode('cp1252', 'xmlcharrefreplace')
        size = len(text)

        pages = []
        for i in range((len(text) + TEXT_RECORD_SIZE - 1) // TEXT_RECORD_SIZE):
            zobj = zlib.compressobj(9, zlib.DEFLATED, 13, 8, 0)
            pages.append(zobj.compress(text[i * TEXT_RECORD_SIZE : (i * TEXT_RECORD_SIZE) + TEXT_RECORD_SIZE]) + zobj.flush())

        return size, pages

    def _images(self, manifest: Manifest) -> list[tuple[str, bytes]]:
        from calibre.ebooks.oeb.base import OEB_RASTER_IMAGES

        images = []
        used_names = []

        for item in manifest:
            if item.media_type in OEB_RASTER_IMAGES:
                try:
                    data = b''

                    idata = item.data
                    assert isinstance(idata, bytes)  # raster images are unparsed bytes, errors are handled below
                    im = Image.open(io.BytesIO(idata)).convert('L')
                    data = io.BytesIO()
                    im.save(data, 'PNG')
                    data = data.getvalue()

                    name = f'{len(used_names)}.png'
                    name = unique_name(name, used_names)
                    used_names.append(name)
                    self.name_map[item.href] = name

                    images.append((name, data))
                except Exception as e:
                    self.log.error(f'Error: Could not include file {item.href} because {e}.')

        return images

    def _info_section(self, metadata: OEBMetadata | None) -> str:
        text = 'TYPE=2\n'
        if metadata:
            if len(metadata.title) >= 1:
                text += f'TITLE={metadata.title[0].value}\n'
            if len(metadata.creator) >= 1:
                from calibre.ebooks.metadata import authors_to_string

                text += f'AUTHOR={authors_to_string([x.value for x in metadata.creator])}\n'
        text += f'GENERATOR={__appname__} - {__version__}\n'
        text += 'PARSE=1\n'
        text += 'OUTPUT=1\n'
        text += 'BODY=index.html\n'

        return text
