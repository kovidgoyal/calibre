#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, string, weakref
from functools import wraps

from PyQt4.Qt import (
    QWidget, QImage, QPainter, QColor, QApplication, Qt, QPixmap, QRectF,
    QPointF, QPen, pyqtSignal, QUndoCommand, QUndoStack, QIcon)

from calibre import fit_image
from calibre.gui2 import error_dialog

def painter(func):
    @wraps(func)
    def ans(self, painter):
        painter.save()
        try:
            return func(self, painter)
        finally:
            painter.restore()
    return ans

ucase_map = {l:string.ascii_uppercase[i] for i, l in enumerate(string.ascii_lowercase)}
def capitalize(x):
    return ucase_map[x[0]] + x[1:]

class SelectionState(object):

    __slots__ = ('last_press_point', 'current_mode', 'rect', 'in_selection', 'drag_corner', 'dragging', 'last_drag_pos')

    def __init__(self):
        self.reset()

    def reset(self, full=True):
        self.last_press_point = None
        if full:
            self.current_mode = None
            self.rect = None
        self.in_selection = False
        self.drag_corner = None
        self.dragging = None
        self.last_drag_pos = None

class Command(QUndoCommand):

    def __init__(self, text, canvas):
        QUndoCommand.__init__(self, text)
        self.canvas_ref = weakref.ref(canvas)
        self.before_image = i = canvas.current_image
        if i is None:
            raise ValueError('No image loaded')
        if i.isNull():
            raise ValueError('Cannot perform operations on invalid images')
        self.after_image = canvas.current_image = self(canvas)

    def undo(self):
        canvas = self.canvas_ref()
        canvas.set_image(self.before_image)

    def redo(self):
        canvas = self.canvas_ref()
        canvas.set_image(self.after_image)

class Trim(Command):

    def __init__(self, canvas):
        Command.__init__(self, _('Trim image'), canvas)

    def __call__(self, canvas):
        img = canvas.current_image
        target = canvas.target
        sr = canvas.selection_state.rect
        left_border = (abs(sr.left() - target.left())/target.width()) * img.width()
        top_border = (abs(sr.top() - target.top())/target.height()) * img.height()
        right_border = (abs(target.right() - sr.right())/target.width()) * img.width()
        bottom_border = (abs(target.bottom() - sr.bottom())/target.height()) * img.height()
        return img.copy(left_border, top_border, img.width() - left_border - right_border, img.height() - top_border - bottom_border)

def imageop(func):
    @wraps(func)
    def ans(self, *args, **kwargs):
        if self.original_image_data is None:
            return error_dialog(self, _('No image'), _('No image loaded'), show=True)
        if not self.is_valid:
            return error_dialog(self, _('Invalid image'), _('The current image is not valid'), show=True)
        return func(self, *args, **kwargs)
    return ans

