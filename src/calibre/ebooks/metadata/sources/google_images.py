#!/usr/bin/env python2
# vim:fileencoding=UTF-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from collections import OrderedDict

from calibre.ebooks.metadata.sources.base import Source, Option

USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64; rv:45.0) Gecko/20100101 Firefox/45.0'


class GoogleImages(Source):

    name = 'Google Images'
    version = (1, 0, 0)
    minimum_calibre_version = (2, 80, 0)
    description = _('Downloads covers from a Google Image search. Useful to find larger/alternate covers.')
    capabilities = frozenset(['cover'])
    config_help_message = _('Configure the Google Image Search plugin')
    can_get_multiple_covers = True
    supports_gzip_transfer_encoding = True
    options = (Option('max_covers', 'number', 5, _('Maximum number of covers to get'),
                      _('The maximum number of covers to process from the Google search result')),
               Option('size', 'choices', 'svga', _('Cover size'),
                      _('Search for covers larger than the specified size'),
                      choices=OrderedDict((
                          ('any', _('Any size'),),
                          ('l', _('Large'),),
                          ('qsvga', _('Larger than %s')%'400x300',),
                          ('vga', _('Larger than %s')%'640x480',),
                          ('svga', _('Larger than %s')%'600x800',),
                          ('xga', _('Larger than %s')%'1024x768',),
                          ('2mp', _('Larger than %s')%'2 MP',),
                          ('4mp', _('Larger than %s')%'4 MP',),
                      ))),
    )

    def download_cover(self, log, result_queue, abort,
            title=None, authors=None, identifiers={}, timeout=30, get_best_cover=False):
        if not title:
            return
        timeout = max(60, timeout)  # Needs at least a minute
        title = ' '.join(self.get_title_tokens(title))
        author = ' '.join(self.get_author_tokens(authors))
        urls = self.get_image_urls(title, author, log, abort, timeout)
        self.download_multiple_covers(title, authors, urls, get_best_cover, timeout, result_queue, abort, log)

    @property
    def user_agent(self):
        return USER_AGENT

    def get_image_urls(self, title, author, log, abort, timeout):
        from calibre.utils.cleantext import clean_ascii_chars
        from urllib import urlencode
        import html5lib
        import json
        from collections import OrderedDict
        ans = OrderedDict()
        br = self.browser
        q = urlencode({'as_q': ('%s %s'%(title, author)).encode('utf-8')}).decode('utf-8')
        sz = self.prefs['size']
        if sz == 'any':
            sz = ''
        elif sz == 'l':
            sz = 'isz:l,'
        else:
            sz = 'isz:lt,islt:%s,' % sz
        # See https://www.google.com/advanced_image_search to understand this
        # URL scheme
        url = 'https://www.google.com/search?as_st=y&tbm=isch&{}&as_epq=&as_oq=&as_eq=&cr=&as_sitesearch=&safe=images&tbs={}iar:t,ift:jpg'.format(q, sz)
        log('Search URL: ' + url)
        raw = br.open(url).read().decode('utf-8')
        root = html5lib.parse(clean_ascii_chars(raw), treebuilder='lxml', namespaceHTMLElements=False)
        for div in root.xpath('//div[@class="rg_meta"]'):
            try:
                data = json.loads(div.text)
            except Exception:
                continue
            if 'ou' in data:
                ans[data['ou']] = True
        return list(ans.iterkeys())


def test():
    from Queue import Queue
    from threading import Event
    from calibre.utils.logging import default_log
    p = GoogleImages(None)
    p.log = default_log
    rq = Queue()
    p.download_cover(default_log, rq, Event(), title='The Heroes',
                     authors=('Joe Abercrombie',))
    print ('Downloaded', rq.qsize(), 'covers')


if __name__ == '__main__':
    test()
