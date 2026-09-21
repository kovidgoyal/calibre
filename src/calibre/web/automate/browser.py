#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import asyncio
import random
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse

from calibre.web.automate.camoufox import Browser as CamoufoxBrowser
from calibre.web.automate.camoufox import Error, Page, debug

wikipedia_topics = (
    'Lists_of_deaths_by_year',
    'United_States',
    'India',
    'China',
    'United_Kingdom',
    'President',
    'Red',
    'Green',
    'Cyan',
    'Magenta',
)
subreddits = (
    'funny',
    'AskReddit',
    'gaming',
    'pics',
    'worldnews',
    'todayilearned',
    'Music',
    'movies',
    'science',
    'memes',
    'aww',
)
bbc_topics = (
    'news/world',
    'news',
    'sport',
    'business',
    'health',
)
fox_news_topics = (
    'us',
    'politics',
    'world',
    'opinion',
)

# A visit that is over in a few milliseconds is not what a person reading a
# page looks like, but neither is one that holds up the download for a minute
MIN_DWELL_TIME = 0.75  # seconds
MAX_DWELL_TIME = 2.5  # seconds
WARMUP_TIMEOUT = 30.0  # seconds, per site


class Warmup:
    """A handful of commonly browsed sites, visited before the real work starts.

    A browser profile whose very first request is for an obscure news article,
    with no cookies and an empty history, is itself a signal. Visiting a few
    popular sites first gives the profile the cookies, cache entries and
    history that an ordinary one has.

    :param forced_urls: always visited, in addition to the random selection
    :param min_num: the fewest of the built-in sites to visit
    :param max_num: the most of the built-in sites to visit
    :param excluded_domains: sites whose hostname ends with one of these are
        never visited, used to keep the warmup away from the site that is about
        to be downloaded from
    """

    def __init__(self, *forced_urls: str, min_num: int = 2, max_num: int = 3, excluded_domains: Iterable[str] = ()) -> None:
        # sample() rather than choices() as the latter picks with replacement,
        # which means the same page of a site can be visited twice
        foxes = tuple(f'https://www.foxnews.com/{x}' for x in random.sample(fox_news_topics, k=2))
        bbc = tuple(f'https://www.bbc.com/{x}' for x in random.sample(bbc_topics, k=2))
        wiki = tuple(f'https://en.wikipedia.org/wiki/{x}' for x in random.sample(wikipedia_topics, k=2))
        reddit = tuple(f'https://www.reddit.com/r/{x}' for x in random.sample(subreddits, k=2))
        urls = (
            (
                'https://www.amazon.com/gp/css/order-history?ref_=nav_orders_first',
                'https://x.com',
                'https://www.youtube.com',
            )
            + foxes
            + bbc
            + wiki
            + reddit
        )
        disallow = frozenset(excluded_domains)
        if disallow:

            def is_not_excluded(x: str) -> bool:
                p = urlparse(x)
                for q in disallow:
                    assert p.hostname is not None
                    if p.hostname.endswith(q):
                        return False
                return True

            urls = tuple(filter(is_not_excluded, urls))
        num = min(random.randint(min_num, max_num), len(urls))
        # dict.fromkeys() so that a forced URL that is also one of the built-in
        # sites is not visited twice
        self.urls = tuple(dict.fromkeys(random.sample(urls, k=num) + list(forced_urls)))

    async def visit(self, page: Page, url: str) -> None:
        """Load url and behave, briefly, like someone looking at it."""
        await page.open(url, wait='domcontentloaded', timeout=WARMUP_TIMEOUT)
        # Scrolling is what makes a visit look like reading rather than
        # fetching, and it also triggers the lazy loading that decides whether
        # a site thinks it has served a real viewer
        for _ in range(random.randint(1, 3)):
            await asyncio.sleep(random.uniform(MIN_DWELL_TIME, MAX_DWELL_TIME))
            await page.evaluate(f'window.scrollBy({{top: {random.randint(200, 900)}, behavior: "smooth"}})')
        await asyncio.sleep(random.uniform(MIN_DWELL_TIME, MAX_DWELL_TIME))

    async def __call__(self, br: CamoufoxBrowser) -> None:
        """Visit every URL in turn, in a tab that is discarded afterwards.

        A site that is down, slow or blocking us is not worth failing the
        download over, so every visit is allowed to fail on its own.
        """
        if not self.urls:
            return
        page = await br.new_page()
        try:
            for url in self.urls:
                try:
                    await self.visit(page, url)
                except (Error, TimeoutError) as err:
                    debug(f'Warming up on {url} failed: {err}')
        finally:
            await page.close()


class Browser(CamoufoxBrowser):
    """A camoufox browser that warms itself up before it is used for anything.

    Any other keyword argument is passed through to :class:`camoufox.Browser`.
    """

    def __init__(self, headless: bool = True, warmup: Warmup | None = None, **kw: Any) -> None:  # noqa: ANN401
        super().__init__(headless=headless, **kw)
        self.warmup = warmup

    async def launch(self) -> None:
        await super().launch()
        if self.warmup is not None:
            await self.warmup(self)
