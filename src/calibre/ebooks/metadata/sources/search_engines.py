#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals
import json
import os
import re
import time
from collections import namedtuple
from contextlib import contextmanager
from threading import Lock

try:
    from urllib.parse import parse_qs, quote_plus, unquote, urlencode, quote, urlparse
except ImportError:
    from urlparse import parse_qs, urlparse
    from urllib import quote_plus, urlencode, unquote, quote

from lxml import etree

from calibre import browser as _browser, prints, random_user_agent
from calibre.constants import cache_dir
from calibre.ebooks.chardet import xml_to_unicode
from calibre.utils.lock import ExclusiveFile
from calibre.utils.random_ua import accept_header_for_ua

current_version = (1, 2, 2)
minimum_calibre_version = (2, 80, 0)
webcache = {}
webcache_lock = Lock()


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


def ddg_search(terms, site=None, br=None, log=prints, safe_search=False, dump_raw=None, timeout=60):
    # https://duck.co/help/results/syntax
    terms = [quote_term(ddg_term(t)) for t in terms]
    if site is not None:
        terms.append(quote_term(('site:' + site)))
    q = '+'.join(terms)
    url = 'https://duckduckgo.com/html/?q={q}&kp={kp}'.format(
        q=q, kp=1 if safe_search else -1)
    log('Making ddg query: ' + url)
    br = br or browser()
    root = query(br, url, 'ddg', dump_raw, timeout=timeout)
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
    while not ua or 'Edg/' in ua:
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
        ans.append(Result(a.get('href'), title, cached_url))
    if not ans:
        title = ' '.join(root.xpath('//title/text()'))
        log('Failed to find any results on results page, with title:', title)
    return ans, url


def bing_develop():
    for result in bing_search('heroes abercrombie'.split(), 'www.amazon.com', dump_raw='/t/raw.html', show_user_agent=True)[0]:
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


def google_get_cached_url(url, br=None, log=prints, timeout=60):
    ourl = url
    if not isinstance(url, bytes):
        url = url.encode('utf-8')
    cu = quote(url, safe='')
    if isinstance(cu, bytes):
        cu = cu.decode('utf-8')
    cached_url = 'https://webcache.googleusercontent.com/search?q=cache:' + cu
    br = google_specialize_browser(br or browser())
    try:
        raw = query(br, cached_url, 'google-cache', parser=lambda x: x.encode('utf-8'), timeout=timeout)
    except Exception as err:
        log('Failed to get cached URL from google for URL: {} with error: {}'.format(ourl, err))
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


def google_extract_cache_urls(raw):
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8', 'replace')
    pat = re.compile(r'\\x22(https://webcache\.googleusercontent\.com/.+?)\\x22')
    upat = re.compile(r'\\\\u([0-9a-fA-F]{4})')
    xpat = re.compile(r'\\x([0-9a-fA-F]{2})')
    cache_pat = re.compile('cache:([^:]+):(.+)')

    def urepl(m):
        return chr(int(m.group(1), 16))

    seen = set()
    ans = {}
    for m in pat.finditer(raw):
        cache_url = upat.sub(urepl, m.group(1))
        # print(1111111, cache_url)
        # the following two are necessary for results from Portugal
        cache_url = xpat.sub(urepl, cache_url)
        cache_url = cache_url.replace('&amp;', '&')

        m = cache_pat.search(cache_url)
        cache_id, src_url = m.group(1), m.group(2)
        if cache_id in seen:
            continue
        seen.add(cache_id)
        src_url = src_url.split('+')[0]
        src_url = unquote(src_url)
        curl = canonicalize_url_for_cache_map(src_url)
        # print(22222, cache_id, src_url, curl)
        ans[curl] = cache_url
    return ans


def google_parse_results(root, raw, log=prints, ignore_uncached=True):
    cache_url_map = google_extract_cache_urls(raw)
    # print('\n'.join(cache_url_map))
    ans = []
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
        if curl in cache_url_map:
            cached_url = cache_url_map[curl]
        else:
            try:
                c = div.xpath('descendant::*[@role="menuitem"]//a[@class="fl"]')[0]
            except IndexError:
                if ignore_uncached:
                    log('Ignoring {!r} as it has no cached page'.format(title))
                    continue
                c = {'href': ''}
            cached_url = c.get('href')
        ans.append(Result(a.get('href'), title, cached_url))
    if not ans:
        title = ' '.join(root.xpath('//title/text()'))
        log('Failed to find any results on results page, with title:', title)
    return ans


def google_specialize_browser(br):
    with webcache_lock:
        if not hasattr(br, 'google_consent_cookie_added'):
            br.set_simple_cookie('CONSENT', 'YES+', '.google.com', path='/')
            br.google_consent_cookie_added = True
    return br


def google_format_query(terms, site=None, tbm=None):
    terms = [quote_term(google_term(t)) for t in terms]
    if site is not None:
        terms.append(quote_term(('site:' + site)))
    q = '+'.join(terms)
    url = 'https://www.google.com/search?q={q}'.format(q=q)
    if tbm:
        url += '&tbm=' + tbm
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
    return google_get_cached_url(url, br, log, timeout) or wayback_machine_cached_url(url, br, log, timeout)


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
