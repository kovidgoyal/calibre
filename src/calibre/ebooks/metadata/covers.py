#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import traceback, socket, re, sys
from functools import partial
from threading import Thread, Event
from Queue import Queue, Empty
from lxml import etree

import mechanize

from calibre.customize import Plugin
from calibre import browser, prints
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.constants import preferred_encoding, DEBUG

class CoverDownload(Plugin):
    '''
    These plugins are used to download covers for books.
    '''

    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Kovid Goyal'
    type = _('Cover download')

    def has_cover(self, mi, ans, timeout=5.):
        '''
        Check if the book described by mi has a cover. Call ans.set() if it
        does. Do nothing if it doesn't.

        :param mi: MetaInformation object
        :param timeout: timeout in seconds
        :param ans: A threading.Event object
        '''
        raise NotImplementedError()

    def get_covers(self, mi, result_queue, abort, timeout=5.):
        '''
        Download covers for books described by the mi object. Downloaded covers
        must be put into the result_queue. If more than one cover is available,
        the plugin should continue downloading them and putting them into
        result_queue until abort.is_set() returns True.

        :param mi: MetaInformation object
        :param result_queue: A multithreaded Queue
        :param abort: A threading.Event object
        :param timeout: timeout in seconds
        '''
        raise NotImplementedError()

    def exception_to_string(self, ex):
        try:
            return unicode(ex)
        except:
            try:
                return str(ex).decode(preferred_encoding, 'replace')
            except:
                return repr(ex)

    def debug(self, *args, **kwargs):
        if DEBUG:
            prints('\t'+self.name+':', *args, **kwargs)



class HeadRequest(mechanize.Request):

    def get_method(self):
        return 'HEAD'

class OpenLibraryCovers(CoverDownload): # {{{
    'Download covers from openlibrary.org'

    OPENLIBRARY = 'http://covers.openlibrary.org/b/isbn/%s-L.jpg?default=false'
    name = 'openlibrary.org covers'
    description = _('Download covers from openlibrary.org')
    author = 'Kovid Goyal'

    def has_cover(self, mi, ans, timeout=5.):
        if not mi.isbn:
            return False
        br = browser()
        br.set_handle_redirect(False)
        try:
            br.open_novisit(HeadRequest(self.OPENLIBRARY%mi.isbn), timeout=timeout)
            self.debug('cover for', mi.isbn, 'found')
            ans.set()
        except Exception, e:
            if callable(getattr(e, 'getcode', None)) and e.getcode() == 302:
                self.debug('cover for', mi.isbn, 'found')
                ans.set()
            else:
                self.debug(e)

    def get_covers(self, mi, result_queue, abort, timeout=5.):
        if not mi.isbn:
            return
        br = browser()
        try:
            ans = br.open(self.OPENLIBRARY%mi.isbn, timeout=timeout).read()
            result_queue.put((True, ans, 'jpg', self.name))
        except Exception, e:
            if callable(getattr(e, 'getcode', None)) and e.getcode() == 404:
                result_queue.put((False, _('ISBN: %s not found')%mi.isbn, '', self.name))
            else:
                result_queue.put((False, self.exception_to_string(e),
                    traceback.format_exc(), self.name))

# }}}

class LibraryThingCovers(CoverDownload): # {{{

    name = 'librarything.com covers'
    description = _('Download covers from librarything.com')
    author = 'Kovid Goyal'

    LIBRARYTHING = 'http://www.librarything.com/isbn/'

    def get_cover_url(self, isbn, br, timeout=5.):
        try:
            src = br.open_novisit('http://www.librarything.com/isbn/'+isbn,
                    timeout=timeout).read().decode('utf-8', 'replace')
        except Exception, err:
            if isinstance(getattr(err, 'args', [None])[0], socket.timeout):
                err = Exception(_('LibraryThing.com timed out. Try again later.'))
            raise err
        else:
            s = BeautifulSoup(src)
            url = s.find('td', attrs={'class':'left'})
            if url is None:
                if s.find('div', attrs={'class':'highloadwarning'}) is not None:
                    raise Exception(_('Could not fetch cover as server is experiencing high load. Please try again later.'))
                raise Exception(_('ISBN: %s not found')%isbn)
            url = url.find('img')
            if url is None:
                raise Exception(_('LibraryThing.com server error. Try again later.'))
            url = re.sub(r'_S[XY]\d+', '', url['src'])
            return url

    def has_cover(self, mi, ans, timeout=5.):
        if not mi.isbn:
            return False
        br = browser()
        try:
            self.get_cover_url(mi.isbn, br, timeout=timeout)
            self.debug('cover for', mi.isbn, 'found')
            ans.set()
        except Exception, e:
            self.debug(e)

    def get_covers(self, mi, result_queue, abort, timeout=5.):
        if not mi.isbn:
            return
        br = browser()
        try:
            url = self.get_cover_url(mi.isbn, br, timeout=timeout)
            cover_data = br.open_novisit(url).read()
            result_queue.put((True, cover_data, 'jpg', self.name))
        except Exception, e:
            result_queue.put((False, self.exception_to_string(e),
                traceback.format_exc(), self.name))

