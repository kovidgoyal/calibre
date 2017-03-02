#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import json
import re
import time
from collections import defaultdict, namedtuple
from future_builtins import map
from urllib import quote_plus, urlencode
from urlparse import parse_qs

from lxml import etree

import html5lib
from calibre import browser as _browser, prints, random_user_agent
from calibre.utils.monotonic import monotonic
from calibre.utils.random_ua import accept_header_for_ua

current_version = (1, 0, 0)
minimum_calibre_version = (2, 80, 0)


last_visited = defaultdict(lambda: 0)
Result = namedtuple('Result', 'url title cached_url')


def browser():
    ua = random_user_agent(allow_ie=False)
    br = _browser(user_agent=ua)
    br.set_handle_gzip(True)
    br.addheaders += [
        ('Accept', accept_header_for_ua(ua)),
        ('Upgrade-insecure-requests', '1'),
    ]
    return br


def encode_query(**query):
    q = {k.encode('utf-8'): v.encode('utf-8') for k, v in query.iteritems()}
    return urlencode(q).decode('utf-8')


def parse_html(raw):
    return html5lib.parse(raw, treebuilder='lxml', namespaceHTMLElements=False)


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
    return quote_plus(x.encode('utf-8')).decode('utf-8')


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
    terms = map(ddg_term, terms)
    terms = [quote_term(t) for t in terms]
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
        ans.append(Result(ddg_href(a.get('href')), etree.tostring(
            a, encoding=unicode, method='text', with_tail=False), None))
    return ans


def ddg_develop():
    br = browser()
    for result in ddg_search('heroes abercrombie'.split(), 'www.amazon.com', dump_raw='/t/raw.html', br=br):
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
    terms = map(bing_term, terms)
    terms = [quote_term(t) for t in terms]
    if site is not None:
        terms.append(quote_term(('site:' + site)))
    q = '+'.join(terms)
    url = 'https://www.bing.com/search?q={q}'.format(q=q)
    log('Making bing query: ' + url)
    br = br or browser()
    root = query(br, url, 'bing', dump_raw, timeout=timeout)
    ans = []
    for li in root.xpath('//*[@id="b_results"]/li[@class="b_algo"]'):
        a = li.xpath('descendant::h2/a[@href]')[0]
        div = li.xpath('descendant::div[@class="b_attribution" and @u]')[0]
        d, w = div.get('u').split('|')[-2:]
        # The bing cache does not have a valid https certificate currently
        # (March 2017)
        cached_url = 'http://cc.bingj.com/cache.aspx?q={q}&d={d}&mkt=en-US&setlang=en-US&w={w}'.format(
            q=q, d=d, w=w)
        ans.append(Result(ddg_href(a.get('href')), etree.tostring(
            a, encoding=unicode, method='text', with_tail=False), cached_url))
    return ans


def bing_develop():
    br = browser()
    for result in bing_search('heroes abercrombie'.split(), 'www.amazon.com', dump_raw='/t/raw.html', br=br):
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
