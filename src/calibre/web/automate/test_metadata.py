#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Tests for the code that drives the camoufox browser for metadata downloads.
# None of them use a real browser: Camoufox itself is tested in test_camoufox,
# what is tested here is what is built on top of it, using a fake browser that
# records what is done with it.

import asyncio
import os
import threading
import time
import unittest
from collections import Counter
from collections.abc import Callable, Coroutine, Mapping, Sequence
from queue import Empty, Queue
from threading import Event as ThreadingEvent
from typing import Any, cast
from unittest.mock import MagicMock, patch
from urllib.parse import quote_plus, urljoin

from calibre.web.automate import metadata
from calibre.web.automate.camoufox import Browser, Error, Event
from calibre.web.automate.metadata import (
    ENV_VAR,
    FIND_LINK_JS,
    GOOGLE_REJECT_JS,
    SELECT_OPTION_JS,
    AmazonHandler,
    BrowserFailed,
    Deadline,
    GoogleImagesHandler,
    Link,
    SessionWorker,
    SourceHandler,
    State,
    TabPool,
    amazon_department_value,
    amazon_page_kind,
    amazon_results,
    google_page_kind,
    parse_html,
    run_in_browser,
)
from calibre.web.automate.worker import start_worker

HOME = 'https://www.amazon.com/'
OPTIONS = (
    ('search-alias=aps', 'All Departments'),
    ('search-alias=stripbooks-intl-ship', 'Books'),
    ('search-alias=digital-text', 'Kindle Store'),
)
HOME_PAGE = (
    '<html><body><form id="nav-search-bar-form"><select id="searchDropdownBox">'
    + ''.join(f'<option value="{v}">{t}</option>' for v, t in OPTIONS)
    + '</select><input id="twotabsearchtextbox" name="field-keywords"></form></body></html>'
)
CONTINUE_PAGE = '''<html><body><h4>Click the button below to continue shopping</h4>
<form method="get" action="/errors_page/validateCaptcha"><input type="hidden" name="amzn" value="x">
<input type="hidden" name="field-keywords" value="TANMXF"><button type="submit">Continue shopping</button></form></body></html>'''
CAPTCHA_PAGE = '''<html><body><form method="get" action="/errors/validateCaptcha">
<img src="https://images-na.ssl-images-amazon.com/captcha/abc/Captcha_xyz.jpg">
<input id="captchacharacters" name="field-keywords" type="text"><button type="submit">Continue</button></form></body></html>'''
CHALLENGE_PAGE = '''<html><head><script src="https://abc.token.awswaf.com/abc/challenge.js"></script></head>
<body><div id="challenge-container"></div></body></html>'''


def result_item(asin: str, title: str, title_href: str, formats: Sequence[tuple[str, str]] = (), sponsored: bool = False) -> str:
    cls = 's-result-item s-asin' + (' AdHolder' if sponsored else '')
    fmts = ''.join(f'<div class="a-row a-size-base a-color-base"><a class="a-link-normal" href="{href}">{name}</a></div>' for name, href in formats)
    return (
        f'<div class="{cls}" data-component-type="s-search-result" data-asin="{asin}">'
        f'<a class="a-link-normal s-no-outline" href="{title_href}"><img src="x.jpg"></a>'
        f'<a class="a-link-normal" href="{title_href}"><h2><span>{title}</span></h2></a>'
        f'<span>by <a href="/e/author">Some Author</a></span>{fmts}</div>'
    )


def results_page(*items: str) -> str:
    return HOME_PAGE.replace('</body>', '<div class="s-main-slot">' + ''.join(items) + '</div></body>')


# The results used by most of the tests, each a different case for picking
# which of the results to open
RESULTS = results_page(
    # An advert for a book that is also in the results proper, which shifts
    # the index of the links to it in the document
    result_item('B00000000B', 'Advertised', '/Advertised/dp/B00000000B/ref=sp', sponsored=True),
    # The title links to the audiobook, of which there is also a Kindle edition
    # and a paperback
    result_item(
        'B000000002',
        'Audio First',
        '/Audio-First-audiobook/dp/B000000002/ref=sr_1',
        (
            ('Audiobook', '/Audio-First-audiobook/dp/B000000002/ref=sr_1'),
            ('Kindle', '/Audio-First-ebook/dp/B000000003/ref=sr_1k'),
            ('Paperback', '/Audio-First/dp/0000000004/ref=sr_1p'),
        ),
    ),
    # A paperback first, of which there is a Kindle edition too
    result_item(
        '0000000005',
        'A Paperback',
        '/A-Paperback/dp/0000000005/ref=sr_2',
        (('Paperback', '/A-Paperback/dp/0000000005/ref=sr_2'), ('Kindle', '/A-Paperback-ebook/dp/B000000006/ref=sr_2k')),
    ),
    # Rejected by its title
    result_item('B000000007', 'Something [Audio CD]', '/Something/dp/B000000007/ref=sr_3'),
    # Only available as something to listen to
    result_item(
        'B000000008', 'Only Audio', '/Only-Audio-audiobook/dp/B000000008/ref=sr_4', (('Audible Audiobook', '/Only-Audio-audiobook/dp/B000000008/ref=sr_4'),)
    ),
    # Not a product at all
    result_item('B000000009', 'Not A Product', '/gp/video/storefront'),
    # Not a valid ASIN
    result_item('', 'No ASIN', '/No-Asin/dp/B00000000Z/ref=sr_6'),
    # The same book a second time
    result_item('0000000005', 'A Paperback', '/A-Paperback/dp/0000000005/ref=sr_7'),
    # The book that was advertised at the top
    result_item('B00000000B', 'Advertised', '/Advertised/dp/B00000000B/ref=sr_8'),
)

GOOGLE_URL = 'https://www.google.com/search?as_st=y&udm=2&as_q=some+book'
GOOGLE_IMAGES = (
    ('doc1', 'https://example.com/cover1.jpg'),
    ('doc2', 'https://example.com/cover2.jpg'),
    # Social media, which is skipped
    ('doc3', 'https://lookaside.instagram.com/seo/google_widget/crawler/?media_id=1'),
    ('doc4', 'https://scontent-lhr8-1.xx.fbcdn.net/v/t39.30808-6/1_n.jpg'),
    # Not only JPEG
    ('doc5', 'https://example.com/cover5.png'),
)
GOOGLE_RESULTS = (
    '<html><body>'
    + ''.join(f'<div data-docid="{doc}"><img src="thumb.jpg"></div>' for doc, url in GOOGLE_IMAGES)
    + '<script>var padding = "'
    + 'x' * 100
    + '"; var data = {'
    + ', '.join(f'"{doc}": [1,[0,"{doc}",["https://encrypted-tbn0.gstatic.com/images?q={doc}",287,175],["{url}",1600,1000],0]]' for doc, url in GOOGLE_IMAGES)
    + '};</script></body></html>'
)


