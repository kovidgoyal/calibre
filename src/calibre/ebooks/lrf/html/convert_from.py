# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>


import copy
import glob
import os
import re
import sys
import tempfile
from collections import deque
from functools import partial
from itertools import chain
from math import ceil, floor

from calibre import (
    __appname__, entity_to_unicode, fit_image, force_unicode, preferred_encoding
)
from calibre.constants import filesystem_encoding
from calibre.devices.interface import DevicePlugin as Device
from calibre.ebooks import ConversionError
from calibre.ebooks.BeautifulSoup import (
    BeautifulSoup, Comment, Declaration, NavigableString, ProcessingInstruction, Tag
)
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.lrf import Book
from calibre.ebooks.lrf.html.color_map import lrs_color
from calibre.ebooks.lrf.html.table import Table
from calibre.ebooks.lrf.pylrs.pylrs import (
    CR, BlockSpace, BookSetting, Canvas, CharButton, DropCaps, EmpLine, Image,
    ImageBlock, ImageStream, Italic, JumpButton, LrsError, Paragraph, Plot,
    RuledLine, Span, Sub, Sup, TextBlock
)
from calibre.ptempfile import PersistentTemporaryFile
from polyglot.builtins import itervalues, string_or_bytes
from polyglot.urllib import unquote, urlparse

"""
Code to convert HTML ebooks into LRF ebooks.

I am indebted to esperanc for the initial CSS->Xylog Style conversion code
and to Falstaff for pylrs.
"""

from PIL import Image as PILImage


def update_css(ncss, ocss):
    for key in ncss.keys():
        if key in ocss:
            ocss[key].update(ncss[key])
        else:
            ocss[key] = ncss[key]


def munge_paths(basepath, url):
    purl = urlparse(unquote(url),)
    path, fragment = purl[2], purl[5]
    if path:
        path = path.replace('/', os.sep)
    if not path:
        path = basepath
    elif not os.path.isabs(path):
        dn = os.path.dirname(basepath)
        path = os.path.join(dn, path)
    return os.path.normpath(path), fragment


def strip_style_comments(match):
    src = match.group()
    while True:
        lindex = src.find('/*')
        if lindex < 0:
            break
        rindex = src.find('*/', lindex)
        if rindex < 0:
            src = src[:lindex]
            break
        src = src[:lindex] + src[rindex+2:]
    return src


def tag_regex(tagname):
    '''Return non-grouping regular expressions that match the opening and closing tags for tagname'''
    return dict(open=r'(?:<\s*%(t)s\s+[^<>]*?>|<\s*%(t)s\s*>)'%dict(t=tagname),
                close=r'</\s*%(t)s\s*>'%dict(t=tagname))


