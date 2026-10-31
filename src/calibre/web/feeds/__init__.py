#!/usr/bin/env python
# License: GPLv3 Copyright: 2008, Kovid Goyal <kovid at kovidgoyal.net>

"""
Contains the logic for parsing feeds.
"""

import copy
import re
import time
import traceback
from collections.abc import Callable, Iterable, Iterator
from typing import TYPE_CHECKING, TypedDict

from calibre import force_unicode, replace_entities, strftime
from calibre.utils.cleantext import clean_ascii_chars, clean_xml_chars
from calibre.utils.date import dt_factory, local_tz, utcnow
from calibre.utils.localization import _
from calibre.utils.logging import Log, default_log

if TYPE_CHECKING:
    from feedparser import FeedParserDict


class IndexArticle(TypedDict, total=False):
    "An article in the index returned by :meth:`BasicNewsRecipe.parse_index`"

    id: str
    title: str
    url: str | None
    date: str
    description: str
    content: str
    author: str
    timestamp: float


class Article:
    def __init__(
        self,
        id: str,
        title: str | bytes | None,
        url: str | None,
        author: str | None,
        summary: str | None,
        published: time.struct_time,
        content: str | None,
    ) -> None:
        from lxml import html

        self.downloaded = False
        self.id = id
        if not title or not isinstance(title, (str, bytes)):
            title = _('Unknown')
        title = force_unicode(title, 'utf-8')
        self._title = clean_xml_chars(title).strip()
        try:
            self._title = replace_entities(self._title)
        except Exception:
            pass
        self._title = clean_ascii_chars(self._title)
        self.url = url
        self.author = author
        self.toc_thumbnail = None
        self.internal_toc_entries = ()
        if author and not isinstance(author, str):
            author = author.decode('utf-8', 'replace')
        if summary and not isinstance(summary, str):
            summary = summary.decode('utf-8', 'replace')
        summary = clean_xml_chars(summary) if summary else summary
        self.summary = summary
        if summary and '<' in summary:
            try:
                s = html.fragment_fromstring(summary, create_parent=True)
                summary = html.tostring(s, method='text', encoding='unicode')
            except Exception:
                print('Failed to process article summary, deleting:')
                print(summary.encode('utf-8'))
                traceback.print_exc()
                summary = ''
        self.text_summary = clean_ascii_chars(summary)
        self.author = author
        self.content = content
        self.date = published
        self.utctime = dt_factory(self.date, assume_utc=True, as_utc=True)
        self.localtime = self.utctime.astimezone(local_tz)
        self._formatted_date = None

    @property
    def formatted_date(self) -> str:

        if self._formatted_date is None:
            self._formatted_date = strftime(' [%a, %d %b %H:%M]', t=self.localtime.timetuple())
        return self._formatted_date

    @formatted_date.setter
    def formatted_date(self, val: str) -> None:
        if isinstance(val, str):
            self._formatted_date = val

    @property
    def title(self) -> str:
        t = self._title
        if not isinstance(t, str) and hasattr(t, 'decode'):
            t = t.decode('utf-8', 'replace')
        return t

    @title.setter
    def title(self, val: str) -> None:
        self._title = clean_ascii_chars(val)

    def __repr__(self) -> str:
        return '''\
Title       : {}
URL         : {}
Author      : {}
Summary     : {}
Date        : {}
TOC thumb   : {}
Has content : {}
'''.format(
            self.title,
            self.url,
            self.author,
            self.summary[:20] + '...',  # ty: ignore[not-subscriptable]
            self.localtime.strftime('%a, %d %b, %Y %H:%M'),
            self.toc_thumbnail,
            bool(self.content),
        )

    def __str__(self) -> str:
        return repr(self)

    def is_same_as(self, other_article: object) -> bool:
        # if self.title != getattr(other_article, 'title', False):
        #     return False
        if self.url:
            return self.url == getattr(other_article, 'url', False)
        return self.content == getattr(other_article, 'content', False)


