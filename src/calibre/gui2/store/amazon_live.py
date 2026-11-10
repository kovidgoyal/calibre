#!/usr/bin/env python
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

import re
from urllib.parse import urlencode, urlparse

from lxml import html

from calibre.constants import DEBUG
from calibre.gui2.store.search_result import SearchResult
from calibre.scraper.simple import read_url

try:
    from calibre.utils.xml_parse import safe_html_fromstring
except ImportError:
    safe_html_fromstring = html.fromstring

module_version = 3  # needed for live updates
minimum_calibre_version = (9, 17, 0)

# The first search of a session waits for the browser to launch and warm up
BROWSER_TIMEOUT = 120  # seconds
ASIN_PAT = re.compile(r'^[A-Z0-9]{10}$')
DP_PAT = re.compile(r'/dp/([A-Z0-9]{10})(?:[/?]|$)')
# An amount of money, with the currency before or after it, as in: $1.99,
# INR 93.25 or 0,99 €
MONEY_PAT = re.compile(r'(?:[$€£¥₹]|R\$|[A-Z]{2,3}\$?)\s?\d[\d.,]*\d|\d[\d.,]*\s?(?:[$€£¥₹]|[A-Z]{3}\b)')


class AmazonBlocked(Exception):
    pass


def has_class(name):
    return f'contains(concat(" ", normalize-space(@class), " "), " {name} ")'


def text_of(elem):
    return ' '.join(''.join(elem.itertext()).split())


def search_in_browser(self, query, timeout):
    """Search using the shared Camoufox browser, which can get past the bot
    checks Amazon puts in front of anything that is not a browser."""
    from calibre.web.automate.metadata import run_in_browser

    site = urlparse(self.SEARCH_BASE_URL).hostname
    result = run_in_browser('amazon', 'search_results', {'site': site, 'query': query, 'department': 'digital-text'}, timeout=max(timeout, BROWSER_TIMEOUT))
    if result.get('error'):
        raise AmazonBlocked(result['error'])
    return result['html']


def is_bot_check(raw):
    return not raw.strip() or '.awswaf.com/' in raw or 'validateCaptcha' in raw


def search_with_scraper(self, query, timeout):
    uquery = self.SEARCH_BASE_QUERY.copy()
    uquery[self.FIELD_KEYWORDS] = query
    url = self.SEARCH_BASE_URL + '?' + urlencode(uquery)
    return read_url(self.scraper_storage, url, timeout=timeout)


def search_results_html(self, query, timeout):
    try:
        return search_in_browser(self, query, timeout)
    except Exception as err:
        # The browser is not available, for example, because it is still
        # being installed, or because this calibre is too old to have it
        browser_error = err
    if DEBUG:
        print(f'Searching {self.SEARCH_BASE_URL} with a browser failed, trying without one. Error: {browser_error}')
    raw = search_with_scraper(self, query, timeout)
    if is_bot_check(raw):
        raise AmazonBlocked(
            f'Amazon blocked searching {self.SEARCH_BASE_URL} without a browser, and searching with a browser failed with error: {browser_error}'
        )
    return raw


def format_links(item):
    """The links to the formats of a search result, below its title."""
    return item.xpath(f'descendant::div[{has_class("a-row")} and {has_class("a-size-base")} and {has_class("a-color-base")}]/a[contains(@href, "/dp/")]')


def kindle_asin(item):
    """The ASIN of the Kindle edition of a search result, or None if it does
    not have one. Kindle is a name, the same in every language."""
    for a in format_links(item):
        if 'kindle' in text_of(a).lower() or '-ebook/dp/' in (a.get('href') or '').lower():
            m = DP_PAT.search(a.get('href') or '')
            if m is not None:
                return m.group(1)
            asin = item.get('data-asin') or ''
            return asin if ASIN_PAT.match(asin) else None
    return None


def authors_of(item):
    """The authors, in the row with them in, between the "by" label, which is
    in the language of the page, and the next separator. Authors are links to
    their pages on Amazon, or, for those without one, plain text."""
    for row in item.xpath(f'descendant::div[{has_class("a-row")}][span]'):
        children = list(row)
        label = next(
            (i for i, c in enumerate(children) if c.tag == 'span' and (c.get('class') or '').split() == ['a-size-base']),
            None,
        )
        if label is None:
            continue
        parts = []
        for c in children[label + 1 :]:
            if c.tag == 'span' and text_of(c) == '|':
                break
            parts.append(text_of(c))
            if c.tail:
                parts.append(c.tail)
        if ans := ' '.join(' '.join(parts).split()):
            return ans.replace(' ,', ',')
    return ''


def price_of(item):
    price = ''
    for span in item.xpath(f'descendant::span[{has_class("a-price")}]/span[{has_class("a-offscreen")}]'):
        if q := text_of(span):
            price = q
            break
    if not any(c in '123456789' for c in price):
        # Books in Kindle Unlimited show the price for members, zero, with the
        # price to buy them in a sentence below it
        for span in item.xpath(f'descendant::div[{has_class("a-row")} and {has_class("a-color-secondary")}]/span'):
            if m := MONEY_PAT.search(text_of(span)):
                return m.group()
    return price


def parse_results(raw, max_results):
    root = safe_html_fromstring(raw)
    seen = set()
    for item in root.xpath('//div[@data-component-type="s-search-result" and @data-asin]'):
        if len(seen) >= max_results:
            break
        if 'AdHolder' in (item.get('class') or '').split():
            continue
        # Even though only Kindle books are searched for Amazon will still put
        # in results for other formats, so skip anything without a Kindle
        # edition
        asin = kindle_asin(item)
        if asin is None or asin in seen:
            continue
        titles = item.xpath('descendant::h2')
        if not titles:
            continue
        seen.add(asin)
        s = SearchResult()
        s.cover_url = ''.join(item.xpath(f'descendant::img[{has_class("s-image")}]/@src')[:1]).strip()
        s.title = text_of(titles[0])
        s.author = authors_of(item)
        s.detail_item = asin
        s.price = price_of(item)
        s.formats = 'Kindle'
        yield s


def search_amazon(self, query, max_results=10, timeout=60, write_html_to=None):
    if isinstance(query, bytes):
        # The Get books dialog passes the query as UTF-8 encoded bytes
        query = query.decode('utf-8')
    raw = search_results_html(self, query, timeout)
    if write_html_to is not None:
        with open(write_html_to, 'w', encoding='utf-8') as f:
            f.write(raw)
    yield from parse_results(raw, max_results)


def get_details_amazon(self, search_result, timeout):
    # The DRM status of a book is only on its details page, and fetching that
    # for every search result is what gets Amazon to detect a bot, so it is
    # left unknown. Still present as older calibre versions call it.
    return False


def get_store_link_amazon(self, detail_item):
    return (self.DETAILS_URL + detail_item) if detail_item else self.STORE_LINK
