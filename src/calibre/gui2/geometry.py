#!/usr/bin/env python
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


# See https://bugreports.qt.io/browse/QTBUG-69104 for why we need to implement
# our own restore geometry


from qt.core import QApplication, QRect, QScreen, QSize, Qt, QWidget

from calibre.constants import is_debugging as _is_debugging
from calibre.utils.config_base import tweaks


def geometry_pref_name(name):
    return f'geometry-of-{name}'


def is_debugging():
    return _is_debugging() and tweaks.get('show_geometry_debug_output')


def debug(*a, **kw):
    if is_debugging():
        from pprint import pformat
        items = []
        for x in a:
            if not isinstance(x, str):
                x = pformat(x)
            items.append(x)
        print(*items)


def size_as_dict(self: QSize):
    return {'width': self.width(), 'height': self.height()}


def dict_as_size(x: dict) -> QSize:
    return QSize(x['width'], x['height'])


def rect_as_dict(self: QRect):
    return {'x': self.left(), 'y': self.top(), 'width': self.width(), 'height': self.height()}


def dict_as_rect(g: dict) -> QRect:
    return QRect(g['x'], g['y'], g['width'], g['height'])


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
        'virtual_geometry': rect_as_dict(self.virtualGeometry()),
        'index_in_screens_list': num,
    }


def geometry_for_restore_as_dict(self: QWidget):
    s = self.screen()
    if s is None:
        return {}
    ans = {
        'screen': screen_as_dict(s),
        'geometry': rect_as_dict(self.geometry()),
        'frame_geometry': rect_as_dict(self.frameGeometry()),
        'normal_geometry': rect_as_dict(self.normalGeometry()),
        'maximized': self.isMaximized(),
        'full_screened': self.isFullScreen(),
    }
    return ans


def delete_geometry(prefs: dict, name: str):
    prefs.pop(geometry_pref_name(name), None)


def save_geometry(self: QWidget, prefs: dict, name: str):
    x = geometry_for_restore_as_dict(self)
    if x:
        if is_debugging():
            debug('Saving geometry for:', name)
            debug(x)
        x['qt'] = bytearray(self.saveGeometry())
        prefs.set(geometry_pref_name(name), x)


def find_matching_screen(screen_as_dict):
    screens = QApplication.instance().screens()
    size = dict_as_size(screen_as_dict['size_in_logical_pixels'])
    vg = dict_as_rect(screen_as_dict['virtual_geometry'])
    dpr = screen_as_dict['device_pixel_ratio']
    screens_of_matching_size = tuple(
        s for s in screens if s.size() == size and vg == s.virtualGeometry() and s.devicePixelRatio() == dpr)
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
    if len(screens_of_matching_size) == 1:
        return screens_of_matching_size[0]


def _do_restore(self: QWidget, s: QScreen, geometry: QRect, saved_data: dict):
    ws = self.windowState()
    if ws & (Qt.WindowState.WindowFullScreen | Qt.WindowState.WindowMaximized):
        debug('Not restoring geometry as widget is already maximized or fullscreen')
        return True
    if self.screen() is not s:
        debug('Moving widget to saved screen')
        self.setScreen(s)
    debug('Setting widget geometry to:', rect_as_dict(geometry))
    self.setGeometry(geometry)
    if saved_data['full_screened']:
        debug('Restoring widget to full screen')
        self.setWindowState(Qt.WindowState.WindowFullScreen)
    elif saved_data['maximized']:
        debug('Restoring widget to maximized')
        self.setWindowState(Qt.WindowState.WindowMaximized)
    return True


def _restore_to_matching_screen(self: QWidget, s: QScreen, saved_data: dict) -> bool:
    saved_geometry = dict_as_rect(saved_data['geometry'])
    return _do_restore(self, s, saved_geometry, saved_data)


def _restore_to_new_screen(self: QWidget, s: QScreen, saved_data: dict) -> bool:
    saved_geometry = dict_as_rect(saved_data['geometry'])
    saved_frame_geometry = dict_as_rect(saved_data['frame_geometry'])
    if not saved_geometry.isValid() or not saved_frame_geometry.isValid():
        return False
    frame_height = max(0, saved_frame_geometry.height() - saved_geometry.height())
    frame_width = max(0, saved_frame_geometry.width() - saved_geometry.width())
    available_geometry = s.availableGeometry()
    available_size = QSize(available_geometry.width() - frame_width, available_geometry.height() - frame_height)
    sz = QSize(min(saved_geometry.width(), available_size.width()), min(saved_geometry.height(), available_size.height()))
    if not sz.isValid():
        return False
    left = available_geometry.left() + (available_size.width() - sz.width()) // 2
    top = available_geometry.top() + (available_size.height() - sz.height()) // 2
    geometry = QRect(left, top, sz.width(), sz.height())
    return _do_restore(self, s, geometry, saved_data)


def _restore_geometry(self: QWidget, prefs: dict, name: str, get_legacy_saved_geometry: callable = None) -> bool:
    x = prefs.get(geometry_pref_name(name))
    if not x:
        old = get_legacy_saved_geometry() if get_legacy_saved_geometry else prefs.get(name)
        if old is not None:
            return self.restoreGeometry(old)
        return False
    if is_debugging():
        debug('Restoring geometry for:', name)
        dx =  x.copy()
        del dx['qt']
        debug(dx)
    s = find_matching_screen(x['screen'])
    debug('Matching screen:', screen_as_dict(s) if s else None)
    if s is None:
        if is_debugging():
            debug('No screens matched saved screen. Available screens:', tuple(map(screen_as_dict, QApplication.instance().screens())))
        p = self.nativeParentWidget()
        if p is not None:
            s = p.screen()
        if s is None:
            s = self.screen()
            if s is None:
                s = QApplication.instance().primaryScreen()
    else:
        return _restore_to_matching_screen(self, s, x)
    if s is None:
        return False
    return _restore_to_new_screen(self, s, x)


screen_debug_has_been_output = False


def restore_geometry(self: QWidget, prefs: dict, name: str, get_legacy_saved_geometry: callable = None) -> bool:
    global screen_debug_has_been_output
    if not screen_debug_has_been_output:
        screen_debug_has_been_output = True
        debug('Screens currently in system:')
        for screen in QApplication.instance().screens():
            debug(screen_as_dict(screen))
    if _restore_geometry(self, prefs, name, get_legacy_saved_geometry):
        return True
    sz = self.sizeHint()
    if sz.isValid():
        self.resize(self.sizeHint())
    return False


QWidget.save_geometry = save_geometry
QWidget.restore_geometry = restore_geometry
