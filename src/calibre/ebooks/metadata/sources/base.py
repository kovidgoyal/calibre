#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, threading

from calibre import browser, random_user_agent
from calibre.customize import Plugin
from calibre.utils.logging import ThreadSafeLog, FileStream
from calibre.utils.config import JSONConfig

msprefs = JSONConfig('metadata_sources.json')

def create_log(ostream=None):
    log = ThreadSafeLog(level=ThreadSafeLog.DEBUG)
    log.outputs = [FileStream(ostream)]
    return log

words = ("the", "a", "an", "of", "and")
prefix_pat = re.compile(r'^(%s)\s+'%("|".join(words)))
trailing_paren_pat = re.compile(r'\(.*\)$')
whitespace_pat = re.compile(r'\s+')

def cleanup_title(s):
    if not s:
        s = _('Unknown')
    s = s.strip().lower()
    s = prefix_pat.sub(' ', s)
    s = trailing_paren_pat.sub('', s)
    s = whitespace_pat.sub(' ', s)
    return s.strip()


class Source(Plugin):

    type = _('Metadata source')
    author = 'Kovid Goyal'

    supported_platforms = ['windows', 'osx', 'linux']

    capabilities = frozenset()

    touched_fields = frozenset()

    def __init__(self, *args, **kwargs):
        Plugin.__init__(self, *args, **kwargs)
        self._isbn_to_identifier_cache = {}
        self._identifier_to_cover_url_cache = {}
        self.cache_lock = threading.RLock()
        self._config_obj = None
        self._browser = None

    # Configuration {{{

    @property
    def prefs(self):
        if self._config_obj is None:
            self._config_obj = JSONConfig('metadata_sources/%s.json'%self.name)
        return self._config_obj
    # }}}

    # Browser {{{

    @property
    def browser(self):
        if self._browser is None:
            self._browser = browser(user_agent=random_user_agent())
        return self._browser

    # }}}

    # Utility functions {{{

    def cache_isbn_to_identifier(self, isbn, identifier):
        with self.cache_lock:
            self._isbn_to_identifier_cache[isbn] = identifier

    def cached_isbn_to_identifier(self, isbn):
        with self.cache_lock:
            return self._isbn_to_identifier_cache.get(isbn, None)

    def cache_identifier_to_cover_url(self, id_, url):
        with self.cache_lock:
            self._identifier_to_cover_url_cache[id_] = url

    def cached_identifier_to_cover_url(self, id_):
        with self.cache_lock:
            return self._identifier_to_cover_url_cache.get(id_, None)

    def get_author_tokens(self, authors, only_first_author=True):
        '''
        Take a list of authors and return a list of tokens useful for an
        AND search query. This function tries to return tokens in
        first name middle names last name order, by assuming that if a comma is
        in the author name, the name is in lastname, other names form.
        '''

        if authors:
            # Leave ' in there for Irish names
            pat = re.compile(r'[-,:;+!@#$%^&*(){}.`~"\s\[\]/]')
            if only_first_author:
                authors = authors[:1]
            for au in authors:
                parts = au.split()
                if ',' in au:
                    # au probably in ln, fn form
                    parts = parts[1:] + parts[:1]
                for tok in parts:
                    tok = pat.sub('', tok).strip()
                    if len(tok) > 2 and tok.lower() not in ('von', ):
                        yield tok


    def get_title_tokens(self, title):
        '''
        Take a title and return a list of tokens useful for an AND search query.
        Excludes connectives and punctuation.
        '''
        if title:
            pat = re.compile(r'''[-,:;+!@#$%^&*(){}.`~"'\s\[\]/]''')
            title = pat.sub(' ', title)
            tokens = title.split()
            for token in tokens:
                token = token.strip()
                if token and token.lower() not in ('a', 'and', 'the'):
                    yield token

    def split_jobs(self, jobs, num):
        'Split a list of jobs into at most num groups, as evenly as possible'
        groups = [[] for i in range(num)]
        jobs = list(jobs)
        while jobs:
            for gr in groups:
                try:
                    job = jobs.pop()
                except IndexError:
                    break
                gr.append(job)
        return [g for g in groups if g]

    def test_fields(self, mi):
        '''
        Return the first field from self.touched_fields that is null on the
        mi object
        '''
        for key in self.touched_fields:
            if key.startswith('identifier:'):
                key = key.partition(':')[-1]
                if not mi.has_identifier(key):
                    return 'identifier: ' + key
            elif mi.is_null(key):
                return key


    # }}}

    # Metadata API {{{

    def get_cached_cover_url(self, identifiers):
        '''
        Return cached cover URL for the book identified by
        the identifiers dict or Noneif no such URL exists
        '''
        return None

    def compare_identify_results(self, x, y, title=None, authors=None,
            identifiers={}):
        '''
        Method used to sort the results from a call to identify by relevance.
        Uses the actual query and various heuristics to rank results.
        Re-implement in your plugin if this generic algorithm is not suitable.
        Note that this method assumes x and y have a source_relevance
        attribute.

        one < two iff one is more relevant than two
        '''
        # First, guarantee that if the query specifies an ISBN, the result with
        # the same isbn is the most relevant
        def isbn_test(mi):
            return mi.isbn and mi.isbn == identifiers.get('isbn', None)

        def boolcmp(a, b):
            return -1 if a and not b else 1 if not a and b else 0

        x_has_isbn, y_has_isbn = isbn_test(x), isbn_test(y)
        result = boolcmp(x_has_isbn, y_has_isbn)
        if result != 0:
            return result

        # Now prefer results that have complete metadata over those that don't
        x_has_all_fields = self.test_fields(x) is None
        y_has_all_fields = self.test_fields(y) is None

        result = boolcmp(x_has_all_fields, y_has_all_fields)
        if result != 0:
            return result

        # Now prefer results whose title matches the search query
        if title:
            x_title = cleanup_title(x.title)
            y_title = cleanup_title(y.title)
            t = cleanup_title(title)
            x_has_title, y_has_title = x_title == t, y_title == t
            result = boolcmp(x_has_title, y_has_title)
            if result != 0:
                return result

        # Now prefer results with the longer comments, within 10%
        cx = len(x.comments.strip() if x.comments else '')
        cy = len(y.comments.strip() if y.comments else '')
        t = (cx + cy) / 20
        result = cy - cx
        if result != 0 and abs(cx - cy) > t:
            return result

        # Now prefer results with cached cover URLs
        x_has_cover = self.get_cached_cover_url(x.identifiers) is not None
        y_has_cover = self.get_cached_cover_url(y.identifiers) is not None
        result = boolcmp(x_has_cover, y_has_cover)
        if result != 0:
            return result

        # Now use the relevance reported by the remote search engine
        return x.source_relevance - y.source_relevance

    def identify(self, log, result_queue, abort, title=None, authors=None,
            identifiers={}, timeout=5):
        '''
        Identify a book by its title/author/isbn/etc.

        If identifiers(s) are specified and no match is found and this metadata
        source does not store all related identifiers (for example, all ISBNs
        of a book), this method should retry with just the title and author
        (assuming they were specified).

        If this metadata source also provides covers, the URL to the cover
        should be cached so that a subsequent call to the get covers API with
        the same ISBN/special identifier does not need to get the cover URL
        again. Use the caching API for this.

        Every Metadata object put into result_queue by this method must have a
        `source_relevance` attribute that is an integer indicating the order in
        which the results were returned by the metadata source for this query.
        This integer will be used by :meth:`compare_identify_results`. If the
        order is unimportant, set it to zero for every result.

        Make sure that any cover/isbn mapping information is cached before the
        Metadata object is put into result_queue.

        :param log: A log object, use it to output debugging information/errors
        :param result_queue: A result Queue, results should be put into it.
                            Each result is a Metadata object
        :param abort: If abort.is_set() returns True, abort further processing
                      and return as soon as possible
        :param title: The title of the book, can be None
        :param authors: A list of authors of the book, can be None
        :param identifiers: A dictionary of other identifiers, most commonly
                            {'isbn':'1234...'}
        :param timeout: Timeout in seconds, no network request should hang for
                        longer than timeout.
        :return: None if no errors occurred, otherwise a unicode representation
                 of the error suitable for showing to the user

        '''
        return None

    # }}}

