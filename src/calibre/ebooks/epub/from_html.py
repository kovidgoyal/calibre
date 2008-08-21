__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
import os, sys, logging
from lxml import html
from lxml.etree import XPath
get_text = XPath("//text()")

from calibre import LoggingInterface
from calibre.ebooks.html import PreProcessor
from calibre.ebooks.epub import config as common_config
from calibre.ebooks.epub.traverse import traverse, opf_traverse
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.meta import get_metadata
from calibre.ebooks.metadata.opf import OPFReader
from calibre.ptempfile import PersistentTemporaryDirectory


class HTMLProcessor(PreProcessor, LoggingInterface):
    
    ENCODING_PATS = [re.compile(r'<[^<>]+encoding=[\'"](.*?)[\'"][^<>]*>', re.IGNORECASE),
                     re.compile(r'<meta.*?content=[\'"].*?charset=([^\s\'"]+).*?[\'"].*?>', re.IGNORECASE)]
    
    def __init__(self, htmlfile, opts, tdir, resource_map, htmlfiles):
        LoggingInterface.__init__(self, logging.getLogger('html2epub'))
        self.htmlfile = htmlfile
        self.opts = opts
        self.tdir = tdir
        self.resource_map = resource_map
        self.resource_dir = os.path.join(tdir, 'resources')
        self.htmlfiles = htmlfiles
        self.parse_html()
        self.root.rewrite_links(self.rewrite_links, resolve_base_href=False)
        self.rewrite_links(htmlfiles)
        self.extract_css()
        self.collect_font_statistics()
        self.split()
        
    def parse_html(self):
        ''' Create lxml ElementTree from HTML '''
        src = open(self.htmlfile.path, 'rb').decode(self.htmlfile.encoding, 'replace')
        src = self.preprocess(src)
        # lxml chokes on unicode input when it contains encoding declarations
        for pat in self.ENCODING_PATS: 
            src = pat.sub('', src)
        try:
            self.root = html.document_fromstring(src)
        except:
            if self.opts.verbose:
                self.log_exception('lxml based parsing failed')
            self.root = html.soupparser.fromstring()
        self.head = self.body = None
        head = self.root.xpath('//head')
        if head:
            self.head = head[0]
        body = self.root.xpath('//body')
        if body:
            self.body = body[0]
        self.detected_chapters = self.opts.chapter(self.root)
            
    def rewrite_links(self, olink):
        link = self.htmlfile.resolve(olink)
        if not link.path or not os.path.exists(link.path) or not os.path.isfile(link.path):
            return olink
        if link.path in self.htmlfiles:
            return os.path.basename(link.path)
        if link.path in self.resource_map.keys():
            return self.resource_map[]
        name = os.path.basename(link.path)
        name, ext = os.path.splitext(name)
        name += ('_%d'%len(self.resource_map)) + ext
        shutil.copyfile(link.path, os.path.join(self.resource_dir, name))
        name = 'resources/'+name
        self.resource_map[link.path] = name 
        return name
        
    
    def extract_css(self):
        css = []
        for link in self.root.xpath('//link'):
            if 'css' in link.get('type', 'text/css').lower():
                file = self.htmlfile.resolve(link.get('href', ''))
                if os.path.exists(file) and os.path.isfile(file):
                    css.append(open(file, 'rb').read().decode('utf-8'))
                link.getparent().remove(link)
                    
        for style in self.root.xpath('//style'):
            if 'css' in style.get('type', 'text/css').lower():
                css.append('\n'.join(get_text(style)))
                style.getparent().remove(style)
        
        font_id = 1
        for font in self.root.xpath('//font'):
            try:
                size = int(font.attrib.pop('size', '3'))
            except:
                size = 3
            setting = 'font-size: %d%%;'%int((float(size)/3) * 100)
            face = font.attrib.pop('face', None)
            if face is not None:
                setting += 'font-face:%s;'%face
            color = font.attrib.pop('color', None)
            if color is not None:
                setting += 'color:%s'%color
            id = 'calibre_font_id_%d'%font_id
            font['id'] = 'calibre_font_id_%d'%font_id
            font_id += 1
            css.append('#%s { %s }'%(id, setting))
            
        
        css_counter = 1
        for elem in self.root.xpath('//*[@style]'):
            if 'id' not in elem.keys():
                elem['id'] = 'calibre_css_id_%d'%css_counter
                css_counter += 1
            css.append('#%s {%s}'%(elem['id'], elem['style']))
            elem.attrib.pop('style')
        chapter_counter = 1
        for chapter in self.detected_chapters:
            if chapter.tag.lower() == 'a':
                if 'name' in chapter.keys():
                    chapter['id'] = id = chapter['name']
                elif 'id' in chapter.keys():
                    id = chapter['id']
                else:
                    id = 'calibre_detected_chapter_%d'%chapter_counter
                    chapter_counter += 1
                    chapter['id'] = id
            else:
                if 'id' not in chapter.keys():
                    id = 'calibre_detected_chapter_%d'%chapter_counter
                    chapter_counter += 1
                    chapter['id'] = id
            css.append('#%s {%s}'%(id, 'page-break-before:always'))
                     
        self.raw_css = '\n\n'.join(css)
        # TODO: Figure out what to do about CSS imports from linked stylesheets 
                
    def collect_font_statistics(self):
        '''
        Collect font statistics to figure out the base font size used in this
        HTML document.
        '''
        self.font_statistics = {} #: A mapping of font size (in pts) to number of characters rendered at that font size
        for text in get_text(self.body if self.body is not None else self.root):
            length, parent = len(re.sub(r'\s+', '', text)), text.getparent()
            #TODO: Use cssutils on self.raw_css to figure out the font size 
            # of this piece text and update statistics accordingly        
    
    def split(self):
        ''' Split into individual flows to accommodate Adobe's incompetence '''
        # TODO: Split on page breaks, keeping track of anchors (a.name and id)
        # and preserving tree structure so that CSS continues to apply
        pass
            

