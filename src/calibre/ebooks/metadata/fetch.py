from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import traceback, sys, textwrap, re
from threading import Thread

from calibre import prints
from calibre.utils.config import OptionParser
from calibre.utils.logging import default_log

from calibre.customize import Plugin

class MetadataSource(Plugin):

    author = 'Kovid Goyal'

    supported_platforms = ['windows', 'osx', 'linux']

    #: The type of metadata fetched. 'basic' means basic metadata like
    #: title/author/isbn/etc. 'social' means social metadata like
    #: tags/rating/reviews/etc.
    metadata_type = 'basic'

    type = _('Metadata download')

    def __call__(self, title, author, publisher, isbn, verbose, log=None,
            extra=None):
        self.worker = Thread(target=self.fetch)
        self.worker.daemon = True
        self.title = title
        self.verbose = verbose
        self.author = author
        self.publisher = publisher
        self.isbn = isbn
        self.log = log if log is not None else default_log
        self.extra = extra
        self.exception, self.tb, self.results = None, None, []
        self.worker.start()

    def fetch(self):
        '''
        All the actual work is done here.
        '''
        raise NotImplementedError

    def is_ok(self):
        '''
        Used to check if the plugin has been correctly customized.
        For example: The isbndb plugin checks to see if the site_customization
        has been set with an isbndb.com access key.
        '''
        return True

    def join(self):
        return self.worker.join()


class GoogleBooks(MetadataSource):

    name = 'Google Books'
    description = _('Downloads metadata from Google Books')

    def fetch(self):
        from calibre.ebooks.metadata.google_books import search
        try:
            self.results = search(self.title, self.author, self.publisher,
                                  self.isbn, max_results=10,
                                  verbose=self.verbose)
        except Exception, e:
            self.exception = e
            self.tb = traceback.format_exc()


class ISBNDB(MetadataSource):

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
            if self.author:
                args.extend(['--author', self.author])
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

    def customization_help(self, gui=False):
        ans = _('To use isbndb.com you must sign up for a %sfree account%s '
                'and enter your access key below.')
        if gui:
            ans = '<p>'+ans%('<a href="http://www.isbndb.com">', '</a>')
        else:
            ans = ans.replace('%s', '')
        return ans

class Amazon(MetadataSource):

    name = 'Amazon'
    metadata_type = 'social'
    description = _('Downloads social metadata from amazon.com')

    def fetch(self):
        if not self.isbn:
            return
        from calibre.ebooks.metadata.amazon import get_social_metadata
        try:
            self.results = get_social_metadata(self.title, self.author,
                    self.publisher, self.isbn)
        except Exception, e:
            self.exception = e
            self.tb = traceback.format_exc()

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

def search(title=None, author=None, publisher=None, isbn=None, isbndb_key=None,
           verbose=0):
    assert not(title is None and author is None and publisher is None and \
                   isbn is None)
    from calibre.customize.ui import metadata_sources, migrate_isbndb_key
    migrate_isbndb_key()
    if isbn is not None:
        isbn = re.sub(r'[^a-zA-Z0-9]', '', isbn).upper()
    fetchers = list(metadata_sources(isbndb_key=isbndb_key))

    for fetcher in fetchers:
        fetcher(title, author, publisher, isbn, verbose)
    for fetcher in fetchers:
        fetcher.join()
    results = list(fetchers[0].results)
    for fetcher in fetchers[1:]:
        merge_results(results, fetcher.results)

    results = sorted(results, cmp=lambda x, y : cmp(
            (x.comments.strip() if x.comments else ''),
            (y.comments.strip() if y.comments else '')
                                                  ), reverse=True)

    return results, [(x.name, x.exception, x.tb) for x in fetchers]

def get_social_metadata(mi, verbose=0):
    from calibre.customize.ui import metadata_sources
    fetchers = list(metadata_sources(metadata_type='social'))
    for fetcher in fetchers:
        fetcher(mi.title, mi.authors, mi.publisher, mi.isbn, verbose)
    for fetcher in fetchers:
        fetcher.join()
    ratings, tags, comments = [], set([]), set([])
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
