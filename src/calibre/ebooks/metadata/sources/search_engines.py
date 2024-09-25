#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import json
import os
import re
import sys
import time
from collections import namedtuple
from contextlib import contextmanager
from functools import partial
from threading import Lock

try:
    from urllib.parse import parse_qs, quote, quote_plus, urlencode, urlparse
except ImportError:
    from urllib import quote, quote_plus, urlencode

    from urlparse import parse_qs, urlparse

from lxml import etree

from calibre import browser as _browser
from calibre import prints as safe_print
from calibre import random_user_agent
from calibre.constants import cache_dir
from calibre.ebooks.chardet import xml_to_unicode
from calibre.utils.lock import ExclusiveFile
from calibre.utils.random_ua import accept_header_for_ua

current_version = (1, 2, 7)
minimum_calibre_version = (2, 80, 0)
webcache = {}
webcache_lock = Lock()
prints = partial(safe_print, file=sys.stderr)


Result = namedtuple('Result', 'url title cached_url')


@contextmanager
def rate_limit(name='test', time_between_visits=2, max_wait_seconds=5 * 60, sleep_time=0.2):
    lock_file = os.path.join(cache_dir(), 'search-engine.' + name + '.lock')
    with ExclusiveFile(lock_file, timeout=max_wait_seconds, sleep_time=sleep_time) as f:
        try:
            lv = float(f.read().decode('utf-8').strip())
        except Exception:
            lv = 0
        # we cannot use monotonic() as this is cross process and historical
        # data as well
        delta = time.time() - lv
        if delta < time_between_visits:
            time.sleep(time_between_visits - delta)
        try:
            yield
        finally:
            f.seek(0)
            f.truncate()
            f.write(repr(time.time()).encode('utf-8'))


def tostring(elem):
    return etree.tostring(elem, encoding='unicode', method='text', with_tail=False)


def browser():
    ua = random_user_agent(allow_ie=False)
    # ua = 'Mozilla/5.0 (Linux; Android 8.0.0; VTR-L29; rv:63.0) Gecko/20100101 Firefox/63.0'
    br = _browser(user_agent=ua)
    br.set_handle_gzip(True)
    br.addheaders += [
        ('Accept', accept_header_for_ua(ua)),
        ('Upgrade-insecure-requests', '1'),
    ]
    return br


def encode_query(**query):
    q = {k.encode('utf-8'): v.encode('utf-8') for k, v in query.items()}
    return urlencode(q).decode('utf-8')


def parse_html(raw):
    try:
        from html5_parser import parse
    except ImportError:
        # Old versions of calibre
        import html5lib
        return html5lib.parse(raw, treebuilder='lxml', namespaceHTMLElements=False)
    else:
        return parse(raw)


def query(br, url, key, dump_raw=None, limit=1, parser=parse_html, timeout=60, save_raw=None, simple_scraper=None):
    with rate_limit(key):
        if simple_scraper is None:
            raw = br.open_novisit(url, timeout=timeout).read()
            raw = xml_to_unicode(raw, strip_encoding_pats=True)[0]
        else:
            raw = simple_scraper(url, timeout=timeout)
    if dump_raw is not None:
        with open(dump_raw, 'w') as f:
            f.write(raw)
    if save_raw is not None:
        save_raw(raw)
    return parser(raw)


def quote_term(x):
    ans = quote_plus(x.encode('utf-8'))
    if isinstance(ans, bytes):
        ans = ans.decode('utf-8')
    return ans


# DDG + Wayback machine {{{


def ddg_url_processor(url):
    return url


def ddg_term(t):
    t = t.replace('"', '')
    if t.lower() in {'map', 'news'}:
        t = '"' + t + '"'
    if t in {'OR', 'AND', 'NOT'}:
        t = t.lower()
    return t


def ddg_href(url):
    if url.startswith('/'):
        q = url.partition('?')[2]
        url = parse_qs(q.encode('utf-8'))['uddg'][0].decode('utf-8')
    return url


def wayback_machine_cached_url(url, br=None, log=prints, timeout=60):
    q = quote_term(url)
    br = br or browser()
    data = query(br, 'https://archive.org/wayback/available?url=' +
                 q, 'wayback', parser=json.loads, limit=0.25, timeout=timeout)
    try:
        closest = data['archived_snapshots']['closest']
        if closest['available']:
            ans = closest['url'].replace('http:', 'https:', 1)
            # get unmodified HTML
            ans = ans.replace(closest['timestamp'], closest['timestamp'] + 'id_', 1)
            return ans
    except Exception:
        pass
    from pprint import pformat
    log('Response from wayback machine:', pformat(data))


def wayback_url_processor(url):
    if url.startswith('/'):
        # Use original URL instead of absolutizing to wayback URL as wayback is
        # slow
        m = re.search('https?:', url)
        if m is None:
            url = 'https://web.archive.org' + url
        else:
            url = url[m.start():]
    return url


