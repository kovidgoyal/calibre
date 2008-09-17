#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Conversion to EPUB.
'''
import sys, textwrap
from calibre.utils.config import Config, StringConfig
from calibre.utils.zipfile import ZipFile, ZIP_STORED
from calibre.ebooks.html import config as common_config

def initialize_container(path_to_container, opf_name='metadata.opf'):
    '''
    Create an empty EPUB document, with a default skeleton.
    '''
    CONTAINER='''\
<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
   <rootfiles>
      <rootfile full-path="%s" media-type="application/oebps-package+xml"/>
   </rootfiles>
</container>
    '''%opf_name
    zf = ZipFile(path_to_container, 'w')
    zf.writestr('mimetype', 'application/epub+zip', compression=ZIP_STORED)
    zf.writestr('META-INF/', '', 0700)
    zf.writestr('META-INF/container.xml', CONTAINER)
    return zf
    

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
    structure('chapter_mark', ['--chapter-mark'], choices=['pagebreak', 'rule', 'both'],
              default='pagebreak', help=_('Specify how to mark detected chapters. A value of "pagebreak" will insert page breaks before chapters. A value of "rule" will insert a line before chapters. A value of "none" will disable chapter marking and a value of "both" will use both page breaks and lines to mark chapters.'))
    
    toc = c.add_group('toc', 
        _('''\
Control the automatic generation of a Table of Contents. If an OPF file is detected
and it specifies a Table of Contents, then that will be used rather than trying
to auto-generate a Table of Contents.
''').replace('\n', ' '))
    toc('max_toc_recursion', ['--max-toc-recursion'], default=1, 
        help=_('Number of levels of HTML files to try to autodetect TOC entries from. Set to 0 to disable all TOC autodetection. Default is %default.'))
    toc('max_toc_links', ['--max-toc-links'], default=40, 
        help=_('Maximum number of links from each HTML file to insert into the TOC. Set to 0 to disable. Default is: %default.'))
    toc('no_chapters_in_toc', ['--no-chapters-in-toc'], default=False,
        help=_("Don't add auto-detected chapters to the Table of Contents."))
    
    c.add_opt('show_opf', ['--show-opf'], default=False, group='debug',
              help=_('Print generated OPF file to stdout'))
    c.add_opt('show_ncx', ['--show-ncx'], default=False, group='debug',
              help=_('Print generated NCX file to stdout'))
    
    return c