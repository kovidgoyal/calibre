from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import traceback, sys, textwrap
from threading import Thread

from calibre import preferred_encoding
from calibre.utils.config import OptionParser

class FetchGoogle(Thread):
    name = 'Google Books'
        
    def __init__(self, title, author, publisher, isbn, verbose):
        self.title = title
        self.verbose = verbose
        self.author = author
        self.publisher = publisher
        self.isbn = isbn
        Thread.__init__(self, None)
        self.daemon = True
        self.exception, self.tb = None, None
        
    def run(self):
        from calibre.ebooks.metadata.google_books import search
        try:
            self.results = search(self.title, self.author, self.publisher, 
                                  self.isbn, max_results=10, 
                                  verbose=self.verbose)
        except Exception, e:
            self.results = []
            self.exception = e
            self.tb = traceback.format_exc() 


class FetchISBNDB(Thread):
    name = 'IsbnDB'
    def __init__(self, title, author, publisher, isbn, verbose, key):
        self.title = title
        self.author = author
        self.publisher = publisher
        self.isbn = isbn
        self.verbose = verbose
        Thread.__init__(self, None)
        self.daemon = True
        self.exception, self.tb = None, None
        self.key = key
        
    def run(self):
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
        args.append(self.key)
        try:
            opts, args = option_parser().parse_args(args)
            self.results = create_books(opts, args)
        except Exception, e:
            self.results = []
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
    fetchers = [FetchGoogle(title, author, publisher, isbn, verbose)]
    if isbndb_key:
        fetchers.append(FetchISBNDB(title, author, publisher, isbn, verbose, 
                                        isbndb_key))
        
    
    for fetcher in fetchers:
        fetcher.start()
    for fetcher in fetchers:
        fetcher.join()
    for fetcher in fetchers[1:]:
        merge_results(fetchers[0].results, fetcher.results)
        
    results = sorted(fetchers[0].results, cmp=lambda x, y : cmp(
            (x.comments.strip() if x.comments else ''),
            (y.comments.strip() if y.comments else '')
                                                  ), reverse=True)
    
    return results, [(x.name, x.exception, x.tb) for x in fetchers]

        
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
                      'Only needed if you want to search isbndb.com'))
    parser.add_option('-v', '--verbose', default=0, action='count',
                      help='Be more verbose about errors')
    return parser

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    results, exceptions = search(opts.title, opts.author, opts.publisher, 
                                 opts.isbn, opts.isbndb_key, opts.verbose)
    for result in results:
        print unicode(result).encode(preferred_encoding)
        print
        
    for name, exception, tb in exceptions:
        if exception is not None:
            print 'WARNING: Fetching from', name, 'failed with error:'
            print exception
            print tb
            
    return 0
    
if __name__ == '__main__':
    sys.exit(main())