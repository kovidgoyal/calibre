from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import traceback, sys, textwrap, re
from threading import Thread

from calibre import prints
from calibre.utils.config import OptionParser
from calibre.utils.logging import default_log
from calibre.utils.titlecase import titlecase
from calibre.customize import Plugin
from calibre.ebooks.metadata.covers import check_for_cover
from calibre.utils.html2text import html2text

metadata_config = None

class MetadataSource(Plugin): # {{{
    '''
    Represents a source to query for metadata. Subclasses must implement
    at least the fetch method.

    When :meth:`fetch` is called, the `self` object will have the following
    useful attributes (each of which may be None)::

        title, book_author, publisher, isbn, log, verbose and extra

    Use these attributes to construct the search query. extra is reserved for
    future use.

    The fetch method must store the results in `self.results` as a list of
    :class:`Metadata` objects. If there is an error, it should be stored
    in `self.exception` and `self.tb` (for the traceback).
    '''

    author = 'Kovid Goyal'

    supported_platforms = ['windows', 'osx', 'linux']

    #: The type of metadata fetched. 'basic' means basic metadata like
    #: title/author/isbn/etc. 'social' means social metadata like
    #: tags/rating/reviews/etc.
    metadata_type = 'basic'

    #: If not None, the customization dialog will allow for string
    #: based customization as well the default customization. The
    #: string customization will be saved in the site_customization
    #: member.
    string_customization_help = None

    #: Set this to true if your plugin returns HTML markup in comments.
    #: Then if the user disables HTML, calibre will automagically convert
    #: the HTML to Markdown.
    has_html_comments = False

    type = _('Metadata download')

    def __call__(self, title, author, publisher, isbn, verbose, log=None,
            extra=None):
        self.worker = Thread(target=self._fetch)
        self.worker.daemon = True
        self.title = title
        self.verbose = verbose
        self.book_author = author
        self.publisher = publisher
        self.isbn = isbn
        self.log = log if log is not None else default_log
        self.extra = extra
        self.exception, self.tb, self.results = None, None, []
        self.worker.start()

    def _fetch(self):
        try:
            self.fetch()
            if self.results:
                c = self.config_store().get(self.name, {})
                res = self.results
                if hasattr(res, 'authors'):
                    res = [res]
                for mi in res:
                    if not c.get('rating', True):
                        mi.rating = None
                    if not c.get('comments', True):
                        mi.comments = None
                    if not c.get('tags', True):
                        mi.tags = []
                    if self.has_html_comments and mi.comments and \
                            c.get('textcomments', False):
                        try:
                            mi.comments = html2text(mi.comments)
                        except:
                            traceback.print_exc()
                            mi.comments = None

        except Exception, e:
            self.exception = e
            self.tb = traceback.format_exc()

    def fetch(self):
        '''
        All the actual work is done here.
        '''
        raise NotImplementedError

    def join(self):
        return self.worker.join()

    def is_customizable(self):
        return True

    def config_store(self):
        global metadata_config
        if metadata_config is None:
            from calibre.utils.config import XMLConfig
            metadata_config = XMLConfig('plugins/metadata_download')
        return metadata_config

    def config_widget(self):
        from PyQt4.Qt import QWidget, QVBoxLayout, QLabel, Qt, QLineEdit, \
            QCheckBox
        from calibre.customize.ui import config
        w = QWidget()
        w._layout = QVBoxLayout(w)
        w.setLayout(w._layout)
        if self.string_customization_help is not None:
            w._sc_label = QLabel(self.string_customization_help, w)
            w._layout.addWidget(w._sc_label)
            customization = config['plugin_customization']
            def_sc = customization.get(self.name, '')
            if not def_sc:
                def_sc = ''
            w._sc = QLineEdit(def_sc, w)
            w._layout.addWidget(w._sc)
            w._sc_label.setWordWrap(True)
            w._sc_label.setTextInteractionFlags(Qt.LinksAccessibleByMouse
                    | Qt.LinksAccessibleByKeyboard)
            w._sc_label.setOpenExternalLinks(True)
        c = self.config_store()
        c = c.get(self.name, {})
        for x, l in {'rating':_('ratings'), 'tags':_('tags'),
                'comments':_('description/reviews')}.items():
            cb = QCheckBox(_('Download %s from %s')%(l,
                self.name))
            setattr(w, '_'+x, cb)
            cb.setChecked(c.get(x, True))
            w._layout.addWidget(cb)
        
        if self.has_html_comments:
            cb = QCheckBox(_('Convert comments downloaded from %s to plain text')%(self.name))
            setattr(w, '_textcomments', cb)
            cb.setChecked(c.get('textcomments', False))
            w._layout.addWidget(cb)

        return w

    def save_settings(self, w):
        dl_settings = {}
        for x in ('rating', 'tags', 'comments'):
            dl_settings[x] = getattr(w, '_'+x).isChecked()
        if self.has_html_comments:
            dl_settings['textcomments'] = getattr(w, '_textcomments').isChecked()
        c = self.config_store()
        c.set(self.name, dl_settings)
        if hasattr(w, '_sc'):
            sc = unicode(w._sc.text()).strip()
            from calibre.customize.ui import customize_plugin
            customize_plugin(self, sc)

    def customization_help(self):
        return 'This plugin can only be customized using the GUI'

    # }}}

