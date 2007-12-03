##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
""" 
This package contains logic to read and write LRF files. 
The LRF file format is documented at U{http://www.sven.de/librie/Librie/LrfFormat}. 
"""
import sys, os
from optparse import OptionParser, OptionValueError
from htmlentitydefs import name2codepoint
from uuid import uuid4

from ttfquery import describe, findsystem
from fontTools.ttLib import TTLibError

from libprs500.ebooks.lrf.pylrs.pylrs import Book as _Book
from libprs500.ebooks.lrf.pylrs.pylrs import TextBlock, Header, PutObj, \
                                             Paragraph, TextStyle, BlockStyle
from libprs500.ebooks.lrf.fonts import FONT_FILE_MAP
from libprs500.ebooks import ConversionError
from libprs500 import __appname__, __version__, __author__
from libprs500 import iswindows

__docformat__ = "epytext"

class LRFParseError(Exception):
    pass


class PRS500_PROFILE(object):
    screen_width  = 600
    screen_height = 765
    dpi           = 166
    # Number of pixels to subtract from screen_height when calculating height of text area
    fudge         = 18
    font_size     = 10  #: Default (in pt)
    parindent     = 10  #: Default (in pt)
    line_space    = 1.2 #: Default (in pt)
    header_font_size = 6  #: In pt
    header_height    = 30 #: In px
    default_fonts    = { 'sans': "Swis721 BT Roman", 'mono': "Courier10 BT Roman",
                         'serif': "Dutch801 Rm BT Roman"}
    
    name = 'prs500' 
    
class PRS500_PROFILE_UNSAFE(PRS500_PROFILE):
    fudge = 0
    name = 'prs500-unsafe'
    
    
profile_map = {
               PRS500_PROFILE.name : PRS500_PROFILE,
               PRS500_PROFILE_UNSAFE.name : PRS500_PROFILE_UNSAFE,
               }
    
def profile_from_string(option, opt_str, value, parser):
    try:
        profile = profile_map[value]
        setattr(parser.values, option.dest, profile)
    except KeyError:
        raise OptionValueError('Profile: '+value+' is not implemented. Implemented profiles: %s'%(profile_map.keys()))
    
def font_family(option, opt_str, value, parser):
    if value:
        value = value.split(',')
        if len(value) != 2:
            raise OptionValueError('Font family specification must be of the form'+\
                                   ' "path to font directory, font family"')
        path, family = tuple(value)
        if not os.path.isdir(path) or not os.access(path, os.R_OK|os.X_OK):
            raise OptionValueError('Cannot read from ' + path)
        setattr(parser.values, option.dest, (path, family))
    else:
        setattr(parser.values, option.dest, tuple())
            
    
