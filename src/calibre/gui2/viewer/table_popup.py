#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import (QDialog, QDialogButtonBox, QVBoxLayout, QApplication,
                      QSize, QIcon, Qt)
from PyQt5.QtWebKitWidgets import QWebView

from calibre.gui2 import gprefs, error_dialog


class TableView(QDialog):

    def __init__(self, parent, font_magnification_step):
        QDialog.__init__(self, parent)
        self.font_magnification_step = font_magnification_step
        dw = QApplication.instance().desktop()
        self.avail_geom = dw.availableGeometry(parent)

        self.view = QWebView(self)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.zi_button = zi = bb.addButton(_('Zoom &in'), bb.ActionRole)
        self.zo_button = zo = bb.addButton(_('Zoom &out'), bb.ActionRole)
        zi.setIcon(QIcon(I('plus.png')))
        zo.setIcon(QIcon(I('minus.png')))
        zi.clicked.connect(self.zoom_in)
        zo.clicked.connect(self.zoom_out)

        self.l = l = QVBoxLayout()
        self.setLayout(l)
        l.addWidget(self.view)
        l.addWidget(bb)

    def zoom_in(self):
        self.view.setZoomFactor(self.view.zoomFactor() +
                                self.font_magnification_step)

    def zoom_out(self):
        self.view.setZoomFactor(max(0.1, self.view.zoomFactor() - self.font_magnification_step))

    def __call__(self, html, baseurl):
        self.view.setHtml(
            '<!DOCTYPE html><html><body bgcolor="white">%s<body></html>'%html,
            baseurl)
        geom = self.avail_geom
        self.resize(QSize(int(geom.width()/2.5), geom.height()-50))
        geom = gprefs.get('viewer_table_popup_geometry', None)
        if geom is not None:
            self.restoreGeometry(geom)
        self.setWindowTitle(_('View table'))
        self.show()

    def done(self, e):
        gprefs['viewer_table_popup_geometry'] = bytearray(self.saveGeometry())
        return QDialog.done(self, e)


class TablePopup(object):

    def __init__(self, parent):
        self.parent = parent
        self.dialogs = []

    def __call__(self, html, baseurl, font_magnification_step):
        if not html:
            return error_dialog(self.parent, _('No table found'),
                _('No table was found'), show=True)
        d = TableView(self.parent, font_magnification_step)
        self.dialogs.append(d)
        d.finished.connect(self.cleanup, type=Qt.QueuedConnection)
        d(html, baseurl)

    def cleanup(self):
        for d in tuple(self.dialogs):
            if not d.isVisible():
                self.dialogs.remove(d)