def config():
    c = common_config()
    return c

def option_parser():
    c = config()
    return c.option_parser(usage=_('''\
%prog [options] file.html

Convert a HTML file to an EPUB ebook. Follows links in the HTML file. 
'''))

def search_for_opf(dir):
    for f in os.listdir(dir):
        if f.lower().endswith('.opf'):
            return OPFReader(open(os.path.join(dir, f), 'rb'), dir)

def parse_content(filelist, opts):
    tdir = PersistentTemporaryDirectory('_html2epub')
    os.makedirs(os.path.join(tdir, 'content', 'resources'))
    resource_map = {}
    for htmlfile in filelist:
        hp = HTMLProcessor(htmlfile, opts, os.path.join(tdir, 'content'), resource_map)

def convert(htmlfile, opts, notification=None):
    if opts.output is None:
        opts.output = os.path.splitext(os.path.basename(htmlfile))[0] + '.epub'
    opts.output = os.path.abspath(opts.output)
    opf = search_for_opf(os.path.dirname(htmlfile))
    if opf:
        mi = MetaInformation(opf)
    else:
        mi =  get_metadata(open(htmlfile, 'rb'), 'html')
    if opts.title:
        mi.title = opts.title
    if opts.authors != _('Unknown'):
        opts.authors   = opts.authors.split(',')
        opts.authors = [a.strip() for a in opts.authors]
        mi.authors = opts.authors
    
    if not mi.title:
        mi.title = os.path.splitext(os.path.basename(htmlfile))[0]
    if not mi.authors:
        mi.authors = [_('Unknown')]
    
    opts.chapter = XPath(opts.chapter, 
                    namespaces={'re':'http://exslt.org/regular-expressions'})
    
    filelist = None
    print 'Building file list...'
    if opf is not None:
        filelist = opf_traverse(opf, verbose=opts.verbose, encoding=opts.encoding)
    if not filelist:
        filelist = traverse(htmlfile, verbose=opts.verbose, encoding=opts.encoding)\
                    [0 if opts.breadth_first else 1]
    if opts.verbose:
        print '\tFound files...'
        for f in filelist:
            print '\t\t', f
            
    parse_content(filelist, opts)
            
def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) < 2:
        parser.print_help()
        print _('You must specify an input HTML file')
        return 1
    convert(args[1], opts)
    return 0
    
if __name__ == '__main__':
    sys.exit(main())