class Feed:
    def __init__(self, get_article_url: Callable[[FeedParserDict], str | None] = lambda item: item.get('link', None), log: Log = default_log) -> None:
        """
        Parse a feed into articles.
        """
        self.logger = log
        self.get_article_url = get_article_url

    def populate_from_feed(self, feed: FeedParserDict, title: str | None = None, oldest_article: float = 7, max_articles_per_feed: int = 100) -> None:
        entries = feed.entries
        feed = feed.feed
        self.title = feed.get('title', _('Unknown section')) if not title else title
        self.description = feed.get('description', '')
        image = feed.get('image', {})
        self.image_url = image.get('href', None)
        self.image_width = image.get('width', 88)
        self.image_height = image.get('height', 31)
        self.image_alt = image.get('title', '')

        self.articles = []
        self.id_counter = 0
        self.added_articles = []

        self.oldest_article = oldest_article

        for item in entries:
            if len(self.articles) >= max_articles_per_feed:
                break
            self.parse_article(item)

    def populate_from_preparsed_feed(
        self, title: str | None, articles: Iterable[IndexArticle], oldest_article: float = 7, max_articles_per_feed: int = 100
    ) -> None:
        self.title = str(title or _('Unknown feed'))
        self.description = ''
        self.image_url = None
        self.articles = []
        self.added_articles = []

        self.oldest_article = oldest_article
        self.id_counter = 0

        for item in articles:
            if len(self.articles) >= max_articles_per_feed:
                break
            self.id_counter += 1
            id = item.get('id', None)
            if not id:
                id = f'internal id#{self.id_counter}'
            if id in self.added_articles:
                return
            self.added_articles.append(id)
            published = time.gmtime(item.get('timestamp', time.time()))
            title = item.get('title', _('Untitled article'))
            link = item.get('url', None)
            description = item.get('description', '')
            content = item.get('content', '')
            author = item.get('author', '')
            article = Article(id, title, link, author, description, published, content)
            delta = utcnow() - article.utctime
            if delta.days * 24 * 3600 + delta.seconds <= 24 * 3600 * self.oldest_article:
                self.articles.append(article)
            else:
                t = strftime('%a, %d %b, %Y %H:%M', article.localtime.timetuple())
                self.logger.debug(f'Skipping article {title} ({t}) from feed {self.title} as it is too old.')
            d = item.get('date', '')
            article.formatted_date = d

    def parse_article(self, item: FeedParserDict) -> None:
        self.id_counter += 1
        id = item.get('id', None)
        if not id:
            id = f'internal id#{self.id_counter}'
        if id in self.added_articles:
            return
        published = None
        for date_field in ('date_parsed', 'published_parsed', 'updated_parsed'):
            published = item.get(date_field, None)
            if published is not None:
                break
        if not published:
            from dateutil.parser import parse

            for date_field in ('date', 'published', 'updated'):
                try:
                    published = parse(item[date_field]).timetuple()
                except Exception:
                    continue
                break
        if not published:
            published = time.gmtime()
        self.added_articles.append(id)

        title = item.get('title', _('Untitled article'))
        if title.startswith('<'):
            title = re.sub(r'<.+?>', '', title)
        try:
            link = self.get_article_url(item)
        except Exception:
            self.logger.warning(f'Failed to get link for {title}')
            self.logger.debug(traceback.format_exc())
            link = None

        description = item.get('summary', None)
        author = item.get('author', None)

        content = [i.value for i in item.get('content', []) if i.value]
        content = [i if isinstance(i, str) else i.decode('utf-8', 'replace') for i in content]
        content = '\n'.join(content)
        if not content.strip():
            content = None
        if not link and not content:
            return
        article = Article(id, title, link, author, description, published, content)
        delta = utcnow() - article.utctime
        if delta.days * 24 * 3600 + delta.seconds <= 24 * 3600 * self.oldest_article:
            self.articles.append(article)
        else:
            try:
                self.logger.debug(
                    'Skipping article {} ({}) from feed {} as it is too old.'.format(title, article.localtime.strftime('%a, %d %b, %Y %H:%M'), self.title)
                )
            except UnicodeDecodeError:
                if not isinstance(title, str):
                    title = title.decode('utf-8', 'replace')
                self.logger.debug(f'Skipping article {title} as it is too old')

    def reverse(self) -> None:
        self.articles.reverse()

    def __iter__(self) -> Iterator[Article]:
        return iter(self.articles)

    def __len__(self) -> int:
        return len(self.articles)

    def __repr__(self) -> str:
        res = ['_' * 20 + f'\n{art!r}' for art in self]

        return '\n' + '\n'.join(res) + '\n'

    def __str__(self) -> str:
        return repr(self)

    def has_embedded_content(self) -> bool:
        length = 0
        for a in self:
            if a.content or a.summary:
                length += max(len(a.content or ''), len(a.summary or ''))

        return length > 2000 * len(self)

    def has_article(self, article: Article) -> bool:
        return any(a.is_same_as(article) for a in self)

    def find(self, article: Article) -> int:
        for i, a in enumerate(self):
            if a.is_same_as(article):
                return i
        return -1

    def remove(self, article: Article) -> None:
        i = self.find(article)
        if i > -1:
            self.articles[i : i + 1] = []

    def remove_article(self, article: Article) -> None:
        try:
            self.articles.remove(article)
        except ValueError:
            pass


