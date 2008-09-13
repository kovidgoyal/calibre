from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Code to recursively parse HTML files and create an open ebook in a specified
directory or zip file. All the action starts in :function:`create_dir`.
'''

import sys, re, os, shutil, logging, tempfile, cStringIO
from urlparse import urlparse
from urllib import unquote

from lxml import html
from lxml.etree import XPath
get_text = XPath("//text()")

from calibre import LoggingInterface, unicode_path
from calibre.ebooks.chardet import xml_to_unicode, ENCODING_PATS
from calibre.utils.config import Config, StringConfig
from calibre.ebooks.metadata.opf import OPFReader, OPFCreator
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.meta import get_metadata
from calibre.ptempfile import PersistentTemporaryDirectory, PersistentTemporaryFile
from calibre.utils.zipfile import ZipFile


class Link(object):
    '''
    Represents a link in a HTML file.
    '''
    
    @classmethod
    def url_to_local_path(cls, url, base):
        path = url.path
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(base, path))
    
    def __init__(self, url, base):
        '''
        :param url:  The url this link points to. Must be an unquoted unicode string.
        :param base: The base directory that relative URLs are with respect to.
                     Must be a unicode string.
        '''
        assert isinstance(url, unicode) and isinstance(base, unicode)
        self.url         = url
        self.parsed_url  = urlparse(unquote(self.url))
        self.is_local    = self.parsed_url.scheme in ('', 'file')
        self.is_internal = self.is_local and not bool(self.parsed_url.path)
        self.path        = None
        self.fragment    = self.parsed_url.fragment 
        if self.is_local and not self.is_internal:
            self.path = self.url_to_local_path(self.parsed_url, base)

    def __hash__(self):
        if self.path is None:
            return hash(self.url)
        return hash(self.path)

    def __eq__(self, other):
        return self.path == getattr(other, 'path', other)
    
    def __str__(self):
        return u'Link: %s --> %s'%(self.url, self.path) 
        

class IgnoreFile(Exception):
    
    def __init__(self, msg, errno):
        Exception.__init__(self, msg)
        self.doesnt_exist = errno == 2
        self.errno = errno

class HTMLFile(object):
    '''
    Contains basic information about an HTML file. This
    includes a list of links to other files as well as
    the encoding of each file. Also tries to detect if the file is not a HTML
    file in which case :member:`is_binary` is set to True.

    The encoding of the file is available as :member:`encoding`.
    '''
    
    HTML_PAT = re.compile(r'<\s*html', re.IGNORECASE)
    LINK_PAT = re.compile(
    r'<\s*a\s+.*?href\s*=\s*(?:(?:"(?P<url1>[^"]+)")|(?:\'(?P<url2>[^\']+)\')|(?P<url3>[^\s]+))',
    re.DOTALL|re.IGNORECASE)
    
    def __init__(self, path_to_html_file, level, encoding, verbose):
        '''
        :param level: The level of this file. Should be 0 for the root file.
        :param encoding: Use `encoding` to decode HTML.
        '''
        self.path  = unicode_path(path_to_html_file, abs=True)
        self.base  = os.path.dirname(self.path)
        self.level = level
        self.links = []
        
        try:
            with open(self.path, 'rb') as f:
                src = f.read()
        except IOError, err:
            msg = 'Could not read from file: %s with error: %s'%(self.path, unicode(err))
            if level == 0:
                raise IOError(msg)
            raise IgnoreFile(msg, err.errno)
        
        self.is_binary = not bool(self.HTML_PAT.search(src[:1024]))
        
        if not self.is_binary:
            if encoding is None:
                encoding = xml_to_unicode(src[:4096], verbose=verbose)[-1]
                self.encoding = encoding

            src = src.decode(encoding, 'replace')
            self.find_links(src)
                
        
                    
    def __eq__(self, other):
        return self.path == getattr(other, 'path', other)
    
    def __str__(self):
        return u'HTMLFile:%d:%s:%s'%(self.level, 'b' if self.is_binary else 'a', self.path)
    
    def __repr__(self):
        return str(self)
                    
        
    def find_links(self, src):
        for match in self.LINK_PAT.finditer(src):
            url = None
            for i in ('url1', 'url2', 'url3'):
                url = match.group(i)
                if url:
                    break
            link = self.resolve(url)
            if link not in self.links:
                self.links.append(link)
                
    def resolve(self, url):
        return Link(url, self.base)


def depth_first(root, flat, visited=set([])):
    yield root
    visited.add(root)
    for link in root.links:
        if link.path is not None and link not in visited:
            try:
                index = flat.index(link)
            except ValueError: # Can happen if max_levels is used
                continue
            hf = flat[index]
            if hf not in visited:
                yield hf
                visited.add(hf)
                for hf in depth_first(hf, flat, visited):
                    if hf not in visited:
                        yield hf
                        visited.add(hf)
        
                                
def traverse(path_to_html_file, max_levels=sys.maxint, verbose=0, encoding=None):
    '''
    Recursively traverse all links in the HTML file.
    
    :param max_levels: Maximum levels of recursion. Must be non-negative. 0 
                       implies that no links in the root HTML file are followed.
    :param encoding:   Specify character encoding of HTML files. If `None` it is
                       auto-detected.
    :return:           A pair of lists (breadth_first, depth_first). Each list contains
                       :class:`HTMLFile` objects.
    '''
    assert max_levels >= 0
    level = 0
    flat =  [HTMLFile(path_to_html_file, level, encoding, verbose)]
    next_level = list(flat)
    while level < max_levels and len(next_level) > 0:
        level += 1
        nl = []
        for hf in next_level:
            rejects = []
            for link in hf.links:
                if link.path is None or link.path in flat:
                    continue
                try:
                    nf = HTMLFile(link.path, level, encoding, verbose)
                    nl.append(nf)
                    flat.append(nf)
                except IgnoreFile, err:
                    rejects.append(link)
                    if not err.doesnt_exist or verbose > 1:
                        print str(err)
            for link in rejects:
                hf.links.remove(link)
                
        next_level = list(nl)
        
    return flat, list(depth_first(flat[0], flat))
    
    
def opf_traverse(opf_reader, verbose=0, encoding=None):
    '''
    Return a list of :class:`HTMLFile` objects in the order specified by the
    `<spine>` element of the OPF.
    
    :param opf_reader: An :class:`calibre.ebooks.metadata.opf.OPFReader` instance.  
    :param encoding:   Specify character encoding of HTML files. If `None` it is
                       auto-detected.
    '''
    if not opf_reader.spine:
        raise ValueError('OPF does not have a spine')
    flat = []
    for path in opf_reader.spine.items():
        if path not in flat:
            flat.append(os.path.abspath(path))
    flat = [HTMLFile(path, 0, encoding, verbose) for path in flat]
    return flat
            


class PreProcessor(object):
    PREPROCESS = []
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
                  (re.compile(r'-\n\r?'), lambda match: ''),
                  
                  ]
    
    # Fix Book Designer markup
    BOOK_DESIGNER = [
                     # HR
                     (re.compile('<hr>', re.IGNORECASE),
                      lambda match : '<span style="page-break-after:always"> </span>'),
                     # Create header tags
                     (re.compile('<h2[^><]*?id=BookTitle[^><]*?(align=)*(?(1)(\w+))*[^><]*?>[^><]*?</h2>', re.IGNORECASE),
                      lambda match : '<h1 id="BookTitle" align="%s">%s</h1>'%(match.group(2) if match.group(2) else 'center', match.group(3))),
                     (re.compile('<h2[^><]*?id=BookAuthor[^><]*?(align=)*(?(1)(\w+))*[^><]*?>[^><]*?</h2>', re.IGNORECASE),
                      lambda match : '<h2 id="BookAuthor" align="%s">%s</h2>'%(match.group(2) if match.group(2) else 'center', match.group(3))),
                     (re.compile('<span[^><]*?id=title[^><]*?>(.*?)</span>', re.IGNORECASE|re.DOTALL),
                      lambda match : '<h2 class="title">%s</h2>'%(match.group(1),)),
                     (re.compile('<span[^><]*?id=subtitle[^><]*?>(.*?)</span>', re.IGNORECASE|re.DOTALL),
                      lambda match : '<h3 class="subtitle">%s</h3>'%(match.group(1),)),
                     ]
    
    def is_baen(self, src):
        return re.compile(r'<meta\s+name="Publisher"\s+content=".*?Baen.*?"', 
                          re.IGNORECASE).search(src) is not None
                          
    def is_book_designer(self, raw):
        return re.search('<H2[^><]*id=BookTitle', raw) is not None
    
    def is_pdftohtml(self, src):
        return src.startswith('<!-- created by calibre\'s pdftohtml -->')
                          
    def preprocess(self, html):
        if self.is_baen(html):
            rules = self.BAEN
        elif self.is_book_designer(html):
            rules = self.BOOK_DESIGNER
        elif self.is_pdftohtml(html):
            rules = self.PDFTOHTML
        else:
            rules = []
        for rule in self.PREPROCESS + rules:
            html = rule[0].sub(rule[1], html)
        
        return html
    
class Parser(PreProcessor, LoggingInterface):
    
    def __init__(self, htmlfile, opts, tdir, resource_map, htmlfiles, name='htmlparser'):
        LoggingInterface.__init__(self, logging.getLogger(name))
        self.setup_cli_handler(opts.verbose)
        self.htmlfile = htmlfile
        self.opts = opts
        self.tdir = tdir
        self.resource_map = resource_map
        self.htmlfiles = htmlfiles
        self.resource_dir = os.path.join(tdir, 'resources')
        save_counter = 1
        self.htmlfile_map = {}
        for f in self.htmlfiles:
            name = os.path.basename(f.path)
            if name in self.htmlfile_map.values():
                name = os.path.splitext(name)[0] + '_cr_%d'%save_counter + os.path.splitext(name)[1]
                save_counter += 1
            self.htmlfile_map[f.path] = name
        
        self.parse_html()
        self.root.rewrite_links(self.rewrite_links, resolve_base_href=False)
        
    def save(self):
        '''
        Save processed HTML into the content directory.
        Should be called after all HTML processing is finished.
        '''
        with open(os.path.join(self.tdir, self.htmlfile_map[self.htmlfile.path]), 'wb') as f:
            f.write(html.tostring(self.root, 
                        encoding='utf-8', method='xml',
                        include_meta_content_type=True,
                        pretty_print=self.opts.pretty_print)
                    )
            return f.name


    def parse_html(self):
        ''' Create lxml ElementTree from HTML '''
        self.log_info('\tParsing '+os.sep.join(self.htmlfile.path.split(os.sep)[-3:]))
        src = open(self.htmlfile.path, 'rb').read().decode(self.htmlfile.encoding, 'replace')
        src = self.preprocess(src)
        # lxml chokes on unicode input when it contains encoding declarations
        for pat in ENCODING_PATS:
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
    
    def debug_tree(self, name):
        '''
        Dump source tree for later debugging.
        '''
        tdir = tempfile.gettempdir()
        if not os.path.exists(tdir):
            os.makedirs(tdir)
        with open(os.path.join(tdir, '%s-%s-%s.html'%\
                    (self.name, os.path.basename(self.htmlfile.path), name)), 'wb') as f:
            f.write(html.tostring(self.root, encoding='utf-8'))
            self.log_debug(_('Written processed HTML to ')+f.name)
    
            
    def rewrite_links(self, olink):
        '''
        Make all links in document relative so that they work in the EPUB container.
        Also copies any resources (like images, stylesheets, scripts, etc.) into
        the local tree.
        '''
        if not isinstance(olink, unicode):
            olink = olink.decode(self.htmlfile.encoding)
        link = self.htmlfile.resolve(olink)
        if not link.path or not os.path.exists(link.path) or not os.path.isfile(link.path):
            return olink
        if link.path in self.htmlfiles:
            return self.htmlfile_map[link.path]
        if link.path in self.resource_map.keys():
            return self.resource_map[link.path]
        name = os.path.basename(link.path)
        name, ext = os.path.splitext(name)
        name += ('_%d'%len(self.resource_map)) + ext
        shutil.copyfile(link.path, os.path.join(self.resource_dir, name))
        name = 'resources/' + name
        self.resource_map[link.path] = name
        return name
    
    def extract_css(self):
        '''
        Remove all CSS information from the document and store in self.raw_css. 
        This includes <font> tags.
        '''
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
            font.set('id', 'calibre_font_id_%d'%font_id)
            font_id += 1
            css.append('#%s { %s }'%(id, setting))
            
        
        css_counter = 1
        for elem in self.root.xpath('//*[@style]'):
            if 'id' not in elem.keys():
                elem.set('id', 'calibre_css_id_%d'%css_counter)
                css_counter += 1
            css.append('#%s {%s}'%(elem.get('id'), elem.get('style')))
            elem.attrib.pop('style')
        chapter_counter = 1
        for chapter in self.detected_chapters:
            if chapter.tag.lower() == 'a':
                if 'name' in chapter.keys():
                    chapter.attrib['id'] = id = chapter.get('name')
                elif 'id' in chapter.keys():
                    id = chapter.get('id')
                else:
                    id = 'calibre_detected_chapter_%d'%chapter_counter
                    chapter_counter += 1
                    chapter.set('id', id)
            else:
                if 'id' not in chapter.keys():
                    id = 'calibre_detected_chapter_%d'%chapter_counter
                    chapter_counter += 1
                    chapter.set('id', id)
            css.append('#%s {%s}'%(id, 'page-break-before:always'))
                     
        self.raw_css = '\n\n'.join(css)
        # TODO: Figure out what to do about CSS imports from linked stylesheets    

def config(defaults=None, config_name='html', 
           desc=_('Options to control the traversal of HTML')):
    if defaults is None:
        c = Config(config_name, desc)
    else:
        c = StringConfig(defaults, desc)
        
    c.add_opt('output', ['-o', '--output'], default=None,
             help=_('The output directory. Default is the current directory.'))
    c.add_opt('encoding', ['--encoding'], default=None, 
              help=_('Character encoding for HTML files. Default is to auto detect.'))
    c.add_opt('zip', ['--zip'], default=False,
              help=_('Create the output in a zip file. If this option is specified, the --output should be the name of a file not a directory.'))
    
    traversal = c.add_group('traversal', _('Control the following of links in HTML files.'))
    traversal('breadth_first', ['--breadth-first'], default=False,
              help=_('Traverse links in HTML files breadth first. Normally, they are traversed depth first'))
    traversal('max_levels', ['--max-levels'], default=sys.getrecursionlimit(), group='traversal',
              help=_('Maximum levels of recursion when following links in HTML files. Must be non-negative. 0 implies that no links in the root HTML file are followed.'))
    
    metadata = c.add_group('metadata', _('Set metadata of the generated ebook'))
    metadata('title', ['-t', '--title'], default=None,
             help=_('Set the title. Default is to autodetect.'))
    metadata('authors', ['-a', '--authors'], default=_('Unknown'),
             help=_('The author(s) of the ebook, as a comma separated list.'))
        
    debug = c.add_group('debug', _('Options useful for debugging'))
    debug('verbose', ['-v', '--verbose'], default=0, action='count',
          help=_('Be more verbose while processing. Can be specified multiple times to increase verbosity.'))
    debug('pretty_print', ['--pretty-print'], default=False,
          help=_('Output HTML is "pretty printed" for easier parsing by humans'))
    
    return c

def option_parser():
    c = config()
    return c.option_parser(usage=_('''\
