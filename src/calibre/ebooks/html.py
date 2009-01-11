from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Code to recursively parse HTML files and create an open ebook in a specified
directory or zip file. All the action starts in :function:`create_dir`.
'''

import sys, re, os, shutil, logging, tempfile, cStringIO, operator, functools
from urlparse import urlparse
from urllib import unquote

from lxml import etree
from lxml.html import HtmlElementClassLookup, HTMLParser as _HTMLParser, \
                      fromstring as _fromstring, tostring as _tostring, \
                      soupparser, HtmlElement
from lxml.etree import XPath
get_text = XPath("//text()")

from calibre import LoggingInterface, unicode_path, entity_to_unicode
from calibre.ebooks.chardet import xml_to_unicode, ENCODING_PATS
from calibre.utils.config import Config, StringConfig
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.meta import get_metadata
from calibre.ebooks.metadata.opf2 import OPF, OPFCreator
from calibre.ptempfile import PersistentTemporaryDirectory, PersistentTemporaryFile
from calibre.utils.zipfile import ZipFile
from cssutils import CSSParser

class HTMLElement(HtmlElement):
    
    @apply
    def specified_font_size():
        
        def fget(self):
            ans = self.get('specified_font_size', '')
            if not ans:
                return lambda x: x
            if ans.startswith('f'):
                return functools.partial(operator.mul, float(ans[1:]))
            return float(ans)
        
        def fset(self, val):
            self.set('specified_font_size', ('f'+repr(val(1))) if callable(val) else repr(val))
                     
        return property(fget=fget, fset=fset)
    
    @apply
    def computed_font_size():
        def fget(self):
            ans = self.get('computed_font_size', '')
            if ans == '':
                return None
            return float(ans)
        
        def fset(self, val):
            self.set('computed_font_size', repr(val))
        
        return property(fget=fget, fset=fset)
    
    def remove_font_size_information(self):
        for elem in self.iter():
            for p in ('computed', 'specified'):
                elem.attrib.pop(p+'_font_size', None)
                
    def getpath(self):
        return self.getroottree().getpath(self)

class Lookup(HtmlElementClassLookup):
    
    def lookup(self, node_type, document, namespace, name):
        if node_type == 'element':
            return HTMLElement
        return HtmlElementClassLookup.lookup(self, node_type, document, namespace, name)

class HTMLParser(_HTMLParser):
    
    def __init__(self, **kwargs):
        super(HTMLParser, self).__init__(**kwargs)
        self.set_element_class_lookup(Lookup())
        
parser = HTMLParser()

def fromstring(raw, **kw):
    return _fromstring(raw, parser=parser, **kw)

def tostring(root, pretty_print=False):
    return _tostring(root, encoding='utf-8', method='xml', 
                         include_meta_content_type=True, 
                         pretty_print=pretty_print)
    
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
    
    HTML_PAT  = re.compile(r'<\s*html', re.IGNORECASE)
    TITLE_PAT = re.compile('<title>([^<>]+)</title>', re.IGNORECASE)
    LINK_PAT  = re.compile(
    r'<\s*a\s+.*?href\s*=\s*(?:(?:"(?P<url1>[^"]+)")|(?:\'(?P<url2>[^\']+)\')|(?P<url3>[^\s>]+))',
    re.DOTALL|re.IGNORECASE)
    
    def __init__(self, path_to_html_file, level, encoding, verbose, referrer=None):
        '''
        :param level: The level of this file. Should be 0 for the root file.
        :param encoding: Use `encoding` to decode HTML.
        :param referrer: The :class:`HTMLFile` that first refers to this file.
        '''
        self.path     = unicode_path(path_to_html_file, abs=True)
        self.title    = os.path.splitext(os.path.basename(self.path))[0]
        self.base     = os.path.dirname(self.path)
        self.level    = level
        self.referrer = referrer
        self.links    = []
        
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
            else:
                self.encoding = encoding

            src = src.decode(encoding, 'replace')
            match = self.TITLE_PAT.search(src)
            self.title = match.group(1) if match is not None else self.title
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
                    nf = HTMLFile(link.path, level, encoding, verbose, referrer=hf)
                    if nf.is_binary:
                        raise IgnoreFile('%s is a binary file'%nf.path, -1)
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
        path = os.path.abspath(path)
        if path not in flat:
            flat.append(os.path.abspath(path))
    for item in opf_reader.manifest:
        if 'html' in item.mime_type:
            path = os.path.abspath(item.path)
            if path not in flat:
                flat.append(path)
    for i, path in enumerate(flat):
        if not os.path.exists(path):
            path = path.replace('&', '%26')
            if os.path.exists(path):
                flat[i] = path
                for item in opf_reader.itermanifest():
                    item.set('href', item.get('href').replace('&', '%26'))
    ans = []
    for path in flat:
        if os.path.exists(path):
            ans.append(HTMLFile(path, 0, encoding, verbose))
        else:
            print 'WARNING: OPF spine item %s does not exist'%path
    ans = [f for f in ans if not f.is_binary]
    return ans
            

convert_entities = functools.partial(entity_to_unicode, exceptions=['quot', 'apos', 'lt', 'gt', 'amp'])
_span_pat = re.compile('<span.*?</span>', re.DOTALL|re.IGNORECASE)

def sanitize_head(match):
    x = match.group(1)
    x = _span_pat.sub('', x)
    return '<head>\n'+x+'\n</head>'
    
class PreProcessor(object):
    PREPROCESS = [
                  # Some idiotic HTML generators (Frontpage I'm looking at you)
                  # Put all sorts of crap into <head>. This messes up lxml
                  (re.compile(r'<head[^>]*>(.*?)</head>', re.IGNORECASE|re.DOTALL), 
                   sanitize_head),
                  # Convert all entities, since lxml doesn't handle them well
                  (re.compile(r'&(\S+?);'), convert_entities),
                  
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
                  
                  # Remove gray background
                  (re.compile(r'<BODY[^<>]+>'), lambda match : '<BODY>')
                  
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
        return '<!-- created by calibre\'s pdftohtml -->' in src[:1000]
                          
    def preprocess(self, html):
        opts = getattr(self, 'opts', False)
        if opts and hasattr(opts, 'profile') and getattr(opts.profile, 'remove_special_chars', False):
            html = opts.profile.remove_special_chars.sub('', html)
        if self.is_baen(html):
            rules = []
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
#    SELF_CLOSING_TAGS = 'hr|br|link|img|meta|input|area|base|basefont'
#    SELF_CLOSING_RULES = [re.compile(p[0]%SELF_CLOSING_TAGS, re.IGNORECASE) for p in 
#                          [
#                           (r'<(?P<tag>%s)(?P<attrs>(\s+[^<>]*){0,1})(?<!/)>',
#                            '<\g<tag>\g<attrs> />'),
#                           (),
#                           ]
#                          ]
    
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
        self.level = self.htmlfile.level
        for f in self.htmlfiles:
            name = os.path.basename(f.path)
            if name in self.htmlfile_map.values():
                name = os.path.splitext(name)[0] + '_cr_%d'%save_counter + os.path.splitext(name)[1]
                save_counter += 1
            self.htmlfile_map[f.path] = name
        
        self.parse_html()
        self.root.rewrite_links(self.rewrite_links, resolve_base_href=False)
        for bad in ('xmlns', 'lang', 'xml:lang'): # lxml also adds these attributes for XHTML documents, leading to duplicates
            if self.root.get(bad, None) is not None:
                self.root.attrib.pop(bad)
        
    def save_path(self):
        return os.path.join(self.tdir, self.htmlfile_map[self.htmlfile.path])
    
    def declare_xhtml_namespace(self, match):
        if not match.group('raw'):
            return '<html xmlns="http://www.w3.org/1999/xhtml">'
        raw = match.group('raw')
        m = re.search(r'(?i)xmlns\s*=\s*[\'"](?P<uri>[^"\']*)[\'"]', raw)
        if not m:
            return '<html xmlns="http://www.w3.org/1999/xhtml" %s>'%raw
        else:
            return  match.group().replace(m.group('uri'), "http://www.w3.org/1999/xhtml")
    
    def save(self):
        '''
        Save processed HTML into the content directory.
        Should be called after all HTML processing is finished.
        '''
        ans = tostring(self.root, pretty_print=self.opts.pretty_print)
        ans = re.sub(r'(?i)<\s*html(?P<raw>\s+[^>]*){0,1}>', self.declare_xhtml_namespace, ans[:1000]) + ans[1000:]
        ans = re.compile(r'<head>', re.IGNORECASE).sub('<head>\n\t<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />\n', ans[:1000])+ans[1000:]
            
        with open(self.save_path(), 'wb') as f:
            f.write(ans)
            return f.name


    def parse_html(self):
        ''' Create lxml ElementTree from HTML '''
        self.log_info('\tParsing '+os.sep.join(self.htmlfile.path.split(os.sep)[-3:]))
        if self.htmlfile.is_binary:
            raise ValueError('Not a valid HTML file: '+self.htmlfile.path)
        src = open(self.htmlfile.path, 'rb').read().decode(self.htmlfile.encoding, 'replace').strip()
        src = src.replace('\x00', '')
        src = self.preprocess(src)
        # lxml chokes on unicode input when it contains encoding declarations
        for pat in ENCODING_PATS:
            src = pat.sub('', src)
        src = src[src.find('<'):]
        # Remove unclosed <style> tag as that messes up lxml's parsing
        src = re.sub(r'<style>\s*</head>', '', src)
        try:
            self.root = fromstring(src)
        except:
            if self.opts.verbose:
                self.log_exception('lxml based parsing failed')
            self.root = soupparser.fromstring(src, makeelement=parser.makeelement)
        head = self.root.xpath('./head')
        if head:
            head = head[0]
        else:
            head = etree.SubElement(self.root, 'head')
            self.root.remove(head)
            self.root.insert(0, head)

        self.head = head 
        self.body = self.root.body
        for a in self.root.xpath('//a[@name]'):
            a.set('id', a.get('name'))
        if not self.head.xpath('./title'):
            title = etree.SubElement(self.head, 'title')
            title.text = _('Unknown')
    
    def debug_tree(self, name):
        '''
        Dump source tree for later debugging.
        '''
        tdir = tempfile.gettempdir()
        if not os.path.exists(tdir):
            os.makedirs(tdir)
        with open(os.path.join(tdir, '%s-%s.html'%\
                    (os.path.basename(self.htmlfile.path), name)), 'wb') as f:
            f.write(tostring(self.root))
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
        frag = (('#'+link.fragment) if link.fragment else '')
        if link.path == self.htmlfile.path:
            return frag if frag else '#'
        if not link.path or not os.path.exists(link.path) or not os.path.isfile(link.path):
            return olink
        if link.path in self.htmlfiles:
            return self.htmlfile_map[link.path] + frag 
        if re.match(r'\.(x){0,1}htm(l){0,1}', os.path.splitext(link.path)[1]) is not None:
            return olink # This happens when --max-levels is used
        if link.path in self.resource_map.keys():
            return self.resource_map[link.path] + frag
        name = os.path.basename(link.path)
        name, ext = os.path.splitext(name)
        name += ('_%d'%len(self.resource_map)) + ext
        shutil.copyfile(link.path, os.path.join(self.resource_dir, name))
        name = 'resources/' + name
        self.resource_map[link.path] = name
        return name + frag
    
        

class Processor(Parser):
    '''
    This class builds on :class:`Parser` to provide additional methods
    to perform various processing/modification tasks on HTML files.
    '''
    
    LINKS_PATH = XPath('//a[@href]')
    PIXEL_PAT  = re.compile(r'([-]?\d+|[-]?\d*\.\d+)px')
    PAGE_PAT   = re.compile(r'@page[^{]*?{[^}]*?}')
    
    def __init__(self, *args, **kwargs):
        Parser.__init__(self, *args, **kwargs)
        temp = LoggingInterface(logging.getLogger('cssutils'))
        temp.setup_cli_handler(self.opts.verbose)
        self.css_parser = CSSParser(log=temp.logger, loglevel=logging.ERROR)
        self.stylesheet = self.font_css = self.override_css = None
    
    def detect_chapters(self):
        self.detected_chapters = self.opts.chapter(self.root)
        for elem in self.detected_chapters:
            text = u' '.join([t.strip() for t in elem.xpath('descendant::text()')])
            self.log_info('\tDetected chapter: %s', text[:50])
            if self.opts.chapter_mark != 'none':
                hr = etree.Element('hr')
                if elem.getprevious() is None:
                    elem.getparent()[:0] = [hr]
                elif elem.getparent() is not None:
                    insert = None
                    for i, c in enumerate(elem.getparent()):
                        if c is elem:
                            insert = i
                            break
                    elem.getparent()[insert:insert] = [hr]
                if self.opts.chapter_mark != 'rule':
                    hr.set('style', 'width:0pt;page-break-before:always')
                    if self.opts.chapter_mark == 'both':
                        hr2 = etree.Element('hr')
                        hr2.tail = u'\u00a0'
                        p = hr.getparent()
                        i = p.index(hr)
                        p[i:i] = [hr2]
                
                    
        
    def save(self):
        style_path = os.path.splitext(os.path.basename(self.save_path()))[0]
        for i, sheet in enumerate([self.stylesheet, self.font_css, self.override_css]):
            if sheet is not None:
                style = etree.SubElement(self.head, 'link', attrib={'type':'text/css', 'rel':'stylesheet', 
                                                           'href':'resources/%s_%d.css'%(style_path, i),
                                                           'charset':'UTF-8'})
                style.tail = '\n'
                path = os.path.join(os.path.dirname(self.save_path()), *(style.get('href').split('/')))
                self.resource_map[path] = style.get('href')
                raw = getattr(sheet, 'cssText', sheet)
                if isinstance(raw, unicode):
                    raw = raw.encode('utf-8')
                open(path, 'wb').write(raw)
        return Parser.save(self)
    
    def populate_toc(self, toc):
        '''
        Populate the Table of Contents from detected chapters and links.
        '''
        
        def add_item(href, fragment, text, target, type='link'):
            for entry in toc.flat():
                if entry.href == href and entry.fragment == fragment:
                    return entry
            if len(text) > 50:
                text = text[:50] + u'\u2026'
            return target.add_item(href, fragment, text, type=type)
        
        name = self.htmlfile_map[self.htmlfile.path]
        href = 'content/'+name
        
        # Add level 1 and level 2 TOC items
        counter = 0
        
        def elem_to_link(elem, href, counter):
            text = (u''.join(elem.xpath('string()'))).strip()
            if not text:
                return None, None, None
            t = elem.xpath('descendant-or-self::a[@href]')
            if t:
                _href = 'content/' + t[0].get('href', '')
                parts = _href.split('#')
                _href = parts[0]
                frag = None if len(parts) == 1 else parts[-1]
            else:
                _href = href
                id = elem.get('id', 'calibre_chapter_%d'%counter)
                elem.set('id', id)
                frag = id
            return text, _href, frag
                
        
        if self.opts.level1_toc is not None:
            level1 = self.opts.level1_toc(self.root)
            if level1:
                added = {}
                for elem in level1:
                    text, _href, frag = elem_to_link(elem, href, counter)
                    counter += 1
                    if text:
                        added[elem] = add_item(_href, frag, text, toc, type='chapter')
                        add_item(_href, frag, 'Top', added[elem], type='chapter')
                if self.opts.level2_toc is not None:
                    level2 = list(self.opts.level2_toc(self.root))
                    for elem in level2:
                        level1 = None
                        for item in self.root.iterdescendants():
                            if item in added.keys():
                                level1 = added[item]
                            elif item == elem and level1 is not None:
                                text, _href, frag = elem_to_link(elem, href, counter)
                                counter += 1
                                if text:
                                    add_item(_href, frag, text, level1, type='chapter')
                    
            if len(toc) > 0:
                return
        # Add chapters to TOC
        if not self.opts.no_chapters_in_toc:
            for elem in getattr(self, 'detected_chapters', []):
                text = (u''.join(elem.xpath('string()'))).strip()
                if text:
                    counter += 1
                    id = elem.get('id', 'calibre_chapter_%d'%counter)
                    elem.set('id', id)
                    add_item(href, id, text, toc, type='chapter')
        
        if len(list(toc.flat())) >= self.opts.toc_threshold:
            return
        referrer = toc
        if self.htmlfile.referrer is not None:
            try:
                name = self.htmlfile_map[self.htmlfile.referrer.path]
                href = 'content/'+name
                for i in toc.flat():
                    if href == i.href and i.fragment is None:
                        referrer = i
                        break
            except KeyError:
                pass
            if referrer is toc:
                text = self.htmlfile.title
                name = self.htmlfile_map[self.htmlfile.referrer.path]
                href = 'content/'+name
                referrer = add_item(href, None, text, toc)
            
        # Add links to TOC
        if int(self.opts.max_toc_links) > 0:
            for link in list(self.LINKS_PATH(self.root))[:self.opts.max_toc_links]:
                text = (u''.join(link.xpath('string()'))).strip()
                if text:
                    href = link.get('href', '')
                    if href and not (href.startswith('http://') or href.startswith('https://')):
                        href = href.strip()
                        if href.startswith('#'):
                            href = self.htmlfile_map[self.htmlfile.path] + href
                        href = 'content/'+href
                        parts = href.split('#')
                        href, fragment = parts[0], None
                        if len(parts) > 1:
                            fragment = parts[1]
                        add_item(href, fragment, text, referrer)
                    
    @classmethod
    def preprocess_css(cls, css, dpi=96):
        def rescale(match):
            val = match.group(1)
            try:
                val = float(val)
            except ValueError:
                return ''
            return '%fpt'%(72 * val/dpi)
        
        css = cls.PIXEL_PAT.sub(rescale, css)
        css = cls.PAGE_PAT.sub('', css)
        return css
        
    def extract_css(self, parsed_sheets):
        '''
        Remove all CSS information from the document and store it as 
        :class:`StyleSheet` objects.
        '''
        
        def get_id(chapter, counter, prefix='calibre_css_'):
            new_id = '%s_%d'%(prefix, counter)
            if chapter.tag.lower() == 'a' and  'name' in chapter.keys():
                chapter.attrib['id'] = id = chapter.get('name')
                if not id:
                    chapter.attrib['id'] = chapter.attrib['name'] = new_id
                return new_id
            if 'id' in chapter.keys():
                id = chapter.get('id')
            else:
                id = new_id
                chapter.set('id', id)
            return id
    
        self.external_stylesheets, self.stylesheet = [], self.css_parser.parseString('')
        self.specified_override_css = []
        for link in self.root.xpath('//link'):
            if 'css' in link.get('type', 'text/css').lower():
                file = os.path.join(self.tdir, *(link.get('href', '').split('/')))
                if file and not 'http:' in file:
                    if not parsed_sheets.has_key(file):
                        try:
                            self.log_info('Processing stylesheet %s...'%file)
                            css = self.preprocess_css(open(file).read())
                        except (IOError, OSError):
                            self.log_error('Failed to open stylesheet: %s'%file)
                        else:
                            try:
                                try:
                                    parsed_sheets[file] = self.css_parser.parseString(css)
                                except ValueError:
                                    parsed_sheets[file] = \
                                        self.css_parser.parseString(\
                                                css.decode('utf8', 'replace'))
                            except:
                                parsed_sheets[file] = css.decode('utf8', 'replace')
                                self.log_warning('Failed to parse stylesheet: %s'%file)
                                if self.opts.verbose > 1:
                                    self.log_exception('')
                    if parsed_sheets.has_key(file):
                        self.external_stylesheets.append(parsed_sheets[file])
                
        
        for style in self.root.xpath('//style'):
            if 'css' in style.get('type', 'text/css').lower():
                override_css = style.get('title', '') == 'override_css'
                raw = '\n'.join(style.xpath('./text()'))
                css = self.preprocess_css(raw)
                try:
                    sheet = self.css_parser.parseString(css)
                except:
                    self.log_debug('Failed to parse style element')
                else:
                    for rule in sheet:
                        if override_css:
                            self.specified_override_css.append(rule)
                        else:
                            self.stylesheet.add(rule)
                style.getparent().remove(style)
        cache = {}
        class_counter = 0
        for font in self.root.xpath('//font'):
            try:
                size = font.attrib.pop('size', '3')
            except:
                size = '3'
            if size and size.strip() and size.strip()[0] in ('+', '-'):
                size = 3 + float(size) # Hack assumes basefont=3
            try:
                setting = 'font-size: %d%%;'%int((float(size)/3) * 100)
            except ValueError:
                setting = ''
            face = font.attrib.pop('face', None)
            if face is not None:
                faces = []
                for face in face.split(','):
                    if ' ' in face:
                        face = "%s" % face
                    faces.append(face)
                for generic in ('serif', 'sans-serif', 'monospace'):
                    if generic in faces:
                        break
                else:
                    faces.append('serif')
                family = ', '.join(faces)
                setting += 'font-family: %s;' % family
            color = font.attrib.pop('color', None)
            if color is not None:
                setting += 'color:%s'%color
            classname = cache.get(setting, None)
            if classname is None:
                classname = 'calibre_class_%d'%class_counter
                class_counter += 1
                cache[setting] = classname
            cn = font.get('class', '')
            if cn: cn += ' '
            cn += classname
            font.set('class', cn)
            font.tag = 'span'
            
        for elem in self.root.xpath('//*[@style]'):
            setting = elem.get('style')
            classname = cache.get(setting, None)
            if classname is None:
                classname = 'calibre_class_%d'%class_counter
                class_counter += 1
                cache[setting] = classname
            cn = elem.get('class', '')
            if cn: cn += ' '
            cn += classname
            elem.set('class', cn)
            elem.attrib.pop('style')
        
        css = '\n'.join(['.%s {%s;}'%(cn, setting) for \
                         setting, cn in cache.items()])
        sheet = self.css_parser.parseString(self.preprocess_css(css.replace(';;}', ';}')))
        for rule in sheet:
            self.stylesheet.add(rule)
        css = ''
        css += '\n\n' + 'body {margin-top: 0pt; margin-bottom: 0pt; margin-left: 0pt; margin-right: 0pt;}'
        css += '\n\n@page {margin-top: %fpt; margin-bottom: %fpt; }'%(self.opts.margin_top, self.opts.margin_bottom)
        css += '\n\nbody {margin-left: %fpt; margin-right: %fpt}'%(self.opts.margin_left, self.opts.margin_right)
        # Workaround for anchor rendering bug in ADE
        css += '\n\na { color: inherit; text-decoration: inherit; cursor: default; }\na[href] { color: blue; text-decoration: underline; cursor:pointer; }'
        if self.opts.remove_paragraph_spacing:
            css += '\n\np {text-indent: 2em; margin-top:0pt; margin-bottom:0pt; padding:0pt; border:0pt;}'
        if self.opts.override_css:
            css += '\n\n' + self.opts.override_css
        self.override_css = self.css_parser.parseString(self.preprocess_css(css))
        for rule in reversed(self.specified_override_css):
            self.override_css.insertRule(rule, index=0)
        
        
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
    metadata('authors', ['-a', '--authors'], default=None,
             help=_('The author(s) of the ebook, as a comma separated list.'))
    metadata('tags', ['--subjects'], default=None,
             help=_('The subject(s) of this book, as a comma separated list.'))
    metadata('publisher', ['--publisher'], default=None,
             help=_('Set the publisher of this book.'))
    metadata('comments', ['--comment'], default=None,
             help=_('A summary of this book.'))
    metadata('from_opf', ['--metadata-from'], default=None,
              help=_('Load metadata from the specified OPF file'))
        
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
Also collects any resources like images, stylesheets, scripts, etc. 
If an OPF file is specified instead, the list of files in its <spine> element
is used.
'''))