class HTMLConverter:
    SELECTOR_PAT   = re.compile(r"([A-Za-z0-9\-\_\:\.]+[A-Za-z0-9\-\_\:\.\s\,]*)\s*\{([^\}]*)\}")
    PAGE_BREAK_PAT = re.compile(r'page-break-(?:after|before)\s*:\s*(\w+)', re.IGNORECASE)
    IGNORED_TAGS   = (Comment, Declaration, ProcessingInstruction)

    MARKUP_MASSAGE   = [
                        # Close <a /> tags
                        (re.compile(r'<a(\s[^>]*)?/>', re.IGNORECASE),
                         lambda match: '<a'+match.group(1)+'></a>'),
                        # Strip comments from <style> tags. This is needed as
                        # sometimes there are unterminated comments
                        (re.compile(r"<\s*style.*?>(.*?)<\/\s*style\s*>", re.DOTALL|re.IGNORECASE),
                         lambda match: match.group().replace('<!--', '').replace('-->', '')),
                        # remove <p> tags from within <a href> tags
                        (re.compile(r'<\s*a\s+[^<>]*href\s*=[^<>]*>(.*?)<\s*/\s*a\s*>', re.DOTALL|re.IGNORECASE),
                         lambda match: re.compile(r'%(open)s|%(close)s'%tag_regex('p'), re.IGNORECASE).sub('', match.group())),

                        # Replace common line break patterns with line breaks
                        (re.compile(r'<p>(&nbsp;|\s)*</p>', re.IGNORECASE), lambda m: '<br />'),

                        # Replace empty headers with line breaks
                        (re.compile(r'<h[0-5]?>(&nbsp;|\s)*</h[0-5]?>',
                                    re.IGNORECASE), lambda m: '<br />'),

                        # Replace entities
                        (re.compile(r'&(\S+?);'), partial(entity_to_unicode,
                                                           exceptions=['lt', 'gt', 'amp', 'quot'])),
                        # Remove comments from within style tags as they can mess up BeatifulSoup
                        (re.compile(r'(<style.*?</style>)', re.IGNORECASE|re.DOTALL),
                         strip_style_comments),

                        # Remove self closing script tags as they also mess up BeautifulSoup
                        (re.compile(r'(?i)<script[^<>]+?/>'), lambda match: ''),

                        # BeautifulSoup treats self closing <div> tags as open <div> tags
                        (re.compile(r'(?i)<\s*div([^>]*)/\s*>'),
                         lambda match: '<div%s></div>'%match.group(1))

                        ]
    # Fix Baen markup
    BAEN = [
                     (re.compile(r'page-break-before:\s*\w+([\s;\}])', re.IGNORECASE),
                      lambda match: match.group(1)),
                     (re.compile(r'<p>\s*(<a id.*?>\s*</a>)\s*</p>', re.IGNORECASE),
                      lambda match: match.group(1)),
                     (re.compile(r'<\s*a\s+id="p[0-9]+"\s+name="p[0-9]+"\s*>\s*</a>', re.IGNORECASE),
                      lambda match: ''),
                     ]
    # Fix pdftohtml markup
    PDFTOHTML  = [
                  # Remove <hr> tags
                  (re.compile(r'<hr.*?>', re.IGNORECASE), lambda match: '<br />'),
                  # Remove page numbers
                  (re.compile(r'\d+<br>', re.IGNORECASE), lambda match: ''),
                  # Remove <br> and replace <br><br> with <p>
                  (re.compile(r'<br.*?>\s*<br.*?>', re.IGNORECASE), lambda match: '<p>'),
                  (re.compile(r'(.*)<br.*?>', re.IGNORECASE),
                   lambda match: match.group() if re.match('<', match.group(1).lstrip()) or len(match.group(1)) < 40
                                else match.group(1)),
                  # Remove hyphenation
                  (re.compile(r'-\n\r?'), lambda match: ''),

                  ]

    # Fix Book Designer markup
    BOOK_DESIGNER = [
                     # HR
                     (re.compile('<hr>', re.IGNORECASE),
                      lambda match : '<span style="page-break-after:always"> </span>'),
                     # Create header tags
                     (re.compile(r'<h2[^><]*?id=BookTitle[^><]*?(align=)*(?(1)(\w+))*[^><]*?>[^><]*?</h2>', re.IGNORECASE),
                      lambda match : '<h1 id="BookTitle" align="%s">%s</h1>'%(match.group(2) if match.group(2) else 'center', match.group(3))),
                     (re.compile(r'<h2[^><]*?id=BookAuthor[^><]*?(align=)*(?(1)(\w+))*[^><]*?>[^><]*?</h2>', re.IGNORECASE),
                      lambda match : '<h2 id="BookAuthor" align="%s">%s</h2>'%(match.group(2) if match.group(2) else 'center', match.group(3))),
                     (re.compile(r'<span[^><]*?id=title[^><]*?>(.*?)</span>', re.IGNORECASE|re.DOTALL),
                      lambda match : '<h2 class="title">%s</h2>'%(match.group(1),)),
                     (re.compile(r'<span[^><]*?id=subtitle[^><]*?>(.*?)</span>', re.IGNORECASE|re.DOTALL),
                      lambda match : '<h3 class="subtitle">%s</h3>'%(match.group(1),)),
                     # Blank lines
                     (re.compile(r'<div[^><]*?>(&nbsp;){4}</div>', re.IGNORECASE),
                      lambda match : '<p></p>'),
                     ]

    def __hasattr__(self, attr):
        if hasattr(self.options, attr):
            return True
        return object.__hasattr__(self, attr)

    def __getattr__(self, attr):
        if hasattr(self.options, attr):
            return getattr(self.options, attr)
        return object.__getattribute__(self, attr)

    def __setattr__(self, attr, val):
        if hasattr(self.options, attr):
            setattr(self.options, attr, val)
        else:
            object.__setattr__(self, attr, val)

    CSS = {
           'h1'     : {"font-size"   : "xx-large", "font-weight":"bold", 'text-indent':'0pt'},
           'h2'     : {"font-size"   : "x-large", "font-weight":"bold", 'text-indent':'0pt'},
           'h3'     : {"font-size"   : "large", "font-weight":"bold", 'text-indent':'0pt'},
           'h4'     : {"font-size"   : "large", 'text-indent':'0pt'},
           'h5'     : {"font-weight" : "bold", 'text-indent':'0pt'},
           'b'      : {"font-weight" : "bold"},
           'strong' : {"font-weight" : "bold"},
           'i'      : {"font-style"  : "italic"},
           'cite'   : {'font-style'  : 'italic'},
           'em'     : {"font-style"  : "italic"},
           'small'  : {'font-size'   : 'small'},
           'pre'    : {'font-family' : 'monospace', 'white-space': 'pre'},
           'code'   : {'font-family' : 'monospace'},
           'tt'     : {'font-family' : 'monospace'},
           'center' : {'text-align'  : 'center'},
           'th'     : {'font-size'   : 'large', 'font-weight':'bold'},
           'big'    : {'font-size'   : 'large', 'font-weight':'bold'},
           '.libprs500_dropcaps' : {'font-size': 'xx-large'},
           'u'      : {'text-decoration': 'underline'},
           'sup'    : {'vertical-align': 'super', 'font-size': '60%'},
           'sub'    : {'vertical-align': 'sub', 'font-size': '60%'},
           }

    def __init__(self, book, fonts, options, logger, paths):
        '''
        Convert HTML files at C{paths} and add to C{book}. After creating
        the object, you must call L{self.writeto} to output the LRF/S file.

        @param book: The LRF book
        @type book:  L{lrf.pylrs.Book}
        @param fonts: dict specifying the font families to use
        '''
        # Defaults for various formatting tags
        object.__setattr__(self, 'options', options)
        self.log = logger
        self.fonts = fonts  # : dict specifying font families to use
        # Memory
        self.scaled_images    = {}    #: Temporary files with scaled version of images
        self.rotated_images   = {}    #: Temporary files with rotated version of images
        self.text_styles      = []    #: Keep track of already used textstyles
        self.block_styles     = []    #: Keep track of already used blockstyles
        self.images  = {}      #: Images referenced in the HTML document
        self.targets = {}      #: <a name=...> and id elements
        self.links   = deque()  # : <a href=...> elements
        self.processed_files = []
        self.extra_toc_entries = []  # : TOC entries gleaned from semantic information
        self.image_memory = []
        self.id_counter = 0
        self.unused_target_blocks = []  # : Used to remove extra TextBlocks
        self.link_level  = 0    #: Current link level
        self.memory = []        #: Used to ensure that duplicate CSS unhandled errors are not reported
        self.tops = {}          #: element representing the top of each HTML file in the LRF file
        self.previous_text = ''  # : Used to figure out when to lstrip
        self.stripped_space = ''
        self.preserve_block_style = False  # : Used so that <p> tags in <blockquote> elements are handled properly
        self.avoid_page_break = False
        self.current_page = book.create_page()

        # Styles
        self.blockquote_style = book.create_block_style(sidemargin=60,
                                                        topskip=20, footskip=20)
        self.unindented_style = book.create_text_style(parindent=0)

        self.in_table = False
        # List processing
        self.list_level = 0
        self.list_indent = 20
        self.list_counter = 1

        self.book = book                #: The Book object representing a BBeB book

        self.override_css = {}
        self.override_pcss = {}

        if self._override_css is not None:
            if os.access(self._override_css, os.R_OK):
                with open(self._override_css, 'rb') as f:
                    src = f.read()
            else:
                src = self._override_css
            if isinstance(src, bytes):
                src = src.decode('utf-8', 'replace')
            match = self.PAGE_BREAK_PAT.search(src)
            if match and not re.match('avoid', match.group(1), re.IGNORECASE):
                self.page_break_found = True
            ncss, npcss = self.parse_css(src)
            if ncss:
                update_css(ncss, self.override_css)
            if npcss:
                update_css(npcss, self.override_pcss)

        paths = [os.path.abspath(path) for path in paths]
        paths = [path.decode(sys.getfilesystemencoding()) if not isinstance(path, str) else path for path in paths]

        while len(paths) > 0 and self.link_level <= self.link_levels:
            for path in paths:
                if path in self.processed_files:
                    continue
                try:
                    self.add_file(path)
                except KeyboardInterrupt:
                    raise
                except:
                    if self.link_level == 0:  # Die on errors in the first level
                        raise
                    for link in self.links:
                        if link['path'] == path:
                            self.links.remove(link)
                            break
                    self.log.warn('Could not process '+path)
                    if self.verbose:
                        self.log.exception(' ')
            self.links = self.process_links()
            self.link_level += 1
            paths = [link['path'] for link in self.links]

        if self.current_page is not None and self.current_page.has_text():
            self.book.append(self.current_page)

        for text, tb in self.extra_toc_entries:
            self.book.addTocEntry(text, tb)

        if self.base_font_size > 0:
            self.log.info('\tRationalizing font sizes...')
            self.book.rationalize_font_sizes(self.base_font_size)

    def is_baen(self, soup):
        return bool(soup.find('meta', attrs={'name':'Publisher',
                        'content':re.compile('Baen', re.IGNORECASE)}))

    def is_book_designer(self, raw):
        return bool(re.search('<H2[^><]*id=BookTitle', raw))

    def preprocess(self, raw):
        nmassage = []
        nmassage.extend(HTMLConverter.MARKUP_MASSAGE)

        if not self.book_designer and self.is_book_designer(raw):
            self.book_designer = True
            self.log.info(_('\tBook Designer file detected.'))

        self.log.info(_('\tParsing HTML...'))

        if self.baen:
            nmassage.extend(HTMLConverter.BAEN)

        if self.pdftohtml:
            nmassage.extend(HTMLConverter.PDFTOHTML)
        if self.book_designer:
            nmassage.extend(HTMLConverter.BOOK_DESIGNER)
        if isinstance(raw, bytes):
            raw = xml_to_unicode(raw, replace_entities=True)[0]
        for pat, repl in nmassage:
            raw = pat.sub(repl, raw)
        soup = BeautifulSoup(raw)
        if not self.baen and self.is_baen(soup):
            self.baen = True
            self.log.info(_('\tBaen file detected. Re-parsing...'))
            return self.preprocess(raw)
        if self.book_designer:
            t = soup.find(id='BookTitle')
            if t:
                self.book.set_title(self.get_text(t))
            a = soup.find(id='BookAuthor')
            if a:
                self.book.set_author(self.get_text(a))
        if self.verbose:
            tdir = tempfile.gettempdir()
            if not os.path.exists(tdir):
                os.makedirs(tdir)
            try:
                with open(os.path.join(tdir, 'html2lrf-verbose.html'), 'wb') as f:
                    f.write(str(soup).encode('utf-8'))
                    self.log.info(_('Written preprocessed HTML to ')+f.name)
            except:
                pass

        return soup

    def add_file(self, path):
        self.css = HTMLConverter.CSS.copy()
        self.pseudo_css = self.override_pcss.copy()
        for selector in self.override_css:
            if selector in self.css:
                self.css[selector].update(self.override_css[selector])
            else:
                self.css[selector] = self.override_css[selector]

        self.file_name = os.path.basename(path)
        self.log.info(_('Processing %s')%(path if self.verbose else self.file_name))

        if not os.path.exists(path):
            path = path.replace('&', '%26')  # convertlit replaces & with %26 in file names
        with open(path, 'rb') as f:
            raw = f.read()
        if self.pdftohtml:  # Bug in pdftohtml that causes it to output invalid UTF-8 files
            raw = raw.decode('utf-8', 'ignore')
        elif self.encoding is not None:
            raw = raw.decode(self.encoding, 'ignore')
        else:
            raw = xml_to_unicode(raw, self.verbose)[0]
        soup = self.preprocess(raw)
        self.log.info(_('\tConverting to BBeB...'))
        self.current_style = {}
        self.page_break_found = False
        if not isinstance(path, str):
            path = path.decode(sys.getfilesystemencoding())
        self.target_prefix = path
        self.previous_text = '\n'
        self.tops[path] = self.parse_file(soup)
        self.processed_files.append(path)

    def parse_css(self, style):
        """
        Parse the contents of a <style> tag or .css file.
        @param style: C{str(style)} should be the CSS to parse.
        @return: A dictionary with one entry per selector where the key is the
        selector name and the value is a dictionary of properties
        """
        sdict, pdict = {}, {}
        style = re.sub(r'/\*.*?\*/', '', style)  # Remove /*...*/ comments
        for sel in re.findall(HTMLConverter.SELECTOR_PAT, style):
            for key in sel[0].split(','):
                val = self.parse_style_properties(sel[1])
                key = key.strip().lower()
                if '+' in key:
                    continue
                if ':' in key:
                    key, sep, pseudo = key.partition(':')
                    if key in pdict:
                        if pseudo in pdict[key]:
                            pdict[key][pseudo].update(val)
                        else:
                            pdict[key][pseudo] = val
                    else:
                        pdict[key] = {pseudo:val}
                else:
                    if key in sdict:
                        sdict[key].update(val)
                    else:
                        sdict[key] = val
        return sdict, pdict

    def parse_style_properties(self, props):
        """
        Parses a style attribute. The code within a CSS selector block or in
        the style attribute of an HTML element.
        @return: A dictionary with one entry for each property where the key
                is the property name and the value is the property value.
        """
        prop = dict()
        for s in props.split(';'):
            l = s.split(':',1)
            if len(l)==2:
                key = l[0].strip().lower()
                val = l[1].strip()
                prop[key] = val
        return prop

    def tag_css(self, tag, parent_css={}):
        """
        Return a dictionary of style properties applicable to Tag tag.
        """
        def merge_parent_css(prop, pcss):
            # float should not be inherited according to the CSS spec
            # however we need to as we don't do alignment at a block level.
            # float is removed by the process_alignment function.
            inherited = ['text-align', 'float', 'white-space', 'color',
                         'line-height', 'vertical-align']
            temp = {}
            for key in pcss.keys():
                chk = key.lower()
                # float should not be inherited according to the CSS spec
                # however we need to as we don't do alignment at a block level.
                # float is removed by the process_alignment function.
                if chk.startswith('font') or chk in inherited:
                    temp[key] = pcss[key]
            prop.update(temp)

        prop, pprop = {}, {}
        tagname = tag.name.lower()
        if parent_css:
            merge_parent_css(prop, parent_css)
        if tag.has_attr("align"):
            al = tag['align'].lower()
            if al in ('left', 'right', 'center', 'justify'):
                prop["text-align"] = al
        if tagname in self.css:
            prop.update(self.css[tagname])
        if tagname in self.pseudo_css:
            pprop.update(self.pseudo_css[tagname])
        if tag.has_attr("class"):
            cls = tag['class']
            if isinstance(cls, list):
                cls = ' '.join(cls)
            cls = cls.lower()
            for cls in cls.split():
                for classname in ["."+cls, tagname+"."+cls]:
                    if classname in self.css:
                        prop.update(self.css[classname])
                    if classname in self.pseudo_css:
                        pprop.update(self.pseudo_css[classname])
        if tag.has_attr('id') and tag['id'] in self.css:
            prop.update(self.css[tag['id']])
        if tag.has_attr("style"):
            prop.update(self.parse_style_properties(tag["style"]))
        return prop, pprop

    def parse_file(self, soup):
        def get_valid_block(page):
            for item in page.contents:
                if isinstance(item, (Canvas, TextBlock, ImageBlock, RuledLine)):
                    if isinstance(item, TextBlock) and not item.contents:
                        continue
                    return item
        if not self.current_page:
            self.current_page = self.book.create_page()
        self.current_block = self.book.create_text_block()
        self.current_para = Paragraph()
        if self.cover:
            self.add_image_page(self.cover)
            self.cover = None
        top = self.current_block
        self.current_block.must_append = True

        self.soup = soup
        self.process_children(soup, {}, {})
        self.soup = None

        if self.current_para and self.current_block:
            self.current_para.append_to(self.current_block)
        if self.current_block and self.current_page:
            self.current_block.append_to(self.current_page)
        if self.avoid_page_break:
            self.avoid_page_break = False
        elif self.current_page and self.current_page.has_text():
            self.book.append(self.current_page)
            self.current_page = None

        if top not in top.parent.contents:  # May have been removed for a cover image
            top = top.parent.contents[0]
        if not top.has_text() and top.parent.contents.index(top) == len(top.parent.contents)-1:
            # Empty block at the bottom of a page
            opage = top.parent
            top.parent.contents.remove(top)
            if self.book.last_page() is opage:
                if self.current_page and self.current_page.has_text():
                    for c in self.current_page.contents:
                        if isinstance(c, (TextBlock, ImageBlock)):
                            return c
                raise ConversionError(_('Could not parse file: %s')%self.file_name)
            else:
                try:
                    index = self.book.pages().index(opage)
                except ValueError:
                    self.log.warning(_('%s is an empty file')%self.file_name)
                    tb = self.book.create_text_block()
                    self.current_page.append(tb)
                    return tb
                for page in list(self.book.pages()[index+1:]):
                    for c in page.contents:
                        if isinstance(c, (TextBlock, ImageBlock, Canvas)):
                            return c
                raise ConversionError(_('Could not parse file: %s')%self.file_name)

        return top

    def create_link(self, children, tag):
        para = None
        for i in range(len(children)-1, -1, -1):
            if isinstance(children[i], (Span, EmpLine)):
                para = children[i]
                break
        if para is None:
            raise ConversionError(
                _('Failed to parse link %(tag)s %(children)s')%dict(
                    tag=tag, children=children))
        text = self.get_text(tag, 1000)
        if not text:
            text = 'Link'
            img = tag.find('img')
            if img:
                try:
                    text = img['alt']
                except KeyError:
                    pass

        path, fragment = munge_paths(self.target_prefix, tag['href'])
        return {'para':para, 'text':text, 'path':os.path.abspath(path),
                'fragment':fragment, 'in toc': (self.link_level == 0 and
                    not self.use_spine and not self.options.no_links_in_toc)}

    def get_text(self, tag, limit=None):
        css = self.tag_css(tag)[0]
        if ('display' in css and css['display'].lower() == 'none') or ('visibility' in css and css['visibility'].lower() == 'hidden'):
            return ''
        text, alt_text = '', ''
        for c in tag.contents:
            if limit is not None and len(text) > limit:
                break
            if isinstance(c, HTMLConverter.IGNORED_TAGS):
                continue
            if isinstance(c, NavigableString):
                text += str(c)
            elif isinstance(c, Tag):
                if c.name.lower() == 'img' and c.has_attr('alt'):
                    alt_text += c['alt']
                    continue
                text += self.get_text(c)
        return text if text.strip() else alt_text

    def process_links(self):
        def add_toc_entry(text, target):
            # TextBlocks in Canvases have a None parent or an Objects Parent
            if target.parent is not None and \
               hasattr(target.parent, 'objId'):
                self.book.addTocEntry(ascii_text, tb)
            else:
                self.log.debug("Cannot add link %s to TOC"%ascii_text)

        def get_target_block(fragment, targets):
            '''Return the correct block for the <a name> element'''
            bs = targets[fragment]
            if not isinstance(bs, BlockSpace):
                return bs
            ans, found, page = None, False, bs.parent
            for item in page.contents:
                if found:
                    if isinstance(item, (TextBlock, RuledLine, ImageBlock)):
                        ans = item
                        break
                if item == bs:
                    found = True
                    continue

            if not ans:
                for i in range(len(page.contents)-1, -1, -1):
                    if isinstance(page.contents[i], (TextBlock, RuledLine, ImageBlock)):
                        ans = page.contents[i]
                        break

            if not ans:
                ntb = self.book.create_text_block()
                ntb.Paragraph(' ')
                page.append(ntb)
                ans = ntb

            if found:
                targets[fragment] =  ans
                page.contents.remove(bs)
            return ans

        outside_links = deque()
        while len(self.links) > 0:
            link = self.links.popleft()
            para, text, path, fragment = link['para'], link['text'], link['path'], link['fragment']
            ascii_text = text

            if not isinstance(path, str):
                path = path.decode(sys.getfilesystemencoding())
            if path in self.processed_files:
                if path+fragment in self.targets.keys():
                    tb = get_target_block(path+fragment, self.targets)
                else:
                    tb = self.tops[path]
                if link['in toc']:
                    add_toc_entry(ascii_text, tb)

                jb = JumpButton(tb)
                self.book.append(jb)
                cb = CharButton(jb, text=text)
                para.contents = []
                para.append(cb)
                try:
                    self.unused_target_blocks.remove(tb)
                except ValueError:
                    pass
            else:
                outside_links.append(link)

        return outside_links

    def create_toc(self, toc):
        for item in toc.top_level_items():
            ascii_text = item.text
            if not item.fragment and item.abspath in self.tops:
                self.book.addTocEntry(ascii_text, self.tops[item.abspath])
            elif item.abspath:
                url = item.abspath+(item.fragment if item.fragment else '')
                if url in self.targets:
                    self.book.addTocEntry(ascii_text, self.targets[url])

    def end_page(self):
        """
        End the current page, ensuring that any further content is displayed
        on a new page.
        """
        if self.current_para.has_text():
            self.current_para.append_to(self.current_block)
            self.current_para = Paragraph()
        if self.current_block.has_text() or self.current_block.must_append:
            self.current_block.append_to(self.current_page)
            self.current_block = self.book.create_text_block()
        if self.current_page.has_text():
            self.book.append(self.current_page)
            self.current_page = self.book.create_page()

    def add_image_page(self, path):
        if os.access(path, os.R_OK):
            self.end_page()
            pwidth, pheight = self.profile.screen_width, self.profile.screen_height - \
                              self.profile.fudge
            page = self.book.create_page(evensidemargin=0, oddsidemargin=0,
                                         topmargin=0, textwidth=pwidth,
                                         headheight=0, headsep=0, footspace=0,
                                         footheight=0,
                                         textheight=pheight)
            if path not in self.images:
                self.images[path] = ImageStream(path)
            im = PILImage.open(path)
            width, height = im.size
            canvas = Canvas(pwidth, pheight)
            ib = ImageBlock(self.images[path], x1=width,
                            y1=height, xsize=width, ysize=height,
                            blockwidth=width, blockheight=height)
            canvas.put_object(ib, int((pwidth-width)/2.), int((pheight-height)/2.))
            page.append(canvas)
            self.book.append(page)

    def process_children(self, ptag, pcss, ppcss={}):
        """ Process the children of ptag """
        # Need to make a copy of contents as when
        # extract is called on a child, it will
        # mess up the iteration.
        for c in copy.copy(ptag.contents):
            if isinstance(c, HTMLConverter.IGNORED_TAGS):
                continue
            elif isinstance(c, Tag):
                self.parse_tag(c, pcss)
            elif isinstance(c, NavigableString):
                self.add_text(c, pcss, ppcss)
        if not self.in_table:
            try:
                if self.minimize_memory_usage:
                    ptag.extract()
            except AttributeError:
                print(ptag, type(ptag))

    def get_alignment(self, css):
        val = css['text-align'].lower() if 'text-align' in css else None
        align = 'head'
        if val is not None:
            if val in ["right", "foot"]:
                align = "foot"
            elif val == "center":
                align = "center"
        if 'float' in css:
            val = css['float'].lower()
            if val == 'left':
                align = 'head'
            if val == 'right':
                align = 'foot'
            css.pop('float')
        return align

    def process_alignment(self, css):
        '''
        Create a new TextBlock only if necessary as indicated by css
        @type css: dict
        '''
        align = self.get_alignment(css)
        if align != self.current_block.textStyle.attrs['align']:
            self.current_para.append_to(self.current_block)
            self.current_block.append_to(self.current_page)
            ts = self.book.create_text_style(**self.current_block.textStyle.attrs)
            ts.attrs['align'] = align
            try:
                index = self.text_styles.index(ts)
                ts = self.text_styles[index]
            except ValueError:
                self.text_styles.append(ts)
            self.current_block = self.book.create_text_block(
                                blockStyle=self.current_block.blockStyle,
                                textStyle=ts)
            self.current_para = Paragraph()
            return True
        return False

    def add_text(self, tag, css, pseudo_css, force_span_use=False):
        '''
        Add text to the current paragraph taking CSS into account.
        @param tag: Either a BeautifulSoup tag or a string
        @param css: A dict
        '''
        src = tag.string if hasattr(tag, 'string') else tag
        if len(src) > 32760:
            pos = 0
            while pos < len(src):
                self.add_text(src[pos:pos+32760], css, pseudo_css, force_span_use)
                pos += 32760
            return
        src = src.replace('\r\n', '\n').replace('\r', '\n')

        if 'first-letter' in pseudo_css and len(src) > 1:
            src = src.lstrip()
            f = src[0]
            next = 1
            if f in ("'", '"', '\u201c', '\u2018', '\u201d', '\u2019'):
                if len(src) >= 2:
                    next = 2
                    f = src[:2]
            src = src[next:]
            ncss = css.copy()
            ncss.update(pseudo_css.pop('first-letter'))
            self.add_text(f, ncss, {}, force_span_use)

        collapse_whitespace = 'white-space' not in css or css['white-space'] != 'pre'
        if self.process_alignment(css) and collapse_whitespace:
            # Dont want leading blanks in a new paragraph
            src = src.lstrip()

        def append_text(src):
            fp, key, variant = self.font_properties(css)
            for x, y in [('\xad', ''), ('\xa0', ' '), ('\ufb00', 'ff'), ('\ufb01', 'fi'), ('\ufb02', 'fl'), ('\ufb03', 'ffi'), ('\ufb04', 'ffl')]:
                src = src.replace(x, y)

            valigner = lambda x: x
            if 'vertical-align' in css:
                valign = css['vertical-align']
                if valign in ('sup', 'super', 'sub'):
                    fp['fontsize'] = int(fp['fontsize']) * 5 // 3
                    valigner = Sub if valign == 'sub' else Sup
            normal_font_size = int(fp['fontsize'])

            if variant == 'small-caps':
                dump = Span(fontsize=normal_font_size-30)
                temp = []
                for c in src:
                    if c.isupper():
                        if temp:
                            dump.append(valigner(''.join(temp)))
                            temp = []
                        dump.append(Span(valigner(c), fontsize=normal_font_size))
                    else:
                        temp.append(c.upper())
                src = dump
                if temp:
                    src.append(valigner(''.join(temp)))
            else:
                src = valigner(src)

            if key in ['italic', 'bi']:
                already_italic = False
                for fonts in self.fonts.values():
                    it = fonts['italic'][1] if 'italic' in fonts else ''
                    bi = fonts['bi'][1] if 'bi' in fonts else ''
                    if fp['fontfacename'] in (it, bi):
                        already_italic = True
                        break
                if not already_italic:
                    src = Italic(src)

            unneeded = []
            for prop in fp:
                if fp[prop] == self.current_block.textStyle.attrs[prop]:
                    unneeded.append(prop)
            for prop in unneeded:
                fp.pop(prop)
            attrs = {}
            if 'color' in css and not self.ignore_colors:
                attrs['textcolor'] = lrs_color(css['color'])
            attrs.update(fp)
            elem = Span(text=src, **attrs) if (attrs or force_span_use) else src
            if 'text-decoration' in css:
                dec = css['text-decoration'].lower()
                linepos = 'after' if dec == 'underline' else 'before' if dec == 'overline' else None
                if linepos is not None:
                    elem = EmpLine(elem, emplineposition=linepos)
            self.current_para.append(elem)

        if collapse_whitespace:
            src = re.sub(r'\s{1,}', ' ', src)
            if self.stripped_space and len(src) == len(src.lstrip(' \n\r\t')):
                src = self.stripped_space + src
            src, orig = src.rstrip(' \n\r\t'), src
            self.stripped_space = orig[len(src):]
            if len(self.previous_text) != len(self.previous_text.rstrip(' \n\r\t')):
                src = src.lstrip(' \n\r\t')
            if len(src):
                self.previous_text = src
                append_text(src)
        else:
            srcs = src.split('\n')
            for src in srcs[:-1]:
                append_text(src)
                self.line_break()
            last = srcs[-1]
            if len(last):
                append_text(last)

    def line_break(self):
        self.current_para.append(CR())
        self.previous_text = '\n'

    def end_current_para(self):
        '''
        End current paragraph with a paragraph break after it.
        '''
        if self.current_para.contents:
            self.current_block.append(self.current_para)
        self.current_block.append(CR())
        self.current_para = Paragraph()

    def end_current_block(self):
        '''
        End current TextBlock. Create new TextBlock with the same styles.
        '''
        if self.current_para.contents:
            self.current_block.append(self.current_para)
            self.current_para = Paragraph()
        if self.current_block.contents or self.current_block.must_append:
            self.current_page.append(self.current_block)
            self.current_block = self.book.create_text_block(textStyle=self.current_block.textStyle,
                                                         blockStyle=self.current_block.blockStyle)

    def process_image(self, path, tag_css, width=None, height=None,
                      dropcaps=False, rescale=False):
        def detect_encoding(im):
            fmt = im.format
            if fmt == 'JPG':
                fmt = 'JPEG'
            return fmt
        original_path = path
        if path in self.rotated_images:
            path = self.rotated_images[path].name
        if path in self.scaled_images:
            path = self.scaled_images[path].name

        try:
            im = PILImage.open(path)
        except OSError as err:
            self.log.warning('Unable to process image: %s\n%s'%(original_path, err))
            return
        encoding = detect_encoding(im)

        def scale_image(width, height):
            if width <= 0:
                width = 1
            if height <= 0:
                height = 1
            pt = PersistentTemporaryFile(suffix='_html2lrf_scaled_image_.'+encoding.lower())
            self.image_memory.append(pt)  # Necessary, trust me ;-)
            try:
                im.resize((int(width), int(height)), PILImage.ANTIALIAS).save(pt, encoding)
                pt.close()
                self.scaled_images[path] = pt
                return pt.name
            except (OSError, SystemError) as err:  # PIL chokes on interlaced PNG images as well a some GIF images
                self.log.warning(
                    _('Unable to process image %(path)s. Error: %(err)s')%dict(
                        path=path, err=err))

        if width is None or height is None:
            width, height = im.size
        elif rescale and (width < im.size[0] or height < im.size[1]):
            path = scale_image(width, height)
            if not path:
                return

        factor = 720./self.profile.dpi
        pheight = int(self.current_page.pageStyle.attrs['textheight'])
        pwidth  = int(self.current_page.pageStyle.attrs['textwidth'])

        if dropcaps:
            scale = False
            if width > 0.75*pwidth:
                width = int(0.75*pwidth)
                scale = True
            if height > 0.75*pheight:
                height = int(0.75*pheight)
                scale = True
            if scale:
                path = scale_image(width, height)
            if path not in self.images:
                self.images[path] = ImageStream(path)
            im = Image(self.images[path], x0=0, y0=0, x1=width, y1=height,
                               xsize=width, ysize=height)
            line_height = (int(self.current_block.textStyle.attrs['baselineskip']) +
                            int(self.current_block.textStyle.attrs['linespace']))//10
            line_height *= self.profile.dpi/72
            lines = int(ceil(height/line_height))
            dc = DropCaps(lines)
            dc.append(Plot(im, xsize=ceil(width*factor), ysize=ceil(height*factor)))
            self.current_para.append(dc)
            return

        if self.autorotation and width > pwidth and width > height:
            pt = PersistentTemporaryFile(suffix='_html2lrf_rotated_image_.'+encoding.lower())
            try:
                im = im.rotate(90)
                im.save(pt, encoding)
                path = pt.name
                self.rotated_images[path] = pt
                width, height = im.size
            except OSError:  # PIL chokes on interlaced PNG files and since auto-rotation is not critical we ignore the error
                self.log.debug(_('Unable to process interlaced PNG %s')% original_path)
            finally:
                pt.close()

        scaled, width, height = fit_image(width, height, pwidth, pheight)
        if scaled:
            path = scale_image(width, height)

        if not path:
            return

        if path not in self.images:
            try:
                self.images[path] = ImageStream(path, encoding=encoding)
            except LrsError as err:
                self.log.warning(('Could not process image: %s\n%s')%(
                    original_path, err))
                return

        im = Image(self.images[path], x0=0, y0=0, x1=width, y1=height,
                               xsize=width, ysize=height)

        self.process_alignment(tag_css)

        if max(width, height) <= min(pwidth, pheight)/5:
            self.current_para.append(Plot(im, xsize=ceil(width*factor),
                                          ysize=ceil(height*factor)))
        elif height <= int(floor((2/3)*pheight)):
            pb = self.current_block
            self.end_current_para()
            self.process_alignment(tag_css)
            self.current_para.append(Plot(im, xsize=width*factor,
                                          ysize=height*factor))
            self.current_block.append(self.current_para)
            self.current_page.append(self.current_block)
            self.current_block = self.book.create_text_block(
                                            textStyle=pb.textStyle,
                                            blockStyle=pb.blockStyle)
            self.current_para = Paragraph()
        else:
            self.end_page()
            if len(self.current_page.contents) == 1 and not self.current_page.has_text():
                self.current_page.contents[0:1] = []
            self.current_page.append(Canvas(width=pwidth,
                                            height=height))
            left = int(floor((pwidth - width)/2))
            self.current_page.contents[-1].put_object(
                            ImageBlock(self.images[path], xsize=width,
                                       ysize=height, x1=width, y1=height,
                                       blockwidth=width, blockheight=height),
                            left, 0)

    def process_page_breaks(self, tag, tagname, tag_css):
        if 'page-break-before' in tag_css.keys():
            if tag_css['page-break-before'].lower() != 'avoid':
                self.end_page()
            tag_css.pop('page-break-before')
        end_page = False
        if 'page-break-after' in tag_css.keys():
            if tag_css['page-break-after'].lower() == 'avoid':
                self.avoid_page_break = True
            else:
                end_page = True
            tag_css.pop('page-break-after')
        if (self.force_page_break_attr[0].match(tagname) and
           tag.has_attr(self.force_page_break_attr[1]) and
           self.force_page_break_attr[2].match(tag[self.force_page_break_attr[1]])) or \
           self.force_page_break.match(tagname):
            self.end_page()
            self.page_break_found = True
        if not self.page_break_found and self.page_break.match(tagname):
            number_of_paragraphs = sum(
                len([1 for i in block.contents if isinstance(i, Paragraph)])
                for block in self.current_page.contents if isinstance(block, TextBlock)
            )

            if number_of_paragraphs > 2:
                self.end_page()
                self.log.debug('Forcing page break at %s'%tagname)
        return end_page

    def block_properties(self, tag_css):

        def get(what):
            src = [None for i in range(4)]
            if what in tag_css:
                msrc = tag_css[what].split()
                for i in range(min(len(msrc), len(src))):
                    src[i] = msrc[i]
            for i, c in enumerate(('-top', '-right', '-bottom', '-left')):
                if what + c in tag_css:
                    src[i] = tag_css[what+c]
            return src

        s1, s2 = get('margin'), get('padding')

        bl = str(self.current_block.blockStyle.attrs['blockwidth'])+'px'

        def set(default, one, two):
            fval = None
            if one is not None:
                val = self.unit_convert(one, base_length='10pt' if 'em' in one else bl)
                if val is not None:
                    fval = val
            if two is not None:
                val = self.unit_convert(two, base_length='10pt' if 'em' in two else bl)
                if val is not None:
                    fval = val if fval is None else fval + val
            if fval is None:
                fval = default
            return fval

        ans = {}
        ans['topskip']    = set(self.book.defaultBlockStyle.attrs['topskip'], s1[0], s2[0])
        ans['footskip']   = set(self.book.defaultBlockStyle.attrs['footskip'], s1[2], s2[2])
        ans['sidemargin'] = set(self.book.defaultBlockStyle.attrs['sidemargin'], s1[3], s2[3])

        factor = 0.7
        if 2*int(ans['sidemargin']) >= factor*int(self.current_block.blockStyle.attrs['blockwidth']):
            # Try using (left + right)/2
            val = int(ans['sidemargin'])
            ans['sidemargin'] = set(self.book.defaultBlockStyle.attrs['sidemargin'], s1[1], s2[1])
            val += int(ans['sidemargin'])
            val /= 2.
            ans['sidemargin'] = int(val)
        if 2*int(ans['sidemargin']) >= factor*int(self.current_block.blockStyle.attrs['blockwidth']):
            ans['sidemargin'] = int((factor*int(self.current_block.blockStyle.attrs['blockwidth'])) / 2)

        for prop in ('topskip', 'footskip', 'sidemargin'):
            if isinstance(ans[prop], string_or_bytes):
                ans[prop] = int(ans[prop])
            if ans[prop] < 0:
                ans[prop] = 0

        return ans

    def font_properties(self, css):
        '''
        Convert the font propertiess in css to the Xylog equivalents. If the CSS
        does not contain a particular font property, the default from self.book.defaultTextSytle
        is used. Assumes 1em = 10pt
        @return: dict, key, variant. The dict contains the Xlog equivalents. key indicates
          the font type (i.e. bold, bi, normal) and variant is None or 'small-caps'
        '''
        t = {}
        for key in ('fontwidth', 'fontsize', 'wordspace', 'fontfacename', 'fontweight', 'baselineskip'):
            t[key] = self.book.defaultTextStyle.attrs[key]

        def font_weight(val):
            ans = 0
            m = re.search("([0-9]+)", val)
            if m:
                ans = int(m.group(1))
            elif val.find("bold") >= 0 or val.find("strong") >= 0:
                ans = 700
            return 'bold' if ans >= 700 else 'normal'

        def font_style(val):
            ans = 'normal'
            if 'italic' in val or 'oblique' in val:
                ans = 'italic'
            return ans

        def font_family(val):
            ans = 'serif'
            if max(val.find("courier"), val.find("mono"), val.find("fixed"), val.find("typewriter"))>=0:
                ans = 'mono'
            elif max(val.find("arial"), val.find("helvetica"), val.find("verdana"),
                 val.find("trebuchet"), val.find("sans")) >= 0:
                ans = 'sans'
            return ans

        def font_variant(val):
            ans = None
            if 'small-caps' in val.lower():
                ans = 'small-caps'
            return ans

        def font_key(family, style, weight):
            key = 'normal'
            if style == 'italic' and weight == 'normal':
                key = 'italic'
            elif style == 'normal' and weight == 'bold':
                key = 'bold'
            elif style == 'italic' and weight == 'bold':
                key = 'bi'
            return key

        def font_size(val):
            '''
            Assumes 1em=100%=10pt
            '''
            normal = 100
            ans = self.unit_convert(val, pts=True, base_length='10pt')

            if ans:
                if ans <= 0:
                    ans += normal
                    if ans == 0:  # Common case of using -1em to mean "smaller"
                        ans = int(font_size("smaller"))
                    if ans < 0:
                        ans = normal
            else:
                if ans == 0:
                    ans = int(font_size("smaller"))
                elif "smaller" in val:
                    ans = normal - 20
                elif "xx-small" in val:
                    ans = 40
                elif "x-small" in val:
                    ans = 60
                elif "small" in val:
                    ans = 80
                elif "medium" in val:
                    ans = 100
                elif "larger" in val:
                    ans = normal + 20
                elif "xx-large" in val:
                    ans = 180
                elif "x-large" in val:
                    ans = 140
                elif "large" in val:
                    ans = 120
            if ans is not None:
                ans += int(self.font_delta * 20)
                ans = str(ans)
            return ans

        family, weight, style, variant = 'serif', 'normal', 'normal', None
        for key in css.keys():
            val = css[key].lower()
            if key == 'font':
                vals = val.split()
                for val in vals:
                    family = font_family(val)
                    if family != 'serif':
                        break
                for val in vals:
                    weight = font_weight(val)
                    if weight != 'normal':
                        break
                for val in vals:
                    style = font_style(val)
                    if style != 'normal':
                        break
                for val in vals:
                    sz = font_size(val)
                    if sz:
                        t['fontsize'] = sz
                        break
                for val in vals:
                    variant = font_variant(val)
                    if variant:
                        t['fontvariant'] = variant
                        break
            elif key in ['font-family', 'font-name']:
                family = font_family(val)
            elif key == "font-size":
                ans = font_size(val)
                if ans:
                    t['fontsize'] = ans
            elif key == 'font-weight':
                weight = font_weight(val)
            elif key == 'font-style':
                style = font_style(val)
            elif key == 'font-variant':
                variant = font_variant(val)

        if variant:
            css['font-variant'] = variant

        key = font_key(family, style, weight)
        if key in self.fonts[family]:
            t['fontfacename'] = self.fonts[family][key][1]
        else:
            t['fontfacename'] = self.fonts[family]['normal'][1]
        if key in ['bold', 'bi']:
            t['fontweight'] = 700

        fs = int(t['fontsize'])
        if fs > 120:
            t['wordspace'] = fs // 4
        t['baselineskip'] = fs + 20
        return t, key, variant

    def unit_convert(self, val, pts=False, base_length='10pt'):
        '''
        Tries to convert html units in C{val} to pixels.
        @param pts: If True return 10*pts instead of pixels.
        @return: The number of pixels (an int) if successful. Otherwise, returns None.
        '''
        dpi = self.profile.dpi
        result = None
        try:
            result = int(val)
        except ValueError:
            pass
        m = re.search(r"\s*(-*[0-9]*\.?[0-9]*)\s*(%|em|px|mm|cm|in|dpt|pt|pc)", val)

        if m is not None and m.group(1):
            unit = float(m.group(1))
            if m.group(2) == '%':
                normal = self.unit_convert(base_length)
                result = (unit/100) * normal
            elif m.group(2) == 'px':
                result = unit
            elif m.group(2) == 'in':
                result = unit * dpi
            elif m.group(2) == 'pt':
                result = unit * dpi/72
            elif m.group(2) == 'dpt':
                result = unit * dpi/720
            elif m.group(2) == 'em':
                normal = self.unit_convert(base_length)
                result = unit * normal
            elif m.group(2) == 'pc':
                result = unit * (dpi/72) * 12
            elif m.group(2) == 'mm':
                result = unit * 0.04 * (dpi)
            elif m.group(2) == 'cm':
                result = unit * 0.4 * (dpi)
        if result is not None:
            if pts:
                result = int(round(result * (720/dpi)))
            else:
                result = int(round(result))
        return result

    def text_properties(self, tag_css):
        indent = self.book.defaultTextStyle.attrs['parindent']
        if 'text-indent' in tag_css:
            bl = str(self.current_block.blockStyle.attrs['blockwidth'])+'px'
            if 'em' in tag_css['text-indent']:
                bl = '10pt'
            indent = self.unit_convert(str(tag_css['text-indent']), pts=True, base_length=bl)
            if not indent:
                indent = 0
            if indent > 0 and indent < 10 * self.minimum_indent:
                indent = int(10 * self.minimum_indent)

        fp = self.font_properties(tag_css)[0]
        fp['parindent'] = indent

        if 'line-height' in tag_css:
            bls, ls = int(self.book.defaultTextStyle.attrs['baselineskip']), \
                      int(self.book.defaultTextStyle.attrs['linespace'])
            try:  # See if line-height is a unitless number
                val = int(float(tag_css['line-height'].strip()) * (ls))
                fp['linespace'] = val
            except ValueError:
                val = self.unit_convert(tag_css['line-height'], pts=True, base_length='1pt')
            if val is not None:
                val -= bls
                if val >= 0:
                    fp['linespace'] = val

        return fp

    def process_block(self, tag, tag_css):
        ''' Ensure padding and text-indent properties are respected '''
        text_properties = self.text_properties(tag_css)
        block_properties = self.block_properties(tag_css)
        indent = (float(text_properties['parindent'])/10) * (self.profile.dpi/72)
        margin = float(block_properties['sidemargin'])
        # Since we're flattening the block structure, we need to ensure that text
        # doesn't go off the left edge of the screen
        if indent < 0 and margin + indent < 0:
            text_properties['parindent'] = int(-margin * (72/self.profile.dpi) * 10)

        align = self.get_alignment(tag_css)

        def fill_out_properties(props, default):
            for key in default.keys():
                if key not in props:
                    props[key] = default[key]

        fill_out_properties(block_properties, self.book.defaultBlockStyle.attrs)
        fill_out_properties(text_properties, self.book.defaultTextStyle.attrs)

        def properties_different(dict1, dict2):
            for key in dict1.keys():
                if dict1[key] != dict2[key]:
                    return True
            return False

        if properties_different(self.current_block.blockStyle.attrs, block_properties) or \
           properties_different(self.current_block.textStyle.attrs, text_properties) or\
           align != self.current_block.textStyle.attrs['align']:
            ts = self.current_block.textStyle.copy()
            ts.attrs.update(text_properties)
            ts.attrs['align'] = align
            bs = self.current_block.blockStyle.copy()
            if not self.preserve_block_style:
                bs.attrs.update(block_properties)
            self.current_block.append_to(self.current_page)
            try:
                index = self.text_styles.index(ts)
                ts = self.text_styles[index]
            except ValueError:
                self.text_styles.append(ts)
            try:
                index = self.block_styles.index(bs)
                bs = self.block_styles[index]
            except ValueError:
                self.block_styles.append(bs)
            self.current_block = self.book.create_text_block(blockStyle=bs,
                                                             textStyle=ts)
            return True
        return False

    def process_anchor(self, tag, tag_css, tag_pseudo_css):
        if not self.in_table:  # Anchors in tables are handled separately
            key = 'name' if tag.has_attr('name') else 'id'
            name = tag[key].replace('#', '')
            previous = self.current_block
            self.process_children(tag, tag_css, tag_pseudo_css)
            target = None

            if self.current_block == previous:
                self.current_block.must_append = True
                target = self.current_block
            else:
                found = False
                for item in self.current_page.contents:
                    if item == previous:
                        found = True
                        continue
                    if found:
                        target = item
                        break
                if target and not isinstance(target, (TextBlock, ImageBlock)):
                    if isinstance(target, RuledLine):
                        target = self.book.create_text_block(textStyle=self.current_block.textStyle,
                                                     blockStyle=self.current_block.blockStyle)
                        target.Paragraph(' ')
                        self.current_page.append(target)
                    else:
                        target = BlockSpace()
                        self.current_page.append(target)
                if target is None:
                    if self.current_block.has_text():
                        target = self.current_block
                    else:
                        target = self.current_block
                        self.current_block.must_append = True
            self.targets[self.target_prefix+name] = target
        else:
            self.process_children(tag, tag_css, tag_pseudo_css)

    def parse_tag(self, tag, parent_css):
        try:
            tagname = tag.name.lower()
        except AttributeError:
            if not isinstance(tag, HTMLConverter.IGNORED_TAGS):
                self.add_text(tag, parent_css, {})
            return
        tag_css, tag_pseudo_css = self.tag_css(tag, parent_css=parent_css)
        try:  # Skip element if its display attribute is set to none
            if tag_css['display'].lower() == 'none' or \
               tag_css['visibility'].lower() == 'hidden':
                return
        except KeyError:
            pass
        if not self.disable_chapter_detection and \
           (self.chapter_attr[0].match(tagname) and
            (self.chapter_attr[1].lower() == 'none' or
             (tag.has_attr(self.chapter_attr[1]) and
              self.chapter_attr[2].match(tag[self.chapter_attr[1]])))):
            self.log.debug('Detected chapter %s'%tagname)
            self.end_page()
            self.page_break_found = True

            if self.options.add_chapters_to_toc:
                self.current_block.must_append = True
                self.extra_toc_entries.append((self.get_text(tag,
                    limit=1000), self.current_block))

        end_page = self.process_page_breaks(tag, tagname, tag_css)
        try:
            if tagname in ["title", "script", "meta", 'del', 'frameset']:
                pass
            elif tagname == 'a' and self.link_levels >= 0:
                if tag.has_attr('href') and not self.link_exclude.match(tag['href']):
                    if urlparse(tag['href'])[0] not in ('', 'file'):
                        self.process_children(tag, tag_css, tag_pseudo_css)
                    else:
                        path = munge_paths(self.target_prefix, tag['href'])[0]
                        ext = os.path.splitext(path)[1]
                        if ext:
                            ext = ext[1:].lower()
                        if os.access(path, os.R_OK) and os.path.isfile(path):
                            if ext in ['png', 'jpg', 'bmp', 'jpeg']:
                                self.process_image(path, tag_css)
                            else:
                                text = self.get_text(tag, limit=1000)
                                if not text.strip():
                                    text = "Link"
                                self.add_text(text, tag_css, {}, force_span_use=True)
                                self.links.append(self.create_link(self.current_para.contents, tag))
                                if tag.has_attr('id') or tag.has_attr('name'):
                                    key = 'name' if tag.has_attr('name') else 'id'
                                    self.targets[self.target_prefix+tag[key]] = self.current_block
                                    self.current_block.must_append = True
                        else:
                            self.log.debug('Could not follow link to '+tag['href'])
                            self.process_children(tag, tag_css, tag_pseudo_css)
                elif tag.has_attr('name') or tag.has_attr('id'):
                    self.process_anchor(tag, tag_css, tag_pseudo_css)
                else:
                    self.process_children(tag, tag_css, tag_pseudo_css)
            elif tagname == 'img':
                if tag.has_attr('src'):
                    path = munge_paths(self.target_prefix, tag['src'])[0]
                    if not os.path.exists(path):
                        path = path.replace('&', '%26')  # convertlit replaces & with %26
                    if os.access(path, os.R_OK) and os.path.isfile(path):
                        width, height = None, None
                        try:
                            width = int(tag['width'])
                            height = int(tag['height'])
                        except:
                            pass
                        dropcaps = tag.get('class') in ('libprs500_dropcaps', ['libprs500_dropcaps'])
                        self.process_image(path, tag_css, width, height,
                                           dropcaps=dropcaps, rescale=True)
                    elif not urlparse(tag['src'])[0]:
                        self.log.warn('Could not find image: '+tag['src'])
                else:
                    self.log.debug("Failed to process: %s"%str(tag))
            elif tagname in ['style', 'link']:
                ncss, npcss = {}, {}
                if tagname == 'style':
                    text = ''.join([str(i) for i in tag.findAll(text=True)])
                    css, pcss = self.parse_css(text)
                    ncss.update(css)
                    npcss.update(pcss)
                elif (tag.has_attr('type') and tag['type'] in ("text/css", "text/x-oeb1-css") and tag.has_attr('href')):
                    path = munge_paths(self.target_prefix, tag['href'])[0]
                    try:
                        with open(path, 'rb') as f:
                            src = f.read().decode('utf-8', 'replace')
                        match = self.PAGE_BREAK_PAT.search(src)
                        if match and not re.match('avoid', match.group(1), re.IGNORECASE):
                            self.page_break_found = True
                        ncss, npcss = self.parse_css(src)
                    except OSError:
                        self.log.warn('Could not read stylesheet: '+tag['href'])
                if ncss:
                    update_css(ncss, self.css)
                    self.css.update(self.override_css)
                if npcss:
                    update_css(npcss, self.pseudo_css)
                    self.pseudo_css.update(self.override_pcss)
            elif tagname == 'pre':
                self.end_current_para()
                self.end_current_block()
                self.current_block = self.book.create_text_block()
                ts = self.current_block.textStyle.copy()
                self.current_block.textStyle = ts
                self.current_block.textStyle.attrs['parindent'] = '0'

                if tag.contents:
                    c = tag.contents[0]
                    if isinstance(c, NavigableString):
                        c = str(c).replace('\r\n', '\n').replace('\r', '\n')
                        if c.startswith('\n'):
                            c = c[1:]
                            tag.contents[0] = NavigableString(c)
                            tag.contents[0].setup(tag)
                self.process_children(tag, tag_css, tag_pseudo_css)
                self.end_current_block()
            elif tagname in ['ul', 'ol', 'dl']:
                self.list_level += 1
                if tagname == 'ol':
                    old_counter = self.list_counter
                    self.list_counter = 1
                    try:
                        self.list_counter = int(tag['start'])
                    except:
                        pass
                prev_bs = self.current_block.blockStyle
                self.end_current_block()
                attrs = self.current_block.blockStyle.attrs
                attrs = attrs.copy()
                attrs['sidemargin'] = self.list_indent*self.list_level
                bs = self.book.create_block_style(**attrs)
                self.current_block = self.book.create_text_block(
                                            blockStyle=bs,
                                            textStyle=self.unindented_style)
                self.process_children(tag, tag_css, tag_pseudo_css)
                self.end_current_block()
                self.current_block.blockStyle = prev_bs
                self.list_level -= 1
                if tagname == 'ol':
                    self.list_counter = old_counter
            elif tagname in ['li', 'dt', 'dd']:
                margin = self.list_indent*self.list_level
                if tagname == 'dd':
                    margin += 80
                if int(self.current_block.blockStyle.attrs['sidemargin']) != margin:
                    self.end_current_block()
                    attrs = self.current_block.blockStyle.attrs
                    attrs = attrs.copy()
                    attrs['sidemargin'] = margin
                    attrs['blockwidth'] = int(attrs['blockwidth']) + margin
                    bs = self.book.create_block_style(**attrs)
                    self.current_block = self.book.create_text_block(
                                            blockStyle=bs,
                                            textStyle=self.unindented_style)

                if self.current_para.has_text():
                    self.line_break()
                    self.current_block.append(self.current_para)
                self.current_para = Paragraph()
                self.previous_text = '\n'
                if tagname == 'li':
                    in_ol, parent = True, tag.parent
                    while parent:
                        if parent.name and parent.name.lower() in ['ul', 'ol']:
                            in_ol = parent.name.lower() == 'ol'
                            break
                        parent = parent.parent
                    prepend = str(self.list_counter)+'. ' if in_ol else '\u2022' + ' '
                    self.current_para.append(Span(prepend))
                    self.process_children(tag, tag_css, tag_pseudo_css)
                    if in_ol:
                        self.list_counter += 1
                else:
                    self.process_children(tag, tag_css, tag_pseudo_css)
            elif tagname == 'blockquote':
                self.current_para.append_to(self.current_block)
                self.current_block.append_to(self.current_page)
                pb = self.current_block
                self.current_para = Paragraph()
                ts = self.book.create_text_style()
                ts.attrs['parindent'] = 0
                try:
                    index = self.text_styles.index(ts)
                    ts = self.text_styles[index]
                except ValueError:
                    self.text_styles.append(ts)
                bs = self.book.create_block_style()
                bs.attrs['sidemargin'], bs.attrs['topskip'], bs.attrs['footskip'] = \
                60, 20, 20
                try:
                    index = self.block_styles.index(bs)
                    bs = self.block_styles[index]
                except ValueError:
                    self.block_styles.append(bs)
                self.current_block = self.book.create_text_block(
                                        blockStyle=bs, textStyle=ts)
                self.previous_text = '\n'
                self.preserve_block_style = True
                self.process_children(tag, tag_css, tag_pseudo_css)
                self.preserve_block_style = False
                self.current_para.append_to(self.current_block)
                self.current_block.append_to(self.current_page)
                self.current_para = Paragraph()
                self.current_block = self.book.create_text_block(textStyle=pb.textStyle,
                                                                 blockStyle=pb.blockStyle)
            elif tagname in ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                new_block = self.process_block(tag, tag_css)

                if (self.anchor_ids and tag.has_attr('id')) or (self.book_designer and tag.get('class') in ('title', ['title'])):
                    if not tag.has_attr('id'):
                        tag['id'] = __appname__+'_id_'+str(self.id_counter)
                        self.id_counter += 1

                    tkey = self.target_prefix+tag['id']
                    if not new_block:
                        self.end_current_block()
                    self.current_block.must_append = True
                    self.targets[tkey] = self.current_block
                    if (self.book_designer and tag.get('class') in ('title', ['title'])):
                        self.extra_toc_entries.append((self.get_text(tag, 100), self.current_block))

                src = self.get_text(tag, limit=1000)

                if not self.disable_chapter_detection and tagname.startswith('h'):
                    if self.chapter_regex.search(src):
                        self.log.debug('Detected chapter %s'%src)
                        self.end_page()
                        self.page_break_found = True

                        if self.options.add_chapters_to_toc:
                            self.current_block.must_append = True
                            self.extra_toc_entries.append((self.get_text(tag,
                                limit=1000), self.current_block))

                if self.current_para.has_text():
                    self.current_para.append_to(self.current_block)
                self.current_para = Paragraph()

                self.previous_text = '\n'

                if not tag.contents:
                    self.current_block.append(CR())
                    return

                if self.current_block.contents:
                    self.current_block.append(CR())

                self.process_children(tag, tag_css, tag_pseudo_css)

                if self.current_para.contents :
                    self.current_block.append(self.current_para)
                self.current_para = Paragraph()
                if tagname.startswith('h') or self.blank_after_para:
                    self.current_block.append(CR())
            elif tagname in ['b', 'strong', 'i', 'em', 'span', 'tt', 'big', 'code', 'cite', 'sup', 'sub']:
                self.process_children(tag, tag_css, tag_pseudo_css)
            elif tagname == 'font':
                if tag.has_attr('face'):
                    tag_css['font-family'] = tag['face']
                if tag.has_attr('color'):
                    tag_css['color'] = tag['color']
                self.process_children(tag, tag_css, tag_pseudo_css)
            elif tagname in ['br']:
                self.line_break()
                self.previous_text = '\n'
            elif tagname in ['hr', 'tr']:  # tr needed for nested tables
                self.end_current_block()
                if tagname == 'hr' and not tag_css.get('width', '').strip().startswith('0'):
                    self.current_page.RuledLine(linelength=int(self.current_page.pageStyle.attrs['textwidth']))
                self.previous_text = '\n'
                self.process_children(tag, tag_css, tag_pseudo_css)
            elif tagname == 'td':  # Needed for nested tables
                if not self.in_table:
                    self.current_para.append(' ')
                    self.previous_text = ' '
                self.process_children(tag, tag_css, tag_pseudo_css)
            elif tagname == 'table' and not self.ignore_tables and not self.in_table:
                tag_css = self.tag_css(tag)[0]  # Table should not inherit CSS
                try:
                    self.process_table(tag, tag_css)
                except Exception as err:
                    self.log.warning(_('An error occurred while processing a table: %s. Ignoring table markup.')%repr(err))
                    self.log.exception('')
                    self.log.debug(_('Bad table:\n%s')%str(tag)[:300])
                    self.in_table = False
                    self.process_children(tag, tag_css, tag_pseudo_css)
                finally:
                    if self.minimize_memory_usage:
                        tag.extract()
            else:
                self.process_children(tag, tag_css, tag_pseudo_css)
        finally:
            if end_page:
                self.end_page()

    def process_table(self, tag, tag_css):
        self.end_current_block()
        self.current_block = self.book.create_text_block()
        rowpad = 10
        table = Table(self, tag, tag_css, rowpad=rowpad, colpad=10)
        canvases = []
        ps = self.current_page.pageStyle.attrs
        for block, xpos, ypos, delta, targets in table.blocks(int(ps['textwidth']), int(ps['textheight'])):
            if not block:
                if ypos > int(ps['textheight']):
                    raise Exception(_('Table has cell that is too large'))
                canvases.append(Canvas(int(self.current_page.pageStyle.attrs['textwidth']), ypos+rowpad,
                        blockrule='block-fixed'))
                for name in targets:
                    self.targets[self.target_prefix+name] = canvases[-1]
            else:
                if xpos > 65535:
                    xpos = 65535
                canvases[-1].put_object(block, xpos + int(delta/2), ypos)

        for canvas in canvases:
            self.current_page.append(canvas)
        self.end_current_block()

    def remove_unused_target_blocks(self):
        for block in self.unused_target_blocks:
            block.parent.contents.remove(block)
            block.parent = None

    def writeto(self, path, lrs=False):
        self.remove_unused_target_blocks()
        self.book.renderLrs(path) if lrs else self.book.renderLrf(path)

    def cleanup(self):
        for _file in chain(itervalues(self.scaled_images), itervalues(self.rotated_images)):
            _file.__del__()


