__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Fetch cover from LibraryThing.com based on ISBN number.
'''

import sys, socket, os, re

from lxml import html
import mechanize

from calibre import browser, prints
from calibre.utils.config import OptionParser
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.ebooks.chardet import strip_encoding_declarations

OPENLIBRARY = 'http://covers.openlibrary.org/b/isbn/%s-L.jpg?default=false'

class HeadRequest(mechanize.Request):

    def get_method(self):
        return 'HEAD'

def check_for_cover(isbn, timeout=5.):
    br = browser()
    br.set_handle_redirect(False)
    try:
        br.open_novisit(HeadRequest(OPENLIBRARY%isbn), timeout=timeout)
        return True
    except Exception, e:
        if callable(getattr(e, 'getcode', None)) and e.getcode() == 302:
            return True
    return False

class LibraryThingError(Exception):
    pass

class ISBNNotFound(LibraryThingError):
    pass

class ServerBusy(LibraryThingError):
    pass

def login(br, username, password, force=True):
    br.open('http://www.librarything.com')
    br.select_form('signup')
    br['formusername'] = username
    br['formpassword'] = password
    br.submit()


def cover_from_isbn(isbn, timeout=5., username=None, password=None):
    src = None
    br = browser()
    try:
        return br.open(OPENLIBRARY%isbn, timeout=timeout).read(), 'jpg'
    except:
        pass # Cover not found
    if username and password:
        try:
            login(br, username, password, force=False)
        except:
            pass
    try:
        src = br.open_novisit('http://www.librarything.com/isbn/'+isbn,
                timeout=timeout).read().decode('utf-8', 'replace')
    except Exception, err:
        if isinstance(getattr(err, 'args', [None])[0], socket.timeout):
            err = LibraryThingError(_('LibraryThing.com timed out. Try again later.'))
        raise err
    else:
        s = BeautifulSoup(src)
        url = s.find('td', attrs={'class':'left'})
        if url is None:
            if s.find('div', attrs={'class':'highloadwarning'}) is not None:
                raise ServerBusy(_('Could not fetch cover as server is experiencing high load. Please try again later.'))
            raise ISBNNotFound('ISBN: '+isbn+_(' not found.'))
        url = url.find('img')
        if url is None:
            raise LibraryThingError(_('LibraryThing.com server error. Try again later.'))
        url = re.sub(r'_S[XY]\d+', '', url['src'])
        cover_data = br.open_novisit(url).read()
        return cover_data, url.rpartition('.')[-1]

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
        br = browser()
        if username and password:
            try:
                login(br, username, password, force=False)
            except:
                pass

        raw = br.open_novisit('http://www.librarything.com/isbn/'
                    +isbn).read()
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
    mi = get_social_metadata('', [], '', isbn)
    prints(mi)
    cover_data, ext = cover_from_isbn(isbn, username=opts.username,
            password=opts.password)
    if not ext:
        ext = 'jpg'
    oname = os.path.abspath(isbn+'.'+ext)
    open(oname, 'w').write(cover_data)
    print 'Cover saved to file', oname
    return 0

if __name__ == '__main__':
    sys.exit(main())
