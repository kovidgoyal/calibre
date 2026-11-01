# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

import glob
import os
import shutil
from typing import IO, TYPE_CHECKING

from calibre.customize.conversion import InputFormatPlugin
from calibre.ptempfile import TemporaryDirectory
from calibre.utils import StreamOrPath
from calibre.utils.localization import _

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.metadata.toc import TOC
    from calibre.ebooks.oeb.base import OEBBook
    from calibre.utils.logging import Log


class PMLInput(InputFormatPlugin):
    name = 'PML Input'
    author = 'John Schember'
    description = _('Convert PML to OEB')
    # pmlz is a zip file containing pml files and png images.
    file_types = {'pml', 'pmlz'}
    commit_name = 'pml_input'

    def process_pml(self, pml_path: str | IO[bytes], html_path: str, close_all: bool = False) -> TOC:
        from calibre.ebooks.pml.pmlconverter import PML_HTMLizer

        with StreamOrPath(pml_path, 'rb') as pml_stream, StreamOrPath(html_path, 'wb') as html_stream:
            pml_stream.seek(0)
            ienc = getattr(pml_stream, 'encoding', None)
            if ienc is None:
                ienc = 'cp1252'
            enc_opt = getattr(self.options, 'input_encoding', None)
            if enc_opt:
                ienc = enc_opt

            self.log.debug('Converting PML to HTML...')
            hizer = PML_HTMLizer()
            html = hizer.parse_pml(pml_stream.read().decode(ienc), html_path)
            html = f'<html><head><title></title></head><body>{html}</body></html>'
            html_stream.write(html.encode('utf-8', 'replace'))
            return hizer.get_toc()

    def get_images(self, stream: IO[bytes] | None = None, tdir: str | None = None, top_level: bool = False) -> list[str]:
        images = []
        imgs = []

        if top_level:
            assert tdir is not None
            imgs = glob.glob(os.path.join(tdir, '*.png'))
        # Images not in top level try bookname_img directory because
        # that's where Dropbook likes to see them.
        if not imgs:
            if hasattr(stream, 'name') and tdir is not None:
                imgs = glob.glob(os.path.join(tdir, os.path.splitext(os.path.basename(stream.name))[0] + '_img', '*.png'))
        # No images in Dropbook location try generic images directory
        if not imgs and tdir is not None:
            imgs = glob.glob(os.path.join(os.path.join(tdir, 'images'), '*.png'))
        if imgs:
            os.makedirs(os.path.join(os.getcwd(), 'images'))
        for img in imgs:
            pimg_name = os.path.basename(img)
            pimg_path = os.path.join(os.getcwd(), 'images', pimg_name)

            images.append('images/' + pimg_name)

            shutil.copy(img, pimg_path)

        return images

    def convert(self, stream: IO[bytes], options: Values, file_ext: str, log: Log, accelerators: dict[str, str]) -> str:
        from calibre.ebooks.metadata.opf2 import OPFCreator
        from calibre.ebooks.metadata.toc import TOC
        from calibre.utils.zipfile import ZipFile

        # PMLInput stores the conversion options on the instance, shadowing the
        # class level set of OptionRecommendations
        self.options = options  # ty: ignore[invalid-assignment]
        self.log = log
        pages, images = [], []
        toc = TOC()

        if file_ext == 'pmlz':
            log.debug('De-compressing content to temporary directory...')
            with TemporaryDirectory('_unpmlz') as tdir:
                zf = ZipFile(stream)
                zf.extractall(tdir)

                pmls = glob.glob(os.path.join(tdir, '*.pml'))
                for pml in pmls:
                    html_name = os.path.splitext(os.path.basename(pml))[0] + '.html'
                    html_path = os.path.join(os.getcwd(), html_name)

                    pages.append(html_name)
                    log.debug(f'Processing PML item {pml}...')
                    ttoc = self.process_pml(pml, html_path)
                    toc += ttoc
                images = self.get_images(stream, tdir, True)
        else:
            toc = self.process_pml(stream, 'index.html')
            pages.append('index.html')

            if hasattr(stream, 'name'):
                images = self.get_images(stream, os.path.abspath(os.path.dirname(stream.name)))

        # We want pages to be ordered alphabetically.
        pages.sort()

        manifest_items = []
        for item in pages + images:
            manifest_items.append((item, None))

        from calibre.ebooks.metadata.meta import get_metadata

        log.debug('Reading metadata from input file...')
        mi = get_metadata(stream, 'pml')
        if 'images/cover.png' in images:
            mi.cover = 'images/cover.png'
        opf = OPFCreator(os.getcwd(), mi)
        log.debug('Generating manifest...')
        opf.create_manifest(manifest_items)
        opf.create_spine(pages)
        opf.set_toc(toc)
        with open('metadata.opf', 'wb') as opffile:
            with open('toc.ncx', 'wb') as tocfile:
                opf.render(opffile, tocfile, 'toc.ncx')

        return os.path.join(os.getcwd(), 'metadata.opf')

    def postprocess_book(self, oeb: OEBBook, opts: Values, log: Log) -> None:
        from lxml import etree

        from calibre.ebooks.oeb.base import XHTML, barename

        for item in oeb.spine:
            root = item.data
            if isinstance(root, etree._Element):
                for heading in root.iterdescendants(*map(XHTML, 'h1 h2 h3 h4 h5 h6'.split())):
                    if not len(heading):
                        continue
                    span = heading[0]
                    if not heading.text and not span.text and not len(span) and isinstance(span.tag, str) and barename(span.tag) == 'span':
                        if not heading.get('id') and (span_id := span.get('id')):
                            heading.set('id', span_id)
                            heading.text = span.tail
                            heading.remove(span)
                    if len(heading) == 1 and heading[0].get('style') == 'text-align: center; margin: auto;':
                        div = heading[0]
                        if isinstance(div.tag, str) and barename(div.tag) == 'div' and not len(div) and not div.get('id') and not heading.get('style'):
                            heading.text = (heading.text or '') + (div.text or '') + (div.tail or '')
                            heading.remove(div)
                            heading.set('style', 'text-align: center')
