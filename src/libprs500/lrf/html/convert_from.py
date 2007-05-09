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

I am indebted to esperanc for the CSS->Xylog Style conversion routines
and to Falstaff for pylrs.
"""
import os, re, sys, shutil, traceback, copy
from htmlentitydefs import name2codepoint
from urllib import urlopen, unquote
from urlparse import urlparse
from tempfile import mkdtemp
from operator import itemgetter
from math import ceil

from libprs500.lrf.html.BeautifulSoup import BeautifulSoup, Comment, Tag, \
                                             NavigableString, Declaration, ProcessingInstruction
from libprs500.lrf.pylrs.pylrs import Paragraph, CR, Italic, ImageStream, TextBlock, \
                                      ImageBlock, JumpButton, CharButton, \
                                      Bold, Space, Plot, Image, BlockSpace,\
                                      RuledLine
from libprs500.lrf.pylrs.pylrs import Span as _Span
from libprs500.lrf import ConversionError, option_parser, Book
from libprs500 import extract

class Span(_Span):
    replaced_entities = [ 'amp', 'lt', 'gt' , 'ldquo', 'rdquo', 'lsquo', 'rsquo', 'nbsp' ]
    patterns = [ re.compile('&'+i+';') for i in replaced_entities ]
    targets  = [ unichr(name2codepoint[i]) for i in replaced_entities ]
    rules = zip(patterns, targets)
    
    
    @staticmethod
    def unit_convert(val, ref=80):
        """
        Tries to convert html units stored in C{val} to pixels. C{ref} contains
        the reference value for relative units. Returns the number of pixels
        (an int) if successful. Otherwise, returns None.
        Assumes: 1 pixel is 1/4 mm. One em is 10pts
        """
        result = None
        m = re.match("\s*(-*[0-9]*\.?[0-9]*)\s*(%|em|px|mm|cm|in|pt|pc)", val)
        if m is not None:
            unit = float(m.group(1))
            if m.group(2) == '%':
                result = int(unit/100.0*ref)
            elif m.group(2) == 'px':
                result =  int(unit)
            elif m.group(2) == 'in':
                result =  int(unit * 25.4 * 4)
            elif m.group(2) == 'pt':
                result = int(unit * 25.4 * 4 / 72)
            elif m.group(2)== 'em':
                result = int(unit * 25.4 * 4 / 72 * 10)
            elif m.group(2)== 'pc':
                result =  int(unit * 25.4 * 4 / 72 * 12)
            elif m.group(2)== 'mm':
                result =  int(unit * 4)
            elif m.group(2)== 'cm':
                result =  int(unit * 10 * 4)                    
        return result
    
    @staticmethod
    def translate_attrs(d, font_delta=0, memory=None):
        """
        Receives a dictionary of html attributes and styles and returns
        approximate Xylog equivalents in a new dictionary
        """
        def font_weight(val):
            ans = None
            m = re.search("([0-9]+)", val)
            if m:
                ans = str(int(m.group(1)))
            elif val.find("bold") >= 0 or val.find("strong") >= 0:
                ans = "1000"
            return ans
        
        def font_family(val):
            ans = None
            if max(val.find("courier"), val.find("mono"), val.find("fixed"), val.find("typewriter"))>=0:
                ans = "Courier10 BT Roman"
            elif max(val.find("arial"), val.find("helvetica"), val.find("verdana"), 
                 val.find("trebuchet"), val.find("sans")) >= 0:
                ans = "Swis721 BT Roman"
            return ans
        
        def font_size(val):
            ans = None
            unit = Span.unit_convert(val, 14)
            if unit:
                # Assume a 10 pt font (14 pixels) has fontsize 100
                ans = int (unit / 14.0 * 100)
            else:
                if "xx-small" in val:
                    ans = 40
                elif "x-small" in val >= 0:
                    ans = 60
                elif "small" in val:
                    ans = 80
                elif "xx-large" in val:
                    ans = 180
                elif "x-large" in val >= 0:
                    ans = 140
                elif "large" in val >= 0:
                    ans = 120
            if ans is not None: 
                ans += font_delta * 20
                ans = str(ans)
            return ans
        
        t = dict()
        for key in d.keys():
            val = d[key].lower()
            if key == 'font':
                val = val.split()
                val.reverse()
                for sval in val:
                    ans = font_family(sval)
                    if ans:
                        t['fontfacename'] = ans
                    else:
                        ans = font_size(sval)
                        if ans:
                            t['fontsize'] = ans
                        else:
                            ans = font_weight(sval)
                            if ans:
                                t['fontweight'] = ans
            elif key in ['font-family', 'font-name']:                
                ans = font_family(val)                
                if ans:
                    t['fontfacename'] = ans
            elif key == "font-size":
                ans = font_size(val)
                if ans:
                    t['fontsize'] = ans
            elif key == 'font-weight':
                ans = font_weight(val)
                if ans:
                    t['fontweight'] = ans
                    if ans > 140:
                        t['wordspace'] = '50'
            elif key.startswith("margin"):
                if key == "margin":
                    u = []
                    for x in val.split(" "):
                        u.append(Span.unit_convert (x,200)*2)
                    if len(u)==1:
                        u = [u[0], u[0], u[0], u[0]]
                    elif len(u)==2:
                        u = [u[0], u[1], u[0], u[1]]
                    elif len(u)==3:
                        u = [u[0], u[1], u[2], u[1]]
                elif key == "margin-top":
                    u = [Span.unit_convert(val, 200)*2, None, None, None]
                elif key == "margin-right":
                    u = [None, Span.unit_convert(val, 200)*2, None, None]
                elif key == "margin-bottom":
                    u = [None, None, Span.unit_convert(val, 200)*2, None]
                else:
                    u = [None, None, None, Span.unit_convert(val, 200)*2]
                if u[2] is not None:
                    t["parskip"] = str(u[2])
                    t["footskip"] = str(u[2])
                if u[0] is not None:
                    t["topskip"] = str(u[0])
                if u[1] is not None:
                    t["sidemargin"] = str(u[1])                
            else:
                report = True
                if memory != None:
                    if key in memory:
                        report = False
                    else:
                        memory.append(key)
                if report:
                    print >>sys.stderr, 'Unhandled/malformed CSS key:', key, d[key]
        return t        
    
    def __init__(self, ns, css, memory, font_delta=0):
        src = ns.string if hasattr(ns, 'string') else ns
        src = re.sub(r'\s{2,}', ' ', src)  # Remove multiple spaces
        for pat, repl in Span.rules:
            src = pat.sub(repl, src)
        if not src:
            raise ConversionError('No point in adding an empty string to a Span')
        if 'font-style' in css.keys():
            fs = css.pop('font-style')
            if fs.lower() == 'italic':
                src = Italic(src)
        attrs = Span.translate_attrs(css, font_delta=font_delta, memory=memory)
        _Span.__init__(self, text=src, **attrs)
        
        
        
class HTMLConverter(object):
    SELECTOR_PAT  = re.compile(r"([A-Za-z0-9\-\_\:\.]+[A-Za-z0-9\-\_\:\.\s\,]*)\s*\{([^\}]*)\}")
    IGNORED_TAGS  = (Comment, Declaration, ProcessingInstruction)
    # Fix <a /> elements 
    MARKUP_MASSAGE   = [(re.compile("(<\s*[aA]\s+.*\/)\s*>"), 
                         lambda match: match.group(1)+"></a>")]
    # Fix Baen markup
    BAEN_SANCTIFY = [(re.compile(r'<\s*[Aa]\s+id="p[0-9]+"\s+name="p[0-9]+"\s*>\s*<\/[Aa]>'), 
                      lambda match: ''), 
                      (re.compile(r'page-break-before:\s*\w+([\s;\}])'), 
                       lambda match: match.group(1)) ] 
    
    
    
    class Link(object):
        def __init__(self, para, tag):
            self.para = para
            self.tag = tag
            
    # Defaults for various formatting tags        
    css = dict(
            h1     = {"font-size"   :"xx-large", "font-weight":"bold"},
            h2     = {"font-size"   :"x-large", "font-weight":"bold"},
            h3     = {"font-size"   :"large", "font-weight":"bold"},
            h4     = {"font-size"   :"large"},
            h5     = {"font-weight" :"bold"},
            b      = {"font-weight" :"bold"},
            strong = {"font-weight" :"bold"},
            i      = {"font-style"  :"italic"},
            em     = {"font-style"  :"italic"},
            small  = {'font-size'   :'small'},
            pre    = {'font-family' :'monospace' },
            center = {'text-align'  : 'center'}
            )
    processed_files = {} #: Files that have been processed
    
    def __init__(self, book, path, dpi=166, width=575, height=747, 
                 font_delta=0, verbose=False, cover=None,
                 max_link_levels=sys.maxint, link_level=0,
                 is_root=True, baen=False):
        '''
        Convert HTML file at C{path} and add it to C{book}. After creating
        the object, you must call L{self.process_links} on it to create the links and
        then L{self.writeto} to output the LRF/S file.
        
        @param book: The LRF book 
        @type book:  L{libprs500.lrf.pylrs.Book}
        @param path: path to the HTML file to process
        @type path:  C{str}
        @param width: Width of the device on which the LRF file is to be read
        @type width: C{int}
        @param height: Height of the device on which the LRF file is to be read
        @type height: C{int}
        @param font_delta: The amount in pts by which all fonts should be changed
        @type font_delta: C{int}
        @param verbose: Whether processing should be verbose or not
        @type verbose: C{bool}
        @param cover: Path to an image to use as the cover of this book
        @type cover: C{str}
        @param max_link_levels: Number of link levels to process recursively
        @type max_link_levels: C{int}
        @param link_level: Current link level
        @type link_level: C{int}
        @param is_root: True iff this object is converting the root HTML file 
        @type is_root: C{bool}
        '''
        self.page_width = width   #: The width of the page
        self.page_height = height #: The height of the page
        self.dpi         = dpi    #: The DPI of the intended display device
        self.max_link_levels = max_link_levels #: Number of link levels to process recursively
        self.link_level  = link_level  #: Current link level
        self.justification_styles = dict(head=book.create_text_style(align='head'), 
                                         foot=book.create_text_style(align='foot'), 
                                         center=book.create_text_style(align='center'))
        self.blockquote_style = book.create_block_style(sidemargin=60, 
                                                        topskip=20, footskip=20)
        self.unindented_style = book.create_text_style(parindent=0)
        self.images  = {}         #: Images referenced in the HTML document
        self.targets = {}         #: <a name=...> elements
        self.links   = []         #: <a href=...> elements        
        self.files   = {}         #: links that point to other files
        self.links_processed = False #: Whether links_processed has been called on this object
        self.font_delta = font_delta
        self.cover = cover
        self.memory = []          #: Used to ensure that duplicate CSS unhandled erros are not reported
        self.in_ol = False #: Flag indicating we're in an <ol> element
        self.book = book #: The Book object representing a BBeB book
        self.is_root = is_root           #: Are we converting the root HTML file
        self.lstrip_toggle = False #; If true the next add_text call will do an lstrip
        path = os.path.abspath(path)
        os.chdir(os.path.dirname(path))
        self.file_name = os.path.basename(path)
        print "Processing", self.file_name
        print '\tParsing HTML...',
        sys.stdout.flush()
        nmassage = copy.copy(BeautifulSoup.MARKUP_MASSAGE)
        nmassage.extend(HTMLConverter.MARKUP_MASSAGE)
        self.baen = baen
        if baen:
            nmassage.extend(HTMLConverter.BAEN_SANCTIFY)
        self.soup = BeautifulSoup(open(self.file_name, 'r').read(), 
                         convertEntities=BeautifulSoup.HTML_ENTITIES,
                         markupMassage=nmassage)
        print 'done\n\tConverting to BBeB...',
        sys.stdout.flush()
        self.verbose = verbose        
        self.current_page = None
        self.current_para = None
        self.current_style = {}        
        self.parse_file()
        HTMLConverter.processed_files[path] = self
        print 'done'
        
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
                if chk.startswith('font') or chk == 'text-align':
                    temp[key] = pcss[key]
            prop.update(temp)
            
        prop = dict()
        if tag.has_key("align"):
            prop["text-align"] = tag["align"]
        if self.css.has_key(tag.name):
            prop.update(self.css[tag.name])
        if tag.has_key("class"):
            cls = tag["class"].lower()            
            for classname in ["."+cls, tag.name+"."+cls]:
                if self.css.has_key(classname):
                    prop.update(self.css[classname])
        if parent_css:
            merge_parent_css(prop, parent_css)
        if tag.has_key("style"):
            prop.update(self.parse_style_properties(tag["style"]))    
        return prop
        
    def parse_file(self):
        previous = self.book.last_page()
        self.current_page = self.book.create_page()
        self.current_block = self.book.create_text_block()
        self.current_para = Paragraph()
        if self.cover:
            self.add_image_page(self.cover)
        self.top = self.current_block
        
        self.process_children(self.soup, {})
        if self.current_para and self.current_block:
            self.current_para.append_to(self.current_block)
        if self.current_block and self.current_page:
            self.current_block.append_to(self.current_page)
        if self.current_page and self.current_page.has_text():
            self.book.append(self.current_page)
        
        if not self.top.parent:
            if not previous:
                self.top = self.book.pages()[0].contents[0]
            else:
                found = False
                for page in self.book.pages():
                    if page == previous:
                        found = True
                        continue
                    if found:
                        self.top = page.contents[0]
                        break
            if not self.top.parent:
                raise ConversionError, 'Could not parse ' + self.file_name
                    
        
            
    def get_text(self, tag):
            css = self.tag_css(tag)
            if css.has_key('display') and css['display'].lower() == 'none':
                return ''
            text = ''
            for c in tag.contents:
                if isinstance(c, NavigableString):
                    text += str(c)
                elif isinstance(c, Comment):
                    return ''
                elif isinstance(c, Tag):
                    text += self.get_text(c)
            return text
    
    def process_links(self):
        def get_target_block(fragment, targets):
            '''Return the correct block for the <a name> element'''
            bs = targets[fragment]
            if not isinstance(bs, BlockSpace):
                return bs
            ans, found, page = None, False, bs.parent
            for item in page.contents:
                if found:
                    if isinstance(item, (TextBlock, ImageBlock)):
                        ans = item
                        break
                if item == bs:
                    found = True
                    continue
            
            if not ans:
                for i in range(len(page.contents)-1, -1, -1):
                    if isinstance(page.contents[i], (TextBlock, ImageBlock)):
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
        for link in self.links:
            purl = urlparse(link.tag['href'])
            if purl[1]: # Not a link to a file on the local filesystem
                continue
            path, fragment = unquote(purl[2]), purl[5]
            para, tag = link.para, link.tag
            if not path or os.path.basename(path) == self.file_name:
                if fragment in self.targets.keys():
                    tb = get_target_block(fragment, self.targets)
                    if self.is_root:
                        self.book.addTocEntry(self.get_text(tag), tb)                 
                    sys.stdout.flush()
                    jb = JumpButton(tb)
                    self.book.append(jb)
                    cb = CharButton(jb, text=self.get_text(tag))
                    para.contents = []
                    para.append(cb)
            elif self.link_level < self.max_link_levels:                
                if not os.access(path, os.R_OK):
                    if self.verbose:
                        print "Skipping", link
                    continue
                path = os.path.abspath(path)
                if not path in HTMLConverter.processed_files.keys():                    
                    try:                        
                        self.files[path] = HTMLConverter(self.book, path, 
                                     width=self.page_width, height=self.page_height,
                                     dpi=self.dpi,
                                     font_delta=self.font_delta, verbose=self.verbose,
                                     link_level=self.link_level+1,
                                     max_link_levels=self.max_link_levels,
                                     is_root = False, baen=self.baen)
                        HTMLConverter.processed_files[path] = self.files[path]
                    except Exception, err:
                        print >>sys.stderr, 'Unable to process', path, err
                        if self.verbose:
                            traceback.print_exc()
                        continue
                    finally:
                        os.chdir(cwd)
                else:
                    self.files[path] = HTMLConverter.processed_files[path]
                conv = self.files[path]
                if fragment in conv.targets.keys():
                    tb = get_target_block(fragment, conv.targets)
                else:
                    tb = conv.top
                if self.is_root:
                    self.book.addTocEntry(self.get_text(tag), tb)      
                jb = JumpButton(tb)                
                self.book.append(jb)
                cb = CharButton(jb, text=self.get_text(tag))
                para.contents = []
                para.append(cb)                
                    
        self.links_processed = True        
        
        for path in self.files.keys():
            if self.files[path].links_processed:
                continue
            try:
                os.chdir(os.path.dirname(path))
                self.files[path].process_links()
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
                                         topmargin=0, textwidth=self.page_width,
                                         textheight=self.page_height)
            if not self.images.has_key(path):
                self.images[path] = ImageStream(path)
            page.append(ImageBlock(self.images[path]))
            self.book.append(page)
    
    def process_children(self, ptag, pcss):
        """ Process the children of ptag """
        for c in ptag.contents:
            if isinstance(c, HTMLConverter.IGNORED_TAGS):
                continue
            elif isinstance(c, Tag):
                self.parse_tag(c, pcss)
            elif isinstance(c, NavigableString):
                self.add_text(c, pcss)
                    
    def add_text(self, tag, css):
        '''
        Add text to the current paragraph taking CSS into account.
        @param tag: Either a BeautifulSoup tag or a string
        @param css:
        @type css:
        '''
        src = tag.string if hasattr(tag, 'string') else tag 
        if self.lstrip_toggle:
            src = src.lstrip()
            self.lstrip_toggle = False
        if not src.strip():
            self.current_para.append(' ')
        else:
            align = 'head'
            if css.has_key('text-align'):
                val = css['text-align']                
                if val in ["right", "foot"]:
                    align = "foot"
                elif val == "center":
                    align = "center"
                css.pop('text-align')
            if align != self.current_block.textStyle.attrs['align']:
                self.current_para.append_to(self.current_block)
                self.current_block.append_to(self.current_page)
                self.current_block = self.book.create_text_block(
                                    textStyle=self.justification_styles[align])
                self.current_para = Paragraph()
            try:
                self.current_para.append(Span(src, self.sanctify_css(css), self.memory,\
                                              font_delta=self.font_delta))
            except ConversionError, err:
                if self.verbose:
                    print >>sys.stderr, err
        
    def sanctify_css(self, css):
        """ Make css safe for use in a SPAM Xylog tag """
        for key in css.keys():
            test = key.lower()
            if test.startswith('margin') or 'indent' in test or \
               'padding' in test or 'border' in test or 'page-break' in test \
               or test.startswith('mso') or test.startswith('background')\
               or test in ['color', 'display', 'text-decoration', \
                           'letter-spacing', 'text-autospace', 'text-transform', 
                           'font-variant']:
                css.pop(key)
        return css
    
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
        self.current_block = self.book.create_text_block()
    
    def parse_tag(self, tag, parent_css):
        try:
            tagname = tag.name.lower()
        except AttributeError:
            if not isinstance(tag, HTMLConverter.IGNORED_TAGS):
                self.add_text(tag, parent_css)
            return
        tag_css = self.tag_css(tag, parent_css=parent_css)
        try: # Skip element if its display attribute is set to none
            if tag_css['display'].lower() == 'none':
                return
        except KeyError:
            pass
        if 'page-break-before' in tag_css.keys():
            if tag_css['page-break-before'].lower() != 'avoid':
                self.end_page()
            tag_css.pop('page-break-before')
        end_page = False
        if 'page-break-after' in tag_css.keys() and \
           tag_css['page-break-after'].lower() != 'avoid':
            end_page = True
            tag_css.pop('page-break-after')
            
        if tagname in ["title", "script", "meta", 'del', 'frameset']:            
            pass
        elif tagname == 'a' and self.max_link_levels >= 0:
            if tag.has_key('name'):
                previous = self.current_block
                self.process_children(tag, tag_css)
                target = None
                if self.current_block == previous:
                    self.current_para.append_to(self.current_block)
                    self.current_para = Paragraph()
                    if self.current_block.has_text():
                        target = self.current_block                        
                    else:
                        target = BlockSpace()
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
                            target = self.book.create_text_block()
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
                        
                self.targets[tag['name']] = target
            elif tag.has_key('href'):
                purl = urlparse(tag['href'])
                path = purl[2]
                if path and os.path.splitext(path)[1][1:].lower() in \
                    ['png', 'jpg', 'bmp', 'jpeg']:
                    self.add_image_page(path)
                else:
                    self.add_text('Link: '+tag['href'], tag_css)
                    self.links.append(HTMLConverter.Link(self.current_para.contents[-1], tag))
        elif tagname == 'img':
            if tag.has_key('src') and os.access(unquote(tag['src']), os.R_OK):
                width, height = self.page_width, self.page_height
                try:
                    try:
                        from PIL import Image as PILImage
                    except:
                        pass
                    else:
                        im = PILImage.open(unquote(tag['src']))
                        width, height = im.size
                    if tag.has_key('width'):
                        width = int(tag['width'])
                    if tag.has_key('height'):
                        height = int(tag['height'])
                except:
                    pass
                path = os.path.abspath(unquote(tag['src']))
                if not self.images.has_key(path):
                    self.images[path] = ImageStream(path)
                factor = 720./self.dpi
                if max(width, height) <= min(self.page_width, self.page_height)/5.:
                    im = Image(self.images[path], x0=0, y0=0, x1=width, y1=height,\
                               xsize=width, ysize=height)                    
                    self.current_para.append(Plot(im, xsize=ceil(width*factor), 
                                                  ysize=ceil(height*factor)))
                elif max(width, height) <= min(self.page_width, self.page_height)/2.:
                    self.end_current_para()
                    im = Image(self.images[path], x0=0, y0=0, x1=width, y1=height,\
                               xsize=width, ysize=height)
                    self.current_para.append(Plot(im, xsize=width*factor, 
                                                  ysize=height*factor))
                else:
                    self.current_block.append(self.current_para)
                    self.current_page.append(self.current_block)
                    self.current_para = Paragraph()
                    self.current_block = self.book.create_text_block()
                    im = ImageBlock(self.images[path], x1=width, y1=height, 
                                    xsize=width, ysize=height)
                    self.current_page.append(im)                        
            else:
                print >>sys.stderr, "Failed to process:", tag
                
                self.add_image_page(tag['src'])                
        elif tagname in ['style', 'link']:
            if tagname == 'style':
                for c in tag.contents:
                    if isinstance(c,NavigableString):
                        self.css.update(self.parse_css(str(c)))
            elif tag.has_key('type') and tag['type'] == "text/css" \
                    and tag.has_key('href'):
                url = tag['href']
                try:
                    if url.startswith('http://'):
                        f = urlopen(url)
                    else:
                        f = open(unquote(url))
                    self.parse_css(f.read())
                    f.close()
                except IOError:
                    pass
        elif tagname == 'pre':
            self.end_current_para()
            self.current_block.append_to(self.current_page)
            self.current_block = self.book.create_text_block(
                                    textStyle=self.unindented_style)
            src = ''.join([str(i) for i in tag.contents])
            lines = src.split('\n')
            for line in lines:
                try:
                    self.current_para.append(Span(line, tag_css, self.memory))
                    self.current_para.CR()
                except ConversionError:
                    pass
            self.end_current_block()
        elif tagname in ['ul', 'ol']:
            self.in_ol = 1 if tagname == 'ol' else 0
            self.end_current_block()
            self.current_block = self.book.create_text_block(
                                        textStyle=self.unindented_style)
            self.process_children(tag, tag_css)
            self.in_ol = 0
            self.end_current_block()
        elif tagname == 'li':
            prepend = str(self.in_ol)+'. ' if self.in_ol else u'\u2022' + ' '
            if self.current_para.has_text():
                self.current_para.append(CR())
                self.current_block.append(self.current_para)
            self.current_para = Paragraph()
            self.current_para.append(Space(xsize=100))
            self.current_para.append(prepend)
            self.process_children(tag, tag_css)
            if self.in_ol:
                self.in_ol += 1
        elif tagname in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            self.end_current_para()
            if self.current_block.contents:
                self.current_block.append(CR())
            self.process_children(tag, tag_css)
            self.end_current_para()
            self.current_block.append(CR())
        elif tagname == 'blockquote':
            self.current_para.append_to(self.current_block)
            self.current_block.append_to(self.current_page)
            self.current_para = Paragraph()
            self.current_block = self.book.create_text_block(
                                    blockStyle=self.blockquote_style,
                                    textStyle=self.unindented_style)
            self.process_children(tag, tag_css)
            self.end_current_block()
        elif tagname in ['p', 'div']:
            self.end_current_para()
            self.lstrip_toggle = True
            self.process_children(tag, tag_css)
            self.end_current_para()
        elif tagname in ['b', 'strong', 'i', 'em', 'span']:
            self.process_children(tag, tag_css)
        elif tagname == 'font':
            if tag.has_key('face'):
                tag_css['font-family'] = tag['face']
            self.process_children(tag, tag_css)
        elif tagname in ['br', 'tr']:
            self.current_para.append(CR())
            self.process_children(tag, tag_css)
        elif tagname == 'hr':
            self.end_current_para()            
            self.current_block.append(CR())
            self.end_current_block()
            self.current_page.RuledLine(linelength=self.page_width)
        else:            
            self.process_children(tag, tag_css)
        
        if end_page:
                self.end_page()
                    
    def writeto(self, path, lrs=False):
        self.book.renderLrs(path) if lrs else self.book.renderLrf(path)
        

def process_file(path, options):
    cwd = os.getcwd()
    dirpath = None
    try:
        dirpath, path = get_path(path)
        cpath, tpath = options.cover, ''
        if options.cover and os.access(options.cover, os.R_OK):            
            try:
                from PIL import Image as PILImage
                from libprs500.prs500 import PRS500
                from libprs500.ptempfile import PersistentTemporaryFile
                im = PILImage.open(os.path.join(cwd, cpath))
                cim = im.resize((600, 800), PILImage.BICUBIC)
                cf = PersistentTemporaryFile(prefix="html2lrf_", suffix=".jpg")
                cf.close()                
                cim.save(cf.name)
                cpath = cf.name
                th = PRS500.THUMBNAIL_HEIGHT
                tim = im.resize((int(0.75*th), th), PILImage.ANTIALIAS)
                tf = PersistentTemporaryFile(prefix="html2lrf_", suffix=".jpg")
                tf.close()
                tim.save(tf.name)
                tpath = tf.name
            except ImportError:
                print >>sys.stderr, "WARNING: You don't have PIL installed. ",
                'Cover and thumbnails wont work'
                pass
        args = dict(font_delta=options.font_delta, title=options.title, \
                    author=options.author, sourceencoding='utf8',\
                    freetext=options.freetext, category=options.category)
        if tpath:
            args['thumbnail'] = tpath
        header = None
        if options.header:
            header = Paragraph()
            header.append(Bold(options.title))
            header.append(' by ')
            header.append(Italic(options.author))
        book = Book(header=header, **args)
        conv = HTMLConverter(book, path, font_delta=options.font_delta, 
                             cover=cpath, max_link_levels=options.link_levels,
                             baen=options.baen)
        conv.process_links()
        oname = options.output
        if not oname:
            suffix = '.lrs' if options.lrs else '.lrf'
            name = os.path.splitext(os.path.basename(path))[0] + suffix
            oname = os.path.join(cwd,name)
        oname = os.path.abspath(os.path.expanduser(oname))
        conv.writeto(oname, lrs=options.lrs)
        print 'Output written to', oname
    finally:
        os.chdir(cwd)
        if dirpath:
            shutil.rmtree(dirpath, True)
        
def main():
    """ CLI for html -> lrf conversions """
    parser = option_parser("""usage: %prog [options] mybook.[html|rar|zip]

         %prog converts mybook.html to mybook.lrf""")
    parser.add_option('--cover', action='store', dest='cover', default=None, \
                      help='Path to file containing image to be used as cover')
    parser.add_option('--lrs', action='store_true', dest='lrs', \
                      help='Convert to LRS', default=False)
    parser.add_option('--font-delta', action='store', type='int', default=0, \
                      help="""Increase the font size by 2 * FONT_DELTA pts. 
                      If FONT_DELTA is negative, the font size is decreased.""",
                      dest='font_delta')
    parser.add_option('--link-levels', action='store', type='int', default=sys.maxint, \
                      dest='link_levels',
                      help='''The maximum number of levels to recursively process
                              links. A value of 0 means thats links are not followed.
                              A negative value means that <a> tags are ignored.''')
    parser.add_option('--baen', action='store_true', default=False, dest='baen',
                      help='''Preprocess Baen HTML files to improve generated LRF.''')
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.print_help()
        sys.exit(1)
    src = args[0]
    if options.title == None:
        options.title = os.path.splitext(os.path.basename(src))[0]
    process_file(src, options)

def console_query(dirpath, candidate, docs):
    if len(docs) == 1:
        return 0
    try:
        import readline
    except ImportError:
        pass
    i = 0
    for doc in docs:
        prefix = '>' if i == candidate else ''
        print prefix+str(i)+'.\t', doc[0]
        i += 1
    print
    while True:
        try:
            choice = raw_input('Choose file to convert (0-'+str(i-1) + \
                               '). Current choice is ['+ str(candidate) + ']:')
            if not choice:
                return candidate
            choice = int(choice)
            if choice < 0 or choice >= i:
                continue
            candidate = choice
        except EOFError, KeyboardInterrupt:
            sys.exit()
        except:
            continue
        break
    return candidate
        

def get_path(path, query=console_query):
    path = os.path.abspath(os.path.expanduser(path))
    ext = os.path.splitext(path)[1][1:].lower()
    if ext in ['htm', 'html', 'xhtml']:
        return None, path
    dirpath = mkdtemp('','html2lrf')
    extract(path, dirpath)
    candidate, docs = None, []
    for root, dirs, files in os.walk(dirpath):
        for name in files:
            ext = os.path.splitext(name)[1][1:].lower()
            if ext not in ['html', 'xhtml', 'htm', 'xhtm']:
                continue
            docs.append((name, root, os.stat(os.path.join(root, name)).st_size))
            if 'toc' in name.lower():
                candidate = name
    docs.sort(key=itemgetter(2))
    if candidate:
        for i in range(len(docs)):
            if docs[i][0] == candidate:
                candidate = i
                break
    else:
        candidate = len(docs) - 1
    if len(docs) == 0:
        raise ConversionError('No suitable files found in archive')
    if len(docs) > 0:
        candidate = query(dirpath, candidate, docs)
    return dirpath, os.path.join(docs[candidate][1], docs[candidate][0])


if __name__ == '__main__':
    main()