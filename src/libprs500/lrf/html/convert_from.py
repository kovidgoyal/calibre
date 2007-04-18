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
"""
import os, re, sys
from htmlentitydefs import name2codepoint
from optparse import OptionParser

from libprs500.lrf.html.BeautifulSoup import BeautifulSoup, Comment, Tag, NavigableString
from libprs500.lrf.pylrs.pylrs import Book, Page, Paragraph, TextBlock, CR, Italic
from libprs500.lrf.pylrs.pylrs import Span as _Span
from libprs500.lrf import ConversionError

class Span(_Span):
    replaced_entities = [ 'amp', 'lt', 'gt' , 'ldquo', 'rdquo', 'lsquo', 'rsquo' ]
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
        else:
            try:
                result = int(val)
            except ValueError:
                return None
        return result
    
    @staticmethod
    def translate_attrs(d):
        """
        Receives a dictionary of html attributes and styles and returns
        approximate Xylog equivalents in a new dictionary
        """
        t = dict()
        for key in d.keys():
            try:
                val = d[key].lower()
            except IndexError:
                val = None
            if key == "font-family":
                if max(val.find("courier"), val.find("mono"), val.find("fixed"), val.find("typewriter"))>=0:
                    t["fontfacename"] = "Courier10 BT Roman"
                elif max(val.find("arial"), val.find("helvetica"), val.find("verdana"), 
                         val.find("trebuchet"), val.find("sans")) >= 0:
                    t["fontfacename"] = "Swis721 BT Roman"
                else:
                    t["fontfacename"] = "Dutch801 Rm BT Roman"
            elif key == "font-size":
                unit = Span.unit_convert(val, 14)
                if unit is not None:
                    # Assume a 10 pt font (14 pixels) has fontsize 100
                    t["fontsize"] = str(int (unit / 14.0 * 100))
                else:
                    if val.find("xx-small") >= 0:
                        t["fontsize"] = "40"
                    elif val.find("x-small") >= 0:
                        t["fontsize"] = "60"
                    elif val.find("small") >= 0:
                        t["fontsize"] = "80"
                    elif val.find("xx-large") >= 0:
                        t["fontsize"] = "180"
                    elif val.find("x-large") >= 0:
                        t["fontsize"] = "140"
                    elif val.find("large") >= 0:
                        t["fontsize"] = "120"                
                    else:
                        t["fontsize"] = "100"
            elif key == "font-weight":
                m = re.match ("\s*([0-9]+)", val)
                if m is not None:
                    #report (m.group(1))
                    t["fontweight"] = str(int(int(m.group(1))))
                else:
                    if val.find("bold") >= 0 or val.find("strong") >= 0:
                        t["fontweight"] = "1000"
                    else:
                        t["fontweight"] = "400"
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
            elif key == "text-align" or key == "align":
                if val in ["right", "foot"]:
                    t["align"] = "foot"
                elif val == "center":
                    t["align"] = "center"
                else:
                    t["align"] = "head"
            else:
                t[key] = d[key]
        return t        
    
    def __init__(self, ns, css):
        src = ns.string
        src = re.sub('[\n\r]+', '', src)
        for pat, repl in Span.rules:
            src = pat.sub(repl, src)
        if not src:
            raise ConversionError('No point in adding an empty string')
        if 'font-style' in css.keys():
            fs = css.pop('font-style')
            if fs.lower() == 'italic':
                src = Italic(src)
        attrs = Span.translate_attrs(css)
        _Span.__init__(self, text=src, **attrs)
        
        
        
class HTMLConvertor(object):
    selector_pat = re.compile(r"([A-Za-z0-9\-\_\:\.]+[A-Za-z0-9\-\_\:\.\s\,]*)\s*\{([^\}]*)\}")
    # Defaults for various formatting tags
    css = dict(
            h1     = {"font-size":"xx-large", "font-weight":"bold"},
            h2     = {"font-size":"x-large", "font-weight":"bold"},
            h3     = {"font-size":"large", "font-weight":"bold"},
            h4     = {"font-size":"large"},
            h5     = {"font-weight":"bold"},
            b      = {"font-weight":"bold"},
            strong = {"font-weight":"bold"},
            i      = {"font-style":"italic"},
            em     = {"font-style":"italic"},
            )
    
    def __init__(self, book, soup, verbose=False):
        self.book = book #: The Book object representing a BBeB book        
        self.soup = soup #: Parsed HTML soup
        self.verbose = verbose
        self.current_page = None
        self.current_para = None
        self.current_style = {}
        self.parse_file(self.soup.html)
        
    def parse_css(self, style):
        """
        Parse the contents of a <style> tag or .css file.
        @param style: C{str(style)} should be the CSS to parse.
        @return: A dictionary with one entry per selector where the key is the
        selector name and the value is a dictionary of properties
        """
        sdict = dict()
        for sel in re.findall(HTMLConvertor.selector_pat, style):
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
                if key.lower().startswith('font'):
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
        
    def parse_file(self, html):
        if self.current_page:
            self.book.append(self.current_page)
        self.current_page = Page()
        self.current_block = TextBlock()
        self.current_para = Paragraph()
        self.parse_tag(html, {})
        if self.current_para:
            self.current_block.append(self.current_para)
        if self.current_block:
            self.current_page.append(self.current_block)
        if self.current_page:
            self.book.append(self.current_page)
            
    def end_page(self):
        self.current_block.append(self.current_para)
        self.current_para = Paragraph()
        self.current_page.append(self.current_block)
        self.current_block = TextBlock()
        self.book.append(self.current_page)
        self.current_page = Page()
        
        
    def parse_tag(self, tag, parent_css):
        def sanctify_css(css):
            """ Make css safe for use in a SPAM Xylog tag """
            for key in css.keys():
                test = key.lower()
                if test.startswith('margin') or 'indent' in test or \
                   'padding' in test or 'border' in test or test in \
                   ['color', 'display', 'text-decoration', 'letter-spacing']:
                    css.pop(key)
            return css
                    
        def add_text(tag, css):
            try:
                self.current_para.append(Span(tag, sanctify_css(css)))
            except ConversionError, err:
                if self.verbose:
                    print >>sys.stderr, err
        
        
                    
        def process_text_tag(tag, pcss):
            if 'page-break-before' in pcss.keys():
                if pcss['page-break-before'].lower() != 'avoid':
                    self.end_page()
                pcss.pop('page-break-before')
            end_page = False
            if 'page-break-after' in pcss.keys():
                end_page = True
                pcss.pop('page-break-after')
            for c in tag.contents:
                if isinstance(tag, NavigableString):
                    add_text(tag, pcss)
                else:
                    self.parse_tag(c, pcss)
            if end_page:
                self.end_page()
            
        try:
            tagname = tag.name.lower()
        except AttributeError:
            add_text(tag, parent_css)
            return
        if tagname in ["title", "script", "meta"]:
            pass
        elif tagname in ['style', 'link']:
            # TODO: Append CSS to self.css
            pass
        elif tagname == 'p':
            css = self.tag_css(tag, parent_css=parent_css)
            indent = css.pop('text-indent', '')
            if indent:
                # TODO: If indent is different from current textblock's parindent
                # start a new TextBlock
                pass
            self.current_para.CR() # Put a paragraph end             
            self.current_block.append(self.current_para)
            self.current_para = Paragraph()
            process_text_tag(tag, css)
        elif tagname in ['b', 'strong', 'i', 'em', 'span']:
            css = self.tag_css(tag, parent_css=parent_css)            
            process_text_tag(tag, css)
        elif tagname == 'font':
            pass
        elif tagname == 'link':
            pass
        elif tagname == 'style':
            pass
        elif tagname == 'br':
            self.current_para.append(CR())
        elif tagname == 'hr':
            self.current_page.append(self.current_para)
            self.current_block.append(self.current_page)
            self.current_para = Paragraph()
            self.current_page = Page()
        else:
            css = self.tag_css(tag, parent_css=parent_css)
            for c in tag.contents:
                if isinstance(c, Comment):
                    continue
                elif isinstance(c, Tag):
                    self.parse_tag(c, css)
                elif isinstance(c, NavigableString):                    
                    add_text(c, css)
                    
    def writeto(self, path):
        if path.lower().endswith('lrs'):
            self.book.renderLrs(path)
        else:
            self.book.renderLrf(path)
        

def process_file(path, options):
    cwd = os.getcwd()    
    try:
        path = os.path.abspath(path)
        os.chdir(os.path.dirname(path))
        soup = BeautifulSoup(open(path, 'r').read(), \
                         convertEntities=BeautifulSoup.HTML_ENTITIES)
        book = Book(title=options.title, author=options.author, \
                    sourceencoding='utf8')
        conv = HTMLConvertor(book, soup)
        name = os.path.splitext(os.path.basename(path))[0]+'.lrf'
        os.chdir(cwd)
        conv.writeto(name)        
    finally:
        os.chdir(cwd)
        
def main():
    """ CLI for html -> lrf conversions """
    parser = OptionParser(usage=\
        """usage: %prog [options] mybook.txt
        
        %prog converts mybook.txt to mybook.lrf
        """\
        )
    parser.add_option("-t", "--title", action="store", type="string", \
                    dest="title", help="Set the title")
    parser.add_option("-a", "--author", action="store", type="string", \
                    dest="author", help="Set the author", default='Unknown')
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.print_help()
        sys.exit(1)
    src = args[0]
    if options.title == None:
        options.title = os.path.splitext(os.path.basename(src))[0]
    process_file(src, options)


if __name__ == '__main__':
    main()