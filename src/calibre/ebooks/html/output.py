from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re

from lxml import etree

from calibre.customize.conversion import OutputFormatPlugin
from calibre import CurrentDir
from calibre.customize.conversion import OptionRecommendation

from urllib import unquote

class HTMLOutput(OutputFormatPlugin):

    name = 'HTML Output'
    author = 'Fabian Grassl'
    file_type = 'html'

    recommendations = set([('pretty_print', True, OptionRecommendation.HIGH)])

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        self.log  = log
        self.opts = opts
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        with CurrentDir(output_path):
            with open('index.html', 'wb') as f:
                root = oeb_book.html_toc()
                html_txt = etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=False)
                f.write(html_txt)
            for item in oeb_book.manifest:
                log('write: %s '%item.href)
                path = os.path.abspath(unquote(item.href))
                dir = os.path.dirname(path)
                if not os.path.exists(dir):
                    os.makedirs(dir)
                with open(path, 'wb') as f:
                    f.write(str(item))
                item.unload_data_from_memory(memory=path)
