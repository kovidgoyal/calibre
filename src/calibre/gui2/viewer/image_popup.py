#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import (QDialog, QPixmap, QUrl, QScrollArea, QLabel, QSizePolicy,
        QDialogButtonBox, QVBoxLayout, QPalette, QApplication, QSize, QIcon,
        Qt, QTransform)

from calibre.gui2 import choose_save_file, gprefs

class ImageView(QDialog):

    def __init__(self, parent, current_img, current_url):
        QDialog.__init__(self)
        dw = QApplication.instance().desktop()
        self.avail_geom = dw.availableGeometry(parent)
        self.current_img = current_img
        self.current_url = current_url
        self.factor = 1.0

        self.label = l = QLabel()
        l.setBackgroundRole(QPalette.Base);
        l.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        l.setScaledContents(True)

        self.scrollarea = sa = QScrollArea()
        sa.setBackgroundRole(QPalette.Dark)
        sa.setWidget(l)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.zi_button = zi = bb.addButton(_('Zoom &in'), bb.ActionRole)
        self.zo_button = zo = bb.addButton(_('Zoom &out'), bb.ActionRole)
        self.save_button = so = bb.addButton(_('&Save as'), bb.ActionRole)
        self.rotate_button = ro = bb.addButton(_('&Rotate'), bb.ActionRole)
        zi.setIcon(QIcon(I('plus.png')))
        zo.setIcon(QIcon(I('minus.png')))
        so.setIcon(QIcon(I('save.png')))
        ro.setIcon(QIcon(I('rotate-right.png')))
        zi.clicked.connect(self.zoom_in)
        zo.clicked.connect(self.zoom_out)
        so.clicked.connect(self.save_image)
        ro.clicked.connect(self.rotate_image)

        self.l = l = QVBoxLayout()
        self.setLayout(l)
        l.addWidget(sa)
        l.addWidget(bb)

    def zoom_in(self):
        self.factor *= 1.25
        self.adjust_image(1.25)

    def zoom_out(self):
        self.factor *= 0.8
        self.adjust_image(0.8)

    def save_image(self):
        filters=[('Images', ['png', 'jpeg', 'jpg'])]
        f = choose_save_file(self, 'viewer image view save dialog',
                _('Choose a file to save to'), filters=filters,
                all_files=False)
        if f:
            self.current_img.save(f)

    def adjust_image(self, factor):
        self.label.resize(self.factor * self.current_img.size())
        self.zi_button.setEnabled(self.factor <= 3)
        self.zo_button.setEnabled(self.factor >= 0.3333)
        self.adjust_scrollbars(factor)

    def adjust_scrollbars(self, factor):
        for sb in (self.scrollarea.horizontalScrollBar(),
                self.scrollarea.verticalScrollBar()):
            sb.setValue(int(factor*sb.value()) + ((factor - 1) * sb.pageStep()/2))

    def rotate_image(self):
        pm = self.label.pixmap()
        t = QTransform()
        t.rotate(90)
        pm = pm.transformed(t)
        self.label.setPixmap(pm)
        self.label.adjustSize()

    def __call__(self):
        geom = self.avail_geom
        self.label.setPixmap(self.current_img)
        self.label.adjustSize()
        self.resize(QSize(int(geom.width()/2.5), geom.height()-50))
        geom = gprefs.get('viewer_image_popup_geometry', None)
        if geom is not None:
            self.restoreGeometry(geom)
        self.current_image_name = unicode(self.current_url.toString()).rpartition('/')[-1]
        title = _('View Image: %s')%self.current_image_name
        self.setWindowTitle(title)
        self.show()

    def done(self, e):
        gprefs['viewer_image_popup_geometry'] = bytearray(self.saveGeometry())
        return QDialog.done(self, e)

class ImagePopup(object):

    def __init__(self, parent):
        self.current_img = QPixmap()
        self.current_url = QUrl()
        self.parent = parent
        self.dialogs = []

    def __call__(self):
        if self.current_img.isNull():
            return
        d = ImageView(self.parent, self.current_img, self.current_url)
        self.dialogs.append(d)
        d.finished.connect(self.cleanup, type=Qt.QueuedConnection)
        d()

    def cleanup(self):
        for d in tuple(self.dialogs):
            if not d.isVisible():
                self.dialogs.remove(d)

