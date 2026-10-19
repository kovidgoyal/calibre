#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""
Fetch the web pages metadata sources get their data from with the Camoufox
browser, for the sources whose websites block anything that is not a browser.
"""

# These two are read by calibre.live, which updates the server half of this
# module from the calibre website, so that changes to the websites it drives
# can be kept up with without needing a new calibre release
module_version = 1
minimum_calibre_version = (9, 17, 0)

import asyncio
import os
import re
import time
from collections.abc import AsyncGenerator, Callable, Coroutine, Iterable, Mapping, Sequence
from contextlib import asynccontextmanager, suppress
from threading import Lock, Thread
from types import ModuleType
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple
from urllib.parse import urljoin, urlparse

from calibre.constants import ismacos
from calibre.web.automate.camoufox import Element, Error, Page, TimeoutExceeded, debug, wait_for
from calibre.web.automate.download_deps import Install
from calibre.web.automate.worker import make_request, start_worker

if TYPE_CHECKING:
    from lxml.etree import _Element

    from calibre.web.automate.camoufox import Browser

# How it fits together
# ====================
#
# A single worker process runs one Camoufox instance for all the metadata
# downloads of a calibre session, so that the cost of launching and warming up
# the browser is paid once. The process belongs to whichever process first
# needs it: the calibre GUI, which runs every metadata download in a short lived
# job process of its own and tells those jobs where to find the worker through
# the ENV_VAR environment variable, or a command line tool such as
# fetch-ebook-metadata, which needs it only for its own lifetime.
#
# Every source has a handler, a subclass of SourceHandler, which serves the
# source's requests one at a time and in order, since making several requests
# at once of the same website from one browser is what a bot looks like, not
# what a person does. Different sources are served concurrently, each in tabs
# of its own, so that adding sources does not make each of them wait for the
# others. A handler keeps one tab of its own for searching in, and borrows tabs
# for loading the pages it finds from TabPool, which limits the number of tabs
# open at once across all the sources.

ENV_VAR = 'CALIBRE_METADATA_BROWSER_WORKER'
WORKER_MODULE = 'calibre.web.automate.metadata'

# Tabs for loading pages, shared by all sources. Enough for two sources each
# opening five search results at once.
MAX_DETAIL_TABS = 10
# How long a source's search tab is kept open once the source stops using it
SEARCH_TAB_IDLE_TIME = 300.0  # seconds
IDLE_CHECK_INTERVAL = 30.0  # seconds
# How long a request may take, including waiting for its turn, if the client
# does not say. Long enough for the first request of a session, which waits for
# the browser to launch and warm up.
DEFAULT_REQUEST_TIMEOUT = 120.0  # seconds
# How long to wait for a tab to appear after clicking a link with the new tab
# modifier held, before opening the link in a tab of our own instead
POPUP_TIMEOUT = 5.0  # seconds
POPUP_POLL_INTERVAL = 0.05  # seconds
# The longest to wait for any one page loaded in a tab of its own
PAGE_TIMEOUT = 30.0  # seconds
# The longest to wait for a form field that might never appear
FIELD_TIMEOUT = 20.0  # seconds
# The longest to wait for a page to finish loading its stylesheets and images
# before clicking on anything in it, see SourceHandler.settle()
SETTLE_TIMEOUT = 10.0  # seconds
SCROLL_TIMEOUT = 3.0  # seconds
NEW_TAB_MODIFIER = 'meta' if ismacos else 'control'


# Server side, runs in the worker process {{{


class Link(NamedTuple):
    """A link to open in a tab of its own.

    If selector is given the link is opened by clicking on the element
    ``document.querySelectorAll(selector)[index]``, provided its href attribute
    is still href, otherwise url is loaded in a new tab.
    """

    url: str
    selector: str = ''
    index: int = 0
    href: str = ''


class Deadline:
    def __init__(self, when: float) -> None:
        self.when = when

    def remaining(self, at_most: float = 0) -> float:
        ans = max(0.0, self.when - time.time())
        return min(ans, at_most) if at_most else ans


class Blocked(Exception):
    """The website answered with a page we cannot get past."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


def error_result(kind: str, message: str) -> dict[str, Any]:
    return {'error': message, 'kind': kind}


class TabPool:
    """The number of tabs that may be open for loading pages at once.

    A request reserves all the tabs it is going to use in one go, being given
    as many of those it wants as are free, but always at least one. Since it
    never holds some tabs while waiting for more, requests can never end up
    waiting on each other.
    """

    def __init__(self, size: int) -> None:
        self.size = max(1, size)
        self.free = self.size
        self.waiters: list[asyncio.Future[None]] = []

    async def reserve(self, wanted: int) -> int:
        while self.free < 1:
            waiter = asyncio.get_running_loop().create_future()
            self.waiters.append(waiter)
            try:
                await waiter
            finally:
                with suppress(ValueError):
                    self.waiters.remove(waiter)
        ans = max(1, min(wanted, self.free))
        self.free -= ans
        return ans

    def release(self, count: int) -> None:
        # Not a coroutine, so that it cannot be interrupted, which matters as
        # it is called while unwinding from cancellation
        self.free = min(self.size, self.free + count)
        waiters, self.waiters = self.waiters, []
        for waiter in waiters:
            if not waiter.done():
                waiter.set_result(None)

    @asynccontextmanager
    async def slots(self, wanted: int) -> AsyncGenerator[int]:
        count = await self.reserve(wanted)
        try:
            yield count
        finally:
            self.release(count)


