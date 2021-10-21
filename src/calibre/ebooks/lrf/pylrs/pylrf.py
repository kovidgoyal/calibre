#!/usr/bin/env python


"""
    pylrf.py -- very low level interface to create lrf files.  See pylrs for
    higher level interface that can use this module to render books to lrf.
"""
import struct
import zlib
import io
import codecs
import os

from .pylrfopt import tagListOptimizer
from polyglot.builtins import iteritems, string_or_bytes

PYLRF_VERSION = "1.0"

#
# Acknowledgement:
#   This software would not have been possible without the pioneering
#   efforts of the author of lrf2lrs.py, Igor Skochinsky.
#
# Copyright (c) 2007 Mike Higgins (Falstaff)
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

#
# Change History:
#
# V1.0 06 Feb 2007
# Initial Release.

#
# Current limitations and bugs:
#   Never "scrambles" any streams (even if asked to).  This does not seem
#   to hurt anything.
#
#   Not based on any official documentation, so many assumptions had to be made.
#
#   Can be used to create lrf files that can lock up an eBook reader.
#   This is your only warning.
#
#   Unsupported objects: Canvas, Window, PopUpWindow, Sound, Import,
#                        SoundStream, ObjectInfo
#
#   The only button type supported is JumpButton.
#
#   Unsupported tags: SoundStop, Wait, pos on BlockSpace (and those used by
#                     unsupported objects).
#
#   Tags supporting Japanese text and Asian layout have not been tested.
#
#   Tested on Python 2.4 and 2.5, Windows XP and Sony PRS-500.
#
#   Commented even less than pylrs, but not very useful when called directly,
#   anyway.
#


class LrfError(Exception):
    pass


def writeByte(f, byte):
    f.write(struct.pack("<B", byte))


def writeWord(f, word):
    if int(word) > 65535:
        raise LrfError('Cannot encode a number greater than 65535 in a word.')
    if int(word) < 0:
        raise LrfError('Cannot encode a number < 0 in a word: '+str(word))
    f.write(struct.pack("<H", int(word)))


def writeSignedWord(f, sword):
    f.write(struct.pack("<h", int(float(sword))))


def writeWords(f, *words):
    f.write(struct.pack("<%dH" % len(words), *words))


def writeDWord(f, dword):
    f.write(struct.pack("<I", int(dword)))


def writeDWords(f, *dwords):
    f.write(struct.pack("<%dI" % len(dwords), *dwords))


def writeQWord(f, qword):
    f.write(struct.pack("<Q", qword))


def writeZeros(f, nZeros):
    f.write(b"\0" * nZeros)


def writeString(f, s):
    f.write(s)


def writeIdList(f, idList):
    writeWord(f, len(idList))
    writeDWords(f, *idList)


def writeColor(f, color):
    # TODO: allow color names, web format
    f.write(struct.pack(">I", int(color, 0)))


def writeLineWidth(f, width):
    writeWord(f, int(width))


def writeUnicode(f, string, encoding):
    if isinstance(string, bytes):
        string = string.decode(encoding)
    string = string.encode("utf-16-le")
    length = len(string)
    if length > 65535:
        raise LrfError('Cannot write strings longer than 65535 characters.')
    writeWord(f, length)
    writeString(f, string)


def writeRaw(f, string, encoding):
    if isinstance(string, bytes):
        string = string.decode(encoding)

    string = string.encode("utf-16-le")
    writeString(f, string)


def writeRubyAA(f, rubyAA):
    ralign, radjust = rubyAA
    radjust = {"line-edge":0x10, "none":0}[radjust]
    ralign = {"start":1, "center":2}[ralign]
    writeWord(f, ralign | radjust)


def writeBgImage(f, bgInfo):
    imode, iid = bgInfo
    imode = {"pfix": 0, "fix":1, "tile":2, "centering":3}[imode]
    writeWord(f, imode)
    writeDWord(f, iid)


def writeEmpDots(f, dotsInfo, encoding):
    refDotsFont, dotsFontName, dotsCode = dotsInfo
    writeDWord(f, refDotsFont)
    LrfTag("fontfacename", dotsFontName).write(f, encoding)
    writeWord(f, int(dotsCode, 0))


