#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time, sys, hashlib, binascii, random, os
from urllib import quote as quote_, unquote as unquote_
from functools import wraps

import cherrypy
from cherrypy.lib.auth_digest import digest_auth, get_ha1_dict_plain

from calibre import strftime as _strftime, prints, isbytestring
from calibre.utils.date import now as nowf
from calibre.utils.config import tweaks
from calibre.utils.icu import sort_key

class Offsets(object):
    'Calculate offsets for a paginated view'

    def __init__(self, offset, delta, total):
        if offset < 0:
            offset = 0
        if offset >= total:
            raise cherrypy.HTTPError(404, 'Invalid offset: %r'%offset)
        last_allowed_index = total - 1
        last_current_index = offset + delta - 1
        self.slice_upper_bound = offset+delta
        self.offset = offset
        self.next_offset = last_current_index + 1
        if self.next_offset > last_allowed_index:
            self.next_offset = -1
        self.previous_offset = self.offset - delta
        if self.previous_offset < 0:
            self.previous_offset = 0
        self.last_offset = last_allowed_index - delta
        if self.last_offset < 0:
            self.last_offset = 0


def expose(func):

    @wraps(func)
    def do(*args, **kwargs):
        self = func.im_self
        if self.opts.develop:
            start = time.time()

        dict.update(cherrypy.response.headers, {'Server':self.server_name})
        if not self.embedded:
            self.db.check_if_modified()
        ans = func(*args, **kwargs)
        if self.opts.develop:
            prints('Function', func.__name__, 'called with args:', args, kwargs)
            prints('\tTime:', func.__name__, time.time()-start)
        return ans

    return do

class AuthController(object):

    '''
    Implement Digest authentication for the content server. Android browsers
    cannot handle HTTP AUTH when downloading files, as the download is handed
    off to a separate process. So we use a cookie based authentication scheme
    for some endpoints (/get) to allow downloads to work on android. Apparently,
    cookies are passed to the download process. The cookie expires after
    MAX_AGE seconds.

    The android browser appears to send a GET request to the server and only if
    that request succeeds is the download handed off to the download process.
    Therefore, even if the user clicks Get after MAX_AGE, it should still work.
    In fact, we could reduce MAX_AGE, but we leave it high as the download
    process might have downloads queued and therefore not start the download
    immediately.

    Note that this makes the server vulnerable to session-hijacking (i.e. some
    one can sniff the traffic and create their own requests to /get with the
    appropriate cookie, for an hour). The fix is to use https, but since this
    is usually run as a private server, that cannot be done. If you care about
    this vulnerability, run the server behind a reverse proxy that uses HTTPS.
    '''

    MAX_AGE = 3600 # Number of seconds after a successful digest auth for which
                   # the cookie auth will be allowed

    def __init__(self, realm, users_dict):
        self.realm = realm
        self.users_dict = users_dict
        self.secret = bytes(binascii.hexlify(os.urandom(random.randint(20,
            30))))
        self.cookie_name = 'android_workaround'
        self.key_order = random.choice(('%(t)s:%(s)s', '%(s)s:%(t)s'))

    def hashit(self, raw):
        return hashlib.sha256(raw).hexdigest()

    def __call__(self, func, allow_cookie_auth):

        @wraps(func)
        def authenticate(*args, **kwargs):
            cookie = cherrypy.request.cookie.get(self.cookie_name, None)
            ua = cherrypy.request.headers.get('User-Agent', '').strip()

            if ('iPad;' in ua or 'iPhone;' in ua or (
                not (allow_cookie_auth and self.is_valid(cookie)))):
                # Apparently the iPad cant handle this
                # see https://bugs.launchpad.net/bugs/1013976
                digest_auth(self.realm, get_ha1_dict_plain(self.users_dict),
                            self.secret)

            cookie = cherrypy.response.cookie
            cookie[self.cookie_name] = self.generate_cookie()
            cookie[self.cookie_name]['path'] = '/'
            cookie[self.cookie_name]['version'] = '1'

            return func(*args, **kwargs)

        authenticate.im_self = func.im_self
        return authenticate

    def generate_cookie(self, timestamp=None):
        '''
        Generate a cookie. The cookie contains a plain text timestamp and a
        hash of the timestamp and the server secret.
        '''
        timestamp = int(time.time()) if timestamp is None else timestamp
        key = self.hashit(self.key_order%dict(t=timestamp, s=self.secret))
        return '%d:%s'%(timestamp, key)

    def is_valid(self, cookie):
        '''
        Check that cookie has not been spoofed (i.e. verify the declared
        timestamp against the hashed timestamp). If the timestamps match, check
        that the cookie has not expired. Return True iff the cookie has not
        been spoofed and has not expired.
        '''
        try:
            timestamp, hashpart = cookie.value.split(':', 1)
            timestamp = int(timestamp)
        except:
            return False
        s_timestamp, s_hashpart = self.generate_cookie(timestamp).split(':', 1)
        is_valid = s_hashpart == hashpart
        return (is_valid and (time.time() - timestamp) < self.MAX_AGE)

def strftime(fmt='%Y/%m/%d %H:%M:%S', dt=None):
    if not hasattr(dt, 'timetuple'):
        dt = nowf()
    dt = dt.timetuple()
    try:
        return _strftime(fmt, dt)
    except:
        return _strftime(fmt, nowf().timetuple())

def format_tag_string(tags, sep, ignore_max=False, no_tag_count=False, joinval=', '):
    MAX = sys.maxint if ignore_max else tweaks['max_content_server_tags_shown']
    if tags:
        tlist = [t.strip() for t in tags.split(sep)]
    else:
        tlist = []
    tlist.sort(key=sort_key)
    if len(tlist) > MAX:
        tlist = tlist[:MAX]+['...']
    if no_tag_count:
        return joinval.join(tlist) if tlist else ''
    else:
        return u'%s:&:%s'%(tweaks['max_content_server_tags_shown'],
                     joinval.join(tlist)) if tlist else ''

def quote(s):
    if isinstance(s, unicode):
        s = s.encode('utf-8')
    return quote_(s)

def unquote(s):
    ans = unquote_(s)
    if isbytestring(ans):
        ans = ans.decode('utf-8')
    return ans

def cookie_time_fmt(time_t):
    return time.strftime('%a, %d-%b-%Y %H:%M:%S GMT', time_t)

def cookie_max_age_to_expires(max_age):
    gmt_expiration_time = time.gmtime(time.time() + max_age)
    return cookie_time_fmt(gmt_expiration_time)