class Canvas(QWidget):

    BACKGROUND = QColor(60, 60, 60)
    SHADE_COLOR = QColor(0, 0, 0, 180)
    SELECT_PEN = QPen(QColor(Qt.white))

    selection_state_changed = pyqtSignal(object)
    image_changed = pyqtSignal(object)

    @property
    def has_selection(self):
        return self.selection_state.current_mode == 'selected'

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.ClickFocus)
        self.selection_state = SelectionState()
        self.undo_stack = QUndoStack()
        self.undo_stack.setUndoLimit(10)

        self.original_image_data = None
        self.current_image = None
        self.current_scaled_pixmap = None
        self.last_canvas_size = None
        self.target = QRectF(0, 0, 0, 0)

        self.undo_action = a = self.undo_stack.createUndoAction(self, _('Undo') + ' ')
        a.setIcon(QIcon(I('edit-undo.png')))
        self.redo_action = a = self.undo_stack.createRedoAction(self, _('Redo') + ' ')
        a.setIcon(QIcon(I('edit-redo.png')))

    def load_image(self, data):
        self.selection_state.reset()
        self.original_image_data = data
        self.current_image = i = self.original_image = QImage()
        i.loadFromData(data)
        self.is_valid = not i.isNull()
        self.update()
        self.image_changed.emit(self.current_image)

    def set_image(self, qimage):
        self.selection_state.reset()
        self.current_scaled_pixmap = None
        self.current_image = qimage
        self.is_valid = not qimage.isNull()
        self.update()
        self.image_changed.emit(self.current_image)

    def cleanup(self):
        self.undo_stack.clear()
        self.original_image_data = self.current_image = self.current_scaled_pixmap = None

    @imageop
    def trim_image(self):
        if self.selection_state.rect is None:
            return error_dialog(self, _('No selection'), _(
                'No active selection, first select a region in the image, by dragging with your mouse'), show=True)
        self.undo_stack.push(Trim(self))

    # The selection rectangle {{{
    @property
    def dc_size(self):
        sr = self.selection_state.rect
        dx = min(75, sr.width() / 4)
        dy = min(75, sr.height() / 4)
        return dx, dy

    def get_drag_corner(self, pos):
        dx, dy = self.dc_size
        sr = self.selection_state.rect
        x, y = pos.x(), pos.y()
        hedge = 'left' if x < sr.x() + dx else 'right' if x > sr.right() - dx else None
        vedge = 'top' if y < sr.y() + dy else 'bottom' if y > sr.bottom() - dy else None
        return (hedge, vedge) if hedge or vedge else None

    def get_drag_rect(self):
        sr = self.selection_state.rect
        dc = self.selection_state.drag_corner
        if None in (sr, dc):
            return
        dx, dy = self.dc_size
        if None in dc:
            # An edge
            if dc[0] is None:
                top = sr.top() if dc[1] == 'top' else sr.bottom() - dy
                ans = QRectF(sr.left() + dx, top, sr.width() - 2 * dx, dy)
            else:
                left = sr.left() if dc[0] == 'left' else sr.right() - dx
                ans = QRectF(left, sr.top() + dy, dx, sr.height() - 2 * dy)
        else:
            # A corner
            left = sr.left() if dc[0] == 'left' else sr.right() - dx
            top = sr.top() if dc[1] == 'top' else sr.bottom() - dy
            ans = QRectF(left, top, dx, dy)
        return ans

    def get_cursor(self):
        dc = self.selection_state.drag_corner
        if dc is None:
            ans = Qt.OpenHandCursor if self.selection_state.last_drag_pos is None else Qt.ClosedHandCursor
        elif None in dc:
            ans = Qt.SizeVerCursor if dc[0] is None else Qt.SizeHorCursor
        else:
            ans = Qt.SizeBDiagCursor if dc in {('left', 'bottom'), ('right', 'top')} else Qt.SizeFDiagCursor
        return ans

    def move_edge(self, edge, dp):
        sr = self.selection_state.rect
        horiz = edge in {'left', 'right'}
        func = getattr(sr, 'set' + capitalize(edge))
        delta = getattr(dp, 'x' if horiz else 'y')()
        buf = 50
        if horiz:
            minv = self.target.left() if edge == 'left' else sr.left() + buf
            maxv = sr.right() - buf if edge == 'left' else self.target.right()
        else:
            minv = self.target.top() if edge == 'top' else sr.top() + buf
            maxv = sr.bottom() - buf if edge == 'top' else self.target.bottom()
        func(max(minv, min(maxv, delta + getattr(sr, edge)())))

    def move_selection_rect(self, x, y):
        sr = self.selection_state.rect
        half_width = sr.width() / 2.0
        half_height = sr.height() / 2.0
        c = sr.center()
        nx = c.x() + x
        ny = c.y() + y
        minx = self.target.left() + half_width
        maxx = self.target.right() - half_width
        miny, maxy = self.target.top() + half_height, self.target.bottom() - half_height
        nx = max(minx, min(maxx, nx))
        ny = max(miny, min(maxy, ny))
        sr.moveCenter(QPointF(nx, ny))

    def move_selection(self, dp):
        dm = self.selection_state.dragging
        if dm is None:
            self.move_selection_rect(dp.x(), dp.y())
        else:
            for edge in dm:
                if edge is not None:
                    self.move_edge(edge, dp)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.target.contains(ev.pos()):
            pos = ev.pos()
            self.selection_state.last_press_point = pos
            if self.selection_state.current_mode is None:
                self.selection_state.current_mode = 'select'

            elif self.selection_state.current_mode == 'selected':
                if self.selection_state.rect is not None and self.selection_state.rect.contains(pos):
                    self.selection_state.drag_corner = self.selection_state.dragging = self.get_drag_corner(pos)
                    self.selection_state.last_drag_pos = pos
                    self.setCursor(self.get_cursor())
                else:
                    self.selection_state.current_mode = 'select'
                    self.selection_state.rect = None
                    self.selection_state_changed.emit(False)

    def mouseMoveEvent(self, ev):
        changed = False
        if self.selection_state.in_selection:
            changed = True
        self.selection_state.in_selection = False
        self.selection_state.drag_corner = None
        pos = ev.pos()
        cursor = Qt.ArrowCursor
        try:
            if not self.target.contains(pos):
                return
            if ev.buttons() & Qt.LeftButton:
                if self.selection_state.last_press_point is not None and self.selection_state.current_mode is not None:
                    if self.selection_state.current_mode == 'select':
                        self.selection_state.rect = QRectF(self.selection_state.last_press_point, pos).normalized()
                        changed = True
                    elif self.selection_state.last_drag_pos is not None:
                        self.selection_state.in_selection = True
                        self.selection_state.drag_corner = self.selection_state.dragging
                        dp = pos - self.selection_state.last_drag_pos
                        self.selection_state.last_drag_pos = pos
                        self.move_selection(dp)
                        cursor = self.get_cursor()
                        changed = True
            else:
                if self.selection_state.rect is None or not self.selection_state.rect.contains(pos):
                    return
                if self.selection_state.current_mode == 'selected':
                    if self.selection_state.rect is not None and self.selection_state.rect.contains(pos):
                        self.selection_state.drag_corner = self.get_drag_corner(pos)
                        self.selection_state.in_selection = True
                        cursor = self.get_cursor()
                        changed = True
        finally:
            if changed:
                self.update()
            self.setCursor(cursor)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.selection_state.dragging = self.selection_state.last_drag_pos = None
            if self.selection_state.current_mode == 'select':
                r = self.selection_state.rect
                if r is None or max(r.width(), r.height()) < 3:
                    self.selection_state.reset()
                else:
                    self.selection_state.current_mode = 'selected'
                self.selection_state_changed.emit(self.has_selection)
            elif self.selection_state.current_mode == 'selected' and self.selection_state.rect is not None and self.selection_state.rect.contains(ev.pos()):
                self.setCursor(self.get_cursor())
            self.update()
    # }}}

    def keyPressEvent(self, ev):
        k = ev.key()
        if k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down) and self.has_selection:
            ev.accept()
            delta = 10 if ev.modifiers() & Qt.ShiftModifier else 1
            x = y = 0
            if k in (Qt.Key_Left, Qt.Key_Right):
                x = delta * (-1 if k == Qt.Key_Left else 1)
            else:
                y = delta * (-1 if k == Qt.Key_Up else 1)
            self.move_selection_rect(x, y)
            self.update()
        else:
            return QWidget.keyPressEvent(self, ev)

    # Painting {{{
    @painter
    def draw_background(self, painter):
        painter.fillRect(self.rect(), self.BACKGROUND)

    @painter
    def draw_image_error(self, painter):
        font = painter.font()
        font.setPointSize(3 * font.pointSize())
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(Qt.black))
        painter.drawText(self.rect(), Qt.AlignCenter, _('Not a valid image'))

    def load_pixmap(self):
        canvas_size = self.rect().width(), self.rect().height()
        if self.last_canvas_size != canvas_size:
            if self.last_canvas_size is not None and self.selection_state.rect is not None:
                self.selection_state.reset()
                # TODO: Migrate the selection rect
            self.last_canvas_size = canvas_size
            self.current_scaled_pixmap = None
        if self.current_scaled_pixmap is None:
            pwidth, pheight = self.last_canvas_size
            i = self.current_image
            width, height = i.width(), i.height()
            scaled, width, height = fit_image(width, height, pwidth, pheight)
            if scaled:
                i = self.current_image.scaled(width, height, transformMode=Qt.SmoothTransformation)
            self.current_scaled_pixmap = QPixmap.fromImage(i)

    @painter
    def draw_pixmap(self, painter):
        p = self.current_scaled_pixmap
        width, height = p.width(), p.height()
        pwidth, pheight = self.last_canvas_size
        x = int(abs(pwidth - width)/2.)
        y = int(abs(pheight - height)/2.)
        self.target = QRectF(x, y, width, height)
        painter.drawPixmap(self.target, p, QRectF(p.rect()))

    @painter
    def draw_selection_rect(self, painter):
        cr, sr = self.target, self.selection_state.rect
        painter.setPen(self.SELECT_PEN)
        painter.setRenderHint(QPainter.Antialiasing, False)
        if self.selection_state.current_mode == 'selected':
            # Shade out areas outside the selection rect
            for r in (
                QRectF(cr.topLeft(), QPointF(sr.left(), cr.bottom())),  # left
                QRectF(QPointF(sr.left(), cr.top()), sr.topRight()),  # top
                QRectF(QPointF(sr.right(), cr.top()), cr.bottomRight()),  # right
                QRectF(sr.bottomLeft(), QPointF(sr.right(), cr.bottom())),  # bottom
            ):
                painter.fillRect(r, self.SHADE_COLOR)

            dr = self.get_drag_rect()
            if self.selection_state.in_selection and dr is not None:
                # Draw the resize rectangle
                painter.save()
                painter.setCompositionMode(QPainter.RasterOp_SourceAndNotDestination)
                painter.setClipRect(sr.adjusted(1, 1, -1, -1))
                painter.drawRect(dr)
                painter.restore()

        # Draw the selection rectangle
        painter.setCompositionMode(QPainter.RasterOp_SourceAndNotDestination)
        painter.drawRect(sr)

    def paintEvent(self, event):
        QWidget.paintEvent(self, event)
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        try:
            self.draw_background(p)
            if self.original_image_data is None:
                return
            if not self.is_valid:
                return self.draw_image_error(p)
            self.load_pixmap()
            self.draw_pixmap(p)
            if self.selection_state.rect is not None:
                self.draw_selection_rect(p)
        finally:
            p.end()
    # }}}

if __name__ == '__main__':
    app = QApplication([])
    with open(sys.argv[-1], 'rb') as f:
        data = f.read()
    c = Canvas()
    c.load_image(data)
    c.show()
    app.exec_()
