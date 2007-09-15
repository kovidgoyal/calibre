##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
import struct, array, zlib

from libprs500.ebooks.lrf import LRFParseError
from libprs500.ebooks.lrf.tags import Tag

class LRFObject(object):
    
    tag_map = {
        0xF500: ['', ''],
        0xF502: ['infoLink', 'D'],
        0xF501: ['', ''],
        
        # Ruby tags
        0xF575: ['rubyAlignAndAdjust', 'W'],
        0xF576: ['rubyoverhang', 'W', {0: 'none', 1:'auto'}],
        0xF577: ['empdotsposition', 'W', {1: 'before', 2:'after'}],
        0xF578: ['','parse_empdots'],
        0xF579: ['emplineposition', 'W', {1: 'before', 2:'after'}],
        0xF57A: ['emplinetype', 'W', {0: 'none', 0x10: 'solid', 0x20: 'dashed', 0x30: 'double', 0x40: 'dotted'}]

    }
    
    @classmethod
    def descramble_buffer(cls, buf, l, xorKey):
        i = 0
        a = array.array('B',buf)
        while l>0:
            a[i] ^= xorKey
            i+=1
            l-=1
        return a.tostring()

    @classmethod
    def parse_empdots(self, tag, f):
        self.refEmpDotsFont, self.empDotsFontName, self.empDotsCode = tag.contents
    
    def __init__(self, stream, id, scramble_key, boundary):
        self._scramble_key = scramble_key
        
        while stream.tell() < boundary:
            tag = Tag(stream)
            self.handle_tag(tag, stream)
            
    def parse_bg_image(self, tag, f):
        self.bg_image_mode, self.bg_image_id = struct.unpack("<HI", tag.contents)
    
    def handle_tag(self, tag, stream, tag_map=None):
        if tag_map is None:
            tag_map = self.__class__.tag_map
        if tag.id in tag_map:
            h = tag_map[tag.id]
            if h[1] == 'D':
                val = tag.dword
            elif h[1] == 'W':
                val = tag.word
            elif h[1] == 'w':
                val = tag.word
                if val > 0x8000: 
                    val -= 0x10000
            elif h[1] == 'B':
                val = tag.paramByte()
            elif h[1] == 'P':
                val = tag.contents
            elif h[1] != '':
                val = getattr(self, h[1])(tag, stream)
    
            if h[1] != '' and h[0] != '':
                if len(h) > 2:
                    val = h[2][val]
                setattr(self, h[0], val)
        else:    
            raise LRFParseError("Unknown tag in %s: %s" % (self.__class__.__name__, str(tag)))
        
class LRFStream(LRFObject):
    tag_map = {
        0xF504: ['', 'read_stream_size'],
        0xF554: ['stream_flags', 'W'],
        0xF505: ['', 'read_stream'],
        0xF506: ['', 'end_stream'],
      }
    tag_map.update(LRFObject.tag_map)
    
    def __init__(self, stream, id, scramble_key, boundary):
        self.stream = ''
        self.stream_size = 0
        self.stream_read = False
        LRFObject.__init__(self, stream, id, scramble_key, boundary)
        
    def read_stream_size(self, tag, stream):
        self.stream_size = tag.dword
        
    def end_stream(self, tag, stream):
        self.stream_read = True
    
    def read_stream(self, tag, stream):
        if self.stream_read:
            raise LRFParseError('There can be only one stream per object')
        if not hasattr(self, 'stream_flags'):
            raise LRFParseError('Stream flags not initialized')
        self.stream = stream.read(self.stream_size)
        if self.stream_flags & 0x200 !=0:
            l = len(self.stream);
            key = l % self._scramble_key + 0xF;
            if l > 0x400 and (isinstance(self, ImageStream) or isinstance(self, Font) or isinstance(self, SoundStream)):
                l = 0x400;
            self.stream = self.descramble_buffer(self.stream, l, key)
        if self.stream_flags & 0x100 !=0:
            decomp_size = struct.unpack("<I", self.stream[:4])[0]
            self.stream = zlib.decompress(self.stream[4:])
            if len(self.stream) != decomp_size:
                raise LRFParseError("Stream decompressed size is wrong!")
        if stream.read(2) != '\x06\xF5':
            print "Warning: corrupted end-of-stream tag at %08X; skipping it"%stream.tell()-2
        self.end_stream(None, None)


class PageTree(LRFObject):
    tag_map = {
        0xF55C: ['pageList', 'P'],
      }
    tag_map.update(LRFObject.tag_map)
    

