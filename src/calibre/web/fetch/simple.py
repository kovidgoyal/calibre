#!/usr/bin/env python
from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch a webpage and its links recursively. The webpages are saved to disk in
UTF-8 encoding with any charset declarations removed.
'''
import sys, socket, os, urlparse, re, time, copy, urllib2, threading, traceback
from urllib import url2pathname, quote
from httplib import responses
from base64 import b64decode

from calibre import browser, relpath, unicode_path, fit_image
from calibre.constants import filesystem_encoding, iswindows
from calibre.utils.filenames import ascii_filename
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag
from calibre.ebooks.chardet import xml_to_unicode
from calibre.utils.config import OptionParser
from calibre.utils.logging import Log
from calibre.utils.magick import Image
from calibre.utils.magick.draw import identify_data, thumbnail
from calibre.utils.imghdr import what

class FetchError(Exception):
    pass

class closing(object):
    'Context to automatically close something at the end of a block.'

    def __init__(self, thing):
        self.thing = thing

    def __enter__(self):
        return self.thing

    def __exit__(self, *exc_info):
        try:
            self.thing.close()
        except Exception:
            pass


bad_url_counter = 0
def basename(url):
    try:
        parts = urlparse.urlsplit(url)
        path = url2pathname(parts.path)
        res = os.path.basename(path)
    except:
        global bad_url_counter
        bad_url_counter += 1
        return 'bad_url_%d.html'%bad_url_counter
    if not os.path.splitext(res)[1]:
        return 'index.html'
    return res

def save_soup(soup, target):
    ns = BeautifulSoup('<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />')
    nm = ns.find('meta')
    metas = soup.findAll('meta', content=True)
    added = False
    for meta in metas:
        if 'charset' in meta.get('content', '').lower():
            meta.replaceWith(nm)
            added = True
    if not added:
        head = soup.find('head')
        if head is not None:
            head.insert(0, nm)

    selfdir = os.path.dirname(target)

    for tag in soup.findAll(['img', 'link', 'a']):
        for key in ('src', 'href'):
            path = tag.get(key, None)
            if path and os.path.isfile(path) and os.path.exists(path) and os.path.isabs(path):
                tag[key] = unicode_path(relpath(path, selfdir).replace(os.sep, '/'))

    html = unicode(soup)
    with open(target, 'wb') as f:
        f.write(html.encode('utf-8'))

class response(str):

    def __new__(cls, *args):
        obj = super(response, cls).__new__(cls, *args)
        obj.newurl = None
        return obj

def default_is_link_wanted(url, tag):
    raise NotImplementedError()

class RecursiveFetcher(object):
    LINK_FILTER = tuple(re.compile(i, re.IGNORECASE) for i in
                ('.exe\s*$', '.mp3\s*$', '.ogg\s*$', '^\s*mailto:', '^\s*$'))
    #ADBLOCK_FILTER = tuple(re.compile(i, re.IGNORECASE) for it in
    #                       (
    #
    #                        )
    #                       )
    CSS_IMPORT_PATTERN = re.compile(r'\@import\s+url\((.*?)\)', re.IGNORECASE)
    default_timeout = socket.getdefaulttimeout() # Needed here as it is used in __del__

    def __init__(self, options, log, image_map={}, css_map={}, job_info=None):
        bd = options.dir
        if not isinstance(bd, unicode):
            bd = bd.decode(filesystem_encoding)

        self.base_dir = os.path.abspath(os.path.expanduser(bd))
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
        self.log = log
        self.verbose = options.verbose
        self.timeout = options.timeout
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
        self.image_url_processor = None
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
        self.preprocess_raw_html = getattr(options, 'preprocess_raw_html',
                lambda raw, url: raw)
        self.prepreprocess_html_ext = getattr(options, 'skip_ad_pages', lambda soup: None)
        self.postprocess_html_ext= getattr(options, 'postprocess_html', None)
        self._is_link_wanted     = getattr(options, 'is_link_wanted',
                default_is_link_wanted)
        self.compress_news_images_max_size = getattr(options, 'compress_news_images_max_size', None)
        self.compress_news_images = getattr(options, 'compress_news_images', False)
        self.compress_news_images_auto_size = getattr(options, 'compress_news_images_auto_size', 16)
        self.scale_news_images = getattr(options, 'scale_news_images', None)
        self.download_stylesheets = not options.no_stylesheets
        self.show_progress = True
        self.failed_links = []
        self.job_info = job_info

    def get_soup(self, src, url=None):
        nmassage = copy.copy(BeautifulSoup.MARKUP_MASSAGE)
        nmassage.extend(self.preprocess_regexps)
        nmassage += [(re.compile(r'<!DOCTYPE .+?>', re.DOTALL), lambda m: '')] # Some websites have buggy doctype declarations that mess up beautifulsoup
        # Remove comments as they can leave detritus when extracting tags leaves
        # multiple nested comments
        nmassage.append((re.compile(r'<!--.*?-->', re.DOTALL), lambda m: ''))
        usrc = xml_to_unicode(src, self.verbose, strip_encoding_pats=True)[0]
        usrc = self.preprocess_raw_html(usrc, url)
        soup = BeautifulSoup(usrc, markupMassage=nmassage)

        replace = self.prepreprocess_html_ext(soup)
        if replace is not None:
            soup = BeautifulSoup(xml_to_unicode(replace, self.verbose, strip_encoding_pats=True)[0], markupMassage=nmassage)

        if self.keep_only_tags:
            body = Tag(soup, 'body')
            try:
                if isinstance(self.keep_only_tags, dict):
                    self.keep_only_tags = [self.keep_only_tags]
                for spec in self.keep_only_tags:
                    for tag in soup.find('body').findAll(**spec):
                        body.insert(len(body.contents), tag)
                soup.find('body').replaceWith(body)
            except AttributeError: # soup has no body element
                pass

        def remove_beyond(tag, next):
            while tag is not None and getattr(tag, 'name', None) != 'body':
                after = getattr(tag, next)
                while after is not None:
                    ns = getattr(tag, next)
                    after.extract()
                    after = ns
                tag = tag.parent

        if self.remove_tags_after is not None:
            rt = [self.remove_tags_after] if isinstance(self.remove_tags_after, dict) else self.remove_tags_after
            for spec in rt:
                tag = soup.find(**spec)
                remove_beyond(tag, 'nextSibling')

        if self.remove_tags_before is not None:
            tag = soup.find(**self.remove_tags_before)
            remove_beyond(tag, 'previousSibling')

        for kwds in self.remove_tags:
            for tag in soup.findAll(**kwds):
                tag.extract()
        return self.preprocess_html_ext(soup)


    def fetch_url(self, url):
        data = None
        self.log.debug('Fetching', url)

        # Check for a URL pointing to the local filesystem and special case it
        # for efficiency and robustness. Bypasses delay checking as it does not
        # apply to local fetches. Ensures that unicode paths that are not
        # representable in the filesystem_encoding work.
        is_local = 0
        if url.startswith('file://'):
            is_local = 7
        elif url.startswith('file:'):
            is_local = 5
        if is_local > 0:
            url = url[is_local:]
            if iswindows and url.startswith('/'):
                url = url[1:]
            with open(url, 'rb') as f:
                data = response(f.read())
                data.newurl = 'file:'+url # This is what mechanize does for
                                          # local URLs
            return data

        delta = time.time() - self.last_fetch_at
        if delta < self.delay:
            time.sleep(self.delay - delta)
        if isinstance(url, unicode):
            url = url.encode('utf-8')
        # Not sure is this is really needed as I think mechanize
        # handles quoting automatically, but leaving it
        # in case it breaks something
        if re.search(r'\s+', url) is not None:
            purl = list(urlparse.urlparse(url))
            for i in range(2, 6):
                purl[i] = quote(purl[i])
            url = urlparse.urlunparse(purl)
        open_func = getattr(self.browser, 'open_novisit', self.browser.open)
        try:
            with closing(open_func(url, timeout=self.timeout)) as f:
                data = response(f.read()+f.read())
                data.newurl = f.geturl()
        except urllib2.URLError as err:
            if hasattr(err, 'code') and responses.has_key(err.code):
                raise FetchError, responses[err.code]
            if getattr(err, 'reason', [0])[0] == 104 or \
                getattr(getattr(err, 'args', [None])[0], 'errno', None) in (-2,
                        -3): # Connection reset by peer or Name or service not known
                self.log.debug('Temporary error, retrying in 1 second')
                time.sleep(1)
                with closing(open_func(url, timeout=self.timeout)) as f:
                    data = response(f.read()+f.read())
                    data.newurl = f.geturl()
            else:
                raise err
        finally:
            self.last_fetch_at = time.time()
        return data


    def start_fetch(self, url):
        soup = BeautifulSoup(u'<a href="'+url+'" />')
        self.log.debug('Downloading')
        res = self.process_links(soup, url, 0, into_dir='')
        self.log.debug(url, 'saved to', res)
        return res

    def is_link_ok(self, url):
        for i in self.__class__.LINK_FILTER:
            if i.search(url):
                return False
        return True

    def is_link_wanted(self, url, tag):
        try:
            return self._is_link_wanted(url, tag)
        except NotImplementedError:
            pass
        except:
            return False
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
        diskpath = unicode_path(os.path.join(self.current_dir, 'stylesheets'))
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
                    data = self.fetch_url(iurl)
                except Exception:
                    self.log.exception('Could not fetch stylesheet ', iurl)
                    continue
                stylepath = os.path.join(diskpath, 'style'+str(c)+'.css')
                with self.stylemap_lock:
                    self.stylemap[iurl] = stylepath
                with open(stylepath, 'wb') as x:
                    x.write(data)
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
                            data = self.fetch_url(iurl)
                        except Exception:
                            self.log.exception('Could not fetch stylesheet ', iurl)
                            continue
                        c += 1
                        stylepath = os.path.join(diskpath, 'style'+str(c)+'.css')
                        with self.stylemap_lock:
                            self.stylemap[iurl] = stylepath
                        with open(stylepath, 'wb') as x:
                            x.write(data)
                        ns.replaceWith(src.replace(m.group(1), stylepath))

    def rescale_image(self, data):
        orig_w, orig_h, ifmt = identify_data(data)
        orig_data = data # save it in case compression fails
        if self.scale_news_images is not None:
            wmax, hmax = self.scale_news_images
            scale, new_w, new_h = fit_image(orig_w, orig_h, wmax, hmax)
            if scale:
                data = thumbnail(data, new_w, new_h, compression_quality=95)[-1]
                orig_w = new_w
                orig_h = new_h
        if self.compress_news_images_max_size is None:
            if self.compress_news_images_auto_size is None: # not compressing
                return data
            else:
                maxsizeb = (orig_w * orig_h)/self.compress_news_images_auto_size
        else:
            maxsizeb = self.compress_news_images_max_size * 1024
        scaled_data = data # save it in case compression fails
        if len(scaled_data) <= maxsizeb: # no compression required
            return scaled_data

        img = Image()
        quality = 95
        img.load(data)
        while len(data) >= maxsizeb and quality >= 5:
            quality -= 5
            img.set_compression_quality(quality)
            data = img.export('jpg')

        if len(data) >= len(scaled_data): # compression failed
            return orig_data if len(orig_data) <= len(scaled_data) else scaled_data

        if len(data) >= len(orig_data): # no improvement
            return orig_data

        return data

    def process_images(self, soup, baseurl):
        diskpath = unicode_path(os.path.join(self.current_dir, 'images'))
        if not os.path.exists(diskpath):
            os.mkdir(diskpath)
        c = 0
        for tag in soup.findAll(lambda tag: tag.name.lower()=='img' and tag.has_key('src')):
            iurl = tag['src']
            if iurl.startswith('data:image/'):
                try:
                    data = b64decode(iurl.partition(',')[-1])
                except:
                    self.log.exception('Failed to decode embedded image')
                    continue
            else:
                if callable(self.image_url_processor):
                    iurl = self.image_url_processor(baseurl, iurl)
                if not urlparse.urlsplit(iurl).scheme:
                    iurl = urlparse.urljoin(baseurl, iurl, False)
                with self.imagemap_lock:
                    if self.imagemap.has_key(iurl):
                        tag['src'] = self.imagemap[iurl]
                        continue
                try:
                    data = self.fetch_url(iurl)
                    if data == 'GIF89a\x01':
                        # Skip empty GIF files as PIL errors on them anyway
                        continue
                except Exception:
                    self.log.exception('Could not fetch image ', iurl)
                    continue
            c += 1
            fname = ascii_filename('img'+str(c))
            if isinstance(fname, unicode):
                fname = fname.encode('ascii', 'replace')
            itype = what(None, data)
            if itype is None and b'<svg' in data[:1024]:
                # SVG image
                imgpath = os.path.join(diskpath, fname+'.svg')
                with self.imagemap_lock:
                    self.imagemap[iurl] = imgpath
                with open(imgpath, 'wb') as x:
                    x.write(data)
                tag['src'] = imgpath
            else:
                try:
                    if itype not in {'png', 'jpg', 'jpeg'}:
                        itype = 'png' if itype == 'gif' else 'jpg'
                        im = Image()
                        im.load(data)
                        data = im.export(itype)
                    if self.compress_news_images and itype in {'jpg','jpeg'}:
                        try:
                            data = self.rescale_image(data)
                        except:
                            self.log.exception('failed to compress image '+iurl)
                            identify_data(data)
                    else:
                        identify_data(data)
                    # Moon+ apparently cannot handle .jpeg files
                    if itype == 'jpeg':
                        itype = 'jpg'
                    imgpath = os.path.join(diskpath, fname+'.'+itype)
                    with self.imagemap_lock:
                        self.imagemap[iurl] = imgpath
                    with open(imgpath, 'wb') as x:
                        x.write(data)
                    tag['src'] = imgpath
                except:
                    traceback.print_exc()
                    continue

    def absurl(self, baseurl, tag, key, filter=True):
        iurl = tag[key]
        parts = urlparse.urlsplit(iurl)
        if not parts.netloc and not parts.path and not parts.query:
            return None
        if not parts.scheme:
            iurl = urlparse.urljoin(baseurl, iurl, False)
        if not self.is_link_ok(iurl):
            self.log.debug('Skipping invalid link:', iurl)
            return None
        if filter and not self.is_link_wanted(iurl, tag):
            self.log.debug('Filtered link: '+iurl)
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
                    dsrc = self.fetch_url(iurl)
                    newbaseurl = dsrc.newurl
                    if len(dsrc) == 0 or \
                       len(re.compile('<!--.*?-->', re.DOTALL).sub('', dsrc).strip()) == 0:
                        raise ValueError('No content at URL %r'%iurl)
                    if callable(self.encoding):
                        dsrc = self.encoding(dsrc)
                    elif self.encoding is not None:
                        dsrc = dsrc.decode(self.encoding, 'replace')
                    else:
                        dsrc = xml_to_unicode(dsrc, self.verbose)[0]

                    soup = self.get_soup(dsrc, url=iurl)

                    base = soup.find('base', href=True)
                    if base is not None:
                        newbaseurl = base['href']
                    self.log.debug('Processing images...')
                    self.process_images(soup, newbaseurl)
                    if self.download_stylesheets:
                        self.process_stylesheets(soup, newbaseurl)

                    _fname = basename(iurl)
                    if not isinstance(_fname, unicode):
                        _fname.decode('latin1', 'replace')
                    _fname = _fname.encode('ascii', 'replace').replace('%', '').replace(os.sep, '')
                    _fname = ascii_filename(_fname)
                    _fname = os.path.splitext(_fname)[0]+'.xhtml'
                    res = os.path.join(linkdiskpath, _fname)
                    self.downloaded_paths.append(res)
                    self.filemap[nurl] = res
                    if recursion_level < self.max_recursions:
                        self.log.debug('Processing links...')
                        self.process_links(soup, newbaseurl, recursion_level+1)
                    else:
                        self.process_return_links(soup, newbaseurl)
                        self.log.debug('Recursion limit reached. Skipping links in', iurl)

                    if callable(self.postprocess_html_ext):
                        soup = self.postprocess_html_ext(soup,
                                c==0 and recursion_level==0 and not getattr(self, 'called_first', False),
                                self.job_info)

                        if c==0 and recursion_level == 0:
                            self.called_first = True

                    save_soup(soup, res)
                    self.localize_link(tag, 'href', res)
                except Exception:
                    self.failed_links.append((iurl, traceback.format_exc()))
                    self.log.exception('Could not fetch link', iurl)
                finally:
                    self.current_dir = diskpath
                    self.files += 1
        finally:
            self.current_dir = prev_dir
        if self.show_progress:
            print
        return res

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
    parser.add_option('--delay', default=0, dest='delay', type='float',
                      help=_('Minimum interval in seconds between consecutive fetches. Default is %default s'))
    parser.add_option('--encoding', default=None,
                      help=_('The character encoding for the websites you are trying to download. The default is to try and guess the encoding.'))
    parser.add_option('--match-regexp', default=[], action='append', dest='match_regexps',
                      help=_('Only links that match this regular expression will be followed. This option can be specified multiple times, in which case as long as a link matches any one regexp, it will be followed. By default all links are followed.'))
    parser.add_option('--filter-regexp', default=[], action='append', dest='filter_regexps',
                      help=_('Any link that matches this regular expression will be ignored. This option can be specified multiple times, in which case as long as any regexp matches a link, it will be ignored. By default, no links are ignored. If both filter regexp and match regexp are specified, then filter regexp is applied first.'))
    parser.add_option('--dont-download-stylesheets', action='store_true', default=False,
                      help=_('Do not download CSS stylesheets.'), dest='no_stylesheets')
    parser.add_option('--verbose', help=_('Show detailed output information. Useful for debugging'),
                      default=False, action='store_true', dest='verbose')
    return parser


def create_fetcher(options, image_map={}, log=None):
    if log is None:
        log = Log(level=Log.DEBUG) if options.verbose else Log()
    return RecursiveFetcher(options, log, image_map={})

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
