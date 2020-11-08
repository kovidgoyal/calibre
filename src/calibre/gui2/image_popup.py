#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import (QDialog, QPixmap, QUrl, QScrollArea, QLabel, QSizePolicy,
        QDialogButtonBox, QVBoxLayout, QPalette, QApplication, QSize, QIcon,
        Qt, QTransform, QSvgRenderer, QImage, QPainter, QHBoxLayout, QCheckBox)

from calibre import fit_image
from calibre.gui2 import choose_save_file, gprefs, NO_URL_FORMATTING, max_available_height
from polyglot.builtins import unicode_type


def render_svg(widget, path):
    img = QPixmap()
    rend = QSvgRenderer()
    if rend.load(path):
        dpr = getattr(widget, 'devicePixelRatioF', widget.devicePixelRatio)()
        sz = rend.defaultSize()
        h = (max_available_height() - 50)
        w = int(h * sz.height() / float(sz.width()))
        pd = QImage(w * dpr, h * dpr, QImage.Format_RGB32)
        pd.fill(Qt.white)
        p = QPainter(pd)
        rend.render(p)
        p.end()
        img = QPixmap.fromImage(pd)
        img.setDevicePixelRatio(dpr)
    return img


class ImageView(QDialog):

    def __init__(self, parent, current_img, current_url, geom_name='viewer_image_popup_geometry'):
        QDialog.__init__(self)
        self.setWindowFlag(Qt.WindowMinimizeButtonHint)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint)
        dw = QApplication.instance().desktop()
        self.avail_geom = dw.availableGeometry(parent if parent is not None else self)
        self.current_img = current_img
        self.current_url = current_url
        self.factor = 1.0
        self.geom_name = geom_name

        self.label = l = QLabel(self)
        l.setBackgroundRole(QPalette.Text if QApplication.instance().is_dark_theme else QPalette.Base)
        l.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        l.setScaledContents(True)

        self.scrollarea = sa = QScrollArea()
        sa.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
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

        self.l = l = QVBoxLayout(self)
        l.addWidget(sa)
        self.h = h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        l.addLayout(h)
        self.fit_image = i = QCheckBox(_('&Fit image'))
        i.setToolTip(_('Fit image inside the available space'))
        i.setChecked(bool(gprefs.get('image_popup_fit_image')))
        i.stateChanged.connect(self.fit_changed)
        h.addWidget(i), h.addStretch(), h.addWidget(bb)
        if self.fit_image.isChecked():
            self.set_to_viewport_size()
        geom = gprefs.get(self.geom_name)
        if geom is not None:
            self.restoreGeometry(geom)

    def set_to_viewport_size(self):
        page_size = self.scrollarea.size()
        pw, ph = page_size.width() - 2, page_size.height() - 2
        img_size = self.current_img.size()
        iw, ih = img_size.width(), img_size.height()
        scaled, nw, nh = fit_image(iw, ih, pw, ph)
        if scaled:
            self.factor = min(nw/iw, nh/ih)
        img_size.setWidth(nw), img_size.setHeight(nh)
        self.label.resize(img_size)

    def resizeEvent(self, ev):
        if self.fit_image.isChecked():
            self.set_to_viewport_size()

    def factor_from_fit(self):
        scaled_height = self.label.size().height()
        actual_height = self.current_img.size().height()
        return scaled_height / actual_height

    def zoom_in(self):
        if self.fit_image.isChecked():
            factor = self.factor_from_fit()
            self.fit_image.setChecked(False)
            self.factor = factor
        self.factor *= 1.25
        self.adjust_image(1.25)

    def zoom_out(self):
        if self.fit_image.isChecked():
            factor = self.factor_from_fit()
            self.fit_image.setChecked(False)
            self.factor = factor
        self.factor *= 0.8
        self.adjust_image(0.8)

    def save_image(self):
        filters=[('Images', ['png', 'jpeg', 'jpg'])]
        f = choose_save_file(self, 'viewer image view save dialog',
                _('Choose a file to save to'), filters=filters,
                all_files=False)
        if f:
            from calibre.utils.img import save_image
            save_image(self.current_img.toImage(), f)

    def fit_changed(self):
        fitted = bool(self.fit_image.isChecked())
        gprefs.set('image_popup_fit_image', fitted)
        if self.fit_image.isChecked():
            self.set_to_viewport_size()
        else:
            self.factor = 1
            self.adjust_image(1)

    def adjust_image(self, factor):
        if self.fit_image.isChecked():
            self.set_to_viewport_size()
            return
        self.label.resize(self.factor * self.current_img.size())
        self.zi_button.setEnabled(self.factor <= 3)
        self.zo_button.setEnabled(self.factor >= 0.3333)
        self.adjust_scrollbars(factor)

    def adjust_scrollbars(self, factor):
        for sb in (self.scrollarea.horizontalScrollBar(),
                self.scrollarea.verticalScrollBar()):
            sb.setValue(int(factor*sb.value()) + int(((factor - 1) * sb.pageStep()/2)))

    def rotate_image(self):
        pm = self.label.pixmap()
        t = QTransform()
        t.rotate(90)
        pm = self.current_img = pm.transformed(t)
        self.label.setPixmap(pm)
        self.label.adjustSize()
        if self.fit_image.isChecked():
            self.set_to_viewport_size()
        else:
            self.factor = 1
            for sb in (self.scrollarea.horizontalScrollBar(),
                    self.scrollarea.verticalScrollBar()):
                sb.setValue(0)

    def __call__(self, use_exec=False):
        geom = self.avail_geom
        self.label.setPixmap(self.current_img)
        self.label.adjustSize()
        self.resize(QSize(int(geom.width()/2.5), geom.height()-50))
        geom = gprefs.get(self.geom_name, None)
        if geom is not None:
            QApplication.instance().safe_restore_geometry(self, geom)
        try:
            self.current_image_name = unicode_type(self.current_url.toString(NO_URL_FORMATTING)).rpartition('/')[-1]
        except AttributeError:
            self.current_image_name = self.current_url
        title = _('View image: %s')%self.current_image_name
        self.setWindowTitle(title)
        if use_exec:
            self.exec_()
        else:
            self.show()

    def done(self, e):
        gprefs[self.geom_name] = bytearray(self.saveGeometry())
        return QDialog.done(self, e)

    def wheelEvent(self, event):
        d = event.angleDelta().y()
        if abs(d) > 0 and not self.scrollarea.verticalScrollBar().isVisible():
            event.accept()
            (self.zoom_out if d < 0 else self.zoom_in)()


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


if __name__ == '__main__':
    import sys
    from calibre.gui2 import Application
    app = Application([])
    p = QPixmap()
    p.load(sys.argv[-1])
    u = QUrl.fromLocalFile(sys.argv[-1])
    d = ImageView(None, p, u)
    d()
    app.exec_()
