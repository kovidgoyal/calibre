#!/usr/bin/env python

"""
lrf2lrs v 0.4 2007-01-09

Copyright (c) 2006-2007 roxfan, Igor Skochinsky

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

import zlib, sys, struct, array, codecs, string, StringIO, re
from types import FunctionType

import libprs500.ebooks.lrf.lrs.tags as tags
from libprs500 import __version__, __appname__

class LRFException(Exception):
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

def getString(f):
    return tags.TagStringParser(f)

def recurseTagMap(obj, tagmap, tag, f):
    if tag.tagId in tagmap:
        h = tagmap[tag.tagId]
        if type(h[1]) is FunctionType:
            val = h[1](obj,tag,f)
        elif h[1]=='D':
            val = tag.paramDWord()
        elif h[1]=='W':
            val = tag.paramWord()
        elif h[1]=='w':
            val = tag.paramWord()
            if val>0x8000: val = val-0x10000
        elif h[1]=='B':
            val = tag.paramByte()
        elif h[1]=='P':
            val = tag.params
        elif h[1]!='':
            val = getattr(obj, h[1])(tag, f) #call obj.method(tag, f)

        if h[1]!='' and h[0]!='':
            setattr(obj, h[0], val)
            #print str(obj)+"."+h[0]+"="+str(getattr(obj, h[0]))
        return True
    elif 0 in tagmap:
        return recurseTagMap(obj, tagmap[0], tag, f)
    elif 1 in tagmap:
        for i in tagmap[1]:
            res = recurseTagMap(obj, i, tag, f)
            if res: return res
        return
    return None

def doTagMap(obj, tagmap, tag, f):
    res = recurseTagMap(obj, tagmap, tag, f)
    if res:
        return res
    else:
        raise LRFException("Unknown tag in %s: %s" % (obj.__class__.__name__,str(tag)))

def colorToString(val):
    return '0x%02X%02X%02X%02X' % (val & 0xFF, (val>>8)&0xFF, (val>>16)&0xFF, (val>>24)&0xFF)

def recurseTagMapXml(obj, tagmap, objects):
    s = ''
    for tag in tagmap:
        if tag>2:
            h = tagmap[tag]
            if len(h)<3:
                raise LRFException("Don't know how to convert tag %04X!" % (tag))
            valname = h[0]
            if valname=='':
                mapping = h[2]
                if mapping!=None:
                    if (type(mapping) is FunctionType):
                        s += mapping(obj, objects)
                    else:
                        raise LRFException("Unknown mapping type for tag %04X: %s!" % (tag, type(mapping)))
            elif hasattr(obj, valname):
                val = getattr(obj, valname)
                mapping = h[2]
                if mapping!=None:
                    if type(mapping) is str:
                        if mapping == 'C':
                            if val&0xFF!=0xFF: s += ' %s="%s"' % (valname, colorToString(val))
                        elif mapping == 'L':
                            s += ' %s="%d"' % (valname, val*5)
                        else:
                            s += ' '+valname+'="'+mapping % val+'"'
                    elif type(mapping) is FunctionType:
                        s += mapping(val)
                    elif type(mapping) is dict:
                        if val in mapping:
                            if mapping[val]!=None:
                                s += ' '+valname+'="'+mapping[val]+'"'
                        else:
                            raise LRFException("Unexpected value (%s) for tag '%s' (%04X)!" % (str(val), valname, tag))
                    else:
                        raise LRFException("Unknown mapping type for tag %04X: %s!" % (tag, type(mapping)))
        elif tag==0:
            s+=recurseTagMapXml(obj, tagmap[0], objects)
        elif tag==1:
            for i in tagmap[1]:
                s += recurseTagMapXml(obj, i, objects)
        else:
            raise LRFException("Bad tag value: %04X!" % tag)
    return s

def doTagMapXml(obj, tagmap, objects):
    res = recurseTagMapXml(obj, tagmap, objects)
    return res

def recurseTagMapXml2(obj, tagmap, objects, tag):
    s = u''
    tagId = tag.tagId
    if tagId in tagmap:
        h = tagmap[tagId]
        if len(h)<3:
            raise LRFException("Don't know how to convert tag %04X!" % (tagId))
        valname = h[0]
        if valname=='':
            mapping = h[2]
            if mapping!=None:
                if (type(mapping) is FunctionType):
                    s += mapping(obj, objects)
                else:
                    raise LRFException("Unknown mapping type for tag %04X: %s!" % (tag, type(mapping)))
        else:
            if h[1]=='D':
                val = tag.paramDWord()
            elif h[1]=='W':
                val = tag.paramWord()
            elif h[1]=='w':
                val = tag.paramWord()
                if val>0x8000: val = val-0x10000
            elif h[1]=='B':
                val = tag.paramByte()
            elif h[1]=='P':
                val = tag.params
            elif h[1]!='':
                val = getattr(obj, h[1])(tag, f) #call obj.method(tag, f)
            else:
                raise LRFException("Don't know how to get value for tag %04X!" % tagId)
            mapping = h[2]
            if type(mapping) is str:
                if mapping == 'C':
                    if val&0xFF!=0xFF: s += ' %s="%s"' % (valname, colorToString(val))
                    else: s+=' '
                else:
                    s += ' '+valname+'="'+mapping % val+'"'
            elif type(mapping) is FunctionType:
                s += mapping(val)
            elif type(mapping) is dict:
                if val in mapping:
                    s += ' '+valname+'="'+mapping[val]+'"'
                else:
                    raise LRFException("Unexpected value (%s) for tag '%s' (%04X)!" % (str(val), valname, tagId))
            else:
                raise LRFException("Unknown mapping type for tag %04X: %s!" % (tagId, type(mapping)))
    elif 0 in tagmap:
        s+=recurseTagMapXml2(obj, tagmap[0], objects, tag)
    elif 1 in tagmap:
        for i in tagmap[1]:
            s += recurseTagMapXml2(obj, i, objects, tag)
    return s

def doTagMapXml2(obj, tagmap, objects, tag):
    s = recurseTagMapXml2(obj, tagmap, objects, tag)
    if len(s)==0:
        raise LRFException("Bad tag value: %04X!" % tag.tagId)
    return s

def descrambleBuf(buf, l, xorKey):
    i = 0
    a = array.array('B',buf)
    while l>0:
        a[i] ^= xorKey
        i+=1
        l-=1
    return a.tostring()

def nullfunc(obj, objects): return ''

class LRFObject:
    tagMap = {
        0xF500: ['', '', None],
        0xF502: ['infoLink', 'D', None],
        0xF501: ['','', None]
    }
    def __init__(self, objId):
        self.objId = objId
        self.toDump = True
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def addXmlTags(self, objects):
        res = u' objid="%d"' % self.objId
        if self.__class__.__name__ == "LRFImageStream":
            label = "imagestreamlabel"
        elif self.__class__.__name__ == "LRFPopUpWin":
            label = "popupwinlabel"
        elif self.__class__.__name__ == "LRFWindow":
            label = "windowlabel"
        elif self.__class__.__name__ == "LRFESound":
            label = "esoundlabel"
        elif self.__class__.__name__ == "LRFHeader":
            label = "headerlabel"
        elif self.__class__.__name__ == "LRFFooter":
            label = "footerlabel"
        elif self.__class__.__name__[-3:] == "Atr":
            label = ""
        else:
            label = "objlabel"
        if label!="":
            res += ' %s="%s.%d"' % (label, self.__class__.__name__[3:], self.objId)
        if hasattr(self,'toclabel'):
            res += ' toclabel="%s"' % self.toclabel
        return res
    def __str__(self):
        return self.__class__.__name__+": %04X" % self.objId


class LRFStream(LRFObject):
    tagMap = {
        0xF504: ['', 'doStreamSize'],
        0xF554: ['streamFlags', 'W'],
        0xF505: ['','readStream'],
        0xF506: ['','endStream'],
        0: LRFObject.tagMap
      }
    def __init__(self, objId):
        LRFObject.__init__(self, objId)
        self.stream=''
        self.streamSize=0
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def endStream(self, tag, f):
        gotEndStream = True
    def doStreamSize(self, tag, f):
        self.streamSize = tag.paramDWord()
        if self.streamSize == 0: self.stream=''
    def readStream(self, tag, f):
        if hasattr(self,'gotEndStream') and self.gotEndStream:
            raise LRFException("There can be only one stream per object!")
        if not hasattr(self, 'streamSize'):
            raise LRFException("Stream size was not defined!")
        if not hasattr(self, 'streamFlags'):
            raise LRFException("Stream flags were not defined!")
        self.stream = f.read(self.streamSize)
        if self.streamFlags & 0x200 !=0:
            l = len(self.stream);
            key = l % self.scrambleKey + 0xF;
            if l>0x400 and (isinstance(self,LRFImageStream) or isinstance(self,LRFFont) or isinstance(self,LRFSoundStream)):
                l = 0x400;
            #print "Descrambling %X bytes with key %X" % (l, key)
            self.stream = descrambleBuf(self.stream, l, key)
        if self.streamFlags & 0x100 !=0:
            decompSize = struct.unpack("<I",self.stream[:4])[0]
            #print "Decompressing %X bytes -> %X bytes" % (len(self.stream)-4, decompSize)
            self.stream = zlib.decompress(self.stream[4:])
            if len(self.stream)!=decompSize:
                raise LRFException("Stream decompressed size is wrong!")
        off = f.tell()
        next = f.read(2)
        if next!='\x06\xF5':
            print "Warning: corrupted end-of-stream tag at %08X; skipping it"%off
        self.endStream(0,0)

#01
class LRFPageTree(LRFObject):
    tagMap = {
        0xF55C: ['pageList', 'P'],
        0: LRFObject.tagMap
      }
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def toXml(self, objects, main=False):
        self.toDump = False
        if main:
            print "Writing main pages...",
            res = u"<Main>\n"
        else:
            res = u'<Pages objid="%d">\n' % self.objId
        for i in self.pageList:
            #print "Page id=%X"% i
            res+=objects[i].toXml(objects)
        if main:
            res += u"</Main>\n"
            print "done."
        else:
            res += u"</Pages>\n"
        return res;

def bgImageToString(self, objects):
    modemap = {0: 'fix', 1: 'fix', 2: 'tile', 3: 'centering'}
    s = ''
    if hasattr(self,'bgImageMode'):
        s += ' bgimagemode="%s"' % modemap[getattr(self,'bgImageMode')]
        if hasattr(self,'bgImageId'):
            refid = getattr(self,'bgImageId')
            if refid>0: s += ' refbgimage="%d"' % refid
    return s

def parseBgImage(self, tag, f):
    self.bgImageMode, self.bgImageId = struct.unpack("<HI", tag.params)

#05
class LRFPageAtr(LRFObject):
    tagMap = {
        0xF507: ['oddheaderid', 'D', '%d'],
        0xF508: ['evenheaderid', 'D', '%d'],
        0xF509: ['oddfooterid', 'D', '%d'],
        0xF50A: ['evenfooterid', 'D', '%d'],
        0xF521: ['topmargin', 'W', '%d'],
        0xF522: ['headheight', 'W', '%d'],
        0xF523: ['headsep', 'W', '%d'],
        0xF524: ['oddsidemargin', 'W', '%d'],
        0xF52C: ['evensidemargin', 'W', '%d'],
        0xF525: ['textheight', 'W', '%d'],
        0xF526: ['textwidth', 'W', '%d'],
        0xF527: ['footspace', 'W', '%d'],
        0xF528: ['footheight', 'W', '%d'],
        0xF535: ['layout', 'W', {0x41: 'TbRl', 0x34: 'LrTb'}],
        0xF52B: ['pageposition', 'W', {0: 'any', 1:'upper', 2: 'lower'}],
        0xF52A: ['setemptyview', 'W', {1: 'show', 0: 'empty'}],
        0xF5DA: ['setwaitprop', 'W', {1: 'replay', 2: 'noreplay'}],
        0xF529: ['', parseBgImage, bgImageToString],
        0: LRFObject.tagMap
      }
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def toXml(self, objects):
        self.toDump = False
        res = u'<PageStyle stylelabel="%d"' % self.objId
        res += doTagMapXml(self, self.tagMap, objects)
        res += LRFObject.addXmlTags(self, objects)
        res += u"/>\n"
        return res;

class LRFPageContent:
   tagMap = {
       0xF503: ['', 'doContained'],
       0xF54E: ['', 'doPageDiv'],
       0xF547: ['', 'doXSpace'],
       0xF546: ['', 'doYSpace'],
       0xF548: ['', 'doPos'],
       0xF573: ['', 'doRuledLine'],
       0xF5D4: ['', 'doWait'],
       0xF5D6: ['', 'doSoundStop'],
     }
   maplinetype = {0: 'none', 0x10: 'solid', 0x20: 'dashed', 0x30: 'double', 0x40: 'dotted', 0x13: 'unknown13'}

   def __init__(self, objects):
       self.xml = u''
       self.objects = objects
       self.inBlockspace = False
   def handleTag(self, tag, f):
       #print "LRFPageContent:", tag
       return doTagMap(self, self.tagMap, tag, f)
   def closeBlockspace(self):
       if self.inBlockspace:
           self.xml += self.getBlockSpace()
           if hasattr(self,'xspace'): delattr(self,'xspace')
           if hasattr(self,'yspace'): delattr(self,'yspace')
           if hasattr(self,'pos'): delattr(self,'pos')
           self.inBlockspace = False
   def doSimpleTag(self, tag, f):
       self.closeBlockspace()
       self.xml += self.tagMap[tag.tagId][2]
   def doContained(self, tag, f):
       self.closeBlockspace()
       self.xml += self.objects[tag.paramDWord()].toXml(self.objects)
   def doPageDiv(self, tag, f):
       self.closeBlockspace()
       pars = struct.unpack("<HIHI",tag.params)
       self.xml += u'<PageDiv pain="%d" spacesize="%d" linewidth="%d" linecolor="%s"/>\n' % (pars[0], pars[1], pars[2], colorToString(pars[3]))
   def doRuledLine(self, tag, f):
       self.closeBlockspace()
       pars = struct.unpack("<HHHI",tag.params)
       self.xml += u'<RuledLine linelength="%d" linetype="%s" linewidth="%d" linecolor="%s"/>\n' % (pars[0], self.maplinetype[pars[1]], pars[2], colorToString(pars[3]))
   def doXSpace(self, tag, f):
       self.xspace = tag.paramWord()
       self.inBlockspace = True
   def doPos(self, tag, f):
       posmap = {1:'bottomleft', 2:'bottomright',3:'topright',4:'topleft', 5:'base'}
       self.pos = posmap[tag.paramWord()]
       self.inBlockspace = True
   def doYSpace(self, tag, f):
       self.yspace = tag.paramWord()
       self.inBlockspace = True
   def getBlockSpace(self):
       if hasattr(self,'pos'):
           res = u'<Locate pos="%s"' % self.pos
       else:
           res = u'<BlockSpace'
       if hasattr(self,'xspace'): res +=' xspace="%d"' % self.xspace
       if hasattr(self,'yspace'): res +=' yspace="%d"' % self.yspace
       res += '/>\n'
       return res
   def doWait(self, tag, f):
       self.closeBlockspace()
       self.xml += u'<Wait time="%d"/>\n' % tag.paramWord()
   def doSoundStop(self, tag, f):
       self.closeBlockspace()
       self.xml += u'<SoundStop/>\n'
   def toXml(self, objects):
       self.closeBlockspace()
       return self.xml

#02
class LRFPage(LRFStream):
    tagMap = {
        0xF503: ['pageStyle', 'D'],
        0xF50B: ['contents', 'P'],
        0xF571: ['',''],
        0xF57C: ['parentPageTree','D'],
        1: [LRFPageAtr.tagMap, LRFStream.tagMap]
      }
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def toXml(self, objects):
        self.toDump = False
        res = u'<Page pagestyle="%d"' % self.pageStyle
        res += doTagMapXml(self, LRFPageAtr.tagMap, objects)
        res += LRFObject.addXmlTags(self, objects)
        res += u'>\n'
        f = StringIO.StringIO(self.stream)
        l = len(self.stream)
        cont = LRFPageContent(objects)
        while f.tell()<l:
            tag = tags.LRFTag(f)
            # print tag
            if cont.handleTag(tag, f) == False:
                break
        res += cont.toXml(objects)
        res += u'</Page>\n'
        return res

#07
class LRFBlockAtr(LRFObject):
    tagMap = {
        0xF531: ['blockwidth', 'W', '%d'],
        0xF532: ['blockheight', 'W', '%d'],
        0xF533: ['blockrule', 'W', {0x14: "horz-fixed", 0x12: "horz-adjustable", 0x41: "vert-fixed", 0x21: "vert-adjustable", 0x44: "block-fixed", 0x22: "block-adjustable"}],
        0xF534: ['bgcolor', 'D', 'C'],
        0xF535: ['layout', 'W', {0x41: 'TbRl', 0x34: 'LrTb'}],
        0xF536: ['framewidth', 'W', '%d'],
        0xF537: ['framecolor', 'D', 'C'],
        0xF52E: ['framemode', 'W', {0: None, 2: 'curve',1:'square'}],
        0xF538: ['topskip', 'W', '%d'],
        0xF539: ['sidemargin', 'W', '%d'],
        0xF53A: ['footskip', 'W', '%d'],
        0xF529: ['', parseBgImage, bgImageToString],
        0: LRFObject.tagMap
      }
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def toXml(self, objects):
        self.toDump = False
        res = u'<BlockStyle stylelabel="%d"' % self.objId
        res += doTagMapXml(self, self.tagMap, objects)
        res += LRFObject.addXmlTags(self, objects)
        res += u"/>\n"
        return res;

#03
class LRFHeader(LRFStream):
   tagMap = {
       1: [LRFBlockAtr.tagMap, LRFStream.tagMap]
     }
   contentTags = {
       0xF549: ['','doPutObj']
   }
   def handleTag(self, tag, f):
       return doTagMap(self, self.tagMap, tag, f)
   def doPutObj(self, tag, f):
       pars = struct.unpack("<HHI",tag.params)
       self.xml += u'<PutObj x1="%d" y1="%d" refobj="%d"/>\n' % pars
   def toXml(self, objects):
       #print "in LRFText.toXml"
       if self.__class__.__name__ == "LRFHeader":
           res = u'<Header'
       else:
           res = u'<Footer'
       res += doTagMapXml(self, LRFBlockAtr.tagMap, objects)
       res += LRFObject.addXmlTags(self, objects)
       res += u'>\n'
       self.toDump = False
       f = StringIO.StringIO(self.stream)
       l = len(self.stream)
       self.xml = u''
       while f.tell()<l:
           tag = tags.LRFTag(f)
           #print tag
           if doTagMap(self, self.contentTags, tag, f) == False:
               break
       res += self.xml
       if self.__class__.__name__ == "LRFHeader":
           res += u'</Header>\n'
       else:
           res += u'</Footer>\n'
       return res


#04
class LRFFooter(LRFHeader):
   pass

#08
class LRFMiniPage(LRFStream):
    tagMap = {
        0xF541: ['minipagewidth', 'W', "%d"],
        0xF542: ['minipageheight', 'W', "%d"],
        1: [LRFBlockAtr.tagMap, LRFStream.tagMap]
      }
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def toXml(self, objects):
        self.toDump = False
        res = u'<MiniPage minipagewidth="%d" minipageheight="%d"' % (self.minipagewidth, self.minipageheight)
        res += doTagMapXml(self, LRFBlockAtr.tagMap, objects)
        res += LRFObject.addXmlTags(self, objects)
        res += u">\n"
        f = StringIO.StringIO(self.stream)
        l = len(self.stream)
        cont = LRFPageContent(objects)
        while f.tell()<l:
            tag = tags.LRFTag(f)
            # print tag
            if cont.handleTag(tag, f) == False:
                break
        res += cont.toXml(objects)
        res += u'</MiniPage>\n'
        return res

#06
class LRFBlock(LRFStream):
    tagMap = {
        0xF503: ['atrId', 'D'],
        1: [LRFBlockAtr.tagMap, LRFStream.tagMap]
      }
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)

    def addXmlTags(self, objects):
        res = doTagMapXml(self, LRFBlockAtr.tagMap, objects)
        res += ' blockstyle="%d"' % self.atrId
        res += LRFObject.addXmlTags(self, objects)
        return res

    def getLinkedObjectId(self):
        tag = tags.LRFTag(self.stream)
        if tag.tagId != 0xF503:
            raise LRFException("Bad block content")
        return tag.paramDWord()

    def toXml(self, objects):
        self.toDump = False
        tag = tags.LRFTag(self.stream)
        if tag.tagId != 0xF503:
            raise LRFException("Bad block content")
        obj = objects[tag.paramDWord()]
        obj.toDump = False
        if isinstance(obj, LRFSimpleText):
            name = 'SimpleTextBlock'
        elif isinstance(obj, LRFText):
            name = 'TextBlock'
        elif isinstance(obj, LRFImage):
            name = 'ImageBlock'
        elif isinstance(obj, LRFButton):
            name = 'ButtonBlock'
        else:
            raise LRFException("Unexpected block type: "+obj.__class__.__name__)
        res = u'<%s' % name
        res += obj.addXmlTags(objects)
        res += self.addXmlTags(objects)
        res += u'>\n'
        res += obj.toXml(objects)
        res += u'</%s>\n' % name
        return res

#0C
class LRFImage(LRFObject):
    tagMap = {
        0xF54A: ['', 'parseImageRect'],
        0xF54B: ['', 'parseImageSize'],
        0xF54C: ['refObjectId', 'D'],      #imagestream or import
        0xF555: ['comment', 'P'],
        0: LRFObject.tagMap
      }
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def parseImageRect(self, tag, f):
        self.imageRect = struct.unpack("<HHHH", tag.params)
    def parseImageSize(self, tag, f):
        self.imageSize = struct.unpack("<HH", tag.params)
    def addXmlTags(self, objects):
        res = u''
        if hasattr(self,'imageRect'):
            res += u' x0="%d" y0="%d" x1="%d" y1="%d"' % self.imageRect
        if hasattr(self,'imageSize'):
            res += u' xsize="%d" ysize="%d"' % self.imageSize
        if hasattr(self,'refObjectId'):
            if isinstance(objects[self.refObjectId], LRFImport):
                res += u' refimport="%d"' % self.refObjectId
            else:
                res += u' refstream="%d"' % self.refObjectId
        #res += LRFObject.addXmlTags(self, objects)
        return res
    def toXml(self, objects, noblock=False):
        self.toDump = False
        if noblock:
            res = u'<Image'
            res += self.addXmlTags(objects)
            res += LRFObject.addXmlTags(self, objects)
            if hasattr(self,'comment'):
                res += u'>\n' + self.comment + u'\n</Image>'
            else:
                res += u'/>\n'
            return res
        else:
            if hasattr(self,'comment'):
                return self.comment
            else:
                return u''

class LRFCanvasContent:
   tagMap = {
        0xF549: ['', 'doPutObj'],
      }
   def __init__(self, objects):
       self.xml = u''
       self.objects = objects
   def handleTag(self, tag, f):
       return doTagMap(self, self.tagMap, tag, f)
   def doSimpleTag(self, tag, f):
       self.closeSpan()
       self.xml += self.tagMap[tag.tagId][2]
   def doPutObj(self, tag, f):
       self.xml += u'<PutObj x1="%d" y1="%d" refobj="%d"/>\n' % struct.unpack("<HHI", tag.params)
   def toXml(self, objects):
       return self.xml

#0D
class LRFCanvas(LRFStream):
    tagMap = {
        0xF551: ['canvaswidth', 'W', "%d"],
        0xF552: ['canvasheight', 'W', "%d"],
        0xF5DA: ['', 'parseWaits', nullfunc],
        1: [LRFBlockAtr.tagMap, LRFStream.tagMap]
      }
    xmlMap = {
        0xF551: ['canvaswidth', 'W', "%d"],
        0xF552: ['canvasheight', 'W', "%d"],
        0xFF00: ['setwaitprop', 'W', {1: 'replay', 2: 'noreplay'}],
        0xFF01: ['setwaitsync', 'W', {0: 'sync', 0x10: 'async'}]
    }
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def parseWaits(self, tag, f):
        val = tag.paramWord()
        self.setwaitprop = val&0xF
        self.setwaitsync = val&0xF0
    def toXml(self, objects):
        #print "in LRFCanvas.toXml"
        self.toDump = False
        res = u'<Canvas'
        res += doTagMapXml(self, self.xmlMap, objects)
        res += doTagMapXml(self, LRFBlockAtr.tagMap, objects)
        res += LRFObject.addXmlTags(self, objects)
        res += u'>\n'
        f = StringIO.StringIO(self.stream)
        l = len(self.stream)
        cont = LRFCanvasContent(objects)
        while f.tell()<l:
            pos = f.tell()
            tag = tags.LRFTag(f)
            #print tag
            if cont.handleTag(tag, f) == False:
                break
        res += cont.toXml(objects)
        res += u'</Canvas>\n'
        return res


def rubyAlignAndAdjustToString(rubyAlignAndAdjust):
    adj = "";
    if rubyAlignAndAdjust&0xF0 == 0x10:
        adj = "line-edge"
    elif rubyAlignAndAdjust&0xF0 == 0:
        adj = "none"
    else:
        adj = "bad rubyadjust(0x%X)" % rubyAlignAndAdjust&0xF0

    if rubyAlignAndAdjust&0xF == 1:
        align = "start"
    elif rubyAlignAndAdjust&0xF == 2:
        align = "center"
    else:
        align = "bad rubyalign(0x%X)" % rubyAlignAndAdjust&0xF

    return u' rubyalign="%s" rubyadjust="%s"' % (align, adj)

def empDotsToString(self, objects):
    res = u''
    if hasattr(self,'refEmpDotsFont') and self.refEmpDotsFont!=0:
        res += u' refempdotsfont="%d"' % self.refEmpDotsFont
    if hasattr(self,'empDotsFontName') and self.empDotsFontName!="":
        res += u' empdotsfontname="%s"' % self.empDotsFontName
    if hasattr(self,'empDotsCode') and self.empDotsCode!=0:
        res += u' empdotscode="0x%04x"' % self.empDotsCode
    return res

rubyTags = {
    0xF575: ['rubyAlignAndAdjust', 'W', rubyAlignAndAdjustToString],
    0xF576: ['rubyoverhang', 'W', {0: 'none', 1:'auto'}],
    0xF577: ['empdotsposition', 'W', {1: 'before', 2:'after'}],
    0xF578: ['','parseEmpDots', empDotsToString],
    0xF579: ['emplineposition', 'W', {1: 'before', 2:'after'}],
    0xF57A: ['emplinetype', 'W', {0: 'none', 0x10: 'solid', 0x20: 'dashed', 0x30: 'double', 0x40: 'dotted'}]
}

def addRubyXmlTags(self, objects):
    return doTagMapXml(self, rubyTags, objects)

#0B
class LRFTextAtr(LRFObject):
    tagMap = {
        0xF511: ['fontsize', 'w', "%d"],
        0xF512: ['fontwidth', 'w', "%d"],
        0xF513: ['fontescapement', 'w', "%d"],
        0xF514: ['fontorientation', 'w', "%d"],
        0xF515: ['fontweight', 'W', "%d"],
        0xF516: ['fontfacename', 'P', "%s"],
        0xF517: ['textcolor', 'D', 'C'],
        0xF518: ['textbgcolor', 'D', 'C'],
        0xF519: ['wordspace', 'w', "%d"],
        0xF51A: ['letterspace', 'w', "%d"],
        0xF51B: ['baselineskip', 'w', "%d"],
        0xF51C: ['linespace', 'w', "%d"],
        0xF51D: ['parindent', 'w', "%d"],
        0xF51E: ['parskip', 'w', "%d"],
        0xF53C: ['align', 'W', {1: 'head', 4: 'center', 8: 'foot'}],
        0xF53D: ['column', 'W', "%d"],
        0xF53E: ['columnsep', 'W', "%d"],
        0xF5DD: ['charspace', 'w', "%d"],
        0xF5F1: ['textlinewidth', 'W', "L"],
        0xF5F2: ['linecolor', 'D', 'C'],
        1: [rubyTags, LRFObject.tagMap]
      }
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def parseEmpDots(self, tag, f):
        self.refEmpDotsFont, self.empDotsFontName, self.empDotsCode = tag.params;
    def toXml(self, objects):
        self.toDump = False
        res = u'<TextStyle stylelabel="%d"' % self.objId
        res += LRFObject.addXmlTags(self, objects)
        res += doTagMapXml(self, self.tagMap, objects)
        res += u"/>\n"
        return res;

class LRFTextContent:
   tagMap = {
       0xF581: ['', 'doSimpleTag', u'<Italic>'],
       0xF582: ['', 'doSimpleTag', u'</Italic>'],
       0xF5B1: ['', 'doSimpleTag', u'<Yoko>'],
       0xF5B2: ['', 'doSimpleTag', u'</Yoko>'],
       0xF5B3: ['', 'doSimpleTag', u'<Tate>'],
       0xF5B4: ['', 'doSimpleTag', u'</Tate>'],
       0xF5B5: ['', 'doSimpleTag', u'<Nekase>'],
       0xF5B6: ['', 'doSimpleTag', u'</Nekase>'],
       0xF5A1: ['', 'doBeginP'],
       0xF5A2: ['', 'doEndP'],
       0xF5A7: ['', 'doBeginCharButton'],
       0xF5A8: ['', 'doSimpleTag', u'</CharButton>'],
       0xF5A9: ['', 'doSimpleTag', u'<Rubi>'],
       0xF5AA: ['', 'doSimpleTag', u'</Rubi>'],
       0xF5AB: ['', 'doSimpleTag', u'<Oyamoji>'],
       0xF5AC: ['', 'doSimpleTag', u'</Oyamoji>'],
       0xF5AD: ['', 'doSimpleTag', u'<Rubimoji>'],
       0xF5AE: ['', 'doSimpleTag', u'</Rubimoji>'],
       0xF5B7: ['', 'doSimpleTag', u'<Sup>'],
       0xF5B8: ['', 'doSimpleTag', u'</Sup>'],
       0xF5B9: ['', 'doSimpleTag', u'<Sub>'],
       0xF5BA: ['', 'doSimpleTag', u'</Sub>'],
       0xF5BB: ['', 'doSimpleTag', u'<NoBR>'],
       0xF5BC: ['', 'doSimpleTag', u'</NoBR>'],
       0xF5BD: ['', 'doSimpleTag', u'<EmpDots>'],
       0xF5BE: ['', 'doSimpleTag', u'</EmpDots>'],
       0xF5C1: ['', 'doBeginEL'],
       0xF5C2: ['', 'doEndEL'],
       0xF5C6: ['', 'doBeginBox'],
       0xF5C7: ['', 'doSimpleTag', '</Box>'],
       0xF5CA: ['', 'doSpace'],
       0xF5CC: ['', 'doString'],
       0xF5D1: ['', 'doPlot'],
       0xF5D2: ['', 'doSimpleTag', u'<CR/>\n'],
     }
   maplinetype = {0: 'none', 0x10: 'solid', 0x20: 'dashed', 0x30: 'double', 0x40: 'dotted'}
   mapadjustment = {1: 'top', 2: 'center', 3: 'baseline', 4: 'bottom'}

   def __init__(self, objects):
       self.xml = u''
       self.objects = objects
       self.inSpan = False
       self.inSpanBegin = False
       self.inSpanEnd = False
       self.inPSpan = False
       self.spanChanges = []
   def doSpanTag(self, tag, f):
       #if self.inSpanEnd:
       #    if self.inSpan: self.inSpan = False
       #    if tag.tagId in self.spanChanges:
       #       self.spanChanges.remove(tag.tagId)
       #       return
       #    else:
       #       self.xml += u'</Span>'
       #       self.inSpanEnd = False
       if self.inSpan:
           self.xml += u'</Span>'
           self.inSpan = False
       #    self.inSpanEnd = True
       text = doTagMapXml2(self, LRFTextAtr.tagMap, self.objects, tag)
       if not self.inSpanBegin:
           self.spanText = u'<Span'
           self.inSpanBegin = True
       #    self.spanChanges.append(tag.tagId)
       self.spanText += text

   def closeSpan(self, add = True):
       if self.inSpanBegin:
           self.spanText += u'>'
           r = re.compile(r' (\w+)=".*?"(.*?)\1(=".*?")')
           m = re.search(r, self.spanText)
           while m:
               #self.xml += "\n*** before: "+self.spanText+"***\n"
               self.spanText = self.spanText[:m.start()] + m.group(2) + m.group(1) + m.group(3) + self.spanText[m.end():]
               #self.xml += "\n*** after: "+self.spanText+"***\n"
               m = re.search(r, self.spanText)
           if add:
               self.xml += self.spanText
               self.spanText = u''
           self.inSpanBegin = False
           self.inSpan = True

   def handleTag(self, tag, f):
       if tag.tagId in self.tagMap:
           return doTagMap(self, self.tagMap, tag, f)
       else:
           self.doSpanTag(tag, f)
           return True

   def doSimpleTag(self, tag, f):
       self.closeSpan()
       self.xml += self.tagMap[tag.tagId][2]

   def doSpace(self, tag, f):
       self.closeSpan()
       self.xml += u'<Space xsize="%d"/>'%tag.paramSWord()

   def doPlot(self, tag, f):
       self.closeSpan()
       pars = struct.unpack("<HHII",tag.params)
       self.xml += u'<Plot xsize="%d" ysize="%d" refobj="%d"'%pars[:3]
       self.xml += u' adjustment="%s"/>'%self.mapadjustment[pars[3]]

   def doOpenTag(self, tag, f, name):
       if self.inSpanBegin:
           self.closeSpan(False)
           self.spanText=u'<'+name+self.spanText[5:]
           self.xml += self.spanText
           self.spanText = u''
           self.inPSpan = True
           self.inSpan = False
       elif self.inSpan:
           raise LRFError("bad stuff happened")
           self.xml += u'</Span>'
           self.inSpan = False
       else:
           self.xml += u'<%s>'%name

   def doCloseTag(self, tag, f, name):
       if self.inSpanBegin:
          self.inSpanBegin = False
          self.spanText = u''
       else:
          self.closeSpan()
       if self.inSpan:
           self.xml += u'</Span>'
           self.inSpan = False
       if self.inPSpan:
           self.inPSpan = False
           self.inSpan = False
       self.xml += u'</%s>\n'%name

   def doBeginP(self, tag, f):
       self.doOpenTag(tag, f, u"P")

   def doEndP(self, tag, f):
       self.doCloseTag(tag, f, u"P")

   def doBeginEL(self, tag, f):
       self.doOpenTag(tag, f, u"EmpLine")

   def doEndEL(self, tag, f):
       self.doCloseTag(tag, f, u"EmpLine")

   def doBeginCharButton(self, tag, f):
       self.closeSpan()
       self.xml += u'<CharButton refobj="%d">' % tag.paramDWord()
   def doBeginBox(self, tag, f):
       self.closeSpan()
       self.xml += u'<Box linetype="%s">' % self.maplinetype[tag.paramWord()]
   def doString(self, tag, f):
       self.closeSpan()
       strlen = tag.paramWord()
       self.addText(f.read(strlen))
   def addText(self, text):
       self.closeSpan()
       mapping = { 0x22: u'&quot;', 0x26: u'&amp;', 0x27: u'&apos;', 0x3c: u'&lt;', 0x3e: u'&gt;' }
       s = unicode(text,"utf-16-le")
       self.xml += s.translate(mapping)
   def toXml(self, objects):
       self.closeSpan()
       return self.xml

#0A
class LRFText(LRFStream):
    tagMap = {
        0xF503: ['atrId', 'D'],
        1: [LRFTextAtr.tagMap, LRFStream.tagMap]
      }
    def parseEmpDots(self, tag, f):
        self.refEmpDotsFont, self.empDotsFontName, self.empDotsCode = tag.params;
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def addXmlTags(self, objects):
        res = u''
        #print "in LRFText.addXmlTags"
        if hasattr(self, 'atrId'):
            #print "atrId=%d" % self.atrId
            res += u' textstyle="%d"' % self.atrId
        else:
            raise LRFException("no textstyle defined!")
        res += doTagMapXml(self, LRFTextAtr.tagMap, objects)
        return res

    def toXml(self, objects):
        #print "in LRFText.toXml"
        res = u''
        #res += u'<Text id="%d">' % self.objId
        self.toDump = False
        f = StringIO.StringIO(self.stream)
        l = len(self.stream)
        cont = LRFTextContent(objects)
        while f.tell()<l:
            pos = f.tell()
            try:
                tag = tags.LRFTag(f)
                #print tag
                if cont.handleTag(tag, f) == False:
                    break
            except tags.LRFTagException:
                f.seek(pos)
                cont.addText(f.read(2))
        res += cont.toXml(objects)
        #res += u'</Text>'
        return res

#0E
class LRFESound(LRFObject):
    tagMap = {
        0xF553: ['refstream', 'D', "%d"],      #refstream
        0: LRFObject.tagMap
      }
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def toXml(self, objects, noblock=False):
        self.toDump = False
        res = u'<eSound'
        res += doTagMapXml(self, self.tagMap, objects)
        res += LRFObject.addXmlTags(self, objects)
        res += u'/>\n'
        return res

imgext = {0x11: 'jpeg', 0x12: 'png', 0x13: 'bmp', 0x14: 'gif'}

#11
class LRFImageStream(LRFStream):
    tagMap = {
        0xF555: ['comment', 'P'],
        1: [LRFStream.tagMap]
      }
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def toXml(self, objects):
        self.toDump = False
        ext = imgext[self.streamFlags & 0xFF]
        fname = 'imagestream_%d.%s' % (self.objId, ext)
        file(fname,'wb').write(self.stream)
        res = u'<ImageStream encoding="%s" file="%s"' % (ext.upper(), fname)
        res += LRFObject.addXmlTags(self, objects)
        if hasattr(self,'comment'):
            res += u'>\n' + self.comment + u'\n</ImageStream>'
        else:
            res += u'/>\n'
        return res

#12
class LRFImport(LRFStream):
   tagMap = {
       0xF50E: ['importtype', 'W'],
       0: LRFStream.tagMap
     }
   xmlMap = {
       0xF50E: ['importtype', 'W', {0x11: 'ImageStream', 0x17: 'SoundStream'}]
   }
   importTags = {
       0xF556: ['', 'doObjLink'],
       0xF50D: ['', 'doFileLink']
   }
   acctypemap = {1: 'url', 2:'cid', 3:'pass'}

   def handleTag(self, tag, f):
       return doTagMap(self, self.tagMap, tag, f)
   def addText(self, text):
       mapping = { 0x22: u'&quot;', 0x26: u'&amp;', 0x27: u'&apos;', 0x3c: u'&lt;', 0x3e: u'&gt;' }
       s = unicode(text,"utf-16-le")
       self.xml += s.translate(mapping)

   def doObjLink(self, tag, f):
       acctype = tag.paramWord()
       if f.tell()<self.streamlen:
          text = getString(f)
       else:
          text = u''
       if f.tell()<self.streamlen:
          objid = getDWord(f)
       else:
          objid = 0
       self.xml+='<ObjLink accesstype="%s" refobj="%d">%s</ObjLink>\n' % (self.acctypemap[acctype], objid, text)

   def doFileLink(self, tag, f):
       acctype = tag.paramWord()
       if f.tell()<self.streamlen:
          text = getString(f)
       else:
          text = u''
       self.xml+='<FileLink accesstype="%s">%s</FileLink>\n' % (self.acctypemap[acctype], text)

   def toXml(self, objects):
       #print "in LRFText.toXml"
       res = u'<Import'
       res += doTagMapXml(self, self.xmlMap, objects)
       res += LRFObject.addXmlTags(self, objects)
       res += u'>\n'
       self.toDump = False
       f = StringIO.StringIO(self.stream)
       self.streamlen = len(self.stream)
       self.xml = u''
       while f.tell()<self.streamlen:
           tag = tags.LRFTag(f)
           #print tag
           if doTagMap(self, self.importTags, tag, f) == False:
               break
       res += self.xml
       res += u'</Import>\n'
       return res

#13
class LRFButton(LRFObject):
    tagMap = {
        0xF503: ['', 'doRefImage'],
        0xF561: ['buttonFlags','W'],           #<Button/>
        0xF562: ['','doBaseButton'],            #<BaseButton>
        0xF563: ['',''],            #</BaseButton>
        0xF564: ['','doFocusinButton'],            #<FocusinButton>
        0xF565: ['',''],            #</FocusinButton>
        0xF566: ['','doPushButton'],            #<PushButton>
        0xF567: ['',''],            #</PushButton>
        0xF568: ['','doUpButton'],            #<UpButton>
        0xF569: ['',''],            #</UpButton>
        0xF56A: ['','doStartActions'],            #start actions
        0xF56B: ['',''],            #end actions
        0xF56C: ['','parseJumpTo'], #JumpTo
        0xF56D: ['','parseSendMessage'], #<SendMessage
        0xF56E: ['','parseCloseWindow'],            #<CloseWindow/>
        0xF5D6: ['','parseSoundStop'],            #<SoundStop/>
        0xF5F9: ['','parseRun'],    #Run
        1: [LRFObject.tagMap]
      }
    def __init__(self, objId):
        self.objId = objId
        self.xml = u''
        self.refImage = {}
        self.actions = {}
        self.toDump = True
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def doRefImage(self, tag, f):
        self.refImage[self.buttonType] = tag.paramDWord()
    def doBaseButton(self, tag, f):
        self.buttonType = 0
        self.actions[self.buttonType] = []
    def doFocusinButton(self, tag, f):
        self.buttonType = 1
    def doPushButton(self, tag, f):
        self.buttonType = 2
    def doUpButton(self, tag, f):
        self.buttonType = 3
    def doStartActions(self, tag, f):
        self.actions[self.buttonType] = []
    def parseJumpTo(self, tag, f):
        self.actions[self.buttonType].append((1, struct.unpack("<II", tag.params)))
    def parseSendMessage(self, tag, f):
        params = (tag.paramWord(), getString(f), getString(f))
        self.actions[self.buttonType].append((2, params))
    def parseCloseWindow(self, tag, f):
        self.actions[self.buttonType].append((3,))
    def parseSoundStop(self, tag, f):
        self.actions[self.buttonType].append((4,))
    def parseRun(self, tag, f):
        self.actions[self.buttonType].append((5, struct.unpack("<HI", tag.params)))
    def doButton(self, name, num):
        res = u'<'+name
        if num in self.refImage:
            ref = self.refImage[num]
            if ref!=0: res+= u' refimage="%d"' % ref
        res += u'>\n'
        for i in self.actions[num]:
            if i[0] == 1:
                res += u'<JumpTo refpage="%d" refobj="%d"/>\n' % i[1]
            elif i[0] == 2:
                msgtypemap = {0:'any', 0x11:'cid', 0x12:'url', 0x13:'path', 0x20: 'exec', 0x30:'close'}
                msgtype, msg, msglabel = msgtypemap[i[1][0]], i[1][1], i[1][2]
                res += u'<SendMessage messagelabel="%s" messagetype="%s">%s</SendMessage>\n' % (msglabel, msgtype, msg)
            elif i[0] == 3:
                res += u'<CloseWindow/>\n' % i[1]
            elif i[0] == 4:
                res += u'<SoundStop/>\n' % i[1]
            elif i[0] == 5:
                runoptionmap = {0: 'normal', 1:'opposite', 0x10:'center', 0x11:'opposite-center'}
                res += u'<Run runoption="%s" refobj="%d"/>\n' % (runoptionmap[i[1][0]], i[1][1])
            else: raise LRFException("bad action")
        res += u'</'+name+'>\n'
        return res
    def addXmlTags(self, objects):
        return u''
    def toXml(self, objects, noblock=False):
        #print "in LRFButton.toXml"
        self.toDump = False
        res = u''
        if noblock:
            res+=u'<Button'
            res += LRFObject.addXmlTags(self,objects)
            res+=u'>\n'
        if self.buttonFlags & 1 != 0:
            res += self.doButton('BaseButton', 0)
        if self.buttonFlags & 4 != 0:
            res += self.doButton('FocusinButton', 1)
        if self.buttonFlags & 0x10 != 0:
            res += self.doButton('PushButton', 2)
        if self.buttonFlags & 0x40 != 0:
            res += self.doButton('UpButton', 3)
        if noblock: res+=u'</Button>\n'
        return res

#08
class LRFWindow(LRFStream):
    tagMap = {
        0xF5DB: ['windowwidth', 'W', "%d"],
        0xF5DC: ['windowheight', 'W', "%d"],
        0xF5DA: ['setwaitprop', 'W', {1: 'replay', 2: 'noreplay'}],
        1: [LRFBlockAtr.tagMap, LRFStream.tagMap]
      }
    xmlMap = {
        0xF5DB: ['windowwidth', 'W', "%d"],
        0xF5DC: ['windowheight', 'W', "%d"],
        0xFF00: ['setwaitprop', 'W', {1: 'replay', 2: 'noreplay'}],
        0xFF01: ['setwaitsync', 'W', {0: 'sync', 0x10: 'async'}]
    }
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def toXml(self, objects):
        self.toDump = False
        res = u'<Window'
        res += doTagMapXml(self, LRFBlockAtr.tagMap, objects)
        res += doTagMapXml(self, self.xmlMap, objects)
        res += LRFObject.addXmlTags(self, objects)
        res += u">\n"
        f = StringIO.StringIO(self.stream)
        l = len(self.stream)
        cont = LRFPageContent(objects)
        while f.tell()<l:
            tag = tags.LRFTag(f)
            # print tag
            if cont.handleTag(tag, f) == False:
                break
        res += cont.toXml(objects)
        res += u'</Window>\n'
        return res

#15
class LRFPopUpWin(LRFObject):
    tagMap = {
        0xF503: ['refBlockId', 'D'],
        0: LRFObject.tagMap
      }
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def toXml(self, objects):
        #print "in LRFSound.toXml"
        self.toDump = False
        res = u'<PopUpWin'
        res += LRFObject.addXmlTags(self, objects)
        res += u'>\n'
        res += objects[self.refBlockId].toXml(objects)
        res += u'</PopUpWin>\n'
        return res
#16
class LRFSound(LRFObject):
    tagMap = {
        0xF557: ['times', 'W', "%d"],
        0xF558: ['playmode', 'W', {0:'sync', 1:'async'}],
        0xF54C: ['refstream', 'D', "%d"],  #stream or import
        0: LRFObject.tagMap
      }
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def toXml(self, objects):
        #print "in LRFSound.toXml"
        self.toDump = False
        res = u'<Sound'
        res += LRFObject.addXmlTags(self, objects)
        res += doTagMapXml(self, self.tagMap, objects)
        res += u'/>\n'
        return res

#17
class LRFSoundStream(LRFStream):
    tagMap = {
        1: [LRFStream.tagMap]
      }
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def toXml(self, objects):
        self.toDump = False
        #print "in LRFSoundStream.toXml"
        sndext = {0x23: 'pcm', 0x21: 'mp3', 0x24:'atrac'}
        ext = sndext[self.streamFlags & 0xFF]
        fname = 'soundstream_%d.%s' % (self.objId, ext)
        file(fname,'wb').write(self.stream)
        res = u'<SoundStream encoding="%s" file="%s"' % (ext.upper(), fname)
        res += LRFObject.addXmlTags(self, objects)
        res += u'/>\n'
        return res

#18
class LRFFont(LRFStream):
    tagMap = {
        0xF559: ['fontFilename', 'P'],
        0xF55D: ['fontFacename', 'P'],
        1: [LRFStream.tagMap]
      }
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def toXml(self, objects):
        self.toDump = False
        return u'<RegistFont fontname="%s" file="%s" encoding="TTF" fontfilename="%s"/>\n'%(self.fontFacename, self.fontFilename, self.fontFilename)

#1A
class LRFObjectInfo(LRFStream):
    tagMap = {
        1: [LRFStream.tagMap]
      }
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def toXml(self, objects):
        self.toDump = False
        return u''

#1D
class LRFSimpleText(LRFText):
    pass
    """tagMap = {
        0: LRFText.tagMap
      }
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)"""

def bindingToString(binding):
    if binding==1:
        return "Lr"
    elif binding==16:
        return "Rl"
    else: return "bad binding(%d)" % binding

#1C
class LRFBookAtr(LRFObject):
    tagMap = {
        0xF57B: ['pageTreeId', 'D', lambda val: ''],
        0xF5D8: ['', 'addRFont', nullfunc],
        0xF5DA: ['setwaitprop', 'W', {1: 'replay', 2: 'noreplay'}],
        1: [rubyTags, LRFObject.tagMap]
      }
    def __init__(self, objId):
        self.FontLinkList = []
        LRFObject.__init__(self, objId)
    def handleTag(self, tag, f):
        return doTagMap(self, self.tagMap, tag, f)
    def parseEmpDots(self, tag, f):
        self.refEmpDotsFont, self.empDotsFontName, self.empDotsCode = tag.params
    def addRFont(self, tag, f):
        self.FontLinkList.append(tag.paramDWord())
    def toXml(self, objects, lrffile):
        self.toDump = False
        res = u'<BookStyle stylelabel="%d"' % self.objId
        res += LRFObject.addXmlTags(self, objects)
        res += u'>\n<SetDefault'
        #res += addRubyXmlTags(self, objects)
        res += doTagMapXml(self, self.tagMap, objects)
        res += u'/>\n'
        res += '<BookSetting bindingdirection="%s" dpi="%d" screenwidth="%d" screenheight="%d" colordepth="%d"/>\n' \
             % (bindingToString(lrffile.binding), lrffile.dpi, lrffile.width, lrffile.height, lrffile.colorDepth)
        for i in self.FontLinkList:
            res += objects[i].toXml(objects)
        res += u'</BookStyle>\n'
        return res

#1E
class LRFTOCObject(LRFStream):
    def handleTag(self, tag, f):
        return LRFStream.handleTag(self, tag, f)
    def toXml(self, objects):
        self.toDump = False
        res = u'<TOC>\n'
        f = StringIO.StringIO(self.stream)
        l = len(self.stream)
        c = getWord(f)
        f.seek(4*(c+1))
        while c>0:
        #<TocLabel refobj="108" refpage="105">ImageBlock108label</TocLabel>
            refpage = getDWord(f)
            refobj = getDWord(f)
            label = getString(f)
            res += u'<TocLabel refobj="%d" refpage="%d">%s</TocLabel>\n' % (refobj, refpage, label)
            objects[refobj].toclabel = label
            c -= 1
        res += u"</TOC>\n"
        return res

def LRFObjectFactory(f, offset, size, key):
    objMap = [
        None,          #00
        LRFPageTree,   #01
        LRFPage,       #02
        LRFHeader,     #03
        LRFFooter,     #04
        LRFPageAtr,    #05
        LRFBlock,      #06
        LRFBlockAtr,   #07
        LRFMiniPage,   #08
        None,          #09
        LRFText,       #0A
        LRFTextAtr,    #0B
        LRFImage,      #0C
        LRFCanvas,     #0D
        LRFESound,     #0E
        None,          #0F
        None,          #10
        LRFImageStream,#11
        LRFImport,     #12
        LRFButton,     #13
        LRFWindow,     #14
        LRFPopUpWin,   #15
        LRFSound,      #16
        LRFSoundStream,#17
        None,          #18
        LRFFont,       #19
        LRFObjectInfo, #1A
        None,          #1B
        LRFBookAtr,    #1C
        LRFSimpleText, #1D
        LRFTOCObject,  #1E
    ]

    f.seek(offset)
    startTag = tags.LRFTag(f)
    if startTag.tagId!=0xF500: raise LRFException("Bad object start!")
    objId, objType = struct.unpack("<IH",startTag.params)
    if objType<len(objMap) and objMap[objType] is not None:
        obj = objMap[objType](objId)
    else:
        #raise LRFException("Unknown object type: %02X!" % objType)
        print "Unknown object type: %02X!" % objType
    #print "Object type: %02X" % objType
    obj.scrambleKey = key
    while f.tell()<offset+size:
        try:
            tag = tags.LRFTag(f)
            #print tag
        except:
            print "Bad tag at offset %08X"%f.tell()
            raise
        if obj.handleTag(tag, f) == False:
            break
    return obj

    def __str__(self):
        return "Object ID: %04X, Type: %02X" % self.objId, self.objType

class LRFFile:
    def __init__(self, fname):
        self.filename = fname
    def parseHeader(self,f):
        t = f.read(8);
        if t!="L\0R\0F\0\0\0":
            raise LRFException("Bad LRF header");
        self.version = getWord(f);            #4
        self.xorKey = getWord(f);             #0A
        self.rootObjectId = getDWord(f);      #0C
        self.nObjects = getQWord(f);          #10
        self.offObjectTable = getQWord(f);    #18
        f.read(4);                            #20
        self.binding = getByte(f)             #24
        f.read(1);                            #25
        self.dpi = getWord(f);                #26
        f.read(2);                            #28
        self.width  = getWord(f)              #2A
        self.height = getWord(f)              #2C
        self.colorDepth = getByte(f)          #2E
        f.read(1);                            #2F
        f.read(20)                            #30
        self.TocObjId = getDWord(f)           #44
        self.TocObjOffset = getDWord(f)       #48
        self.DocInfoCompSize = getWord(f)     #4C
        if (self.version>800):
            self.thumbType = getWord(f)
            self.thumbSize = getDWord(f)
        if (self.DocInfoCompSize):
            uncompSize = getDWord(f)
            try:
                self.docInfo = zlib.decompress(f.read(self.DocInfoCompSize-4))
            except zlib.error:
                raise LRFException("decompression failed");
            if len(self.docInfo)!=uncompSize:
                raise LRFException("expected %d, got %d decompressed bytes" % (uncompSize, len(self.docInfo)));
        if (self.version>800 and self.thumbSize>0):
            self.thumbname = self.filename[:-4]+"_thumb."+imgext[self.thumbType]
            file(self.thumbname,'wb').write(f.read(self.thumbSize))

    def parseObjects(self,f):
        print "Parsing objects...",
        if (self.offObjectTable):
            f.seek(self.offObjectTable)
            obj_array = array.array("I",f.read(4*4*self.nObjects))
            if ord(array.array("i",[1]).tostring()[0])==0: #big-endian
                obj_array.byteswap()
            self.objects = {}
            for i in range(self.nObjects):
                objid, objoff, objsize = obj_array[i*4:i*4+3]
                obj = LRFObjectFactory(f, objoff, objsize, self.xorKey)
                #print obj
                self.objects[objid] = obj
            print "done."
        else:
            raise LRFExceptions("Call parseHeader() first!")

    def parse(self,f):
        f.seek(0);
        self.parseHeader(f)
        self.parseObjects(f)

    def getDocInfo(self):
        r=unicode(self.docInfo,"utf-16-le")
        r=re.sub(r"<\?xml.*?>","",r)
        r=string.replace(r,"<Page>","<SumPage>")
        r=string.replace(r,"</Page>","</SumPage>")
        if (self.version>800 and self.thumbSize>0):
            r=string.replace(r,"<DocInfo>",'<DocInfo>\n<CThumbnail file="%s"/>' % self.thumbname)
        return r

    def toXml(self):
        xml = u"""<?xml version="1.0" encoding="UTF-16"?>
