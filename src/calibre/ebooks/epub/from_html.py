from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
import os, sys, re, shutil
from lxml.etree import XPath

from calibre.ebooks.html import Parser, get_text, merge_metadata, get_filelist
from calibre.ebooks.epub import config as common_config
from calibre.ptempfile import PersistentTemporaryDirectory


class HTMLProcessor(Parser):
    
    def __init__(self, htmlfile, opts, tdir, resource_map, htmlfiles):
        Parser.__init__(self, htmlfile, opts, tdir, resource_map, htmlfiles, 
                        name='html2epub')
        if opts.verbose > 2:
            self.debug_tree('parsed')
        self.detected_chapters = self.opts.chapter(self.root)
        self.extract_css()
        
        if opts.verbose > 2:
            self.debug_tree('nocss')
        
        self.collect_font_statistics()
        
        self.split()
        
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
            

def config(defaults=None):
    c = common_config(defaults=defaults)
    return c

def option_parser():
    c = config()
    return c.option_parser(usage=_('''\
%prog [options] file.html

Convert a HTML file to an EPUB ebook. Follows links in the HTML file. 
'''))

def parse_content(filelist, opts):
    tdir = PersistentTemporaryDirectory('_html2epub')
    os.makedirs(os.path.join(tdir, 'content', 'resources'))
    resource_map = {}
    for htmlfile in filelist:
        hp = HTMLProcessor(htmlfile, opts, os.path.join(tdir, 'content'), 
                           resource_map, filelist)

def convert(htmlfile, opts, notification=None):
    htmlfile = os.path.abspath(htmlfile)
    if opts.output is None:
        opts.output = os.path.splitext(os.path.basename(htmlfile))[0] + '.epub'
    opts.output = os.path.abspath(opts.output)
    opf, filelist = get_filelist(htmlfile, opts)
    mi = merge_metadata(htmlfile, opf, opts)
    opts.chapter = XPath(opts.chapter, 
                    namespaces={'re':'http://exslt.org/regular-expressions'})
    resource_map = parse_content(filelist, opts)
    resources = [os.path.join(opts.output, 'content', f) for f in resource_map.values()]
    if opf.cover and os.access(opf.cover, os.R_OK):
        shutil.copyfile(opf.cover, os.path.join(opts.output, 'content', 'resources', '_cover_'+os.path.splitext(opf.cover)))
        cpath = os.path.join(opts.output, 'content', 'resources', '_cover_'+os.path.splitext(opf.cover))
        shutil.copyfile(opf.cover, cpath)
        resources.append(cpath)
            
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