ddg_scraper_storage = []


def ddg_search(terms, site=None, br=None, log=prints, safe_search=False, dump_raw=None, timeout=60):
    # https://duck.co/help/results/syntax
    terms = [quote_term(ddg_term(t)) for t in terms]
    if site is not None:
        terms.append(quote_term(('site:' + site)))
    q = '+'.join(terms)
    url = 'https://duckduckgo.com/html/?q={q}&kp={kp}'.format(
        q=q, kp=1 if safe_search else -1)
    log('Making ddg query: ' + url)
    from calibre.scraper.simple import read_url
    br = br or browser()
    root = query(br, url, 'ddg', dump_raw, timeout=timeout, simple_scraper=partial(read_url, ddg_scraper_storage))
    ans = []
    for a in root.xpath('//*[@class="results"]//*[@class="result__title"]/a[@href and @class="result__a"]'):
        try:
            ans.append(Result(ddg_href(a.get('href')), tostring(a), None))
        except KeyError:
            log('Failed to find ddg href in:', a.get('href'))
    return ans, url


def ddg_develop():
    br = browser()
    for result in ddg_search('heroes abercrombie'.split(), 'www.amazon.com', dump_raw='/t/raw.html', br=br)[0]:
        if '/dp/' in result.url:
            print(result.title)
            print(' ', result.url)
            print(' ', get_cached_url(result.url, br))
            print()
# }}}

# Bing {{{


def bing_term(t):
    t = t.replace('"', '')
    if t in {'OR', 'AND', 'NOT'}:
        t = t.lower()
    return t


def bing_url_processor(url):
    return url


def resolve_bing_wrapper_page(url, br, log):
    raw = br.open_novisit(url).read().decode('utf-8', 'replace')
    m = re.search(r'var u = "(.+)"', raw)
    if m is None:
        log(f'Failed to resolve bing wrapper page for url: {url}')
        return url
    log(f'Resolved bing wrapped URL: {url} to {m.group(1)}')
    return m.group(1)


def bing_search(terms, site=None, br=None, log=prints, safe_search=False, dump_raw=None, timeout=60, show_user_agent=False):
    # http://vlaurie.com/computers2/Articles/bing_advanced_search.htm
    terms = [quote_term(bing_term(t)) for t in terms]
    if site is not None:
        terms.append(quote_term(('site:' + site)))
    q = '+'.join(terms)
    url = 'https://www.bing.com/search?q={q}'.format(q=q)
    log('Making bing query: ' + url)
    br = br or browser()
    br.addheaders = [x for x in br.addheaders if x[0].lower() != 'user-agent']
    ua = ''
    from calibre.utils.random_ua import random_common_chrome_user_agent
    while not ua:
        ua = random_common_chrome_user_agent()
    if show_user_agent:
        print('User-agent:', ua)
    br.addheaders.append(('User-agent', ua))

    root = query(br, url, 'bing', dump_raw, timeout=timeout)
    ans = []
    for li in root.xpath('//*[@id="b_results"]/li[@class="b_algo"]'):
        a = li.xpath('descendant::h2/a[@href]') or li.xpath('descendant::div[@class="b_algoheader"]/a[@href]')
        a = a[0]
        title = tostring(a)
        try:
            div = li.xpath('descendant::div[@class="b_attribution" and @u]')[0]
        except IndexError:
            log('Ignoring {!r} as it has no cached page'.format(title))
            continue
        d, w = div.get('u').split('|')[-2:]
        cached_url = 'https://cc.bingj.com/cache.aspx?q={q}&d={d}&mkt=en-US&setlang=en-US&w={w}'.format(
            q=q, d=d, w=w)
        url = a.get('href')
        if url.startswith('https://www.bing.com/'):
            url = resolve_bing_wrapper_page(url, br, log)
        ans.append(Result(url, title, cached_url))
    if not ans:
        title = ' '.join(root.xpath('//title/text()'))
        log('Failed to find any results on results page, with title:', title)
    return ans, url


def bing_develop(terms='heroes abercrombie'):
    if isinstance(terms, str):
        terms = terms.split()
    for result in bing_search(terms, 'www.amazon.com', dump_raw='/t/raw.html', show_user_agent=True)[0]:
        if '/dp/' in result.url:
            print(result.title)
            print(' ', result.url)
            print(' ', result.cached_url)
            print()
# }}}

# Google {{{


def google_term(t):
    t = t.replace('"', '')
    if t in {'OR', 'AND', 'NOT'}:
        t = t.lower()
    return t


def google_url_processor(url):
    return url


def google_cache_url_for_url(url):
    if not isinstance(url, bytes):
        url = url.encode('utf-8')
    cu = quote(url, safe='')
    if isinstance(cu, bytes):
        cu = cu.decode('utf-8')
    return 'https://webcache.googleusercontent.com/search?q=cache:' + cu


