#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import json
import re
import time
from collections import defaultdict, namedtuple
try:
    from urllib.parse import parse_qs, quote_plus, urlencode
except ImportError:
    from urlparse import parse_qs
    from urllib import quote_plus, urlencode

from lxml import etree

from calibre import browser as _browser, prints, random_user_agent
from calibre.utils.monotonic import monotonic
from calibre.utils.random_ua import accept_header_for_ua

current_version = (1, 0, 4)
minimum_calibre_version = (2, 80, 0)


last_visited = defaultdict(lambda: 0)
Result = namedtuple('Result', 'url title cached_url')


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


def query(br, url, key, dump_raw=None, limit=1, parser=parse_html, timeout=60):
    delta = monotonic() - last_visited[key]
    if delta < limit and delta > 0:
        time.sleep(delta)
    try:
        raw = br.open_novisit(url, timeout=timeout).read()
    finally:
        last_visited[key] = monotonic()
    if dump_raw is not None:
        with open(dump_raw, 'wb') as f:
            f.write(raw)
    return parser(raw)


def quote_term(x):
    ans = quote_plus(x.encode('utf-8'))
    if isinstance(ans, bytes):
        ans = ans.decode('utf-8')
    return ans


# DDG + Wayback machine {{{

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
            return closest['url'].replace('http:', 'https:')
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
        ans.append(Result(ddg_href(a.get('href')), tostring(a), None))
    return ans, url


def ddg_develop():
    br = browser()
    for result in ddg_search('heroes abercrombie'.split(), 'www.amazon.com', dump_raw='/t/raw.html', br=br)[0]:
        if '/dp/' in result.url:
            print(result.title)
            print(' ', result.url)
            print(' ', wayback_machine_cached_url(result.url, br))
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


def bing_search(terms, site=None, br=None, log=prints, safe_search=False, dump_raw=None, timeout=60):
    # http://vlaurie.com/computers2/Articles/bing_advanced_search.htm
    terms = [quote_term(bing_term(t)) for t in terms]
    if site is not None:
        terms.append(quote_term(('site:' + site)))
    q = '+'.join(terms)
    url = 'https://www.bing.com/search?q={q}'.format(q=q)
    log('Making bing query: ' + url)
    br = br or browser()
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
        # The bing cache does not have a valid https certificate currently
        # (March 2017)
        cached_url = 'http://cc.bingj.com/cache.aspx?q={q}&d={d}&mkt=en-US&setlang=en-US&w={w}'.format(
            q=q, d=d, w=w)
        ans.append(Result(a.get('href'), title, cached_url))
    if not ans:
        title = ' '.join(root.xpath('//title/text()'))
        log('Failed to find any results on results page, with title:', title)
    return ans, url


def bing_develop():
    br = browser()
    for result in bing_search('heroes abercrombie'.split(), 'www.amazon.com', dump_raw='/t/raw.html', br=br)[0]:
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


def google_search(terms, site=None, br=None, log=prints, safe_search=False, dump_raw=None, timeout=60):
    terms = [quote_term(google_term(t)) for t in terms]
    if site is not None:
        terms.append(quote_term(('site:' + site)))
    q = '+'.join(terms)
    url = 'https://www.google.com/search?q={q}'.format(q=q)
    log('Making google query: ' + url)
    br = br or browser()
    root = query(br, url, 'google', dump_raw, timeout=timeout)
    ans = []
    for div in root.xpath('//*[@id="search"]//*[@id="rso"]//*[@class="g"]'):
        try:
            a = div.xpath('descendant::div[@class="r"]/a[@href]')[0]
        except IndexError:
            log('Ignoring div with no descendant')
            continue
        title = tostring(a)
        try:
            c = div.xpath('descendant::*[@role="menu"]//a[@class="fl"]')[0]
        except IndexError:
            log('Ignoring {!r} as it has no cached page'.format(title))
            continue
        cached_url = c.get('href')
        ans.append(Result(a.get('href'), title, cached_url))
    if not ans:
        title = ' '.join(root.xpath('//title/text()'))
        log('Failed to find any results on results page, with title:', title)
    return ans, url


def google_develop(search_terms='1423146786'):
    br = browser()
    for result in google_search(search_terms.split(), 'www.amazon.com', dump_raw='/t/raw.html', br=br)[0]:
        if '/dp/' in result.url:
            print(result.title)
            print(' ', result.url)
            print(' ', result.cached_url)
            print()
# }}}


def resolve_url(url):
    prefix, rest = url.partition(':')[::2]
    if prefix == 'bing':
        return bing_url_processor(rest)
    if prefix == 'wayback':
        return wayback_url_processor(rest)
    return url
