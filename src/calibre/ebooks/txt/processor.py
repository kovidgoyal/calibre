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

def txt_to_markdown(txt, title=''):
    md = markdown.Markdown(
        extensions=['footnotes', 'tables', 'toc'],
        safe_mode=False,)
    html = u'<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/><title>%s</title></head><body>%s</body></html>' % (title,
        md.convert(txt))

    return html

def opf_writer(path, opf_name, manifest, spine, mi):
    opf = OPFCreator(path, mi)
    opf.create_manifest(manifest)
    opf.create_spine(spine)
    with open(os.path.join(path, opf_name), 'wb') as opffile:
        opf.render(opffile)