class FeedCollection(list):
    def __init__(self, feeds: Iterable[Feed]) -> None:
        list.__init__(self, [f for f in feeds if len(f.articles) > 0])
        found_articles = set()
        duplicates = set()

        def in_set(s: Iterable[Article], a: Article) -> Article | None:
            for x in s:
                if a.is_same_as(x):
                    return x
            return None

        print('#feeds', len(self))
        print(list(map(len, self)))
        for f in self:
            dups = []
            for a in f:
                first = in_set(found_articles, a)
                if first is not None:
                    dups.append(a)
                    duplicates.add((first, f))
                else:
                    found_articles.add(a)
            for x in dups:
                f.articles.remove(x)

        self.duplicates = duplicates
        print(len(duplicates))
        print(list(map(len, self)))
        # raise

    def find_article(self, article: Article) -> tuple[int, int] | None:
        for j, f in enumerate(self):
            for i, a in enumerate(f):
                if a is article:
                    return j, i

    def restore_duplicates(self) -> None:
        temp = []
        for article, feed in self.duplicates:
            art = copy.deepcopy(article)
            j, i = self.find_article(article)  # ty: ignore[not-iterable]
            art.url = f'../feed_{j}/article_{i}/index.html'
            temp.append((feed, art))
        for feed, art in temp:
            feed.articles.append(art)


def feed_from_xml(
    raw_xml: bytes,
    title: str | None = None,
    oldest_article: float = 7,
    max_articles_per_feed: int = 100,
    get_article_url: Callable[[FeedParserDict], str | None] = lambda item: item.get('link', None),
    log: Log = default_log,
) -> Feed:
    from feedparser import parse

    # Handle unclosed escaped entities. They trip up feedparser and HBR for one
    # generates them
    raw_xml = re.sub(rb'(&amp;#\d+)([^0-9;])', rb'\1;\2', raw_xml)
    feed = parse(raw_xml)
    pfeed = Feed(get_article_url=get_article_url, log=log)
    pfeed.populate_from_feed(feed, title=title, oldest_article=oldest_article, max_articles_per_feed=max_articles_per_feed)
    return pfeed


def feeds_from_index(
    index: Iterable[tuple[str, Iterable[IndexArticle]]], oldest_article: float = 7, max_articles_per_feed: int = 100, log: Log = default_log
) -> list[Feed]:
    """
    @param index: A parsed index as returned by L{BasicNewsRecipe.parse_index}.
    @return: A list of L{Feed} objects.
    @rtype: list
    """
    feeds = []
    for title, articles in index:
        pfeed = Feed(log=log)
        pfeed.populate_from_preparsed_feed(title, articles, oldest_article=oldest_article, max_articles_per_feed=max_articles_per_feed)
        feeds.append(pfeed)
    return feeds