# class GoogleBooks(MetadataSource): # {{{

    # name = 'Google Books'
    # description = _('Downloads metadata from Google Books')

    # def fetch(self):
        # from calibre.ebooks.metadata.google_books import search
        # try:
            # self.results = search(self.title, self.book_author, self.publisher,
                                  # self.isbn, max_results=10,
                                  # verbose=self.verbose)
        # except Exception, e:
            # self.exception = e
            # self.tb = traceback.format_exc()

    # }}}

class ISBNDB(MetadataSource): # {{{

    name = 'IsbnDB'
    description = _('Downloads metadata from isbndb.com')

    def fetch(self):
        if not self.site_customization:
            return
        from calibre.ebooks.metadata.isbndb import option_parser, create_books
        args = ['isbndb']
        if self.isbn:
            args.extend(['--isbn', self.isbn])
        else:
            if self.title:
                args.extend(['--title', self.title])
            if self.book_author:
                args.extend(['--author', self.book_author])
            if self.publisher:
                args.extend(['--publisher', self.publisher])
        if self.verbose:
            args.extend(['--verbose'])
        args.append(self.site_customization) # IsbnDb key
        try:
            opts, args = option_parser().parse_args(args)
            self.results = create_books(opts, args)
        except Exception, e:
            self.exception = e
            self.tb = traceback.format_exc()

    @property
    def string_customization_help(self):
        ans = _('To use isbndb.com you must sign up for a %sfree account%s '
                'and enter your access key below.')
        return '<p>'+ans%('<a href="http://www.isbndb.com">', '</a>')

    # }}}

# class Amazon(MetadataSource): # {{{

    # name = 'Amazon'
    # metadata_type = 'social'
    # description = _('Downloads social metadata from amazon.com')

    # has_html_comments = True

    # def fetch(self):
        # if not self.isbn:
            # return
        # from calibre.ebooks.metadata.amazon import get_social_metadata
        # try:
            # self.results = get_social_metadata(self.title, self.book_author,
                    # self.publisher, self.isbn)
        # except Exception, e:
            # self.exception = e
            # self.tb = traceback.format_exc()

    # }}}

class LibraryThing(MetadataSource): # {{{

    name = 'LibraryThing'
    metadata_type = 'social'
    description = _('Downloads series/tags/rating information from librarything.com')

    def fetch(self):
        if not self.isbn:
            return
        from calibre.ebooks.metadata.library_thing import get_social_metadata
        try:
            self.results = get_social_metadata(self.title, self.book_author,
                    self.publisher, self.isbn)
        except Exception, e:
            self.exception = e
            self.tb = traceback.format_exc()

    # }}}


def result_index(source, result):
    if not result.isbn:
        return -1
    for i, x in enumerate(source):
        if x.isbn == result.isbn:
            return i
    return -1

def merge_results(one, two):
    for x in two:
        idx = result_index(one, x)
        if idx < 0:
            one.append(x)
        else:
            one[idx].smart_update(x)

class MetadataSources(object):

    def __init__(self, sources):
        self.sources = sources

    def __enter__(self):
        for s in self.sources:
            s.__enter__()
        return self

    def __exit__(self, *args):
        for s in self.sources:
            s.__exit__()

    def __call__(self, *args, **kwargs):
        for s in self.sources:
            s(*args, **kwargs)

    def join(self):
        for s in self.sources:
            s.join()

def filter_metadata_results(item):
    keywords = ["audio", "tape", "cassette", "abridged", "playaway"]
    for keyword in keywords:
        if item.publisher and keyword in item.publisher.lower():
            return False
    return True

def do_cover_check(item):
    item.has_cover = False
    try:
        item.has_cover = check_for_cover(item)
    except:
        pass # Cover not found

def check_for_covers(items):
    threads = [Thread(target=do_cover_check, args=(item,)) for item in items]
    for t in threads: t.start()
    for t in threads: t.join()

