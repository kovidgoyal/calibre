#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
'''
import textwrap

from PyQt4.QtCore import Qt, QCoreApplication
from PyQt4.QtGui import QDialog, QPixmap, QGraphicsScene, QIcon

from calibre.gui2.dialogs.book_info_ui import Ui_BookInfo

class BookInfo(QDialog, Ui_BookInfo):
    
    def __init__(self, parent, info):
        QDialog.__init__(self, parent)
        Ui_BookInfo.__init__(self)
        self.setupUi(self)
        
        self.default_pixmap = QPixmap(':/images/book.svg').scaled(80,
                                                                  100,
                                                            Qt.IgnoreAspectRatio,
                                                            Qt.SmoothTransformation)
        
        self.setWindowTitle(info[_('Title')])
        desktop = QCoreApplication.instance().desktop()
        screen_height = desktop.availableGeometry().height() - 100
        self.resize(self.size().width(), screen_height)
        self.title.setText('<b>'+info.pop(_('Title')))
        self.comments.setText(info.pop(_('Comments'), ''))
        
        cdata = info.pop('cover', '')
        pixmap = QPixmap()
        pixmap.loadFromData(cdata)
        if pixmap.isNull():
            pixmap = self.default_pixmap
            
        self.setWindowIcon(QIcon(pixmap))
        
        self.scene = QGraphicsScene()
        self.scene.addPixmap(pixmap)
        self.cover.setScene(self.scene)
        
        rows = u''
        self.text.setText('')
        self.data = info
        for key in info.keys():
            txt  = info[key]
            txt  = u'<br />\n'.join(textwrap.wrap(txt, 120))
            rows += u'<tr><td><b>%s:</b></td><td>%s</td></tr>'%(key, txt)
        self.text.setText(u'<table>'+rows+'</table>')