class SourceHandler:
    """Serves the requests of one metadata source, one at a time."""

    name: ClassVar[str] = ''

    def __init__(self, state: State) -> None:
        self.state = state
        # asyncio locks are first come, first served, so requests are handled
        # in the order they arrived in
        self.queue = asyncio.Lock()
        self.search_tab: Page | None = None
        self.search_tab_key = ''
        self.last_used = time.monotonic()

    @property
    def browser(self) -> Browser:
        return self.state.browser

    async def handle(self, action: str, args: Mapping[str, Any], deadline: Deadline) -> dict[str, Any]:
        raise NotImplementedError(f'The {self.name} metadata source has no action: {action}')

    async def search_page(self, key: str, deadline: Deadline) -> Page:
        """The tab this source searches in, kept open between requests.

        key identifies the website being searched, asking for a different one
        replaces the tab rather than navigating it, the way a person would open
        a different shop in a new tab.
        """
        if self.search_tab is not None and (self.search_tab.closed or self.search_tab_key != key):
            await self.close_search_tab()
        if self.search_tab is None:
            self.search_tab = await self.browser.new_page(timeout=deadline.remaining(PAGE_TIMEOUT))
            self.search_tab_key = key
        return self.search_tab

    async def close_search_tab(self) -> None:
        page, self.search_tab, self.search_tab_key = self.search_tab, None, ''
        if page is not None:
            with suppress(Error):
                await page.close()

    def is_idle(self, now: float) -> bool:
        return not self.queue.locked() and self.search_tab_unused(now)

    def search_tab_unused(self, now: float) -> bool:
        return self.search_tab is not None and now - self.last_used > SEARCH_TAB_IDLE_TIME

    async def settle(self, page: Page, deadline: Deadline) -> None:
        """Wait for the page to finish loading before using the mouse on it.

        Until its stylesheets and images are in, the layout of a page keeps
        changing, so an element can move away from under the cursor while it is
        on its way there. A page with something on it that never finishes
        loading is used anyway, after a while.
        """
        try:
            await page.wait_for_load('load', timeout=deadline.remaining(SETTLE_TIMEOUT))
        except TimeoutExceeded:
            pass

    async def scroll_to_top(self, page: Page, deadline: Deadline) -> None:
        """Scroll back up to the top of the page, where the search box is.

        Needed after clicking on links further down the page, since scrolling
        an element into view does not cope with a page that scrolls smoothly.
        """
        if not await page.evaluate('window.scrollY'):
            return
        await page.evaluate('window.scrollTo({top: 0, behavior: "smooth"})')
        end = time.monotonic() + deadline.remaining(SCROLL_TIMEOUT)
        while time.monotonic() < end:
            await asyncio.sleep(POPUP_POLL_INTERVAL)
            if not await page.evaluate('window.scrollY'):
                break

    async def submit_and_wait(self, page: Page, submit: Callable[[], Coroutine[Any, Any, Any]], deadline: Deadline) -> None:
        """Do whatever submit does, which should navigate page, and wait for
        the DOM of the page it navigates to."""
        finished = page.navigation_finished()
        try:
            await submit()
            event = await wait_for(finished, deadline.remaining(PAGE_TIMEOUT), 'the page to load')
        finally:
            finished.cancel()
        if event.method == 'Page.navigationAborted':
            raise Error(f'Loading the page was aborted: {event.params.get("errorText")}')
        await page.wait_for_load('domcontentloaded', timeout=deadline.remaining(PAGE_TIMEOUT))

    async def open_in_tabs(self, opener: Page | None, links: Sequence[Link], deadline: Deadline) -> list[dict[str, str]]:
        """Load every link in a tab of its own and hand back the HTML of each.

        As many links are loaded at once as there are tabs to be had, so when
        other sources are busy this works its way through the links in batches
        rather than waiting for enough tabs to load all of them at once. The
        results are in the same order as links. A link that fails to load gets
        a result with an error rather than failing the lot.
        """
        results: list[dict[str, str]] = []
        pending = list(links)
        while pending:
            async with self.state.tab_pool.slots(len(pending)) as count:
                batch, pending = pending[:count], pending[count:]
                results.extend(await self.load_batch(opener, batch, deadline))
        return results

    async def load_batch(self, opener: Page | None, batch: Sequence[Link], deadline: Deadline) -> list[dict[str, str]]:
        tabs: list[Page | dict[str, str]] = []
        try:
            for link in batch:
                try:
                    tabs.append(await self.open_tab(opener, link, deadline))
                except (Error, TimeoutError) as err:
                    tabs.append({'url': link.url, 'error': f'Failed to open {link.url}: {err}'})
            # The tabs were all opened before waiting for any of them, so they
            # load in parallel
            return list(await asyncio.gather(*(self.tab_result(tab, link, deadline) for tab, link in zip(tabs, batch))))
        finally:
            for tab in tabs:
                if not isinstance(tab, dict):
                    with suppress(Error):
                        await tab.close()
            if opener is not None:
                # Tabs that appeared too late to be waited for
                for tab in await self.browser.popup_pages(opener):
                    with suppress(Error):
                        await tab.close()

    async def open_tab(self, opener: Page | None, link: Link, deadline: Deadline) -> Page:
        if opener is not None and link.selector:
            try:
                tab = await self.click_open(opener, link, deadline)
            except (Error, TimeoutError) as err:
                debug(f'Clicking on the link to {link.url} failed: {err}')
            else:
                if tab is not None:
                    return tab
        tab = await self.browser.new_page(timeout=deadline.remaining(PAGE_TIMEOUT))
        try:
            await tab.open(link.url, wait='commit', timeout=deadline.remaining(PAGE_TIMEOUT), referer=opener.url if opener is not None else '')
        except BaseException:
            with suppress(Error):
                await tab.close()
            raise
        return tab

    async def click_open(self, opener: Page, link: Link, deadline: Deadline) -> Page | None:
        """Open a link in a new tab the way a person would, by clicking on it
        with the new tab modifier held down, so that the page is loaded with
        the referrer and the history a click gives it."""
        element: Element | None = await opener.call(FIND_LINK_JS, link.selector, link.index, link.href, by_value=False)
        if element is None:
            return None
        try:
            await element.click(modifiers=(NEW_TAB_MODIFIER,))
        finally:
            await element.dispose()
        end = time.monotonic() + deadline.remaining(POPUP_TIMEOUT)
        while True:
            if tabs := await self.browser.popup_pages(opener):
                for extra in tabs[1:]:
                    with suppress(Error):
                        await extra.close()
                return tabs[0]
            if time.monotonic() >= end:
                return None
            await asyncio.sleep(POPUP_POLL_INTERVAL)

    async def tab_result(self, tab: Page | dict[str, str], link: Link, deadline: Deadline) -> dict[str, str]:
        if isinstance(tab, dict):
            return tab
        try:
            await tab.wait_until_ready(deadline.remaining(PAGE_TIMEOUT))
            # A tab opened by a click starts out on about:blank, whose load
            # events have nothing to do with the page being opened
            end = time.monotonic() + deadline.remaining(PAGE_TIMEOUT)
            while tab.url == 'about:blank':
                if time.monotonic() >= end:
                    raise TimeoutError(f'{link.url} never started loading')
                await asyncio.sleep(POPUP_POLL_INTERVAL)
            await tab.wait_for_load('domcontentloaded', timeout=deadline.remaining(PAGE_TIMEOUT))
            return {'url': tab.url, 'html': await tab.html()}
        except (Error, TimeoutError) as err:
            return {'url': link.url, 'error': f'Failed to load {link.url}: {err}'}