def consent_form(set_eom: bool, label: str, display: str) -> str:
    # The markup of the forms on consent.google.com/ml
    fields = {'gl': 'AT', 'm': '0', 'app': '0', 'pc': 'srp', 'continue': GOOGLE_URL, 'hl': 'en', 'cm': '2', 'set_eom': 'true' if set_eom else 'false'}
    if not set_eom:
        fields.update(set_sc='true', set_aps='true')
    return (
        f'<form action="https://consent.google.com/save" method="POST" style="display:{display};">'
        + ''.join(f'<input type="hidden" name="{k}" value="{v}">' for k, v in fields.items())
        + f'<input type="submit" value="{label}" class="baseButtonGm3 filledButtonGm3 button searchButton" aria-label="{label}"/></form>'
    )


GOOGLE_CONSENT = (
    '<html><body><h1>Before you continue to Google</h1>'
    + consent_form(True, 'Alle ablehnen', 'inline')
    + consent_form(False, 'Alle akzeptieren', 'inline')
    + consent_form(False, 'Alle akzeptieren', 'block')
    + consent_form(True, 'Alle ablehnen', 'block')
    + '</body></html>'
)
GOOGLE_CAPTCHA = '<html><body><form id="captcha-form" action="index" method="post"><div id="recaptcha"></div></form></body></html>'

DETAILS_PAGE = '''<html><head><link rel="canonical" href="https://www.amazon.com/{slug}/dp/{asin}"></head><body>
<span id="productTitle">{title}</span>
<div id="bylineInfo"><span class="author"><a class="a-link-normal" href="/e/a">{author}</a></span></div>
</body></html>'''


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


def deadline(seconds: float = 30) -> Deadline:
    return Deadline(time.time() + seconds)


# A fake browser {{{


class FakeKeyboard:
    def __init__(self, page: FakePage) -> None:
        self.page = page

    async def press(self, key: str) -> None:
        self.page.browser.log.append(('press', key))
        if key == 'Enter':
            self.page.navigate(f'{HOME}s?k={quote_plus(self.page.typed)}')


class FakeElement:
    def __init__(self, page: FakePage, url: str = '') -> None:
        self.page, self.url = page, url
        self.disposed = False

    async def fill(self, text: str) -> None:
        self.page.typed = text
        self.page.browser.log.append(('fill', text))

    async def click(self, modifiers: Sequence[str] = ()) -> None:
        self.page.browser.log.append(('click', self.url, tuple(modifiers)))
        self.page.browser.ctrl_click(self.page, self.url)

    async def dispose(self) -> None:
        self.disposed = True


class FakeConsentButton(FakeElement):
    async def click(self, modifiers: Sequence[str] = ()) -> None:
        self.page.browser.log.append(('click-reject',))
        if self.page.browser.consent_navigates:
            # Back to the page asked for
            asyncio.get_running_loop().call_soon(self.page.navigate, self.page.url)


class FakePage:
    def __init__(self, browser: FakeBrowser, target_id: str, opener_id: str = '') -> None:
        self.browser, self.target_id, self.opener_id = browser, target_id, opener_id
        self.url = 'about:blank'
        self.closed = False
        self.typed = ''
        self.context = 1
        self.keyboard = FakeKeyboard(self)
        self.nav_waiters: list[asyncio.Future[Event]] = []

    def navigate(self, url: str) -> None:
        self.url = url
        self.context += 1
        self.browser.visits[url] += 1
        waiters, self.nav_waiters = self.nav_waiters, []
        for w in waiters:
            if not w.done():
                w.set_result(Event('Page.navigationCommitted', {'url': url}))

    def navigation_finished(self) -> asyncio.Future[Event]:
        ans: asyncio.Future[Event] = asyncio.get_running_loop().create_future()
        self.nav_waiters.append(ans)
        return ans

    async def open(self, url: str, wait: str = 'load', timeout: float = 0, referer: str = '') -> None:  # ruff: ignore[async-function-with-timeout]
        self.browser.log.append(('open', url, referer))
        if url in self.browser.unloadable:
            raise Error(f'Cannot load {url}')
        self.navigate(url)

    async def html(self) -> str:
        pages = self.browser.site.get(self.url)
        if pages is None:
            return f'<html><body><p id="url">{self.url}</p></body></html>'
        return pages[min(self.browser.visits[self.url], len(pages)) - 1]

    async def wait_until_ready(self, timeout: float = 0) -> None:  # ruff: ignore[async-function-with-timeout]
        pass

    async def wait_for_load(self, state: str = 'load', timeout: float = 0) -> None:  # ruff: ignore[async-function-with-timeout]
        await asyncio.sleep(self.browser.load_time)

    async def wait_for_execution_context(self, timeout: float = 0) -> int:  # ruff: ignore[async-function-with-timeout]
        return self.context

    async def wait_for_new_execution_context(self, previous: int, timeout: float = 0) -> int:  # ruff: ignore[async-function-with-timeout]
        if self.context == previous:
            # The bot check reloading the page once it is done
            self.navigate(self.url)
        return self.context

    async def call(self, js: str, *args: Any, by_value: bool = True) -> Any:  # ruff: ignore[any-type]
        if js == FIND_LINK_JS:
            selector, index, href = args
            self.browser.log.append(('find', selector, index, href))
            if self.browser.links_missing:
                return None
            return FakeElement(self, urljoin(self.url, href))
        if js == GOOGLE_REJECT_JS:
            self.browser.log.append(('reject',))
            forms = parse_html(await self.html()).xpath(metadata.GOOGLE_REJECT_XPATH + '[descendant::button or descendant::input[@type="submit"]]')
            return FakeConsentButton(self) if forms else None
        if js == SELECT_OPTION_JS:
            self.browser.log.append(('select', args[1]))
            return True
        raise AssertionError(f'Unexpected JavaScript: {js}')

    async def wait_for_selector(self, css_selector: str, timeout: float = 0, visible: bool = False) -> FakeElement:  # ruff: ignore[async-function-with-timeout]
        return FakeElement(self)

    async def click(self, css_selector: str, timeout: float = 0) -> None:  # ruff: ignore[async-function-with-timeout]
        self.browser.log.append(('click-selector', css_selector))
        # The continue shopping button leads back to the page asked for
        self.navigate(self.url)

    async def evaluate(self, expression: str) -> int:
        return 0

    async def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.browser.open_tabs -= 1


