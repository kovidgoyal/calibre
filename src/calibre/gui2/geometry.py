#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


# See https://bugreports.qt.io/browse/QTBUG-69104 for why we need to implement
# our own restore geometry


from qt.core import QRect, QScreen, QSize, QWidget, QApplication, Qt


def size_as_dict(self: QSize):
    return {'width': self.width(), 'height': self.height()}


def rect_as_dict(self: QRect):
    return {'x': self.left(), 'y': self.top(), 'width': self.width(), 'height': self.height()}


def screen_as_dict(self: QScreen):
    try:
        num = QApplication.instance().screens().index(self)
    except Exception:
        num = -1
    return {
        'name': self.name(),
        'serial': self.serialNumber(),
        'manufacturer': self.manufacturer(),
        'model': self.model(),
        'depth': self.depth(),
        'device_pixel_ratio': self.devicePixelRatio(),
        'size_in_logical_pixels': size_as_dict(self.size()),
        'geometry_in_logical_pixels': rect_as_dict(self.geometry()),
        'index_in_screens_list': num,
    }


def geometry_for_restore_as_dict(self: QWidget):
    s = self.screen()
    if s is None:
        return {}
    return {
        'screen': screen_as_dict(s),
        'geometry': rect_as_dict(self.geometry()),
        'frame_geometry': rect_as_dict(self.frameGeometry()),
        'normal_geometry': rect_as_dict(self.normalGeometry()),
        'maximized': self.isMaximized(),
        'full_screened': self.isFullScreen(),
    }


def save_geometry(self: QWidget, prefs: dict, name: str):
    x = geometry_for_restore_as_dict(self)
    if x:
        prefs.set(f'geometry-of-{name}', x)


def find_matching_screen(screen_as_dict):
    screens = QApplication.instance().screens()
    size = QSize(**screen_as_dict['size'])
    screens_of_matching_size = tuple(
        s for s in screens if
        s.size() == size and s.devicePixelRatio() == screen_as_dict['device_pixel_ratio'])
    if screen_as_dict['serial']:
        for q in screens_of_matching_size:
            if q.serialNumber() == screen_as_dict['serial']:
                return q

    def match(key, val):
        v = screen_as_dict[key]
        return bool(not v or v == val)

    for q in screens_of_matching_size:
        if match('name', q.name()) and match('manufacturer', q.manufacturer()) and match('model', q.model()):
            return q


def _restore_geometry(self: QWidget, prefs: dict, name: str) -> bool:
    x = prefs.get(f'geometry-of-{name}')
    if not x:
        return False
    s = find_matching_screen(x['screen'])
    if s is None:
        p = self.nativeParentWidget()
        if p is not None:
            s = p.screen()
        if s is None:
            s = self.screen()
            if s is None:
                s = QApplication.instance().primaryScreen()
    if s is None:
        return False
    saved_geometry = QRect(**x['geometry'])
    saved_frame_geometry = QRect(**x['frame_geometry'])
    if not saved_geometry.isValid() or not saved_frame_geometry.isValid():
        return False
    frame_height = max(0, saved_frame_geometry.height() - saved_geometry.height())
    frame_width = max(0, saved_frame_geometry.width() - saved_geometry.width())
    available_geometry = s.availableGeometry()
    available_size = QSize(available_geometry.width() - frame_width, available_geometry.height() - frame_height)
    sz = QSize(min(saved_geometry.width(), available_size.width()), min(saved_geometry.height(), available_size.height()))
    if not sz.isValid():
        return False
    max_left = available_geometry.left() + (available_size.width() - sz.width())
    max_top = available_geometry.top() + (available_size.height() - sz.height())
    geometry = QRect(min(saved_geometry.left(), max_left), min(saved_geometry.top(), max_top), sz.width(), sz.height())
    ws = self.windowState()
    if ws & (Qt.WindowState.WindowFullScreen | Qt.WindowState.WindowMaximized):
        return True
    self.setGeometry(geometry)
    if x['full_screened']:
        self.showFullScreen()
    elif x['maximized']:
        self.showMaximized()


def restore_geometry(self: QWidget, prefs: dict, name: str) -> bool:
    if restore_geometry(self, prefs, name):
        return True
    sz = self.sizeHint()
    if sz.isValid():
        self.resize(self.sizeHint())
    return False


QWidget.save_geometry = save_geometry
QWidget.restore_geometry = restore_geometry
