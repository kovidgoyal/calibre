#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re

from calibre.customize.ui import available_input_formats

def is_supported(path):
    ext = os.path.splitext(path)[1].replace('.', '').lower()
    ext = re.sub(r'(x{0,1})htm(l{0,1})', 'html', ext)
    return ext in available_input_formats()

class UnsupportedFormatError(Exception):

    def __init__(self, fmt):
        Exception.__init__(self, _('%s format books are not supported')%fmt.upper())

def EbookIterator(*args, **kwargs):
    'For backwards compatibility'
    from calibre.ebooks.oeb.iterator.book import EbookIterator
    return EbookIterator(*args, **kwargs)

def get_preprocess_html(path_to_ebook, output):
    from calibre.ebooks.conversion.preprocess import HTMLPreProcessor
    iterator = EbookIterator(path_to_ebook)
    iterator.__enter__(only_input_plugin=True, run_char_count=False,
            read_anchor_map=False)
    preprocessor = HTMLPreProcessor(None, False)
    with open(output, 'wb') as out:
        for path in iterator.spine:
            with open(path, 'rb') as f:
                html = f.read().decode('utf-8', 'replace')
            html = preprocessor(html, get_preprocess_html=True)
            out.write(html.encode('utf-8'))
            out.write(b'\n\n' + b'-'*80 + b'\n\n')

