##    Copyright (C) 2008 Roger Critchlow <rec@elf.org>
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

#
# major mismatch in Button/ButtonBlock/JumpButton
# major mismatch in providing referenced object instead of object reference
# 

import sys, os
from xml.etree.ElementTree import ElementTree

from libprs500.ebooks.lrf.pylrs.pylrs import \
     Book, StyleDefault, BookSetting, \
     ImageBlock, Header, Footer, PutObj, \
     Paragraph, CR, Italic, Bold, ImageStream, \
     CharButton, Button, PushButton, JumpTo, \
     Plot, Image, RuledLine, Canvas, DropCaps, \
     Sup, Sub, Span, Text, EmpLine, Font, \
     LrsError,  Space, Box, ButtonBlock, NoBR

from libprs500 import __appname__, __version__

class LrsParser(object):
    filterAttrib = ['objid', 'refobj', 'objlabel', 'pagestyle', 'blockstyle', 'textstyle', 'stylelabel',
                    'evenheaderid', 'oddheaderid', 'evenfooterid', 'oddfooterid', 'page_tree_id', 'refstream']
    def __init__(self, file):
        self.file = file
        self.book = Book()
        self.objects = dict()
        self.dobjects = dict()
        self.tocs = list()
        self.charbuttons = list()
        self.jumptos = list()
        self.pagestyles = list()
        self.blockstyles = list()
        self.textstyles = list()
        self.footers = list()
        self.headers = list()
        self.putobjs = list()
        self.plots = list()
        self.images = list()
        self.imageblocks = list()
        self.root = ElementTree(file=file)

    #
    # find an element by objid
    #
    def get_element_by_objid(self, objid):
        if objid not in self.objects:
            for element in self.root.getiterator():
                if 'objid' in element.attrib:
                    id = element.attrib['objid']
                    if id not in self.objects:
                        self.objects[id] = element
                    elif self.equal_element(self.objects[id], element):
                        continue
                    elif self.objects[id] != element:
                        raise LrsError, "multiple objects with same objid=%s, %s and %s"%(id, element.tag, self.objects[id].tag)
        if objid in self.objects:
            return self.objects[objid]
        return None
    
    #
    # put the tag and attributes into one string
    #
    def element_dump(self, element):
        str = ""
        str += "<%s"%element.tag
        keys = element.attrib.keys()
        keys.sort()
        for key in keys:
            str += " %s=\"%s\""%(key,element.attrib[key])
        # should do something about sub elements and sub text
        str += "/>"
        return str
    
    #
    # compare two elements for identical tags and attributes
    #
    def equal_element(self, e1, e2):
        return e1.tag == e2.tag and self._equal_attrib(e1, e2, ignore=[])

    #
    # compare two element attrib dictionaries for equivalence
    # ignoring some attributes
    #
    def equal_attrib(self, e1, e2):
        return self._equal_attrib(e1, e2, ignore=LrsParser.filterAttrib)

    def _equal_attrib(self, e1, e2, ignore):
        #print "comparing %s to %s in equal_attrib"%(e1.tag,e2.tag)
        a1 = e1.attrib
        a2 = e2.attrib
        for name in a1.keys():
            if name in ignore:
                continue
            if name not in a2:
                #print "compare: %s in e1 not in e2"%name
                return False
            if a1[name] != a2[name]:
                #print "compare: %s e1=%s != e2=%s"%(name, a1[name], a2[name])
                return False
        for name in a2.keys():
            if name in ignore:
                continue
            if name not in a1:
                #print "compare: %s in e1 not in e2"%name
                return False
            if a1[name] != a2[name]:
                #print "compare: %s e1=%s != e2=%s"%(name, a1[name], a2[name])
                return False
        return True

    #
    # process an attrib dictionary for passing into a pylrs create
    #
    def process_attrib(self, element):
        attrib = element.attrib.copy()
        for name in LrsParser.filterAttrib:
            if name in attrib:
                id = attrib[name]
                if name == 'objid':
                    if id not in self.objects:
                        self.objects[id] = element
                    elif self.objects[id] != element and not self.equal_element(self.objects[id], element):
                        raise LrsError, "multiple objects with same objid=%s, %s and %s"%(id, element.tag, self.objects[id].tag)
                del attrib[name]
        return attrib

    #
    # get and parse a style element
    #
    def fetch_style(self, element, stylename):
        """get the style element referenced by stylename in element.attrib"""

        if stylename not in element.attrib:
            return None
        id = element.attrib[stylename]
        if id in self.dobjects:
            return self.dobjects[id]
        style = self.get_element_by_objid(id)
        if style == None:
            raise LrsError, "no %s style element found for objid=%s"%(stylename, id)
        #print "found style type %s with objid = %s after getting %s"%(style.tag, style.attrib['objid'], id)
        newstyle = None
        #
        # yuck - headers and footers really mess this up
        # until then, there were no objid pointers in any
        # style object.
        # hmm, so maybe we push them always into the page
        if stylename == 'pagestyle':
            for e in self.pagestyles:
                if self.equal_attrib(e, style):
                    #print "making pagestyle %s alias to %s"%(id, e.attrib['objid'])
                    newstyle = self.dobjects[e.attrib['objid']]
                    break
            if newstyle == None:
                #print "making pagestyle %s"%id
                self.pagestyles.append(style)
                attrib = self.process_attrib(style)
                for name in ['evenfooter', 'evenheader', 'footer', 'header', 'oddfooter', 'oddheader' ]:
                    if name+'id' in style.attrib:
                        attrib[name] = self.fetch_header_footer(style, name+'id')
                newstyle = self.book.create_page_style(**attrib)
        elif stylename == 'blockstyle':
            for e in self.blockstyles:
                if self.equal_attrib(e, style):
                    #print "making blockstyle %s alias to %s"%(id, e.attrib['objid'])
                    newstyle = self.dobjects[e.attrib['objid']]
                    break
            if newstyle == None:
                #print "making blockstyle %s"%id
                self.blockstyles.append(style)
                newstyle = self.book.create_block_style(**self.process_attrib(style))
        elif stylename == 'textstyle':
            for e in self.textstyles:
                if self.equal_attrib(e, style):
                    #print "making textstyle %s alias to %s"%(id, e.attrib['objid'])
                    newstyle = self.dobjects[e.attrib['objid']]
                    break
            if newstyle == None:
                #print "making textstyle %s"%id
                self.textstyles.append(style)
                #if 'textlinewidth' in style.attrib:
                #    print "creating new TextStyle with textlinewidth='%s'"%style.attrib['textlinewidth']
                newstyle = self.book.create_text_style(**self.process_attrib(style))
        else:
            raise LrsError, "no handler for %s style name"
        self.dobjects[id] = newstyle
        return newstyle
        
    #
    # get and parse a header or footer element
    #
    def fetch_header_footer(self, element, hfname):
        """get the header/footer element referenced by hfname in element.attrib"""

        if hfname not in element.attrib:
            return None
        id = element.attrib[hfname]
        if id in self.dobjects:
            return self.dobjects[id]
        hf = self.get_element_by_objid(id)
        if hf == None:
            raise LrsError, "no %s element found for objid=%s"%(hfname, id)
        #print "found header/footer type %s with objid = %s after getting %s"%(hf.tag, hf.attrib['objid'], id)
        newhf = None
        if hfname == 'evenheaderid' or hfname == 'oddheaderid':
            for e in self.headers:
                if self.equal_header_footer(e, hf):
                    #print "making header/footer %s alias to %s"%(id, e.attrib['objid'])
                    newhf = self.dobjects[e.attrib['objid']]
                    break
            if newhf == None:
                #print "making header %s"%id
                self.headers.append(hf)
                newhf = self.process_Header(hf)
        elif hfname == 'evenfooterid' or hfname == 'oddfooterid':
            for e in self.footers:
                if self.equal_header_footer(e, hf):
                    #print "making footer %s alias to %s"%(id, e.attrib['objid'])
                    newhf = self.dobjects[e.attrib['objid']]
                    break
            if newhf == None:
                #print "making footer %s"%id
                self.footers.append(hf)
                newhf = self.process_Footer(hf)
        else:
            raise LrsError, "no handler for %s header/footer name"
        self.dobjects[id] = newhf
        return newhf
        
    #
    # these mostly ignore the terminal elements, should be errors in the end
    #
    def process_leaf(self, element):
        raise LrsError, "process leaf element %s???"%element.tag

    def process_empty(self, element):
        if element.text or element.getchildren():
            raise LrsError, "element %s is not empty???"%element.tag

    #
    # elements referenced by sets of text elements
    #
    # def process_Rubi(rubi):
    #    """Process <Rubi> element"""
    #    for element in rubi:
    #        if element.tag == "Oyamoji":
    #            process_simple_char0(element)
    #        elif element.tag == "Rubimoji":
    #            process_simple_char0(element)
    #        else:
    #            print "No <Rubi> processor for ", element.tag
    #            
    # def process_AltString(altString):
    #    """Process <AltString> element"""
    #    for element in altString:
    #        if element.tag == "Org":
    #            process_text(element)
    #        elif element.tag == "Alt":
    #            process_text(element)
    #        else:
    #            print "No <AltString> processor for ", element.tag

    #
    # sets of text elements
    #
    def process_text(self, text, obj):
        """process an element as text"""
    
        if text.text != None:
            obj.append(Text(text.text))

        for element in text:
            print "No text processor for %s", self.element_dump(element)
            if element.tail != None:
                obj.append(Text(element.tail))

        return obj
    
    #
    # <Plot> occurs in draw_char, simple_char2, ...
    #
    def process_Plot(self, plot):
        self.plots.append(plot)
        plot.lrsplot = Plot(None, **self.process_attrib(plot))
        return plot.lrsplot

    def process_draw_char(self, draw_char, obj):
        """Process an element in the DrawChar set"""

        if draw_char.text != None:
            obj.append(Text(draw_char.text))

        for element in draw_char:
            if element.tag == "Span":
                span = self.process_draw_char(element, Span(**self.process_attrib(element)))
                if not span.isEmpty():
                    obj.append(span)
            elif element.tag == "Plot":
                obj.append(self.process_text(element, self.process_Plot(element)))
            elif element.tag == "CR":
                obj.append(CR())
            elif element.tag == "Space":
                obj.append(Space(**self.process_attrib(element)))
            elif element.tag == "CharButton":
                self.charbuttons.append(element)
                element.lrscharbutton = CharButton(None, **self.process_attrib(element))
                obj.append(self.process_simple_char1(element, element.lrscharbutton))
            elif element.tag == "Sup":
                obj.append(self.process_simple_char0(element, Sup()))
            elif element.tag == "Sub":
                obj.append(self.process_simple_char0(element, Sub()))
            elif element.tag == "NoBR":
                obj.append(self.process_simple_char1(element, NoBR()))
            elif element.tag == "DrawChar":
                obj.append(self.process_simple_char0(element, DropCaps(**self.process_attrib(element))))
            elif element.tag == "Box":
                obj.append(self.process_simple_char0(element, Box(**self.process_attrib(element))))
            elif element.tag == "Italic":
                obj.append(self.process_draw_char(element, Italic()))
            elif element.tag == "Bold":
                obj.append(self.process_draw_char(element, Bold()))
            # elif element.tag == "Fill":
            #    obj.append(Fill(**self.process_attrib(element)))
            # elif element.tag == "Rubi":
            #    obj.append(self.process_Rubi(element))
            # elif element.tag == "Yoko":
            #    obj.append(self.process_simple_char0(element, Yoko(**self.process_attrib(element))))
            # elif element.tag == "Tate":
            #    obj.append(self.process_simple_char2(element, Tate(**self.process_attrib(element))))
            # elif element.tag == "Nekase":
            #    obj.append(self.process_simple_char2(element, Nekase(**self.process_attrib(element))))
            elif element.tag == "EmpLine":
                obj.append(self.process_simple_char0(element, EmpLine(**self.process_attrib(element))))
            # elif element.tag == "EmpDots":
            #    obj.append(self.process_simple_char0(element, EmpDots(**self.process_attrib(element))))
            # elif element.tag == "Gaiji":
            #    obj.append(self.process_text(element, Gaiji(**self.process_attrib(element))))
            # elif element.tag == "AltString":
            #    obj.append(self.process_AltString(element))
            else:
                print "No DrawChar set processor for ", element.tag
            if element.tail != None:
                obj.append(Text(element.tail))

        return obj

    def process_simple_char0(self, simple_char0, obj):
        """Process an element in the SimpleChar0 set"""

        if simple_char0.text != None:
            obj.append(Text(simple_char0.text))
        for element in simple_char0:
            if element.tag == "Plot":
                obj.append(self.process_text(element, self.process_Plot(element)))
            # elif element.tag == "Gaiji":
            #    obj.append(process_text(element, Gaiji(**self.process_attrib(element))))
            # elif element.tag == "AltString":
            #    obj.append(process_AltString(element))
            else:
                print "No SimpleChar0 set processor for ", element.tag
            if element.tail != None:
                obj.append(Text(element.tail))

        return obj

    
    def process_simple_char1(self, simple_char1, obj):
        """Process an element in the SimpleChar1 set"""
        if simple_char1.text != None:
            obj.append(Text(simple_char1.text))

        for element in simple_char1:
            if element.tag == "Box":
                obj.append(self.process_simple_char0(element), Box(**self.process_attrib(element)))
            elif element.tag == "Sub":
                obj.append(self.process_simple_char0(element, Sub(**self.process_attrib(element))))
            elif element.tag == "Sup":
                obj.append(self.process_simple_char0(element, Sup(**self.process_attrib(element))))
            elif element.tag == "Space":
                obj.append(Space(**self.process_attrib(element)))
            #    elif element.tag == "Rubi":
            #        obj.append(process_Rubi(element))
            #    elif element.tag == "Gaiji":
            #        obj.append(process_text(element, Gaiji(**self.process_attrib(element))))
            #    elif element.tag == "EmpDots":
            #        obj.append(process_simple_char0(element, EmpDots(**self.process_attrib(element))))
            #    elif element.tag == "EmpLine":
            #        obj.append(process_simple_char0(element, EmpLine(**self.process_attrib(element))))
            #    elif element.tag == "AltString":
            #        obj.append(process_AltString(element))
            else:
                print "No SimpleChar1 set processor for ", element.tag
            if element.tail != None:
                obj.append(Text(element.tail))

        return obj

    def process_simple_char2(self, simple_char2, obj):
        """Process an element in the SimpleChar2 set"""

        if simple_char2.text != None:
            obj.append(Text(simple_char2.text))

        for element in simple_char2:
            if element.tag == "Plot":
                obj.append(self.process_text(element, self.process_Plot(element)))
            # elif element.tag == "Gaiji":
            #    obj.append(process_text(element, Gaiji(**self.process_attrib(element))))
            # elif element.tag == "AltString":
            #    obj.append(process_AltString(element))
            else:
                print "No SimpleChar2 set processor for ", element.tag
            if element.tail != None:
                obj.append(Text(element.tail))

        return obj

    #
    # <PutObj> occurs in <Canvas>, <Header>, <Footer>
    #
    def process_PutObj(self, putobj):
        self.putobjs.append(putobj)
        putobj.lrsputobj = PutObj(None, **self.process_attrib(putobj))
        return putobj.lrsputobj

    #
    # <Canvas> occurs in <Page>, <Objects>, <Window>
    #
    def process_Canvas(self, canvas):
        """Process the <Canvas> element"""

        width = canvas.attrib['canvaswidth']
        height = canvas.attrib['canvasheight']
        del canvas.attrib['canvaswidth']
        del canvas.attrib['canvasheight']
        dcanvas = Canvas(width=width, height=height, **self.process_attrib(canvas))
        
        # text permitted?
        for element in canvas:
            if element.tag == "PutObj":
                dcanvas.append(self.process_PutObj(element))
            # elif element.tag == "MoveTo":
            #     dcanvas.append(MoveTo(**self.process_attrib(element)))
            # elif element.tag == "LineTo":
            #     dcanvas.append(LineTo(**self.process_attrib(element)))
            # elif element.tag == "DrawBox":
            #     dcanvas.append(DrawBox(**self.process_attrib(element)))
            # elif element.tag == "DrawEllipse":
            #     dcanvas.append(DrawEllipse(**self.process_attrib(element)))
            else:
                print "No <Canvas> processor for ", element.tag
            # tail text permitted?
        return dcanvas


    #
    # <TextBlock> occurs in <Page>, <Objects>, <Window>, <PopUpWin>
    #
    def process_TextBlock(self, textBlock):
        """Process the <TextBlock> element"""

        self.dobjects[textBlock.attrib['objid']] = \
            dtextblock = self.book.create_text_block(textStyle=self.fetch_style(textBlock, 'textstyle'),
                                            blockStyle=self.fetch_style(textBlock, 'blockstyle'),
                                            **self.process_attrib(textBlock))
        # text permitted?
        for element in textBlock:
            if element.tag == "P":
                dtextblock.append(self.process_draw_char(element, Paragraph()))
            elif element.tag == "CR":
                dtextblock.append(CR())
            else:
                print "No <TextBlock> processor for ", element.tag
            # tail text permitted?
        return dtextblock
        
    #
    # helper for buttons
    #
    def process_some_Button(self, button, dbutton, name):

        # text permitted?
        for element in button:
            if element.tag == "JumpTo":
                refobj = element.attrib['refobj']
                if refobj in self.dobjects:
                    dbutton.append(JumpTo(self.dobjects[refobj]))
                else:
                    self.jumptos.append(element)
                    element.lrsjumpto = JumpTo(None)
                    dbutton.append(element.lrsjumpto)
            #elif element.tag == "Run":
            #    dbutton.append(Run(**self.process_attrib(element)))
            #elif element.tag == "SoundStop":
            #    dbutton.append(SoundStop(**self.process_attrib(element)))
            #elif element.tag == "CloseWindow":
            #    dbutton.append(CloseWindow(**self.process_attrib(element)))
            else:
                print "No ", name, " processor for ", element.tag
            # tail text permitted?
        return dbutton
                
    #
    # <PushButton> occurs in <ButtonBlock>, <Button>
    #
    def process_PushButton(self, button):
        """Process the <PushButton> element"""
        return self.process_some_Button(button, PushButton(**button.attrib), "<PushButton>")
    

    #
    # <FocusinButton> occurs in <ButtonBlock>, <Button>
    #
    def process_FocusinButton(self, button):
        """Process the <FocusinButton> element"""
        return self.process_some_Button(button, FocusinButton(**button.attrib), "<FocusinButton>")

    #
    # <UpButton> occurs in <ButtonBlock>, <Button>
    #
    def process_UpButton(self, button):
        """Process the <FocusinButton> element"""
        return self.process_some_Button(button, UpButton(**button.attrib), "<UpButton>")
    
    #
    # <ButtonBlock> occurs in <Page>, <Objects>, <Window>
    #
    def process_ButtonBlock(self, buttonBlock):
        """Process the <ButtonBlock> element"""
    
        dbuttonblock = ButtonBlock()
        # text permitted?
        for element in buttonBlock:
            if element.tag == "BaseButton":
                dbuttonblock.append(BaseButton(**self.process_attrib(element)))
            elif element.tag == "FocusinButton":
                dbuttonblock.append(self.process_FocusinButton(element))
            elif element.tag == "PushButton":
                dbuttonblock.append(self.process_PushButton(element))
            elif element.tag == "UpButton":
                dbuttonblock.append(self.process_UpButton(element))
            else:
                print "No <%s> processor for <%s>"%(buttonBlock.tag,element.tag)
            # tail text permitted?
        return dbuttonblock

    #
    # <ImageBlock> occurs in ...
    #
    def process_ImageBlock(self, imageblock):
        self.imageblocks.append(imageblock)
        imageblock.lrsimageblock = ImageBlock(None, **self.process_attrib(imageblock))
        self.dobjects[imageblock.attrib['objid']] = imageblock.lrsimageblock
        return self.process_text(imageblock, imageblock.lrsimageblock)
        
    #
    # <Image> occurs in ...
    def process_Image(self, image):
        self.images.append(image)
        image.lrsimage = Image(None, **self.process_attrib(image))
        self.dobjects[image.attrib['objid']] = image.lrsimage
        return self.process_text(image, image.lrsimage)

    #
    # <Button> occurs at toplevel, also <Page>, <Objects>, <Window>
    #
    def process_Button(self, button):
        """Process the <Button> element"""
    
        self.dobjects[button.attrib['objid']] = \
            dbutton = Button(**self.process_attrib(button))
        # text permitted?
        for element in button:
            if element.tag == "BaseButton":
                dbutton.append(BaseButton(**self.process_attrib(element)))
            elif element.tag == "FocusinButton":
                dbutton.append(self.process_FocusinButton(element))
            elif element.tag == "PushButton":
                dbutton.append(self.process_PushButton(element))
            elif element.tag == "UpButton":
                dbutton.append(self.process_UpButton(element))
            else:
                print "No <Button> processor for <%s>"%element.tag
            # tail text permitted?
        return dbutton

    #
    # <Page> occurs in <Main>, <PageTree>#
    #
    def process_Page(self, page):
        """Process the <Page> element"""
    
        attrib = self.process_attrib(page)
        for name in ['evenfooter', 'evenheader', 'footer', 'header', 'oddfooter', 'oddheader' ]:
            if name+'id' in page.attrib:
                attrib[name] = self.fetch_header_footer(page, name+'id')
        self.dobjects[page.attrib['objid']] = \
            dpage = self.book.create_page(pageStyle=self.fetch_style(page, 'pagestyle'), **attrib)
        # text permitted?
        for element in page:
            if element.tag == "TextBlock":
                dpage.append(self.process_TextBlock(element))
            elif element.tag == "ImageBlock":
                dpage.append(self.process_ImageBlock(element))
            elif element.tag == "ButtonBlock":
                dpage.append(self.process_ButtonBlock(element))
            elif element.tag == "Button":
                dpage.append(self.process_Button(element))
            elif element.tag == "BlockSpace":
                dpage.BlockSpace(**self.process_attrib(element))
            elif element.tag == "Canvas":
                dpage.append(self.process_Canvas(element))
            elif element.tag == "RuledLine":
                dpage.append(RuledLine(**self.process_attrib(element)))
            #elif element.tag == "Wait":
            #    dpage.append(Wait(**self.process_attrib(element)))
            else:
                print "No <Page> processor for ", element.tag
            # tail text permitted?
        return dpage

    # <Header> occurs in <Objects>
    def process_Header(self,header):
        """Process <Header> element"""
        
        dheader = Header(**self.process_attrib(header))
        
        for element in header:
            if element.tag == "PutObj":
                dheader.append(self.process_PutObj(element))
            # elif element.tag == "MoveTo":
            #     dheader.append(MoveTo(**self.process_attrib(element)))
            # elif element.tag == "LineTo":
            #     dheader.append(LineTo(**self.process_attrib(element)))
            # elif element.tag == "DrawBox":
            #     dheader.append(DrawBox(**self.process_attrib(element)))
            # elif element.tag == "DrawEllipse":
            #     dheader.append(DrawEllipse(**self.process_attrib(element)))
            else:
                print "No <Header> processor for ", element.tag

        return dheader

    # <Footer> occurs in <Objects>
    def process_Footer(self, footer):
        """Process <Foother> element"""

        dfooter = Footer(**self.process_attrib(footer))
        
        for element in footer:
            if element.tag == "PutObj":
                dfooter.append(self.process_PutObj(element))
            # elif element.tag == "MoveTo":
            #     dheader.append(MoveTo(**self.process_attrib(element)))
            # elif element.tag == "LineTo":
            #     dheader.append(LineTo(**self.process_attrib(element)))
            # elif element.tag == "DrawBox":
            #     dheader.append(DrawBox(**self.process_attrib(element)))
            # elif element.tag == "DrawEllipse":
            #     dheader.append(DrawEllipse(**self.process_attrib(element)))
            else:
                print "No <Footer> processor for ", element.tag

        return dfooter

    #
    # <ImageStream> occurs in <Objects>
    #
    def process_ImageStream(self, imagestream):
        self.dobjects[imagestream.attrib['objid']] = \
            dimagestream = ImageStream(**self.process_attrib(imagestream))
        return self.process_text(imagestream, dimagestream)

    #
    # Toplevel elements.
    #            

    #
    # <BookInformation> occurs at toplevel
    #
    def process_BookInformation(self, bookInformation):
        """Process the <BookInformation> element"""

        dbookinformation = self.book.delegates[0]
        
        def process_Info(info):
            """Process the <Info> element"""

            dinfo = dbookinformation.delegates[0]
        
            def process_BookInfo(bookInfo):
                """Process the <BookInfo> element"""

                dbookinfo = dinfo.delegates[0]

                for element in bookInfo:
                    if element.tag == "Title":
                        dbookinfo.title = (element.text, element.get("reading"))
                    elif element.tag == "Author":
                        dbookinfo.author = (element.text, element.get("reading"))
                    elif element.tag == "BookID":
                        dbookinfo.bookid = element.text
                    elif element.tag == "Publisher":
                        dbookinfo.publisher = element.text
                    elif element.tag == "Label":
                        dbookinfo.label = element.text
                    elif element.tag == "Category":
                        dbookinfo.category = element.text
                    elif element.tag == "Classification":
                        dbookinfo.classification = element.text
                    elif element.tag == "FreeText":
                        dbookinfo.freetext = element.text
                    else:  
                        print "No <BookInfo> processor for ", element.tag

            def process_DocInfo(docInfo):
                """Process the <DocInfo> element"""
            
                ddocinfo = dinfo.delegates[1]
            
                for element in docInfo:
                    if element.tag == "Language":
                        ddocinfo.language = element.text
                    elif element.tag == "Creator":
                        ddocinfo.creator = element.text
                    elif element.tag == "CreationDate":
                        ddocinfo.creationdate = element.text
                    elif element.tag == "Producer":
                        ddocinfo.producer = element.text
                    elif element.tag == "SumPage":
                        ddocinfo.numberofpages = element.text
                    elif element.tag == "CThumbnail":
                        self.book.delegates[0].delegates[0].delegates[1].thumbnail = element.text
                    else:
                        print "No <DocInfo> processor for ", element.tag

            for element in info:
                if element.tag == "BookInfo":
                    process_BookInfo(element)
                elif element.tag == "DocInfo":
                    process_DocInfo(element)
                # elif element.tag == "Keyword":
                #    # <Keyword>* 
                #    process_text(element)
                else:
                    print "No <Info> processor for ", element.tag

        def process_TOC(toc):
            """Process the <TOC> element in <BookInformation>"""
        
            self.tocs.append(toc)
            for element in toc:
                if element.tag != "TocLabel":
                    print "No <TOC> Processor for ", element.tag
            
        for element in bookInformation:
            if element.tag == "Info":
                process_Info(element)
            elif element.tag == "TOC":
                process_TOC(element)
            else:
                print "No <BookInformation> processor for ", element.tag

    #
    # <Main> occurs in toplevel
    #            
    def process_Main(self, main):
        """Process the <Main> element"""
        # merge atrib onto existing Main element
        for element in main:
            if element.tag == "Page":
                self.book.appendPage(self.process_Page(element))
            else:
                print "No <Main> processor for ", element.tag

    #
    # <PageTree> occurs in toplevel
    #
    def process_PageTree(self, pageTree):
        """Process the <PageTree> element"""

        dpagetree = self.book.delegates[4].Solo(**pageTree.attrib)
    
        for element in pageTree:
            if element.tag == "Page":
                dpagetree.appendPage(self.process_Page(element))
            else:
                print "No <PageTree> processor for ", element.tag

    #
    # <Style> occurs in toplevel
    #
    def process_Style(self, style):
        """Process the <Style> element"""

        dstyle = self.book.delegates[3]
    
        def process_BookStyle(bookStyle):
            """Process the <BookStyle> element"""

            dbookstyle = dstyle.delegates[0]

            for element in bookStyle:
                if element.tag == "SetDefault":
                    dbookstyle.styledefault = StyleDefault(**self.process_attrib(element))
                elif element.tag == "BookSetting":
                    dbookstyle.booksetting = BookSetting(**self.process_attrib(element))
                elif element.tag == "RegistFont":
                    dbookstyle.append(Font(**self.process_attrib(element)))
                else:
                    print "No <BookStyle> processor for ", element.tag
                
        for element in style:
            if element.tag == "BookStyle":
                process_BookStyle(element)
            elif element.tag == "PageStyle":
                # ignore - self.book.append(PageStyle(**self.process_attrib(element)))
                None
            elif element.tag == "TextStyle":
                # ignore - self.book.append(TextStyle(**self.process_attrib(element)))
                None
            elif element.tag == "BlockStyle":
                # ignore - self.book.append(BlockStyle(**self.process_attrib(element)))
                None
            else:
                print "No <Style> processor for ", element.tag

    #
    # <Objects> occurs at toplevel
    #
    def process_Objects(self, objects):
        """Process the <Objects> element"""

        dobjects = self.book.delegates[5]

        # <Window> occurs in <Objects>
        # def process_Window(window):
        #     """Process the <Window> element"""
        #
        #     dwindow = Window(**self.process_attrib(window))
        #
        #     for element in window:
        #         if element.tag == "TextBlock":
        #             dwindow.append(self.process_TextBlock(element))
        #         elif element.tag == "ImageBlock":
        #             dwindow.append(self.process_ImageBlock(element)
        #         elif element.tag == "ButtonBlock":
        #             dwindow.append(self.process_ButtonBlock(element))
        #         elif element.tag == "Button":
        #             dwindow.append(self.process_Button(element))
        #         elif element.tag == "Canvas":
        #             dwindow.append(self.process_Canvas(element))
        #         elif element.tag == "RuledLine":
        #             dwindow.append(RuledLine(**self.process_attrib(element)))
        #         elif element.tag == "Wait":
        #             dwindow.append(Wait(**self.process_attrib(element)))
        #         else:
        #             print "No <Window> processor for ", element.tag

        # <PopUpWin> occurs in <Objects>
        # def process_PopUpWin(popUpWin):
        #     """Process <PopUpWin> element"""
        #     dpopupwin = PopUpWin(**self.process_attrib(popUpWin))
        #     for element in popUpWin:
        #         if element.tag == "TextBlock":
        #             dpopupwin.append(process_TextBlock(element))
        #         elif element.tag == "ImageBlock":
        #             dpopup.append(self.process_ImageBlock(element))
        #         else:
        #             print "No <PopUpWin> processor for ", element.tag
        
        # <TOC> doesn't occur in <Objects>, but we try it
        # def process_TOC(toc):
        #     """Process the <TOC> element in <Objects>"""
        #     for element in toc:
        #         if element.tag == "TocLabel":
        #             # problem here, the pylrs TocLabel wants the textBlock
        #             # not the refobj and refpage that are the specified attributes of the TocLabel
        #             process_leaf(element)
        #         else:
        #             print "No <TOC> Processor for ", element.tag
                
        for element in objects:
            if element.tag == "TextBlock":
                dobjects.append(self.process_TextBlock(element))
            elif element.tag == "ImageBlock":
                dobjects.appendImageBlock(self.process_ImageBlock(element))
            elif element.tag == "ButtonBlock":
                dobjects.append(self.process_ButtonBlock(element))
            elif element.tag == "Button":
                dobjects.append(self.process_Button(element))
            elif element.tag == "Canvas":
                dobjects.append(self.process_Canvas(element))
            # elif element.tag == "Window":
            #     dobjects.appendWindow(process_Window(element))
            # elif element.tag == "PopUpWin":
            #     dobjects.appendPopUpWin(process_PopUpWin(element))
            # elif element.tag == "Sound":
            #     dobjects.appendSound(self.process_empty(element))
            # elif element.tag == "SoundStream":
            #     dobjects.appendSoundStream(self.process_empty(element))
            elif element.tag == "ImageStream":
                dobjects.appendImageStream(self.process_ImageStream(element))
            elif element.tag == "Header":
                # processed as part of Page or PageStyle, just skip here
                None    # self.process_Header(element)
            elif element.tag == "Footer":
                # processed as part of Page or PageStyle
                None    # self.process_Footer(element)
            # elif element.tag == "eSound":
            #     dobjects.appendeSound(process_empty(element))
            elif element.tag == "Image":
                dobjects.appendImage(self.process_Image(element))
            # elif element.tag == "TOC":
            #     dobjects.appendTOC(process_TOC(element))
            else:
                print "No <Objects> processor for ", element.tag

    #
    #
    #
    def process_file(self):
        # Iterate
        for element in self.root.getroot():
            # switch on element.tag
            if element.tag == "Property":
                self.process_empty(element)
            elif element.tag == "BookInformation":
                self.process_BookInformation(element)
            elif element.tag == "Main":
                self.process_Main(element)
            elif element.tag == "PageTree":
                self.process_PageTree(element)
            elif element.tag == "Template":
                self.process_empty(element)
            elif element.tag == "Style":
                self.process_Style(element)
            elif element.tag == "Objects":
                self.process_Objects(element)
            else:
                print "\tNo toplevel processor for ", element.tag
        # Post processing
        for toc in self.tocs:
            for tocLabel in toc:
                refobj = tocLabel.attrib['refobj']
                if refobj not in self.dobjects:
                    raise LrsError, "TocLabel reference to %s did not resolve"%refobj
                else:
                    self.book.addTocEntry(tocLabel.text, self.dobjects[refobj])
        for cb in self.charbuttons:
            refobj = cb.attrib['refobj']
            if refobj not in self.dobjects:
                raise LrsError, "CharButton reference to %s did not resolve"%refobj
            else:
                cb.lrscharbutton.setButton(self.dobjects[refobj])
        for jt in self.jumptos:
            refobj = jt.attrib['refobj']
            if refobj not in self.dobjects:
                raise LrsError, "JumpTo reference to %s did not resolve"%refobj
            else:
                jt.lrsjumpto.setTextBlock(self.dobjects[refobj])
        for po in self.putobjs:
            refobj = po.attrib['refobj']
            if refobj not in self.dobjects:
                raise LrsError, "PutObj reference to %s did not resolve"%refobj
            else:
                po.lrsputobj.setContent(self.dobjects[refobj])
        for pl in self.plots:
            refobj = pl.attrib['refobj']
            if refobj not in self.dobjects:
                raise LrsError, "Plot reference to %s did not resolve"%refobj
            else:
                pl.lrsplot.setObj(self.dobjects[refobj])
        for im in self.images:
            refstream = im.attrib['refstream']
            if refstream not in self.dobjects:
                raise LrsError, "Image reference to %s did not resolve"%refstream
            else:
                im.lrsimage.setRefstream(self.dobjects[refstream])
        for ib in self.imageblocks:
            refstream = ib.attrib['refstream']
            if refstream not in self.dobjects:
                raise LrsError, "ImageBlock reference to %s did not resolve"%refstream
            else:
                ib.lrsimageblock.setRefstream(self.dobjects[refstream])
                
    def renderLrf(self, file):
        self.book.renderLrf(file)
    
    def renderLrs(self, file):
        self.book.renderLrs(file)
        
def option_parser():
    from optparse import OptionParser
    parser = OptionParser(usage='%prog [options] file.lrs', 
                          version=__appname__+ ' ' + __version__, 
                          epilog='Created by Roger Critchlow')
    parser.add_option('-o', '--output', default=None, help='Path to output file')
    parser.add_option('--verbose', default=False, action='store_true',
                      help='Verbose processing')
    parser.add_option('--lrs', default=False, action='store_true',
                      help='Convert LRS to LRS, useful for debugging.')
    return parser

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        return 1
    if not opts.output:
        ext = '.lrs' if opts.lrs else '.lrf'
        opts.output = os.path.splitext(os.path.basename(args[1]))[0]+ext
    opts.output = os.path.abspath(opts.output)
    if opts.verbose:
        import warnings
        warnings.defaultaction = 'error'
        
    converter =  LrsParser(args[1])
    converter.process_file()
    if opts.lrs:
        converter.renderLrs(opts.output)
    else:
        converter.renderLrf(opts.output)

    return 0

if __name__ == '__main__':
    sys.exit(main())
