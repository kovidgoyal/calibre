#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, os

from lxml import html
from lxml.html.builder import (HTML, HEAD, TITLE, BODY, LINK, META)

from calibre.ebooks.docx.container import Container

class Convert(object):

    def __init__(self, path_or_stream, dest_dir=None, log=None):
        self.container = Container(path_or_stream, log=log)
        self.log = self.container.log
        self.dest_dir = dest_dir or os.getcwdu()
        self.body = BODY()
        self.html = HTML(
            HEAD(
                META(charset='utf-8'),
                TITLE('TODO: read from metadata'),
                LINK(rel='stylesheet', type='text/css', href='docx.css'),
            ),
            self.body
        )

    def __call__(self):
        self.write()

    def write(self):
        raw = html.tostring(self.html, encoding='utf-8', doctype='<!DOCTYPE html>')
        with open(os.path.join(self.dest_dir, 'index.html'), 'wb') as f:
            f.write(raw)

if __name__ == '__main__':
    Convert(sys.argv[-1])()
