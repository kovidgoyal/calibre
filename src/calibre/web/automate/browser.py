#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import random
from collections.abc import Iterable
from urllib.parse import urlparse

from camoufox.async_api import AsyncCamoufox  # type: ignore

from calibre.constants import ismacos, iswindows

wikipedia_topics = (
    'Lists_of_deaths_by_year', 'United_States', 'India', 'China', 'United_Kingdom', 'President', 'Red', 'Green', 'Cyan', 'Magenta'
)
subreddits = (
    'funny', 'AskReddit', 'gaming', 'pics', 'worldnews', 'todayilearned', 'Music', 'movies', 'science', 'memes', 'aww',
)
bbc_topics = (
    'news/world', 'news', 'sport', 'business', 'health',
)
fox_news_topics = (
    'us', 'politics', 'world', 'opinion',
)


class Warmup:

    def __init__(self, *forced_urls: str, min_num: int = 2, max_num: int = 3, excluded_domains: Iterable[str] = ()):
        foxes = tuple(f'https://www.foxnews.com/{x}' for x in random.choices(fox_news_topics, k=2))
        bbc = tuple(f'https://www.bbc.com/{x}' for x in random.choices(bbc_topics, k=2))
        wiki = tuple(f'https://en.wikipedia.org/wiki/{x}' for x in random.choices(wikipedia_topics, k=2))
        reddit = tuple(f'https://www.reddit.com/r/{x}' for x in random.choices(subreddits, k=2))
        urls = (
            'https://www.amazon.com/gp/css/order-history?ref_=nav_orders_first',
            'https://x.com',
            'https://www.youtube.com',
            ) + foxes + bbc + wiki + reddit
        disallow = frozenset(excluded_domains)
        if disallow:
            def is_not_excluded(x: str) -> bool:
                p = urlparse(x)
                for q in disallow:
                    if p.hostname.endswith(q):
                        return False
                return True
            urls = tuple(filter(is_not_excluded, urls))
        self.urls = tuple(random.sample(urls, k=random.randint(min_num, max_num))) + forced_urls

    def __call__(self, br: Browser) -> None:
        pass


class Browser(AsyncCamoufox):

    def __init__(self, headless: bool = True, warmup: Warmup | None = None):
        os = 'windows' if iswindows else ('macos' if ismacos else 'linux')
        super().__init__(headless=headless, os=os, humanize=True)
