#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


from calibre.db.tests.base import BaseTest


class FTSTest(BaseTest):

    def test_basic_fts(self):  # {{{
        from apsw import Connection
        from calibre.constants import plugins

        conn = Connection(':memory:')
        plugins.load_apsw_extension(conn, 'sqlite_extension')
    # }}}
