##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
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
'''
Convert PDF to a reflowable format using pdftoxml.exe as the PDF parsing backend.
'''

import sys, os, re, tempfile, subprocess, atexit, shutil, logging, xml.parsers.expat
from xml.etree.ElementTree import parse

from libprs500 import isosx, OptionParser, setup_cli_handlers, __appname__
from libprs500.ebooks import ConversionError

PDFTOXML = 'pdftoxml.exe'
if isosx and hasattr(sys, 'frameworks_dir'):
    PDFTOXML = os.path.join(getattr(sys, 'frameworks_dir'), PDFTOXML)

class StyleContainer(object):
    
    def set_style(self, iterator):
        styles = set([])
        for tok in iterator:
            if hasattr(tok, 'style'):
                styles.add(tok.style)
        counts = [0*i for i in range(len(styles))]
        for i in range(len(styles)):
            counts[i] = sum([1 for j in self if j.style == styles[i]])
        max = max(counts)
        for i in range(len(counts)):
            if counts[i] == max:
                break
        self.style = styles[i]
        for obj in iterator:
            if obj.style == self.style:
                obj.style = None


class Page(object):
    
    def __init__(self, attrs):
        for a in ('number', 'width', 'height'):
            setattr(self, a, float(attrs[a]))
        self.id     = attrs['id']
        self.current_line = None
        self.lines = []
        
    def end_line(self):
        if self.current_line is not None:
            self.current_line.finalize()
            self.lines.append(self.current_line)
            self.current_line = None
            
    def finalize(self):
        self.identify_groups()
        self.look_for_page_break()
    
    def identify_groups(self):
        groups = []
        in_group = False
        for i in range(len(self.lines)):
            if not in_group:
                groups.append(i)
                in_group = True
            else:
                pl = self.lines[i-1]
                cl = self.lines[i]
                if cl.left != pl.left and cl.width != pl.width:
                    groups.append(i)
        self.groups = []
        for i in range(len(groups)):
            start = groups[i]
            if i +1 == len(groups):
                stop = len(self.lines)
            else:
                stop = groups[i+i]
            self.groups.append(self.lines[start:stop])
        
        if len(self.groups) > 1:
            self.group[0].test_header(self.width, self.height)
            self.groups[-1].test_footer(self.width, self.height)
            
    def look_for_page_break(self):
        max = 0
        for g in self.groups:
            if not g.is_footer and g.bottom > max:
                max = g.bottom
        self.page_break_after = max < 0.8*self.height
        

class Group(StyleContainer):
    
    def __init__(self, lines):
        self.lines = lines
        self.set_style(self.lines)
        self.width = max([i.width for i in self.lines])
        self.bottom = max([i.bottom for i in self.lines])
        tot, ltot = 0, 0
        for i in range(1, len(self.lines)):
            bot = self.lines[i-1].bottom
            top = self.lines[i].top
            tot += abs(top - bot)
            ltot += self.lines[i].left
        self.average_line_spacing = tot/float(len(self.lines)-1)
        ltot += self.lines[0].left
        self.average_left_margin = ltot/float(len(self.lines))
        self.left_margin = min([i.left for i in self.lines])
        
        self.detect_paragraphs()
        
        
        
    def detect_paragraphs(self):
        if not self.lines:
            return
        indent_buffer = 5
        self.lines[0].is_para_start = self.lines[0].left > self.average_left_margin+indent_buffer 
        for i in range(1, len(self.lines)):
            pl, l = self.lines[i-1:i+1]
            c1 = pl.bottom - l.top > self.average_line_spacing
            c2 = l.left > self.average_left_margin+indent_buffer
            c3 = pl.width < 0.8 * self.width
            l.is_para_start = c1 or c2 or c3
            
    def test_header(self, page_width, page_height):
        self.is_header = len(self.lines) == 1 and self.lines[0].width < 0.5*page_width 
        
    def test_footer(self, page_width, page_height):
        self.is_footer = len(self.lines) == 1 and self.lines[0].width < 0.5*page_width

class Text(object):
    
    def __init__(self, attrs):
        for a in ('x', 'y', 'width', 'height'):
            setattr(self, a, float(attrs[a]))
        self.id = attrs['id']
        self.objects = []
        
    def add_token(self, tok):
        if not self.objects:
            self.objects.append(tok)
        else:
            ptok = self.objects[-1]
            if tok == ptok:
                ptok.text += ' ' + tok.text
            else:
                self.objects.append(tok)
    
    def add(self, object):
        if isinstance(object, Token):
            self.add_token(object)
        else:
            print 'WARNING: Unhandled object', object.__class__.__name__
            
    def to_xhtml(self):
        res = []
        for obj in self.objects:
            if isinstance(obj, Token):
                res.append(obj.to_xhtml())
        return ' '.join(res)
                

