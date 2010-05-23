#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import time

from calibre import strftime as _strftime, prints
from calibre.utils.date import now as nowf


def expose(func):
    import cherrypy

    def do(self, *args, **kwargs):
        dict.update(cherrypy.response.headers, {'Server':self.server_name})
        if not self.embedded:
            self.db.check_if_modified()
        return func(self, *args, **kwargs)

    return cherrypy.expose(do)

def timeit(func):

    def do(self, *args, **kwargs):
        if self.opts.develop:
            start = time.time()
        ans = func(self, *args, **kwargs)
        if self.opts.develop:
            prints('Function', func.__name__, 'called with args:', args, kwargs)
            prints('\tTime:', func.__name__, time.time()-start)
        return ans

    return do

def strftime(fmt='%Y/%m/%d %H:%M:%S', dt=None):
    if not hasattr(dt, 'timetuple'):
        dt = nowf()
    dt = dt.timetuple()
    try:
        return _strftime(fmt, dt)
    except:
        return _strftime(fmt, nowf().timetuple())


