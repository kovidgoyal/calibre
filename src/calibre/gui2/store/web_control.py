# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from cookielib import Cookie, CookieJar

from PyQt4.Qt import QWebView, QWebPage, QNetworkCookieJar, QNetworkRequest, QString

class NPWebView(QWebView):
    
    def __init__(self, *args):
        QWebView.__init__(self, *args)
        self.gui = None

        #self.setPage(NPWebPage())
        self.page().networkAccessManager().setCookieJar(QNetworkCookieJar())
        self.page().setForwardUnsupportedContent(True)
        self.page().unsupportedContent.connect(self.start_download)
        self.page().downloadRequested.connect(self.start_download)
        self.page().networkAccessManager().sslErrors.connect(self.ignore_ssl_errors)
        #self.page().networkAccessManager().finished.connect(self.fin)
    
    def createWindow(self, type):
        if type == QWebPage.WebBrowserWindow:
            return self
        else:
            return None

    def set_gui(self, gui):
        self.gui = gui
        
    def start_download(self, request):
        if not self.gui:
            print 'no gui'
            return
        
        url = unicode(request.url().toString())
        self.gui.download_from_store(url, self.get_cookies())

    def ignore_ssl_errors(self, reply, errors):
        reply.ignoreSslErrors(errors)
        
    def fin(self, reply):
        if reply.error():
            print 'error'
            print reply.error()
            #print reply.attribute(QNetworkRequest.HttpStatusCodeAttribute).toInt()
            
    def get_cookies(self):
        cj = CookieJar()
        
        for c in self.page().networkAccessManager().cookieJar().allCookies():
            version = 0
            name = unicode(QString(c.name()))
            value = unicode(QString(c.value()))
            port = None
            port_specified = False
            domain = unicode(c.domain())
            if domain:
                domain_specified = True
                if domain.startswith('.'):
                    domain_initial_dot = True
                else:
                    domain_initial_dot = False
            else:
                domain = None
                domain_specified = False
            path = unicode(c.path())
            if path:
                path_specified = True
            else:
                path = None
                path_specified = False
            secure = c.isSecure()
            expires = c.expirationDate().toMSecsSinceEpoch() / 1000
            discard = c.isSessionCookie()
            comment = None
            comment_url = None
            rest = None
            
            cookie = Cookie(version, name, value,
                 port, port_specified,
                 domain, domain_specified, domain_initial_dot,
                 path, path_specified,
                 secure,
                 expires,
                 discard,
                 comment,
                 comment_url,
                 rest) 
            
            cj.set_cookie(cookie)
            
        return cj


class NPWebPage(QWebPage):
    
    def userAgentForUrl(self, url):
        return 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_6; en-US) AppleWebKit/534.13 (KHTML, like Gecko) Chrome/9.0.597.102 Safari/534.13'
