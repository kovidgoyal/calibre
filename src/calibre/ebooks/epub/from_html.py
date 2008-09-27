from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Conversion of HTML/OPF files follows several stages:

    * All links in the HTML files or in the OPF manifest are
    followed to build up a list of HTML files to be converted.
    This stage is implemented by 
    :function:`calibre.ebooks.html.traverse` and
    :class:`calibre.ebooks.html.HTMLFile`.

    * The HTML is pre-processed to make it more semantic. 
    All links in the HTML files to other resources like images,
    stylesheets, etc. are relativized. The resources are copied 
    into the `resources` sub directory. This is accomplished by
    :class:`calibre.ebooks.html.PreProcessor` and 
    :class:`calibre.ebooks.html.Parser`.

    * The HTML is processed. Various operations are performed.
    All style declarations are extracted and consolidated into 
    a single style sheet. Chapters are auto-detected and marked.
    Various font related manipulations are performed. See
    :class:`HTMLProcessor`.

    * The processed HTML is saved and the 
    :module:`calibre.ebooks.epub.split` module is used to split up
    large HTML files into smaller chunks.

    * The EPUB container is created.
'''

import os, sys, re, cStringIO

from lxml.etree import XPath
try:
    from PIL import Image as PILImage
except ImportError:
    import Image as PILImage

from calibre.ebooks.html import Processor, get_text, merge_metadata, get_filelist,\
    opf_traverse, create_metadata, rebase_toc
from calibre.ebooks.epub import config as common_config
from calibre.ptempfile import TemporaryDirectory
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.toc import TOC
from calibre.ebooks.metadata.opf2 import OPF
from calibre.ebooks.epub import initialize_container, PROFILES
from calibre.ebooks.epub.split import split
from calibre.constants import preferred_encoding


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
            
    def save(self):
        for meta in list(self.root.xpath('//meta')):
            meta.getparent().remove(meta)
        Processor.save(self)
        
        #self.collect_font_statistics()
        
        
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
    toc = TOC(base_path=tdir, type='root')
    for htmlfile in filelist:
        hp = HTMLProcessor(htmlfile, opts, os.path.join(tdir, 'content'), 
                           resource_map, filelist)
        hp.populate_toc(toc)
        hp.save()
    
    if toc.count('chapter') > opts.toc_threshold:
        toc.purge(['file', 'link', 'unknown'])
    if toc.count('chapter') + toc.count('file') > opts.toc_threshold:
        toc.purge(['link', 'unknown'])
    toc.purge(['link'], max=opts.max_toc_links)
    
    return resource_map, hp.htmlfile_map, toc

def convert(htmlfile, opts, notification=None):
    htmlfile = os.path.abspath(htmlfile)
    if opts.output is None:
        opts.output = os.path.splitext(os.path.basename(htmlfile))[0] + '.epub'
    opts.profile = PROFILES[opts.profile]
    opts.output = os.path.abspath(opts.output)
    if opts.override_css is not None:
        try:
            opts.override_css = open(opts.override_css, 'rb').read().decode(preferred_encoding, 'replace')
        except:
            opts.override_css = opts.override_css.decode(preferred_encoding, 'replace')
    if htmlfile.lower().endswith('.opf'):
        opf = OPF(htmlfile, os.path.dirname(os.path.abspath(htmlfile)))
        filelist = opf_traverse(opf, verbose=opts.verbose, encoding=opts.encoding)
        mi = MetaInformation(opf)
    else:
        opf, filelist = get_filelist(htmlfile, opts)
        mi = merge_metadata(htmlfile, opf, opts)
    opts.chapter = XPath(opts.chapter, 
                    namespaces={'re':'http://exslt.org/regular-expressions'})
    
    with TemporaryDirectory(suffix='_html2epub', keep=opts.keep_intermediate) as tdir:
        if opts.keep_intermediate:
            print 'Intermediate files in', tdir
        resource_map, htmlfile_map, generated_toc = parse_content(filelist, opts, tdir)
        resources = [os.path.join(tdir, 'content', f) for f in resource_map.values()]
        
        cover_src = None
        if mi.cover and os.access(mi.cover, os.R_OK):
            cover_src = mi.cover
        else:
            mi.cover = None
        if opts.cover is not None and not opts.prefer_metadata_cover:
            cover_src = opts.cover
        
        if cover_src is not None:
            cover_dest = os.path.join(tdir, 'content', 'resources', '_cover_.jpg')
            PILImage.open(cover_src).convert('RGB').save(cover_dest)
            mi.cover = cover_dest
            resources.append(cover_dest)
            
        spine = [htmlfile_map[f.path] for f in filelist]
        if mi.cover:
            cpath = '/'.join(('resources', os.path.basename(mi.cover)))
            cover = '''\
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
    <head><title>Cover Page</title><style type="text/css">@page {padding: 0pt; margin:0pt}</style></head>
    <body style="padding: 0pt; margin: 0pt;}">
        <div style="text-align:center">
            <img src="%s" alt="cover" />
        </div>
    </body>
</html>'''%cpath
            cpath = os.path.join(tdir, 'content', 'calibre_cover_page.html')
            with open(cpath, 'wb') as f:
                f.write(cover)
            spine[0:0] = [os.path.basename(cpath)]
            mi.cover = None
            mi.cover_data = (None, None)
            
            
        mi = create_metadata(tdir, mi, spine, resources)
        buf = cStringIO.StringIO()
        if mi.toc:
            rebase_toc(mi.toc, htmlfile_map, tdir)
        if opts.use_auto_toc or mi.toc is None or len(list(mi.toc.flat())) < 2:
            mi.toc = generated_toc
        for item in mi.manifest:
            if getattr(item, 'mime_type', None) == 'text/html':
                item.mime_type = 'application/xhtml+xml'
        opf_path = os.path.join(tdir, 'metadata.opf')
        with open(opf_path, 'wb') as f:
            mi.render(f, buf, 'toc.ncx')
        if opts.show_opf:
            print open(os.path.join(tdir, 'metadata.opf')).read()
        toc = buf.getvalue()
        if toc:
            with open(os.path.join(tdir, 'toc.ncx'), 'wb') as f:
                f.write(toc)
            if opts.show_ncx:
                print toc
        split(opf_path, opts)
        epub = initialize_container(opts.output)
        epub.add_dir(tdir)
        print 'Output written to', opts.output
        if opts.extract_to is not None:
            epub.extractall(opts.extract_to)
        
            
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
