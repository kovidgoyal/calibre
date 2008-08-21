#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Conversion to EPUB.
'''
import sys
from calibre.utils.config import Config, StringConfig

def config(defaults=None):
    desc = _('Options to control the conversion to EPUB')
    if defaults is None:
        c = Config('epub', desc)
    else:
        c = StringConfig(defaults, desc)
        
    c.add_opt('output', ['-o', '--output'], default=None,
             help=_('The output EPUB file. If not specified, it is derived from the input file name.'))
    c.add_opt('encoding', ['--encoding'], default=None, 
              help=_('Character encoding for HTML files. Default is to auto detect.'))
    
    metadata = c.add_group('metadata', _('Set metadata of the generated ebook'))
    metadata('title', ['-t', '--title'], default=None,
             help=_('Set the title. Default is to autodetect.'))
    metadata('authors', ['-a', '--authors'], default=_('Unknown'),
             help=_('The author(s) of the ebook, as a comma separated list.'))
        
    traversal = c.add_group('traversal', _('Control the following of links in HTML files.'))
    traversal('breadth_first', ['--breadth-first'], default=False,
              help=_('Traverse links in HTML files breadth first. Normally, they are traversed depth first'))
    traversal('max_levels', ['--max-levels'], default=sys.getrecursionlimit(), group='traversal',
              help=_('Maximum levels of recursion when following links in HTML files. Must be non-negative. 0 implies that no links in the root HTML file are followed.'))
    
    structure = c.add_group('structure detection', _('Control auto-detection of document structure.'))
    structure('chapter', ['--chapter'], default="//*[re:match(name(), 'h[1-2]') and re:test(., 'chapter|book|section', 'i')]",
            help=_('''\
An XPath expression to detect chapter titles. The default is to consider <h1> or
<h2> tags that contain the text "chapter" or "book" or "section" as chapter titles. This
is achieved by the expression: "//*[re:match(name(), 'h[1-2]') and re:test(., 'chapter|book|section', 'i')]"
The expression used must evaluate to a list of elements. To disable chapter detection,
use the expression "/". 
''').replace('\n', ' '))
    structure('no_chapters_in_toc', ['--no-chapters-in-toc'], default=False,
              help=_('Don\'t add detected chapters to the Table of Contents'))
    structure('no_links_in_toc', ['--no-links-in-toc'], default=False,
              help=_('Don\'t add links in the root HTML file to the Table of Contents'))
    debug = c.add_group('debug', _('Options useful for debugging'))
    debug('verbose', ['-v', '--verbose'], default=0, action='count',
          help=_('Be more verbose while processing. Can be specified multiple times to increase verbosity.'))
    
    return c