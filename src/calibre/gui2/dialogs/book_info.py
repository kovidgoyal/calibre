#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

import textwrap, os, re

from PyQt4.Qt import QCoreApplication, SIGNAL, QModelIndex, QTimer, Qt, \
    QDialog, QPixmap, QGraphicsScene, QIcon, QSize

from calibre.gui2.dialogs.book_info_ui import Ui_BookInfo
from calibre.gui2 import dynamic, open_local_file
from calibre import fit_image
from calibre.library.comments import comments_to_html
from calibre.utils.icu import sort_key

class BookInfo(QDialog, Ui_BookInfo):

    def __init__(self, parent, view, row, view_func):
        QDialog.__init__(self, parent)
        Ui_BookInfo.__init__(self)
        self.setupUi(self)
        self.cover_pixmap = None
        self.comments.sizeHint = self.comments_size_hint
        self.view_func = view_func


        self.view = view
        self.current_row = None
        self.fit_cover.setChecked(dynamic.get('book_info_dialog_fit_cover',
            True))
        self.refresh(row)
        self.connect(self.view.selectionModel(), SIGNAL('currentChanged(QModelIndex,QModelIndex)'), self.slave)
        self.connect(self.next_button, SIGNAL('clicked()'), self.next)
        self.connect(self.previous_button, SIGNAL('clicked()'), self.previous)
        self.connect(self.text, SIGNAL('linkActivated(QString)'), self.open_book_path)
        self.fit_cover.stateChanged.connect(self.toggle_cover_fit)
        self.cover.resizeEvent = self.cover_view_resized

        desktop = QCoreApplication.instance().desktop()
        screen_height = desktop.availableGeometry().height() - 100
        self.resize(self.size().width(), screen_height)


    def comments_size_hint(self):
        return QSize(350, 250)

    def toggle_cover_fit(self, state):
        dynamic.set('book_info_dialog_fit_cover', self.fit_cover.isChecked())
        self.resize_cover()

    def cover_view_resized(self, event):
        QTimer.singleShot(1, self.resize_cover)

    def slave(self, current, previous):
        row = current.row()
        self.refresh(row)

    def open_book_path(self, path):
        path = unicode(path)
        if os.sep in path:
            open_local_file(path)
        else:
            self.view_func(self.view.model().id(self.current_row), path)

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

    def resize_cover(self):
        if self.cover_pixmap is None:
            return
        self.setWindowIcon(QIcon(self.cover_pixmap))
        self.scene = QGraphicsScene()
        pixmap = self.cover_pixmap
        if self.fit_cover.isChecked():
            scaled, new_width, new_height = fit_image(pixmap.width(),
                    pixmap.height(), self.cover.size().width()-10,
                    self.cover.size().height()-10)
            if scaled:
                pixmap = pixmap.scaled(new_width, new_height,
                        Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.scene.addPixmap(pixmap)
        self.cover.setScene(self.scene)

    def refresh(self, row):
        if isinstance(row, QModelIndex):
            row = row.row()
        if row == self.current_row:
            return
        info = self.view.model().get_book_info(row)
        if info is None:
            # Indicates books was deleted from library, or row numbers have
            # changed
            return

        self.previous_button.setEnabled(False if row == 0 else True)
        self.next_button.setEnabled(False if row == self.view.model().rowCount(QModelIndex())-1 else True)
        self.current_row = row
        self.setWindowTitle(info[_('Title')])
        self.title.setText('<b>'+info.pop(_('Title')))
        comments = info.pop(_('Comments'), '')
        if comments:
            comments = comments_to_html(comments)
        if re.search(r'<[a-zA-Z]+>', comments) is None:
            lines = comments.splitlines()
            lines = [x if x.strip() else '<br><br>' for x in lines]
            comments = '\n'.join(lines)
        self.comments.setHtml('<div>%s</div>' % comments)
        cdata = info.pop('cover', '')
        self.cover_pixmap = QPixmap.fromImage(cdata)
        self.resize_cover()

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
        for key in sorted(info.keys(), key=sort_key):
            if key == 'id': continue
            txt  = info[key]
            if key.endswith(':html'):
                key = key[:-5]
            if key != _('Path'):
                txt  = u'<br />\n'.join(textwrap.wrap(txt, 120))
            rows += u'<tr><td><b>%s:</b></td><td>%s</td></tr>'%(key, txt)
        self.text.setText(u'<table>'+rows+'</table>')
