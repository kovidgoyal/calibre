

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
''''''

import struct

from calibre.ebooks.lrf import LRFParseError
from polyglot.builtins import unicode_type


class Tag(object):

    tags = {
                0x00 : (6, "*ObjectStart"),
                0x01 : (0, "*ObjectEnd"),
                0x02 : (4, "*ObjectInfoLink"),
                0x03 : (4, "*Link"),
                0x04 : (4, "*StreamSize"),
                0x05 : (0, "*StreamStart"),
                0x06 : (0, "*StreamEnd"),
                0x07 : (4, None),
                0x08 : (4, None),
                0x09 : (4, None),
                0x0A : (4, None),
                0x0B : ("type_one", "*ContainedObjectsList"),
                0x0D : (2, None),
                0x0E : (2, None),
                0x11 : (2, None),
                0x12 : (2, None),
                0x13 : (2, None),
                0x14 : (2, None),
                0x15 : (2, None),
                0x16 : ("string", None),
                0x17 : (4, None),
                0x18 : (4, None),
                0x19 : (2, None),
                0x1A : (2, None),
                0x1B : (2, None),
                0x1C : (2, None),
                0x1D : (2, None),
                0x1E : (2, None),
                0x21 : (2, None),
                0x22 : (2, None),
                0x23 : (2, None),
                0x24 : (2, None),
                0x25 : (2, None),
                0x26 : (2, None),
                0x27 : (2, None),
                0x28 : (2, None),
                0x29 : (6, None),
                0x2A : (2, None),
                0x2B : (2, None),
                0x2C : (2, None),
                0x2D : (4, None),
                0x2E : (2, None),
                0x31 : (2, None),
                0x32 : (2, None),
                0x33 : (2, None),
                0x34 : (4, None),
                0x35 : (2, None),
                0x36 : (2, None),
                0x37 : (4, None),
                0x38 : (2, None),
                0x39 : (2, None),
                0x3A : (2, None),
                0x3C : (2, None),
                0x3D : (2, None),
                0x3E : (2, None),
                0x41 : (2, None),
                0x42 : (2, None),
                0x44 : (4, None),
                0x45 : (4, None),
                0x46 : (2, None),
                0x47 : (2, None),
                0x48 : (2, None),
                0x49 : (8, None),
                0x4A : (8, None),
                0x4B : (4, None),
                0x4C : (4, None),
                0x4D : (0, None),
                0x4E : (12, None),
                0x51 : (2, None),
                0x52 : (2, None),
                0x53 : (4, None),
                0x54 : (2, "*StreamFlags"),
                0x55 : ("string", None),
                0x56 : (2, None),
                0x57 : (2, None),
                0x58 : (2, None),
                0x59 : ("string", None),
                0x5A : ("string", None),
                0x5B : (4, None),
                0x5C : ("type_one", None),
                0x5D : ("string", None),
                0x5E : (2, None),
                0x61 : (2, None),
                0x62 : (0, None),
                0x63 : (0, None),
                0x64 : (0, None),
                0x65 : (0, None),
                0x66 : (0, None),
                0x67 : (0, None),
                0x68 : (0, None),
                0x69 : (0, None),
                0x6A : (0, None),
                0x6B : (0, None),
                0x6C : (8, None),
                0x6D : (2, None),
                0x6E : (0, None),
                0x71 : (0, None),
                0x72 : (0, None),
                0x73 : (10, None),
                0x75 : (2, None),
                0x76 : (2, None),
                0x77 : (2, None),
                0x78 : ("tag_78", None),
                0x79 : (2, None),
                0x7A : (2, None),
                0x7B : (4, None),
                0x7C : (4, "*ParentPageTree"),
                0x81 : (0, None),
                0x82 : (0, None),
                0xA1 : (4, None),
                0xA2 : (0, None),
                0xA5 : ("unknown", None),
                0xA6 : (0, None),
                0xA7 : (4, None),
                0xA8 : (0, None),
                0xA9 : (0, None),
                0xAA : (0, None),
                0xAB : (0, None),
                0xAC : (0, None),
                0xAD : (0, None),
                0xAE : (0, None),
                0xB1 : (0, None),
                0xB2 : (0, None),
                0xB3 : (0, None),
                0xB4 : (0, None),
                0xB5 : (0, None),
                0xB6 : (0, None),
                0xB7 : (0, None),
                0xB8 : (0, None),
                0xB9 : (0, None),
                0xBA : (0, None),
                0xBB : (0, None),
                0xBC : (0, None),
                0xBD : (0, None),
                0xBE : (0, None),
                0xC1 : (0, None),
                0xC2 : (0, None),
                0xC3 : (2, None),
                0xC4 : (0, None),
                0xC5 : (2, None),
                0xC6 : (2, None),
                0xC7 : (0, None),
                0xC8 : (2, None),
                0xC9 : (0, None),
                0xCA : (2, None),
                0xCB : ("unknown", None),
                0xCC : (2, None),
                0xD1 : (12, None),
                0xD2 : (0, None),
                0xD4 : (2, None),
                0xD6 : (0, None),
                0xD7 : (14, None),
                0xD8 : (4, None),
                0xD9 : (8, None),
                0xDA : (2, None),
                0xDB : (2, None),
                0xDC : (2, None),
                0xDD : (2, None),
                0xF1 : (2, None),
                0xF2 : (4, None),
                0xF3 : (4, None),
                0xF4 : (2, None),
                0xF5 : (4, None),
                0xF6 : (4, None),
                0xF7 : (4, None),
                0xF8 : (4, None),
                0xF9 : (6, None),
                }
    name_map = {}
    for key in tags.keys():
        temp = tags[key][1]
        if temp is not None:
            name_map[key] = temp

    def __init__(self, stream):
        self.offset = stream.tell()
        tag_id = struct.unpack("<BB", stream.read(2))
        if tag_id[1] != 0xF5:
            raise LRFParseError("Bad tag ID %02X at %d"%(tag_id[1], self.offset))
        if tag_id[0] not in self.__class__.tags:
            raise LRFParseError("Unknown tag ID: F5%02X" % tag_id[0])

        self.id = 0xF500 + tag_id[0]

        size, self.name = self.__class__.tags[tag_id[0]]
        if isinstance(size, unicode_type):
            parser = getattr(self, size + '_parser')
            self.contents = parser(stream)
        else:
            self.contents = stream.read(size)

    def __str__(self):
        s = "Tag %04X " % self.id
        if self.name:
            s += self.name
        s += " at %08X, contents: %s" % (self.offset, repr(self.contents))
        return s

    @property
    def byte(self):
        if len(self.contents) != 1:
            raise LRFParseError("Bad parameter for tag ID: %04X" % self.id)
        return struct.unpack("<B", self.contents)[0]

    @property
    def word(self):
        if len(self.contents) != 2:
            raise LRFParseError("Bad parameter for tag ID: %04X" % self.id)
        return struct.unpack("<H", self.contents)[0]

    @property
    def sword(self):
        if len(self.contents) != 2:
            raise LRFParseError("Bad parameter for tag ID: %04X" % self.id)
        return struct.unpack("<h", self.contents)[0]

    @property
    def dword(self):
        if len(self.contents) != 4:
            raise LRFParseError("Bad parameter for tag ID: %04X" % self.id)
        return struct.unpack("<I", self.contents)[0]

    def dummy_parser(self, stream):
        raise LRFParseError("Unknown tag at %08X" % stream.tell())

    @classmethod
    def string_parser(self, stream):
        size = struct.unpack("<H", stream.read(2))[0]
        return unicode_type(stream.read(size), "utf_16")

    def type_one_parser(self, stream):
        cnt = struct.unpack("<H", stream.read(2))[0]
        res = []
        while cnt > 0:
            res.append(struct.unpack("<I", stream.read(4))[0])
            cnt -= 1
        return res

    def tag_78_parser(self, stream):
        pos = stream.tell()
        res = []
        res.append(struct.unpack("<I", stream.read(4))[0])
        tag = Tag(stream)
        if tag.id != 0xF516:
            raise LRFParseError("Bad tag 78 at %08X" % pos)
        res.append(tag.contents)
        res.append(struct.unpack("<H", stream.read(2))[0])
        return res