def option_parser(usage):
    parser = OptionParser(usage=usage, version=__appname__+' '+__version__,
                          epilog=_('Created by ')+__author__)
    metadata = parser.add_option_group('METADATA OPTIONS')
    metadata.add_option("-t", "--title", action="store", type="string", default=None,\
                    dest="title", help=_("Set the title. Default: filename."))
    metadata.add_option("-a", "--author", action="store", type="string", \
                    dest="author", help=_("Set the author(s). Multiple authors should be set as a comma separated list. Default: %default"), 
                    default=_('Unknown'))
    metadata.add_option("--comment", action="store", type="string", \
                    dest="freetext", help=_("Set the comment."), default='  ')
    metadata.add_option("--category", action="store", type="string", \
                    dest="category", help=_("Set the category"), default='  ')    
    metadata.add_option('--title-sort', action='store', default='', dest='title_sort',
                      help=_('Sort key for the title'))
    metadata.add_option('--author-sort', action='store', default='', dest='author_sort',
                      help=_('Sort key for the author'))
    metadata.add_option('--publisher', action='store', default='Unknown', dest='publisher',
                      help=_('Publisher'))
    metadata.add_option('--cover', action='store', dest='cover', default=None, \
                        help=_('Path to file containing image to be used as cover'))
    metadata.add_option('--use-metadata-cover', action='store_true', default=False, 
                        help=_('If there is a cover graphic detected in the source file, use that instead of the specified cover.'))
     
    parser.add_option('-o', '--output', action='store', default=None, \
                      help=_('Output file name. Default is derived from input filename'))
    parser.add_option('--ignore-tables', action='store_true', default=False, dest='ignore_tables',
                      help=_('Render HTML tables as blocks of text instead of actual tables. This is neccessary if the HTML contains very large or complex tables.'))
    laf = parser.add_option_group('LOOK AND FEEL')
    laf.add_option('--base-font-size', action='store', type='float', default=10.,
                   help=_('''Specify the base font size in pts. All fonts are rescaled accordingly. This option obsoletes the --font-delta option and takes precedence over it. To use --font-delta, set this to 0.'''))
    laf.add_option('--enable-autorotation', action='store_true', default=False, 
                   help=_('Enable autorotation of images that are wider than the screen width.'), 
                   dest='autorotation')
    laf.add_option('--wordspace', dest='wordspace', default=2.5, type='float',
                   help=_('Set the space between words in pts. Default is %default'))
    laf.add_option('--blank-after-para', action='store_true', default=False,
                   dest='blank_after_para', help=_('Separate paragraphs by blank lines.'))
    laf.add_option('--header', action='store_true', default=False, dest='header',
                      help=_('Add a header to all the pages with title and author.'))
    laf.add_option('--headerformat', default="%t by %a", dest='headerformat', type='string',
                        help=_('Set the format of the header. %a is replaced by the author and %t by the title. Default is %default'))
    laf.add_option('--override-css', default=None, dest='_override_css', type='string',
                   help=_('Override the CSS. Can be either a path to a CSS stylesheet or a string. If it is a string it is interpreted as CSS.'))
    laf.add_option('--use-spine', default=False, dest='use_spine', action='store_true',
                   help=_('Use the <spine> element from the OPF file to determine the order in which the HTML files are appended to the LRF. The .opf file must be in the same directory as the base HTML file.'))
    laf.add_option('--font-delta', action='store', type='float', default=0., \
                  help=_("""Increase the font size by 2 * FONT_DELTA pts and """
                  '''the line spacing by FONT_DELTA pts. FONT_DELTA can be a fraction.'''
                  """If FONT_DELTA is negative, the font size is decreased."""),
                  dest='font_delta')

    
    page = parser.add_option_group('PAGE OPTIONS')
    profiles = profile_map.keys()
    page.add_option('-p', '--profile', default=PRS500_PROFILE, dest='profile', type='choice',
                      choices=profiles, action='callback', callback=profile_from_string,
                      help=_('''Profile of the target device for which this LRF is '''
                      '''being generated. The profile determines things like the '''
                      '''resolution and screen size of the target device. '''
                      '''Default: %s Supported profiles: ''')%(PRS500_PROFILE.name,)+\
                      ', '.join(profiles))
    page.add_option('--left-margin', default=20, dest='left_margin', type='int',
                    help=_('''Left margin of page. Default is %default px.'''))
    page.add_option('--right-margin', default=20, dest='right_margin', type='int',
                    help=_('''Right margin of page. Default is %default px.'''))
    page.add_option('--top-margin', default=10, dest='top_margin', type='int',
                    help=_('''Top margin of page. Default is %default px.'''))
    page.add_option('--bottom-margin', default=0, dest='bottom_margin', type='int',
                    help=_('''Bottom margin of page. Default is %default px.'''))
    link = parser.add_option_group('LINK PROCESSING OPTIONS')
    link.add_option('--link-levels', action='store', type='int', default=sys.maxint, \
                      dest='link_levels',
                      help=_(r'''The maximum number of levels to recursively process '''
                              '''links. A value of 0 means thats links are not followed. '''
                              '''A negative value means that <a> tags are ignored.'''))
    link.add_option('--link-exclude', dest='link_exclude', default='@',
                      help=_('''A regular expression. <a> tags whoose href '''
                      '''matches will be ignored. Defaults to %default'''))
    chapter = parser.add_option_group('CHAPTER OPTIONS')
    chapter.add_option('--disable-chapter-detection', action='store_true', 
                      default=False, dest='disable_chapter_detection', 
                      help=_('''Prevent the automatic insertion of page breaks'''
                      ''' before detected chapters.'''))
    chapter.add_option('--chapter-regex', dest='chapter_regex', 
                      default='chapter|book|appendix',
                      help=_('''The regular expression used to detect chapter titles.'''
                      ''' It is searched for in heading tags (h1-h6). Defaults to %default'''))     
    chapter.add_option('--page-break-before-tag', dest='page_break', default='h[12]',
                      help=_('''If html2lrf does not find any page breaks in the '''
                      '''html file and cannot detect chapter headings, it will '''
                      '''automatically insert page-breaks before the tags whose '''
                      '''names match this regular expression. Defaults to %default. '''
                      '''You can disable it by setting the regexp to "$". '''
                      '''The purpose of this option is to try to ensure that '''
                      '''there are no really long pages as this degrades the page '''
                      '''turn performance of the LRF. Thus this option is ignored '''
                      '''if the current page has only a few elements.'''))
    chapter.add_option('--force-page-break-before-tag', dest='force_page_break',
                       default='$', help=_('Force a page break before tags whoose names match this regular expression.'))
    chapter.add_option('--force-page-break-before-attr', dest='force_page_break_attr',
                       default='$,,$', help=_('Force a page break before an element having the specified attribute. The format for this option is tagname regexp,attribute name,attribute value regexp. For example to match all heading tags that have the attribute class="chapter" you would use "h\d,class,chapter". Default is %default'''))
    prepro = parser.add_option_group('PREPROCESSING OPTIONS')
    prepro.add_option('--baen', action='store_true', default=False, dest='baen',
                      help=_('''Preprocess Baen HTML files to improve generated LRF.'''))
    prepro.add_option('--pdftohtml', action='store_true', default=False, dest='pdftohtml',
                      help=_('''You must add this option if processing files generated by pdftohtml, otherwise conversion will fail.'''))
    prepro.add_option('--book-designer', action='store_true', default=False, dest='book_designer',
                      help=_('''Use this option on html0 files from Book Designer.'''))
    
    fonts = parser.add_option_group('FONT FAMILIES', 
    _('''Specify trutype font families for serif, sans-serif and monospace fonts. '''
    '''These fonts will be embedded in the LRF file. Note that custom fonts lead to '''
    '''slower page turns. Each family specification is of the form: '''
    '''"path to fonts directory, family" '''
    '''For example: '''
    '''--serif-family "%s, Times New Roman"
    ''') % ('C:\Windows\Fonts' if iswindows else '/usr/share/fonts/corefonts'))
    fonts.add_option('--serif-family', action='callback', callback=font_family, 
                     default=None, dest='serif_family', type='string',
                     help=_('The serif family of fonts to embed'))
    fonts.add_option('--sans-family',  action='callback', callback=font_family, 
                     default=None, dest='sans_family', type='string',
                     help=_('The sans-serif family of fonts to embed'))
    fonts.add_option('--mono-family',  action='callback', callback=font_family, 
                     default=None, dest='mono_family', type='string',
                     help=_('The monospace family of fonts to embed'))
    
    debug = parser.add_option_group('DEBUG OPTIONS')
    debug.add_option('--verbose', dest='verbose', action='store_true', default=False,
                      help='''Be verbose while processing''')
    debug.add_option('--lrs', action='store_true', dest='lrs', \
                      help='Convert to LRS', default=False)
    parser.add_option('--minimize-memory-usage', action='store_true', default=False,
                      help=_('Minimize memory usage at the cost of longer processing times. Use this option if you are on a memory constrained machine.'))
    return parser