def writeRuledLine(f, lineInfo):
    lineLength, lineType, lineWidth, lineColor = lineInfo
    writeWord(f, lineLength)
    writeWord(f, LINE_TYPE_ENCODING[lineType])
    writeWord(f, lineWidth)
    writeColor(f, lineColor)


LRF_SIGNATURE = b"L\x00R\x00F\x00\x00\x00"

# XOR_KEY = 48
XOR_KEY = 65024  # that's what lrf2lrs says -- not used, anyway...

LRF_VERSION = 1000  # is 999 for librie? lrf2lrs uses 1000

IMAGE_TYPE_ENCODING = dict(GIF=0x14, PNG=0x12, BMP=0x13, JPEG=0x11, JPG=0x11)

OBJECT_TYPE_ENCODING = dict(
        PageTree=0x01,
        Page=0x02,
        Header=0x03,
        Footer=0x04,
        PageAtr=0x05, PageStyle=0x05,
        Block=0x06,
        BlockAtr=0x07, BlockStyle=0x07,
        MiniPage=0x08,
        TextBlock=0x0A, Text=0x0A,
        TextAtr=0x0B, TextStyle=0x0B,
        ImageBlock=0x0C, Image=0x0C,
        Canvas=0x0D,
        ESound=0x0E,
        ImageStream=0x11,
        Import=0x12,
        Button=0x13,
        Window=0x14,
        PopUpWindow=0x15,
        Sound=0x16,
        SoundStream=0x17,
        Font=0x19,
        ObjectInfo=0x1A,
        BookAtr=0x1C, BookStyle=0x1C,
        SimpleTextBlock=0x1D,
        TOC=0x1E
)

LINE_TYPE_ENCODING =  {
        'none':0, 'solid':0x10, 'dashed':0x20, 'double':0x30, 'dotted':0x40
}

BINDING_DIRECTION_ENCODING = dict(Lr=1, Rl=16)


