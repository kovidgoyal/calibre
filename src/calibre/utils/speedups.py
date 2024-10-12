#!/usr/bin/env python
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import os


class ReadOnlyFileBuffer:

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

    def seekable(self):
        return True

    def getvalue(self):
        return self.mv

    def close(self):
        pass


def svg_path_to_painter_path(d):
    '''
    Convert a tiny SVG 1.2 path into a QPainterPath.

    :param d: The value of the d attribute of an SVG <path> tag
    '''
    from qt.core import QPainterPath
    cmd = last_cmd = b''
    path = QPainterPath()
    moveto_abs, moveto_rel = b'M', b'm'
    closepath1, closepath2 = b'Z', b'z'
    lineto_abs, lineto_rel = b'L', b'l'
    hline_abs, hline_rel = b'H', b'h'
    vline_abs, vline_rel = b'V', b'v'
    curveto_abs, curveto_rel = b'C', b'c'
    smoothcurveto_abs, smoothcurveto_rel = b'S', b's'
    quadcurveto_abs, quadcurveto_rel = b'Q', b'q'
    smoothquadcurveto_abs, smoothquadcurveto_rel = b'T', b't'

    # Store the last parsed values
    # x/y = end position
    # x1/y1 and x2/y2 = bezier control points
    x = y = x1 = y1 = x2 = y2 = 0

    if isinstance(d, str):
        d = d.encode('ascii')
    d = d.replace(b',', b' ').replace(b'\n', b' ')
    end = len(d)
    pos = [0]

    def read_byte():
        p = pos[0]
        pos[0] += 1
        return d[p:p+1]

    def parse_float():
        chars = []
        while pos[0] < end:
            c = read_byte()
            if c == b' ' and not chars:
                continue
            if c in b'-.0123456789':
                chars.append(c)
            else:
                break
        if not chars:
            raise ValueError('Premature end of input while expecting a number')
        return float(b''.join(chars))

    def parse_floats(num, x_offset=0, y_offset=0):
        for i in range(num):
            val = parse_float()
            yield val + (x_offset if i % 2 == 0 else y_offset)

    repeated_command = None

    while pos[0] < end:
        last_cmd = cmd
        cmd = read_byte() if repeated_command is None else repeated_command
        repeated_command = None

        if cmd == b' ':
            continue
        if cmd == moveto_abs:
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
        elif cmd in b'-.0123456789':
            # A new number begins
            # In this case, multiple parameters tuples are specified for the last command
            # We rewind to reparse data correctly
            pos[0] -= 1

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