def search_for_opf(dir):
    for f in os.listdir(dir):
        if f.lower().endswith('.opf'):
            return OPF(open(os.path.join(dir, f), 'rb'), dir)


def get_filelist(htmlfile, opts):
    '''
    Build list of files referenced by html file or try to detect and use an
    OPF file instead.
    '''
    print 'Building file list...'
    dir = os.path.dirname(htmlfile)
    if not dir:
        dir = os.getcwd()
    opf = search_for_opf(dir)
    filelist = None
    if opf is not None:
        try:
            filelist = opf_traverse(opf, verbose=opts.verbose, encoding=opts.encoding)
        except:
            pass
    if not filelist:
        filelist = traverse(htmlfile, max_levels=int(opts.max_levels),
                            verbose=opts.verbose, encoding=opts.encoding)\
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
    elif htmlfile:
        try:
            mi =  get_metadata(open(htmlfile, 'rb'), 'html')
        except:
            mi = MetaInformation(None, None)
    
    if opts.from_opf is not None and os.access(opts.from_opf, os.R_OK):
        mi.smart_update(OPF(open(opts.from_opf, 'rb'), os.path.abspath(os.path.dirname(opts.from_opf))))
    for attr in ('title', 'authors', 'publisher', 'tags', 'comments'):
        val = getattr(opts, attr, None)
        if val is None or val == _('Unknown') or val == [_('Unknown')]:
            continue
        if attr in ('authors', 'tags'):
            val = [i.strip() for i in val.split(',') if i.strip()]
        setattr(mi, attr, val)
        
    cover = getattr(opts, 'cover', False)
    if cover and os.path.exists(cover):
        mi.cover = os.path.abspath(cover)
        
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
    mi.guide = None
    entries = [('content/'+f, 'application/xhtml+xml') for f in filelist] + [(f, None) for f in resources]
    for f in filelist:
        if os.path.exists(os.path.join(basepath, 'content', 'resources', f+'.css')):
            entries.append(('content/resources/'+f+'.css', 'text/css'))
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
        opf = OPF(open(htmlfile, 'rb'), os.path.dirname(os.path.abspath(htmlfile)))
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

def gui_main(htmlfile, pt=None):
    '''
    Convenience wrapper for use in recursively importing HTML files.
    '''
    if pt is None:
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
