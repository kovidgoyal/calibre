#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

import os


class ReadOnlyFileBuffer(object):

    ''' A zero copy implementation of a file like object. Uses memoryviews for efficiency. '''

    def __init__(self, raw):
        self.sz, self.mv = len(raw), (raw if isinstance(raw, memoryview) else memoryview(raw))
        self.pos = 0

    def tell(self):
        return self.pos

    def read(self, n=None):
        if n is None:
            ans = self.mv[self.pos:]
            self.pos = self.sz
            return ans
        ans = self.mv[self.pos:self.pos+n]
        self.pos = min(self.pos + n, self.sz)
        return ans

    def seek(self, pos, whence=os.SEEK_SET):
        if whence == os.SEEK_SET:
            self.pos = pos
        elif whence == os.SEEK_END:
            self.pos = self.sz + pos
        else:
            self.pos += pos
        self.pos = max(0, min(self.pos, self.sz))
        return self.pos

    def getvalue(self):
        return self.mv

    def close(self):
        pass


def svg_path_to_painter_path(d):
    '''
    Convert a tiny SVG 1.2 path into a QPainterPath.

    :param d: The value of the d attribute of an SVG <path> tag
    '''
    from PyQt5.Qt import QPainterPath
    cmd = last_cmd = b''
    path = QPainterPath()
    moveto_abs, moveto_rel = b'Mm'
    closepath1, closepath2 = b'Zz'
    lineto_abs, lineto_rel = b'Ll'
    hline_abs, hline_rel = b'Hh'
    vline_abs, vline_rel = b'Vv'
    curveto_abs, curveto_rel = b'Cc'
    smoothcurveto_abs, smoothcurveto_rel = b'Ss'
    quadcurveto_abs, quadcurveto_rel = b'Qq'
    smoothquadcurveto_abs, smoothquadcurveto_rel = b'Tt'

    # Store the last parsed values
    # x/y = end position
    # x1/y1 and x2/y2 = bezier control points
    x = y = x1 = y1 = x2 = y2 = 0

    data = d.replace(b',', b' ').replace(b'\n', b' ')
    if isinstance(data, type('')):
        data = data.encode('ascii')
    end = len(data)
    data = ReadOnlyFileBuffer(data)

    def parse_float():
        chars = []
        while data.tell() < end:
            c = data.read(1)
            if c == b' ' and not chars:
                continue
            if c == b'-' or b'0' <= c[0] <= b'9' or c == b'.':
                chars.append(c[0])
            else:
                break
        if not chars:
            raise ValueError('Premature end of input while expecting a number')
        return float(b''.join(chars))

    def parse_floats(num, x_offset=0, y_offset=0):
        for i in xrange(num):
            val = parse_float()
            yield val + (x_offset if i % 2 == 0 else y_offset)

    repeated_command = None

    while data.tell() < end:
        last_cmd = cmd
        cmd = data.read(1) if repeated_command is None else repeated_command
        repeated_command = None

        if cmd == b' ':
            continue
        elif cmd == moveto_abs:
            x, y = parse_float(), parse_float()
            path.moveTo(x, y)
        elif cmd == moveto_rel:
            x += parse_float()
            y += parse_float()
            path.moveTo(x, y)
        elif cmd == closepath1 or cmd == closepath2:
            path.closeSubpath()
        elif cmd == lineto_abs:
            x, y = parse_floats(2)
            path.lineTo(x, y)
        elif cmd == lineto_rel:
            x += parse_float()
            y += parse_float()
            path.lineTo(x, y)
        elif cmd == hline_abs:
            x = parse_float()
            path.lineTo(x, y)
        elif cmd == hline_rel:
            x += parse_float()
            path.lineTo(x, y)
        elif cmd == vline_abs:
            y = parse_float()
            path.lineTo(x, y)
        elif cmd == vline_rel:
            y += parse_float()
            path.lineTo(x, y)
        elif cmd == curveto_abs:
            x1, y1, x2, y2, x, y = parse_floats(6)
            path.cubicTo(x1, y1, x2, y2, x, y)
        elif cmd == curveto_rel:
            x1, y1, x2, y2, x, y = parse_floats(6, x, y)
            path.cubicTo(x1, y1, x2, y2, x, y)
        elif cmd == smoothcurveto_abs:
            if last_cmd == curveto_abs or last_cmd == curveto_rel or last_cmd == smoothcurveto_abs or last_cmd == smoothcurveto_rel:
                x1 = 2 * x - x2
                y1 = 2 * y - y2
            else:
                x1, y1 = x, y
            x2, y2, x, y = parse_floats(4)
            path.cubicTo(x1, y1, x2, y2, x, y)
        elif cmd == smoothcurveto_rel:
            if last_cmd == curveto_abs or last_cmd == curveto_rel or last_cmd == smoothcurveto_abs or last_cmd == smoothcurveto_rel:
                x1 = 2 * x - x2
                y1 = 2 * y - y2
            else:
                x1, y1 = x, y
            x2, y2, x, y = parse_floats(4, x, y)
            path.cubicTo(x1, y1, x2, y2, x, y)
        elif cmd == quadcurveto_abs:
            x1, y1, x, y = parse_floats(4)
            path.quadTo(x1, y1, x, y)
        elif cmd == quadcurveto_rel:
            x1, y1, x, y = parse_floats(4, x, y)
            path.quadTo(x1, y1, x, y)
        elif cmd == smoothquadcurveto_abs:
            if last_cmd in (quadcurveto_abs, quadcurveto_rel, smoothquadcurveto_abs, smoothquadcurveto_rel):
                x1 = 2 * x - x1
                y1 = 2 * y - y1
            else:
                x1, y1 = x, y
            x, y = parse_floats(2)
            path.quadTo(x1, y1, x, y)
        elif cmd == smoothquadcurveto_rel:
            if last_cmd in (quadcurveto_abs, quadcurveto_rel, smoothquadcurveto_abs, smoothquadcurveto_rel):
                x1 = 2 * x - x1
                y1 = 2 * y - y1
            else:
                x1, y1 = x, y
            x, y = parse_floats(2, x, y)
            path.quadTo(x1, y1, x, y)
        elif cmd[0] in b'-.' or b'0' <= cmd[0] <= b'9':
            # A new number begins
            # In this case, multiple parameters tuples are specified for the last command
            # We rewind to reparse data correctly
            data.seek(-1, os.SEEK_CUR)

            # Handle extra parameters
            if last_cmd == moveto_abs:
                repeated_command = cmd = lineto_abs
            elif last_cmd == moveto_rel:
                repeated_command = cmd = lineto_rel
            elif last_cmd in (closepath1, closepath2):
                raise ValueError('Extra parameters after close path command')
            elif last_cmd in (
                lineto_abs, lineto_rel, hline_abs, hline_rel, vline_abs,
                vline_rel, curveto_abs, curveto_rel,smoothcurveto_abs,
                smoothcurveto_rel, quadcurveto_abs, quadcurveto_rel,
                smoothquadcurveto_abs, smoothquadcurveto_rel
            ):
                repeated_command = cmd = last_cmd
        else:
            raise ValueError('Unknown path command: %s' % cmd)
    return path
