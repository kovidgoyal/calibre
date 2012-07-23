#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, threading
from future_builtins import map

from calibre import browser, random_user_agent
from calibre.customize import Plugin
from calibre.utils.config import JSONConfig
from calibre.utils.titlecase import titlecase
from calibre.utils.icu import capitalize, lower, upper
from calibre.ebooks.metadata import check_isbn

msprefs = JSONConfig('metadata_sources/global.json')
msprefs.defaults['txt_comments'] = False
msprefs.defaults['ignore_fields'] = []
msprefs.defaults['user_default_ignore_fields'] = []
msprefs.defaults['max_tags'] = 20
msprefs.defaults['wait_after_first_identify_result'] = 30 # seconds
msprefs.defaults['wait_after_first_cover_result'] = 60 # seconds
msprefs.defaults['swap_author_names'] = False
msprefs.defaults['fewer_tags'] = True

# Google covers are often poor quality (scans/errors) but they have high
# resolution, so they trump covers from better sources. So make sure they
# are only used if no other covers are found.
msprefs.defaults['cover_priorities'] = {'Google':2}

def create_log(ostream=None):
    from calibre.utils.logging import ThreadSafeLog, FileStream
    log = ThreadSafeLog(level=ThreadSafeLog.DEBUG)
    log.outputs = [FileStream(ostream)]
    return log

# Comparing Metadata objects for relevance {{{
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

class InternalMetadataCompareKeyGen(object):

    '''
    Generate a sort key for comparison of the relevance of Metadata objects,
    given a search query. This is used only to compare results from the same
    metadata source, not across different sources.

    The sort key ensures that an ascending order sort is a sort by order of
    decreasing relevance.

    The algorithm is:

        * Prefer results that have the same ISBN as specified in the query
        * Prefer results with a cached cover URL
        * Prefer results with all available fields filled in
        * Prefer results that are an exact title match to the query
        * Prefer results with longer comments (greater than 10% longer)
        * Use the relevance of the result as reported by the metadata source's search
           engine
    '''

    def __init__(self, mi, source_plugin, title, authors, identifiers):
        isbn = 1 if mi.isbn and mi.isbn == identifiers.get('isbn', None) else 2

        all_fields = 1 if source_plugin.test_fields(mi) is None else 2

        exact_title = 1 if title and \
                cleanup_title(title) == cleanup_title(mi.title) else 2

        has_cover = 2 if (not source_plugin.cached_cover_url_is_reliable or
                source_plugin.get_cached_cover_url(mi.identifiers) is None) else 1

        self.base = (isbn, has_cover, all_fields, exact_title)
        self.comments_len = len(mi.comments.strip() if mi.comments else '')
        self.extra = (getattr(mi, 'source_relevance', 0), )

    def __cmp__(self, other):
        result = cmp(self.base, other.base)
        if result == 0:
            # Now prefer results with the longer comments, within 10%
            cx, cy = self.comments_len, other.comments_len
            t = (cx + cy) / 20
            delta = cy - cx
            if abs(delta) > t:
                result = delta
            else:
                result = cmp(self.extra, other.extra)
        return result

# }}}

def get_cached_cover_urls(mi):
    from calibre.customize.ui import metadata_plugins
    plugins = list(metadata_plugins(['identify']))
    for p in plugins:
        url = p.get_cached_cover_url(mi.identifiers)
        if url:
            yield (p, url)

def dump_caches():
    from calibre.customize.ui import metadata_plugins
    return {p.name:p.dump_caches() for p in metadata_plugins(['identify'])}

def load_caches(dump):
    from calibre.customize.ui import metadata_plugins
    plugins = list(metadata_plugins(['identify']))
    for p in plugins:
        cache = dump.get(p.name, None)
        if cache:
            p.load_caches(cache)

def cap_author_token(token):
    lt = lower(token)
    if lt in ('von', 'de', 'el', 'van', 'le'):
        return lt
    # no digits no spez. characters
    if re.match(r'([^\d\W]\.){2,}$', lt, re.UNICODE) is not None:
        # Normalize tokens of the form J.K. to J. K.
        parts = token.split('.')
        return '. '.join(map(capitalize, parts)).strip()
    scots_name = None
    for x in ('mc', 'mac'):
        if (token.lower().startswith(x) and len(token) > len(x) and
                (
                    token[len(x)] == upper(token[len(x)]) or
                    lt == token
                )):
            scots_name = len(x)
            break
    ans = capitalize(token)
    if scots_name is not None:
        ans = ans[:scots_name] + upper(ans[scots_name]) + ans[scots_name+1:]
    for x in ('-', "'"):
        idx = ans.find(x)
        if idx > -1 and len(ans) > idx+2:
            ans = ans[:idx+1] + upper(ans[idx+1]) + ans[idx+2:]
    return ans

