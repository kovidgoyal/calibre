from __future__ import with_statement
from calibre.ebooks.metadata.opf import OPFReader
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
import os, sys, re, shutil, cStringIO
from lxml.etree import XPath

from calibre.ebooks.html import Processor, get_text, merge_metadata, get_filelist,\
    opf_traverse, create_metadata, rebase_toc
from calibre.ebooks.epub import config as common_config
from calibre.ptempfile import TemporaryDirectory
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.toc import TOC


class HTMLProcessor(Processor):
    
    def __init__(self, htmlfile, opts, tdir, resource_map, htmlfiles):
        Processor.__init__(self, htmlfile, opts, tdir, resource_map, htmlfiles, 
                        name='html2epub')
        if opts.verbose > 2:
            self.debug_tree('parsed')
        self.detect_chapters()
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
            # of this piece of text and update statistics accordingly        
    
    def split(self):
        ''' Split into individual flows to accommodate Adobe's incompetence '''
        # TODO: Only split file larger than 300K (as specified in profile)
        # Split on page breaks first and then on <h1-6> tags and then on
        # <div> and finally on <p>.  
        pass
            

def config(defaults=None):
    return common_config(defaults=defaults)

def option_parser():
    c = config()
    return c.option_parser(usage=_('''\
%prog [options] file.html|opf

Convert a HTML file to an EPUB ebook. Recursively follows links in the HTML file.
If you specify an OPF file instead of an HTML file, the list of links is takes from
the <spine> element of the OPF file.  
'''))

def parse_content(filelist, opts, tdir):
    os.makedirs(os.path.join(tdir, 'content', 'resources'))
    resource_map = {}
    toc = TOC(base_path=tdir)
    for htmlfile in filelist:
        hp = HTMLProcessor(htmlfile, opts, os.path.join(tdir, 'content'), 
                           resource_map, filelist)
        hp.populate_toc(toc)
        hp.save()
    return resource_map, hp.htmlfile_map, toc

def convert(htmlfile, opts, notification=None):
    htmlfile = os.path.abspath(htmlfile)
    if opts.output is None:
        opts.output = os.path.splitext(os.path.basename(htmlfile))[0] + '.epub'
    opts.output = os.path.abspath(opts.output)
    if htmlfile.lower().endswith('.opf'):
        opf = OPFReader(htmlfile, os.path.dirname(os.path.abspath(htmlfile)))
        filelist = opf_traverse(opf, verbose=opts.verbose, encoding=opts.encoding)
        mi = MetaInformation(opf)
    else:
        opf, filelist = get_filelist(htmlfile, opts)
        mi = merge_metadata(htmlfile, opf, opts)
    opts.chapter = XPath(opts.chapter, 
                    namespaces={'re':'http://exslt.org/regular-expressions'})
    
    with TemporaryDirectory('_html2epub') as tdir:
        resource_map, htmlfile_map, generated_toc = parse_content(filelist, opts, tdir)
        resources = [os.path.join(opts.output, 'content', f) for f in resource_map.values()]
        
        if opf.cover and os.access(opf.cover, os.R_OK):
            shutil.copyfile(opf.cover, os.path.join(opts.output, 'content', 'resources', '_cover_'+os.path.splitext(opf.cover)))
            cpath = os.path.join(opts.output, 'content', 'resources', '_cover_'+os.path.splitext(opf.cover))
            shutil.copyfile(opf.cover, cpath)
            resources.append(cpath)
            mi.cover = cpath
            
        spine = [htmlfile_map[f.path] for f in filelist]
        mi = create_metadata(tdir, mi, spine, resources)
        buf = cStringIO.StringIO()
        if mi.toc:
            rebase_toc(mi.toc, htmlfile_map, opts.output)
        if mi.toc is None or len(mi.toc) < 2:
            mi.toc = generated_toc
        with open(os.path.join(tdir, 'metadata.opf'), 'wb') as f:
            mi.render(f, buf)
        toc = buf.getvalue()
        if toc:
            with open(os.path.join(tdir, 'toc.ncx'), 'wb') as f:
                f.write(toc)
            
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