class PageAttr(LRFObject):
    tag_map = {
        0xF507: ['oddheaderid', 'D'],
        0xF508: ['evenheaderid', 'D'],
        0xF509: ['oddfooterid', 'D'],
        0xF50A: ['evenfooterid', 'D'],
        0xF521: ['topmargin', 'W'],
        0xF522: ['headheight', 'W'],
        0xF523: ['headsep', 'W'],
        0xF524: ['oddsidemargin', 'W'],
        0xF52C: ['evensidemargin', 'W'],
        0xF525: ['textheight', 'W'],
        0xF526: ['textwidth', 'W'],
        0xF527: ['footspace', 'W'],
        0xF528: ['footheight', 'W'],
        0xF535: ['layout', 'W', {0x41: 'TbRl', 0x34: 'LrTb'}],
        0xF52B: ['pageposition', 'W', {0: 'any', 1:'upper', 2: 'lower'}],
        0xF52A: ['setemptyview', 'W', {1: 'show', 0: 'empty'}],
        0xF5DA: ['setwaitprop', 'W', {1: 'replay', 2: 'noreplay'}],
        0xF529: ['', "parse_bg_image"],
      }
    tag_map.update(LRFObject.tag_map)


class Page(LRFStream):
    tag_map = {
        0xF503: ['pageStyle', 'D'],
        0xF50B: ['contents', 'P'],
        0xF571: ['', ''],
        0xF57C: ['parentPageTree','D'],
      }
    tag_map.update(PageAttr.tag_map)
    tag_map.update(LRFStream.tag_map)
    

class BlockAttr(LRFObject):
    tag_map = {
        0xF531: ['blockwidth', 'W'],
        0xF532: ['blockheight', 'W'],
        0xF533: ['blockrule', 'W', {0x14: "horz-fixed", 0x12: "horz-adjustable", 0x41: "vert-fixed", 0x21: "vert-adjustable", 0x44: "block-fixed", 0x22: "block-adjustable"}],
        0xF534: ['bgcolor', 'D'],
        0xF535: ['layout', 'W', {0x41: 'TbRl', 0x34: 'LrTb'}],
        0xF536: ['framewidth', 'W'],
        0xF537: ['framecolor', 'D'],
        0xF52E: ['framemode', 'W', {0: 'none', 2: 'curve', 1:'square'}],
        0xF538: ['topskip', 'W'],
        0xF539: ['sidemargin', 'W'],
        0xF53A: ['footskip', 'W'],
        0xF529: ['', 'parse_bg_image'],
      }
    tag_map.update(LRFObject.tag_map)

class Block(LRFStream):
    tag_map = {
        0xF503: ['atrId', 'D'],
      }
    tag_map.update(BlockAttr.tag_map)
    tag_map.update(LRFStream.tag_map)

class Header(LRFStream):
    tag_map = {}
    tag_map.update(LRFStream.tag_map)
    tag_map.update(BlockAttr.tag_map)

class Footer(Header):
    pass

class MiniPage(LRFObject):
    pass

class TextAttr(LRFObject):
    tag_map = {
        0xF511: ['fontsize', 'w'],
        0xF512: ['fontwidth', 'w'],
        0xF513: ['fontescapement', 'w'],
        0xF514: ['fontorientation', 'w'],
        0xF515: ['fontweight', 'W'],
        0xF516: ['fontfacename', 'P'],
        0xF517: ['textcolor', 'D'],
        0xF518: ['textbgcolor', 'D'],
        0xF519: ['wordspace', 'w'],
        0xF51A: ['letterspace', 'w'],
        0xF51B: ['baselineskip', 'w'],
        0xF51C: ['linespace', 'w'],
        0xF51D: ['parindent', 'w'],
        0xF51E: ['parskip', 'w'],
        0xF53C: ['align', 'W', {1: 'head', 4: 'center', 8: 'foot'}],
        0xF53D: ['column', 'W'],
        0xF53E: ['columnsep', 'W'],
        0xF5DD: ['charspace', 'w'],
        0xF5F1: ['textlinewidth', 'W'],
        0xF5F2: ['linecolor', 'D'],
      }
    tag_map.update(LRFObject.tag_map)

class Text(LRFStream):
    tag_map = {
        0xF503: ['atrId', 'D'],
      }
    tag_map.update(TextAttr.tag_map)
    tag_map.update(LRFStream.tag_map)


class Image(LRFObject):
    tag_map = {
        0xF54A: ['', 'parse_image_rect'],
        0xF54B: ['', 'parse_image_size'],
        0xF54C: ['ref_object_id', 'D'],      #imagestream or import
        0xF555: ['comment', 'P'],
      }
    
    def parse_image_rect(self, tag, f):
        self.image_rect = struct.unpack("<HHHH", tag.contents)
        
    def parse_image_size(self, tag, f):
        self.image_size = struct.unpack("<HH", tag.contents)

class Canvas(LRFStream):
    tag_map = {
        0xF551: ['canvaswidth', 'W'],
        0xF552: ['canvasheight', 'W'],
        0xF5DA: ['', 'parse_waits'],
      }
    tag_map.update(BlockAttr.tag_map)
    tag_map.update(LRFStream.tag_map)
    
    def parse_waits(self, tag, f):
        val = tag.word
        self.setwaitprop = val&0xF
        self.setwaitsync = val&0xF0

class ESound(LRFObject):
    pass

class ImageStream(LRFStream):
    tag_map = {
        0xF555: ['comment', 'P'],
      }
    tag_map.update(LRFStream.tag_map)

