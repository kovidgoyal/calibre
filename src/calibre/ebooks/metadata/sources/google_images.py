#!/usr/bin/env python
# vim:fileencoding=UTF-8
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid@kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from collections import OrderedDict

from calibre import random_user_agent
from calibre.ebooks.metadata.sources.base import Option, Source

try:
    from calibre.utils.localization import _
except ImportError:
    pass


def parse_html(raw):
    try:
        from html5_parser import parse
    except ImportError:
        # Old versions of calibre
        import html5lib

        return html5lib.parse(raw, treebuilder='lxml', namespaceHTMLElements=False)
    else:
        return parse(raw)


def imgurl_from_id(raw, tbnid):
    from json import JSONDecoder

    q = '"{}",['.format(tbnid)
    start_pos = raw.index(q)
    if start_pos < 100:
        return
    jd = JSONDecoder()
    data = jd.raw_decode('[' + raw[start_pos:])[0]
    # from pprint import pprint
    # pprint(data)
    url_num = 0
    for x in data:
        if isinstance(x, list) and len(x) == 3:
            q = x[0]
            if hasattr(q, 'lower') and q.lower().startswith('http'):
                url_num += 1
                if url_num > 1:
                    return q


# Images from posts on social media, which are rarely covers and often cannot
# be downloaded without logging in
SOCIAL_MEDIA_DOMAINS = ('instagram.com', 'cdninstagram.com', 'facebook.com', 'fbsbx.com', 'fbcdn.net')


def is_social_media(url):
    try:
        from urllib.parse import urlparse
    except ImportError:
        from urlparse import urlparse  # type: ignore
    host = (urlparse(url).hostname or '').lower()
    return any(host == d or host.endswith('.' + d) for d in SOCIAL_MEDIA_DOMAINS)


def parse_google_markup(raw):
    root = parse_html(raw)
    # newer markup pages use data-docid not data-tbnid
    results = root.xpath('//div/@data-tbnid') or root.xpath('//div/@data-docid')
    ans = OrderedDict()
    for tbnid in results:
        try:
            imgurl = imgurl_from_id(raw, tbnid)
        except Exception:
            continue
        if imgurl and not is_social_media(imgurl):
            ans[imgurl] = True
    return list(ans)


class GoogleImages(Source):
    name = 'Google Images'
    version = (1, 1, 0)
    minimum_calibre_version = (9, 17, 0)
    description = _('Downloads covers from a Google Image search. Useful to find larger/alternate covers.')
    capabilities = frozenset(['cover'])
    can_get_multiple_covers = True
    supports_gzip_transfer_encoding = True
    uses_camoufox_worker = True
    options = (
        Option(
            'max_covers',
            'number',
            5,
            _('Maximum number of covers to get'),
            _('The maximum number of covers to process from the Google search result'),
        ),
        Option(
            'size',
            'choices',
            'svga',
            _('Cover size'),
            _('Search for covers larger than the specified size'),
            choices=OrderedDict((
                (
                    'any',
                    _('Any size'),
                ),
                (
                    'l',
                    _('Large'),
                ),
                (
                    'qsvga',
                    _('Larger than %s') % '400x300',
                ),
                (
                    'vga',
                    _('Larger than %s') % '640x480',
                ),
                (
                    'svga',
                    _('Larger than %s') % '600x800',
                ),
                (
                    'xga',
                    _('Larger than %s') % '1024x768',
                ),
                (
                    '2mp',
                    _('Larger than %s') % '2 MP',
                ),
                (
                    '4mp',
                    _('Larger than %s') % '4 MP',
                ),
            )),
        ),
    )

    def download_cover(self, log, result_queue, abort, title=None, authors=None, identifiers=None, timeout=30, get_best_cover=False):
        if identifiers is None:
            identifiers = {}
        if not title:
            return
        timeout = max(60, timeout)  # Needs at least a minute
        title = ' '.join(self.get_title_tokens(title))
        author = ' '.join(self.get_author_tokens(authors))
        urls = self.get_image_urls(title, author, log, abort, timeout)
        self.download_multiple_covers(title, authors, urls, get_best_cover, timeout, result_queue, abort, log)

    @property
    def user_agent(self):
        return random_user_agent(allow_ie=False)

    def get_image_urls(self, title, author, log, abort, timeout):
        from calibre.utils.cleantext import clean_ascii_chars
        from calibre.web.automate.metadata import BrowserFailed

        url = self.search_url(title, author)
        log('Search URL: ' + url)
        try:
            raw = self.search_in_browser(url, log, timeout)
        except BrowserFailed as e:
            # Google blocks anything that is not a browser, but try anyway
            log.warn('Failed to use a browser to search Google, trying without one:', e)
            raw = self.search_without_browser(url)
        if raw is None or abort.is_set():
            return []
        raw = clean_ascii_chars(raw)
        # with open('/t/raw.html', 'w') as f:
        #     f.write(raw)
        return parse_google_markup(raw)

    def search_url(self, title, author):
        try:
            from urllib.parse import urlencode
        except ImportError:
            from urllib import urlencode  # type: ignore
        q = urlencode({'as_q': ('%s %s' % (title, author)).encode('utf-8')})
        if isinstance(q, bytes):
            q = q.decode('utf-8')
        sz = self.prefs['size']
        sz = '' if sz == 'any' else '&imgsz=' + sz
        # See https://www.google.com/advanced_image_search to understand this
        # URL scheme. imgar=t|xt is for tall and extra tall images.
        return 'https://www.google.com/search?as_st=y&udm=2&{}&as_epq=&as_oq=&as_eq=&cr=&as_sitesearch=&safe=images{}&imgar=t%7Cxt'.format(q, sz)

    def search_in_browser(self, url, log, timeout):
        """The HTML of the search results page, or None if Google would not
        show it. Raises BrowserFailed if the browser could not be used."""
        from calibre.web.automate.metadata import run_in_browser

        # The first search of a session waits for the browser to launch and
        # warm up, which takes longer than searching usually does
        result = run_in_browser('google_images', 'search', {'url': url}, timeout=max(timeout, 120))
        if result.get('error'):
            log.error('Searching Google failed:', result['error'])
            return None
        return result['html']

    def search_without_browser(self, url):
        br = self.browser
        # See https://github.com/benbusby/whoogle-search/pull/1054 for cookies
        br.set_simple_cookie('CONSENT', 'PENDING+987', '.google.com', path='/')
        from calibre.web.automate.metadata import google_consent_cookie

        socs = google_consent_cookie()
        br.set_simple_cookie(socs['name'], socs['value'], socs['domain'], path=socs['path'])
        # br.set_debug_http(True)
        return br.open(url).read().decode('utf-8')


def test_raw():
    import sys

    raw = open(sys.argv[-1]).read()
    for x in parse_google_markup(raw):
        print(x)


def test(title='Star Trek: Section 31: Control', authors=('David Mack',)):
    try:
        from queue import Queue
    except ImportError:
        from Queue import Queue  # type: ignore
    from threading import Event

    from calibre.utils.logging import default_log

    p = GoogleImages(None)
    setattr(p, 'log', default_log)
    rq = Queue()
    p.download_cover(default_log, rq, Event(), title=title, authors=authors)
    print('Downloaded', rq.qsize(), 'covers')


if __name__ == '__main__':
    test()
