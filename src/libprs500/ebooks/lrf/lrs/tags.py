import struct, StringIO

tagparams = {}
tagnames = {}

class LRFTagException(Exception):
    def __init__(self,msg):
        self.msg=msg
    def __str__(self):
        return repr(self.msg)

def getByte(f):
    return struct.unpack("<B",f.read(1))[0];

def getWord(f):
    return struct.unpack("<H",f.read(2))[0];

def getDWord(f):
    return struct.unpack("<I",f.read(4))[0];

def getQWord(f):
    return struct.unpack("<Q",f.read(8))[0];

def def_tag(val, params, name=None):
    tagparams[val] = params
    if (name): tagnames[val] = name

class LRFTag:
    def __init__(self,f):
        if isinstance(f, basestring):
            f = StringIO.StringIO(f)
        self.fileOffset = f.tell()
        tagId = struct.unpack("<BB",f.read(2))
        if tagId[1]!=0xF5: raise LRFTagException("Bad tag ID")
        if tagId[0] not in tagparams: raise LRFTagException("Unknown tag ID: F5%02X" % tagId[0])
        params = tagparams[tagId[0]]
        if type(params) is int:
            self.params = f.read(params)
        else:
            self.params = params(f)
        if tagId[0] in tagnames: self.name = tagnames[tagId[0]]
        #else:
        #    raise LRFException("No param parser for tag ID: F5%02X" % tagId[0])
        self.tagId = 0xF500 + tagId[0]
    def __str__(self):
        s = "Tag %04X" % self.tagId
        if hasattr(self,"name"): s+=" (%s)" % self.name
        s += " at %08X, params: " % (self.fileOffset) + repr(self.params)
        return s
    def paramDWord(self):
        if len(self.params)!=4:
            raise LRFTagException("Bad parameter for tag ID: %04X" % self.tagId)
        return struct.unpack("<I",self.params)[0];
    def paramWord(self):
        if len(self.params)!=2:
            raise LRFTagException("Bad parameter for tag ID: %04X" % self.tagId)
        return struct.unpack("<H",self.params)[0];
    def paramSWord(self):
        if len(self.params)!=2:
            raise LRFTagException("Bad parameter for tag ID: %04X" % self.tagId)
        return struct.unpack("<h",self.params)[0];

#<word> count, then count <dword>s
def Tag0B_5CParser(f):
    cnt = getWord(f)
    res = []
    while cnt>0:
        res.append(getDWord(f))
        cnt -= 1
    return res

def DummyTagParser(f):
    raise LRFTagException("Uknown dummy tag at %08X" % f.tell())

#<word> size, then string of size bytes
def TagStringParser(f):
    cnt = getWord(f)
    return unicode(f.read(cnt),"utf_16")

#<dword>, then <FF16> <w:len> <len string> <w2>
def Tag78Parser(f):
    pos = f.tell()
    res = []
    res.append(getDWord(f))
    tag = LRFTag(f)
    if tag.tagId != 0xF516: raise LRFTagException("Bad tag 78 at %08X" % pos)
    res.append(tag.params)
    res.append(getWord(f))
    return res

