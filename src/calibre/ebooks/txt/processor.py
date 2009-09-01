# -*- coding: utf-8 -*-

'''
Read content from txt file.
'''

import os
import re

from calibre.ebooks.markdown import markdown
from calibre.ebooks.metadata.opf2 import OPFCreator

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

HTML_TEMPLATE = u'<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/><title>%s</title></head><body>%s</body></html>'

def convert_basic(txt, title=''):
    lines = []
    for line in txt.splitlines():
        lines.append('<p>%s</p>' % line)
    return HTML_TEMPLATE % (title, '\n'.join(lines))

def convert_markdown(txt, title=''):
    md = markdown.Markdown(
        extensions=['footnotes', 'tables', 'toc'],
        safe_mode=False,)
    return HTML_TEMPLATE % (title, md.convert(txt))

def separate_paragraphs(txt):
    txt = txt.replace('\r\n', '\n')
    txt = txt.replace('\r', '\n')
    txt = re.sub(u'(?<=.)\n(?=.)', u'\n\n', txt)
    return txt

def opf_writer(path, opf_name, manifest, spine, mi):
    opf = OPFCreator(path, mi)
    opf.create_manifest(manifest)
    opf.create_spine(spine)
    with open(os.path.join(path, opf_name), 'wb') as opffile:
        opf.render(opffile)