def search(title=None, author=None, publisher=None, isbn=None, isbndb_key=None,
           verbose=0):
    assert not(title is None and author is None and publisher is None and \
                   isbn is None)
    from calibre.customize.ui import metadata_sources, migrate_isbndb_key
    migrate_isbndb_key()
    if isbn is not None:
        isbn = re.sub(r'[^a-zA-Z0-9]', '', isbn).upper()
    fetchers = list(metadata_sources(isbndb_key=isbndb_key))
    with MetadataSources(fetchers) as manager:
        manager(title, author, publisher, isbn, verbose)
        manager.join()

    results = list(fetchers[0].results)
    for fetcher in fetchers[1:]:
        merge_results(results, fetcher.results)

    results = list(filter(filter_metadata_results, results))

    check_for_covers(results)

    words = ("the", "a", "an", "of", "and")
    prefix_pat = re.compile(r'^(%s)\s+'%("|".join(words)))
    trailing_paren_pat = re.compile(r'\(.*\)$')
    whitespace_pat = re.compile(r'\s+')

    def sort_func(x, y):

        def cleanup_title(s):
            if s is None:
                s = _('Unknown')
            s = s.strip().lower()
            s = prefix_pat.sub(' ', s)
            s = trailing_paren_pat.sub('', s)
            s = whitespace_pat.sub(' ', s)
            return s.strip()

        t = cleanup_title(title)
        x_title = cleanup_title(x.title)
        y_title = cleanup_title(y.title)

        # prefer titles that start with the search title
        tx = cmp(t, x_title)
        ty = cmp(t, y_title)
        result = 0 if abs(tx) == abs(ty) else abs(tx) - abs(ty)

        # then prefer titles that have a cover image
        if result == 0:
            result = -cmp(x.has_cover, y.has_cover)

        # then prefer titles with the longest comment, with in 10%
        if result == 0:
            cx = len(x.comments.strip() if x.comments else '')
            cy = len(y.comments.strip() if y.comments else '')
            t = (cx + cy) / 20
            result = cy - cx
            if abs(result) < t:
                result = 0

        return result

    results = sorted(results, cmp=sort_func)

    # if for some reason there is no comment in the top selection, go looking for one
    if len(results) > 1:
        if not results[0].comments or len(results[0].comments) == 0:
            for r in results[1:]:
                try:
                    if title and title.lower() == r.title[:len(title)].lower() \
                            and r.comments and len(r.comments):
                        results[0].comments = r.comments
                        break
                except:
                    pass
        # Find a pubdate
        pubdate = None
        for r in results:
            if r.pubdate is not None:
                pubdate = r.pubdate
                break
        if pubdate is not None:
            for r in results:
                if r.pubdate is None:
                    r.pubdate = pubdate

    def fix_case(x):
        if x and x.isupper():
            x = titlecase(x)
        return x

    for r in results:
        r.title = fix_case(r.title)
        if r.authors:
            r.authors = list(map(fix_case, r.authors))

    return results, [(x.name, x.exception, x.tb) for x in fetchers]

def get_social_metadata(mi, verbose=0):
    from calibre.customize.ui import metadata_sources
    fetchers = list(metadata_sources(metadata_type='social'))
    with MetadataSources(fetchers) as manager:
        manager(mi.title, mi.authors, mi.publisher, mi.isbn, verbose)
        manager.join()
    ratings, tags, comments, series, series_index = [], set([]), set([]), None, None
    for fetcher in fetchers:
        if fetcher.results:
            dmi = fetcher.results
            if dmi.rating is not None:
                ratings.append(dmi.rating)
            if dmi.tags:
                for t in dmi.tags:
                    tags.add(t)
            if mi.pubdate is None and dmi.pubdate is not None:
                mi.pubdate = dmi.pubdate
            if dmi.comments:
                comments.add(dmi.comments)
            if dmi.series is not None:
                series = dmi.series
                if dmi.series_index is not None:
                    series_index = dmi.series_index
    if ratings:
        rating = sum(ratings)/float(len(ratings))
        if mi.rating is None or mi.rating < 0.1:
            mi.rating = rating
        else:
            mi.rating = (mi.rating + rating)/2.0
    if tags:
        if not mi.tags:
            mi.tags = []
        mi.tags += list(tags)
        mi.tags = list(sorted(list(set(mi.tags))))
    if comments:
        if not mi.comments or len(mi.comments)+20 < len(' '.join(comments)):
            mi.comments = ''
            for x in comments:
                mi.comments += x+'\n\n'
    if series and series_index is not None:
        mi.series = series
        mi.series_index = series_index

    return [(x.name, x.exception, x.tb) for x in fetchers if x.exception is not
            None]



def option_parser():
    parser = OptionParser(textwrap.dedent(
        '''\
        %prog [options]

        Fetch book metadata from online sources. You must specify at least one
        of title, author, publisher or ISBN. If you specify ISBN, the others
        are ignored.
        '''
    ))
    parser.add_option('-t', '--title', help='Book title')
    parser.add_option('-a', '--author', help='Book author(s)')
    parser.add_option('-p', '--publisher', help='Book publisher')
    parser.add_option('-i', '--isbn', help='Book ISBN')
    parser.add_option('-m', '--max-results', default=10,
                      help='Maximum number of results to fetch')
    parser.add_option('-k', '--isbndb-key',
                      help=('The access key for your ISBNDB.com account. '
                      'Only needed if you want to search isbndb.com '
                      'and you haven\'t customized the IsbnDB plugin.'))
    parser.add_option('-v', '--verbose', default=0, action='count',
                      help='Be more verbose about errors')
    return parser

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    results, exceptions = search(opts.title, opts.author, opts.publisher,
                                 opts.isbn, opts.isbndb_key, opts.verbose)
    social_exceptions = []
    for result in results:
        social_exceptions.extend(get_social_metadata(result, opts.verbose))
        prints(unicode(result))
        print

    for name, exception, tb in exceptions+social_exceptions:
        if exception is not None:
            print 'WARNING: Fetching from', name, 'failed with error:'
            print exception
            print tb

    return 0

if __name__ == '__main__':
    sys.exit(main())