FIND_LINK_JS = '''(selector, index, href) => {
    const a = document.querySelectorAll(selector)[index];
    return (a && a.getAttribute('href') === href) ? a : null;
}'''

SELECT_OPTION_JS = '''(selector, value) => {
    const s = document.querySelector(selector);
    if (!s || s.value === value) return false;
    s.value = value;
    s.dispatchEvent(new Event('input', {bubbles: true}));
    s.dispatchEvent(new Event('change', {bubbles: true}));
    return true;
}'''


def parse_html(html: str) -> _Element:
    from html5_parser import parse

    return parse(html)


# Amazon {{{

AMAZON_SEARCH_BOX = '#twotabsearchtextbox, #nav-search-bar-form input[name="field-keywords"]'
AMAZON_DEPARTMENT = '#searchDropdownBox'
AMAZON_CONTINUE = 'form[action*="validateCaptcha"] button, form[action*="validateCaptcha"] input[type="submit"]'
AMAZON_MAX_INTERSTITIALS = 4
ASIN_PAT = re.compile(r'^[A-Z0-9]{10}$')
DP_PAT = re.compile(r'/dp/([A-Z0-9]{10})(?:[/?]|$)')
# Words in the name of a format that mean it is something to listen to, which
# is not what calibre wants metadata for when there is anything else
AUDIO_FORMAT_WORDS = ('audio', 'audible', 'hörbuch', 'hörbücher', 'luisterboek', 'ljudbok', 'オーディオブック')


def amazon_page_kind(root: _Element) -> str:
    """What sort of page Amazon answered with: the page asked for (ok), a
    CAPTCHA (captcha), the JavaScript challenge that works out whether it is
    talking to a browser and then reloads the page (challenge) or the page with
    only a button to click that Amazon puts in front of browsers it is not sure
    about (continue)."""
    if root.xpath('//div[@id="challenge-container"] | //script[contains(@src, ".awswaf.com/")]'):
        return 'challenge'
    forms = root.xpath('//form[contains(@action, "validateCaptcha")]')
    if not forms:
        return 'ok'
    for form in forms:
        # The continue page has a field-keywords field too, but a hidden one
        if form.xpath(
            'descendant::input[@id="captchacharacters" or (@name="field-keywords" and not(@type="hidden"))] | descendant::img[contains(@src, "captcha")]'
        ):
            return 'captcha'
    return 'continue'


