#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, pprint, time, uuid
from cookielib import Cookie
from threading import current_thread

from PyQt4.Qt import (QObject, QNetworkAccessManager, QNetworkDiskCache,
        QNetworkProxy, QNetworkProxyFactory, QEventLoop, QUrl, pyqtSignal,
        QDialog, QVBoxLayout, QSize, QNetworkCookieJar, Qt, pyqtSlot, QPixmap)
from PyQt4.QtWebKit import QWebPage, QWebSettings, QWebView, QWebElement

from calibre import USER_AGENT, prints, get_proxies, get_proxy_info, prepare_string_for_xml
from calibre.constants import ispy3, cache_dir
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.logging import ThreadSafeLog
from calibre.gui2 import must_use_qt
from calibre.web.jsbrowser.forms import FormsMixin, default_timeout

class Timeout(Exception):
    pass

class LoadError(Exception):
    pass


class WebPage(QWebPage):  # {{{

    def __init__(self, log,
            confirm_callback=None,
            prompt_callback=None,
            user_agent=USER_AGENT,
            enable_developer_tools=False,
            parent=None):
        QWebPage.__init__(self, parent)

        self.log = log
        self.user_agent = user_agent if user_agent else USER_AGENT
        self.confirm_callback = confirm_callback
        self.prompt_callback = prompt_callback
        self.setForwardUnsupportedContent(True)
        self.unsupportedContent.connect(self.on_unsupported_content)
        settings = self.settings()
        if enable_developer_tools:
            settings.setAttribute(QWebSettings.DeveloperExtrasEnabled, True)
        QWebSettings.enablePersistentStorage(os.path.join(cache_dir(),
                'webkit-persistence'))
        QWebSettings.setMaximumPagesInCache(0)
        self.bridge_name = 'b' + uuid.uuid4().get_hex()
        self.mainFrame().javaScriptWindowObjectCleared.connect(
                self.add_window_objects)
        self.dom_loaded = False

    def add_window_objects(self):
        self.dom_loaded = False
        mf = self.mainFrame()
        mf.addToJavaScriptWindowObject(self.bridge_name, self)
        mf.evaluateJavaScript('document.addEventListener( "DOMContentLoaded", %s.content_loaded, false )' % self.bridge_name)

    def load_url(self, url):
        self.dom_loaded = False
        url = QUrl(url)
        self.mainFrame().load(url)
        self.ready_state  # Without this, DOMContentLoaded does not fire for file:// URLs

    @pyqtSlot()
    def content_loaded(self):
        self.dom_loaded = True

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

    @pyqtSlot(result=bool)
    def shouldInterruptJavaScript(self):
        if self.view() is not None:
            return QWebPage.shouldInterruptJavaScript(self)
        return True

    def on_unsupported_content(self, reply):
        self.log.warn('Unsupported content, ignoring: %s'%reply.url())

    @property
    def ready_state(self):
        return unicode(self.mainFrame().evaluateJavaScript('document.readyState').toString())

    @pyqtSlot(QPixmap)
    def transfer_image(self, img):
        self.saved_img = img

    def get_image(self, qwe_or_selector):
        qwe = qwe_or_selector
        if not isinstance(qwe, QWebElement):
            qwe = self.mainFrame().findFirstElement(qwe)
            if qwe.isNull():
                raise ValueError('Failed to find element with selector: %r'
                        % qwe_or_selector)
        self.saved_img = QPixmap()
        qwe.evaluateJavaScript('%s.transfer_image(this)' % self.bridge_name)
        try:
            return self.saved_img
        finally:
            del self.saved_img


# }}}

class ProxyFactory(QNetworkProxyFactory):  # {{{

    def __init__(self, log):
        QNetworkProxyFactory.__init__(self)
        proxies = get_proxies()
        self.proxies = {}
        for scheme, proxy_string in proxies.iteritems():
            scheme = scheme.lower()
            info = get_proxy_info(scheme, proxy_string)
            if info is None:
                continue
            hn, port = info['hostname'], info['port']
            if not hn or not port:
                continue
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