TAG_INFO = dict(
        rawtext=(0, writeRaw),
        ObjectStart=(0xF500, "<IH"),
        ObjectEnd=(0xF501,),
        # InfoLink (0xF502)
        Link=(0xF503, "<I"),
        StreamSize=(0xF504, writeDWord),
        StreamData=(0xF505, writeString),
        StreamEnd=(0xF506,),
        oddheaderid=(0xF507, writeDWord),
        evenheaderid=(0xF508, writeDWord),
        oddfooterid=(0xF509, writeDWord),
        evenfooterid=(0xF50A, writeDWord),
        ObjectList=(0xF50B, writeIdList),
        fontsize=(0xF511, writeSignedWord),
        fontwidth=(0xF512, writeSignedWord),
        fontescapement=(0xF513, writeSignedWord),
        fontorientation=(0xF514, writeSignedWord),
        fontweight=(0xF515, writeWord),
        fontfacename=(0xF516, writeUnicode),
        textcolor=(0xF517, writeColor),
        textbgcolor=(0xF518, writeColor),
        wordspace=(0xF519, writeSignedWord),
        letterspace=(0xF51A, writeSignedWord),
        baselineskip=(0xF51B, writeSignedWord),
        linespace=(0xF51C, writeSignedWord),
        parindent=(0xF51D, writeSignedWord),
        parskip=(0xF51E, writeSignedWord),
        # F51F, F520
        topmargin=(0xF521, writeWord),
        headheight=(0xF522, writeWord),
        headsep=(0xF523, writeWord),
        oddsidemargin=(0xF524, writeWord),
        textheight=(0xF525, writeWord),
        textwidth=(0xF526, writeWord),
        canvaswidth=(0xF551, writeWord),
        canvasheight=(0xF552, writeWord),
        footspace=(0xF527, writeWord),
        footheight=(0xF528, writeWord),
        bgimage=(0xF529, writeBgImage),
        setemptyview=(0xF52A, {'show':1, 'empty':0}, writeWord),
        pageposition=(0xF52B, {'any':0,'upper':1, 'lower':2}, writeWord),
        evensidemargin=(0xF52C, writeWord),
        framemode=(0xF52E,
                           {'None':0, 'curve':2, 'square':1}, writeWord),
        blockwidth=(0xF531, writeWord),
        blockheight=(0xF532, writeWord),
        blockrule=(0xF533, {"horz-fixed":0x14, "horz-adjustable":0x12,
                                 "vert-fixed":0x41, "vert-adjustable":0x21,
                                 "block-fixed":0x44, "block-adjustable":0x22},
                                 writeWord),
        bgcolor=(0xF534, writeColor),
        layout=(0xF535, {'TbRl':0x41, 'LrTb':0x34}, writeWord),
        framewidth=(0xF536, writeWord),
        framecolor=(0xF537, writeColor),
        topskip=(0xF538, writeWord),
        sidemargin=(0xF539, writeWord),
        footskip=(0xF53A, writeWord),
        align=(0xF53C, {'head':1, 'center':4, 'foot':8}, writeWord),
        column=(0xF53D, writeWord),
        columnsep=(0xF53E, writeSignedWord),
        minipagewidth=(0xF541, writeWord),
        minipageheight=(0xF542, writeWord),
        yspace=(0xF546, writeWord),
        xspace=(0xF547, writeWord),
        PutObj=(0xF549, "<HHI"),
        ImageRect=(0xF54A, "<HHHH"),
        ImageSize=(0xF54B, "<HH"),
        RefObjId=(0xF54C, "<I"),
        PageDiv=(0xF54E, "<HIHI"),
        StreamFlags=(0xF554, writeWord),
        Comment=(0xF555, writeUnicode),
        FontFilename=(0xF559, writeUnicode),
        PageList=(0xF55C, writeIdList),
        FontFacename=(0xF55D, writeUnicode),
        buttonflags=(0xF561, writeWord),
        PushButtonStart=(0xF566,),
        PushButtonEnd=(0xF567,),
        buttonactions=(0xF56A,),
        endbuttonactions=(0xF56B,),
        jumpto=(0xF56C, "<II"),
        RuledLine=(0xF573, writeRuledLine),
        rubyaa=(0xF575, writeRubyAA),
        rubyoverhang=(0xF576, {'none':0, 'auto':1}, writeWord),
        empdotsposition=(0xF577, {'before':1, 'after':2}, writeWord),
        empdots=(0xF578, writeEmpDots),
        emplineposition=(0xF579, {'before':1, 'after':2}, writeWord),
        emplinetype=(0xF57A, LINE_TYPE_ENCODING, writeWord),
        ChildPageTree=(0xF57B, "<I"),
        ParentPageTree=(0xF57C, "<I"),
        Italic=(0xF581,),
        ItalicEnd=(0xF582,),
        pstart=(0xF5A1, writeDWord),  # what goes in the dword? refesound
        pend=(0xF5A2,),
        CharButton=(0xF5A7, writeDWord),
        CharButtonEnd=(0xF5A8,),
        Rubi=(0xF5A9,),
        RubiEnd=(0xF5AA,),
        Oyamoji=(0xF5AB,),
        OyamojiEnd=(0xF5AC,),
        Rubimoji=(0xF5AD,),
        RubimojiEnd=(0xF5AE,),
        Yoko=(0xF5B1,),
        YokoEnd=(0xF5B2,),
        Tate=(0xF5B3,),
        TateEnd=(0xF5B4,),
        Nekase=(0xF5B5,),
        NekaseEnd=(0xF5B6,),
        Sup=(0xF5B7,),
        SupEnd=(0xF5B8,),
        Sub=(0xF5B9,),
        SubEnd=(0xF5BA,),
        NoBR=(0xF5BB,),
        NoBREnd=(0xF5BC,),
        EmpDots=(0xF5BD,),
        EmpDotsEnd=(0xF5BE,),
        EmpLine=(0xF5C1,),
        EmpLineEnd=(0xF5C2,),
        DrawChar=(0xF5C3, '<H'),
        DrawCharEnd=(0xF5C4,),
        Box=(0xF5C6, LINE_TYPE_ENCODING, writeWord),
        BoxEnd=(0xF5C7,),
        Space=(0xF5CA, writeSignedWord),
        textstring=(0xF5CC, writeUnicode),
        Plot=(0xF5D1, "<HHII"),
        CR=(0xF5D2,),
        RegisterFont=(0xF5D8, writeDWord),
        setwaitprop=(0xF5DA, {'replay':1, 'noreplay':2}, writeWord),
        charspace=(0xF5DD, writeSignedWord),
        textlinewidth=(0xF5F1, writeLineWidth),
        linecolor=(0xF5F2, writeColor)
    )