class FakeBrowser:
    def __init__(self, site: Mapping[str, Sequence[str]] | None = None, load_time: float = 0) -> None:
        self.site = dict(site or {})
        self.load_time = load_time
        self.log: list[tuple[Any, ...]] = []
        self.visits: Counter[str] = Counter()
        self.pages: list[FakePage] = []
        self.new_pages: list[FakePage] = []
        self.open_tabs = self.max_open_tabs = 0
        self.popups_work = True
        self.links_missing = False
        self.unloadable: set[str] = set()
        self.cookie_jar: list[dict[str, Any]] = []
        self.consent_navigates = True

    async def cookies(self) -> list[dict[str, Any]]:
        return list(self.cookie_jar)

    async def set_cookies(self, cookies: Sequence[Mapping[str, Any]]) -> None:
        self.log.append(('set_cookies', tuple(c['name'] for c in cookies)))
        self.cookie_jar.extend(dict(c) for c in cookies)

    def add_page(self, opener_id: str = '') -> FakePage:
        page = FakePage(self, f'tab-{len(self.pages)}', opener_id)
        self.pages.append(page)
        self.open_tabs += 1
        self.max_open_tabs = max(self.max_open_tabs, self.open_tabs)
        return page

    async def new_page(self, timeout: float = 0) -> FakePage:  # ruff: ignore[async-function-with-timeout]
        return self.add_page()

    def ctrl_click(self, opener: FakePage, url: str) -> None:
        if self.popups_work:
            popup = self.add_page(opener.target_id)
            self.new_pages.append(popup)
            # The tab appears before the page in it starts loading
            asyncio.get_running_loop().call_soon(popup.navigate, url)

    async def popup_pages(self, opener: FakePage | None = None) -> tuple[FakePage, ...]:
        assert opener is not None
        ans = tuple(p for p in self.new_pages if p.opener_id == opener.target_id)
        self.new_pages[:] = [p for p in self.new_pages if p.opener_id != opener.target_id]
        return ans

    def detail_tabs(self) -> list[FakePage]:
        return [p for p in self.pages if p.url not in (HOME, 'about:blank') and '/s?k=' not in p.url]


def fake_state(browser: FakeBrowser, handlers: Sequence[type[SourceHandler]] = (AmazonHandler,), max_detail_tabs: int = 10) -> State:
    return State(cast('Browser', browser), handlers, max_detail_tabs)


def search_args(**kw: Any) -> dict[str, Any]:  # ruff: ignore[any-type]
    ans: dict[str, Any] = {'site': 'www.amazon.com', 'domain': 'com', 'query': 'audio first', 'department': 'stripbooks'}
    ans.update(kw)
    return ans


def amazon_site(home: Sequence[str] = (HOME_PAGE,), query: str = 'audio first', results: str = RESULTS) -> dict[str, Sequence[str]]:
    return {HOME: home, f'{HOME}s?k={quote_plus(query)}': (results,)}


# }}}


# Stub handlers {{{


class RecordingHandler(SourceHandler):
    """Records the order requests are handled in and can be made to wait."""

    name = 'recorder'

    def __init__(self, state: State) -> None:
        super().__init__(state)
        self.handled: list[Any] = []
        self.release = asyncio.Event()

    async def handle(self, action: str, args: Mapping[str, Any], deadline: Deadline) -> dict[str, Any]:
        match action:
            case 'record':
                await asyncio.sleep(float(args.get('delay') or 0))
                self.handled.append(args['id'])
                return {'id': args['id']}
            case 'wait':
                await self.release.wait()
                self.handled.append(args['id'])
                return {'id': args['id']}
            case 'log':
                return {'handled': self.handled}
            case 'raise':
                raise ValueError('a handler failure')
            case 'open':
                return {'details': await self.open_in_tabs(None, [Link(u) for u in args['urls']], deadline)}
        return await super().handle(action, args, deadline)


class OtherHandler(RecordingHandler):
    name = 'other'


def opener_handler(name: str) -> type[RecordingHandler]:
    return cast('type[RecordingHandler]', type(f'Handler_{name}', (RecordingHandler,), {'name': name}))


# Used in the worker process by the tests of the worker as a whole


async def setup_for_test(input_data: Mapping[str, Any]) -> None:
    metadata.state = fake_state(FakeBrowser(), (RecordingHandler, OtherHandler))


def start_test_worker() -> tuple[str, Callable[[], int]]:
    return start_worker('calibre.web.automate.metadata:impl_handle_request', 'calibre.web.automate.test_metadata:setup_for_test', input_data={})


# }}}


class TestPageAnalysis(unittest.TestCase):
    def test_metadata_page_kind(self) -> None:
        for html, kind in ((HOME_PAGE, 'ok'), (RESULTS, 'ok'), (CONTINUE_PAGE, 'continue'), (CAPTCHA_PAGE, 'captcha'), (CHALLENGE_PAGE, 'challenge')):
            self.assertEqual(amazon_page_kind(parse_html(html)), kind, html)

    def test_metadata_google_page_kind(self) -> None:
        self.assertEqual(google_page_kind(GOOGLE_URL, parse_html(GOOGLE_RESULTS)), 'ok')
        self.assertEqual(google_page_kind(GOOGLE_URL, parse_html(GOOGLE_CAPTCHA)), 'captcha')
        self.assertEqual(google_page_kind('https://www.google.com/sorry/index?continue=x', parse_html('<p>sorry</p>')), 'captcha')
        self.assertEqual(google_page_kind('https://consent.google.com/ml?continue=x', parse_html('<p>cookies</p>')), 'consent')
        # Asked in a dialog over the page asked for
        self.assertEqual(google_page_kind(GOOGLE_URL, parse_html(GOOGLE_CONSENT)), 'consent')
        self.assertEqual(google_page_kind(GOOGLE_URL, parse_html(GOOGLE_RESULTS.replace('</body>', GOOGLE_CONSENT[12:]))), 'ok')
        self.assertEqual(google_page_kind(GOOGLE_URL, parse_html(GOOGLE_CONSENT.replace('value="true"', 'value="false"'))), 'ok')

    def test_metadata_department(self) -> None:
        root = parse_html(HOME_PAGE)
        # A suffix is allowed for, an alias that is merely a prefix is not
        self.assertEqual(amazon_department_value(root, 'stripbooks'), 'search-alias=stripbooks-intl-ship')
        self.assertEqual(amazon_department_value(root, 'aps'), 'search-alias=aps')
        self.assertEqual(amazon_department_value(root, 'strip'), '')
        self.assertEqual(amazon_department_value(parse_html(CONTINUE_PAGE), 'aps'), '')

    def test_metadata_results(self) -> None:
        root = parse_html(RESULTS)
        selector = 'div[data-component-type="s-search-result"][data-asin="{}"] a[href*="/dp/"]'.format
        self.assertEqual(
            amazon_results(root, HOME, 'com'),
            [
                # The Kindle edition instead of the audiobook, which is the
                # fourth link in the result: image, title, audiobook, Kindle
                Link(f'{HOME}Audio-First-ebook/dp/B000000003/ref=sr_1k', selector('B000000002'), 3, '/Audio-First-ebook/dp/B000000003/ref=sr_1k'),
                Link(f'{HOME}A-Paperback/dp/0000000005/ref=sr_2', selector('0000000005'), 1, '/A-Paperback/dp/0000000005/ref=sr_2'),
                # The second link of the second result for this ASIN, the two
                # links of the advert coming before it in the document
                Link(f'{HOME}Advertised/dp/B00000000B/ref=sr_8', selector('B00000000B'), 3, '/Advertised/dp/B00000000B/ref=sr_8'),
            ],
        )
        self.assertEqual([x.url for x in amazon_results(root, HOME, 'com', max_results=1)], [f'{HOME}Audio-First-ebook/dp/B000000003/ref=sr_1k'])
        kindle = amazon_results(root, HOME, 'com', prefer_kindle=True)
        href = '/A-Paperback-ebook/dp/B000000006/ref=sr_2k'
        self.assertEqual(kindle[1], Link(urljoin(HOME, href), selector('0000000005'), 3, href))
        self.assertEqual(amazon_results(parse_html(HOME_PAGE), HOME, 'com'), [])

    def test_metadata_results_titles(self) -> None:
        page = results_page(result_item('B000000001', 'Libro (Spanish Edition)', '/x/dp/B000000001/ref=1'))
        self.assertEqual(amazon_results(parse_html(page), HOME, 'com'), [])
        self.assertEqual(len(amazon_results(parse_html(page), 'https://www.amazon.de/', 'de')), 1)


