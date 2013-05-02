# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import glob
import os
import shutil

from calibre.customize.conversion import InputFormatPlugin
from calibre.ptempfile import TemporaryDirectory

class PMLInput(InputFormatPlugin):

    name        = 'PML Input'
    author      = 'John Schember'
    description = 'Convert PML to OEB'
    # pmlz is a zip file containing pml files and png images.
    file_types  = set(['pml', 'pmlz'])

    def process_pml(self, pml_path, html_path, close_all=False):
        from calibre.ebooks.pml.pmlconverter import PML_HTMLizer

        pclose = False
        hclose = False

        if not hasattr(pml_path, 'read'):
            pml_stream = open(pml_path, 'rb')
            pclose = True
        else:
            pml_stream = pml_path
            pml_stream.seek(0)

        if not hasattr(html_path, 'write'):
            html_stream = open(html_path, 'wb')
            hclose = True
        else:
            html_stream = html_path

        ienc = pml_stream.encoding if pml_stream.encoding else 'cp1252'
        if self.options.input_encoding:
            ienc = self.options.input_encoding

        self.log.debug('Converting PML to HTML...')
        hizer = PML_HTMLizer()
        html = hizer.parse_pml(pml_stream.read().decode(ienc), html_path)
        html = '<html><head><title></title></head><body>%s</body></html>'%html
        html_stream.write(html.encode('utf-8', 'replace'))

        if pclose:
            pml_stream.close()
        if hclose:
            html_stream.close()

        return hizer.get_toc()

    def get_images(self, stream, tdir, top_level=False):
        images = []
        imgs = []

        if top_level:
            imgs = glob.glob(os.path.join(tdir, '*.png'))
        # Images not in top level try bookname_img directory because
        # that's where Dropbook likes to see them.
        if not imgs:
            if hasattr(stream, 'name'):
                imgs = glob.glob(os.path.join(tdir, os.path.splitext(os.path.basename(stream.name))[0] + '_img', '*.png'))
        # No images in Dropbook location try generic images directory
        if not imgs:
            imgs = glob.glob(os.path.join(os.path.join(tdir, u'images'), u'*.png'))
        if imgs:
            os.makedirs(os.path.join(os.getcwdu(), u'images'))
        for img in imgs:
            pimg_name = os.path.basename(img)
            pimg_path = os.path.join(os.getcwdu(), 'images', pimg_name)

            images.append('images/' + pimg_name)

            shutil.copy(img, pimg_path)

        return images

    def convert(self, stream, options, file_ext, log,
                accelerators):
        from calibre.ebooks.metadata.toc import TOC
        from calibre.ebooks.metadata.opf2 import OPFCreator
        from calibre.utils.zipfile import ZipFile

        self.options = options
        self.log = log
        pages, images = [], []
        toc = TOC()

        if file_ext == 'pmlz':
            log.debug('De-compressing content to temporary directory...')
            with TemporaryDirectory(u'_unpmlz') as tdir:
                zf = ZipFile(stream)
                zf.extractall(tdir)

                pmls = glob.glob(os.path.join(tdir, u'*.pml'))
                for pml in pmls:
                    html_name = os.path.splitext(os.path.basename(pml))[0]+'.html'
                    html_path = os.path.join(os.getcwdu(), html_name)

                    pages.append(html_name)
                    log.debug('Processing PML item %s...' % pml)
                    ttoc = self.process_pml(pml, html_path)
                    toc += ttoc
                images = self.get_images(stream, tdir, True)
        else:
            toc = self.process_pml(stream, u'index.html')
            pages.append(u'index.html')

            if hasattr(stream, 'name'):
                images = self.get_images(stream, os.path.abspath(os.path.dirname(stream.name)))

        # We want pages to be orded alphabetically.
        pages.sort()

        manifest_items = []
        for item in pages+images:
            manifest_items.append((item, None))

        from calibre.ebooks.metadata.meta import get_metadata
        log.debug('Reading metadata from input file...')
        mi = get_metadata(stream, 'pml')
        if 'images/cover.png' in images:
            mi.cover = u'images/cover.png'
        opf = OPFCreator(os.getcwdu(), mi)
        log.debug('Generating manifest...')
        opf.create_manifest(manifest_items)
        opf.create_spine(pages)
        opf.set_toc(toc)
        with open(u'metadata.opf', 'wb') as opffile:
            with open(u'toc.ncx', 'wb') as tocfile:
                opf.render(opffile, tocfile, u'toc.ncx')

        return os.path.join(os.getcwdu(), u'metadata.opf')
