__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Fetch cover from LibraryThing.com based on ISBN number.
'''

import sys, re

from lxml import html
import mechanize

from calibre import browser, prints, random_user_agent
from calibre.utils.config import OptionParser
from calibre.ebooks.chardet import strip_encoding_declarations

OPENLIBRARY = 'http://covers.openlibrary.org/b/isbn/%s-L.jpg?default=false'


_lt_br = None
def get_browser():
    global _lt_br
    if _lt_br is None:
        _lt_br = browser(user_agent=random_user_agent())
    return _lt_br.clone_browser()

class HeadRequest(mechanize.Request):

    def get_method(self):
        return 'HEAD'

def check_for_cover(isbn, timeout=5.):
    br = get_browser()
    br.set_handle_redirect(False)
    try:
        br.open_novisit(HeadRequest(OPENLIBRARY%isbn), timeout=timeout)
        return True
    except Exception as e:
        if callable(getattr(e, 'getcode', None)) and e.getcode() == 302:
            return True
    return False

class LibraryThingError(Exception):
    pass

class ISBNNotFound(LibraryThingError):
    pass

class ServerBusy(LibraryThingError):
    pass

def login(br, username, password):
    raw = br.open('http://www.librarything.com').read()
    if '>Sign out' in raw:
        return
    br.select_form('signup')
    br['formusername'] = username
    br['formpassword'] = password
    raw = br.submit().read()
    if '>Sign out' not in raw:
        raise ValueError('Failed to login as %r:%r'%(username, password))

def option_parser():
    parser = OptionParser(usage=\
_('''
%prog [options] ISBN

Fetch a cover image/social metadata for the book identified by ISBN from LibraryThing.com
'''))
    parser.add_option('-u', '--username', default=None,
                      help='Username for LibraryThing.com')
    parser.add_option('-p', '--password', default=None,
                      help='Password for LibraryThing.com')
    return parser

def get_social_metadata(title, authors, publisher, isbn, username=None,
        password=None):
    from calibre.ebooks.metadata import MetaInformation
    mi = MetaInformation(title, authors)
    if isbn:
        br = get_browser()
        try:
            login(br, username, password)

            raw = br.open_novisit('http://www.librarything.com/isbn/'
                        +isbn).read()
        except:
            return mi
        if '/wiki/index.php/HelpThing:Verify' in raw:
            raise Exception('LibraryThing is blocking calibre.')
        if not raw:
            return mi
        raw = raw.decode('utf-8', 'replace')
        raw = strip_encoding_declarations(raw)
        root = html.fromstring(raw)
        h1 = root.xpath('//div[@class="headsummary"]/h1')
        if h1 and not mi.title:
            mi.title = html.tostring(h1[0], method='text', encoding=unicode)
        h2 = root.xpath('//div[@class="headsummary"]/h2/a')
        if h2 and not mi.authors:
            mi.authors = [html.tostring(x, method='text', encoding=unicode) for
                    x in h2]
        h3 = root.xpath('//div[@class="headsummary"]/h3/a')
        if h3:
            match = None
            for h in h3:
               series = html.tostring(h, method='text', encoding=unicode)
               match = re.search(r'(.+) \((.+)\)', series)
               if match is not None:
                   break
            if match is not None:
                mi.series = match.group(1).strip()
                match = re.search(r'[0-9.]+', match.group(2))
                si = 1.0
                if match is not None:
                    si = float(match.group())
                mi.series_index = si
        #tags = root.xpath('//div[@class="tags"]/span[@class="tag"]/a')
        #if tags:
        #    mi.tags = [html.tostring(x, method='text', encoding=unicode) for x
        #            in tags]
        span = root.xpath(
                '//table[@class="wsltable"]/tr[@class="wslcontent"]/td[4]//span')
        if span:
            raw = html.tostring(span[0], method='text', encoding=unicode)
            match = re.search(r'([0-9.]+)', raw)
            if match is not None:
                rating = float(match.group())
                if rating > 0 and rating <= 5:
                    mi.rating = rating
    return mi


def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        return 1
    isbn = args[1]
    from calibre.customize.ui import metadata_sources, cover_sources
    lt = None
    for x in metadata_sources('social'):
        if x.name == 'LibraryThing':
            lt = x
            break
    lt('', '', '', isbn, True)
    lt.join()
    if lt.exception:
        print lt.tb
        return 1
    mi = lt.results
    prints(mi)
    mi.isbn = isbn

    lt = None
    for x in cover_sources():
        if x.name == 'librarything.com covers':
            lt = x
            break

    from threading import Event
    from Queue import Queue
    ev = Event()
    lt.has_cover(mi, ev)
    hc = ev.is_set()
    print 'Has cover:', hc
    if hc:
        abort = Event()
        temp = Queue()
        lt.get_covers(mi, temp, abort)

        cover = temp.get_nowait()
        if cover[0]:
            open(isbn + '.jpg', 'wb').write(cover[1])
            print 'Cover saved to:', isbn+'.jpg'
        else:
            print 'Cover download failed'
            print cover[2]

    return 0

if __name__ == '__main__':
    sys.exit(main())