def amazon_department_value(root: _Element, alias: str) -> str:
    """The value of the option for the search alias in the department menu.

    Which options there are varies by store and even by where in the world the
    browser is, one in India gets stripbooks-intl-ship in the US store, so the
    alias only has to match up to such a suffix.
    """
    for option in root.xpath(f'//select[@id="{AMAZON_DEPARTMENT[1:]}"]/option[@value]'):
        value = option.get('value') or ''
        current = value.partition('search-alias=')[2]
        if current == alias or current.startswith(alias + '-'):
            return value
    return ''


def amazon_title_ok(title: str, domain: str) -> bool:
    title = title.lower()
    bad = [
        'bulk pack',
        '[audiobook]',
        '[audio cd]',
        '(a book companion)',
        '( slipcase with door )',
        ': free sampler',
    ]
    if domain == 'com':
        bad.extend(f'({x} edition)' for x in ('spanish', 'german'))
    if any(x in title for x in bad):
        return False
    # Bad entries in the catalog
    return not (title and title[0] in '[{' and re.search(r'\(\s*author\s*\)', title) is not None)


def text_of(elem: _Element) -> str:
    return ' '.join(''.join(elem.itertext()).split())


def has_class(name: str) -> str:
    return f'contains(concat(" ", normalize-space(@class), " "), " {name} ")'


def amazon_results(root: _Element, base_url: str, domain: str, max_results: int = 5, prefer_kindle: bool = False) -> list[Link]:
    """The links to the best edition of each of the first few books in the
    search results, skipping adverts and anything that is not a book.

    A search result is a book in all its formats, linked to separately below
    its title, with the title itself linking to whichever format Amazon thinks
    best, often enough the audiobook. That is swapped for the first format that
    is not audio, or for the Kindle edition if that is preferred.
    """
    ans: list[Link] = []
    seen: set[str] = set()
    # How many of the links that the selector for each ASIN matches have gone
    # by, since the same book can appear more than once in the results
    links_before: dict[str, int] = {}
    for item in root.xpath('//div[@data-component-type="s-search-result" and @data-asin]'):
        asin = item.get('data-asin') or ''
        if not ASIN_PAT.match(asin):
            continue
        links = item.xpath('descendant::a[contains(@href, "/dp/")]')
        offset = links_before.get(asin, 0)
        links_before[asin] = offset + len(links)
        if 'AdHolder' in (item.get('class') or '').split() or len(ans) >= max_results:
            continue
        title_links = item.xpath('descendant::a[contains(@href, "/dp/") and descendant::h2] | descendant::h2/descendant::a[contains(@href, "/dp/")]')
        if not title_links:
            continue
        title_link = title_links[0]
        if not amazon_title_ok(text_of(title_link), domain):
            continue
        formats: dict[str, str] = {}
        format_links: list[tuple[str, _Element]] = []
        for a in item.xpath(f'descendant::div[{has_class("a-row")} and {has_class("a-size-base")} and {has_class("a-color-base")}]/a[contains(@href, "/dp/")]'):
            name = text_of(a).lower()
            if (m := DP_PAT.search(a.get('href') or '')) is not None and name:
                formats.setdefault(m.group(1), name)
                format_links.append((name, a))

        def format_of(a: _Element) -> str:
            m = DP_PAT.search(a.get('href') or '')
            return formats.get(m.group(1), '') if m is not None else ''  # ruff: ignore[function-uses-loop-variable]

        def is_audio(name: str, a: _Element) -> bool:
            href = (a.get('href') or '').lower()
            return any(x in name for x in AUDIO_FORMAT_WORDS) or '-audiobook/dp/' in href or '-audio/dp/' in href

        def is_kindle(name: str, a: _Element) -> bool:
            return 'kindle' in name or '-ebook/dp/' in (a.get('href') or '').lower()

        chosen = title_link
        if prefer_kindle and not is_kindle(format_of(title_link), title_link):
            chosen = next((a for name, a in format_links if is_kindle(name, a)), title_link)
        if is_audio(format_of(chosen), chosen):
            alternative = next((a for name, a in format_links if not is_audio(name, a)), None)
            if alternative is None:
                continue
            chosen = alternative
        href = chosen.get('href') or ''
        m = DP_PAT.search(href)
        if m is None or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        selector = f'div[data-component-type="s-search-result"][data-asin="{asin}"] a[href*="/dp/"]'
        ans.append(Link(urljoin(base_url, href), selector, offset + links.index(chosen), href))
    return ans