def find_custom_fonts(options, logger):
    fonts = {'serif' : None, 'sans' : None, 'mono' : None}
    def find_family(option):
        path, family = option
        paths = findsystem.findFonts([path])
        results = {}
        for path in paths:
            if len(results.keys()) == 4:
                break
            f = describe.openFont(path)
            name, cfamily = describe.shortName(f)
            if cfamily.lower().strip() != family.lower().strip():
                continue
            try:
                wt, italic = describe.modifiers(f)
            except TTLibError:
                logger.exception('Could not process fonts in %s', path)
                wt, italic = 0, 0
            result = (path, name)
            if wt == 400 and italic == 0:
                results['normal'] = result
            elif wt == 400 and italic > 0:
                results['italic'] = result
            elif wt >= 700 and italic == 0:
                results['bold'] = result
            elif wt >= 700 and italic > 0:
                results['bi'] = result
        return results
    if options.serif_family:
        fonts['serif'] = find_family(options.serif_family)
        if not fonts['serif']:
            logger.warn('Unable to find serif family %s in %s'%(options.serif_family[1].strip(), options.serif_family[0]))
    if options.sans_family:
        fonts['sans'] = find_family(options.sans_family)
        if not fonts['sans']:
            logger.warn('Unable to find sans family %s in %s'%(options.sans_family[1].strip(), options.sans_family[0]))        
    if options.mono_family:
        fonts['mono'] = find_family(options.mono_family)
        if not fonts['mono']:
            logger.warn('Unable to find mono family %s in %s'%(options.mono_family[1].strip(), options.mono_family[0]))        
    return fonts
    
        