class TestTabPool(unittest.TestCase):
    def test_metadata_tab_pool(self) -> None:
        async def t() -> None:
            pool = TabPool(3)
            self.assertEqual(await pool.reserve(5), 3)
            waiter = asyncio.create_task(pool.reserve(2))
            await asyncio.sleep(0.01)
            self.assertFalse(waiter.done(), 'a reservation was granted with no tabs free')
            pool.release(1)
            # Gets what there is rather than waiting for all it wanted
            self.assertEqual(await asyncio.wait_for(waiter, 1), 1)
            pool.release(3)
            self.assertEqual(pool.free, 3)
            # A cancelled waiter is forgotten
            self.assertEqual(await pool.reserve(3), 3)
            waiter = asyncio.create_task(pool.reserve(1))
            await asyncio.sleep(0.01)
            waiter.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await waiter
            self.assertEqual(pool.waiters, [])
            pool.release(3)
            async with pool.slots(2) as count:
                self.assertEqual((count, pool.free), (2, 1))
            self.assertEqual(pool.free, 3)
            with self.assertRaises(ValueError):
                async with pool.slots(1):
                    raise ValueError('released all the same')
            self.assertEqual(pool.free, 3)

        run(t())


class TestHandlers(unittest.TestCase):
    def search(self, browser: FakeBrowser, *requests: Mapping[str, Any]) -> list[dict[str, Any]]:
        async def t() -> list[dict[str, Any]]:
            state = fake_state(browser)
            ans = []
            for args in requests or (search_args(),):
                ans.append(await state.handle({'source': 'amazon', 'action': 'search', 'args': args, 'deadline': time.time() + 30}))
            return ans

        return run(t())

    def test_metadata_amazon_search(self) -> None:
        browser = FakeBrowser(amazon_site())
        result = self.search(browser)[0]
        self.assertNotIn('error', result)
        expected = [f'{HOME}Audio-First-ebook/dp/B000000003/ref=sr_1k', f'{HOME}A-Paperback/dp/0000000005/ref=sr_2', f'{HOME}Advertised/dp/B00000000B/ref=sr_8']
        self.assertEqual([d['url'] for d in result['details']], expected)
        for d in result['details']:
            self.assertIn(d['url'], d['html'])
        self.assertEqual(result['results_url'], f'{HOME}s?k=audio+first')
        self.assertNotIn('results_html', result)
        actions = [x[0] for x in browser.log]
        self.assertEqual(actions[:4], ['open', 'select', 'fill', 'press'])
        self.assertEqual(browser.log[1], ('select', 'search-alias=stripbooks-intl-ship'))
        self.assertEqual(browser.log[2], ('fill', 'audio first'))
        # Every result was opened by clicking on it with the modifier held
        clicks = [x for x in browser.log if x[0] == 'click']
        self.assertEqual([x[1] for x in clicks], expected)
        self.assertTrue(all(x[2] == (metadata.NEW_TAB_MODIFIER,) for x in clicks))
        self.assertNotIn('open', actions[1:])
        # The result tabs are closed, the search tab is kept for next time
        self.assertEqual([p.closed for p in browser.pages], [False, True, True, True])

    def test_metadata_amazon_search_tab_reused(self) -> None:
        site = amazon_site()
        site.update(amazon_site(query='a paperback'))
        site['https://www.amazon.co.uk/'] = (HOME_PAGE,)
        site[f'https://www.amazon.co.uk/s?k={quote_plus("a paperback")}'] = (RESULTS,)
        browser = FakeBrowser(site)
        results = self.search(
            browser, search_args(), search_args(query='a paperback', department='aps'), search_args(query='a paperback', site='www.amazon.co.uk', domain='uk')
        )
        self.assertEqual([r.get('error') for r in results], [None, None, None])
        opens = [x[1] for x in browser.log if x[0] == 'open']
        # The second search is typed into the results page of the first one,
        # a different store gets a tab of its own
        self.assertEqual(opens, [HOME, 'https://www.amazon.co.uk/'])
        books = 'search-alias=stripbooks-intl-ship'
        self.assertEqual([x[1] for x in browser.log if x[0] == 'select'], [books, 'search-alias=aps', books])
        search_tabs = [p for p in browser.pages if p.url == HOME or '/s?k=' in p.url]
        self.assertEqual([p.closed for p in search_tabs], [True, False])

    def test_metadata_amazon_interstitials(self) -> None:
        browser = FakeBrowser(amazon_site(home=(CHALLENGE_PAGE, CONTINUE_PAGE, HOME_PAGE)))
        result = self.search(browser)[0]
        self.assertNotIn('error', result)
        self.assertEqual(len(result['details']), 3)
        self.assertEqual([x for x in browser.log if x[0] == 'click-selector'], [('click-selector', metadata.AMAZON_CONTINUE)])

        browser = FakeBrowser(amazon_site(home=(CHALLENGE_PAGE, CAPTCHA_PAGE)))
        result = self.search(browser)[0]
        self.assertEqual(result['kind'], 'captcha')
        self.assertNotIn('fill', [x[0] for x in browser.log])

        browser = FakeBrowser(amazon_site(home=(CONTINUE_PAGE,)))
        result = self.search(browser)[0]
        self.assertEqual(result['kind'], 'blocked')

    def test_metadata_amazon_results_html(self) -> None:
        result = self.search(FakeBrowser(amazon_site()), search_args(include_results_html=True))[0]
        self.assertIn('Audio-First-ebook', result['results_html'])

    def test_metadata_amazon_no_popups(self) -> None:
        for attr in ('popups_work', 'links_missing'):
            browser = FakeBrowser(amazon_site())
            setattr(browser, attr, not getattr(browser, attr))
            with patch.object(metadata, 'POPUP_TIMEOUT', 0.05):
                result = self.search(browser)[0]
            urls = [d['url'] for d in result['details']]
            self.assertEqual(len(urls), 3)
            for d in result['details']:
                self.assertIn(d['url'], d['html'])
            # Opened in tabs of our own instead, with the results page as the referrer
            opens = [x for x in browser.log if x[0] == 'open'][1:]
            self.assertEqual(opens, [('open', u, f'{HOME}s?k=audio+first') for u in urls])
            self.assertTrue(all(p.closed for p in browser.detail_tabs()))

    def test_metadata_amazon_details(self) -> None:
        async def t() -> tuple[FakeBrowser, dict[str, Any]]:
            browser = FakeBrowser()
            browser.unloadable.add(f'{HOME}dp/B000000002')
            state = fake_state(browser)
            urls = [f'{HOME}dp/B000000001', f'{HOME}dp/B000000002', f'{HOME}dp/B000000003']
            return browser, await state.handle({'source': 'amazon', 'action': 'details', 'args': {'urls': urls}})

        browser, result = run(t())
        details = result['details']
        self.assertEqual([d['url'] for d in details], [f'{HOME}dp/B000000001', f'{HOME}dp/B000000002', f'{HOME}dp/B000000003'])
        self.assertIn('B000000001', details[0]['html'])
        self.assertIn('Cannot load', details[1]['error'])
        self.assertIn('B000000003', details[2]['html'])
        self.assertTrue(all(p.closed for p in browser.pages))

    def test_metadata_batches(self) -> None:
        "With most of the tabs taken the results are opened a few at a time"

        async def t() -> tuple[FakeBrowser, dict[str, Any], int]:
            browser = FakeBrowser(amazon_site())
            state = fake_state(browser, max_detail_tabs=10)
            taken = await state.tab_pool.reserve(8)
            # Only the search tab is open
            result = await state.handle({'source': 'amazon', 'action': 'search', 'args': search_args()})
            state.tab_pool.release(taken)
            return browser, result, state.tab_pool.free

        browser, result, free = run(t())
        self.assertEqual(len(result['details']), 3)
        # One search tab and two result tabs at most
        self.assertEqual(browser.max_open_tabs, 3)
        self.assertEqual(free, 10)

    def test_metadata_many_sources(self) -> None:
        "Sources share the tabs without exceeding the limit and without deadlocking"
        handlers = [opener_handler(f'source{i}') for i in range(5)]

        async def t() -> tuple[FakeBrowser, list[dict[str, Any]], int]:
            browser = FakeBrowser(load_time=0.01)
            state = fake_state(browser, handlers, max_detail_tabs=3)
            requests = [
                state.handle({'source': h.name, 'action': 'open', 'args': {'urls': [f'https://{h.name}.com/{j}' for j in range(5)]}})
                for h in handlers
                for _ in range(2)
            ]
            results = await asyncio.wait_for(asyncio.gather(*requests), 30)
            return browser, results, state.tab_pool.free

        browser, results, free = run(t())
        self.assertEqual(len(results), 10)
        for r in results:
            self.assertEqual(len(r['details']), 5)
            self.assertTrue(all('html' in d for d in r['details']))
        self.assertEqual(browser.max_open_tabs, 3)
        self.assertEqual(browser.open_tabs, 0)
        self.assertEqual(free, 3)

    def test_metadata_tabs_released_after_failure(self) -> None:
        async def t() -> tuple[FakeBrowser, State]:
            browser = FakeBrowser()
            browser.unloadable.update({'https://x.com/0', 'https://x.com/1'})
            state = fake_state(browser, (RecordingHandler,), max_detail_tabs=2)
            r = await state.handle({'source': 'recorder', 'action': 'open', 'args': {'urls': ['https://x.com/0', 'https://x.com/1', 'https://x.com/2']}})
            self.assertEqual(['error' in d for d in r['details']], [True, True, False])
            # And when the request as a whole fails
            with patch.object(FakePage, 'html', side_effect=RuntimeError('boom')), self.assertRaises(RuntimeError):
                await state.handle({'source': 'recorder', 'action': 'open', 'args': {'urls': ['https://x.com/3']}})
            return browser, state

        browser, state = run(t())
        self.assertEqual(state.tab_pool.free, 2)
        self.assertEqual(browser.open_tabs, 0)

    def test_metadata_idle_search_tab(self) -> None:
        async def t() -> None:
            browser = FakeBrowser(amazon_site())
            state = fake_state(browser)
            handler = state.handlers['amazon']
            await state.handle({'source': 'amazon', 'action': 'search', 'args': search_args()})
            tab = handler.search_tab
            assert tab is not None
            await state.close_idle_tabs_once()
            self.assertFalse(tab.closed, 'a recently used search tab was closed')
            handler.last_used -= metadata.SEARCH_TAB_IDLE_TIME + 1
            async with handler.queue:
                # Not while a request is being handled
                self.assertFalse(handler.is_idle(time.monotonic()))
            await state.close_idle_tabs_once()
            self.assertTrue(tab.closed)
            self.assertIsNone(handler.search_tab)
            state.start_reaper()
            reaper = state.reaper
            state.stop_reaper()
            assert reaper is not None
            await asyncio.sleep(0)
            self.assertTrue(reaper.cancelled())

        run(t())

    def google_search(self, browser: FakeBrowser, *urls: str) -> list[dict[str, Any]]:
        async def t() -> list[dict[str, Any]]:
            state = fake_state(browser, (GoogleImagesHandler,))
            return [await state.handle({'source': 'google_images', 'action': 'search', 'args': {'url': url}, 'deadline': time.time() + 30}) for url in urls]

        return run(t())

    def test_metadata_google_images_search(self) -> None:
        other = GOOGLE_URL.replace('some+book', 'other+book')
        browser = FakeBrowser({GOOGLE_URL: (GOOGLE_RESULTS,), other: (GOOGLE_RESULTS,)})
        results = self.google_search(browser, GOOGLE_URL, other)
        self.assertEqual(results, [{'url': GOOGLE_URL, 'html': GOOGLE_RESULTS}, {'url': other, 'html': GOOGLE_RESULTS}])
        # Both searches in the one tab, the second with the first as its
        # referrer, and the consent cookie set only once
        self.assertEqual([x for x in browser.log if x[0] == 'open'], [('open', GOOGLE_URL, ''), ('open', other, GOOGLE_URL)])
        self.assertEqual([x for x in browser.log if x[0] == 'set_cookies'], [('set_cookies', ('SOCS',))])
        self.assertEqual(len(browser.pages), 1)
        self.assertEqual(browser.cookie_jar[0]['domain'], '.google.com')

    def test_metadata_google_images_consent(self) -> None:
        browser = FakeBrowser({GOOGLE_URL: (GOOGLE_CONSENT, GOOGLE_RESULTS)})
        result = self.google_search(browser, GOOGLE_URL)[0]
        self.assertEqual(result, {'url': GOOGLE_URL, 'html': GOOGLE_RESULTS})
        self.assertEqual([x[0] for x in browser.log if x[0] in ('open', 'reject', 'click-reject')], ['open', 'reject', 'click-reject'])

        # Rejecting cookies in a dialog that does not navigate anywhere, so the
        # search is loaded again
        browser = FakeBrowser({GOOGLE_URL: (GOOGLE_CONSENT, GOOGLE_RESULTS)})
        browser.consent_navigates = False
        with patch.object(metadata, 'CONSENT_NAVIGATION_TIMEOUT', 0.05):
            result = self.google_search(browser, GOOGLE_URL)[0]
        self.assertEqual(result, {'url': GOOGLE_URL, 'html': GOOGLE_RESULTS})
        self.assertEqual([x[0] for x in browser.log if x[0] in ('open', 'reject', 'click-reject')], ['open', 'reject', 'click-reject', 'open'])

        # Asked again and again
        browser = FakeBrowser({GOOGLE_URL: (GOOGLE_CONSENT,)})
        result = self.google_search(browser, GOOGLE_URL)[0]
        self.assertEqual(result['kind'], 'consent')
        self.assertEqual(len([x for x in browser.log if x[0] == 'click-reject']), metadata.GOOGLE_MAX_CONSENTS)

        # No button to reject cookies with
        no_button = '<html><body><form action="https://consent.google.com/save"><input name="set_eom" value="true"></form></body></html>'
        browser = FakeBrowser({GOOGLE_URL: (no_button,)})
        result = self.google_search(browser, GOOGLE_URL)[0]
        self.assertEqual(result['kind'], 'consent')
        self.assertNotIn('click-reject', [x[0] for x in browser.log])

    def test_metadata_google_images_blocked(self) -> None:
        result = self.google_search(FakeBrowser({GOOGLE_URL: (GOOGLE_CAPTCHA,)}), GOOGLE_URL)[0]
        self.assertEqual(result['kind'], 'captcha')
        self.assertNotIn('html', result)
        with self.assertRaises(ValueError):
            self.google_search(FakeBrowser(), 'https://www.example.com/search?q=x')


