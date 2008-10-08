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
from calibre.ebooks.html import config as common_config, tostring

class DefaultProfile(object):
    
    flow_size   = sys.maxint
    screen_size = None
    remove_soft_hyphens = False
    
class PRS505(DefaultProfile):
    
    flow_size   = 300000
    screen_size = (600, 775)
    remove_soft_hyphens = True
        

PROFILES = {
            'PRS505' : PRS505,
            'None'   : DefaultProfile,
            }

def rules(stylesheets):
    for s in stylesheets:
        if hasattr(s, 'cssText'):
            for r in s:
                if r.type == r.STYLE_RULE:
                    yield r

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
    c.add_opt('profile', ['--profile'], default='PRS505', choices=list(PROFILES.keys()),
              help=_('Profile of the target device this EPUB is meant for. Set to None to create a device independent EPUB. The profile is used for device specific restrictions on the EPUB. Choices are: ')+str(list(PROFILES.keys())))
    c.add_opt('override_css', ['--override-css'], default=None,
              help=_('Either the path to a CSS stylesheet or raw CSS. This CSS will override any existing CSS declarations in the source files.'))
    structure = c.add_group('structure detection', _('Control auto-detection of document structure.'))
    structure('chapter', ['--chapter'], default="//*[re:match(name(), 'h[1-2]') and re:test(., 'chapter|book|section|part', 'i')] | //*[@class = 'chapter']",
            help=_('''\
An XPath expression to detect chapter titles. The default is to consider <h1> or
<h2> tags that contain the words "chapter","book","section" or "part" as chapter titles as 
well as any tags that have class="chapter". 
The expression used must evaluate to a list of elements. To disable chapter detection,
use the expression "/". See the XPath Tutorial in the calibre User Manual for further
help on using this feature.
''').replace('\n', ' '))
    structure('chapter_mark', ['--chapter-mark'], choices=['pagebreak', 'rule', 'both', 'none'],
              default='pagebreak', help=_('Specify how to mark detected chapters. A value of "pagebreak" will insert page breaks before chapters. A value of "rule" will insert a line before chapters. A value of "none" will disable chapter marking and a value of "both" will use both page breaks and lines to mark chapters.'))
    structure('cover', ['--cover'], default=None,
              help=_('Path to the cover to be used for this book'))
    structure('prefer_metadata_cover', ['--prefer-metadata-cover'], default=False,
              action='store_true',
              help=_('Use the cover detected from the source file in preference to the specified cover.'))
    
    toc = c.add_group('toc', 
        _('''\
Control the automatic generation of a Table of Contents. If an OPF file is detected
and it specifies a Table of Contents, then that will be used rather than trying
to auto-generate a Table of Contents.
''').replace('\n', ' '))
    toc('max_toc_links', ['--max-toc-links'], default=50, 
        help=_('Maximum number of links to insert into the TOC. Set to 0 to disable. Default is: %default. Links are only added to the TOC if less than the --toc-threshold number of chapters were detected.'))
    toc('no_chapters_in_toc', ['--no-chapters-in-toc'], default=False,
        help=_("Don't add auto-detected chapters to the Table of Contents."))
    toc('toc_threshold', ['--toc-threshold'], default=6,
        help=_('If fewer than this number of chapters is detected, then links are added to the Table of Contents.'))
    toc('level1_toc', ['--level1-toc'], default=None,
        help=_('XPath expression that specifies all tags that should be added to the Table of Contents at level one. If this is specified, it takes precedence over other forms of auto-detection.'))
    toc('level2_toc', ['--level2-toc'], default=None,
        help=_('XPath expression that specifies all tags that should be added to the Table of Contents at level two. Each entry is added under the previous level one entry.'))
    toc('from_ncx', ['--from-ncx'], default=None,
        help=_('Path to a .ncx file that contains the table of contents to use for this ebook. The NCX file should contain links relative to the directory it is placed in. See http://www.niso.org/workrooms/daisy/Z39-86-2005.html#NCX for an overview of the NCX format.'))
    toc('use_auto_toc', ['--use-auto-toc'], default=False,
        help=_('Normally, if the source file already has a Table of Contents, it is used in preference to the autodetected one. With this option, the autodetected one is always used.'))
    
    layout = c.add_group('page layout', _('Control page layout'))
    layout('margin_top', ['--margin-top'], default=5.0, 
           help=_('Set the top margin in pts. Default is %default'))
    layout('margin_bottom', ['--margin-bottom'], default=5.0, 
           help=_('Set the bottom margin in pts. Default is %default'))
    layout('margin_left', ['--margin-left'], default=5.0, 
           help=_('Set the left margin in pts. Default is %default'))
    layout('margin_right', ['--margin-right'], default=5.0, 
           help=_('Set the right margin in pts. Default is %default'))
    layout('base_font_size2', ['--base-font-size'], default=12.0,
           help=_('The base font size in pts. Default is %defaultpt. Set to 0 to disable rescaling of fonts.'))
    layout('remove_paragraph_spacing', ['--remove-paragraph-spacing'], default=True,
           help=_('Remove spacing between paragraphs. Will not work if the source file forces inter-paragraph spacing.'))
    layout('preserve_tag_structure', ['--preserve-tag-structure'], default=False,
           help=_('Preserve the HTML tag structure while splitting large HTML files. This is only neccessary if the HTML files contain CSS that uses sibling selectors. Enabling this greatly slows down processing of large HTML files.'))
    
    c.add_opt('show_opf', ['--show-opf'], default=False, group='debug',
              help=_('Print generated OPF file to stdout'))
    c.add_opt('show_ncx', ['--show-ncx'], default=False, group='debug',
              help=_('Print generated NCX file to stdout'))
    c.add_opt('keep_intermediate', ['--keep-intermediate-files'], group='debug', default=False,
              help=_('Keep intermediate files during processing by html2epub'))
    c.add_opt('extract_to', ['--extract-to'], group='debug', default=None,
              help=_('Extract the contents of the produced EPUB file to the specified directory.'))
    return c