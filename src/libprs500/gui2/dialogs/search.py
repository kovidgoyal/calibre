##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
import re
from PyQt4.QtGui import QWidget, QDialog, QVBoxLayout
from PyQt4.QtCore import SIGNAL

from libprs500.gui2.dialogs.search_ui import Ui_Dialog
from libprs500.gui2.dialogs.search_item_ui import Ui_Form
from libprs500.gui2 import qstring_to_unicode

class SearchItem(Ui_Form, QWidget):
    
    FIELDS = {
              _('Title')     : 'title:',
              _('Author')    : 'author:',
              _('Publisher') :'publisher:',
              _('Tag')       :'tag',
              _('Series')    :'series:',
              _('Format')    :'format:',
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
        return ' '.join(ans)
            