class AmazonHandler(SourceHandler):
    name = 'amazon'

    async def handle(self, action: str, args: Mapping[str, Any], deadline: Deadline) -> dict[str, Any]:
        try:
            match action:
                case 'search':
                    return await self.search(args, deadline)
                case 'details':
                    return {'details': await self.open_in_tabs(None, [Link(str(u)) for u in args['urls']], deadline)}
        except Blocked as err:
            return error_result(err.kind, str(err))
        return await super().handle(action, args, deadline)

    async def check_page(self, page: Page, deadline: Deadline) -> _Element:
        """Get past the interstitials, if any, and hand back the parsed page."""
        for attempt in range(AMAZON_MAX_INTERSTITIALS + 1):
            context = await page.wait_for_execution_context(deadline.remaining(PAGE_TIMEOUT))
            try:
                root = parse_html(await page.html())
            except Error:
                # The page navigated away while being read
                await page.wait_for_new_execution_context(context, deadline.remaining(PAGE_TIMEOUT))
                await page.wait_for_load('domcontentloaded', timeout=deadline.remaining(PAGE_TIMEOUT))
                continue
            kind = amazon_page_kind(root)
            match kind:
                case 'ok':
                    return root
                case 'captcha':
                    raise Blocked(
                        'captcha',
                        'Amazon asked for a CAPTCHA to be solved, probably because too many books were downloaded. Wait for some time and try again.',
                    )
                case 'challenge':
                    # It reloads the page once it is done, which may already
                    # have happened, in which case there is a new context
                    debug('Waiting for the Amazon bot check to finish')
                    await page.wait_for_new_execution_context(context, deadline.remaining(PAGE_TIMEOUT))
                    await page.wait_for_load('domcontentloaded', timeout=deadline.remaining(PAGE_TIMEOUT))
                case 'continue':
                    debug('Clicking past the Amazon continue shopping page')
                    await self.settle(page, deadline)
                    await self.submit_and_wait(page, lambda: page.click(AMAZON_CONTINUE, timeout=deadline.remaining(FIELD_TIMEOUT)), deadline)
        raise Blocked('blocked', 'Amazon keeps answering with pages that are not the one asked for')

    async def search(self, args: Mapping[str, Any], deadline: Deadline) -> dict[str, Any]:
        """Search the way a person does, by typing the query into the search
        box of the store's home page, or of whatever page of the store the tab
        was left on, and then open the books found in tabs of their own."""
        site = str(args['site'])
        domain = str(args.get('domain') or 'com')
        page = await self.search_page(site, deadline)
        if urlparse(page.url).hostname != site:
            await page.open(f'https://{site}/', wait='domcontentloaded', timeout=deadline.remaining(PAGE_TIMEOUT))
        root = await self.check_page(page, deadline)
        await self.settle(page, deadline)
        if value := amazon_department_value(root, str(args.get('department') or 'aps')):
            await page.call(SELECT_OPTION_JS, AMAZON_DEPARTMENT, value)
        await self.scroll_to_top(page, deadline)
        box = await page.wait_for_selector(AMAZON_SEARCH_BOX, timeout=deadline.remaining(FIELD_TIMEOUT), visible=True)
        try:
            await box.fill(str(args['query']))
        finally:
            await box.dispose()
        await self.submit_and_wait(page, lambda: page.keyboard.press('Enter'), deadline)
        root = await self.check_page(page, deadline)
        await self.settle(page, deadline)
        links = amazon_results(root, page.url, domain, int(args.get('max_results') or 5), bool(args.get('prefer_kindle')))
        ans: dict[str, Any] = {'results_url': page.url, 'details': await self.open_in_tabs(page, links, deadline)}
        if args.get('include_results_html'):
            from lxml.etree import tostring

            ans['results_html'] = tostring(root, encoding='unicode', method='html')
        return ans


# }}}

# Google Images {{{

GOOGLE_SEARCH_HOST = 'www.google.com'
# Whatever page Google answers with, the results, the CAPTCHA or the cookie
# consent page, has one of these in it once it has loaded
GOOGLE_PAGE_LOADED = 'div[data-docid], div[data-tbnid], #captcha-form, #recaptcha, form[action*="consent.google."]'
GOOGLE_MAX_CONSENTS = 2
# How long to wait for rejecting cookies to navigate back to the results,
# which it may not do, see GoogleImagesHandler.reject_cookies()
CONSENT_NAVIGATION_TIMEOUT = 10.0  # seconds
# The form that rejects cookies on the page asking for them to be agreed to
# posts to consent.google.com/save and is the one with set_eom=true, the one
# that accepts them having set_eom=false. It is found that way, rather than by
# the label of its button, as the label is in the language of the user. There
# can be more than one such form, only one of which is visible, depending on
# the size of the window.
GOOGLE_REJECT_XPATH = '//form[contains(@action, "consent.google.") and contains(@action, "/save") and descendant::input[@name="set_eom" and @value="true"]]'
GOOGLE_REJECT_JS = '''() => {
    for (const form of document.querySelectorAll('form[action*="consent.google."]')) {
        if (!form.getAttribute('action').includes('/save') || !form.querySelector('input[name="set_eom"][value="true"]')) continue;
        for (const button of form.querySelectorAll('button, input[type="submit"]')) {
            const rect = button.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0 && getComputedStyle(button).visibility !== 'hidden') return button;
        }
    }
    return null;
}'''