def Book(options, logger, font_delta=0, header=None, 
         profile=PRS500_PROFILE, **settings):
    ps = {}
    ps['topmargin']      = options.top_margin
    ps['evensidemargin'] = options.left_margin
    ps['oddsidemargin']  = options.left_margin
    ps['textwidth']      = profile.screen_width - (options.left_margin + options.right_margin)
    ps['textheight']     = profile.screen_height - (options.top_margin + options.bottom_margin) - profile.fudge
    if header:
        hdr = Header()
        hb = TextBlock(textStyle=TextStyle(align='foot', 
                                           fontsize=int(profile.header_font_size*10)),
                       blockStyle=BlockStyle(blockwidth=ps['textwidth']))
        hb.append(header)
        hdr.PutObj(hb)
        ps['headheight'] = profile.header_height
        ps['header']     = hdr
        ps['topmargin']  = 0
        ps['textheight'] = profile.screen_height - (options.bottom_margin + ps['topmargin'] + ps['headheight'] + profile.fudge)
    fontsize = int(10*profile.font_size+font_delta*20)
    baselineskip = fontsize + 20
    fonts = find_custom_fonts(options, logger)
    tsd = dict(fontsize=fontsize, 
               parindent=int(10*profile.parindent), 
               linespace=int(10*profile.line_space),
               baselineskip=baselineskip,
               wordspace=10*options.wordspace)
    if fonts['serif'] and fonts['serif'].has_key('normal'):
        tsd['fontfacename'] = fonts['serif']['normal'][1]
    
    book = _Book(textstyledefault=tsd, 
                pagestyledefault=ps, 
                blockstyledefault=dict(blockwidth=ps['textwidth']),
                bookid=uuid4().hex,
                **settings)
    for family in fonts.keys():
        if fonts[family]:
            for font in fonts[family].values():
                book.embed_font(*font)
                FONT_FILE_MAP[font[1]] = font[0]
    
    for family in ['serif', 'sans', 'mono']:
        if not fonts[family]:
            fonts[family] = { 'normal' : (None, profile.default_fonts[family]) }
        elif not fonts[family].has_key('normal'):
            raise ConversionError, 'Could not find the normal version of the ' + family + ' font'
    return book, fonts

def entity_to_unicode(match, exceptions=[]):
    ent = match.group(1)
    if ent in exceptions:
        return '&'+ent+';'
    if ent.startswith(u'#x'):
        return unichr(int(ent[2:], 16))
    if ent.startswith(u'#'):
        return unichr(int(ent[1:]))
    try:
        return unichr(name2codepoint[ent])
    except KeyError:
        return '&'+ent+';'
