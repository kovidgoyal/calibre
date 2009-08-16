"""Default URL reading functions"""
__all__ = ['_defaultFetcher']
__docformat__ = 'restructuredtext'
__version__ = '$Id: tokenize2.py 1547 2008-12-10 20:42:26Z cthedot $'

from cssutils import VERSION
import encutils
import errorhandler
import urllib2
import util

log = errorhandler.ErrorHandler()

def _defaultFetcher(url):
    """Retrieve data from ``url``. cssutils default implementation of fetch
    URL function.

    Returns ``(encoding, string)`` or ``None``
    """
    request = urllib2.Request(url)
    request.add_header('User-agent', 
                       'cssutils %s (http://www.cthedot.de/cssutils/)' % VERSION)
    try:        
        res = urllib2.urlopen(request)
    except OSError, e:
        # e.g if file URL and not found
        log.warn(e, error=OSError)
    except (OSError, ValueError), e:
        # invalid url, e.g. "1"
        log.warn(u'ValueError, %s' % e.args[0], error=ValueError)
    except urllib2.HTTPError, e:
        # http error, e.g. 404, e can be raised
        log.warn(u'HTTPError opening url=%r: %s %s' % 
                          (url, e.code, e.msg), error=e)
    except urllib2.URLError, e:
        # URLError like mailto: or other IO errors, e can be raised
        log.warn(u'URLError, %s' % e.reason, error=e)
    else:
        if res:
            mimeType, encoding = encutils.getHTTPInfo(res)
            if mimeType != u'text/css':
                log.error(u'Expected "text/css" mime type for url=%r but found: %r' % 
                                  (url, mimeType), error=ValueError)
            return encoding, res.read()
