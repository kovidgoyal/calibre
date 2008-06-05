__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import re
from PyQt4.QtGui import QWidget, QDialog, QVBoxLayout
from PyQt4.QtCore import SIGNAL

from calibre.gui2.dialogs.search_ui import Ui_Dialog
from calibre.gui2.dialogs.search_item_ui import Ui_Form
from calibre.gui2 import qstring_to_unicode

class SearchItem(Ui_Form, QWidget):
    
    FIELDS = {
              _('Title')     : 'title:',
              _('Author')    : 'author:',
              _('Publisher') : 'publisher:',
              _('Tag')       : 'tag:',
              _('Series')    : 'series:',
              _('Format')    : 'format:',
              _('Comments')  : 'comments:',
              _('Any')       :''
              }
    
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.setupUi(self)
        
        for field in self.FIELDS.keys():
            self.field.addItem(field)
            
    def token(self):
        txt = qstring_to_unicode(self.text.text()).strip()
        if txt:
            if self.negate.isChecked():
                txt = '!'+txt
            tok = self.FIELDS[qstring_to_unicode(self.field.currentText())]+txt
            if re.search(r'\s', tok):
                tok = '"%s"'%tok
            return tok
            
        
        
class SearchDialog(Ui_Dialog, QDialog):
    
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        
        self.tokens = []
        self.token_layout = QVBoxLayout()
        self.search_items_frame.setLayout(self.token_layout)
        self.add_token()
        self.add_token()
        
        self.connect(self.fewer_button, SIGNAL('clicked()'), self.remove_token)
        self.connect(self.more_button, SIGNAL('clicked()'), self.add_token)
        
    def remove_token(self):
        if self.tokens:
            tok = self.tokens[-1]
            self.tokens = self.tokens[:-1]
            self.token_layout.removeWidget(tok)
            tok.setVisible(False)
    
    def add_token(self):
        tok = SearchItem(self)
        self.token_layout.addWidget(tok)
        self.tokens.append(tok)
        
    def search_string(self):
        ans = []
        for tok in self.tokens:
            token = tok.token()
            if token:
                ans.append(token)
        ans = ' '.join(ans)
        if self.match_any.isChecked():
            ans = '['+ans+']'
        return ans
            