class TestQueueing(unittest.TestCase):
    def test_metadata_queue_in_order(self) -> None:
        async def t() -> None:
            state = fake_state(FakeBrowser(), (RecordingHandler, OtherHandler))
            # Later requests are quicker, so would finish first if they were
            # not queued behind the earlier ones
            tasks = [
                asyncio.create_task(state.handle({'source': 'recorder', 'action': 'record', 'args': {'id': i, 'delay': 0.05 * (4 - i)}})) for i in range(4)
            ]
            await asyncio.gather(*tasks)
            self.assertEqual(cast('RecordingHandler', state.handlers['recorder']).handled, [0, 1, 2, 3])

        run(t())

    def test_metadata_sources_concurrent(self) -> None:
        async def t() -> None:
            state = fake_state(FakeBrowser(), (RecordingHandler, OtherHandler))
            recorder = cast('RecordingHandler', state.handlers['recorder'])
            blocked = asyncio.create_task(state.handle({'source': 'recorder', 'action': 'wait', 'args': {'id': 'blocked'}}))
            await asyncio.sleep(0.01)
            # A different source is not held up
            r = await asyncio.wait_for(state.handle({'source': 'other', 'action': 'record', 'args': {'id': 'other'}}), 1)
            self.assertEqual(r, {'id': 'other'})
            self.assertFalse(blocked.done())
            recorder.release.set()
            self.assertEqual(await blocked, {'id': 'blocked'})

        run(t())

    def test_metadata_deadlines(self) -> None:
        async def t() -> None:
            state = fake_state(FakeBrowser(), (RecordingHandler,))
            recorder = cast('RecordingHandler', state.handlers['recorder'])
            blocked = asyncio.create_task(state.handle({'source': 'recorder', 'action': 'wait', 'args': {'id': 'blocked'}}))
            await asyncio.sleep(0.01)
            queued = asyncio.create_task(state.handle({'source': 'recorder', 'action': 'record', 'args': {'id': 'late'}, 'deadline': time.time() + 0.05}))
            await asyncio.sleep(0.1)
            recorder.release.set()
            await blocked
            r = await queued
            self.assertEqual(r['kind'], 'timeout')
            # It was skipped, not acted on
            self.assertEqual(recorder.handled, ['blocked'])
            # A request that takes too long once started is stopped
            r = await state.handle({'source': 'recorder', 'action': 'record', 'args': {'id': 'slow', 'delay': 5}, 'deadline': time.time() + 0.05})
            self.assertEqual(r['kind'], 'timeout')
            self.assertEqual(recorder.handled, ['blocked'])
            with self.assertRaises(KeyError):
                await state.handle({'source': 'no-such-source', 'action': 'record'})

        run(t())


