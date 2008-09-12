# urllib2 work-alike interface
# ...from urllib2...
from urllib2 import \
     URLError, \
     HTTPError, \
     GopherError
# ...and from mechanize
from _opener import OpenerDirector, \
     SeekableResponseOpener, \
     build_opener, install_opener, urlopen
from _auth import \
     HTTPPasswordMgr, \
     HTTPPasswordMgrWithDefaultRealm, \
     AbstractBasicAuthHandler, \
     AbstractDigestAuthHandler, \
     HTTPProxyPasswordMgr, \
     ProxyHandler, \
     ProxyBasicAuthHandler, \
     ProxyDigestAuthHandler, \
     HTTPBasicAuthHandler, \
     HTTPDigestAuthHandler, \
     HTTPSClientCertMgr
from _request import \
     Request
from _http import \
     RobotExclusionError

# handlers...
# ...from urllib2...
from urllib2 import \
     BaseHandler, \
     UnknownHandler, \
     FTPHandler, \
     CacheFTPHandler, \
     FileHandler, \
     GopherHandler
# ...and from mechanize
from _http import \
     HTTPHandler, \
     HTTPDefaultErrorHandler, \
     HTTPRedirectHandler, \
     HTTPEquivProcessor, \
     HTTPCookieProcessor, \
     HTTPRefererProcessor, \
     HTTPRefreshProcessor, \
     HTTPErrorProcessor, \
     HTTPRobotRulesProcessor
from _upgrade import \
     HTTPRequestUpgradeProcessor, \
     ResponseUpgradeProcessor
from _debug import \
     HTTPResponseDebugProcessor, \
     HTTPRedirectDebugProcessor
from _seek import \
     SeekableProcessor
# crap ATM
## from _gzip import \
##      HTTPGzipProcessor
import httplib
if hasattr(httplib, 'HTTPS'):
    from _http import HTTPSHandler
del httplib
