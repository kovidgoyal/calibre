#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QThread

from calibre.utils.dictclient import Connection

class Lookup(QThread):

    TEMPLATE = u'''<html>
    <body>
    <div>
    {0}
    </div>
    </body>
    </html>
    '''

    def __init__(self, word, parent=None):
        QThread.__init__(self, parent)

        self.word = word.encode('utf-8') if isinstance(word, unicode) else word
        self.result = self.traceback = self.exception = None

    def define(self):
        conn = Connection('dict.org')
        self.result = conn.define('!', self.word)
        if self.result:
            self.result = self.result[0].defstr

    def run(self):
        try:
            self.define()
        except Exception as e:
            import traceback
            self.exception = e
            self.traceback = traceback.format_exc()

    def format_exception(self):
        lines = ['<b>Failed to connect to dict.org</b>', '']
        lines += self.traceback.splitlines()
        ans = '<br>'.join(lines)
        if not isinstance(ans, unicode):
            ans = ans.decode('utf-8')
        return self.TEMPLATE.format(ans)

    def no_results(self):
        ans = _('No results found for:') + ' ' + self.word.decode('utf-8')
        return self.TEMPLATE.format(ans)

    @property
    def html_result(self):
        if self.exception is not None:
            return self.format_exception()
        if not self.result:
            return self.no_results()
        lines = self.result.splitlines()
        lines[0] = '<b>'+lines[0]+'</b>'

        ans = '<br>'.join(lines)
        if not isinstance(ans, unicode):
            ans = ans.decode('utf-8')
        return self.TEMPLATE.format(ans)

