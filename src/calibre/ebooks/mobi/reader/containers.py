#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from struct import unpack_from, error

from calibre.utils.imghdr import what


def find_imgtype(data):
    return what(None, data) or 'unknown'


class Container:

    def __init__(self, data):
        self.is_image_container = False
        self.resource_index = 0

        if len(data) > 60 and data[48:52] == b'EXTH':
            length, num_items = unpack_from(b'>LL', data, 52)
            pos = 60
            while pos < 60 + length - 8:
                try:
                    idx, size = unpack_from(b'>LL', data, pos)
                except error:
                    break
                pos += 8
                size -= 8
                if size < 0:
                    break
                if idx == 539:
                    self.is_image_container = data[pos:pos+size] == b'application/image'
                    break
                pos += size

    def load_image(self, data):
        self.resource_index += 1
        if self.is_image_container:
            data = data[12:]
            imgtype = find_imgtype(data)
            if imgtype != 'unknown':
                return data, imgtype
        return None, None


