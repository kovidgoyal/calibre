# -*- coding: utf-8 -*-

'''
Read content from txt file.
'''

import os
import re

from calibre import prepare_string_for_xml
from calibre.ebooks.markdown import markdown
from calibre.ebooks.metadata.opf2 import OPFCreator

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

HTML_TEMPLATE = u'<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/><title>%s</title></head><body>\n%s\n</body></html>'

def convert_basic(txt, title=''):
    lines = []
    # Strip whitespace from the beginning and end of the line. Also replace
    # all line breaks with \n.
    for line in txt.splitlines():
        lines.append(line.strip())
    txt = '\n'.join(lines)

    # Remove blank lines from the beginning and end of the document.
    txt = re.sub('^\s+(?=.)', '', txt)
    txt = re.sub('(?<=.)\s+$', '', txt)
    # Remove excessive line breaks.
    txt = re.sub('\n{3,}', '\n\n', txt)

    lines = []
    # Split into paragraphs based on having a blank line between text.
    for line in txt.split('\n\n'):
        if line.strip():
            lines.append('<p>%s</p>' % prepare_string_for_xml(line.replace('\n', ' ')))

    return HTML_TEMPLATE % (title, '\n'.join(lines))

def convert_markdown(txt, title='', disable_toc=False):
    md = markdown.Markdown(
          extensions=['footnotes', 'tables', 'toc'],
          extension_configs={"toc": {"disable_toc": disable_toc}},
          safe_mode=False)
    return HTML_TEMPLATE % (title, md.convert(txt))

def separate_paragraphs_single_line(txt):
    txt = txt.replace('\r\n', '\n')
    txt = txt.replace('\r', '\n')
    txt = re.sub(u'(?<=.)\n(?=.)', u'\n\n', txt)
    return txt

def separate_paragraphs_print_formatted(txt):
    txt = re.sub('(?miu)^(\t+|[ ]{2,})(?=.)', '\n\t', txt)
    return txt

def opf_writer(path, opf_name, manifest, spine, mi):
    opf = OPFCreator(path, mi)
    opf.create_manifest(manifest)
    opf.create_spine(spine)
    with open(os.path.join(path, opf_name), 'wb') as opffile:
        opf.render(opffile)