class Import(LRFObject):
    pass

class Button(LRFObject):
    tag_map = {
        0xF503: ['', 'do_ref_image'],
        0xF561: ['button_flags','W'],           #<Button/>
        0xF562: ['','do_base_button'],            #<BaseButton>
        0xF563: ['',''],            #</BaseButton>
        0xF564: ['','do_focusin_button'],            #<FocusinButton>
        0xF565: ['',''],            #</FocusinButton>
        0xF566: ['','do_push_button'],            #<PushButton>
        0xF567: ['',''],            #</PushButton>
        0xF568: ['','do_up_button'],            #<UpButton>
        0xF569: ['',''],            #</UpButton>
        0xF56A: ['','do_start_actions'],            #start actions
        0xF56B: ['',''],            #end actions
        0xF56C: ['','parse_jump_to'], #JumpTo
        0xF56D: ['','parse_send_message'], #<SendMessage
        0xF56E: ['','parse_close_window'],            #<CloseWindow/>
        0xF5D6: ['','parse_sound_stop'],            #<SoundStop/>
        0xF5F9: ['','parse_run'],    #Run
      }
    tag_map.update(LRFObject.tag_map)
    
    def __init__(self, stream, id, scramble_key, boundary):
        self.xml = u''
        self.refimage = {}
        self.actions = {}
        self.to_dump = True
        LRFObject.__init__(self, stream, id, scramble_key, boundary)
    
    def do_ref_image(self, tag, f):
        self.refimage[self.button_yype] = tag.dword
        
    def do_base_button(self, tag, f):
        self.button_type = 0
        self.actions[self.button_type] = []
        
    def do_focus_in_button(self, tag, f):
        self.button_type = 1
        
    def do_push_button(self, tag, f):
        self.button_type = 2
        
    def do_up_button(self, tag, f):
        self.button_type = 3
        
    def do_start_actions(self, tag, f):
        self.actions[self.button_type] = []
        
    def parse_jump_to(self, tag, f):
        self.actions[self.button_type].append((1, struct.unpack("<II", tag.contents)))
    
    def parse_send_message(self, tag, f):
        params = (tag.word, Tag.string_parser(f), Tag.string_parser(f))
        self.actions[self.button_type].append((2, params))
        
    def parse_close_window(self, tag, f):
        self.actions[self.button_type].append((3,))
        
    def parse_sound_stop(self, tag, f):
        self.actions[self.button_type].append((4,))
    
    def parse_run(self, tag, f):
        self.actions[self.button_type].append((5, struct.unpack("<HI", tag.contents)))

class Window(LRFObject):
    pass

class PopUpWin(LRFObject):
    pass

class Sound(LRFObject):
    pass

class SoundStream(LRFObject):
    pass

class Font(LRFStream):
    tag_map = {
        0xF559: ['fontFilename', 'P'],
        0xF55D: ['fontFacename', 'P'],
      }
    tag_map.update(LRFStream.tag_map)

class ObjectInfo(LRFObject):
    pass


class BookAttr(LRFObject):
    tag_map = {
        0xF57B: ['pageTreeId', 'D'],
        0xF5D8: ['', 'add_font'],
        0xF5DA: ['setwaitprop', 'W', {1: 'replay', 2: 'noreplay'}],
      }
    tag_map.update(LRFObject.tag_map)
    
    def __init__(self, stream, id, scramble_key, boundary):
        self.font_link_list = []
        LRFObject.__init__(self, stream, id, scramble_key, boundary)
        
    def add_font(self, tag, f):
        self.font_link_list.append(tag.dword)

class SimpleText(LRFObject):
    pass

class TOCObject(LRFStream):
    pass

object_map = [
    None,       #00
    PageTree,   #01
    Page,       #02
    Header,     #03
    Footer,     #04
    PageAttr,    #05
    Block,      #06
    BlockAttr,   #07
    MiniPage,   #08
    None,       #09
    Text,       #0A
    TextAttr,    #0B
    Image,      #0C
    Canvas,     #0D
    ESound,     #0E
    None,       #0F
    None,       #10
    ImageStream,#11
    Import,     #12
    Button,     #13
    Window,     #14
    PopUpWin,   #15
    Sound,      #16
    SoundStream,#17
    None,       #18
    Font,       #19
    ObjectInfo, #1A
    None,       #1B
    BookAttr,    #1C
    SimpleText, #1D
    TOCObject,  #1E
]


def get_object(stream, id, offset, size, scramble_key):
    stream.seek(offset)
    start_tag = Tag(stream)
    if start_tag.id != 0xF500:
        raise LRFParseError('Bad object start')
    obj_id, obj_type = struct.unpack("<IH", start_tag.contents)
    if obj_type < len(object_map) and object_map[obj_type] is not None:
        return object_map[obj_type](stream, obj_id, scramble_key, offset+size-8)
    
    raise LRFParseError("Unknown object type: %02X!" % obj_type)

        
