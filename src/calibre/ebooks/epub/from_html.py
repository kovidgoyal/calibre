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

import os, sys, cStringIO, logging, re, functools, shutil

from lxml.etree import XPath
from lxml import html, etree
from PyQt4.Qt import QApplication, QPixmap

from calibre.ebooks.html import Processor, merge_metadata, get_filelist,\
    opf_traverse, create_metadata, rebase_toc, Link, parser
from calibre.ebooks.epub import config as common_config, tostring
from calibre.ptempfile import TemporaryDirectory
from calibre.ebooks.metadata.toc import TOC
from calibre.ebooks.metadata.opf2 import OPF
from calibre.ebooks.epub import initialize_container, PROFILES
from calibre.ebooks.epub.split import split
from calibre.ebooks.epub.fonts import Rationalizer
from calibre.constants import preferred_encoding
from calibre.customize.ui import run_plugins_on_postprocess
from calibre import walk, CurrentDir, to_unicode

content = functools.partial(os.path.join, u'content')

def remove_bad_link(element, attribute, link, pos):
    if attribute is not None:
        if element.tag in ['link']:
            element.getparent().remove(element)
        else:
            element.set(attribute, '')
            del element.attrib[attribute]

def check_links(opf_path, pretty_print):
    '''
    Find and remove all invalid links in the HTML files 
    '''
    logger = logging.getLogger('html2epub')
    logger.info('\tChecking files for bad links...')
    pathtoopf = os.path.abspath(opf_path)
    with CurrentDir(os.path.dirname(pathtoopf)):
        opf = OPF(open(pathtoopf, 'rb'), os.path.dirname(pathtoopf))
        html_files = []
        for item in opf.itermanifest():
            if 'html' in item.get('media-type', '').lower():
                f = item.get('href').split('/')[-1].decode('utf-8')
                html_files.append(os.path.abspath(content(f)))
        
        for path in html_files:
            if not os.access(path, os.R_OK):
                continue
            base = os.path.dirname(path)
            root = html.fromstring(open(content(path), 'rb').read(), parser=parser)
            for element, attribute, link, pos in list(root.iterlinks()):
                link = to_unicode(link)
                plink = Link(link, base)
                bad = False
                if plink.path is not None and not os.path.exists(plink.path):
                    bad = True
                if bad:
                    remove_bad_link(element, attribute, link, pos)
            open(content(path), 'wb').write(tostring(root, pretty_print))

def find_html_index(files):
    '''
    Given a list of files, find the most likely root HTML file in the
    list.
    '''
    html_pat = re.compile(r'\.(x){0,1}htm(l){0,1}$', re.IGNORECASE)
    html_files = [f for f in files if html_pat.search(f) is not None]
    if not html_files:
        raise ValueError(_('Could not find an ebook inside the archive'))
    html_files = [(f, os.stat(f).st_size) for f in html_files]
    html_files.sort(cmp = lambda x, y: cmp(x[1], y[1]))
    html_files = [f[0] for f in html_files]
    for q in ('toc', 'index'):
        for f in html_files:
            if os.path.splitext(f)[0].lower() == q:
                return f, os.path.splitext(f)[1].lower()[1:]
    return html_files[-1], os.path.splitext(html_files[-1])[1].lower()[1:]