def google_page_kind(url: str, root: _Element) -> str:
    """What sort of page Google answered with: the page asked for (ok), the
    CAPTCHA it puts in front of browsers it thinks are bots (captcha) or the
    page asking for its use of cookies to be agreed to (consent).

    A page with results is the page asked for, even if it also asks for cookies
    to be agreed to, since what is wanted from it is there.
    """
    parsed = urlparse(url)
    if (parsed.hostname or '').startswith('consent.google.'):
        return 'consent'
    if parsed.path.startswith('/sorry/') or root.xpath('//form[@id="captcha-form"] | //div[@id="recaptcha"]'):
        return 'captcha'
    if not root.xpath('//div[@data-docid or @data-tbnid]') and root.xpath(GOOGLE_REJECT_XPATH):
        return 'consent'
    return 'ok'


def google_consent_cookie() -> dict[str, Any]:
    """The cookie Google sets when its use of cookies is rejected, so that
    browsers in places where it asks are not sent to the consent page. See
    https://github.com/benbusby/whoogle-search/pull/1054"""
    from base64 import standard_b64encode
    from datetime import date

    template = b'\x08\x01\x128\x08\x14\x12+boq_identityfrontenduiserver_20231107.05_p0\x1a\x05en-US \x03\x1a\x06\x08\x80\xf1\xca\xaa\x06'
    template = template.replace(b'20231107', date.today().strftime('%Y%m%d').encode('ascii'))  # ruff: ignore[call-date-today]
    value = standard_b64encode(template).decode('ascii').rstrip('=')
    return {'name': 'SOCS', 'value': value, 'domain': '.google.com', 'path': '/', 'secure': True}


class GoogleImagesHandler(SourceHandler):
    name = 'google_images'

    async def handle(self, action: str, args: Mapping[str, Any], deadline: Deadline) -> dict[str, Any]:
        try:
            match action:
                case 'search':
                    return await self.search(args, deadline)
        except Blocked as err:
            return error_result(err.kind, str(err))
        return await super().handle(action, args, deadline)

    async def ensure_consent_cookie(self) -> None:
        if not any(c.get('name') == 'SOCS' and str(c.get('domain') or '').endswith('google.com') for c in await self.browser.cookies()):
            await self.browser.set_cookies([google_consent_cookie()])

    async def search(self, args: Mapping[str, Any], deadline: Deadline) -> dict[str, Any]:
        """Load the image search results page at url, built by the source as
        it knows the search options, in the tab kept for searching Google and
        hand back its HTML."""
        url = str(args['url'])
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname != GOOGLE_SEARCH_HOST:
            raise ValueError(f'Not a Google search URL: {url}')
        page = await self.search_page(GOOGLE_SEARCH_HOST, deadline)
        referer = page.url if urlparse(page.url).hostname == GOOGLE_SEARCH_HOST else ''
        await self.ensure_consent_cookie()
        await page.open(url, wait='domcontentloaded', timeout=deadline.remaining(PAGE_TIMEOUT), referer=referer)
        html, kind = await self.read_page(page, url, deadline)
        for attempt in range(GOOGLE_MAX_CONSENTS):
            if kind != 'consent':
                break
            await self.reject_cookies(page, url, deadline)
            html, kind = await self.read_page(page, url, deadline)
        match kind:
            case 'captcha':
                raise Blocked(
                    'captcha',
                    'Google asked for a CAPTCHA to be solved, probably because too many searches were made. Wait for some time and try again.',
                )
            case 'consent':
                raise Blocked('consent', 'Google keeps asking for its use of cookies to be agreed to, even after they were rejected')
        return {'url': page.url, 'html': html}

    async def read_page(self, page: Page, url: str, deadline: Deadline) -> tuple[str, str]:
        """The HTML of the page Google answered with, once it has loaded, and
        what sort of page it is, see google_page_kind()."""
        try:
            elem = await page.wait_for_selector(GOOGLE_PAGE_LOADED, timeout=deadline.remaining(FIELD_TIMEOUT))
        except TimeoutExceeded:
            # No results, which is not an error
            debug(f'Google never showed any image results for: {url}')
        else:
            await elem.dispose()
        # The first search of a session is reloaded by Google once it has
        # checked for JavaScript, so the element can be from a page that is
        # still loading, whose image URLs are in scripts near its end
        await page.wait_for_load('domcontentloaded', timeout=deadline.remaining(PAGE_TIMEOUT))
        html = await page.html()
        return html, google_page_kind(page.url, parse_html(html))

    async def reject_cookies(self, page: Page, url: str, deadline: Deadline) -> None:
        """Click the button that rejects cookies on the page asking for them
        to be agreed to, which takes the browser on to the page asked for.

        Should rejecting them not navigate anywhere, as it need not when Google
        asks in a dialog over the page asked for, that page is loaded again,
        now that there is a cookie saying they were rejected.
        """
        debug('Rejecting cookies on the Google consent page')
        await self.settle(page, deadline)
        button: Element | None = await page.call(GOOGLE_REJECT_JS, by_value=False)
        if button is None:
            raise Blocked('consent', 'Google asked for its use of cookies to be agreed to, but the button to reject them could not be found')
        finished = page.navigation_finished()
        try:
            await button.click()
            event = await wait_for(finished, deadline.remaining(CONSENT_NAVIGATION_TIMEOUT), 'rejecting cookies to load a page')
        except TimeoutExceeded:
            debug('Rejecting cookies did not load a page, loading the search results again')
            await page.open(url, wait='domcontentloaded', timeout=deadline.remaining(PAGE_TIMEOUT))
            return
        finally:
            finished.cancel()
            await button.dispose()
        if event.method == 'Page.navigationAborted':
            raise Error(f'Loading the page was aborted: {event.params.get("errorText")}')
        await page.wait_for_load('domcontentloaded', timeout=deadline.remaining(PAGE_TIMEOUT))


