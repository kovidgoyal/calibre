#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy
from cookielib import CookieJar

from mechanize import Browser as B

class Browser(B):
    '''
    A cloneable mechanize browser. Useful for multithreading. The idea is that
    each thread has a browser clone. Every clone uses the same thread safe
    cookie jar. All clones share the same browser configuration.
    '''

    def __init__(self, *args, **kwargs):
        self._clone_actions = {}

        B.__init__(self, *args, **kwargs)
        self.set_cookiejar(CookieJar())

    def set_handle_refresh(self, *args, **kwargs):
        B.set_handle_refresh(self, *args, **kwargs)
        self._clone_actions['set_handle_refresh'] = ('set_handle_refresh',
                args, kwargs)

    def set_cookiejar(self, *args, **kwargs):
        B.set_cookiejar(self, *args, **kwargs)
        self._clone_actions['set_cookiejar'] = ('set_cookiejar', args, kwargs)

    def copy_cookies_from_jsbrowser(self, jsbrowser):
        for cookie in jsbrowser.cookies:
            self.cookiejar.set_cookie(cookie)

    @property
    def cookiejar(self):
        return self._clone_actions['set_cookiejar'][1][0]

    def set_handle_redirect(self, *args, **kwargs):
        B.set_handle_redirect(self, *args, **kwargs)
        self._clone_actions['set_handle_redirect'] = ('set_handle_redirect',
                args, kwargs)

    def set_handle_equiv(self, *args, **kwargs):
        B.set_handle_equiv(self, *args, **kwargs)
        self._clone_actions['set_handle_equiv'] = ('set_handle_equiv',
                args, kwargs)

    def set_handle_gzip(self, handle):
        B._set_handler(self, '_gzip', handle)
        self._clone_actions['set_handle_gzip'] = ('set_handle_gzip',
                (handle,), {})

    def set_debug_redirect(self, *args, **kwargs):
        B.set_debug_redirect(self, *args, **kwargs)
        self._clone_actions['set_debug_redirect'] = ('set_debug_redirect',
                args, kwargs)

    def set_debug_responses(self, *args, **kwargs):
        B.set_debug_responses(self, *args, **kwargs)
        self._clone_actions['set_debug_responses'] = ('set_debug_responses',
                args, kwargs)

    def set_debug_http(self, *args, **kwargs):
        B.set_debug_http(self, *args, **kwargs)
        self._clone_actions['set_debug_http'] = ('set_debug_http',
                args, kwargs)

    def set_handle_robots(self, *args, **kwargs):
        B.set_handle_robots(self, *args, **kwargs)
        self._clone_actions['set_handle_robots'] = ('set_handle_robots',
                args, kwargs)

    def set_proxies(self, *args, **kwargs):
        B.set_proxies(self, *args, **kwargs)
        self._clone_actions['set_proxies'] = ('set_proxies', args, kwargs)

    def add_password(self, *args, **kwargs):
        B.add_password(self, *args, **kwargs)
        self._clone_actions['add_password'] = ('add_password', args, kwargs)

    def add_proxy_password(self, *args, **kwargs):
        B.add_proxy_password(self, *args, **kwargs)
        self._clone_actions['add_proxy_password'] = ('add_proxy_password', args, kwargs)

    def clone_browser(self):
        clone = Browser()
        clone.addheaders = copy.deepcopy(self.addheaders)
        for func, args, kwargs in self._clone_actions.values():
            func = getattr(clone, func)
            func(*args, **kwargs)
        return clone

if __name__ == '__main__':
    from calibre import browser
    from pprint import pprint
    orig = browser()
    clone = orig.clone_browser()
    pprint( orig._ua_handlers)
    pprint(clone._ua_handlers)
    assert orig._ua_handlers.keys() == clone._ua_handlers.keys()
    assert orig._ua_handlers['_cookies'].cookiejar is \
            clone._ua_handlers['_cookies'].cookiejar
    assert orig.addheaders == clone.addheaders


