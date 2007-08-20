##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
##    This work is based on htmlbbeb created by esperanc.
##
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
Code to convert HTML ebooks into LRF ebooks.

I am indebted to esperanc for the initial CSS->Xylog Style conversion code
and to Falstaff for pylrs.
"""
import os, re, sys, copy, glob, logging
from htmlentitydefs import name2codepoint
from urllib import unquote
from urlparse import urlparse
from math import ceil, floor
try:
    from PIL import Image as PILImage
except ImportError:
    import Image as PILImage

from libprs500.ebooks.BeautifulSoup import BeautifulSoup, Comment, Tag, \
                            NavigableString, Declaration, ProcessingInstruction
from libprs500.ebooks.lrf.pylrs.pylrs import Paragraph, CR, Italic, ImageStream, \
                TextBlock, ImageBlock, JumpButton, CharButton, \
                Plot, Image, BlockSpace, RuledLine, BookSetting, Canvas, DropCaps, \
                LrsError, Sup, Sub, properties_different
from libprs500.ebooks.lrf.pylrs.pylrs import Span 
from libprs500.ebooks.lrf import Book
from libprs500.ebooks.lrf import option_parser as lrf_option_parser
from libprs500.ebooks import ConversionError
from libprs500.ebooks.lrf.html.table import Table 
from libprs500 import filename_to_utf8,  setup_cli_handlers, __appname__
from libprs500.ptempfile import PersistentTemporaryFile
from libprs500.ebooks.metadata.opf import OPFReader

        
class HTMLConverter(object):
    SELECTOR_PAT   = re.compile(r"([A-Za-z0-9\-\_\:\.]+[A-Za-z0-9\-\_\:\.\s\,]*)\s*\{([^\}]*)\}")
    PAGE_BREAK_PAT = re.compile(r'page-break-(?:after|before)\s*:\s*(\w+)', re.IGNORECASE)
    IGNORED_TAGS   = (Comment, Declaration, ProcessingInstruction)
    replaced_entities = [ 'amp', 'lt', 'gt' , 'ldquo', 'rdquo', 'lsquo', 'rsquo']
    patterns = [ re.compile('&'+i+';') for i in replaced_entities ]
    targets  = [ unichr(name2codepoint[i]) for i in replaced_entities ]
    ENTITY_RULES = zip(patterns, targets) + [(re.compile('&apos;'), "'")]
    
     
    MARKUP_MASSAGE   = [
                        # Close <a /> tags
                        (re.compile("(<a\s+.*?)/>|<a/>", re.IGNORECASE), 
                         lambda match: match.group(1)+"></a>"),
                         # Strip comments from <style> tags. This is needed as 
                         # sometimes there are unterminated comments
                        (re.compile(r"<\s*style.*?>(.*?)<\/\s*style\s*>", re.DOTALL|re.IGNORECASE),
                         lambda match: match.group().replace('<!--', '').replace('-->', '')),
                         # remove <p> tags from within <a> tags
                        (re.compile(r'<a.*?>(.*?)</a\s*>', re.DOTALL|re.IGNORECASE),
                         lambda match: re.compile(r'<\s*?p.*?>', re.IGNORECASE).sub('', match.group())),
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
                  (re.compile(r'<hr.*?>', re.IGNORECASE), lambda match: '<span style="page-break-after:always"> </span>'),
                  # Remove page numbers
                  (re.compile(r'\d+<br>', re.IGNORECASE), lambda match: ''),
                  # Remove <br> and replace <br><br> with <p>
                  (re.compile(r'<br.*?>\s*<br.*?>', re.IGNORECASE), lambda match: '<p>'),
                  (re.compile(r'(.*)<br.*?>', re.IGNORECASE), 
                   lambda match: match.group() if re.match('<', match.group(1).lstrip()) or len(match.group(1)) < 40 
                                else match.group(1)),
                  # Remove hyphenation
                  (re.compile(r'-\n|-\n\r'), lambda match: ''),
                  
                  ]
    
    def __hasattr__(self, attr):
        if hasattr(self.options, attr):
            return True
        return object.__hasattr__(self, attr)
    
    def __getattr__(self, attr):
        if hasattr(self.options, attr):
            return getattr(self.options, attr)
        return object.__getattr__(self, attr)
    
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
           'pre'    : {'font-family' : 'monospace', 'white-space': 'pre' },
           'code'   : {'font-family' : 'monospace' },
           'tt'     : {'font-family' : 'monospace'},
           'center' : {'text-align'  : 'center'},
           'th'     : {'font-size'   : 'large', 'font-weight':'bold'},
           'big'    : {'font-size'   : 'large', 'font-weight':'bold'},
           '.libprs500_dropcaps' : {'font-size': 'xx-large'}, 
           }
    
    def __init__(self, book, fonts, options, logger, path):
        '''
        Convert HTML file at C{path} and add it to C{book}. After creating
        the object, you must call L{self.process_links} on it to create the links and
        then L{self.writeto} to output the LRF/S file.
        
        @param book: The LRF book 
        @type book:  L{libprs500.lrf.pylrs.Book}
        @param fonts: dict specifying the font families to use
        '''
        # Defaults for various formatting tags        
        object.__setattr__(self, 'options', options)
        self.logger = logger        
        self.fonts = fonts #: dict specifying font families to use
        # Memory 
        self.scaled_images = {}    #: Temporary files with scaled version of images        
        self.rotated_images = {}  #: Temporary files with rotated version of images        
        self.text_styles      = []#: Keep track of already used textstyles
        self.block_styles     = []#: Keep track of already used blockstyles
        self.images  = {}     #: Images referenced in the HTML document
        self.targets = {}         #: <a name=...> and id elements
        self.links   = {}         #: <a href=...> elements        
        self.processed_files = []
        self.unused_target_blocks = [] #: Used to remove extra TextBlocks
        self.link_level  = 0  #: Current link level
        self.memory = []        #: Used to ensure that duplicate CSS unhandled erros are not reported
        self.tops = {}          #: element representing the top of each HTML file in the LRF file
        self.previous_text = '' #: Used to figure out when to lstrip
        # Styles 
        self.blockquote_style = book.create_block_style(sidemargin=60, 
                                                        topskip=20, footskip=20)
        self.unindented_style = book.create_text_style(parindent=0)
        
                
        # Set by table processing code so that any <a name> within the table 
        # point to the previous element
        self.anchor_to_previous = None 
        self.in_table = False
        # List processing
        self.list_level = 0
        self.list_indent = 20
        self.list_counter = 1
        
        self.book = book                #: The Book object representing a BBeB book
        self.start_on_file(path, is_root=True)
        
    def is_baen(self, soup):
        return bool(soup.find('meta', attrs={'name':'Publisher', 
                        'content':re.compile('Baen', re.IGNORECASE)}))
    
    def start_on_file(self, path, is_root=True, link_level=0):
        path = os.path.abspath(path)
        os.chdir(os.path.dirname(path))
        self.file_name = os.path.basename(path)
        self.logger.info('Processing %s\n\tParsing HTML...', self.file_name)
        sys.stdout.flush()
        nmassage = copy.copy(BeautifulSoup.MARKUP_MASSAGE)
        nmassage.extend(HTMLConverter.MARKUP_MASSAGE)
        if self.baen:
            nmassage.extend(HTMLConverter.BAEN)
            
        raw = open(self.file_name, 'rb').read()
        if self.pdftohtml:
            nmassage.extend(HTMLConverter.PDFTOHTML)
            raw = unicode(raw, 'utf8', 'replace')
        soup = BeautifulSoup(raw, 
                         convertEntities=BeautifulSoup.HTML_ENTITIES,
                         markupMassage=nmassage)
        if not self.baen and self.is_baen(soup):
            self.baen = True
            self.logger.info('Baen file detected. Re-parsing...')
            return self.start_on_file(path, is_root=is_root, link_level=link_level)
        self.logger.info('\tConverting to BBeB...')
        sys.stdout.flush()        
        self.current_page = None
        self.current_para = None
        self.current_style = {}
        self.page_break_found = False
        match = self.PAGE_BREAK_PAT.search(unicode(soup))
        if match and not re.match('avoid', match.group(1), re.IGNORECASE):
            self.page_break_found = True
        self.css = HTMLConverter.CSS.copy()
        self.target_prefix = path
        self.links[path] = []
        self.previous_text = '\n'
        self.tops[path] = self.parse_file(soup, is_root)
        self.processed_files.append(path)
        self.process_links(is_root, path, link_level=link_level)
            
        
    def parse_css(self, style):
        """
        Parse the contents of a <style> tag or .css file.
        @param style: C{str(style)} should be the CSS to parse.
        @return: A dictionary with one entry per selector where the key is the
        selector name and the value is a dictionary of properties
        """
        sdict = dict()
        style = re.sub('/\*.*?\*/', '', style) # Remove /*...*/ comments
        for sel in re.findall(HTMLConverter.SELECTOR_PAT, style):
            for key in sel[0].split(','):
                key = key.strip().lower()
                val = self.parse_style_properties(sel[1])
                if key in sdict:
                    sdict[key].update(val)
                else:
                    sdict[key] = val
        return sdict

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
                key = str(l[0].strip()).lower()
                val = l[1].strip()
                prop [key] = val
        return prop

    def tag_css(self, tag, parent_css={}):
        """
        Return a dictionary of style properties applicable to Tag tag.
        """
        def merge_parent_css(prop, pcss):
            temp = {}
            for key in pcss.keys():
                chk = key.lower()
                # float should not be inherited according to the CSS spec
                # however we need to as we don't do alignment at a block level.
                # float is removed by the process_alignment function.
                if chk.startswith('font') or chk == 'text-align' or \
                chk == 'float' or chk == 'white-space': 
                    temp[key] = pcss[key]
            prop.update(temp)
            
        prop = dict()
        tagname = tag.name.lower()
        if parent_css:
            merge_parent_css(prop, parent_css)
        if tag.has_key("align"):
            prop["text-align"] = tag["align"]
        if self.css.has_key(tagname):
            prop.update(self.css[tagname])
        if tag.has_key("class"):
            cls = tag["class"].lower()            
            for classname in ["."+cls, tagname+"."+cls]:
                if self.css.has_key(classname):
                    prop.update(self.css[classname])
        if tag.has_key("style"):
            prop.update(self.parse_style_properties(tag["style"]))    
        return prop
        
    def parse_file(self, soup, is_root):
        def get_valid_block(page):
            for item in page.contents:
                if isinstance(item, (Canvas, TextBlock, ImageBlock, RuledLine)):
                    if isinstance(item, TextBlock) and not item.contents:
                        continue
                    return item
        previous = self.book.last_page()
        self.current_page = self.book.create_page()
        self.current_block = self.book.create_text_block()
        self.current_para = Paragraph()
        if self.cover and is_root:
            self.add_image_page(self.cover)
        top = self.current_block
        
        self.process_children(soup, {})
        
        if self.current_para and self.current_block:
            self.current_para.append_to(self.current_block)
        if self.current_block and self.current_page:
            self.current_block.append_to(self.current_page)
        if self.current_page and self.current_page.has_text():
            self.book.append(self.current_page)
        
        if not top.parent or not top.contents:
            if not previous:
                try:
                    previous = self.book.pages()[0]
                except IndexError:                
                    raise ConversionError, self.file_name + ' does not seem to have any content'
                top = get_valid_block(previous)
                if not top or not top.parent:
                    raise ConversionError, self.file_name + ' does not seem to have any content'
                return top
                
            found = False
            for page in self.book.pages():
                if page == previous:
                    found = True
                    continue
                if found:
                    top = get_valid_block(page)
                    if not top:
                        continue
                    break
            
            if not top or not top.parent:
                raise ConversionError, 'Could not parse ' + self.file_name
        return top
            
    def create_link(self, children, tag):
        para = None
        for i in range(len(children)-1, -1, -1):
            if isinstance(children[i], Span):
                para = children[i]
                break
        if para is None:
            raise ConversionError('Failed to parse link %s'%(tag,))
        text = self.get_text(tag, 1000)
        if not text:
            text = 'Link'
            img = tag.find('img')
            if img:
                try:
                    text = img['alt']
                except KeyError:
                    pass
        
        url = urlparse(tag['href'])
        return {'para':para, 'text':text, 'url':url}
        
    
    def get_text(self, tag, limit=None):
            css = self.tag_css(tag)
            if (css.has_key('display') and css['display'].lower() == 'none') or \
               (css.has_key('visibility') and css['visibility'].lower() == 'hidden'):
                return ''
            text = u''
            for c in tag.contents:
                if limit != None and len(text) > limit:
                    break
                if isinstance(c, HTMLConverter.IGNORED_TAGS):
                    return u''
                if isinstance(c, NavigableString):
                    text += unicode(c)                
                elif isinstance(c, Tag):
                    if c.name.lower() == 'img' and c.has_key('alt'):
                        text += c['alt']
                        return text
                    text += self.get_text(c)
            return text
    
    def process_links(self, is_root, selfpath, link_level=0):
        def add_toc_entry(text, target):
            # TextBlocks in Canvases have a None parent or an Objects Parent
            if target.parent != None and \
               hasattr(target.parent, 'objId'): 
                self.book.addTocEntry(ascii_text, tb)
            else:
                self.logger.debug("Cannot add link %s to TOC", ascii_text)
                
        
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
        
        cwd = os.getcwd()
        for link in self.links[selfpath]:
            try:
                para, text, purl = link['para'], link['text'], link['url']
                # Needed for TOC entries due to bug in LRF
                ascii_text = text.encode('ascii', 'replace')
                if purl[1]: # Not a link to a file on the local filesystem
                    continue
                basepath, fragment = unquote(purl[2]), purl[5]
                if not basepath:
                    basepath = selfpath
                path = os.path.abspath(basepath)
                
                if link_level < self.link_levels and path not in self.processed_files:                
                    try:
                        self.start_on_file(path, is_root=False, link_level=link_level+1)
                    except Exception:
                        self.logger.warning('Unable to process %s', path)
                        if self.verbose:
                            self.logger.exception(' ')
                        continue
                    finally:
                        os.chdir(cwd)            
                if path+fragment in self.targets.keys():                    
                    tb = get_target_block(path+fragment, self.targets)
                else:
                    try:
                        tb = self.tops[path]
                    except KeyError:
                        return
                if is_root:
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
            finally:
                os.chdir(cwd)
            
    def end_page(self):
        """
        End the current page, ensuring that any further content is displayed
        on a new page.
        """
        self.current_para.append_to(self.current_block)
        self.current_para = Paragraph()
        self.current_block.append_to(self.current_page)
        self.current_block = self.book.create_text_block()
        if self.current_page.has_text(): 
            self.book.append(self.current_page)
            self.current_page = self.book.create_page()
        
        
    def add_image_page(self, path):
        if os.access(path, os.R_OK):
            self.end_page()            
            page = self.book.create_page(evensidemargin=0, oddsidemargin=0, 
                                         topmargin=0, textwidth=self.profile.screen_width,
                                         headheight=0, headsep=0, footspace=0,
                                         footheight=0, 
                                         textheight=self.profile.screen_height)
            if not self.images.has_key(path):
                self.images[path] = ImageStream(path)
            ib = ImageBlock(self.images[path], x1=self.profile.screen_width,
                            y1=self.profile.screen_height, blockwidth=self.profile.screen_width,
                            blockheight=self.profile.screen_height)
            page.append(ib)
            self.book.append(page)
    
    def process_children(self, ptag, pcss):
        """ Process the children of ptag """
        # Need to make a copy of contents as when
        # extract is called on a child, it will
        # mess up the iteration.
        contents = [i for i in ptag.contents]
        for c in contents:
            if isinstance(c, HTMLConverter.IGNORED_TAGS):
                continue
            elif isinstance(c, Tag):
                self.parse_tag(c, pcss)
            elif isinstance(c, NavigableString):
                self.add_text(c, pcss)
        if not self.in_table:
            ptag.extract()
                    
    def process_alignment(self, css):
        '''
        Create a new TextBlock only if necessary as indicated by css
        @type css: dict
        '''
        align = 'head'
        if css.has_key('text-align'):
            val = css['text-align'].lower()             
            if val in ["right", "foot"]:
                align = "foot"
            elif val == "center":
                align = "center"
        if css.has_key('float'):
            val = css['float'].lower()
            if val == 'left':
                align = 'head'
            if val == 'right':
                align = 'foot'
            css.pop('float')
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
    
    def add_text(self, tag, css, force_span_use=False):
        '''
        Add text to the current paragraph taking CSS into account.
        @param tag: Either a BeautifulSoup tag or a string
        @param css: A dict
        '''
        src = tag.string if hasattr(tag, 'string') else tag
        src = src.replace('\r\n', '\n').replace('\r', '\n')
        collapse_whitespace = not css.has_key('white-space') or css['white-space'] != 'pre'
        if self.process_alignment(css) and collapse_whitespace:
            # Dont want leading blanks in a new paragraph
            src = src.lstrip()
        
        def append_text(src):
            fp, key, variant = self.font_properties(css)
            for pat, repl in self.__class__.ENTITY_RULES:
                src = pat.sub(repl, src)
            src = src.replace(u'\xa0', ' ')# nbsp is replaced with \xa0 by BeatifulSoup
            normal_font_size = int(fp['fontsize'])
            if variant == 'small-caps':
                dump = Span(fontsize=normal_font_size-30)
                temp = []
                for c in src:
                    if c.isupper():
                        if temp:
                            dump.append(''.join(temp))
                            temp = []
                        dump.append(Span(c, fontsize=normal_font_size))
                    else:
                        temp.append(c.upper())
                src = dump                
                if temp:
                    src.append(''.join(temp))
            
            
            if key in ['italic', 'bi']:
                already_italic = False
                for fonts in self.fonts.values():
                    it = fonts['italic'][1] if fonts.has_key('italic') else ''
                    bi = fonts['bi'][1] if fonts.has_key('bi') else ''
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
                
            elem = Span(text=src, **fp) if (fp or force_span_use) else src
            self.current_para.append(elem)
        
        
        if collapse_whitespace:
            src = re.sub(r'\s{1,}', ' ', src)
            if len(self.previous_text) != len(self.previous_text.rstrip()):
                src = src.lstrip()
            if len(src):
                self.previous_text = src
                append_text(src)    
        else:
            srcs = src.split('\n')
            for src in srcs:
                if src:
                    append_text(src)
                    if len(srcs) > 1:                
                        self.line_break()
        
    def line_break(self):
        self.current_para.append(CR())
        self.previous_text = '\n'
        
    def end_current_para(self):
        ''' 
        End current paragraph with a paragraph break after it. If the current
        paragraph has no non whitespace text in it do nothing.
        '''
        if not self.current_para.has_text():
            return
        if self.current_para.contents:
            self.current_block.append(self.current_para)
            self.current_para = Paragraph()
        if self.current_block.contents and \
            not isinstance(self.current_block.contents[-1], CR):
            self.current_block.append(CR())
            
    def end_current_block(self):
        self.current_para.append_to(self.current_block)
        self.current_block.append_to(self.current_page)
        self.current_para = Paragraph()
        self.current_block = self.book.create_text_block(textStyle=self.current_block.textStyle,
                                                         blockStyle=self.current_block.blockStyle)
    
    def process_image(self, path, tag_css, width=None, height=None, dropcaps=False):
        original_path = path
        if self.rotated_images.has_key(path):
            path = self.rotated_images[path].name
        if self.scaled_images.has_key(path):
            path = self.scaled_images[path].name         
        
        try:
            im = PILImage.open(path)
            encoding = im.format
            if encoding:
                encoding = encoding.upper()
                if encoding == 'JPG':
                    encoding = 'JPEG'
        except IOError, err:
            self.logger.warning('Unable to process image: %s\n%s', original_path, err)
            return

        
        if width == None or height == None:            
            width, height = im.size
            
        factor = 720./self.profile.dpi
        
        def scale_image(width, height):
            pt = PersistentTemporaryFile(suffix='.jpeg')
            try:
                im.resize((int(width), int(height)), PILImage.ANTIALIAS).convert('RGB').save(pt, 'JPEG')
                pt.close()
                self.scaled_images[path] = pt
                encoding = 'JPEG'
                return pt.name
            except IOError: # PIL chokes on interlaced PNG images
                self.logger.warning('Unable to process interlaced PNG %s', path)
                return None
        
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
            if not self.images.has_key(path):
                self.images[path] = ImageStream(path)
            im = Image(self.images[path], x0=0, y0=0, x1=width, y1=height,\
                               xsize=width, ysize=height)
            line_height = (int(self.current_block.textStyle.attrs['baselineskip']) + 
                            int(self.current_block.textStyle.attrs['linespace']))//10
            line_height *= self.profile.dpi/72.
            lines = int(ceil(float(height)/line_height))
            dc = DropCaps(lines)
            dc.append(Plot(im, xsize=ceil(width*factor), ysize=ceil(height*factor)))
            self.current_para.append(dc)            
            return
            
        if not self.disable_autorotation and width > pwidth and width > height:
            pt = PersistentTemporaryFile(suffix='.jpeg')
            try:
                im = im.rotate(90)
                im.convert('RGB').save(pt, 'JPEG')
                path = pt.name
                encoding = 'JPEG'
                self.rotated_images[path] = pt
                width, height = im.size
            except IOError: # PIL chokes on interlaced PNG files and since auto-rotation is not critical we ignore the error
                self.logger.debug('Unable to process interlaced PNG %s', original_path)                 
            finally:
                pt.close()
        
        if height > pheight:
            corrf = pheight/(1.*height)
            width, height = floor(corrf*width), pheight-1                        
            if width > pwidth:
                corrf = (pwidth)/(1.*width)
                width, height = pwidth-1, floor(corrf*height)
            path = scale_image(width, height)
        if width > pwidth:
            corrf = pwidth/(1.*width)
            width, height = pwidth-1, floor(corrf*height)
            if height > pheight:
                corrf = (pheight)/(1.*height)
                width, height = floor(corrf*width), pheight-1                        
            path = scale_image(width, height)
        width, height = int(width), int(height)
        
        if not path:
            return        
        
        if not self.images.has_key(path):
            try:
                self.images[path] = ImageStream(path, encoding=encoding)
            except LrsError, err:
                self.logger.warning('Could not process image: %s\n%s', original_path, err)
                return
            
        im = Image(self.images[path], x0=0, y0=0, x1=width, y1=height,\
                               xsize=width, ysize=height)                    
        
        self.process_alignment(tag_css)
        
        if max(width, height) <= min(pwidth, pheight)/5.:                    
            self.current_para.append(Plot(im, xsize=ceil(width*factor), 
                                          ysize=ceil(height*factor)))
        elif height <= int(floor((2/3.)*pheight)): 
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
            self.current_page.append(Canvas(width=pwidth,
                                            height=height))
            left = int(floor((pwidth - width)/2.))
            self.current_page.contents[-1].put_object(
                            ImageBlock(self.images[path], xsize=pwidth,
                                       ysize=pheight, x1=pwidth, y1=pheight,
                                       blockwidth=pwidth, blockheight=pheight),
                            left, 0)
    
    def process_page_breaks(self, tag, tagname, tag_css):
        if 'page-break-before' in tag_css.keys():
            if tag_css['page-break-before'].lower() != 'avoid':
                self.end_page()
            tag_css.pop('page-break-before')
        end_page = False
        if 'page-break-after' in tag_css.keys() and \
           tag_css['page-break-after'].lower() != 'avoid':
            end_page = True
            tag_css.pop('page-break-after')
        if (self.force_page_break_attr[0].match(tagname) and \
           tag.has_key(self.force_page_break_attr[1]) and \
           self.force_page_break_attr[2].match(tag[self.force_page_break_attr[1]])) or \
           self.force_page_break.match(tagname):
            self.end_page()
            self.page_break_found = True
        if not self.page_break_found and self.page_break.match(tagname):
            if len(self.current_page.contents) > 3:
                self.end_page()
                self.logger.debug('Forcing page break at %s', tagname)
        return end_page
    
    def block_properties(self, tag_css):
        ans = {}
        for key in ('topskip', 'footskip', 'sidemargin'):
            ans[key] = self.book.defaultBlockStyle.attrs[key]
        
        src = [None for i in range(4)]         
        if tag_css.has_key('padding'):
            msrc = tag_css['padding'].split()
            for i in range(len(msrc)):
                src[i] = msrc[i]
        i = 0
        for c in ('top', 'right', 'bottom', 'left'):
            if tag_css.has_key('padding-'+c):
                src[i] = tag_css['padding-'+c]
            i += 1
        
        t = {}
        t['topskip'], t['footskip'], t['sidemargin'] = src[0], src[2], src[3]
        for key in ('topskip', 'footskip', 'sidemargin'):
            if t[key] is not None:
                ans[key] = self.unit_convert(t[key])
                
        return ans
    
    def font_properties(self, css):
        '''
        Convert the font propertiess in css to the Xylog equivalents. If the CSS
        does not contain a particular font property, the default from self.book.defaultTextSytle
        is used. 
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
            normal = 100 #10*pts
            ans = self.unit_convert(val, pts=True)
            if ans:
                if ans < 0:
                    ans += normal
                    if ans < 0:
                        ans = normal
            else:
                if "xx-small" in val:
                    ans = 40
                elif "x-small" in val:
                    ans = 60
                elif "small" in val:
                    ans = 80
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
        
        key = font_key(family, style, weight)
        if self.fonts[family].has_key(key):
            t['fontfacename'] = self.fonts[family][key][1]
        else:
            t['fontfacename'] = self.fonts[family]['normal'][1]
        if key in ['bold', 'bi']:
                t['fontweight'] = 700
        
        fs = int(t['fontsize']) 
        if fs > 120:
            t['wordspace'] = int(fs/4.)
        t['baselineskip'] = fs + 20
        return t, key, variant
        
    def unit_convert(self, val, pts=False):
        '''
        Tries to convert html units in C{val} to pixels.
        Assumes: 1em = 100% = 10pts  
        @param pts: If True return 10*pts instead of pixels.
        @return: The number of pixels (an int) if successful. Otherwise, returns None.        
        '''
        dpi = self.profile.dpi
        result = None
        try:
            result = int(val)
        except ValueError:
            pass
        m = re.match("\s*(-*[0-9]*\.?[0-9]*)\s*(%|em|px|mm|cm|in|pt|pc)", val)
        if m is not None:
            unit = float(m.group(1))
            if m.group(2) == '%':
                normal = self.unit_convert('10pt')
                result = int((unit/100.0)*normal)
            elif m.group(2) == 'px':
                result =  int(unit)
            elif m.group(2) == 'in':
                result =  int(unit * dpi)
            elif m.group(2) == 'pt':
                result = int(unit * dpi/72.)
            elif m.group(2)== 'em':
                result = int(unit * (dpi/72.) * 10)
            elif m.group(2)== 'pc':
                result =  int(unit * (dpi/72.) * 12)
            elif m.group(2)== 'mm':
                result =  int(unit * 0.04 * (dpi/72.))
            elif m.group(2)== 'cm':
                result =  int(unit * 0.4 * (dpi/72.))
        if pts:
            if result is not None:
                result = int((float(result)/dpi)*720)
        return result
        
    def text_properties(self, tag_css):
        indent = self.book.defaultTextStyle.attrs['parindent']
        if tag_css.has_key('text-indent'):
            indent = self.unit_convert(str(tag_css['text-indent']), pts=True)
            if not indent:
                indent = 0
            if hasattr(self, 'minimum_indent') and indent > 0 and indent < self.minimum_indent:
                indent = self.minimum_indent
                
        fp = self.font_properties(tag_css)[0]
        fp['parindent'] = indent
        return fp
        
    
    def process_block(self, tag, tag_css, tkey):        
        ''' Ensure padding and text-indent properties are respected '''
        text_properties = self.text_properties(tag_css)
        block_properties = self.block_properties(tag_css)
        
        if properties_different(self.current_block.blockStyle.attrs, block_properties) or \
           properties_different(self.current_block.textStyle.attrs, text_properties):
            ts = self.current_block.textStyle.copy()
            ts.attrs.update(text_properties)
            bs = self.current_block.blockStyle.copy()
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
            self.targets[tkey] = self.current_block
    
    def parse_tag(self, tag, parent_css):
        try:
            tagname = tag.name.lower()
        except AttributeError:
            if not isinstance(tag, HTMLConverter.IGNORED_TAGS):
                self.add_text(tag, parent_css)
            return
        tag_css = self.tag_css(tag, parent_css=parent_css)
        try: # Skip element if its display attribute is set to none
            if tag_css['display'].lower() == 'none' or \
               tag_css['visibility'].lower() == 'hidden':
                return
        except KeyError:
            pass
        end_page = self.process_page_breaks(tag, tagname, tag_css)
        
        if tagname in ["title", "script", "meta", 'del', 'frameset']:            
            pass
        elif tagname == 'a' and self.link_levels >= 0:
            if tag.has_key('href') and not self.link_exclude.match(tag['href']):
                purl = urlparse(tag['href'])
                path = unquote(purl[2])
                ext = os.path.splitext(path)[1]
                if ext: ext = ext[1:].lower()
                if path and os.access(path, os.R_OK) and ext and \
                                        ext in ['png', 'jpg', 'bmp', 'jpeg']:
                    self.process_image(path, tag_css)
                else:
                    text = self.get_text(tag, limit=1000)
                    if not text.strip():
                        text = "Link"
                    self.add_text(text, tag_css, force_span_use=True)
                    self.links[self.target_prefix].append(self.create_link(self.current_para.contents, tag))
                    if tag.has_key('id') or tag.has_key('name'):
                        key = 'name' if tag.has_key('name') else 'id'
                        self.targets[self.target_prefix+tag[key]] = self.current_block
            elif tag.has_key('name') or tag.has_key('id'):
                key = 'name' if tag.has_key('name') else 'id'
                name = tag[key].replace('#', '')
                if self.anchor_to_previous:
                    self.process_children(tag, tag_css)
                    for c in self.anchor_to_previous.contents:
                        if isinstance(c, (TextBlock, ImageBlock)):
                            self.targets[self.target_prefix+tag[key]] = c
                            return
                    tb = self.book.create_text_block()
                    tb.Paragraph(" ")
                    self.anchor_to_previous.append(tb)
                    self.targets[self.target_prefix+name] = tb                    
                    return
                previous = self.current_block
                self.process_children(tag, tag_css)
                target = None
                
                if self.current_block == previous:                    
                    if self.current_para.has_text():
                        self.current_para.append_to(self.current_block)
                        self.current_para = Paragraph()
                        target = self.current_block                 
                    else: # Empty <a> element
                        self.current_page.append(self.current_block)                        
                        self.current_block = self.book.create_text_block(
                                textStyle=self.current_block.textStyle,
                                blockStyle=self.current_block.blockStyle)
                        target = self.book.create_text_block()
                        self.current_page.append(target)
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
                    if target == None:
                        if self.current_block.has_text():
                            target = self.current_block
                        else:
                            target = BlockSpace()
                            self.current_page.append(target)
                self.targets[self.target_prefix+name] = target                            
        elif tagname == 'img':
            if tag.has_key('src') and os.access(unquote(tag['src']), os.R_OK):
                path = os.path.abspath(unquote(tag['src']))
                width, height = None, None
                try:
                    width = int(tag['width'])
                    height = int(tag['height'])
                except:
                    pass
                dropcaps = tag.has_key('class') and tag['class'] == 'libprs500_dropcaps'
                self.process_image(path, tag_css, width, height, dropcaps=dropcaps)
            else:
                self.logger.debug("Failed to process: %s", str(tag))
        elif tagname in ['style', 'link']:
            def update_css(ncss):
                for key in ncss.keys():
                    if self.css.has_key(key):
                        self.css[key].update(ncss[key])
                    else:
                        self.css[key] = ncss[key]
            ncss = {}
            if tagname == 'style':
                for c in tag.contents:
                    if isinstance(c, NavigableString):
                        ncss.update(self.parse_css(str(c)))
            elif tag.has_key('type') and tag['type'] == "text/css" \
                    and tag.has_key('href'):
                purl = urlparse(tag['href'])
                path = unquote(purl[2])                
                try:
                    f = open(path, 'rb')
                    src = f.read()
                    f.close()
                    match = self.PAGE_BREAK_PAT.search(src) 
                    if match and not re.match('avoid', match.group(1), re.IGNORECASE):
                        self.page_break_found = True
                    ncss = self.parse_css(src)
                except IOError:
                    pass
            if ncss:
                update_css(ncss)            
        elif tagname == 'pre':
            self.end_current_para()
            self.end_current_block()
            self.current_block = self.book.create_text_block()
            self.current_block.textStyle.attrs['parindent'] = '0'
            if tag.contents:
                c = tag.contents[0]
                if isinstance(c, NavigableString):
                    c = str(c).replace('\r\n', '\n').replace('\r', '\n')
                    if c.startswith('\n'):
                        c = c[1:]
                        tag.contents[0] = NavigableString(c)
            self.process_children(tag, tag_css)
            self.end_current_block()
        elif tagname in ['ul', 'ol', 'dl']:
            self.list_level += 1
            if tagname == 'ol':
                old_counter = self.list_counter
                self.list_counter = 1
            prev_bs = self.current_block.blockStyle
            self.end_current_block()
            attrs = self.current_block.blockStyle.attrs
            attrs = attrs.copy()
            attrs['sidemargin'] = self.list_indent*self.list_level
            bs = self.book.create_block_style(**attrs)
            self.current_block = self.book.create_text_block(
                                        blockStyle=bs,
                                        textStyle=self.unindented_style)
            self.process_children(tag, tag_css)
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
                prepend = str(self.list_counter)+'. ' if in_ol else u'\u2022' + ' '
                self.current_para.append(Span(prepend))
                self.process_children(tag, tag_css)
                if in_ol:
                    self.list_counter += 1
            else:
                self.process_children(tag, tag_css)    
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
            self.process_children(tag, tag_css)
            self.current_para.append_to(self.current_block)
            self.current_block.append_to(self.current_page)
            self.current_para = Paragraph()
            self.current_block = self.book.create_text_block(textStyle=pb.textStyle,
                                                             blockStyle=pb.blockStyle)
        elif tagname in ['sub', 'sup']:
            text = self.get_text(tag)
            elem = Sub if tagname == 'sub' else Sup 
            self.current_para.append(elem(text))
                                
        elif tagname in ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            tkey = None
            if self.anchor_ids and tag.has_key('id'):                
                target = self.book.create_text_block(textStyle=self.current_block.textStyle,
                                                     blockStyle=self.current_block.blockStyle)
                tkey = self.target_prefix+tag['id']
                self.targets[tkey] = target
                
                if len(self.current_block.contents) > 2:
                    self.end_current_block()
                    self.current_page.append(target)
                    self.unused_target_blocks.append(target)
                else:
                    self.targets[tkey] = self.current_block
                    self.current_block.must_append = True
            src = self.get_text(tag, limit=1000)
            if not self.disable_chapter_detection and tagname.startswith('h'):
                if self.chapter_regex.search(src):
                    self.logger.debug('Detected chapter %s', src)
                    self.end_page()
                    self.page_break_found = True
            if not tag.contents:
                self.current_block.append(CR())
                self.current_block.must_append = True
                return
            self.process_block(tag, tag_css, tkey)
            if self.current_para.contents:
                self.current_block.append(self.current_para)            
            if self.current_block.contents:
                self.current_block.append(CR())
            self.previous_text = '\n'
            self.current_para = Paragraph()
            
            self.process_children(tag, tag_css)
            if self.current_para.contents:
                self.current_block.append(self.current_para)
            self.current_para = Paragraph()
            if tagname.startswith('h') or self.blank_after_para:
                self.current_block.append(CR())                            
        elif tagname in ['b', 'strong', 'i', 'em', 'span', 'tt', 'big', 'code', 'cite']:
            self.process_children(tag, tag_css)
        elif tagname == 'font':
            if tag.has_key('face'):
                tag_css['font-family'] = tag['face']
            self.process_children(tag, tag_css)
        elif tagname in ['br']:
            self.line_break()
            self.previous_text = '\n'
        elif tagname in ['hr', 'tr']: # tr needed for nested tables
            self.end_current_para()
            self.line_break()
            self.end_current_block()
            if tagname == 'hr':
                self.current_page.RuledLine(linelength=int(self.current_page.pageStyle.attrs['textwidth']))
            self.previous_text = '\n'
            self.process_children(tag, tag_css)
        elif tagname == 'td': # Needed for nested tables
            self.current_para.append(' ')
            self.previous_text = ' '
            self.process_children(tag, tag_css)
        elif tagname == 'table' and not self.ignore_tables and not self.in_table:
            tag_css = self.tag_css(tag) # Table should not inherit CSS
            try:
                self.process_table(tag, tag_css)
            except Exception, err:
                self.logger.warning('An error occurred while processing a table: %s', str(err))
                self.logger.debug('', exc_info=True)
                self.logger.warning('Ignoring table markup for table:\n%s', str(tag)[:300])
                self.in_table = False
                self.process_children(tag, tag_css)
            finally:                
                tag.extract()
        else:
            self.process_children(tag, tag_css)        
        if end_page:
                self.end_page()
                    
    def process_table(self, tag, tag_css):
        self.end_current_block()
        self.current_block = self.book.create_text_block()
        rowpad = 10
        table = Table(self, tag, tag_css, rowpad=rowpad, colpad=10)
        canvases = []
        ps = self.current_page.pageStyle.attrs
        for block, xpos, ypos, delta in table.blocks(int(ps['textwidth']), int(ps['textheight'])):
            if not block:
                if ypos > int(ps['textheight']):
                    raise Exception, 'Table has cell that is too large' 
                canvases.append(Canvas(int(self.current_page.pageStyle.attrs['textwidth']), ypos+rowpad,
                        blockrule='block-fixed'))
            else:
                canvases[-1].put_object(block, xpos + int(delta/2.), ypos)
            
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
        for _file in self.scaled_images.values() + self.rotated_images.values():   
            _file.__del__()

def process_file(path, options, logger=None):
    if re.match('http://|https://', path):
        raise ConversionError, 'You have to save the website %s as an html file first and then run html2lrf on it.'%(path,)
    if logger is None:
        level = logging.DEBUG if options.verbose else logging.INFO
        logger = logging.getLogger('html2lrf')
        setup_cli_handlers(logger, level)
    cwd = os.getcwd()
    default_title = filename_to_utf8(os.path.splitext(os.path.basename(path))[0])
    dirpath = os.path.dirname(path)
    try:
        cpath, tpath = '', '' 
        try_opf(path, options, logger)
        if options.cover:            
            cpath = os.path.join(dirpath, os.path.basename(options.cover))
            if not os.path.exists(cpath):
                cpath = os.path.abspath(os.path.expanduser(options.cover))
            options.cover = cpath
            if os.access(options.cover, os.R_OK):        
                from libprs500.devices.prs500.driver import PRS500                
                im = PILImage.open(os.path.join(cwd, cpath))
                cim = im.resize((options.profile.screen_width, 
                                 options.profile.screen_height), 
                                PILImage.BICUBIC).convert('RGB')
                cf = PersistentTemporaryFile(prefix=__appname__+"_", suffix=".jpg")
                cf.close()                
                cim.save(cf.name)
                cpath = cf.name
                th = PRS500.THUMBNAIL_HEIGHT
                tim = im.resize((int(0.75*th), th), PILImage.ANTIALIAS).convert('RGB')
                tf = PersistentTemporaryFile(prefix="html2lrf_", suffix=".jpg")
                tf.close()
                tim.save(tf.name)
                tpath = tf.name
            else:
                raise ConversionError, 'Cannot read from: %s'% (options.cover,)
        
                    
        if not options.title:
            options.title = default_title
        title = (options.title, options.title_sort)
        author = (options.author, options.author_sort)
        args = dict(font_delta=options.font_delta, title=title, \
                    author=author, sourceencoding='utf8',\
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
            fheader = re.sub(r'([^%]|^)%t','\1' + options.title, fheader)
            fheader = re.sub(r'([^%]|^)%a','\1' + options.author, fheader)
            fheader = re.sub(r'%%a','%a',fheader)
            fheader = re.sub(r'%%t','%t',fheader)                
            header.append(fheader + "  ")            
        book, fonts = Book(options, header=header, **args)
        le = re.compile(options.link_exclude) if options.link_exclude else \
             re.compile('$')
        pb = re.compile(options.page_break, re.IGNORECASE) if options.page_break else \
             re.compile('$')
        fpb = re.compile(options.force_page_break, re.IGNORECASE) if options.force_page_break else \
             re.compile('$')
        options.cover = cpath
        options.force_page_break = fpb
        options.link_exclude = le
        options.page_break = pb
        options.chapter_regex = re.compile(options.chapter_regex, re.IGNORECASE)
        fpba = options.force_page_break_attr.split(',')
        if len(fpba) != 3:
            fpba = ['$', '', '$']
        options.force_page_break_attr = [re.compile(fpba[0], re.IGNORECASE), fpba[1],
                                         re.compile(fpba[2], re.IGNORECASE)]
        if not hasattr(options, 'anchor_ids'):
            options.anchor_ids = True
        conv = HTMLConverter(book, fonts, options, logger, path)
        oname = options.output
        if not oname:
            suffix = '.lrs' if options.lrs else '.lrf'
            name = os.path.splitext(os.path.basename(path))[0] + suffix
            oname = os.path.join(cwd,name)
        oname = os.path.abspath(os.path.expanduser(oname))
        conv.writeto(oname, lrs=options.lrs)
        logger.info('Output written to %s', oname)
        conv.cleanup()
        return oname
    finally:
        os.chdir(cwd)

def try_opf(path, options, logger):
    try:
        opf = glob.glob(os.path.join(os.path.dirname(path),'*.opf'))[0]
    except IndexError:
        return
    opf = OPFReader(open(opf, 'rb'))    
    try:
        title = opf.title        
        if title and not options.title:
            options.title = title
        if options.author == 'Unknown':
            if opf.authors:
                options.author = ', '.join(opf.authors)
            if opf.author_sort:
                options.author_sort = opf.author_sort
        if options.publisher == 'Unknown':
            publisher = opf.publisher
            if publisher:
                options.publisher = publisher
        if not options.category:
            category = opf.category
            if category:
                options.category = category
        if not options.cover:
            cover = opf.cover            
            if cover:
                cover = os.path.join(os.path.dirname(path), cover)
                if os.access(cover, os.R_OK):
                    try:
                        PILImage.open(cover)
                        options.cover = cover
                    except:
                        pass
        if not options.cover:
            for prefix in opf.possible_cover_prefixes():
                if options.cover:
                    break
                for suffix in ['.jpg', '.jpeg', '.gif', '.png', '.bmp']:
                    cpath = os.path.join(os.path.dirname(path), prefix+suffix)
                    try:
                        PILImage.open(cpath)
                        options.cover = cpath
                        break
                    except:
                        continue        
    except Exception:
        logger.exception('Failed to process opf file')
                
def option_parser():
    return lrf_option_parser('''Usage: %prog [options] mybook.html\n\n'''
                    '''%prog converts mybook.html to mybook.lrf''')

def main(args=sys.argv):    
    try:
        parser = option_parser()
        options, args = parser.parse_args(args)    
        if options.output:
            options.output = os.path.abspath(os.path.expanduser(options.output))
        if len(args) != 2:
            parser.print_help()
            return 1
        src = args[1]
        if options.verbose:
            import warnings
            warnings.defaultaction = 'error'
    except Exception, err:
        print >> sys.stderr, err
        return 1
    
    process_file(src, options)
    return 0



if __name__ == '__main__':
    sys.exit(main())