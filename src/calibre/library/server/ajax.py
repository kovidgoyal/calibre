#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json
from functools import wraps

import cherrypy

from calibre.utils.date import isoformat
from calibre.utils.config import prefs
from calibre.ebooks.metadata.book.json_codec import JsonCodec

class Endpoint(object): # {{{
    'Manage mime-type json serialization, etc.'

    def __init__(self, mimetype='application/json; charset=utf-8',
            set_last_modified=True):
        self.mimetype = mimetype
        self.set_last_modified = set_last_modified

    def __call__(eself, func):

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Remove AJAX caching disabling jquery workaround arg
            # This arg is put into AJAX queries by jQuery to prevent
            # caching in the browser. We dont want it passed to the wrapped
            # function
            kwargs.pop('_', None)

            ans = func(self, *args, **kwargs)
            cherrypy.response.headers['Content-Type'] = eself.mimetype
            if eself.set_last_modified:
                updated = self.db.last_modified()
                cherrypy.response.headers['Last-Modified'] = \
                    self.last_modified(max(updated, self.build_time))
            if 'application/json' in eself.mimetype:
                ans = json.dumps(ans, indent=2,
                        ensure_ascii=False).encode('utf-8')
            return ans

        return wrapper
# }}}

class AjaxServer(object):

    def __init__(self):
        self.ajax_json_codec = JsonCodec()

    def add_routes(self, connect):
        base_href = '/ajax'
        connect('ajax_book', base_href+'/book/{book_id}', self.ajax_book)
        connect('ajax_categories', base_href+'/categories',
                self.ajax_categories)

    # Get book metadata {{{
    @Endpoint()
    def ajax_book(self, book_id):
        cherrypy.response.headers['Content-Type'] = \
                'application/json; charset=utf-8'
        try:
            book_id = int(book_id)
            mi = self.db.get_metadata(book_id, index_is_id=True)
        except:
            raise cherrypy.HTTPError(404, 'No book with id: %r'%book_id)
        try:
            mi.rating = mi.rating/2.
        except:
            mi.rating = 0.0
        cherrypy.response.timeout = 3600
        cherrypy.response.headers['Last-Modified'] = \
                self.last_modified(mi.last_modified)

        data = self.ajax_json_codec.encode_book_metadata(mi)
        for x in ('publication_type', 'size', 'db_id', 'lpath', 'mime',
                'rights', 'book_producer'):
            data.pop(x, None)

        def absurl(url):
            return self.opts.url_prefix + url

        data['cover'] = absurl(u'/get/cover/%d'%book_id)
        data['thumbnail'] = absurl(u'/get/thumb/%d'%book_id)
        mi.format_metadata = {k.lower():dict(v) for k, v in
                mi.format_metadata.iteritems()}
        for v in mi.format_metadata.itervalues():
            mtime = v.get('mtime', None)
            if mtime is not None:
                v['mtime'] = isoformat(mtime, as_utc=True)
        data['format_metadata'] = mi.format_metadata
        fmts = set(x.lower() for x in mi.format_metadata.iterkeys())
        pf = prefs['output_format'].lower()
        other_fmts = list(fmts)
        try:
            fmt = pf if pf in fmts else other_fmts[0]
        except:
            fmt = None
        if fmts and fmt:
            other_fmts = [x for x in fmts if x != fmt]
        data['formats'] = sorted(fmts)
        if fmt:
            data['main_format'] = {fmt: absurl(u'/get/%s/%d'%(fmt, book_id))}
        else:
            data['main_format'] = None
        data['other_formats'] = {fmt: absurl(u'/get/%s/%d'%(fmt, book_id)) for fmt
                in other_fmts}

        return data
    # }}}

    @Endpoint()
    def ajax_categories(self):
        pass
