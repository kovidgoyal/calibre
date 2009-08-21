#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from sphinx.builders.html import StandaloneHTMLBuilder

class EPUBHelpBuilder(StandaloneHTMLBuilder):
    """
    Builder that also outputs Qt help project, contents and index files.
    """
    name = 'epub'

    # don't copy the reST source
    copysource = False

    supported_image_types = ['image/svg+xml', 'image/png', 'image/gif',
                             'image/jpeg']

    # don't add links
    add_permalinks = False
    # don't add sidebar etc.
    embedded = True

    def init(self):
        StandaloneHTMLBuilder.init(self)
        # the output files for HTML help must be .html only
        self.out_suffix = '.xhtml'
        self.outdir = os.path.join(self.outdir, 'src')
        #self.config.html_style = 'traditional.css'

    def finish(self):
        StandaloneHTMLBuilder.finish(self)
        print 11111111
