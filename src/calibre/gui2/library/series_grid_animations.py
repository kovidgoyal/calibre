#!/usr/bin/env python
# License: GPLv3

import math

from qt.core import QColor, QLinearGradient, QRect, QRectF


def paint_slide(painter, rect, old_cover, new_cover, progress, direction, horizontal=False):
    distance = rect.width() if horizontal else rect.height()
    if direction > 0:
        painter.drawPixmap(rect, new_cover)
        offset = int(distance * progress)
        painter.drawPixmap(QRect(rect).translated(offset if horizontal else 0, 0 if horizontal else offset), old_cover)
    else:
        painter.drawPixmap(rect, old_cover)
        offset = -int(distance * (1 - progress))
        painter.drawPixmap(QRect(rect).translated(offset if horizontal else 0, 0 if horizontal else offset), new_cover)


def paint_page_curl(painter, rect, old_cover, new_cover, progress, direction, horizontal=False, skew=0.0):
    """Project a curled page as narrow textured strips over the next cover.

    A cylindrical fold compresses the front texture and reverses the back face.
    The fold shadow and a pale paper tint distinguish it from a flat slide.
    No new image decoding, offscreen buffers or GPU context are needed.
    """
    if direction > 0:
        base, page, amount = new_cover, old_cover, progress
    else:
        base, page, amount = old_cover, new_cover, 1 - progress
    painter.drawPixmap(rect, base)
    if amount <= 0:
        painter.drawPixmap(rect, page)
        return
    if amount >= 1:
        return

    # Work in fold coordinates; swap axes for a horizontal turn.
    def area(start, extent, source=False):
        width, height = (page.width(), page.height()) if source else (rect.width(), rect.height())
        left, top = (0, 0) if source else (rect.left(), rect.top())
        if horizontal:
            return QRectF(left + width - start - extent, top, extent, height)
        return QRectF(left, top + start, width, extent)

    painter.save()
    # A small oblique fold suggests lifting a corner. The angle stays fixed
    # for this turn, and vanishes at both endpoints to avoid a visible jump.
    tilt = skew * math.sin(math.pi * amount)
    if tilt:
        painter.translate(rect.center())
        painter.shear(0, tilt) if horizontal else painter.shear(tilt, 0)
        painter.translate(-rect.center())
    height = rect.width() if horizontal else rect.height()
    texture_length = page.width() if horizontal else page.height()
    fold = height * amount
    radius = min(height * 0.13 * math.sin(math.pi * amount), fold / math.pi, (height - fold) / math.pi)
    if radius < 0.5:
        radius = 0

    # The portion of the cover that has not reached the fold stays stationary.
    flat = area(fold, height - fold)
    source = area(texture_length * amount, texture_length * (1 - amount), source=True)
    painter.drawPixmap(flat, page, source)
    if not radius:
        painter.restore()
        return

    if horizontal:
        top = rect.left() + height - fold + radius
        shadow = QLinearGradient(top + radius * 0.4, 0, top - radius * 0.2, 0)
    else:
        top = rect.top() + fold - radius
        shadow = QLinearGradient(0, top - radius * 0.4, 0, top + radius * 0.2)
    shadow.setColorAt(0, QColor(0, 0, 0, 0))
    shadow.setColorAt(1, QColor(0, 0, 0, 105))
    painter.fillRect(area(fold - radius * 1.4, radius * 0.6), shadow)

    # Front and back halves of the cylinder. Strip count depends on the fold's
    # screen size, with a fixed cap to keep repaint work bounded.
    strips = min(24, max(8, int(radius / 2)))
    step = math.pi / (2 * strips)
    for back in (False, True):
        for strip in range(strips):
            angle = strip * step + (math.pi / 2 if back else 0)
            end = angle + step
            y1 = fold - radius * math.sin(angle)
            y2 = fold - radius * math.sin(end)
            target = area(min(y1, y2), max(0.6, abs(y2 - y1) + 0.3))
            source_top = max(0, (fold - radius * end) / height * texture_length)
            source_bottom = max(0, (fold - radius * angle) / height * texture_length)
            source_strip = area(source_top, max(0.1, source_bottom - source_top), source=True)
            if back:
                painter.save()
                if horizontal:
                    painter.translate(target.left() + target.right(), 0)
                    painter.scale(-1, 1)
                else:
                    painter.translate(0, target.top() + target.bottom())
                    painter.scale(1, -1)
                painter.drawPixmap(target, page, source_strip)
                painter.restore()
                shade = int(170 + 55 * math.sin((angle + end) / 2))
                painter.fillRect(target, QColor(244, 240, 225, shade))
            else:
                painter.drawPixmap(target, page, source_strip)
                shade = int(90 * math.sin((angle + end) / 2))
                painter.fillRect(target, QColor(0, 0, 0, shade))
    painter.restore()
