__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import re
from PyQt4.QtGui import QDialog

from calibre.gui2.dialogs.search_ui import Ui_Dialog
from calibre.gui2 import qstring_to_unicode


class SearchDialog(QDialog, Ui_Dialog):

    def __init__(self, *args):
        QDialog.__init__(self, *args)
        self.setupUi(self)

    def tokens(self, raw):
        phrases = re.findall(r'\s+".*?"\s+', raw)
        for f in phrases:
            raw = raw.replace(f, ' ')
        return [t.strip() for t in phrases + raw.split()]

    def search_string(self):
        all, any, phrase, none = map(lambda x: unicode(x.text()),
                (self.all, self.any, self.phrase, self.none))
        all, any, none = map(self.tokens, (all, any, none))
        phrase = phrase.strip()
        all = ' and '.join(all)
        any = ' or '.join(any)
        none = ' and not '.join(none)
        ans = ''
        if phrase:
            ans += '"%s"'%phrase
        if all:
            ans += (' and ' if ans else '') + all
        if none:
            ans += (' and not ' if ans else 'not') + none
        if any:
            ans += (' or ' if ans else '') + any
        return ans

    def token(self):
        txt = qstring_to_unicode(self.text.text()).strip()
        if txt:
            if self.negate.isChecked():
                txt = '!'+txt
            tok = self.FIELDS[qstring_to_unicode(self.field.currentText())]+txt
            if re.search(r'\s', tok):
                tok = '"%s"'%tok
            return tok

