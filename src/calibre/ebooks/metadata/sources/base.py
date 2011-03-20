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

    # }}}

    # Metadata API {{{

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