class Line(list, StyleContainer):
    
    def calculate_geometry(self):
        self.left   = self[0].x
        self.width  = self[-1].x + self[-1].width - self.left
        self.top    = min(o.y for o in self)
        self.bottom = max(o.height+o.y for o in self)
        
    def finalize(self):
        self.calculate_geometry()
        self.set_style(self)
        
    def to_xhtml(self, group_id):
        ans = '<span class="%s" '%group_id
        if self.style is not None:
            ans += 'style="%s"'%self.style.to_css(inline=True)
        ans += '>%s</span>'
        res = []
        for object in self:
            if isinstance(object, Text):
                res.append(object.to_xhtml())
                
        return ans%(' '.join(res))
                
        
class TextStyle(object):
    
    def __init__(self, tok):
        self.bold   = tok.bold
        self.italic = tok.italic
        self.font_name = tok.font_name
        self.font_size = tok.font_size
        self.color     = tok.font_color
        
    def __eq__(self, other):
        if isinstance(other, self.__class__):
            for a in ('font_size', 'bold', 'italic', 'font_name', 'color'):
                if getattr(self, a) != getattr(other, a):
                    return False
            return True
        return False
    
    def to_css(self, inline=False):
        fw  = 'bold' if self.bold else 'normal'
        fs  = 'italic' if self.italic else 'normal'
        fsz = '%dpt'%self.font_size
        props = ['font-weight: %s;'%fw, 'font-style: %s;'%fs, 'font-size: %s;'%fsz,
                 'color: rgb(%d, %d, %d);'%self.color]
        joiner = ' '
        if not inline:
            joiner = '\n'
            props = ['{'] + props + ['}']
        return joiner.join(props) 

class Token(object):
    
    def __init__(self, attrs):
        for a in ('x', 'y', 'width', 'height', 'rotation', 'angle', 'font-size'):
            setattr(self, a.replace('-', '_'), float(attrs[a]))
        for a in ('bold', 'italic'):
            setattr(self, a, attrs[a]=='yes')
        self.font_name = attrs['font-name']
        fc = re.compile(r'#([a-f0-9]{2})([a-f0-9]{2})([a-f0-9]{2})', re.IGNORECASE)
        fc = fc.match(attrs['font-color'])
        self.font_color = (int(fc.group(1), 16), int(fc.group(2), 16), int(fc.group(3), 16))
        self.id = attrs['id']
        self.text = u''
        self.style = TextStyle(self)
        
    def handle_char_data(self, data):
        self.text += data
        
    def __eq__(self, other):
        if isinstance(other, self.__class__):
            for a in ('rotation', 'angle', 'font_size', 'bold', 'italic', 'font_name', 'font_color'):
                if getattr(self, a) != getattr(other, a):
                    return False
            return True
        return False
    
    def to_xhtml(self):
        if self.style is not None:
            ans = u'<span style="%s">%s</span>'%(self.style.to_css(inline=True), self.text)
        else:
            ans = self.text
        return ans