class ObjectTableEntry:

    def __init__(self, objId, offset, size):
        self.objId = objId
        self.offset = offset
        self.size = size

    def write(self, f):
        writeDWords(f, self.objId, self.offset, self.size, 0)


class LrfTag:

    def __init__(self, name, *parameters):
        try:
            tagInfo = TAG_INFO[name]
        except KeyError:
            raise LrfError("tag name %s not recognized" % name)

        self.name = name
        self.type = tagInfo[0]
        self.format = tagInfo[1:]

        if len(parameters) > 1:
            raise LrfError("only one parameter allowed on tag %s" % name)

        if len(parameters) == 0:
            self.parameter = None
        else:
            self.parameter = parameters[0]

    def write(self, lrf, encoding=None):
        if self.type != 0:
            writeWord(lrf, self.type)

        p = self.parameter
        if p is None:
            return

        # print "   Writing tag", self.name
        for f in self.format:
            if isinstance(f, dict):
                p = f[p]
            elif isinstance(f, string_or_bytes):
                if isinstance(p, tuple):
                    writeString(lrf, struct.pack(f, *p))
                else:
                    writeString(lrf, struct.pack(f, p))
            else:
                if f in [writeUnicode, writeRaw, writeEmpDots]:
                    if encoding is None:
                        raise LrfError("Tag requires encoding")
                    f(lrf, p, encoding)
                else:
                    f(lrf, p)


STREAM_SCRAMBLED = 0x200
STREAM_COMPRESSED = 0x100
STREAM_FORCE_COMPRESSED = 0x8100
STREAM_TOC = 0x0051


class LrfStreamBase:

    def __init__(self, streamFlags, streamData=None):
        self.streamFlags = streamFlags
        self.streamData = streamData

    def setStreamData(self, streamData):
        self.streamData = streamData

    def getStreamTags(self, optimize=False):
        # tags:
        #   StreamFlags
        #   StreamSize
        #   StreamStart
        #   (data)
        #   StreamEnd
        #
        # if flags & 0x200, stream is scrambled
        # if flags & 0x100, stream is compressed

        flags = self.streamFlags
        streamBuffer = self.streamData

        # implement scramble?  I never scramble anything...

        if flags & STREAM_FORCE_COMPRESSED == STREAM_FORCE_COMPRESSED:
            optimize = False

        if flags & STREAM_COMPRESSED == STREAM_COMPRESSED:
            uncompLen = len(streamBuffer)
            compStreamBuffer = zlib.compress(streamBuffer)
            if optimize and uncompLen <= len(compStreamBuffer) + 4:
                flags &= ~STREAM_COMPRESSED
            else:
                streamBuffer = struct.pack("<I", uncompLen) + compStreamBuffer

        return [LrfTag("StreamFlags", flags & 0x01FF),
                LrfTag("StreamSize", len(streamBuffer)),
                LrfTag("StreamData", streamBuffer),
                LrfTag("StreamEnd")]


class LrfTagStream(LrfStreamBase):

    def __init__(self, streamFlags, streamTags=None):
        LrfStreamBase.__init__(self, streamFlags)
        if streamTags is None:
            self.tags = []
        else:
            self.tags = streamTags[:]

    def appendLrfTag(self, tag):
        self.tags.append(tag)

    def getStreamTags(self, encoding,
            optimizeTags=False, optimizeCompression=False):
        stream = io.BytesIO()
        if optimizeTags:
            tagListOptimizer(self.tags)

        for tag in self.tags:
            tag.write(stream, encoding)

        self.streamData = stream.getvalue()
        stream.close()
        return LrfStreamBase.getStreamTags(self, optimize=optimizeCompression)


class LrfFileStream(LrfStreamBase):

    def __init__(self, streamFlags, filename):
        LrfStreamBase.__init__(self, streamFlags)
        with open(filename, "rb") as f:
            self.streamData = f.read()


