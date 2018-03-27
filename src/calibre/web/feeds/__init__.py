#!/usr/bin/env  python2

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Contains the logic for parsing feeds.
'''
import time, traceback, copy, re

from calibre.utils.logging import default_log
from calibre import entity_to_unicode, strftime, force_unicode
from calibre.utils.date import dt_factory, utcnow, local_tz
from calibre.utils.cleantext import clean_ascii_chars, clean_xml_chars


class Article(object):

    def __init__(self, id, title, url, author, summary, published, content):
        from lxml import html
        self.downloaded = False
        self.id = id
        if not title or not isinstance(title, basestring):
            title = _('Unknown')
        title = force_unicode(title, 'utf-8')
        self._title = clean_xml_chars(title).strip()
        try:
            self._title = re.sub(r'&(\S+?);',
                entity_to_unicode, self._title)
        except:
            pass
        self._title = clean_ascii_chars(self._title)
        self.url = url
        self.author = author
        self.toc_thumbnail = None
        if author and not isinstance(author, unicode):
            author = author.decode('utf-8', 'replace')
        if summary and not isinstance(summary, unicode):
            summary = summary.decode('utf-8', 'replace')
        summary = clean_xml_chars(summary) if summary else summary
        self.summary = summary
        if summary and '<' in summary:
            try:
                s = html.fragment_fromstring(summary, create_parent=True)
                summary = html.tostring(s, method='text', encoding=unicode)
            except:
                print 'Failed to process article summary, deleting:'
                print summary.encode('utf-8')
                traceback.print_exc()
                summary = u''
        self.text_summary = clean_ascii_chars(summary)
        self.author = author
        self.content = content
        self.date = published
        self.utctime = dt_factory(self.date, assume_utc=True, as_utc=True)
        self.localtime = self.utctime.astimezone(local_tz)
        self._formatted_date = None

    @dynamic_property
    def formatted_date(self):

        def fget(self):
            if self._formatted_date is None:
                self._formatted_date = strftime(" [%a, %d %b %H:%M]",
                        t=self.localtime.timetuple())
            return self._formatted_date

        def fset(self, val):
            if isinstance(val, unicode):
                self._formatted_date = val

        return property(fget=fget, fset=fset)

    @dynamic_property
    def title(self):
        def fget(self):
            t = self._title
            if not isinstance(t, unicode) and hasattr(t, 'decode'):
                t = t.decode('utf-8', 'replace')
            return t

        def fset(self, val):
            self._title = clean_ascii_chars(val)
        return property(fget=fget, fset=fset)

    def __repr__(self):
        return \
(u'''\
Title       : %s
URL         : %s
Author      : %s
Summary     : %s
Date        : %s
TOC thumb   : %s
Has content : %s
'''%(self.title, self.url, self.author, self.summary[:20]+'...',
     self.localtime.strftime('%a, %d %b, %Y %H:%M'), self.toc_thumbnail,
     bool(self.content))).encode('utf-8')

    def __str__(self):
        return repr(self)

    def is_same_as(self, other_article):
        # if self.title != getattr(other_article, 'title', False):
        #    return False
        if self.url:
            return self.url == getattr(other_article, 'url', False)
        return self.content == getattr(other_article, 'content', False)


class Feed(object):

    def __init__(self, get_article_url=lambda item: item.get('link', None),
            log=default_log):
        '''
        Parse a feed into articles.
        '''
        self.logger = log
        self.get_article_url = get_article_url

    def populate_from_feed(self, feed, title=None, oldest_article=7,
                           max_articles_per_feed=100):
        entries = feed.entries
        feed = feed.feed
        self.title        = feed.get('title', _('Unknown section')) if not title else title
        self.description  = feed.get('description', '')
        image             = feed.get('image', {})
        self.image_url    = image.get('href', None)
        self.image_width  = image.get('width', 88)
        self.image_height = image.get('height', 31)
        self.image_alt    = image.get('title', '')

        self.articles = []
        self.id_counter = 0
        self.added_articles = []

        self.oldest_article = oldest_article

        for item in entries:
            if len(self.articles) >= max_articles_per_feed:
                break
            self.parse_article(item)

    def populate_from_preparsed_feed(self, title, articles, oldest_article=7,
                           max_articles_per_feed=100):
        self.title      = unicode(title if title else _('Unknown feed'))
        self.description = ''
        self.image_url  = None
        self.articles   = []
        self.added_articles = []

        self.oldest_article = oldest_article
        self.id_counter = 0

        for item in articles:
            if len(self.articles) >= max_articles_per_feed:
                break
            self.id_counter += 1
            id = item.get('id', None)
            if not id:
                id = 'internal id#%s'%self.id_counter
            if id in self.added_articles:
                return
            self.added_articles.append(id)
            published   = time.gmtime(item.get('timestamp', time.time()))
            title       = item.get('title', _('Untitled article'))
            link        = item.get('url', None)
            description = item.get('description', '')
            content     = item.get('content', '')
            author      = item.get('author', '')
            article = Article(id, title, link, author, description, published, content)
            delta = utcnow() - article.utctime
            if delta.days*24*3600 + delta.seconds <= 24*3600*self.oldest_article:
                self.articles.append(article)
            else:
                t = strftime(u'%a, %d %b, %Y %H:%M', article.localtime.timetuple())
                self.logger.debug(u'Skipping article %s (%s) from feed %s as it is too old.'%
                        (title, t, self.title))
            d = item.get('date', '')
            article.formatted_date = d

    def parse_article(self, item):
        self.id_counter += 1
        id = item.get('id', None)
        if not id:
            id = 'internal id#%s'%self.id_counter
        if id in self.added_articles:
            return
        published = None
        for date_field in ('date_parsed', 'published_parsed',
                           'updated_parsed'):
            published = item.get(date_field, None)
            if published is not None:
                break
        if not published:
            published = time.gmtime()
        self.added_articles.append(id)

        title = item.get('title', _('Untitled article'))
        try:
            link  = self.get_article_url(item)
        except:
            self.logger.warning('Failed to get link for %s'%title)
            self.logger.debug(traceback.format_exc())
            link = None

        description = item.get('summary', None)
        author = item.get('author', None)

        content = [i.value for i in item.get('content', []) if i.value]
        content = [i if isinstance(i, unicode) else i.decode('utf-8', 'replace')
                for i in content]
        content = u'\n'.join(content)
        if not content.strip():
            content = None
        if not link and not content:
            return
        article = Article(id, title, link, author, description, published, content)
        delta = utcnow() - article.utctime
        if delta.days*24*3600 + delta.seconds <= 24*3600*self.oldest_article:
            self.articles.append(article)
        else:
            try:
                self.logger.debug('Skipping article %s (%s) from feed %s as it is too old.'%
                                  (title, article.localtime.strftime('%a, %d %b, %Y %H:%M'), self.title))
            except UnicodeDecodeError:
                if not isinstance(title, unicode):
                    title = title.decode('utf-8', 'replace')
                self.logger.debug('Skipping article %s as it is too old'%title)

    def reverse(self):
        self.articles.reverse()

    def __iter__(self):
        return iter(self.articles)

    def __len__(self):
        return len(self.articles)

    def __repr__(self):
        res = [('%20s\n'%'').replace(' ', '_')+repr(art) for art in self]

        return '\n'+'\n'.join(res)+'\n'

    def __str__(self):
        return repr(self)

    def __bool__(self):
        for article in self:
            if getattr(article, 'downloaded', False):
                return True
        return False

    def has_embedded_content(self):
        length = 0
        for a in self:
            if a.content or a.summary:
                length += max(len(a.content if a.content else ''),
                              len(a.summary if a.summary else ''))

        return length > 2000 * len(self)

    def has_article(self, article):
        for a in self:
            if a.is_same_as(article):
                return True
        return False

    def find(self, article):
        for i, a in enumerate(self):
            if a.is_same_as(article):
                return i
        return -1

    def remove(self, article):
        i = self.index(article)
        if i > -1:
            self.articles[i:i+1] = []

    def remove_article(self, article):
        try:
            self.articles.remove(article)
        except ValueError:
            pass


class FeedCollection(list):

    def __init__(self, feeds):
        list.__init__(self, [f for f in feeds if len(f.articles) > 0])
        found_articles = set([])
        duplicates = set([])

        def in_set(s, a):
            for x in s:
                if a.is_same_as(x):
                    return x
            return None

        print '#feeds', len(self)
        print map(len, self)
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
        print len(duplicates)
        print map(len, self)
        # raise

    def find_article(self, article):
        for j, f in enumerate(self):
            for i, a in enumerate(f):
                if a is article:
                    return (j, i)

    def restore_duplicates(self):
        temp = []
        for article, feed in self.duplicates:
            art = copy.deepcopy(article)
            j, i = self.find_article(article)
            art.url = '../feed_%d/article_%d/index.html'%(j, i)
            temp.append((feed, art))
        for feed, art in temp:
            feed.articles.append(art)


def feed_from_xml(raw_xml, title=None, oldest_article=7,
                  max_articles_per_feed=100,
                  get_article_url=lambda item: item.get('link', None),
                  log=default_log):
    from calibre.web.feeds.feedparser import parse
    # Handle unclosed escaped entities. They trip up feedparser and HBR for one
    # generates them
    raw_xml = re.sub(r'(&amp;#\d+)([^0-9;])', r'\1;\2', raw_xml)
    feed = parse(raw_xml)
    pfeed = Feed(get_article_url=get_article_url, log=log)
    pfeed.populate_from_feed(feed, title=title,
                            oldest_article=oldest_article,
                            max_articles_per_feed=max_articles_per_feed)
    return pfeed


def feeds_from_index(index, oldest_article=7, max_articles_per_feed=100,
        log=default_log):
    '''
    @param index: A parsed index as returned by L{BasicNewsRecipe.parse_index}.
    @return: A list of L{Feed} objects.
    @rtype: list
    '''
    feeds = []
    for title, articles in index:
        pfeed = Feed(log=log)
        pfeed.populate_from_preparsed_feed(title, articles, oldest_article=oldest_article,
                                       max_articles_per_feed=max_articles_per_feed)
        feeds.append(pfeed)
    return feeds