class PDFDocument(object):
    
    SKIPPED_TAGS = ('DOCUMENT', 'METADATA', 'PDFFILENAME', 'PROCESS', 'VERSION',
                    'COMMENT', 'CREATIONDATE')
    
    def __init__(self, filename):
        parser = xml.parsers.expat.ParserCreate('UTF-8')
        parser.buffer_text          = True
        parser.returns_unicode      = True
        parser.StartElementHandler  = self.start_element
        parser.EndElementHandler    = self.end_element
        
        self.pages = []
        self.current_page = None
        self.current_token = None
        
        src = open(filename, 'rb').read()
        self.parser = parser
        parser.Parse(src)
        
        
    def start_element(self, name, attrs):
        if name == 'TOKEN':
            self.current_token = Token(attrs)
            self.parser.CharacterDataHandler = self.current_token.handle_char_data
        elif name == 'TEXT':
            text = Text(attrs)
            if self.current_page.current_line is None:
                self.current_page.current_line = Line()
                self.current_page.current_line.append(text)
            else:
                y, height = self.current_page.current_line[0].y, self.current_page.current_line[0].height
                if y == text.y or y+height == text.y + text.height:
                    self.current_page.current_line.append(text)
                else:
                    self.current_page.end_line()
                    self.current_page.current_line = Line()
                    self.current_page.current_line.append(text)
        elif name == 'PAGE':
            self.current_page = Page(attrs)
        elif name.lower() == 'xi:include':
            print 'WARNING: Skipping vector image'
        elif name in self.SKIPPED_TAGS:
            pass
        else:
            print 'WARNING: Unhandled element', name
        
    def end_element(self, name):
        if name == 'TOKEN':
            if self.current_token.angle == 0 and self.current_token.rotation == 0:
                self.current_page.current_line[-1].add(self.current_token)
            self.current_token = None
            self.parser.CharacterDataHandler = None
        elif name == 'PAGE':
            self.current_page.finalize()
            self.pages.append(self.current_page)
            self.current_page = None
    
    
    def to_xhtml(self):
        header = u'''\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
    "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://www.w3.org/MarkUp/SCHEMA/xhtml11.xsd" >
<head>
<style type="text/css">
%(style)s
</style>
</head>
<body>
%(body)s
</body>
</html>
'''
        res = []
        para = []
        styles = []
        for page in self.pages:
            res.append(u'<a name="%s" />'%page.id)
            for group in page.groups:
                if group.is_header or group.is_footer:
                    continue
                if group.style is not None:
                    styles.append(u'.%s %s\n'%(group.id, group.style.to_css()))
                for line in group.lines:
                    if line.is_para_start:
                        indent = group.left_margin - line.left
                        if para:
                            res.append(u'<p style="text-indent: %dpt">%s</p>'%(indent, ''.join(para)))
                            para = []
                    para.append(line.to_xhtml(group.id))
            if page.page_break_after:
                res.append(u'<br style="page-break-after:always" />')
                if para:
                    res.append(u'<p>%s</p>'%(''.join(para)))
                    para = []
                    
        return (header%dict(style='\n'.join(styles), body='\n'.join(res))).encode('utf-8')

class PDFConverter(object):

    @classmethod
    def generate_xml(cls, pathtopdf, logger):
        pathtopdf = os.path.abspath(pathtopdf)
        tdir = tempfile.mkdtemp('pdf2xml', __appname__)
        atexit.register(shutil.rmtree, tdir)
        xmlfile = os.path.basename(pathtopdf)+'.xml'
        os.chdir(tdir)
        cmd = PDFTOXML + ' -outline "%s" "%s"'%(pathtopdf, xmlfile)
        p = subprocess.Popen(cmd, shell=True, stderr=subprocess.STDOUT, 
                             stdout=subprocess.PIPE)
        log = p.stdout.read()
        ret = p.wait()
        if ret != 0:
            raise ConversionError, log
        xmlfile = os.path.join(tdir, xmlfile)
        if os.stat(xmlfile).st_size < 20:
            raise ConversionError(os.path.basename(pathtopdf) + ' does not allow copying of text.')
        return xmlfile

    
    def __init__(self, pathtopdf, logger, opts):
        self.cwd    = os.getcwdu()
        self.logger = logger
        self.opts   = opts
        try:
            self.logger.info('Converting PDF to XML')
            self.xmlfile   = self.generate_xml(pathtopdf, self.logger)
            self.tdir      = os.path.dirname(self.xmlfile)
            self.data_dir  = self.xmlfile + '_data'
            outline_file = self.xmlfile.rpartition('.')[0]+'_outline.xml'
            self.logger.info('Parsing XML')
            self.document = PDFDocument(self.xmlfile)
            self.outline  = parse(outline_file)
        finally:
            os.chdir(self.cwd)
            
    def convert(self, output_dir):
        doc = self.document.to_xhtml()
        open(os.path.join(output_dir, 'document.html'), 'wb').write(doc)
        
            
            
def option_parser():
    parser = OptionParser(usage=\
'''
%prog [options] myfile.pdf

Convert a PDF file to a HTML file.
''')
    parser.add_option('-o', '--output-dir', default='.', 
                      help=_('Path to output directory in which to create the HTML file. Defaults to current directory.'))
    parser.add_option('--verbose', default=False, action='store_true',
                      help=_('Be more verbose.'))
    return parser    

def main(args=sys.argv, logger=None):
    parser = option_parser()
    options, args = parser.parse_args()
    if logger is None:
        level = logging.DEBUG if options.verbose else logging.INFO
        logger = logging.getLogger('pdf2html')
        setup_cli_handlers(logger, level)
    if len(args) != 1:
        parser.print_help()
        print _('You must specify a single PDF file.')
        return 1
    options.output_dir = os.path.abspath(options.output_dir)
    converter = PDFConverter(os.path.abspath(args[0]), logger, options)
    converter.convert(options.output_dir)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())