class LrfObject:

    def __init__(self, name, objId):
        if objId <= 0:
            raise LrfError("invalid objId for " + name)

        self.name = name
        self.objId = objId
        self.tags = []
        try:
            self.type = OBJECT_TYPE_ENCODING[name]
        except KeyError:
            raise LrfError("object name %s not recognized" % name)

    def __str__(self):
        return 'LRFObject: ' + self.name + ", " + str(self.objId)

    def appendLrfTag(self, tag):
        self.tags.append(tag)

    def appendLrfTags(self, tagList):
        self.tags.extend(tagList)

    # deprecated old name
    append = appendLrfTag

    def appendTagDict(self, tagDict, genClass=None):
        #
        # This code does not really belong here, I think.  But it
        # belongs somewhere, so here it is.
        #
        composites = {}
        for name, value in iteritems(tagDict):
            if name == 'rubyAlignAndAdjust':
                continue
            if name in {
                    "bgimagemode", "bgimageid", "rubyalign", "rubyadjust",
                    "empdotscode", "empdotsfontname", "refempdotsfont"}:
                composites[name] = value
            else:
                self.append(LrfTag(name, value))

        if "rubyalign" in composites or "rubyadjust" in composites:
            ralign = composites.get("rubyalign", "none")
            radjust = composites.get("rubyadjust", "start")
            self.append(LrfTag("rubyaa", (ralign, radjust)))

        if "bgimagemode" in composites or "bgimageid" in composites:
            imode = composites.get("bgimagemode", "fix")
            iid = composites.get("bgimageid", 0)

            # for some reason, page style uses 0 for "fix"
            # we call this pfix to differentiate it
            if genClass == "PageStyle" and imode == "fix":
                imode = "pfix"

            self.append(LrfTag("bgimage", (imode, iid)))

        if "empdotscode" in composites or "empdotsfontname" in composites or \
                "refempdotsfont" in composites:
            dotscode = composites.get("empdotscode", "0x002E")
            dotsfontname = composites.get("empdotsfontname",
                    "Dutch801 Rm BT Roman")
            refdotsfont = composites.get("refempdotsfont", 0)
            self.append(LrfTag("empdots", (refdotsfont, dotsfontname,
                dotscode)))

    def write(self, lrf, encoding=None):
        # print "Writing object", self.name
        LrfTag("ObjectStart", (self.objId, self.type)).write(lrf)

        for tag in self.tags:
            tag.write(lrf, encoding)

        LrfTag("ObjectEnd").write(lrf)


class LrfToc(LrfObject):
    """
        Table of contents.  Format of toc is:
        [ (pageid, objid, string)...]
    """

    def __init__(self, objId, toc, se):
        LrfObject.__init__(self, "TOC", objId)
        streamData = self._makeTocStream(toc, se)
        self._makeStreamTags(streamData)

    def _makeStreamTags(self, streamData):
        stream = LrfStreamBase(STREAM_TOC, streamData)
        self.tags.extend(stream.getStreamTags())

    def _makeTocStream(self, toc, se):
        stream = io.BytesIO()
        nEntries = len(toc)

        writeDWord(stream, nEntries)

        lastOffset = 0
        writeDWord(stream, lastOffset)
        for i in range(nEntries - 1):
            pageId, objId, label = toc[i]
            entryLen = 4 + 4 + 2 + len(label)*2
            lastOffset += entryLen
            writeDWord(stream, lastOffset)

        for entry in toc:
            pageId, objId, label = entry
            if pageId <= 0:
                raise LrfError("page id invalid in toc: " + label)
            if objId <= 0:
                raise LrfError("textblock id invalid in toc: " + label)

            writeDWord(stream, pageId)
            writeDWord(stream, objId)
            writeUnicode(stream, label, se)

        streamData = stream.getvalue()
        stream.close()
        return streamData