def process_file(path, options, logger):
    path = os.path.abspath(path)
    default_title = force_unicode(os.path.splitext(os.path.basename(path))[0], filesystem_encoding)
    dirpath = os.path.dirname(path)

    tpath = ''
    try_opf(path, options, logger)
    if getattr(options, 'cover', None):
        options.cover = os.path.expanduser(options.cover)
        if not os.path.isabs(options.cover):
            options.cover = os.path.join(dirpath, options.cover)
        if os.access(options.cover, os.R_OK):
            th = Device.THUMBNAIL_HEIGHT
            im = PILImage.open(options.cover)
            pwidth, pheight = options.profile.screen_width, \
                              options.profile.screen_height - options.profile.fudge
            width, height = im.size
            if width < pwidth:
                corrf = pwidth/width
                width, height = pwidth, int(corrf*height)

            scaled, width, height = fit_image(width, height, pwidth, pheight)
            try:
                cim = im.resize((width, height), PILImage.BICUBIC).convert('RGB') if \
                      scaled else im
                cf = PersistentTemporaryFile(prefix=__appname__+"_", suffix=".jpg")
                cf.close()
                cim.convert('RGB').save(cf.name)
                options.cover = cf.name

                tim = im.resize((int(0.75*th), th), PILImage.ANTIALIAS).convert('RGB')
                tf = PersistentTemporaryFile(prefix=__appname__+'_', suffix=".jpg")
                tf.close()
                tim.save(tf.name)
                tpath = tf.name
            except OSError as err:  # PIL sometimes fails, for example on interlaced PNG files
                logger.warn(_('Could not read cover image: %s'), err)
                options.cover = None
        else:
            raise ConversionError(_('Cannot read from: %s')% (options.cover,))

    if not options.title:
        options.title = default_title

    for prop in ('author', 'author_sort', 'title', 'title_sort', 'publisher', 'freetext'):
        val = getattr(options, prop, None)
        if val and not isinstance(val, str):
            soup = BeautifulSoup(val)
            setattr(options, prop, str(soup))

    title = (options.title, options.title_sort)
    author = (options.author, options.author_sort)

    args = dict(font_delta=options.font_delta, title=title,
                author=author, sourceencoding='utf8',
                freetext=options.freetext, category=options.category,
                publisher=options.publisher,
                booksetting=BookSetting(dpi=10*options.profile.dpi,
                                        screenheight=options.profile.screen_height,
                                        screenwidth=options.profile.screen_width))
    if tpath:
        args['thumbnail'] = tpath
    header = None
    if options.header:
        header = Paragraph()
        fheader = options.headerformat
        if not options.title:
            options.title = _('Unknown')
        if not options.author:
            options.author = _('Unknown')
        if not fheader:
            fheader = "%t by %a"
        fheader = re.sub(r'(?<!%)%t', options.title, fheader)
        fheader = re.sub(r'(?<!%)%a', options.author, fheader)
        fheader = re.sub(r'%%a','%a',fheader)
        fheader = re.sub(r'%%t','%t',fheader)
        header.append(fheader + "  ")
    book, fonts = Book(options, logger, header=header, **args)
    le = re.compile(options.link_exclude) if options.link_exclude else \
         re.compile('$')
    pb = re.compile(options.page_break, re.IGNORECASE) if options.page_break else \
         re.compile('$')
    fpb = re.compile(options.force_page_break, re.IGNORECASE) if options.force_page_break else \
         re.compile('$')
    cq = options.chapter_attr.split(',')
    if len(cq) < 3:
        raise ValueError('The --chapter-attr setting must have 2 commas.')
    options.chapter_attr = [re.compile(cq[0], re.IGNORECASE), cq[1],
                            re.compile(cq[2], re.IGNORECASE)]
    options.force_page_break = fpb
    options.link_exclude = le
    options.page_break = pb
    if not isinstance(options.chapter_regex, str):
        options.chapter_regex = options.chapter_regex.decode(preferred_encoding)
    options.chapter_regex = re.compile(options.chapter_regex, re.IGNORECASE)
    fpba = options.force_page_break_attr.split(',')
    if len(fpba) != 3:
        fpba = ['$', '', '$']
    options.force_page_break_attr = [re.compile(fpba[0], re.IGNORECASE), fpba[1],
                                     re.compile(fpba[2], re.IGNORECASE)]
    if not hasattr(options, 'anchor_ids'):
        options.anchor_ids = True
    files = options.spine if (options.use_spine and hasattr(options, 'spine')) else [path]
    conv = HTMLConverter(book, fonts, options, logger, files)
    if options.use_spine and hasattr(options, 'toc') and options.toc is not None:
        conv.create_toc(options.toc)
    oname = options.output
    if not oname:
        suffix = '.lrs' if options.lrs else '.lrf'
        name = os.path.splitext(os.path.basename(path))[0] + suffix
        oname = os.path.join(os.getcwd(), name)
    oname = os.path.abspath(os.path.expanduser(oname))
    conv.writeto(oname, lrs=options.lrs)
    conv.cleanup()
    return oname