def fixauthors(authors):
    if not authors:
        return authors
    ans = []
    for x in authors:
        ans.append(' '.join(map(cap_author_token, x.split())))
    return ans

def fixcase(x):
    if x:
        x = titlecase(x)
    return x

class Option(object):
    __slots__ = ['type', 'default', 'label', 'desc', 'name', 'choices']

    def __init__(self, name, type_, default, label, desc, choices=None):
        '''
        :param name: The name of this option. Must be a valid python identifier
        :param type_: The type of this option, one of ('number', 'string',
                        'bool', 'choices')
        :param default: The default value for this option
        :param label: A short (few words) description of this option
        :param desc: A longer description of this option
        :param choices: A dict of possible values, used only if type='choices'.
        dict is of the form {key:human readable label, ...}
        '''
        self.name, self.type, self.default, self.label, self.desc = (name,
                type_, default, label, desc)
        if choices and not isinstance(choices, dict):
            choices = dict([(x, x) for x in choices])
        self.choices = choices

class Source(Plugin):

    type = _('Metadata source')
    author = 'Kovid Goyal'

    supported_platforms = ['windows', 'osx', 'linux']

    #: Set of capabilities supported by this plugin.
    #: Useful capabilities are: 'identify', 'cover'
    capabilities = frozenset()

    #: List of metadata fields that can potentially be download by this plugin
    #: during the identify phase
    touched_fields = frozenset()

    #: Set this to True if your plugin return HTML formatted comments
    has_html_comments = False

    #: Setting this to True means that the browser object will add
    #: Accept-Encoding: gzip to all requests. This can speedup downloads
    #: but make sure that the source actually supports gzip transfer encoding
    #: correctly first
    supports_gzip_transfer_encoding = False

    #: Cached cover URLs can sometimes be unreliable (i.e. the download could
    #: fail or the returned image could be bogus. If that is often the case
    #: with this source set to False
    cached_cover_url_is_reliable = True

    #: A list of :class:`Option` objects. They will be used to automatically
    #: construct the configuration widget for this plugin
    options = ()

    #: A string that is displayed at the top of the config widget for this
    #: plugin
    config_help_message = None


    def __init__(self, *args, **kwargs):
        Plugin.__init__(self, *args, **kwargs)
        self.running_a_test = False # Set to True when using identify_test()
        self._isbn_to_identifier_cache = {}
        self._identifier_to_cover_url_cache = {}
        self.cache_lock = threading.RLock()
        self._config_obj = None
        self._browser = None
        self.prefs.defaults['ignore_fields'] = []
        for opt in self.options:
            self.prefs.defaults[opt.name] = opt.default

    # Configuration {{{

    def is_configured(self):
        '''
        Return False if your plugin needs to be configured before it can be
        used. For example, it might need a username/password/API key.
        '''
        return True

    def is_customizable(self):
        return True

    def customization_help(self):
        return 'This plugin can only be customized using the GUI'

    def config_widget(self):
        from calibre.gui2.metadata.config import ConfigWidget
        return ConfigWidget(self)

    def save_settings(self, config_widget):
        config_widget.commit()

    @property
    def prefs(self):
        if self._config_obj is None:
            self._config_obj = JSONConfig('metadata_sources/%s.json'%self.name)
        return self._config_obj
    # }}}

    # Browser {{{

    @property
    def user_agent(self):
        # Pass in an index to random_user_agent() to test with a particular
        # user agent
        return random_user_agent()

    @property
    def browser(self):
        if self._browser is None:
            self._browser = browser(user_agent=self.user_agent)
            if self.supports_gzip_transfer_encoding:
                self._browser.set_handle_gzip(True)
        return self._browser.clone_browser()

    # }}}

    # Caching {{{

    def get_related_isbns(self, id_):
        with self.cache_lock:
            for isbn, q in self._isbn_to_identifier_cache.iteritems():
                if q == id_:
                    yield isbn

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

    def dump_caches(self):
        with self.cache_lock:
            return {'isbn_to_identifier':self._isbn_to_identifier_cache.copy(),
                    'identifier_to_cover':self._identifier_to_cover_url_cache.copy()}

    def load_caches(self, dump):
        with self.cache_lock:
            self._isbn_to_identifier_cache.update(dump['isbn_to_identifier'])
            self._identifier_to_cover_url_cache.update(dump['identifier_to_cover'])

    # }}}

    # Utility functions {{{

    def get_author_tokens(self, authors, only_first_author=True):
        '''
        Take a list of authors and return a list of tokens useful for an
        AND search query. This function tries to return tokens in
        first name middle names last name order, by assuming that if a comma is
        in the author name, the name is in lastname, other names form.
        '''

        if authors:
            # Leave ' in there for Irish names
            remove_pat = re.compile(r'[!@#$%^&*(){}`~"\s\[\]/]')
            replace_pat = re.compile(r'[-+.:;,]')
            if only_first_author:
                authors = authors[:1]
            for au in authors:
                has_comma = ',' in au
                au = replace_pat.sub(' ', au)
                parts = au.split()
                if has_comma:
                    # au probably in ln, fn form
                    parts = parts[1:] + parts[:1]
                for tok in parts:
                    tok = remove_pat.sub('', tok).strip()
                    if len(tok) > 2 and tok.lower() not in ('von', 'van',
                            _('Unknown').lower()):
                        yield tok

    def get_title_tokens(self, title, strip_joiners=True, strip_subtitle=False):
        '''
        Take a title and return a list of tokens useful for an AND search query.
        Excludes connectives(optionally) and punctuation.
        '''
        if title:
            # strip sub-titles
            if strip_subtitle:
                subtitle = re.compile(r'([\(\[\{].*?[\)\]\}]|[/:\\].*$)')
                if len(subtitle.sub('', title)) > 1:
                    title = subtitle.sub('', title)

            title_patterns = [(re.compile(pat, re.IGNORECASE), repl) for pat, repl in
            [
                # Remove things like: (2010) (Omnibus) etc.
                (r'(?i)[({\[](\d{4}|omnibus|anthology|hardcover|audiobook|audio\scd|paperback|turtleback|mass\s*market|edition|ed\.)[\])}]', ''),
                # Remove any strings that contain the substring edition inside
                # parentheses
                (r'(?i)[({\[].*?(edition|ed.).*?[\]})]', ''),
                # Remove commas used a separators in numbers
                (r'(\d+),(\d+)', r'\1\2'),
                # Remove hyphens only if they have whitespace before them
                (r'(\s-)', ' '),
                # Remove single quotes not followed by 's'
                (r"'(?!s)", ''),
                # Replace other special chars with a space
                (r'''[:,;+!@$%^&*(){}.`~"\s\[\]/]''', ' '),
            ]]

            for pat, repl in title_patterns:
                title = pat.sub(repl, title)

            tokens = title.split()
            for token in tokens:
                token = token.strip()
                if token and (not strip_joiners or token.lower() not in ('a',
                    'and', 'the', '&')):
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

    def clean_downloaded_metadata(self, mi):
        '''
        Call this method in your plugin's identify method to normalize metadata
        before putting the Metadata object into result_queue. You can of
        course, use a custom algorithm suited to your metadata source.
        '''
        if mi.title:
            mi.title = fixcase(mi.title)
        mi.authors = fixauthors(mi.authors)
        mi.tags = list(map(fixcase, mi.tags))
        mi.isbn = check_isbn(mi.isbn)

    # }}}

    # Metadata API {{{

    def get_book_url(self, identifiers):
        '''
        Return a 3-tuple or None. The 3-tuple is of the form:
        (identifier_type, identifier_value, URL).
        The URL is the URL for the book identified by identifiers at this
        source. identifier_type, identifier_value specify the identifier
        corresponding to the URL.
        This URL must be browseable to by a human using a browser. It is meant
        to provide a clickable link for the user to easily visit the books page
        at this source.
        If no URL is found, return None. This method must be quick, and
        consistent, so only implement it if it is possible to construct the URL
        from a known scheme given identifiers.
        '''
        return None

    def get_book_url_name(self, idtype, idval, url):
        '''
        Return a human readable name from the return value of get_book_url().
        '''
        return self.name

    def get_cached_cover_url(self, identifiers):
        '''
        Return cached cover URL for the book identified by
        the identifiers dict or None if no such URL exists.

        Note that this method must only return validated URLs, i.e. not URLS
        that could result in a generic cover image or a not found error.
        '''
        return None

    def identify_results_keygen(self, title=None, authors=None,
            identifiers={}):
        '''
        Return a function that is used to generate a key that can sort Metadata
        objects by their relevance given a search query (title, authors,
        identifiers).

        These keys are used to sort the results of a call to :meth:`identify`.

        For details on the default algorithm see
        :class:`InternalMetadataCompareKeyGen`. Re-implement this function in
        your plugin if the default algorithm is not suitable.
        '''
        def keygen(mi):
            return InternalMetadataCompareKeyGen(mi, self, title, authors,
                identifiers)
        return keygen

    def identify(self, log, result_queue, abort, title=None, authors=None,
            identifiers={}, timeout=30):
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

    def download_cover(self, log, result_queue, abort,
            title=None, authors=None, identifiers={}, timeout=30):
        '''
        Download a cover and put it into result_queue. The parameters all have
        the same meaning as for :meth:`identify`. Put (self, cover_data) into
        result_queue.

        This method should use cached cover URLs for efficiency whenever
        possible. When cached data is not present, most plugins simply call
        identify and use its results.
        '''
        pass

    # }}}