<BBeBXylog version="1.0">
<Property/>
<BookInformation>"""
        xml += self.getDocInfo()
        #xml += self.objects[self.TocObjId].toXml(self.objects)
        xml += u"</BookInformation>\n"
        rootObj = self.objects[self.rootObjectId] #should be a BookAtr
        pageTree = self.objects[rootObj.pageTreeId]
        xml += pageTree.toXml(self.objects, True)
        xml += u'<Template version="1.0">\n</Template>\n'
        xml += u"<Style>\n"
        xml += rootObj.toXml(self.objects, self)
        for i in self.objects:
            o = self.objects[i]
            if isinstance(o,LRFPageAtr) or isinstance(o,LRFBlockAtr) or isinstance(o,LRFTextAtr):
                xml += o.toXml(self.objects)
            elif isinstance(o,LRFBlock):
                self.objects[o.getLinkedObjectId()].toDump = False
        xml += u"</Style>\n"

        hadSolo = False
        for i in self.objects:
            o = self.objects[i]
            if isinstance(o,LRFPageTree) and o.toDump:
                if not hadSolo:
                    print "Writing solo pages...",
                    hadSolo = True
                    xml += u"<Solo>\n"
                xml += o.toXml(self.objects)

        if hadSolo:
            xml += u"</Solo>"
            print "done."

        xml += u'<Objects>\n'
        print "Writing external streams...",
        for i in self.objects:
            o = self.objects[i]
            if o.toDump == False:
                continue
            if isinstance(o,LRFImage) or isinstance(o,LRFButton):
                #print "object id=%02X" % o.objId
                xml += o.toXml(self.objects, True)
            #if isinstance(o,LRFImageStream) or isinstance(o,LRFSoundStream) or isinstance(o,LRFSound) or isinstance(o,LRFPopUpWin):
            else:
                #print "object id=%02X" % o.objId
                xml += o.toXml(self.objects)
        print "done."
        xml += u'</Objects>\n'
        xml += u"</BBeBXylog>"
        return xml

    def __str__(self):
        s = "Version: %d\nXor key: %02X\nRoot object: %X\nObjects: %d\nObject table offset: %X\n" \
            % (self.version, self.xorKey, self.rootObjectId, self.nObjects, self.offObjectTable)
        s += "Flags: %02X\nSize: %dx%d\nToc object: %X\nToc offset: %X" \
            % (self.flags, self.width, self.height, self.TocObjId, self.TocObjOffset)
        #s += "Objects: \n" + str(self.objects)

def option_parser():
    from optparse import OptionParser
    return OptionParser(usage='%prog file.lrf', version=__appname__+' '+__version__)

def main(args=sys.argv):
    print "lrf2lrs (c) 2006-2007 roxfan, igorsk"
    parser = option_parser() 
    args = parser.parse_args(args)[1]
    if len(args)>1:
        fname = args[1]
        f = file(fname, 'rb')
        h = LRFFile(fname)
        h.parse(f)
        if fname[-4:].lower()==".lrf":
            outfname = fname[:-4]+".lrs"
        else:
            outfname = fname+".lrs"
        out = codecs.open(outfname,"w","utf-16")
        out.write(h.toXml())
        return 0
    else:
        parser.print_help()
        return 1

if __name__=='__main__':
    sys.exit(main())