def google_get_cached_url(url, br=None, log=prints, timeout=60):
    # Google's webcache was discontinued in september 2024
    cached_url = google_cache_url_for_url(url)
    br = google_specialize_browser(br or browser())
    try:
        raw = query(br, cached_url, 'google-cache', parser=lambda x: x.encode('utf-8'), timeout=timeout)
    except Exception as err:
        log('Failed to get cached URL from google for URL: {} with error: {}'.format(url, err))
    else:
        with webcache_lock:
            webcache[cached_url] = raw
        return cached_url


def canonicalize_url_for_cache_map(url):
    try:
        purl = urlparse(url)
    except Exception:
        return url
    if '.amazon.' in purl.netloc:
        url = url.split('&', 1)[0]
    return url


def google_parse_results(root, raw, log=prints, ignore_uncached=True):
    ans = []
    seen = set()
    for div in root.xpath('//*[@id="search"]//*[@id="rso"]//div[descendant::h3]'):
        try:
            a = div.xpath('descendant::a[@href]')[0]
        except IndexError:
            log('Ignoring div with no main result link')
            continue
        title = tostring(a)
        src_url = a.get('href')
        # print(f'{src_url=}')
        curl = canonicalize_url_for_cache_map(src_url)
        if curl in seen:
            continue
        seen.add(curl)
        ans.append(Result(a.get('href'), title, curl))
    if not ans:
        title = ' '.join(root.xpath('//title/text()'))
        log('Failed to find any results on results page, with title:', title)
    return ans


def google_consent_cookies():
    # See https://github.com/benbusby/whoogle-search/pull/1054 for cookies
    from base64 import standard_b64encode
    from datetime import date
    base = {'domain': '.google.com', 'path': '/'}
    b = base.copy()
    b['name'], b['value'] = 'CONSENT', 'PENDING+987'
    yield b
    template = b'\x08\x01\x128\x08\x14\x12+boq_identityfrontenduiserver_20231107.05_p0\x1a\x05en-US \x03\x1a\x06\x08\x80\xf1\xca\xaa\x06'
    template.replace(b'20231107', date.today().strftime('%Y%m%d').encode('ascii'))
    b = base.copy()
    b['name'], b['value'] = 'SOCS', standard_b64encode(template).decode('ascii').rstrip('=')
    yield b


def google_specialize_browser(br):
    with webcache_lock:
        if not hasattr(br, 'google_consent_cookie_added'):
            for c in google_consent_cookies():
                br.set_simple_cookie(c['name'], c['value'], c['domain'], path=c['path'])
            br.google_consent_cookie_added = True
    return br


def is_probably_book_asin(t):
    return t and len(t) == 10 and t.startswith('B') and t.upper() == t


def is_asin_or_isbn(t):
    from calibre.ebooks.metadata import check_isbn
    return bool(check_isbn(t) or is_probably_book_asin(t))


def google_format_query(terms, site=None, tbm=None):
    prevent_spelling_correction = False
    for t in terms:
        if is_asin_or_isbn(t):
            prevent_spelling_correction = True
            break
    terms = [quote_term(google_term(t)) for t in terms]
    if site is not None:
        terms.append(quote_term(('site:' + site)))
    q = '+'.join(terms)
    url = 'https://www.google.com/search?q={q}'.format(q=q)
    if tbm:
        url += '&tbm=' + tbm
    if prevent_spelling_correction:
        url += '&nfpr=1'
    return url


def google_search(terms, site=None, br=None, log=prints, safe_search=False, dump_raw=None, timeout=60):
    url = google_format_query(terms, site)
    log('Making google query: ' + url)
    br = google_specialize_browser(br or browser())
    r = []
    root = query(br, url, 'google', dump_raw, timeout=timeout, save_raw=r.append)
    return google_parse_results(root, r[0], log=log), url


def google_develop(search_terms='1423146786', raw_from=''):
    if raw_from:
        with open(raw_from, 'rb') as f:
            raw = f.read()
        results = google_parse_results(parse_html(raw), raw)
    else:
        br = browser()
        results = google_search(search_terms.split(), 'www.amazon.com', dump_raw='/t/raw.html', br=br)[0]
    for result in results:
        if '/dp/' in result.url:
            print(result.title)
            print(' ', result.url)
            print(' ', result.cached_url)
            print()
# }}}


def get_cached_url(url, br=None, log=prints, timeout=60):
    return wayback_machine_cached_url(url, br, log, timeout)


def get_data_for_cached_url(url):
    with webcache_lock:
        return webcache.get(url)


def resolve_url(url):
    prefix, rest = url.partition(':')[::2]
    if prefix == 'bing':
        return bing_url_processor(rest)
    if prefix == 'wayback':
        return wayback_url_processor(rest)
    return url


# if __name__ == '__main__':
#     import sys
#     func = sys.argv[-1]
#     globals()[func]()