# }}}

HANDLERS: tuple[type[SourceHandler], ...] = (AmazonHandler, GoogleImagesHandler)


class State:
    """Everything the worker process owns, created once, on the first request."""

    def __init__(self, browser: Browser, handlers: Iterable[type[SourceHandler]] = HANDLERS, max_detail_tabs: int = MAX_DETAIL_TABS) -> None:
        self.browser = browser
        self.tab_pool = TabPool(max_detail_tabs)
        self.handlers = {cls.name: cls(self) for cls in handlers}
        self.reaper: asyncio.Task[None] | None = None

    async def handle(self, request: Mapping[str, Any]) -> dict[str, Any]:
        name = str(request.get('source') or '')
        handler = self.handlers.get(name)
        if handler is None:
            raise KeyError(f'There is no camoufox handler for the metadata source: {name!r}')
        deadline = Deadline(float(request.get('deadline') or 0) or time.time() + DEFAULT_REQUEST_TIMEOUT)
        async with handler.queue:
            if deadline.remaining() <= 0:
                return error_result('timeout', f'Gave up waiting for earlier downloads from {name} to finish')
            handler.last_used = time.monotonic()
            try:
                async with asyncio.timeout(deadline.remaining()):
                    return await handler.handle(str(request.get('action') or ''), request.get('args') or {}, deadline)
            except TimeoutError:
                return error_result('timeout', f'Timed out downloading from {name}')
            finally:
                handler.last_used = time.monotonic()

    def start_reaper(self) -> None:
        self.reaper = asyncio.create_task(self.close_idle_tabs())

    async def close_idle_tabs(self) -> None:
        while True:
            await asyncio.sleep(IDLE_CHECK_INTERVAL)
            await self.close_idle_tabs_once()

    async def close_idle_tabs_once(self) -> None:
        for handler in self.handlers.values():
            if handler.is_idle(time.monotonic()):
                async with handler.queue:
                    # Check again as a request might have been let in first
                    if handler.search_tab_unused(time.monotonic()):
                        await handler.close_search_tab()

    def stop_reaper(self) -> None:
        reaper, self.reaper = self.reaper, None
        if reaper is not None:
            reaper.cancel()


state: State | None = None


async def impl_setup_browser(input_data: Mapping[str, Any]) -> None:
    global state
    from calibre.web.automate.browser import Browser, Warmup

    warmup = None
    if input_data.get('warmup', True):
        warmup = Warmup()
        debug(f'Warming up camoufox on: {", ".join(warmup.urls)}')
    install = None
    if (install_data := input_data.get('install')) is not None:
        install = Install(*install_data)
    browser = Browser(headless=bool(input_data.get('headless', True)), warmup=warmup, install=install)
    started = time.monotonic()
    await browser.launch()
    debug(f'Camoufox ready for metadata downloads in {time.monotonic() - started:.1f} seconds')
    state = State(browser, max_detail_tabs=int(input_data.get('max_detail_tabs') or MAX_DETAIL_TABS))
    state.start_reaper()


