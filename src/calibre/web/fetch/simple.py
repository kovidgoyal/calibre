#!/usr/bin/env python
from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch a webpage and its links recursively. The webpages are saved to disk in
UTF-8 encoding with any charset declarations removed.
'''
import sys, socket, os, urlparse, codecs, logging, re, time, copy, urllib2, threading, traceback
from urllib import url2pathname
from httplib import responses

from calibre import setup_cli_handlers, browser, sanitize_file_name, \
                    OptionParser, relpath, LoggingInterface
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag
from calibre.ebooks.chardet import xml_to_unicode

class FetchError(Exception):
    pass

def basename(url):
    parts = urlparse.urlsplit(url)
    path = url2pathname(parts.path)
    res = os.path.basename(path)
    if not os.path.splitext(res)[1]:
        return 'index.html'
    return res

def save_soup(soup, target):
    ns = BeautifulSoup('<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />')
    nm = ns.find('meta')
    metas = soup.findAll('meta', content=True)
    for meta in metas:
        if 'charset' in meta['content']:
            meta.replaceWith(nm)
    
    selfdir = os.path.dirname(target)
    
    for tag in soup.findAll(['img', 'link', 'a']):
        for key in ('src', 'href'):
            path = tag.get(key, None)
            if path and os.path.isfile(path) and os.path.exists(path) and os.path.isabs(path):
                tag[key] = relpath(path, selfdir).replace(os.sep, '/')
    
    f = codecs.open(target, 'w', 'utf-8')
    f.write(unicode(soup))
    f.close()


class RecursiveFetcher(object, LoggingInterface):
    LINK_FILTER = tuple(re.compile(i, re.IGNORECASE) for i in 
                ('.exe\s*$', '.mp3\s*$', '.ogg\s*$', '^\s*mailto:', '^\s*$'))
    #ADBLOCK_FILTER = tuple(re.compile(i, re.IGNORECASE) for it in
    #                       (
    #                        
    #                        )
    #                       )
    CSS_IMPORT_PATTERN = re.compile(r'\@import\s+url\((.*?)\)', re.IGNORECASE)
    
    def __init__(self, options, logger, image_map={}, css_map={}, job_info=None):
        LoggingInterface.__init__(self, logger)
        self.base_dir = os.path.abspath(os.path.expanduser(options.dir))
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
        self.default_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(options.timeout)
        self.verbose = options.verbose
        self.encoding = options.encoding
        self.browser = options.browser if hasattr(options, 'browser') else browser()
        self.max_recursions = options.max_recursions
        self.match_regexps  = [re.compile(i, re.IGNORECASE) for i in options.match_regexps]
        self.filter_regexps = [re.compile(i, re.IGNORECASE) for i in options.filter_regexps]
        self.max_files = options.max_files
        self.delay = options.delay
        self.last_fetch_at = 0.
        self.filemap = {}
        self.imagemap = image_map
        self.imagemap_lock = threading.RLock()
        self.stylemap = css_map
        self.stylemap_lock = threading.RLock()
        self.downloaded_paths = []
        self.current_dir = self.base_dir
        self.files = 0
        self.preprocess_regexps  = getattr(options, 'preprocess_regexps', [])
        self.remove_tags         = getattr(options, 'remove_tags', [])
        self.remove_tags_after   = getattr(options, 'remove_tags_after', None)
        self.remove_tags_before  = getattr(options, 'remove_tags_before', None)
        self.keep_only_tags      = getattr(options, 'keep_only_tags', [])
        self.preprocess_html_ext = getattr(options, 'preprocess_html', lambda soup: soup) 
        self.postprocess_html_ext= getattr(options, 'postprocess_html', None)
        self.download_stylesheets = not options.no_stylesheets
        self.show_progress = True
        self.failed_links = []
        self.job_info = job_info
        
    def get_soup(self, src):
        nmassage = copy.copy(BeautifulSoup.MARKUP_MASSAGE)
        nmassage.extend(self.preprocess_regexps)
        soup = BeautifulSoup(xml_to_unicode(src, self.verbose)[0], markupMassage=nmassage)
         
        if self.keep_only_tags:
            body = Tag(soup, 'body')
            for spec in self.keep_only_tags:
                for tag in soup.find('body').findAll(**spec):
                    body.insert(len(body.contents), tag)
            soup.find('body').replaceWith(body)
            
        def remove_beyond(tag, next):
            while tag is not None and tag.name != 'body':
                after = getattr(tag, next)
                while after is not None:
                    ns = getattr(tag, next)
                    after.extract()
                    after = ns
                tag = tag.parent
        
        if self.remove_tags_after is not None:
            tag = soup.find(**self.remove_tags_after)
            remove_beyond(tag, 'nextSibling')
            
        if self.remove_tags_before is not None:
            tag = soup.find(**self.remove_tags_before)
            remove_beyond(tag, 'previousSibling')
            
        for kwds in self.remove_tags:
            for tag in soup.findAll(**kwds):
                tag.extract()
        return self.preprocess_html_ext(soup)
        

    def fetch_url(self, url):
        f = None
        self.log_debug('Fetching %s', url)
        delta = time.time() - self.last_fetch_at 
        if  delta < self.delay:
            time.sleep(delta)
        try:
            f = self.browser.open(url)
        except urllib2.URLError, err:
            if hasattr(err, 'code') and responses.has_key(err.code):
                raise FetchError, responses[err.code]
            if err.reason[0] == 104: # Connection reset by peer
                self.log_debug('Connection reset by peer retrying in 1 second.')
                time.sleep(1)
                f = self.browser.open(url)
            else: 
                raise err
        finally:
            self.last_fetch_at = time.time()
        return f

        
    def start_fetch(self, url):
        soup = BeautifulSoup(u'<a href="'+url+'" />')
        self.log_info('Downloading')
        res = self.process_links(soup, url, 0, into_dir='')
        self.log_info('%s saved to %s', url, res)
        return res
    
    def is_link_ok(self, url):
        for i in self.__class__.LINK_FILTER:
            if i.search(url):
                return False
        return True
        
    def is_link_wanted(self, url):
        if self.filter_regexps:
            for f in self.filter_regexps:
                if f.search(url):
                    return False            
        if self.match_regexps:
            for m in self.match_regexps:
                if m.search(url):
                    return True
            return False
        return True
        
    def process_stylesheets(self, soup, baseurl):
        diskpath = os.path.join(self.current_dir, 'stylesheets')
        if not os.path.exists(diskpath):
            os.mkdir(diskpath)
        for c, tag in enumerate(soup.findAll(lambda tag: tag.name.lower()in ['link', 'style'] and tag.has_key('type') and tag['type'].lower() == 'text/css')):
            if tag.has_key('href'):
                iurl = tag['href']
                if not urlparse.urlsplit(iurl).scheme:
                    iurl = urlparse.urljoin(baseurl, iurl, False)
                with self.stylemap_lock:
                    if self.stylemap.has_key(iurl):
                        tag['href'] = self.stylemap[iurl]
                        continue
                try:
                    f = self.fetch_url(iurl)
                except Exception, err:
                    self.log_warning('Could not fetch stylesheet %s', iurl)
                    self.log_debug('Error: %s', str(err), exc_info=True)
                    continue
                stylepath = os.path.join(diskpath, 'style'+str(c)+'.css')
                with self.stylemap_lock:
                    self.stylemap[iurl] = stylepath
                open(stylepath, 'wb').write(f.read())
                tag['href'] = stylepath
            else:
                for ns in tag.findAll(text=True):                    
                    src = str(ns)
                    m = self.__class__.CSS_IMPORT_PATTERN.search(src)
                    if m:
                        iurl = m.group(1)
                        if not urlparse.urlsplit(iurl).scheme:
                            iurl = urlparse.urljoin(baseurl, iurl, False)
                        with self.stylemap_lock:
                            if self.stylemap.has_key(iurl):
                                ns.replaceWith(src.replace(m.group(1), self.stylemap[iurl]))
                                continue
                        try:
                            f = self.fetch_url(iurl)
                        except Exception, err:
                            self.log_warning('Could not fetch stylesheet %s', iurl)
                            self.log_debug('Error: %s', str(err), exc_info=True)
                            continue
                        c += 1
                        stylepath = os.path.join(diskpath, 'style'+str(c)+'.css')
                        with self.stylemap_lock:
                            self.stylemap[iurl] = stylepath
                        open(stylepath, 'wb').write(f.read())
                        ns.replaceWith(src.replace(m.group(1), stylepath))
                        
                        
    
    def process_images(self, soup, baseurl):
        diskpath = os.path.join(self.current_dir, 'images')
        if not os.path.exists(diskpath):
            os.mkdir(diskpath)
        c = 0
        for tag in soup.findAll(lambda tag: tag.name.lower()=='img' and tag.has_key('src')):
            iurl, ext = tag['src'], os.path.splitext(tag['src'])[1]
            #if not ext:
            #    self.log_debug('Skipping extensionless image %s', iurl)
            #    continue
            if not urlparse.urlsplit(iurl).scheme:
                iurl = urlparse.urljoin(baseurl, iurl, False)
            with self.imagemap_lock:
                if self.imagemap.has_key(iurl):
                    tag['src'] = self.imagemap[iurl]
                    continue
            try:
                f = self.fetch_url(iurl)
            except Exception, err:
                self.log_warning('Could not fetch image %s', iurl)
                self.log_debug('Error: %s', str(err), exc_info=True)
                continue
            c += 1
            imgpath = os.path.join(diskpath, sanitize_file_name('img'+str(c)+ext))
            with self.imagemap_lock:
                self.imagemap[iurl] = imgpath
            open(imgpath, 'wb').write(f.read())
            tag['src'] = imgpath

    def absurl(self, baseurl, tag, key, filter=True): 
        iurl = tag[key]
        parts = urlparse.urlsplit(iurl)
        if not parts.netloc and not parts.path:
            return None
        if not parts.scheme:
            iurl = urlparse.urljoin(baseurl, iurl, False)
        if not self.is_link_ok(iurl):
            self.log_debug('Skipping invalid link: %s', iurl)
            return None
        if filter and not self.is_link_wanted(iurl):
            self.log_debug('Filtered link: '+iurl)
            return None
        return iurl
    
    def normurl(self, url):
        parts = list(urlparse.urlsplit(url))
        parts[4] = ''
        return urlparse.urlunsplit(parts)
                
    def localize_link(self, tag, key, path):
        parts = urlparse.urlsplit(tag[key])
        suffix = '#'+parts.fragment if parts.fragment else ''
        tag[key] = path+suffix
    
    def process_return_links(self, soup, baseurl):
        for tag in soup.findAll(lambda tag: tag.name.lower()=='a' and tag.has_key('href')):
            iurl = self.absurl(baseurl, tag, 'href')            
            if not iurl:
                continue
            nurl = self.normurl(iurl)
            if self.filemap.has_key(nurl):
                self.localize_link(tag, 'href', self.filemap[nurl])
    
    def process_links(self, soup, baseurl, recursion_level, into_dir='links'):
        res = ''
        diskpath = os.path.join(self.current_dir, into_dir)
        if not os.path.exists(diskpath):
            os.mkdir(diskpath)
        prev_dir = self.current_dir
        try:
            self.current_dir = diskpath
            tags = list(soup.findAll('a', href=True))
            
            for c, tag in enumerate(tags):
                if self.show_progress:
                    print '.',
                    sys.stdout.flush()
                sys.stdout.flush()
                iurl = self.absurl(baseurl, tag, 'href', filter=recursion_level != 0)
                if not iurl:
                    continue
                nurl = self.normurl(iurl)
                if self.filemap.has_key(nurl):
                    self.localize_link(tag, 'href', self.filemap[nurl])
                    continue
                if self.files > self.max_files:
                    return res
                linkdir = 'link'+str(c) if into_dir else ''
                linkdiskpath = os.path.join(diskpath, linkdir)
                if not os.path.exists(linkdiskpath):
                    os.mkdir(linkdiskpath)
                try:
                    self.current_dir = linkdiskpath
                    f = self.fetch_url(iurl)
                    dsrc = f.read()
                    if len(dsrc) == 0 or \
                       len(re.compile('<!--.*?-->', re.DOTALL).sub('', dsrc).strip()) == 0:
                        raise ValueError('No content at URL %s'%iurl)
                    if self.encoding is not None:
                        dsrc = dsrc.decode(self.encoding, 'ignore')
                    else:
                        dsrc = xml_to_unicode(dsrc, self.verbose)[0]
                    
                    soup = self.get_soup(dsrc)
                    self.log_debug('Processing images...')
                    self.process_images(soup, f.geturl())
                    if self.download_stylesheets:
                        self.process_stylesheets(soup, f.geturl())
                    
                    res = os.path.join(linkdiskpath, basename(iurl))
                    self.downloaded_paths.append(res)
                    self.filemap[nurl] = res
                    if recursion_level < self.max_recursions:
                        self.log_debug('Processing links...')
                        self.process_links(soup, iurl, recursion_level+1)
                    else:
                        self.process_return_links(soup, iurl) 
                        self.log_debug('Recursion limit reached. Skipping links in %s', iurl)
                    
                    if callable(self.postprocess_html_ext):
                        soup = self.postprocess_html_ext(soup, 
                                c==0 and recursion_level==0 and not getattr(self, 'called_first', False),
                                self.job_info)
                        if c==0 and recursion_level == 0:
                            self.called_first = True
                    
                    save_soup(soup, res)
                    self.localize_link(tag, 'href', res)
                except Exception, err:
                    self.failed_links.append((iurl, traceback.format_exc()))
                    self.log_warning('Could not fetch link %s', iurl)
                    self.log_debug('Error: %s', str(err), exc_info=True)
                finally:
                    self.current_dir = diskpath
                    self.files += 1                
        finally:
            self.current_dir = prev_dir
        if self.show_progress:
            print
        return res
    
    def __del__(self):
        socket.setdefaulttimeout(self.default_timeout)
        
def option_parser(usage=_('%prog URL\n\nWhere URL is for example http://google.com')):
    parser = OptionParser(usage=usage)
    parser.add_option('-d', '--base-dir', 
                      help=_('Base directory into which URL is saved. Default is %default'),
                      default='.', type='string', dest='dir')
    parser.add_option('-t', '--timeout', 
                      help=_('Timeout in seconds to wait for a response from the server. Default: %default s'),
                      default=10.0, type='float', dest='timeout')
    parser.add_option('-r', '--max-recursions', default=1, 
                      help=_('Maximum number of levels to recurse i.e. depth of links to follow. Default %default'),
                      type='int', dest='max_recursions')
    parser.add_option('-n', '--max-files', default=sys.maxint, type='int', dest='max_files',
                      help=_('The maximum number of files to download. This only applies to files from <a href> tags. Default is %default'))
    parser.add_option('--delay', default=0, dest='delay', type='int',
                      help=_('Minimum interval in seconds between consecutive fetches. Default is %default s'))
    parser.add_option('--encoding', default=None, 
                      help=_('The character encoding for the websites you are trying to download. The default is to try and guess the encoding.'))
    parser.add_option('--match-regexp', default=[], action='append', dest='match_regexps',
                      help=_('Only links that match this regular expression will be followed. This option can be specified multiple times, in which case as long as a link matches any one regexp, it will be followed. By default all links are followed.'))
    parser.add_option('--filter-regexp', default=[], action='append', dest='filter_regexps',
                      help=_('Any link that matches this regular expression will be ignored. This option can be specified multiple times, in which case as long as any regexp matches a link, it will be ignored.By default, no links are ignored. If both --filter-regexp and --match-regexp are specified, then --filter-regexp is applied first.'))
    parser.add_option('--dont-download-stylesheets', action='store_true', default=False,
                      help=_('Do not download CSS stylesheets.'), dest='no_stylesheets')
    parser.add_option('--verbose', help=_('Show detailed output information. Useful for debugging'),
                      default=False, action='store_true', dest='verbose')
    return parser


def create_fetcher(options, logger=None, image_map={}):
    if logger is None:
        level = logging.DEBUG if options.verbose else logging.INFO
        logger = logging.getLogger('web2disk')
        setup_cli_handlers(logger, level)
    return RecursiveFetcher(options, logger, image_map={})

def main(args=sys.argv):
    parser = option_parser()    
    options, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        return 1
    
    fetcher = create_fetcher(options) 
    fetcher.start_fetch(args[1])
    

if __name__ == '__main__':    
    sys.exit(main())
