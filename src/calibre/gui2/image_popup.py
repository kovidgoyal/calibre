#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from qt.core import (
    QApplication, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QIcon, QImage,
    QLabel, QPainter, QPalette, QPixmap, QScrollArea, QSize, QSizePolicy,
    Qt, QTransform, QUrl, QVBoxLayout, pyqtSignal, QAction, QKeySequence
)

from calibre import fit_image
from calibre.gui2 import (
    NO_URL_FORMATTING, choose_save_file, gprefs, max_available_height
)


def render_svg(widget, path):
    from qt.core import QSvgRenderer
    img = QPixmap()
    rend = QSvgRenderer()
    if rend.load(path):
        dpr = getattr(widget, 'devicePixelRatioF', widget.devicePixelRatio)()
        sz = rend.defaultSize()
        h = (max_available_height() - 50)
        w = int(h * sz.height() / float(sz.width()))
        pd = QImage(w * dpr, h * dpr, QImage.Format.Format_RGB32)
        pd.fill(Qt.GlobalColor.white)
        p = QPainter(pd)
        rend.render(p)
        p.end()
        img = QPixmap.fromImage(pd)
        img.setDevicePixelRatio(dpr)
    return img


class Label(QLabel):

    toggle_fit = pyqtSignal()
    zoom_requested = pyqtSignal(bool)

    def __init__(self, scrollarea):
        super().__init__(scrollarea)
        scrollarea.zoom_requested.connect(self.zoom_requested)
        self.setBackgroundRole(QPalette.ColorRole.Text if QApplication.instance().is_dark_theme else QPalette.ColorRole.Base)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setScaledContents(True)
        self.default_cursor = self.cursor()
        self.in_drag = False
        self.prev_drag_position = None
        self.scrollarea = scrollarea

    @property
    def is_pannable(self):
        return self.scrollarea.verticalScrollBar().isVisible() or self.scrollarea.horizontalScrollBar().isVisible()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and self.is_pannable:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.in_drag = True
            self.prev_drag_position = ev.globalPos()
        return super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and self.in_drag:
            self.setCursor(self.default_cursor)
            self.in_drag = False
            self.prev_drag_position = None
        return super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self.prev_drag_position is not None:
            p = self.prev_drag_position
            self.prev_drag_position = pos = ev.globalPos()
            self.dragged(pos.x() - p.x(), pos.y() - p.y())
        return super().mouseMoveEvent(ev)

    def dragged(self, dx, dy):
        h = self.scrollarea.horizontalScrollBar()
        if h.isVisible():
            h.setValue(h.value() - dx)
        v = self.scrollarea.verticalScrollBar()
        if v.isVisible():
            v.setValue(v.value() - dy)


class ScrollArea(QScrollArea):

    toggle_fit = pyqtSignal()
    zoom_requested = pyqtSignal(bool)
    current_wheel_angle_delta = 0

    def mouseDoubleClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.toggle_fit.emit()

    def wheelEvent(self, ev):
        if ev.modifiers() == Qt.KeyboardModifier.ControlModifier:
            ad = ev.angleDelta().y()
            if ad * self.current_wheel_angle_delta < 0:
                self.current_wheel_angle_delta = 0
            self.current_wheel_angle_delta += ad
            if abs(self.current_wheel_angle_delta) >= 120:
                self.zoom_requested.emit(self.current_wheel_angle_delta < 0)
                self.current_wheel_angle_delta = 0
            ev.accept()
        else:
            super().wheelEvent(ev)