class TestWorkerProcess(unittest.TestCase):
    def test_metadata_worker_process(self) -> None:
        path, close = start_test_worker()
        try:
            with patch.dict(os.environ, {ENV_VAR: metadata.path_to_env(path)}):
                self.assertEqual(run_in_browser('', 'launch', {})['module_version'], metadata.module_version)
                errors: list[str] = []
                # Requests to the same source are handled one at a time, so the
                # recorder requests take at least 3 * delay in total
                delay = 0.5

                def record(i: int) -> None:
                    try:
                        run_in_browser('recorder', 'record', {'id': i, 'delay': delay})
                    except Exception as e:
                        errors.append(str(e))

                start = time.monotonic()
                threads = []
                for i in range(3):
                    threads.append(threading.Thread(target=record, args=(i,), daemon=True))
                    threads[-1].start()
                    # So that they arrive in order
                    time.sleep(0.05)
                # Another source is answered while those are being worked through
                self.assertEqual(run_in_browser('other', 'record', {'id': 'other'}), {'id': 'other'})
                # Check the property directly rather than against a fixed time
                # budget, which is fragile on slow CI machines
                self.assertTrue(threads[-1].is_alive(), 'other source was held up by the recorder source')
                for t in threads:
                    t.join(10)
                self.assertFalse(errors)
                self.assertGreaterEqual(time.monotonic() - start, 3 * delay)
                self.assertEqual(run_in_browser('recorder', 'log', {})['handled'], [0, 1, 2])
                with self.assertRaisesRegex(BrowserFailed, 'a handler failure'):
                    run_in_browser('recorder', 'raise', {})
        finally:
            close()
        with patch.dict(os.environ, {ENV_VAR: metadata.path_to_env(path)}), self.assertRaisesRegex(BrowserFailed, 'connect'):
            run_in_browser('recorder', 'log', {})

    def test_metadata_session_worker(self) -> None:
        started: list[str] = []

        def fake_start_worker(*args: Any, **kw: Any) -> tuple[str, Callable[[], int]]:  # ruff: ignore[any-type]
            path, close = start_test_worker()
            started.append(path)
            return path, close

        worker = SessionWorker()
        env = {k: v for k, v in os.environ.items() if k != ENV_VAR}
        with (
            patch.object(metadata, 'session_worker', worker),
            patch.object(metadata, 'start_worker', fake_start_worker),
            patch.dict(os.environ, env, clear=True),
        ):
            try:
                self.assertEqual(run_in_browser('recorder', 'record', {'id': 1}), {'id': 1})
                self.assertEqual(run_in_browser('recorder', 'log', {})['handled'], [1])
                self.assertEqual(len(started), 1)
                # A worker that has gone away is replaced
                assert worker.close_worker is not None
                worker.close_worker()
                self.assertEqual(run_in_browser('recorder', 'log', {})['handled'], [])
                self.assertEqual(len(started), 2)
            finally:
                worker.shutdown()

    def test_metadata_env_for_jobs(self) -> None:
        plugin = MagicMock()
        plugin.uses_camoufox_worker = False
        plugin.is_configured.return_value = True
        worker = SessionWorker()

        def launch() -> None:
            worker.path = 'the-path'

        with patch('calibre.customize.ui.metadata_plugins', return_value=[plugin]), patch.object(metadata, 'session_worker', worker):
            with patch.object(worker, 'launch_in_background', side_effect=launch) as launcher:
                self.assertEqual(metadata.env_for_metadata_jobs(), {})
                launcher.assert_not_called()
                plugin.uses_camoufox_worker = True
                self.assertEqual(metadata.env_for_metadata_jobs(), {ENV_VAR: 'the-path'})
                launcher.assert_called_once()
            with patch.object(worker, 'launch_in_background', side_effect=OSError('no workers today')), patch('sys.stderr'):
                self.assertEqual(metadata.env_for_metadata_jobs(), {})

    def test_metadata_live_module(self) -> None:
        live = MagicMock()

        async def impl_handle_request(input_data: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
            return {'live': request}

        async def impl_setup_browser(input_data: Mapping[str, Any]) -> None:
            live.setup_called_with = input_data

        live.impl_handle_request = impl_handle_request
        live.impl_setup_browser = impl_setup_browser
        orig = metadata.live
        metadata.live = None
        try:
            with patch('calibre.live.load_module', return_value=live) as load_module, patch('calibre.live.start_worker') as start_updates:
                run(metadata.setup_browser({'x': 1}))
                self.assertEqual(live.setup_called_with, {'x': 1})
                start_updates.assert_called_once()
                self.assertEqual(run(metadata.handle_request({}, {'a': 1})), {'live': {'a': 1}})
                metadata.finalize({'y': 2})
                live.impl_finalize.assert_called_once_with({'y': 2})
                # Loaded only once per process
                load_module.assert_called_once()
                self.assertEqual(load_module.call_args[0][0], 'calibre.web.automate.metadata')
        finally:
            metadata.live = orig


class TestAmazonPlugin(unittest.TestCase):
    def setUp(self) -> None:
        from calibre.ebooks.metadata.sources.amazon import Amazon
        from calibre.utils.logging import GUILog

        self.plugin = Amazon(None)
        self.plugin._config_obj = {'domain': 'com', 'server': 'auto', 'use_mobi_asin': False, 'prefer_kindle_edition': False}
        self.log = GUILog()

    @property
    def messages(self) -> str:
        return self.log.plain_text

    def details(self, asin: str, title: str = 'Some Book', url: str = '') -> dict[str, str]:
        url = url or f'{HOME}{title.replace(" ", "-")}/dp/{asin}'
        return {'url': url, 'html': DETAILS_PAGE.format(slug=title.replace(' ', '-'), asin=asin, title=title, author='Jane Author')}

    def identify(self, **kw: Any) -> list[Any]:  # ruff: ignore[any-type]
        rq: Queue[Any] = Queue()
        self.plugin.identify(self.log, rq, ThreadingEvent(), timeout=30, **kw)
        ans = []
        while True:
            try:
                ans.append(rq.get_nowait())
            except Empty:
                return ans

    def test_metadata_amazon_create_query(self) -> None:
        p = self.plugin
        self.assertEqual(
            p.create_query(self.log, title='The Name of the Wind', authors=['Patrick Rothfuss', 'X']),
            (['Name', 'of', 'Wind', 'Patrick', 'Rothfuss'], 'stripbooks', 'com', False),
        )
        self.assertEqual(p.create_query(self.log, identifiers={'isbn': '9780756404741'}), (['9780756404741'], 'aps', 'com', True))
        self.assertEqual(p.create_query(self.log, title='x', identifiers={'amazon_uk': 'B0010SKUYM'}), (['B0010SKUYM'], 'aps', 'uk', True))
        self.plugin._config_obj['domain'] = 'br'
        self.assertEqual(p.create_query(self.log, title='Livro')[1:], ('digital-text', 'br', False))
        from calibre.ebooks.metadata.sources.amazon import SearchFailed

        with self.assertRaises(SearchFailed):
            p.create_query(self.log, authors=['Only Authors'])

    def test_metadata_amazon_identify(self) -> None:
        calls: list[tuple[str, str, dict[str, Any]]] = []

        def fake_run_in_browser(source: str, action: str, args: Mapping[str, Any], timeout: float = 0) -> dict[str, Any]:
            calls.append((source, action, dict(args)))
            details = [self.details('B000000003', 'First Book'), {'url': 'broken', 'error': 'it broke'}, self.details('0000000005')]
            return {'results_url': 'x', 'details': details}

        with patch('calibre.web.automate.metadata.run_in_browser', fake_run_in_browser):
            results = self.identify(title='The Name of the Wind', authors=['Patrick Rothfuss'])
        self.assertEqual(
            calls,
            [
                (
                    'amazon',
                    'search',
                    {
                        'site': 'www.amazon.com',
                        'domain': 'com',
                        'query': 'Name of Wind Patrick Rothfuss',
                        'department': 'stripbooks',
                        'max_results': 5,
                        'prefer_kindle': False,
                        'include_results_html': False,
                    },
                )
            ],
        )
        self.assertEqual(
            [(mi.title, mi.authors, mi.identifiers) for mi in results],
            [
                ('First Book', ['Jane Author'], {'amazon': 'B000000003'}),
                ('Some Book', ['Jane Author'], {'amazon': '0000000005'}),
            ],
        )
        self.assertIn('it broke', self.messages)

    def test_metadata_amazon_identify_by_asin(self) -> None:
        calls: list[str] = []

        def fake_run_in_browser(source: str, action: str, args: Mapping[str, Any], timeout: float = 0) -> dict[str, Any]:
            calls.append(action)
            self.assertEqual(args, {'urls': [f'{HOME}dp/B000000003']})
            return {'details': [self.details('B000000003')]}

        with patch('calibre.web.automate.metadata.run_in_browser', fake_run_in_browser):
            results = self.identify(identifiers={'amazon': 'B000000003'})
        self.assertEqual(calls, ['details'])
        self.assertEqual([mi.identifiers for mi in results], [{'amazon': 'B000000003'}])

    def test_metadata_amazon_identify_retries_and_errors(self) -> None:
        queries: list[str] = []

        def no_results(source: str, action: str, args: Mapping[str, Any], timeout: float = 0) -> dict[str, Any]:
            queries.append(args['query'])
            return {'details': []}

        with patch('calibre.web.automate.metadata.run_in_browser', no_results):
            self.assertEqual(self.identify(title='A Title', authors=['An Author'], identifiers={'isbn': '9780756404741'}), [])
        # Tried again without the ISBN
        self.assertEqual(queries, ['9780756404741', 'Title Author'])

        def captcha(source: str, action: str, args: Mapping[str, Any], timeout: float = 0) -> dict[str, Any]:
            return {'error': 'solve this', 'kind': 'captcha'}

        with patch('calibre.web.automate.metadata.run_in_browser', captcha):
            self.assertEqual(self.identify(title='A Title'), [])
        self.assertIn('solve this', self.messages)

    def test_metadata_amazon_fallback(self) -> None:
        def broken(source: str, action: str, args: Mapping[str, Any], timeout: float = 0) -> dict[str, Any]:
            raise BrowserFailed('no browser here')

        with patch('calibre.web.automate.metadata.run_in_browser', broken), patch.object(self.plugin, 'identify_with_search_engine') as se:
            self.identify(title='A Title')
            se.assert_called_once()
            self.assertFalse(se.call_args.kwargs['use_browser'])
            # Only when the server is chosen automatically
            self.plugin._config_obj['server'] = 'amazon'
            se.reset_mock()
            self.identify(title='A Title')
            se.assert_not_called()
        self.assertIn('no browser here', self.messages)

    def test_metadata_amazon_parse_from_browser(self) -> None:
        # The DOM serialized by the browser still has the <meta> tag of
        # whatever encoding the page was served in
        d = self.details('B000000003', 'Café Société')
        d['html'] = d['html'].replace('<head>', '<head><meta charset="iso-8859-1">')
        root = self.plugin.parse_details_from_browser(self.log, d, 'com', 30)
        assert root is not None
        self.assertEqual(root[1].xpath('//span[@id="productTitle"]/text()'), ['Café Société'])
        self.assertIsInstance(root[0], bytes)
        self.assertIsNone(self.plugin.parse_details_from_browser(self.log, {'url': 'x', 'html': '<title>404 - not here</title>'}, 'com', 30))


class TestGoogleImagesPlugin(unittest.TestCase):
    def setUp(self) -> None:
        from calibre.ebooks.metadata.sources.google_images import GoogleImages
        from calibre.utils.logging import GUILog

        self.plugin = GoogleImages(None)
        self.plugin._config_obj = {'max_covers': 5, 'size': 'svga'}
        self.log = GUILog()

    def image_urls(self) -> list[str]:
        return self.plugin.get_image_urls('Some Book', 'An Author', self.log, ThreadingEvent(), 30)

    def test_metadata_google_images_plugin(self) -> None:
        calls: list[tuple[str, str, dict[str, Any]]] = []

        def fake_run_in_browser(source: str, action: str, args: Mapping[str, Any], timeout: float = 0) -> dict[str, Any]:
            calls.append((source, action, dict(args)))
            return {'url': args['url'], 'html': GOOGLE_RESULTS}

        with patch('calibre.web.automate.metadata.run_in_browser', fake_run_in_browser):
            self.assertEqual(self.image_urls(), ['https://example.com/cover1.jpg', 'https://example.com/cover2.jpg', 'https://example.com/cover5.png'])
        self.assertEqual(len(calls), 1)
        source, action, args = calls[0]
        self.assertEqual((source, action), ('google_images', 'search'))
        self.assertTrue(args['url'].startswith('https://www.google.com/search?'), args['url'])
        self.assertIn('as_q=Some+Book+An+Author', args['url'])
        self.assertIn('&imgsz=svga&', args['url'])
        self.assertTrue(args['url'].endswith('&imgar=t%7Cxt'), args['url'])
        self.assertNotIn('tbs=', args['url'])
        self.assertNotIn('as_filetype', args['url'])
        self.plugin._config_obj['size'] = 'any'
        self.assertNotIn('imgsz', self.plugin.search_url('Some Book', 'An Author'))

    def test_metadata_google_images_plugin_errors(self) -> None:
        def captcha(source: str, action: str, args: Mapping[str, Any], timeout: float = 0) -> dict[str, Any]:
            return {'error': 'solve this', 'kind': 'captcha'}

        with patch('calibre.web.automate.metadata.run_in_browser', captcha):
            self.assertEqual(self.image_urls(), [])
        self.assertIn('solve this', self.log.plain_text)

        def broken(source: str, action: str, args: Mapping[str, Any], timeout: float = 0) -> dict[str, Any]:
            raise BrowserFailed('no browser here')

        fallback = patch.object(self.plugin, 'search_without_browser', return_value=GOOGLE_RESULTS)
        with patch('calibre.web.automate.metadata.run_in_browser', broken), fallback as sw:
            self.assertEqual(len(self.image_urls()), 3)
            sw.assert_called_once()
        self.assertIn('no browser here', self.log.plain_text)


def find_tests() -> unittest.TestSuite:
    ans = unittest.TestSuite()
    for cls in (TestPageAnalysis, TestTabPool, TestHandlers, TestQueueing, TestWorkerProcess, TestAmazonPlugin, TestGoogleImagesPlugin):
        ans.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
    return ans


if __name__ == '__main__':
    from calibre.utils.run_tests import run_cli

    run_cli(find_tests())
