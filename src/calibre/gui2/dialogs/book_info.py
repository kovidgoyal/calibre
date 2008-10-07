#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
'''
import textwrap, os

from PyQt4.QtCore import QCoreApplication, SIGNAL, QModelIndex, QUrl
from PyQt4.QtGui import QDialog, QPixmap, QGraphicsScene, QIcon, QDesktopServices

from calibre.gui2.dialogs.book_info_ui import Ui_BookInfo

class BookInfo(QDialog, Ui_BookInfo):
    
    def __init__(self, parent, view, row):
        QDialog.__init__(self, parent)
        Ui_BookInfo.__init__(self)
        self.setupUi(self)
        desktop = QCoreApplication.instance().desktop()
        screen_height = desktop.availableGeometry().height() - 100
        self.resize(self.size().width(), screen_height)
        
        
        self.view = view
        self.current_row = None
        self.refresh(row)
        self.connect(self.view.selectionModel(), SIGNAL('currentChanged(QModelIndex,QModelIndex)'), self.slave)
        self.connect(self.next_button, SIGNAL('clicked()'), self.next)
        self.connect(self.previous_button, SIGNAL('clicked()'), self.previous)
        self.connect(self.text, SIGNAL('linkActivated(QString)'), self.open_book_path)
        
    def slave(self, current, previous):
        row = current.row()
        self.refresh(row)
        
    def open_book_path(self, path):
        if os.sep in unicode(path):
            QDesktopServices.openUrl(QUrl('file:'+path))
        else:
            format = unicode(path)
            path = self.view.model().db.format_abspath(self.current_row, format)
            if path is not None:
                QDesktopServices.openUrl(QUrl('file:'+path))
        
        
    def next(self):
        row = self.view.currentIndex().row()
        ni = self.view.model().index(row+1, 0)
        if ni.isValid():
            self.view.setCurrentIndex(ni)
    
    def previous(self):
        row = self.view.currentIndex().row()
        ni = self.view.model().index(row-1, 0)
        if ni.isValid():
            self.view.setCurrentIndex(ni)
    
    def refresh(self, row):
        if isinstance(row, QModelIndex):
            row = row.row()
        if row == self.current_row:
            return
        self.previous_button.setEnabled(False if row == 0 else True)
        self.next_button.setEnabled(False if row == self.view.model().rowCount(QModelIndex())-1 else True)    
        self.current_row = row
        info = self.view.model().get_book_info(row)
        self.setWindowTitle(info[_('Title')])
        self.title.setText('<b>'+info.pop(_('Title')))
        self.comments.setText(info.pop(_('Comments'), ''))
        
        cdata = info.pop('cover', '')
        pixmap = QPixmap.fromImage(cdata)
        self.setWindowIcon(QIcon(pixmap))
        
        self.scene = QGraphicsScene()
        self.scene.addPixmap(pixmap)
        self.cover.setScene(self.scene)
        
        rows = u''
        self.text.setText('')
        self.data = info
        if _('Path') in info.keys():
            p = info[_('Path')]
            info[_('Path')] = '<a href="%s">%s</a>'%(p, p)
        if _('Formats') in info.keys():
            formats = info[_('Formats')].split(',')
            info[_('Formats')] = ''
            for f in formats:
                f = f.strip()
                info[_('Formats')] += '<a href="%s">%s</a>, '%(f,f)
        for key in info.keys():
            txt  = info[key]
            txt  = u'<br />\n'.join(textwrap.wrap(txt, 120))
            rows += u'<tr><td><b>%s:</b></td><td>%s</td></tr>'%(key, txt)
        self.text.setText(u'<table>'+rows+'</table>')