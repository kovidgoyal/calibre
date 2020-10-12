#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Fetch a webpage and its links recursively. The webpages are saved to disk in
UTF-8 encoding with any charset declarations removed.
'''


import os
import re
import socket
import sys
import threading
import time
import traceback

from calibre import browser, relpath, unicode_path
from calibre.constants import filesystem_encoding, iswindows
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.ebooks.chardet import xml_to_unicode
from calibre.utils.config import OptionParser
from calibre.utils.filenames import ascii_filename
from calibre.utils.img import image_from_data, image_to_data
from calibre.utils.imghdr import what
from calibre.utils.logging import Log
from calibre.web.fetch.utils import rescale_image
from polyglot.builtins import unicode_type
from polyglot.http_client import responses
from polyglot.urllib import (
    URLError, quote, url2pathname, urljoin, urlparse, urlsplit, urlunparse,
    urlunsplit
)
from polyglot.binary import from_base64_bytes


class AbortArticle(Exception):
    pass


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
        parts = urlsplit(url)
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
    for meta in soup.findAll('meta', content=True):
        if 'charset' in meta['content'].lower():
            meta.extract()
    for meta in soup.findAll('meta', charset=True):
        meta.extract()
    head = soup.find('head')
    if head is not None:
        nm = soup.new_tag('meta', charset='utf-8')
        head.insert(0, nm)

    selfdir = os.path.dirname(target)

    for tag in soup.findAll(['img', 'link', 'a']):
        for key in ('src', 'href'):
            path = tag.get(key, None)
            if path and os.path.isfile(path) and os.path.exists(path) and os.path.isabs(path):
                tag[key] = unicode_path(relpath(path, selfdir).replace(os.sep, '/'))

    html = unicode_type(soup)
    with open(target, 'wb') as f:
        f.write(html.encode('utf-8'))


class response(bytes):

    def __new__(cls, *args):
        obj = super(response, cls).__new__(cls, *args)
        obj.newurl = None
        return obj


def default_is_link_wanted(url, tag):
    raise NotImplementedError()


class RecursiveFetcher(object):
    LINK_FILTER = tuple(re.compile(i, re.IGNORECASE) for i in
                ('.exe\\s*$', '.mp3\\s*$', '.ogg\\s*$', '^\\s*mailto:', '^\\s*$'))
    # ADBLOCK_FILTER = tuple(re.compile(i, re.IGNORECASE) for it in
    #                       (
    #
    #                        )
    #                       )
    CSS_IMPORT_PATTERN = re.compile(r'\@import\s+url\((.*?)\)', re.IGNORECASE)
    default_timeout = socket.getdefaulttimeout()  # Needed here as it is used in __del__

    def __init__(self, options, log, image_map={}, css_map={}, job_info=None):
        bd = options.dir
        if not isinstance(bd, unicode_type):
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
        self.postprocess_html_ext = getattr(options, 'postprocess_html', None)
        self.preprocess_image_ext = getattr(options, 'preprocess_image', None)
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
        nmassage = []
        nmassage.extend(self.preprocess_regexps)
        # Remove comments as they can leave detritus when extracting tags leaves
        # multiple nested comments
        nmassage.append((re.compile(r'<!--.*?-->', re.DOTALL), lambda m: ''))
        usrc = xml_to_unicode(src, self.verbose, strip_encoding_pats=True)[0]
        usrc = self.preprocess_raw_html(usrc, url)
        for pat, repl in nmassage:
            usrc = pat.sub(repl, usrc)
        soup = BeautifulSoup(usrc)

        replace = self.prepreprocess_html_ext(soup)
        if replace is not None:
            replace = xml_to_unicode(replace, self.verbose, strip_encoding_pats=True)[0]
            for pat, repl in nmassage:
                replace = pat.sub(repl, replace)
            soup = BeautifulSoup(replace)

        if self.keep_only_tags:
            body = soup.new_tag('body')
            try:
                if isinstance(self.keep_only_tags, dict):
                    self.keep_only_tags = [self.keep_only_tags]
                for spec in self.keep_only_tags:
                    for tag in soup.find('body').findAll(**spec):
                        body.insert(len(body.contents), tag)
                soup.find('body').replaceWith(body)
            except AttributeError:  # soup has no body element
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
            rt = [self.remove_tags_before] if isinstance(self.remove_tags_before, dict) else self.remove_tags_before
            for spec in rt:
                tag = soup.find(**spec)
                remove_beyond(tag, 'previousSibling')

        for kwds in self.remove_tags:
            for tag in soup.findAll(**kwds):
                tag.extract()
        return self.preprocess_html_ext(soup)

    def fetch_url(self, url):
        data = None
        self.log.debug('Fetching', url)
        st = time.time()

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
                data.newurl = 'file:'+url  # This is what mechanize does for
                # local URLs
            self.log.debug('Fetched %s in %.1f seconds' % (url, time.time() - st))
            return data

        delta = time.time() - self.last_fetch_at
        if delta < self.delay:
            time.sleep(self.delay - delta)
        # mechanize does not handle quoting automatically
        if re.search(r'\s+', url) is not None:
            if isinstance(url, unicode_type):
                url = url.encode('utf-8')
            purl = list(urlparse(url))
            for i in range(2, 6):
                purl[i] = quote(purl[i])
            url = urlunparse(purl).decode('utf-8')
        open_func = getattr(self.browser, 'open_novisit', self.browser.open)
        try:
            with closing(open_func(url, timeout=self.timeout)) as f:
                data = response(f.read()+f.read())
                data.newurl = f.geturl()
        except URLError as err:
            if hasattr(err, 'code') and err.code in responses:
                raise FetchError(responses[err.code])
            is_temp = False
            reason = getattr(err, 'reason', None)
            if isinstance(reason, socket.gaierror):
                # see man gai_strerror() for details
                if getattr(reason, 'errno', None) in (socket.EAI_AGAIN, socket.EAI_NONAME):
                    is_temp = True
            if is_temp:  # Connection reset by peer or Name or service not known
                self.log.debug('Temporary error, retrying in 1 second')
                time.sleep(1)
                with closing(open_func(url, timeout=self.timeout)) as f:
                    data = response(f.read()+f.read())
                    data.newurl = f.geturl()
            else:
                raise err
        finally:
            self.last_fetch_at = time.time()
        self.log.debug('Fetched %s in %f seconds' % (url, time.time() - st))
        return data

    def start_fetch(self, url):
        soup = BeautifulSoup('<a href="'+url+'" />')
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
        for c, tag in enumerate(soup.findAll(name=['link', 'style'])):
            try:
                mtype = tag['type']
            except KeyError:
                mtype = 'text/css' if tag.name.lower() == 'style' else ''
            if mtype.lower() != 'text/css':
                continue
            if tag.has_attr('href'):
                iurl = tag['href']
                if not urlsplit(iurl).scheme:
                    iurl = urljoin(baseurl, iurl, False)
                with self.stylemap_lock:
                    if iurl in self.stylemap:
                        tag['href'] = self.stylemap[iurl]
                        continue
                try:
                    data = self.fetch_url(iurl)
                except Exception:
                    self.log.exception('Could not fetch stylesheet ', iurl)
                    continue
                stylepath = os.path.join(diskpath, 'style'+unicode_type(c)+'.css')
                with self.stylemap_lock:
                    self.stylemap[iurl] = stylepath
                with open(stylepath, 'wb') as x:
                    x.write(data)
                tag['href'] = stylepath
            else:
                for ns in tag.findAll(text=True):
                    src = unicode_type(ns)
                    m = self.__class__.CSS_IMPORT_PATTERN.search(src)
                    if m:
                        iurl = m.group(1)
                        if not urlsplit(iurl).scheme:
                            iurl = urljoin(baseurl, iurl, False)
                        with self.stylemap_lock:
                            if iurl in self.stylemap:
                                ns.replaceWith(src.replace(m.group(1), self.stylemap[iurl]))
                                continue
                        try:
                            data = self.fetch_url(iurl)
                        except Exception:
                            self.log.exception('Could not fetch stylesheet ', iurl)
                            continue
                        c += 1
                        stylepath = os.path.join(diskpath, 'style'+unicode_type(c)+'.css')
                        with self.stylemap_lock:
                            self.stylemap[iurl] = stylepath
                        with open(stylepath, 'wb') as x:
                            x.write(data)
                        ns.replaceWith(src.replace(m.group(1), stylepath))

    def rescale_image(self, data):
        return rescale_image(data, self.scale_news_images, self.compress_news_images_max_size, self.compress_news_images_auto_size)

    def process_images(self, soup, baseurl):
        diskpath = unicode_path(os.path.join(self.current_dir, 'images'))
        if not os.path.exists(diskpath):
            os.mkdir(diskpath)
        c = 0
        for tag in soup.findAll('img', src=True):
            iurl = tag['src']
            if iurl.startswith('data:image/'):
                try:
                    data = from_base64_bytes(iurl.partition(',')[-1])
                except Exception:
                    self.log.exception('Failed to decode embedded image')
                    continue
            else:
                if callable(self.image_url_processor):
                    iurl = self.image_url_processor(baseurl, iurl)
                if not urlsplit(iurl).scheme:
                    iurl = urljoin(baseurl, iurl, False)
                with self.imagemap_lock:
                    if iurl in self.imagemap:
                        tag['src'] = self.imagemap[iurl]
                        continue
                try:
                    data = self.fetch_url(iurl)
                    if data == b'GIF89a\x01':
                        # Skip empty GIF files as PIL errors on them anyway
                        continue
                except Exception:
                    self.log.exception('Could not fetch image ', iurl)
                    continue
            c += 1
            fname = ascii_filename('img'+unicode_type(c))
            data = self.preprocess_image_ext(data, iurl) if self.preprocess_image_ext is not None else data
            if data is None:
                continue
            itype = what(None, data)
            if itype == 'svg' or (itype is None and b'<svg' in data[:1024]):
                # SVG image
                imgpath = os.path.join(diskpath, fname+'.svg')
                with self.imagemap_lock:
                    self.imagemap[iurl] = imgpath
                with open(imgpath, 'wb') as x:
                    x.write(data)
                tag['src'] = imgpath
            else:
                try:
                    # Ensure image is valid
                    img = image_from_data(data)
                    if itype not in {'png', 'jpg', 'jpeg'}:
                        itype = 'png' if itype == 'gif' else 'jpeg'
                        data = image_to_data(img, fmt=itype)
                    if self.compress_news_images and itype in {'jpg','jpeg'}:
                        try:
                            data = self.rescale_image(data)
                        except Exception:
                            self.log.exception('failed to compress image '+iurl)
                    # Moon+ apparently cannot handle .jpeg files
                    if itype == 'jpeg':
                        itype = 'jpg'
                    imgpath = os.path.join(diskpath, fname+'.'+itype)
                    with self.imagemap_lock:
                        self.imagemap[iurl] = imgpath
                    with open(imgpath, 'wb') as x:
                        x.write(data)
                    tag['src'] = imgpath
                except Exception:
                    traceback.print_exc()
                    continue

    def absurl(self, baseurl, tag, key, filter=True):
        iurl = tag[key]
        parts = urlsplit(iurl)
        if not parts.netloc and not parts.path and not parts.query:
            return None
        if not parts.scheme:
            iurl = urljoin(baseurl, iurl, False)
        if not self.is_link_ok(iurl):
            self.log.debug('Skipping invalid link:', iurl)
            return None
        if filter and not self.is_link_wanted(iurl, tag):
            self.log.debug('Filtered link: '+iurl)
            return None
        return iurl

    def normurl(self, url):
        parts = list(urlsplit(url))
        parts[4] = ''
        return urlunsplit(parts)

    def localize_link(self, tag, key, path):
        parts = urlsplit(tag[key])
        suffix = ('#'+parts.fragment) if parts.fragment else ''
        tag[key] = path+suffix

    def process_return_links(self, soup, baseurl):
        for tag in soup.findAll('a', href=True):
            iurl = self.absurl(baseurl, tag, 'href')
            if not iurl:
                continue
            nurl = self.normurl(iurl)
            if nurl in self.filemap:
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
                    print('.', end=' ')
                    sys.stdout.flush()
                sys.stdout.flush()
                iurl = self.absurl(baseurl, tag, 'href', filter=recursion_level != 0)
                if not iurl:
                    continue
                nurl = self.normurl(iurl)
                if nurl in self.filemap:
                    self.localize_link(tag, 'href', self.filemap[nurl])
                    continue
                if self.files > self.max_files:
                    return res
                linkdir = 'link'+unicode_type(c) if into_dir else ''
                linkdiskpath = os.path.join(diskpath, linkdir)
                if not os.path.exists(linkdiskpath):
                    os.mkdir(linkdiskpath)
                try:
                    self.current_dir = linkdiskpath
                    dsrc = self.fetch_url(iurl)
                    newbaseurl = dsrc.newurl
                    if len(dsrc) == 0 or \
                       len(re.compile(b'<!--.*?-->', re.DOTALL).sub(b'', dsrc).strip()) == 0:
                        raise ValueError('No content at URL %r'%iurl)
                    if callable(self.encoding):
                        dsrc = self.encoding(dsrc)
                    elif self.encoding is not None:
                        dsrc = dsrc.decode(self.encoding, 'replace')
                    else:
                        dsrc = xml_to_unicode(dsrc, self.verbose)[0]

                    st = time.time()
                    soup = self.get_soup(dsrc, url=iurl)
                    self.log.debug('Parsed %s in %.1f seconds' % (iurl, time.time() - st))

                    base = soup.find('base', href=True)
                    if base is not None:
                        newbaseurl = base['href']
                    self.log.debug('Processing images...')
                    self.process_images(soup, newbaseurl)
                    if self.download_stylesheets:
                        self.process_stylesheets(soup, newbaseurl)

                    _fname = basename(iurl)
                    if not isinstance(_fname, unicode_type):
                        _fname.decode('latin1', 'replace')
                    _fname = _fname.replace('%', '').replace(os.sep, '')
                    _fname = ascii_filename(_fname)
                    _fname = os.path.splitext(_fname)[0][:120] + '.xhtml'
                    res = os.path.join(linkdiskpath, _fname)
                    self.downloaded_paths.append(res)
                    self.filemap[nurl] = res
                    if recursion_level < self.max_recursions:
                        self.log.debug('Processing links...')
                        self.process_links(soup, newbaseurl, recursion_level+1)
                    else:
                        self.process_return_links(soup, newbaseurl)
                        self.log.debug('Recursion limit reached. Skipping links in', iurl)

                    if newbaseurl and not newbaseurl.startswith('/'):
                        for atag in soup.findAll('a', href=lambda x: x and x.startswith('/')):
                            atag['href'] = urljoin(newbaseurl, atag['href'], True)
                    if callable(self.postprocess_html_ext):
                        soup = self.postprocess_html_ext(soup,
                                c==0 and recursion_level==0 and not getattr(self, 'called_first', False),
                                self.job_info)

                        if c==0 and recursion_level == 0:
                            self.called_first = True

                    save_soup(soup, res)
                    self.localize_link(tag, 'href', res)
                except Exception as err:
                    if isinstance(err, AbortArticle):
                        raise
                    self.failed_links.append((iurl, traceback.format_exc()))
                    self.log.exception('Could not fetch link', iurl)
                finally:
                    self.current_dir = diskpath
                    self.files += 1
        finally:
            self.current_dir = prev_dir
        if self.show_progress:
            print()
        return res


def option_parser(usage=_('%prog URL\n\nWhere URL is for example https://google.com')):
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
    parser.add_option('-n', '--max-files', default=sys.maxsize, type='int', dest='max_files',
                      help=_('The maximum number of files to download. This only applies to files from <a href> tags. Default is %default'))
    parser.add_option('--delay', default=0, dest='delay', type='float',
                      help=_('Minimum interval in seconds between consecutive fetches. Default is %default s'))
    parser.add_option('--encoding', default=None,
                      help=_('The character encoding for the websites you are trying to download. The default is to try and guess the encoding.'))
    parser.add_option('--match-regexp', default=[], action='append', dest='match_regexps',
                      help=_('Only links that match this regular expression will be followed. '
                             'This option can be specified multiple times, in which case as long '
                             'as a link matches any one regexp, it will be followed. By default all '
                             'links are followed.'))
    parser.add_option('--filter-regexp', default=[], action='append', dest='filter_regexps',
                      help=_('Any link that matches this regular expression will be ignored.'
                             ' This option can be specified multiple times, in which case as'
                             ' long as any regexp matches a link, it will be ignored. By'
                             ' default, no links are ignored. If both filter regexp and match'
                             ' regexp are specified, then filter regexp is applied first.'))
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
