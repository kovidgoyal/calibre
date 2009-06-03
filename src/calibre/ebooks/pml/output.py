# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

try:
    from PIL import Image
    Image
except ImportError:
    import Image

import cStringIO

from calibre.customize.conversion import OutputFormatPlugin
from calibre.ptempfile import TemporaryDirectory
from calibre.utils.zipfile import ZipFile
from calibre.ebooks.oeb.base import OEB_IMAGES
from calibre.ebooks.pml.pmlml import PMLMLizer

class PMLOutput(OutputFormatPlugin):

    name = 'PML Output'
    author = 'John Schember'
    file_type = 'pmlz'

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        with TemporaryDirectory('_pmlz_output') as tdir:
            pmlmlizer = PMLMLizer(ignore_tables=opts.linearize_tables)
            content = pmlmlizer.extract_content(oeb_book, opts)
            with open(os.path.join(tdir, 'index.pml'), 'wb') as out:
                out.write(content.encode('utf-8'))

            self.write_images(oeb_book.manifest, tdir)

            pmlz = ZipFile(output_path, 'w')
            pmlz.add_dir(tdir)

    def write_images(self, manifest, out_dir):
        for item in manifest:
            if item.media_type in OEB_IMAGES:
                im = Image.open(cStringIO.StringIO(item.data))

                data = cStringIO.StringIO()
                im.save(data, 'PNG')
                data = data.getvalue()

                name = os.path.splitext(os.path.basename(item.href))[0] + '.png'
                path = os.path.join(out_dir, name)

                with open(path, 'wb') as out:
                    out.write(data)