class NetworkAccessManager(QNetworkAccessManager):  # {{{

    OPERATION_NAMES = {getattr(QNetworkAccessManager, '%sOperation'%x) :
            x.upper() for x in ('Head', 'Get', 'Put', 'Post', 'Delete',
                'Custom')
    }
    report_reply_signal = pyqtSignal(object)

    def __init__(self, log, disk_cache_size=50, parent=None):
        QNetworkAccessManager.__init__(self, parent)
        self.reply_count = 0
        self.log = log
        if disk_cache_size > 0:
            self.cache = QNetworkDiskCache(self)
            self.cache.setCacheDirectory(PersistentTemporaryDirectory(prefix='disk_cache_'))
            self.cache.setMaximumCacheSize(int(disk_cache_size * 1024 * 1024))
            self.setCache(self.cache)
        self.sslErrors.connect(self.on_ssl_errors)
        self.pf = ProxyFactory(log)
        self.setProxyFactory(self.pf)
        self.finished.connect(self.on_finished)
        self.cookie_jar = QNetworkCookieJar()
        self.setCookieJar(self.cookie_jar)
        self.main_thread = current_thread()
        self.report_reply_signal.connect(self.report_reply, type=Qt.QueuedConnection)

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
        if current_thread() is not self.main_thread:
            # This method was called in a thread created by Qt. The python
            # interpreter may not be in a safe state, so dont do anything
            # more. This signal is queued which means the reply wont be
            # reported unless someone spins the event loop. So far, I have only
            # seen this happen when doing Ctrl+C in the console.
            self.report_reply_signal.emit(reply)
        else:
            self.report_reply(reply)

    def report_reply(self, reply):
        reply_url = unicode(reply.url().toString())
        self.reply_count += 1
        err = reply.error()

        if err:
            l = self.log.debug if err == reply.OperationCanceledError else self.log.warn
            l("Reply error: %s - %d (%s)" % (reply_url, err, unicode(reply.errorString())))
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

    def py_cookies(self):
        for c in self.cookie_jar.allCookies():
            name, value = map(bytes, (c.name(), c.value()))
            domain = bytes(c.domain())
            initial_dot = domain_specified = domain.startswith(b'.')
            secure = bool(c.isSecure())
            path = unicode(c.path()).strip().encode('utf-8')
            expires = c.expirationDate()
            is_session_cookie = False
            if expires.isValid():
                expires = expires.toTime_t()
            else:
                expires = None
                is_session_cookie = True
            path_specified = True
            if not path:
                path = b'/'
                path_specified = False
            c = Cookie(0,  # version
                    name, value,
                    None,  # port
                    False,  # port specified
                    domain, domain_specified, initial_dot, path,
                    path_specified,
                    secure, expires, is_session_cookie,
                    None,  # Comment
                    None,  # Comment URL
                    {}  # rest
            )
            yield c
# }}}

class LoadWatcher(QObject):  # {{{

    def __init__(self, page, parent=None):
        QObject.__init__(self, parent)
        self.is_loading = True
        self.loaded_ok = None
        page.loadFinished.connect(self)
        self.page = page

    def __call__(self, ok):
        self.loaded_ok = ok
        self.is_loading = False
        self.page.loadFinished.disconnect(self)
        self.page = None
# }}}

class BrowserView(QDialog):  # {{{

    def __init__(self, page, parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)
        self.webview = QWebView(self)
        l.addWidget(self.webview)
        self.resize(QSize(1024, 768))
        self.webview.setPage(page)

# }}}