def try_opf(path, options, logger):
    if hasattr(options, 'opf'):
        opf = options.opf
    else:
        files = glob.glob(os.path.join(os.path.dirname(path),'*'))
        opf = None
        for f in files:
            ext = f.rpartition('.')[-1].lower()
            if ext == 'opf':
                opf = f
                break
    if opf is None:
        return

    dirpath = os.path.dirname(os.path.abspath(opf))
    from calibre.ebooks.metadata.opf2 import OPF as OPF2
    with open(opf, 'rb') as f:
        opf = OPF2(f, dirpath)
    try:
        title = opf.title
        if title and not getattr(options, 'title', None):
            options.title = title
        if getattr(options, 'author', 'Unknown') == 'Unknown':
            if opf.authors:
                options.author = ', '.join(opf.authors)
            if opf.author_sort:
                options.author_sort = opf.author_sort
        if options.publisher == 'Unknown':
            publisher = opf.publisher
            if publisher:
                options.publisher = publisher
        if not getattr(options, 'cover', None) or options.use_metadata_cover:
            orig_cover = getattr(options, 'cover', None)
            options.cover = None
            cover = opf.cover
            if cover:
                cover = cover.replace('/', os.sep)
                if not os.path.isabs(cover):
                    cover = os.path.join(dirpath, cover)
                if os.access(cover, os.R_OK):
                    try:
                        PILImage.open(cover)
                        options.cover = cover
                    except:
                        pass
            if not getattr(options, 'cover', None) and orig_cover is not None:
                options.cover = orig_cover
        if getattr(opf, 'spine', False):
            options.spine = [i.path for i in opf.spine if i.path]
        if not getattr(options, 'toc', None):
            options.toc   = opf.toc
    except Exception:
        logger.exception(_('Failed to process OPF file'))