%prog [options] file.html|opf

Follow all links in an HTML file and collect them into the specified directory.
Also collects any references resources like images, stylesheets, scripts, etc. 
If an OPF file is specified instead, the list of files in its <spine> element
is used.
'''))

def search_for_opf(dir):
    for f in os.listdir(dir):
        if f.lower().endswith('.opf'):
            return OPFReader(open(os.path.join(dir, f), 'rb'), dir)


def get_filelist(htmlfile, opts):
    '''
    Build list of files references by html file or try to detect and use an
    OPF file instead.
    '''
    print 'Building file list...'
    dir = os.path.dirname(htmlfile)
    if not dir:
        dir = os.getcwd()
    opf = search_for_opf(dir)
    filelist = None
    if opf is not None:
        filelist = opf_traverse(opf, verbose=opts.verbose, encoding=opts.encoding)
    if not filelist:
        filelist = traverse(htmlfile, verbose=opts.verbose, encoding=opts.encoding)\
                    [0 if opts.breadth_first else 1]
    if opts.verbose:
        print '\tFound files...'
        for f in filelist:
            print '\t\t', f
    return opf, filelist

def parse_content(filelist, opts):
    '''
    Parse content, rewriting links and copying resources.
    '''
    if not opts.output:
        opts.output = '.'
    opts.output = os.path.abspath(opts.output)
    rdir = os.path.join(opts.output, 'content', 'resources')
    if not os.path.exists(rdir):
        os.makedirs(rdir)
    resource_map = {}
    for htmlfile in filelist:
        p = Parser(htmlfile, opts, os.path.join(opts.output, 'content'),
                           resource_map, filelist)
        p.save()
    return resource_map, p.htmlfile_map

def merge_metadata(htmlfile, opf, opts):
    '''
    Merge metadata from various sources.
    '''
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
    return mi

def create_metadata(basepath, mi, filelist, resources):
    '''
    Create an OPF metadata object with correct spine and manifest.
    '''
    mi = OPFCreator(basepath, mi)
    entries = [('content/'+f, None) for f in filelist] + [(f, None) for f in resources]
    mi.create_manifest(entries)
    mi.create_spine(['content/'+f for f in filelist])
    return mi

def rebase_toc(toc, htmlfile_map, basepath, root=True):
    '''
    Rebase a :class:`calibre.ebooks.metadata.toc.TOC` object. Maps all entries
    in the TOC to point to their new locations relative to the new OPF file.
    '''
    def fix_entry(entry):
        if entry.abspath in htmlfile_map.keys():
            entry.href = 'content/' +  htmlfile_map[entry.abspath]
            
    for entry in toc:
        rebase_toc(entry, htmlfile_map, basepath, root=False)
        fix_entry(entry)
    if root:
        toc.base_path = basepath

def create_dir(htmlfile, opts):
    '''
    Create a directory that contains the open ebook
    '''
    if htmlfile.lower().endswith('.opf'):
        opf = OPFReader(open(htmlfile, 'rb'), os.path.dirname(os.path.abspath(htmlfile)))
        filelist = opf_traverse(opf, verbose=opts.verbose, encoding=opts.encoding)
        mi = MetaInformation(opf)
    else:
        opf, filelist = get_filelist(htmlfile, opts)
        mi = merge_metadata(htmlfile, opf, opts)
    
    resource_map, htmlfile_map = parse_content(filelist, opts)
    resources = [os.path.join(opts.output, 'content', f) for f in resource_map.values()]
    
    if opf and opf.cover and os.access(opf.cover, os.R_OK):
        cpath = os.path.join(opts.output, 'content', 'resources', '_cover_'+os.path.splitext(opf.cover)[-1])
        shutil.copyfile(opf.cover, cpath)
        resources.append(cpath)
        mi.cover = cpath
    
    spine = [htmlfile_map[f.path] for f in filelist]
    mi = create_metadata(opts.output, mi, spine, resources)
    buf = cStringIO.StringIO()
    if mi.toc:
        rebase_toc(mi.toc, htmlfile_map, opts.output)
    with open(os.path.join(opts.output, 'metadata.opf'), 'wb') as f:
        mi.render(f, buf)
    toc = buf.getvalue()
    if toc:
        with open(os.path.join(opts.output, 'toc.ncx'), 'wb') as f:
            f.write(toc)
    print 'Open ebook created in', opts.output
    
def create_oebzip(htmlfile, opts):
    '''
    Create a zip file that contains the Open ebook.
    '''
    tdir = PersistentTemporaryDirectory('_create_oebzip')
    if opts.output is None:
        opts.output = os.path.join(os.path.splitext(htmlfile)[0]+'.oeb.zip')
    ofile = opts.output
    opts.output = tdir
    create_dir(htmlfile, opts)
    zf = ZipFile(ofile, 'w')
    zf.add_dir(opts.output)
    print 'Output saved to', ofile

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) < 2:
        parser.print_help()
        print _('You must specify an input HTML file')
        return 1
    
    htmlfile = args[1]
    if opts.zip:
        create_oebzip(htmlfile, opts)
    else:
        create_dir(htmlfile, opts)
        
    return 0

def gui_main(htmlfile):
    '''
    Convenience wrapper for use in recursively importing HTML files.
    '''
    pt = PersistentTemporaryFile('_html2oeb_gui.oeb.zip')
    pt.close()
    opts = '''
pretty_print = True
max_levels = 5
output  = %s
'''%repr(pt.name)
    c = config(defaults=opts)
    opts = c.parse()
    create_oebzip(htmlfile, opts)
    zf = ZipFile(pt.name, 'r')
    nontrivial = [f for f in zf.infolist() if f.compress_size > 1 and not f.filename.endswith('.opf')]
    if len(nontrivial) < 2:
        return None
    return pt.name
    

if __name__ == '__main__':
    sys.exit(main())