async def impl_handle_request(input_data: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
    assert state is not None
    if not request.get('source'):
        if request.get('action') == 'launch':
            # Only there to get the browser launched, which has been done by
            # the time any request is handled
            return {'module_version': module_version}
        raise KeyError(f'Unknown action for the camoufox metadata worker: {request.get("action")}')
    return await state.handle(request)


def impl_finalize(input_data: Mapping[str, Any]) -> None:
    global state
    current, state = state, None
    if current is not None:
        from calibre.web.automate.browser import close_browser_from_loop

        current.stop_reaper()
        close_browser_from_loop(current.browser)


# The entry points of the worker process. They hand off to the live version of
# this module, which is either the one installed with calibre or a newer one
# downloaded from the calibre website.

live: ModuleType | None = None


def live_module() -> ModuleType:
    global live
    if live is None:
        from calibre.live import Strategy, load_module

        live = load_module(WORKER_MODULE, strategy=Strategy.fast)
    return live


async def setup_browser(input_data: Mapping[str, Any]) -> None:
    from calibre.live import start_worker as start_live_updates

    # Checks for a newer version of this module, for use from the next session
    start_live_updates()
    await live_module().impl_setup_browser(input_data)


async def handle_request(input_data: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
    return await live_module().impl_handle_request(input_data, request)


def finalize(input_data: Mapping[str, Any]) -> None:
    live_module().impl_finalize(input_data)


# }}}


# Client side, runs in the process doing the metadata download {{{


class BrowserFailed(Exception):
    pass


def path_to_env(path: str) -> str:
    # The path of an abstract unix socket starts with a null byte, which an
    # environment variable cannot hold
    return '@' + path[1:] if path.startswith('\0') else path


def path_from_env(val: str) -> str:
    return '\0' + val[1:] if val.startswith('@') else val


class SessionWorker:
    """The worker process belonging to this process, started on first use.

    It exits when this process does, since that closes its stdin.
    """

    def __init__(self, input_data: dict[str, Any] | None = None) -> None:
        self.input_data = input_data or {}
        self.lock = Lock()
        self.path = ''
        self.close_worker: Callable[[], int] | None = None
        self.launch_requested = False

    def ensure_started(self) -> str:
        with self.lock:
            if not self.path:
                self.path, self.close_worker = start_worker(
                    f'{WORKER_MODULE}:handle_request', f'{WORKER_MODULE}:setup_browser', f'{WORKER_MODULE}:finalize', input_data=self.input_data
                )
                self.launch_requested = False
            return self.path

    def forget(self, path: str) -> None:
        """Forget a worker that cannot be connected to, so that the next
        request starts another one."""
        with self.lock:
            if self.path == path:
                self.path, self.close_worker = '', None

    def launch_in_background(self) -> None:
        """Get the browser launched and warmed up while there is nothing for
        it to do, so that it is ready by the time a source wants it."""
        path = self.ensure_started()
        with self.lock:
            if self.launch_requested:
                return
            self.launch_requested = True

        def launch() -> None:
            try:
                response = make_request(path, {'source': '', 'action': 'launch'})
            except OSError as err:
                debug(f'Could not connect to the camoufox metadata worker: {err}')
                self.forget(path)
            else:
                if response.exception:
                    debug(f'Launching camoufox for metadata downloads failed: {response.exception}')
                    with self.lock:
                        self.launch_requested = False

        Thread(target=launch, name='LaunchMetadataBrowser', daemon=True).start()

    def shutdown(self) -> None:
        with self.lock:
            close_worker, self.close_worker = self.close_worker, None
            self.path = ''
        if close_worker is not None:
            close_worker()


session_worker = SessionWorker()


def env_for_metadata_jobs() -> dict[str, str]:
    """The environment variables to give the processes that download
    metadata, so that they all use the browser belonging to this process.

    Empty if none of the metadata sources that are in use need the browser.
    Calling this also starts the browser launching in the background.
    """
    from calibre.customize.ui import metadata_plugins

    if not any(getattr(p, 'uses_camoufox_worker', False) and p.is_configured() for p in metadata_plugins(('identify', 'cover'))):
        return {}
    try:
        session_worker.launch_in_background()
    except Exception:
        # The jobs start a worker of their own when they need one, which is
        # slower but no reason not to download metadata at all
        import traceback

        debug('Failed to start the camoufox worker for metadata downloads:')
        traceback.print_exc()
        return {}
    return {ENV_VAR: path_to_env(session_worker.path)}


def run_in_browser(source: str, action: str, args: Mapping[str, Any], timeout: float = DEFAULT_REQUEST_TIMEOUT) -> dict[str, Any]:
    """Have the handler for source perform action in the shared browser.

    timeout includes the time spent waiting for earlier requests for the same
    source to be finished with. Raises :class:`BrowserFailed` if the worker
    cannot be reached or fails, as opposed to the website not having what was
    asked for, which is reported in the result.
    """
    request = {'source': source, 'action': action, 'args': dict(args), 'deadline': time.time() + timeout}
    path = path_from_env(os.environ.get(ENV_VAR, ''))
    if path:
        try:
            response = make_request(path, request)
        except OSError as err:
            raise BrowserFailed(f'Could not connect to the camoufox metadata worker: {err}') from err
    else:
        # A worker of our own that has died is replaced, once
        for attempt in range(2):
            path = session_worker.ensure_started()
            try:
                response = make_request(path, request)
                break
            except OSError as err:
                session_worker.forget(path)
                if attempt:
                    raise BrowserFailed(f'Could not connect to the camoufox metadata worker: {err}') from err
    if response.exception:
        raise BrowserFailed(f'The camoufox metadata worker failed: {response.exception}\n{response.traceback or ""}'.rstrip())
    return response.response


# }}}


def develop(args: Sequence[str] = ()) -> None:
    """Search Amazon for the query given on the command line, for testing this module by hand."""
    import sys

    args = list(args or sys.argv[1:])
    domain = 'com'
    if args and args[0].startswith('--domain='):
        domain = args.pop(0).partition('=')[2]
    site = {'uk': 'www.amazon.co.uk', 'jp': 'www.amazon.co.jp', 'br': 'www.amazon.com.br', 'au': 'www.amazon.com.au'}.get(domain, f'www.amazon.{domain}')
    started = time.monotonic()
    result = run_in_browser('amazon', 'search', {'site': site, 'domain': domain, 'query': ' '.join(args), 'department': 'stripbooks'})
    print(f'Finished in {time.monotonic() - started:.1f} seconds')
    if result.get('error'):
        print(result['kind'], result['error'])
    for d in result.get('details') or ():
        print(d['url'], d.get('error') or f'{len(d["html"])} characters of HTML')


if __name__ == '__main__':
    develop()
