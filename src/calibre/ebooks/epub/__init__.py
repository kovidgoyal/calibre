#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Conversion to EPUB.
'''
import sys
from calibre.utils.config import Config, StringConfig
from calibre.ebooks.html import config as common_config

def config(defaults=None):
    desc = _('Options to control the conversion to EPUB')
    if defaults is None:
        c = Config('epub', desc)
    else:
        c = StringConfig(defaults, desc)
    
    c.update(common_config())
    c.remove_opt('output')
    c.remove_opt('zip')
    
    c.add_opt('output', ['-o', '--output'], default=None,
             help=_('The output EPUB file. If not specified, it is derived from the input file name.'))
    
    structure = c.add_group('structure detection', _('Control auto-detection of document structure.'))
    structure('chapter', ['--chapter'], default="//*[re:match(name(), 'h[1-2]') and re:test(., 'chapter|book|section', 'i')]",
            help=_('''\
An XPath expression to detect chapter titles. The default is to consider <h1> or
<h2> tags that contain the text "chapter" or "book" or "section" as chapter titles. 
The expression used must evaluate to a list of elements. To disable chapter detection,
use the expression "/". See the XPath Tutorial in the calibre User Manual for further
help on using this feature.
''').replace('\n', ' '))
    structure('no_chapters_in_toc', ['--no-chapters-in-toc'], default=False,
              help=_('Don\'t add detected chapters to the Table of Contents'))
    structure('no_links_in_toc', ['--no-links-in-toc'], default=False,
              help=_('Don\'t add links in the root HTML file to the Table of Contents'))
    
    return c