class HTMLProcessor(Processor, Rationalizer):
    
    def __init__(self, htmlfile, opts, tdir, resource_map, htmlfiles, stylesheets):
        Processor.__init__(self, htmlfile, opts, tdir, resource_map, htmlfiles, 
                           name='html2epub')
        if opts.verbose > 2:
            self.debug_tree('parsed')
        self.detect_chapters()
        
        self.extract_css(stylesheets)
        if self.opts.base_font_size2 > 0:
            self.font_css = self.rationalize(self.external_stylesheets+[self.stylesheet], 
                                             self.root, self.opts)
        if opts.verbose > 2:
            self.debug_tree('nocss')
            
        if hasattr(self.body, 'xpath'):
            for script in list(self.body.xpath('descendant::script')):
                script.getparent().remove(script)
                
        self.fix_markup()
            
    def convert_image(self, img):
        rpath = img.get('src', '')
        path = os.path.join(os.path.dirname(self.save_path()), *rpath.split('/'))
        if os.path.exists(path) and os.path.isfile(path):
            if QApplication.instance() is None:
                app = QApplication([])
                app
            p = QPixmap()
            p.load(path)
            if not p.isNull():
                p.save(path+'_calibre_converted.jpg')
                os.remove(path)
                for key, val in self.resource_map.items():
                    if val == rpath:
                        self.resource_map[key] = rpath+'_calibre_converted.jpg'
        img.set('src', rpath+'_calibre_converted.jpg')
        
    def fix_markup(self):
        '''
        Perform various markup transforms to get the output to render correctly 
        in the quirky ADE.
        '''
        # Replace <br> that are children of <body> with <p>&nbsp;</p>
        if hasattr(self.body, 'xpath'):
            for br in self.body.xpath('./br'):
                br.tag = 'p'
                br.text = u'\u00a0'
                
        if self.opts.profile.remove_object_tags:
            for tag in self.root.xpath('//embed'):
                tag.getparent().remove(tag)
            for tag in self.root.xpath('//object'):
                if tag.get('type', '').lower().strip() in ('image/svg+xml',):
                    continue
                tag.getparent().remove(tag)
                
        
        for tag in self.root.xpath('//title|//style'):
            if not tag.text:
                tag.getparent().remove(tag)
        for tag in self.root.xpath('//script'):
            if not tag.text and not tag.get('src', False):
                tag.getparent().remove(tag)
    
    def save(self):
        for meta in list(self.root.xpath('//meta')):
            meta.getparent().remove(meta)
        #for img in self.root.xpath('//img[@src]'):
        #    self.convert_image(img)
        Processor.save(self)
        
    
            

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
    resource_map, stylesheets = {}, {}
    toc = TOC(base_path=tdir, type='root')
    stylesheet_map = {}
    for htmlfile in filelist:
        logging.getLogger('html2epub').debug('Processing %s...'%htmlfile)
        hp = HTMLProcessor(htmlfile, opts, os.path.join(tdir, 'content'), 
                           resource_map, filelist, stylesheets)
        hp.populate_toc(toc)
        hp.save()
        stylesheet_map[os.path.basename(hp.save_path())] = \
            [s for s in hp.external_stylesheets + [hp.stylesheet, hp.font_css, hp.override_css] if s is not None]
    
    logging.getLogger('html2epub').debug('Saving stylesheets...')
    if opts.base_font_size2 > 0:
        Rationalizer.remove_font_size_information(stylesheets.values())
        for path, css in stylesheets.items():
            raw = getattr(css, 'cssText', css)
            if isinstance(raw, unicode):
                raw = raw.encode('utf-8')
            open(path, 'wb').write(raw)
    if toc.count('chapter') > opts.toc_threshold:
        toc.purge(['file', 'link', 'unknown'])
    if toc.count('chapter') + toc.count('file') > opts.toc_threshold:
        toc.purge(['link', 'unknown'])
    toc.purge(['link'], max=opts.max_toc_links)
    
    return resource_map, hp.htmlfile_map, toc, stylesheet_map

TITLEPAGE = '''\
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
    <head>
        <title>Cover</title>
        <style type="text/css" title="override_css">
            @page {padding: 0pt; margin:0pt}
            body { text-align: center; padding:0pt; margin: 0pt; }
            div { margin: 0pt; padding: 0pt; }
        </style>
    </head>
    <body>
        <div>
            <img src="%s" alt="cover" style="height: 100%%" />
        </div>
    </body>
</html>
'''

