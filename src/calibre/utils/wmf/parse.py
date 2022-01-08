#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, struct

from calibre.utils.wmf import create_bmp_from_dib, to_png


class WMFHeader:

    '''
    For header documentation, see
    http://www.skynet.ie/~caolan/publink/libwmf/libwmf/doc/ora-wmf.html
    '''

    def __init__(self, data, log, verbose):
        self.log, self.verbose = log, verbose
        offset = 0
        file_type, header_size, windows_version = struct.unpack_from('<HHH', data)
        offset += 6

        if header_size != 9:
            raise ValueError('Not a WMF file')

        file_size, num_of_objects = struct.unpack_from('<IH', data, offset)

        if file_size * 2 != len(data):
            # file size is in 2-byte units
            raise ValueError('WMF file header specifies incorrect file size')
        offset += 6

        self.records_start_at = header_size * 2


class WMF:

    def __init__(self, log=None, verbose=0):
        if log is None:
            from calibre.utils.logging import default_log as log
        self.log = log
        self.verbose = verbose

        self.map_mode = None
        self.window_origin = None
        self.window_extent = None
        self.bitmaps = []

        self.function_map = {  # {{{
                30: 'SaveDC',
                53: 'RealizePalette',
                55: 'SetPalEntries',
                79: 'StartPage',
                80: 'EndPage',
                82: 'AbortDoc',
                94: 'EndDoc',
                258: 'SetBkMode',
                259: 'SetMapMode',
                260: 'SetROP2',
                261: 'SetRelabs',
                262: 'SetPolyFillMode',
                263: 'SetStretchBltMode',
                264: 'SetTextCharExtra',
                295: 'RestoreDC',
                298: 'InvertRegion',
                299: 'PaintRegion',
                300: 'SelectClipRegion',
                301: 'SelectObject',
                302: 'SetTextAlign',
                313: 'ResizePalette',
                332: 'ResetDc',
                333: 'StartDoc',
                496: 'DeleteObject',
                513: 'SetBkColor',
                521: 'SetTextColor',
                522: 'SetTextJustification',
                523: 'SetWindowOrg',
                524: 'SetWindowExt',
                525: 'SetViewportOrg',
                526: 'SetViewportExt',
                527: 'OffsetWindowOrg',
                529: 'OffsetViewportOrg',
                531: 'LineTo',
                532: 'MoveTo',
                544: 'OffsetClipRgn',
                552: 'FillRegion',
                561: 'SetMapperFlags',
                564: 'SelectPalette',
                1040: 'ScaleWindowExt',
                1042: 'ScaleViewportExt',
                1045: 'ExcludeClipRect',
                1046: 'IntersectClipRect',
                1048: 'Ellipse',
                1049: 'FloodFill',
                1051: 'Rectangle',
                1055: 'SetPixel',
                1065: 'FrameRegion',
                1352: 'ExtFloodFill',
                1564: 'RoundRect',
                1565: 'PatBlt',
                2071: 'Arc',
                2074: 'Pie',
                2096: 'Chord',
                3379: 'SetDibToDev',
                247: 'CreatePalette',
                248: 'CreateBrush',
                322: 'DibCreatePatternBrush',
                496: 'DeleteObject',
                505: 'CreatePatternBrush',
                762: 'CreatePenIndirect',
                763: 'CreateFontIndirect',
                764: 'CreateBrushIndirect',
                765: 'CreateBitmapIndirect',
                804: 'Polygon',
                805: 'Polyline',
                1078: 'AnimatePalette',
                1313: 'TextOut',
                1336: 'PolyPolygon',
                1574: 'Escape',
                1583: 'DrawText',
                1790: 'CreateBitmap',
                1791: 'CreateRegion',
                2338: 'BitBlt',
                2368: 'DibBitblt',
                2610: 'ExtTextOut',
                2851: 'StretchBlt',
                2881: 'DibStretchBlt',
                3907: 'StretchDIBits'
        }  # }}}

    def __call__(self, stream_or_data):
        data = stream_or_data
        if hasattr(data, 'read'):
            data = data.read()
        self.log.filter_level = self.log.DEBUG
        self.header = WMFHeader(data, self.log, self.verbose)

        offset = self.header.records_start_at
        hsize = struct.calcsize('<IH')
        self.records = []
        while offset < len(data)-6:
            size, func = struct.unpack_from('<IH', data, offset)
            size *= 2  # Convert to bytes
            offset += hsize
            params = b''
            delta = size - hsize
            if delta > 0:
                params = data[offset:offset+delta]
                offset += delta

            func = self.function_map.get(func, func)

            if self.verbose > 3:
                self.log.debug('WMF Record:', size, func)
            self.records.append((func, params))

        for rec in self.records:
            if not hasattr(rec[0], 'split'):
                continue
            f = getattr(self, rec[0], None)
            if callable(f):
                f(rec[1])
            elif self.verbose > 2:
                self.log.debug('Ignoring record:', rec[0])

        self.has_raster_image = len(self.bitmaps) > 0

    def SetMapMode(self, params):
        if len(params) == 2:
            self.map_mode = struct.unpack('<H', params)[0]
        else:
            self.log.warn('Invalid SetMapMode param')

    def SetWindowOrg(self, params):
        if len(params) == 4:
            self.window_origin = struct.unpack('<HH', params)
        elif len(params) == 8:
            self.window_origin = struct.unpack('<II', params)
        elif len(params) == 16:
            self.window_origin = struct.unpack('<LL', params)
        else:
            self.log.warn('Invalid SetWindowOrg param', repr(params))

    def SetWindowExt(self, params):
        if len(params) == 4:
            self.window_extent = struct.unpack('<HH', params)
        elif len(params) == 8:
            self.window_extent = struct.unpack('<II', params)
        elif len(params) == 16:
            self.window_extent = struct.unpack('<LL', params)
        else:
            self.log.warn('Invalid SetWindowExt param', repr(params))

    def DibStretchBlt(self, raw):
        offset = 0
        fmt = '<IHHHHHHHH'
        raster_op, src_height, src_width, y_src, x_src, dest_height, \
            dest_width, y_dest, x_dest = struct.unpack_from('<IHHHHHHHH', raw, offset)
        offset += struct.calcsize(fmt)
        bmp_data = raw[offset:]
        bmp = create_bmp_from_dib(bmp_data)
        self.bitmaps.append(bmp)

    def to_png(self):
        bmps = list(sorted(self.bitmaps, key=lambda x: len(x)))
        bmp = bmps[-1]
        return to_png(bmp)


def wmf_unwrap(wmf_data, verbose=0):
    '''
    Return the largest embedded raster image in the WMF.
    The returned data is in PNG format.
    '''
    w = WMF(verbose=verbose)
    w(wmf_data)
    if not w.has_raster_image:
        raise ValueError('No raster image found in the WMF')
    return w.to_png()


if __name__ == '__main__':
    wmf = WMF(verbose=4)
    wmf(open(sys.argv[-1], 'rb'))
    open('/t/test.bmp', 'wb').write(wmf.bitmaps[0])
    open('/t/test.png', 'wb').write(wmf.to_png())
