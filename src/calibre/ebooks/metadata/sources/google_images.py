#!/usr/bin/env python
# vim:fileencoding=UTF-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from collections import OrderedDict

from calibre import as_unicode
from calibre.ebooks.metadata.sources.base import Source, Option

class GoogleImages(Source):

    name = 'Google Images'
    description = _('Downloads covers from a Google Image search. Useful to find larger/alternate covers.')
    capabilities = frozenset(['cover'])
    config_help_message = _('Configure the Google Image Search plugin')
    can_get_multiple_covers = True
    options = (Option('max_covers', 'number', 5, _('Maximum number of covers to get'),
                      _('The maximum number of covers to process from the google search result')),
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
        from threading import Thread
        import time
        timeout = max(60, timeout) # Needs at least a minute
        title = ' '.join(self.get_title_tokens(title))
        author = ' '.join(self.get_author_tokens(authors))
        urls = self.get_image_urls(title, author, log, abort, timeout)
        if not urls:
            log('No images found in Google for, title: %r and authors: %r'%(title, author))
            return
        urls = urls[:self.prefs['max_covers']]
        if get_best_cover:
            urls = urls[:1]
        log('Downloading %d covers'%len(urls))
        workers = [Thread(target=self.download_image, args=(url, timeout, log, result_queue)) for url in urls]
        for w in workers:
            w.daemon = True
            w.start()
        alive = True
        start_time = time.time()
        while alive and not abort.is_set() and time.time() - start_time < timeout:
            alive = False
            for w in workers:
                if w.is_alive():
                    alive = True
                    break
            abort.wait(0.1)

    def download_image(self, url, timeout, log, result_queue):
        try:
            ans = self.browser.open_novisit(url, timeout=timeout).read()
            result_queue.put((self, ans))
            log('Downloaded cover from: %s'%url)
        except Exception:
            self.log.exception('Failed to download cover from: %r'%url)

    def get_image_urls(self, title, author, log, abort, timeout):
        from calibre.utils.ipc.simple_worker import fork_job, WorkerError
        try:
            return fork_job('calibre.ebooks.metadata.sources.google_images',
                    'search', args=(title, author, self.prefs['size'], timeout), no_output=True, abort=abort, timeout=timeout)['result']
        except WorkerError as e:
            if e.orig_tb:
                log.error(e.orig_tb)
            log.exception('Searching google failed:' + as_unicode(e))
        except Exception as e:
            log.exception('Searching google failed:' + as_unicode(e))

        return []

USER_AGENT = 'Mozilla/5.0 (X11; U; Linux x86_64; en-US; rv:1.9.2.13) Gecko/20101210 Firefox/3.6.13'

def find_image_urls(br, ans):
    import urlparse
    for w in br.page.mainFrame().documentElement().findAll('.images_table a[href]'):
        try:
            imgurl = urlparse.parse_qs(urlparse.urlparse(unicode(w.attribute('href'))).query)['imgurl'][0]
        except:
            continue
        if imgurl not in ans:
            ans.append(imgurl)

def search(title, author, size, timeout, debug=False):
    import time
    from calibre.web.jsbrowser.browser import Browser, LoadWatcher, Timeout
    ans = []
    start_time = time.time()
    br = Browser(user_agent=USER_AGENT, enable_developer_tools=debug)
    br.visit('https://www.google.com/advanced_image_search')
    f = br.select_form('form[action="/search"]')
    f['as_q'] = '%s %s'%(title, author)
    if size != 'any':
        f['imgsz'] = size
    f['imgar'] = 't|xt'
    f['as_filetype'] = 'jpg'
    br.submit(wait_for_load=False)

    # Loop until the page finishes loading or at least five image urls are
    # found
    lw = LoadWatcher(br.page, br)
    while lw.is_loading and len(ans) < 5:
        br.run_for_a_time(0.2)
        find_image_urls(br, ans)
        if time.time() - start_time > timeout:
            raise Timeout('Timed out trying to load google image search page')
    find_image_urls(br, ans)
    if debug:
        br.show_browser()
    br.close()
    del br # Needed to prevent PyQt from segfaulting
    return ans

def test_google():
    import pprint
    pprint.pprint(search('heroes', 'abercrombie', 'svga', 60, debug=True))

def test():
    from Queue import Queue
    from threading import Event
    from calibre.utils.logging import default_log
    p = GoogleImages(None)
    rq = Queue()
    p.download_cover(default_log, rq, Event(), title='The Heroes',
                     authors=('Joe Abercrombie',))
    print ('Downloaded', rq.qsize(), 'covers')

if __name__ == '__main__':
    test()

