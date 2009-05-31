# -*- coding: utf-8 -*-

'''
Read content from txt file.
'''

import os

from calibre.ebooks.markdown import markdown
from calibre.ebooks.metadata.opf2 import OPFCreator

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

def txt_to_markdown(txt):
    md = markdown.Markdown(
        extensions=['footnotes', 'tables', 'toc'],
        safe_mode=False,)
    html = '<html><head><title /></head><body>'+md.convert(txt)+'</body></html>'
    
    return html

def opf_writer(path, opf_name, manifest, spine, mi):
    opf = OPFCreator(path, mi)
    opf.create_manifest(manifest)
    opf.create_spine(spine)
    with open(os.path.join(path, opf_name), 'wb') as opffile:
        opf.render(opffile)

