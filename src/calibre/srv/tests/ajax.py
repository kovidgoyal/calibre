#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import httplib, zlib, json

from calibre.srv.tests.base import LibraryBaseTest

class ContentTest(LibraryBaseTest):

    def test_ajax_book(self):  # {{{
        'Test /ajax/book'
        with self.create_server() as server:
            db = server.handler.router.ctx.get_library()
            conn = server.connect()

            def request(url, headers={}):
                conn.request('GET', '/ajax/book' + url, headers=headers)
                r = conn.getresponse()
                data = r.read()
                if r.status == httplib.OK and data.startswith(b'{'):
                    data = json.loads(data)
                return r, data

            r, data = request('/x')
            self.ae(r.status, httplib.NOT_FOUND)

            r, onedata = request('/1')
            self.ae(r.status, httplib.OK)
            self.ae(request('/1/' + db.server_library_id)[1], onedata)
            self.ae(request('/%s?id_is_uuid=true' % db.field_for('uuid', 1))[1], onedata)

            r, data = request('s')
            self.ae(set(data.iterkeys()), set(map(str, db.all_book_ids())))
            r, zdata = request('s', headers={'Accept-Encoding':'gzip'})
            self.ae(r.getheader('Content-Encoding'), 'gzip')
            self.ae(json.loads(zlib.decompress(zdata, 16+zlib.MAX_WBITS)), data)
            r, data = request('s?ids=1,2')
            self.ae(set(data.iterkeys()), {'1', '2'})

    # }}}