# }}}

def check_for_cover(mi, timeout=5.): # {{{
    from calibre.customize.ui import cover_sources
    ans = Event()
    checkers = [partial(p.has_cover, mi, ans, timeout=timeout) for p in
            cover_sources()]
    workers = [Thread(target=c) for c in checkers]
    for w in workers:
        w.daemon = True
        w.start()
    while not ans.is_set():
        ans.wait(0.1)
        if sum([int(w.is_alive()) for w in workers]) == 0:
            break
    return ans.is_set()

# }}}

def download_covers(mi, result_queue, max_covers=50, timeout=5.): # {{{
    from calibre.customize.ui import cover_sources
    abort = Event()
    temp = Queue()
    getters = [partial(p.get_covers, mi, temp, abort, timeout=timeout) for p in
            cover_sources()]
    workers = [Thread(target=c) for c in getters]
    for w in workers:
        w.daemon = True
        w.start()
    count = 0
    while count < max_covers:
        try:
            result = temp.get_nowait()
            if result[0]:
                count += 1
            result_queue.put(result)
        except Empty:
            pass
        if sum([int(w.is_alive()) for w in workers]) == 0:
            break

    abort.set()

    while True:
        try:
            result = temp.get_nowait()
            count += 1
            result_queue.put(result)
        except Empty:
            break

# }}}

class DoubanCovers(CoverDownload): # {{{
    'Download covers from Douban.com'

    DOUBAN_ISBN_URL = 'http://api.douban.com/book/subject/isbn/'
    CALIBRE_DOUBAN_API_KEY = '0bd1672394eb1ebf2374356abec15c3d'
    name = 'Douban.com covers'
    description = _('Download covers from Douban.com')
    author = 'Li Fanxi'

    def get_cover_url(self, isbn, br, timeout=5.):
        try:
            url = self.DOUBAN_ISBN_URL + isbn + "?apikey=" + self.CALIBRE_DOUBAN_API_KEY
            src = br.open(url, timeout=timeout).read()
        except Exception, err:
            if isinstance(getattr(err, 'args', [None])[0], socket.timeout):
                err = Exception(_('Douban.com API timed out. Try again later.'))
            raise err
        else:
            feed = etree.fromstring(src)
            NAMESPACES = {
              'openSearch':'http://a9.com/-/spec/opensearchrss/1.0/',
              'atom' : 'http://www.w3.org/2005/Atom',
              'db': 'http://www.douban.com/xmlns/'
            }
            XPath = partial(etree.XPath, namespaces=NAMESPACES)
            entries = XPath('//atom:entry')(feed)
            if len(entries) < 1:
                return None
            try:
                cover_url = XPath("descendant::atom:link[@rel='image']/attribute::href")
                u = cover_url(entries[0])[0].replace('/spic/', '/lpic/');
                # If URL contains "book-default", the book doesn't have a cover
                if u.find('book-default') != -1:
                    return None
            except:
                return None
            return u

    def has_cover(self, mi, ans, timeout=5.):
        if not mi.isbn:
            return False
        br = browser()
        try:
            if self.get_cover_url(mi.isbn, br, timeout=timeout) != None:
                self.debug('cover for', mi.isbn, 'found')
                ans.set()
        except Exception, e:
            self.debug(e)

    def get_covers(self, mi, result_queue, abort, timeout=5.):
        if not mi.isbn:
            return
        br = browser()
        try:
            url = self.get_cover_url(mi.isbn, br, timeout=timeout)
            cover_data = br.open_novisit(url).read()
            result_queue.put((True, cover_data, 'jpg', self.name))
        except Exception, e:
            result_queue.put((False, self.exception_to_string(e),
                traceback.format_exc(), self.name))
# }}}

def download_cover(mi, timeout=5.): # {{{
    results = Queue()
    download_covers(mi, results, max_covers=1, timeout=timeout)
    errors, ans = [], None
    while True:
        try:
            x = results.get_nowait()
            if x[0]:
                ans = x[1]
            else:
                errors.append(x)
        except Empty:
            break
    return ans, errors

# }}}

def test(isbns): # {{{
    from calibre.ebooks.metadata import MetaInformation
    mi = MetaInformation('test', ['test'])
    for isbn in isbns:
        prints('Testing ISBN:', isbn)
        mi.isbn = isbn
        found = check_for_cover(mi)
        prints('Has cover:', found)
        ans, errors = download_cover(mi)
        if ans is not None:
            prints('Cover downloaded')
        else:
            prints('Download failed:')
            for err in errors:
                prints('\t', err[-1]+':', err[1])
        print '\n'

# }}}

if __name__ == '__main__':
    isbns = sys.argv[1:] + ['9781591025412', '9780307272119']
    test(isbns)
