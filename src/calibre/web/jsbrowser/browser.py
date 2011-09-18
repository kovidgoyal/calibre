#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, pprint

from PyQt4.Qt import (QObject, QNetworkAccessManager, QNetworkDiskCache,
        QNetworkProxy, QNetworkProxyFactory)
from PyQt4.QtWebKit import QWebPage

from calibre import USER_AGENT, prints, get_proxies, get_proxy_info
from calibre.constants import ispy3, config_dir
from calibre.utils.logging import ThreadSafeLog
from calibre.gui2 import must_use_qt

class WebPage(QWebPage): # {{{

    def __init__(self, log,
            confirm_callback=None,
            prompt_callback=None,
            user_agent=USER_AGENT,
            parent=None):
        QWebPage.__init__(self, parent)

        self.log = log
        self.user_agent = user_agent if user_agent else USER_AGENT
        self.confirm_callback = confirm_callback
        self.prompt_callback = prompt_callback
        self.setForwardUnsupportedContent(True)
        self.unsupportedContent.connect(self.on_unsupported_content)

    def userAgentForUrl(self, url):
        return self.user_agent

    def javaScriptAlert(self, frame, msg):
        if self.view() is not None:
            return QWebPage.javaScriptAlert(self, frame, msg)
        prints('JSBrowser alert():', unicode(msg))

    def javaScriptConfirm(self, frame, msg):
        if self.view() is not None:
            return QWebPage.javaScriptConfirm(self, frame, msg)
        if self.confirm_callback is not None:
            return self.confirm_callback(unicode(msg))
        return True

    def javaScriptConsoleMessage(self, msg, lineno, source_id):
        prints('JSBrowser msg():%s:%s:'%(unicode(source_id), lineno), unicode(msg))

    def javaScriptPrompt(self, frame, msg, default_value, *args):
        if self.view() is not None:
            return QWebPage.javaScriptPrompt(self, frame, msg, default_value,
                    *args)
        if self.prompt_callback is None:
            return (False, default_value) if ispy3 else False
        value = self.prompt_callback(unicode(msg), unicode(default_value))
        ok = value is not None
        if ispy3:
            return ok, value
        if ok:
            result = args[0]
            result.clear()
            result.append(value)
        return ok

    def shouldInterruptJavaScript(self):
        if self.view() is not None:
            return QWebPage.shouldInterruptJavaScript(self)
        return True

    def on_unsupported_content(self, reply):
        self.log.warn('Unsupported content, ignoring: %s'%reply.url())

# }}}

class ProxyFactory(QNetworkProxyFactory): # {{{

    def __init__(self, log):
        QNetworkProxyFactory.__init__(self)
        proxies = get_proxies()
        self.proxies = {}
        for scheme, proxy_string in proxies.iteritems():
            scheme = scheme.lower()
            info = get_proxy_info(scheme, proxy_string)
            if info is None: continue
            hn, port = info['hostname'], info['port']
            if not hn or not port: continue
            log.debug('JSBrowser using proxy:', pprint.pformat(info))
            pt = {'socks5':QNetworkProxy.Socks5Proxy}.get(scheme,
                    QNetworkProxy.HttpProxy)
            proxy = QNetworkProxy(pt, hn, port)
            un, pw = info['username'], info['password']
            if un:
                proxy.setUser(un)
            if pw:
                proxy.setPassword(pw)
            self.proxies[scheme] = proxy

        self.default_proxy = QNetworkProxy(QNetworkProxy.DefaultProxy)

    def queryProxy(self, query):
        scheme = unicode(query.protocolTag()).lower()
        return [self.proxies.get(scheme, self.default_proxy)]
# }}}

class NetworkAccessManager(QNetworkAccessManager): # {{{

    OPERATION_NAMES = { getattr(QNetworkAccessManager, '%sOperation'%x) :
            x.upper() for x in ('Head', 'Get', 'Put', 'Post', 'Delete',
                'Custom')
    }

    def __init__(self, log, use_disk_cache=True, parent=None):
        QNetworkAccessManager.__init__(self, parent)
        self.log = log
        if use_disk_cache:
            self.cache = QNetworkDiskCache(self)
            self.cache.setCacheDirectory(os.path.join(config_dir, 'caches',
                'jsbrowser'))
            self.setCache(self.cache)
        self.sslErrors.connect(self.on_ssl_errors)
        self.pf = ProxyFactory(log)
        self.setProxyFactory(self.pf)
        self.finished.connect(self.on_finished)

    def on_ssl_errors(self, reply, errors):
        reply.ignoreSslErrors()

    def createRequest(self, operation, request, data):
        url = unicode(request.url().toString())
        operation_name = self.OPERATION_NAMES[operation]
        debug = []
        debug.append(('Request: %s %s' % (operation_name, url)))
        for h in request.rawHeaderList():
            try:
                d = '  %s: %s' % (h, request.rawHeader(h))
            except:
                d = '  %r: %r' % (h, request.rawHeader(h))
            debug.append(d)

        if data is not None:
            raw = data.peek(1024)
            try:
                raw = raw.decode('utf-8')
            except:
                raw = repr(raw)
            debug.append('  Request data: %s'%raw)

        self.log.debug('\n'.join(debug))
        return QNetworkAccessManager.createRequest(self, operation, request,
                data)

    def on_finished(self, reply):
        reply_url = unicode(reply.url().toString())

        if reply.error():
            self.log.warn("Reply error: %s - %d (%s)" %
                (reply_url, reply.error(), reply.errorString()))
        else:
            debug = []
            debug.append("Reply successful: %s" % reply_url)
            for h in reply.rawHeaderList():
                try:
                    d = '  %s: %s' % (h, reply.rawHeader(h))
                except:
                    d = '  %r: %r' % (h, reply.rawHeader(h))
                debug.append(d)
            self.log.debug('\n'.join(debug))
# }}}

class Browser(QObject):

    '''
    Browser (WebKit with no GUI).

    This browser is NOT thread safe. Use it in a single thread only! If you
    need to run downloads in parallel threads, use multiple browsers (after
    copying the cookies).
    '''

    def __init__(self,
            # Logging. If None, uses a default log, which does not output
            # debugging info
            log = None,
            # Receives a string and returns True/False. By default, returns
            # True for all strings
            confirm_callback=None,

            # Prompt callback. Receives a msg string and a default value
            # string. Should return the user input value or None if the user
            # canceled the prompt. By default returns None.
            prompt_callback=None,

            # User agent to be used
            user_agent=USER_AGENT,

            # If True a disk cache is used
            use_disk_cache=True,

            # Verbosity
            verbosity = 0
        ):
        must_use_qt()
        QObject.__init__(self)

        if log is None:
            log = ThreadSafeLog()
        if verbosity:
            log.filter_level = log.DEBUG

        self.jquery_lib = P('content_server/jquery.js', data=True,
                allow_user_override=False).decode('utf-8')
        self.simulate_lib = P('jquery.simulate.js', data=True,
                allow_user_override=False).decode('utf-8')

        self.page = WebPage(log, confirm_callback=confirm_callback,
                prompt_callback=prompt_callback, user_agent=user_agent,
                parent=self)
        self.nam = NetworkAccessManager(log, use_disk_cache=use_disk_cache, parent=self)
        self.page.setNetworkAccessManager(self.nam)