class Browser(QObject, FormsMixin):

    '''
    Browser (WebKit with no GUI).

    This browser is NOT thread safe. Use it in a single thread only! If you
    need to run downloads in parallel threads, use multiple browsers (after
    copying the cookies).
    '''

    def __init__(self,
            # Logging. If None, uses a default log, which does not output
            # debugging info
            log=None,
            # Receives a string and returns True/False. By default, returns
            # True for all strings
            confirm_callback=None,

            # Prompt callback. Receives a msg string and a default value
            # string. Should return the user input value or None if the user
            # canceled the prompt. By default returns None.
            prompt_callback=None,

            # User agent to be used
            user_agent=USER_AGENT,

            # The size (in MB) of the on disk cache. Note that because the disk
            # cache cannot be shared between different instances, we currently
            # use a temporary dir for the cache, which is deleted on
            # program exit. Set to zero to disable cache.
            disk_cache_size=50,

            # Enable Inspect element functionality
            enable_developer_tools=False,

            # Verbosity
            verbosity=0,

            # The default timeout (in seconds)
            default_timeout=30
        ):
        must_use_qt()
        QObject.__init__(self)
        FormsMixin.__init__(self)

        if log is None:
            log = ThreadSafeLog()
        if verbosity:
            log.filter_level = log.DEBUG
        self.log = log
        self.default_timeout = default_timeout

        self.page = WebPage(log, confirm_callback=confirm_callback,
                prompt_callback=prompt_callback, user_agent=user_agent,
                enable_developer_tools=enable_developer_tools,
                parent=self)
        self.nam = NetworkAccessManager(log, disk_cache_size=disk_cache_size, parent=self)
        self.page.setNetworkAccessManager(self.nam)

    @property
    def user_agent(self):
        return self.page.user_agent

    def _wait_for_load(self, timeout, url=None):
        timeout = self.default_timeout if timeout is default_timeout else timeout
        loop = QEventLoop(self)
        start_time = time.time()
        end_time = start_time + timeout
        lw = LoadWatcher(self.page, parent=self)
        while lw.is_loading and end_time > time.time():
            if not loop.processEvents():
                time.sleep(0.01)
        if lw.is_loading:
            raise Timeout('Loading of %r took longer than %d seconds'%(
                url, timeout))

        return lw.loaded_ok

    def _wait_for_replies(self, reply_count, timeout):
        final_time = time.time() + timeout
        loop = QEventLoop(self)
        while (time.time() < final_time and self.nam.reply_count <
                reply_count):
            loop.processEvents()
            time.sleep(0.1)
        if self.nam.reply_count < reply_count:
            raise Timeout('Waiting for replies took longer than %d seconds' %
                    timeout)

    def run_for_a_time(self, timeout):
        final_time = time.time() + timeout
        loop = QEventLoop(self)
        while (time.time() < final_time):
            if not loop.processEvents():
                time.sleep(0.1)

    def wait_for_element(self, selector, timeout=default_timeout):
        timeout = self.default_timeout if timeout is default_timeout else timeout
        start_time = time.time()
        while self.css_select(selector) is None:
            self.run_for_a_time(0.1)
            if time.time() - start_time > timeout:
                raise Timeout('DOM failed to load in %.1g seconds' % timeout)
        return self.css_select(selector)

    def visit(self, url, timeout=default_timeout):
        '''
        Open the page specified in URL and wait for it to complete loading.
        Note that when this method returns, there may still be javascript
        that needs to execute (this method returns when the loadFinished()
        signal is called on QWebPage). This method will raise a Timeout
        exception if loading takes more than timeout seconds.

        Returns True if loading was successful, False otherwise.
        '''
        self.current_form = None
        self.page.load_url(url)
        return self._wait_for_load(timeout, url)

    def back(self, wait_for_load=True, timeout=default_timeout):
        '''
        Like clicking the back button in the browser. Waits for loading to complete.
        This method will raise a Timeout exception if loading takes more than timeout seconds.

        Returns True if loading was successful, False otherwise.
        '''
        self.page.triggerAction(self.page.Back)
        if wait_for_load:
            return self._wait_for_load(timeout)

    def stop(self):
        'Stop loading of current page'
        self.page.triggerAction(self.page.Stop)

    def stop_scheduled_refresh(self):
        'Stop any scheduled page refresh/reloads'
        self.page.triggerAction(self.page.StopScheduledPageRefresh)

    def reload(self, bypass_cache=False):
        action = self.page.ReloadAndBypassCache if bypass_cache else self.page.Reload
        self.page.triggerAction(action)

    @property
    def dom_ready(self):
        return self.page.dom_loaded

    def wait_till_dom_ready(self, timeout=default_timeout, url=None):
        timeout = self.default_timeout if timeout is default_timeout else timeout
        start_time = time.time()
        while not self.dom_ready:
            if time.time() - start_time > timeout:
                raise Timeout('Loading of %r took longer than %d seconds'%(
                    url, timeout))
            self.run_for_a_time(0.1)

    def start_load(self, url, timeout=default_timeout, selector=None):
        '''
        Start the loading of the page at url and return once the DOM is ready,
        sub-resources such as scripts/stylesheets/images/etc. may not have all
        loaded.
        '''
        self.current_form = None
        self.page.load_url(url)
        if selector is not None:
            self.wait_for_element(selector, timeout=timeout, url=url)
        else:
            self.wait_till_dom_ready(timeout=timeout, url=url)

    def click(self, qwe_or_selector, wait_for_load=True, ajax_replies=0, timeout=default_timeout):
        '''
        Click the :class:`QWebElement` pointed to by qwe_or_selector.

        :param wait_for_load: If you know that the click is going to cause a
                              new page to be loaded, set this to True to have
                              the method block until the new page is loaded
        :para ajax_replies: Number of replies to wait for after clicking a link
                            that triggers some AJAX interaction
        '''
        initial_count = self.nam.reply_count
        qwe = qwe_or_selector
        if not isinstance(qwe, QWebElement):
            qwe = self.css_select(qwe)
            if qwe is None:
                raise ValueError('Failed to find element with selector: %r'
                        % qwe_or_selector)
        js = '''
            var e = document.createEvent('MouseEvents');
            e.initEvent( 'click', true, true );
            this.dispatchEvent(e);
        '''
        qwe.evaluateJavaScript(js)
        if ajax_replies > 0:
            reply_count = initial_count + ajax_replies
            self._wait_for_replies(reply_count, timeout)
        elif wait_for_load and not self._wait_for_load(timeout):
            raise LoadError('Clicking resulted in a failed load')

    def click_text_link(self, text_or_regex, selector='a[href]',
            wait_for_load=True, ajax_replies=0, timeout=default_timeout):
        target = None
        for qwe in self.page.mainFrame().findAllElements(selector):
            src = unicode(qwe.toPlainText())
            if hasattr(text_or_regex, 'match') and text_or_regex.search(src):
                target = qwe
                break
            if src.lower() == text_or_regex.lower():
                target = qwe
                break
        if target is None:
            raise ValueError('No element matching %r with text %s found'%(
                selector, text_or_regex))
        return self.click(target, wait_for_load=wait_for_load,
                ajax_replies=ajax_replies, timeout=timeout)

    def css_select(self, selector, all=False):
        if all:
            return tuple(self.page.mainFrame().findAllElements(selector).toList())
        ans = self.page.mainFrame().findFirstElement(selector)
        if ans.isNull():
            ans = None
        return ans

    def get_image(self, qwe_or_selector):
        '''
        Return the image identified by qwe_or_selector as a QPixmap. If no such
        image exists, the returned pixmap will be null.
        '''
        return self.page.get_image(qwe_or_selector)

    def get_cached(self, url):
        iod = self.nam.cache.data(QUrl(url))
        if iod is not None:
            try:
                return bytes(bytearray(iod.readAll()))
            finally:
                # Ensure the IODevice is closed right away, so that the
                # underlying file can be deleted if the space is needed,
                # otherwise on windows the file stays locked
                iod.close()
                del iod

    def wait_for_resources(self, urls, timeout=default_timeout):
        timeout = self.default_timeout if timeout is default_timeout else timeout
        start_time = time.time()
        ans = {}
        urls = set(urls)

        def get_resources():
            for url in tuple(urls):
                raw = self.get_cached(url)
                if raw is not None:
                    ans[url] = raw
                    urls.discard(url)

        while urls and time.time() - start_time > timeout and self.page.ready_state not in {'complete', 'completed'}:
            get_resources()
            if urls:
                self.run_for_a_time(0.1)

        if urls:
            get_resources()
        return ans

    def get_resource(self, url, rtype='img', use_cache=True, timeout=default_timeout):
        '''
        Download a resource (image/stylesheet/script). The resource is
        downloaded by visiting an simple HTML page that contains only that
        resource. The resource is then returned from the cache (therefore, to
        use this method you must not disable the cache). If use_cache is True
        then the cache is queried before loading the resource. This can result
        in a stale object if the resource has changed on the server, however,
        it is a big performance boost in the common case, by avoiding a
        roundtrip to the server. The resource is returned as a bytestring or None
        if it could not be loaded.
        '''
        if not hasattr(self.nam, 'cache'):
            raise RuntimeError('Cannot get resources when the cache is disabled')
        if use_cache:
            ans = self.get_cached(url)
            if ans is not None:
                return ans
        try:
            tag = {
                'img': '<img src="%s">',
                'link': '<link href="%s"></link>',
                'script': '<script src="%s"></script>',
            }[rtype] % prepare_string_for_xml(url, attribute=True)
        except KeyError:
            raise ValueError('Unknown resource type: %s' % rtype)

        self.page.mainFrame().setHtml(
            '''<!DOCTYPE html><html><body><div>{0}</div></body></html>'''.format(tag))
        self._wait_for_load(timeout)
        ans = self.get_cached(url)
        if ans is not None:
            return ans

    def show_browser(self):
        '''
        Show the currently loaded web page in a window. Useful for debugging.
        '''
        view = BrowserView(self.page)
        view.exec_()

    @property
    def cookies(self):
        '''
        Return all the cookies set currently as :class:`Cookie` objects.
        Returns expired cookies as well.
        '''
        return list(self.nam.py_cookies())

    @property
    def html(self):
        return unicode(self.page.mainFrame().toHtml())

    def blank(self):
        try:
            self.visit('about:blank', timeout=0.01)
        except Timeout:
            pass

    def close(self):
        self.stop()
        self.blank()
        self.stop()
        self.nam.setCache(QNetworkDiskCache())
        self.nam.cache = None
        self.nam = self.page = None

    def __enter__(self):
        pass

    def __exit__(self, *args):
        self.close()



