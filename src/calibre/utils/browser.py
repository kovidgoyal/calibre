#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy, httplib, ssl
from cookielib import CookieJar, Cookie

from mechanize import Browser as B, HTTPSHandler


class ModernHTTPSHandler(HTTPSHandler):

    ssl_context = None

    def https_open(self, req):
        if self.client_cert_manager is not None:
            key_file, cert_file = self.client_cert_manager.find_key_cert(
                req.get_full_url())
            if cert_file:
                self.ssl_context.load_cert_chain(cert_file, key_file)

        def conn_factory(hostport, **kw):
            kw['context'] = self.ssl_context
            return httplib.HTTPSConnection(hostport, **kw)
        return self.do_open(conn_factory, req)


class Browser(B):
    '''
    A cloneable mechanize browser. Useful for multithreading. The idea is that
    each thread has a browser clone. Every clone uses the same thread safe
    cookie jar. All clones share the same browser configuration.

    Also adds support for fine-tuning SSL verification via an SSL context object.
    '''

    handler_classes = B.handler_classes.copy()
    handler_classes['https'] = ModernHTTPSHandler

    def __init__(self, *args, **kwargs):
        self._clone_actions = {}
        sc = kwargs.pop('ssl_context', None)
        if sc is None:
            sc = ssl.create_default_context() if kwargs.pop('verify_ssl', True) else ssl._create_unverified_context(cert_reqs=ssl.CERT_NONE)

        B.__init__(self, *args, **kwargs)
        self.set_cookiejar(CookieJar())
        self._ua_handlers['https'].ssl_context = sc

    @property
    def https_handler(self):
        return self._ua_handlers['https']

    def set_current_header(self, header, value=None):
        found = False
        q = header.lower()
        remove = []
        for i, (k, v) in enumerate(tuple(self.addheaders)):
            if k.lower() == q:
                if value:
                    self.addheaders[i] = (header, value)
                    found = True
                else:
                    remove.append(i)
        if not found:
            self.addheaders.append((header, value))
        if remove:
            for i in reversed(remove):
                del self.addheaders[i]

    def current_user_agent(self):
        for k, v in self.addheaders:
            if k.lower() == 'user-agent':
                return v

    def set_user_agent(self, newval):
        self.set_current_header('User-agent', newval)

    def set_handle_refresh(self, *args, **kwargs):
        B.set_handle_refresh(self, *args, **kwargs)
        self._clone_actions['set_handle_refresh'] = ('set_handle_refresh',
                args, kwargs)

    def set_cookiejar(self, *args, **kwargs):
        B.set_cookiejar(self, *args, **kwargs)
        self._clone_actions['set_cookiejar'] = ('set_cookiejar', args, kwargs)

    def set_cookie(self, name, value, domain, path='/'):
        self.cookiejar.set_cookie(Cookie(
            None, name, value,
            None, False,
            domain, True, False,
            path, True,
            False, None, False, None, None, None
        ))

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

    def set_debug_redirects(self, *args, **kwargs):
        B.set_debug_redirects(self, *args, **kwargs)
        self._clone_actions['set_debug_redirects'] = ('set_debug_redirects',
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
        clone = self.__class__()
        clone.https_handler.ssl_context = self.https_handler.ssl_context
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
    pprint(orig._ua_handlers)
    pprint(clone._ua_handlers)
    assert orig._ua_handlers.keys() == clone._ua_handlers.keys()
    assert orig._ua_handlers['_cookies'].cookiejar is \
            clone._ua_handlers['_cookies'].cookiejar
    assert orig.addheaders == clone.addheaders