def create_cover_image(src, dest, screen_size, rescale_cover=True):
    try:
        from PyQt4.Qt import QImage, Qt
        if QApplication.instance() is None:
            QApplication([])
        im = QImage()
        im.load(src)
        if im.isNull():
            raise ValueError('Invalid cover image')
        if rescale_cover and screen_size is not None:
            width, height = im.width(), im.height()
            dw, dh = (screen_size[0]-width)/float(width), (screen_size[1]-height)/float(height)
            delta = min(dw, dh)
            if delta > 0:
                nwidth = int(width + delta*(width))
                nheight = int(height + delta*(height))
                im = im.scaled(int(nwidth), int(nheight), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        im.save(dest)
    except:
        import traceback
        traceback.print_exc()
        return False
    return True

def process_title_page(mi, filelist, htmlfilemap, opts, tdir):
    old_title_page = None
    f = lambda x : os.path.normcase(os.path.normpath(x))
    if mi.cover:
        if f(filelist[0].path) == f(mi.cover):
            old_title_page = htmlfilemap[filelist[0].path]
    #logger = logging.getLogger('html2epub')
    metadata_cover = mi.cover
    if metadata_cover and not os.path.exists(metadata_cover):
        metadata_cover = None
        
    cpath = '/'.join(('resources', '_cover_.jpg'))
    cover_dest = os.path.join(tdir, 'content', *cpath.split('/'))
    if metadata_cover is not None:
        if not create_cover_image(metadata_cover, cover_dest, 
                                  opts.profile.screen_size):
            metadata_cover = None
    specified_cover = opts.cover
    if specified_cover and not os.path.exists(specified_cover):
        specified_cover = None
    if specified_cover is not None:
        if not create_cover_image(specified_cover, cover_dest, 
                                  opts.profile.screen_size):
            specified_cover = None
            
    cover = metadata_cover if specified_cover is None or (opts.prefer_metadata_cover and metadata_cover is not None) else specified_cover

    if cover is not None:
        titlepage = TITLEPAGE%cpath
        tp = 'calibre_title_page.html' if old_title_page is None else old_title_page 
        tppath = os.path.join(tdir, 'content', tp)
        with open(tppath, 'wb') as f:
            f.write(titlepage)
        return tp if old_title_page is None else None, True
    elif os.path.exists(cover_dest):
        os.remove(cover_dest)
    return None, old_title_page is not None

def find_oeb_cover(htmlfile):
    if os.stat(htmlfile).st_size > 2048:
        return None
    match = re.search(r'(?i)<img[^<>]+src\s*=\s*[\'"](.+?)[\'"]', open(htmlfile, 'rb').read())
    if match:
        return match.group(1)

def condense_ncx(ncx_path):
    tree = etree.parse(ncx_path)
    for tag in tree.getroot().iter(tag=etree.Element):
        if tag.text:
            tag.text = tag.text.strip()
        if tag.tail:
            tag.tail = tag.tail.strip()
    compressed = etree.tostring(tree.getroot(), encoding='utf-8')
    open(ncx_path, 'wb').write(compressed)

def convert(htmlfile, opts, notification=None, create_epub=True, 
            oeb_cover=False, extract_to=None):
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
    if opts.from_opf:
        opts.from_opf = os.path.abspath(opts.from_opf)
    if opts.from_ncx:
        opts.from_ncx = os.path.abspath(opts.from_ncx)
    if htmlfile.lower().endswith('.opf'):
        opf = OPF(htmlfile, os.path.dirname(os.path.abspath(htmlfile)))
        filelist = opf_traverse(opf, verbose=opts.verbose, encoding=opts.encoding)
        if not filelist:
            # Bad OPF look for a HTML file instead
            htmlfile = find_html_index(walk(os.path.dirname(htmlfile)))[0]
            if htmlfile is None:
                raise ValueError('Could not find suitable file to convert.')
            filelist = get_filelist(htmlfile, opts)[1]
        mi = merge_metadata(None, opf, opts)
    else:
        opf, filelist = get_filelist(htmlfile, opts)
        mi = merge_metadata(htmlfile, opf, opts)
    opts.chapter = XPath(opts.chapter, 
                    namespaces={'re':'http://exslt.org/regular-expressions'})
    if opts.level1_toc:
        opts.level1_toc = XPath(opts.level1_toc, 
                            namespaces={'re':'http://exslt.org/regular-expressions'})
    else:
        opts.level1_toc = None
    if opts.level2_toc:
        opts.level2_toc = XPath(opts.level2_toc, 
                            namespaces={'re':'http://exslt.org/regular-expressions'})
    else:
        opts.level2_toc = None 
    
    with TemporaryDirectory(suffix='_html2epub', keep=opts.keep_intermediate) as tdir:
        if opts.keep_intermediate:
            print 'Intermediate files in', tdir
        resource_map, htmlfile_map, generated_toc, stylesheet_map = \
                                        parse_content(filelist, opts, tdir)
        logger = logging.getLogger('html2epub')
        resources = [os.path.join(tdir, 'content', f) for f in resource_map.values()]
        
        
        title_page, has_title_page = process_title_page(mi, filelist, htmlfile_map, opts, tdir)
        spine = [htmlfile_map[f.path] for f in filelist]
        if not oeb_cover and title_page is not None:
            spine = [title_page] + spine
        mi.cover = None
        mi.cover_data = (None, None)
            
            
        mi = create_metadata(tdir, mi, spine, resources)
        buf = cStringIO.StringIO()
        if mi.toc:
            rebase_toc(mi.toc, htmlfile_map, tdir)
        if opts.use_auto_toc or mi.toc is None or len(list(mi.toc.flat())) < 2:
            mi.toc = generated_toc
        if opts.from_ncx:
            toc = TOC()
            toc.read_ncx_toc(opts.from_ncx)
            mi.toc = toc
        for item in mi.manifest:
            if getattr(item, 'mime_type', None) == 'text/html':
                item.mime_type = 'application/xhtml+xml'
        opf_path = os.path.join(tdir, 'metadata.opf')
        with open(opf_path, 'wb') as f:
            mi.render(f, buf, 'toc.ncx')
        toc = buf.getvalue()
        if toc:
            with open(os.path.join(tdir, 'toc.ncx'), 'wb') as f:
                f.write(toc)
            if opts.show_ncx:
                print toc
        split(opf_path, opts, stylesheet_map)
        check_links(opf_path, opts.pretty_print)
        
        opf = OPF(opf_path, tdir)
        opf.remove_guide()
        oeb_cover_file = None
        if oeb_cover and title_page is not None:
            oeb_cover_file = find_oeb_cover(os.path.join(tdir, 'content', title_page))
        if has_title_page or (oeb_cover and oeb_cover_file):
            opf.create_guide_element()
            if has_title_page and not oeb_cover:
                opf.add_guide_item('cover', 'Cover', 'content/'+spine[0])
            if oeb_cover and oeb_cover_file:
                opf.add_guide_item('cover', 'Cover', 'content/'+oeb_cover_file)
        
        cpath = os.path.join(tdir, 'content', 'resources', '_cover_.jpg')
        if os.path.exists(cpath):
            opf.add_path_to_manifest(cpath, 'image/jpeg')    
        with open(opf_path, 'wb') as f:
            raw = opf.render()
            if not raw.startswith('<?xml '):
                raw = '<?xml version="1.0"  encoding="UTF-8"?>\n'+raw
            f.write(raw)
        ncx_path = os.path.join(os.path.dirname(opf_path), 'toc.ncx')
        if os.path.exists(ncx_path) and os.stat(ncx_path).st_size > opts.profile.flow_size:
            logger.info('Condensing NCX from %d bytes...'%os.stat(ncx_path).st_size)
            condense_ncx(ncx_path)
            if os.stat(ncx_path).st_size > opts.profile.flow_size:
                logger.warn('NCX still larger than allowed size at %d bytes. Menu based Table of Contents may not work on device.'%os.stat(ncx_path).st_size)
            
        if create_epub:
            epub = initialize_container(opts.output)
            epub.add_dir(tdir)
            epub.close()
            run_plugins_on_postprocess(opts.output, 'epub')
            logger.info(_('Output written to ')+opts.output)
        
        if opts.show_opf:
            print open(os.path.join(tdir, 'metadata.opf')).read()
        
        if opts.extract_to is not None:
            if os.path.exists(opts.extract_to):
                shutil.rmtree(opts.extract_to)
            shutil.copytree(tdir, opts.extract_to)
            
        if extract_to is not None:
            if os.path.exists(extract_to):
                shutil.rmtree(extract_to)
            shutil.copytree(tdir, extract_to)
            
        
            
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