class ImageView(QDialog):

    def __init__(self, parent, current_img, current_url, geom_name='viewer_image_popup_geometry', prefs=gprefs):
        QDialog.__init__(self)
        self.prefs = prefs
        self.current_image_name = ''
        self.maximized_at_last_fullscreen = False
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint)
        self.avail_geom = self.screen().availableGeometry()
        self.current_img = current_img
        self.current_url = current_url
        self.factor = 1.0
        self.geom_name = geom_name
        self.zoom_in_action = ac = QAction(self)
        ac.triggered.connect(self.zoom_in)
        ac.setShortcuts([QKeySequence(QKeySequence.StandardKey.ZoomIn), QKeySequence('+', QKeySequence.SequenceFormat.PortableText)])
        self.addAction(ac)
        self.zoom_out_action = ac = QAction(self)
        ac.triggered.connect(self.zoom_out)
        ac.setShortcuts([QKeySequence(QKeySequence.StandardKey.ZoomOut), QKeySequence('-', QKeySequence.SequenceFormat.PortableText)])
        self.addAction(ac)

        self.scrollarea = sa = ScrollArea()
        sa.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        sa.setBackgroundRole(QPalette.ColorRole.Dark)
        self.label = l = Label(sa)
        l.zoom_requested.connect(self.zoom_requested)
        sa.toggle_fit.connect(self.toggle_fit)
        sa.setWidget(l)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.zi_button = zi = bb.addButton(_('Zoom &in'), QDialogButtonBox.ButtonRole.ActionRole)
        self.zo_button = zo = bb.addButton(_('Zoom &out'), QDialogButtonBox.ButtonRole.ActionRole)
        self.save_button = so = bb.addButton(_('&Save as'), QDialogButtonBox.ButtonRole.ActionRole)
        self.copy_button = co = bb.addButton(_('&Copy'), QDialogButtonBox.ButtonRole.ActionRole)
        self.rotate_button = ro = bb.addButton(_('&Rotate'), QDialogButtonBox.ButtonRole.ActionRole)
        self.fullscreen_button = fo = bb.addButton(_('&Full screen'), QDialogButtonBox.ButtonRole.ActionRole)
        zi.setIcon(QIcon.ic('plus.png'))
        zo.setIcon(QIcon.ic('minus.png'))
        so.setIcon(QIcon.ic('save.png'))
        co.setIcon(QIcon.ic('edit-copy.png'))
        ro.setIcon(QIcon.ic('rotate-right.png'))
        fo.setIcon(QIcon.ic('page.png'))
        zi.clicked.connect(self.zoom_in)
        zo.clicked.connect(self.zoom_out)
        so.clicked.connect(self.save_image)
        co.clicked.connect(self.copy_image)
        self.copy_action = QAction(self)
        self.addAction(self.copy_action)
        self.copy_action.triggered.connect(self.copy_button.click)
        self.copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        ro.clicked.connect(self.rotate_image)
        fo.setCheckable(True)

        self.l = l = QVBoxLayout(self)
        l.addWidget(sa)
        self.h = h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        l.addLayout(h)
        self.fit_image = i = QCheckBox(_('&Fit image'))
        i.setToolTip(_('Fit image inside the available space'))
        i.setChecked(bool(self.prefs.get('image_popup_fit_image')))
        i.stateChanged.connect(self.fit_changed)
        h.addWidget(i), h.addStretch(), h.addWidget(bb)
        if self.fit_image.isChecked():
            self.set_to_viewport_size()
        self.restore_geometry(self.prefs, self.geom_name)
        fo.setChecked(self.isFullScreen())
        fo.toggled.connect(self.toggle_fullscreen)

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

    def zoom_requested(self, zoom_out):
        if (zoom_out and self.zo_button.isEnabled()) or (not zoom_out and self.zi_button.isEnabled()):
            (self.zoom_out if zoom_out else self.zoom_in)()

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
                all_files=False, initial_filename=self.current_image_name or None)
        if f:
            from calibre.utils.img import save_image
            save_image(self.current_img.toImage(), f)

    def copy_image(self):
        if self.current_img and not self.current_img.isNull():
            QApplication.instance().clipboard().setPixmap(self.current_img)

    def fit_changed(self):
        fitted = bool(self.fit_image.isChecked())
        self.prefs.set('image_popup_fit_image', fitted)
        if self.fit_image.isChecked():
            self.set_to_viewport_size()
        else:
            self.factor = 1
            self.adjust_image(1)

    def toggle_fit(self):
        self.fit_image.toggle()

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
            sb.setValue(int(factor*sb.value()) + int((factor - 1) * sb.pageStep()/2))

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
        self.restore_geometry(self.prefs, self.geom_name)
        try:
            self.current_image_name = str(self.current_url.toString(NO_URL_FORMATTING)).rpartition('/')[-1]
        except AttributeError:
            self.current_image_name = self.current_url
        reso = ''
        if self.current_img and not self.current_img.isNull():
            reso = f'[{self.current_img.width()}x{self.current_img.height()}]'
        title = _('Image: {name} {resolution}').format(name=self.current_image_name, resolution=reso)
        self.setWindowTitle(title)
        if use_exec:
            self.exec()
        else:
            self.show()

    def done(self, e):
        self.save_geometry(self.prefs, self.geom_name)
        return QDialog.done(self, e)

    def toggle_fullscreen(self):
        on = not self.isFullScreen()
        if on:
            self.maximized_at_last_fullscreen = self.isMaximized()
            self.showFullScreen()
        else:
            if self.maximized_at_last_fullscreen:
                self.showMaximized()
            else:
                self.showNormal()


class ImagePopup:

    def __init__(self, parent, prefs=gprefs):
        self.current_img = QPixmap()
        self.current_url = QUrl()
        self.parent = parent
        self.dialogs = []
        self.prefs = prefs

    def __call__(self):
        if self.current_img.isNull():
            return
        d = ImageView(self.parent, self.current_img, self.current_url, prefs=self.prefs)
        self.dialogs.append(d)
        d.finished.connect(self.cleanup, type=Qt.ConnectionType.QueuedConnection)
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
    app.exec()