class LrfWriter:

    def __init__(self, sourceEncoding):
        self.sourceEncoding = sourceEncoding

        # The following flags are just to have a place to remember these
        # values.  The flags must still be passed to the appropriate classes
        # in order to have them work.

        self.saveStreamTags = False  # used only in testing -- hogs memory

        # highly experimental -- set to True at your own risk
        self.optimizeTags = False
        self.optimizeCompression = False

        # End of placeholders

        self.rootObjId = 0
        self.rootObj = None
        self.binding = 1  # 1=front to back, 16=back to front
        self.dpi = 1600
        self.width = 600
        self.height = 800
        self.colorDepth = 24
        self.tocObjId = 0
        self.docInfoXml = ""
        self.thumbnailEncoding = "JPEG"
        self.thumbnailData = b""
        self.objects = []
        self.objectTable = []

    def getSourceEncoding(self):
        return self.sourceEncoding

    def toUnicode(self, string):
        if isinstance(string, bytes):
            string = string.decode(self.sourceEncoding)

        return string

    def getDocInfoXml(self):
        return self.docInfoXml

    def setPageTreeId(self, objId):
        self.pageTreeId = objId

    def getPageTreeId(self):
        return self.pageTreeId

    def setRootObject(self, obj):
        if self.rootObjId != 0:
            raise LrfError("root object already set")

        self.rootObjId = obj.objId
        self.rootObj = obj

    def registerFontId(self, id):
        if self.rootObj is None:
            raise LrfError("can't register font -- no root object")

        self.rootObj.append(LrfTag("RegisterFont", id))

    def setTocObject(self, obj):
        if self.tocObjId != 0:
            raise LrfError("toc object already set")

        self.tocObjId = obj.objId

    def setThumbnailFile(self, filename, encoding=None):
        with open(filename, "rb") as f:
            self.thumbnailData = f.read()

        if encoding is None:
            encoding = os.path.splitext(filename)[1][1:]

        encoding = encoding.upper()
        if encoding not in IMAGE_TYPE_ENCODING:
            raise LrfError("unknown image type: " + encoding)

        self.thumbnailEncoding = encoding

    def append(self, obj):
        self.objects.append(obj)

    def addLrfObject(self, objId):
        pass

    def writeFile(self, lrf):
        if self.rootObjId == 0:
            raise LrfError("no root object has been set")

        self.writeHeader(lrf)
        self.writeObjects(lrf)
        self.updateObjectTableOffset(lrf)
        self.updateTocObjectOffset(lrf)
        self.writeObjectTable(lrf)

    def writeHeader(self, lrf):
        writeString(lrf, LRF_SIGNATURE)
        writeWord(lrf, LRF_VERSION)
        writeWord(lrf, XOR_KEY)
        writeDWord(lrf, self.rootObjId)
        writeQWord(lrf, len(self.objects))
        writeQWord(lrf, 0)  # 0x18 objectTableOffset -- will be updated
        writeZeros(lrf, 4)  # 0x20 unknown
        writeWord(lrf, self.binding)
        writeDWord(lrf, self.dpi)
        writeWords(lrf, self.width, self.height, self.colorDepth)
        writeZeros(lrf, 20)  # 0x30 unknown
        writeDWord(lrf, self.tocObjId)
        writeDWord(lrf, 0)  # 0x48 tocObjectOffset -- will be updated
        docInfoXml = codecs.BOM_UTF8 + self.docInfoXml.encode("utf-8")
        compDocInfo = zlib.compress(docInfoXml)
        writeWord(lrf, len(compDocInfo) + 4)
        writeWord(lrf, IMAGE_TYPE_ENCODING[self.thumbnailEncoding])
        writeDWord(lrf, len(self.thumbnailData))
        writeDWord(lrf, len(docInfoXml))
        writeString(lrf, compDocInfo)
        writeString(lrf, self.thumbnailData)

    def writeObjects(self, lrf):
        # also appends object entries to the object table
        self.objectTable = []
        for obj in self.objects:
            objStart = lrf.tell()
            obj.write(lrf, self.sourceEncoding)
            objEnd = lrf.tell()
            self.objectTable.append(
                    ObjectTableEntry(obj.objId, objStart, objEnd-objStart))

    def updateObjectTableOffset(self, lrf):
        # update the offset of the object table
        tableOffset = lrf.tell()
        lrf.seek(0x18, 0)
        writeQWord(lrf, tableOffset)
        lrf.seek(0, 2)

    def updateTocObjectOffset(self, lrf):
        if self.tocObjId == 0:
            return

        for entry in self.objectTable:
            if entry.objId == self.tocObjId:
                lrf.seek(0x48, 0)
                writeDWord(lrf, entry.offset)
                lrf.seek(0, 2)
                break
        else:
            raise LrfError("toc object not in object table")

    def writeObjectTable(self, lrf):
        for tableEntry in self.objectTable:
            tableEntry.write(lrf)
