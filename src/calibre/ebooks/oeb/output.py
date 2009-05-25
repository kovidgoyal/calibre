from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from lxml import etree

from calibre.customize.conversion import OutputFormatPlugin
from calibre import CurrentDir
from urllib import unquote

class OEBOutput(OutputFormatPlugin):

    name = 'OEB Output'
    author = 'Kovid Goyal'
    file_type = 'oeb'

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        self.log, self.opts = log, opts
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        from calibre.ebooks.oeb.base import OPF_MIME, NCX_MIME, PAGE_MAP_MIME
        with CurrentDir(output_path):
            results = oeb_book.to_opf2(page_map=True)
            for key in (OPF_MIME, NCX_MIME, PAGE_MAP_MIME):
                href, root = results.pop(key, [None, None])
                if root is not None:
                    raw = etree.tostring(root, pretty_print=True,
                            encoding='utf-8')
                    with open(href, 'wb') as f:
                        f.write('<?xml version="1.0" encoding="UTF-8" ?>\n')
                        f.write(raw)

            for item in oeb_book.manifest:
                path = os.path.abspath(unquote(item.href))
                dir = os.path.dirname(path)
                if not os.path.exists(dir):
                    os.makedirs(dir)
                with open(path, 'wb') as f:
                    f.write(str(item))