def_tag(0x00, 6, "*ObjectStart")
def_tag(0x01, 0, "*ObjectEnd")
def_tag(0x02, 4, "*ObjectInfoLink")
def_tag(0x03, 4, "*Link")
def_tag(0x04, 4, "*StreamSize")
def_tag(0x05, 0, "*StreamStart")
def_tag(0x06, 0, "*StreamEnd")
def_tag(0x07, 4)
def_tag(0x08, 4)
def_tag(0x09, 4)
def_tag(0x0A, 4)
def_tag(0x0B, Tag0B_5CParser, "*ContainedObjectsList")
def_tag(0x0D, 2)
def_tag(0x0E, 2)
def_tag(0x11, 2)
def_tag(0x12, 2)
def_tag(0x13, 2)
def_tag(0x14, 2)
def_tag(0x15, 2)
def_tag(0x16, TagStringParser)
def_tag(0x17, 4)
def_tag(0x18, 4)
def_tag(0x19, 2)
def_tag(0x1A, 2)
def_tag(0x1B, 2)
def_tag(0x1C, 2)
def_tag(0x1D, 2)
def_tag(0x1E, 2)
def_tag(0x21, 2)
def_tag(0x22, 2)
def_tag(0x23, 2)
def_tag(0x24, 2)
def_tag(0x25, 2)
def_tag(0x26, 2)
def_tag(0x27, 2)
def_tag(0x28, 2)
def_tag(0x29, 6)
def_tag(0x2A, 2)
def_tag(0x2B, 2)
def_tag(0x2C, 2)
def_tag(0x2D, 4)
def_tag(0x2E, 2)
def_tag(0x31, 2)
def_tag(0x32, 2)
def_tag(0x33, 2)
def_tag(0x34, 4)
def_tag(0x35, 2)
def_tag(0x36, 2)
def_tag(0x37, 4)
def_tag(0x38, 2)
def_tag(0x39, 2)
def_tag(0x3A, 2)
def_tag(0x3C, 2)
def_tag(0x3D, 2)
def_tag(0x3E, 2)
def_tag(0x41, 2)
def_tag(0x42, 2)
def_tag(0x44, 4)
def_tag(0x45, 4)
def_tag(0x46, 2)
def_tag(0x47, 2)
def_tag(0x48, 2)
def_tag(0x49, 8)
def_tag(0x4A, 8)
def_tag(0x4B, 4)
def_tag(0x4C, 4)
def_tag(0x4D, 0)
def_tag(0x4E, 12)
def_tag(0x51, 2)
def_tag(0x52, 2)
def_tag(0x53, 4)
def_tag(0x54, 2, "*StreamFlags")
def_tag(0x55, TagStringParser)
def_tag(0x56, 2)
def_tag(0x57, 2)
def_tag(0x58, 2)
def_tag(0x59, TagStringParser)
def_tag(0x5A, TagStringParser)
def_tag(0x5B, 4)
def_tag(0x5C, Tag0B_5CParser)
def_tag(0x5D, TagStringParser)
def_tag(0x5E, 2)
def_tag(0x61, 2)
def_tag(0x62, 0)
def_tag(0x63, 0)
def_tag(0x64, 0)
def_tag(0x65, 0)
def_tag(0x66, 0)
def_tag(0x67, 0)
def_tag(0x68, 0)
def_tag(0x69, 0)
def_tag(0x6A, 0)
def_tag(0x6B, 0)
def_tag(0x6C, 8)
def_tag(0x6D, 2)
def_tag(0x6E, 0)
def_tag(0x71, 0)
def_tag(0x72, 0)
def_tag(0x73, 10)
def_tag(0x75, 2)
def_tag(0x76, 2)
def_tag(0x77, 2)
def_tag(0x78, Tag78Parser)
def_tag(0x79, 2)
def_tag(0x7A, 2)
def_tag(0x7B, 4)
def_tag(0x7C, 4, "*ParentPageTree")
def_tag(0x81, 0)
def_tag(0x82, 0)
def_tag(0xA1, 4)
def_tag(0xA2, 0)
def_tag(0xA5, DummyTagParser)
def_tag(0xA6, 0)
def_tag(0xA7, 4)
def_tag(0xA8, 0)
def_tag(0xA9, 0)
def_tag(0xAA, 0)
def_tag(0xAB, 0)
def_tag(0xAC, 0)
def_tag(0xAD, 0)
def_tag(0xAE, 0)
def_tag(0xB1, 0)
def_tag(0xB2, 0)
def_tag(0xB3, 0)
def_tag(0xB4, 0)
def_tag(0xB5, 0)
def_tag(0xB6, 0)
def_tag(0xB7, 0)
def_tag(0xB8, 0)
def_tag(0xB9, 0)
def_tag(0xBA, 0)
def_tag(0xBB, 0)
def_tag(0xBC, 0)
def_tag(0xBD, 0)
def_tag(0xBE, 0)
def_tag(0xC1, 0)
def_tag(0xC2, 0)
def_tag(0xC3, 2)
def_tag(0xC4, 0)
def_tag(0xC5, 2)
def_tag(0xC6, 2)
def_tag(0xC7, 0)
def_tag(0xC8, 2)
def_tag(0xC9, 0)
def_tag(0xCA, 2)
def_tag(0xCB, DummyTagParser)
def_tag(0xCC, 2)
def_tag(0xD1, 12)
def_tag(0xD2, 0)
def_tag(0xD4, 2)
def_tag(0xD6, 0)
def_tag(0xD7, 14)
def_tag(0xD8, 4)
def_tag(0xD9, 8)
def_tag(0xDA, 2)
def_tag(0xDB, 2)
def_tag(0xDC, 2)
def_tag(0xDD, 2)
def_tag(0xF1, 2)
def_tag(0xF2, 4)
def_tag(0xF3, 4)
def_tag(0xF4, 2)
def_tag(0xF5, 4)
def_tag(0xF6, 4)
def_tag(0xF7, 4)
def_tag(0xF8, 4)
def_tag(0xF9, 6)
