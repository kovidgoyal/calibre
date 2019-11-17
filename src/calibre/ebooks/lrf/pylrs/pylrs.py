

# Copyright (c) 2007 Mike Higgins (Falstaff)
# Modifications from the original:
#    Copyright (C) 2007 Kovid Goyal <kovid@kovidgoyal.net>
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
# Current limitations and bugs:
#   Bug: Does not check if most setting values are valid unless lrf is created.
#
#   Unsupported objects: MiniPage, SimpleTextBlock, Canvas, Window,
#                        PopUpWindow, Sound, Import, SoundStream,
#                        ObjectInfo
#
#   Does not support background images for blocks or pages.
#
#   The only button type supported are JumpButtons.
#
#   None of the Japanese language tags are supported.
#
#   Other unsupported tags: PageDiv, SoundStop, Wait, pos,
#                           Plot, Image (outside of ImageBlock),
#                           EmpLine, EmpDots

import os, re, codecs, operator, io
from xml.sax.saxutils import escape
from datetime import date
from xml.etree.ElementTree import Element, SubElement, ElementTree

from .pylrf import (LrfWriter, LrfObject, LrfTag, LrfToc,
        STREAM_COMPRESSED, LrfTagStream, LrfStreamBase, IMAGE_TYPE_ENCODING,
        BINDING_DIRECTION_ENCODING, LINE_TYPE_ENCODING, LrfFileStream,
        STREAM_FORCE_COMPRESSED)
from calibre.utils.date import isoformat

DEFAULT_SOURCE_ENCODING = "cp1252"      # default is us-windows character set
DEFAULT_GENREADING      = "fs"          # default is yes to both lrf and lrs

from calibre import __appname__, __version__
from calibre import entity_to_unicode
from polyglot.builtins import string_or_bytes, unicode_type, iteritems, native_string_type


class LrsError(Exception):
    pass


class ContentError(Exception):
    pass


def _checkExists(filename):
    if not os.path.exists(filename):
        raise LrsError("file '%s' not found" % filename)


def _formatXml(root):
    """ A helper to make the LRS output look nicer. """
    for elem in root.getiterator():
        if len(elem) > 0 and (not elem.text or not elem.text.strip()):
            elem.text = "\n"
        if not elem.tail or not elem.tail.strip():
            elem.tail = "\n"


def ElementWithText(tag, text, **extra):
    """ A shorthand function to create Elements with text. """
    e = Element(tag, **extra)
    e.text = text
    return e


def ElementWithReading(tag, text, reading=False):
    """ A helper function that creates reading attributes. """

    # note: old lrs2lrf parser only allows reading = ""

    if text is None:
        readingText = ""
    elif isinstance(text, string_or_bytes):
        readingText = text
    else:
        # assumed to be a sequence of (name, sortas)
        readingText = text[1]
        text = text[0]

    if not reading:
        readingText = ""
    return ElementWithText(tag, text, reading=readingText)


def appendTextElements(e, contentsList, se):
    """ A helper function to convert text streams into the proper elements. """

    def uconcat(text, newText, se):
        if isinstance(text, bytes):
            text = text.decode(se)
        if isinstance(newText, bytes):
            newText = newText.decode(se)

        return text + newText

    e.text = ""
    lastElement = None

    for content in contentsList:
        if not isinstance(content, Text):
            newElement = content.toElement(se)
            if newElement is None:
                continue
            lastElement = newElement
            lastElement.tail = ""
            e.append(lastElement)
        else:
            if lastElement is None:
                e.text = uconcat(e.text, content.text, se)
            else:
                lastElement.tail = uconcat(lastElement.tail, content.text, se)


class Delegator(object):
    """ A mixin class to create delegated methods that create elements. """

    def __init__(self, delegates):
        self.delegates = delegates
        self.delegatedMethods = []
        # self.delegatedSettingsDict = {}
        # self.delegatedSettings = []
        for d in delegates:
            d.parent = self
            methods = d.getMethods()
            self.delegatedMethods += methods
            for m in methods:
                setattr(self, m, getattr(d, m))

            """
            for setting in d.getSettings():
                if isinstance(setting, string_or_bytes):
                    setting = (d, setting)
                delegates = \
                        self.delegatedSettingsDict.setdefault(setting[1], [])
                delegates.append(setting[0])
                self.delegatedSettings.append(setting)
            """

    def applySetting(self, name, value, testValid=False):
        applied = False
        if name in self.getSettings():
            setattr(self, name, value)
            applied = True

        for d in self.delegates:
            if hasattr(d, "applySetting"):
                applied = applied or d.applySetting(name, value)
            else:
                if name in d.getSettings():
                    setattr(d, name, value)
                    applied = True

        if testValid and not applied:
            raise LrsError("setting %s not valid" % name)

        return applied

    def applySettings(self, settings, testValid=False):
        for (setting, value) in settings.items():
            self.applySetting(setting, value, testValid)
            """
            if setting not in self.delegatedSettingsDict:
                raise LrsError, "setting %s not valid" % setting
            delegates = self.delegatedSettingsDict[setting]
            for d in delegates:
                setattr(d, setting, value)
            """

    def appendDelegates(self, element, sourceEncoding):
        for d in self.delegates:
            e = d.toElement(sourceEncoding)
            if e is not None:
                if isinstance(e, list):
                    for e1 in e:
                        element.append(e1)
                else:
                    element.append(e)

    def appendReferencedObjects(self, parent):
        for d in self.delegates:
            d.appendReferencedObjects(parent)

    def getMethods(self):
        return self.delegatedMethods

    def getSettings(self):
        return []

    def toLrfDelegates(self, lrfWriter):
        for d in self.delegates:
            d.toLrf(lrfWriter)

    def toLrf(self, lrfWriter):
        self.toLrfDelegates(lrfWriter)


class LrsAttributes(object):
    """ A mixin class to handle default and user supplied attributes. """

    def __init__(self, defaults, alsoAllow=None, **settings):
        if alsoAllow is None:
            alsoAllow = []
        self.attrs = defaults.copy()
        for (name, value) in settings.items():
            if name not in self.attrs and name not in alsoAllow:
                raise LrsError("%s does not support setting %s" %
                        (self.__class__.__name__, name))
            if isinstance(value, int):
                value = unicode_type(value)
            self.attrs[name] = value


class LrsContainer(object):
    """ This class is a mixin class for elements that are contained in or
        contain an unknown number of other elements.
    """

    def __init__(self, validChildren):
        self.parent = None
        self.contents = []
        self.validChildren = validChildren
        self.must_append = False  # : If True even an empty container is appended by append_to

    def has_text(self):
        ''' Return True iff this container has non whitespace text '''
        if hasattr(self, 'text'):
            if self.text.strip():
                return True
        if hasattr(self, 'contents'):
            for child in self.contents:
                if child.has_text():
                    return True
        for item in self.contents:
            if isinstance(item, (Plot, ImageBlock, Canvas, CR)):
                return True
        return False

    def append_to(self, parent):
        '''
        Append self to C{parent} iff self has non whitespace textual content
        @type parent: LrsContainer
        '''
        if self.contents or self.must_append:
            parent.append(self)

    def appendReferencedObjects(self, parent):
        for c in self.contents:
            c.appendReferencedObjects(parent)

    def setParent(self, parent):
        if self.parent is not None:
            raise LrsError("object already has parent")

        self.parent = parent

    def append(self, content, convertText=True):
        """
            Appends valid objects to container.  Can auto-covert text strings
            to Text objects.
        """
        for validChild in self.validChildren:
            if isinstance(content, validChild):
                break
        else:
            raise LrsError("can't append %s to %s" %
                    (content.__class__.__name__,
                    self.__class__.__name__))

        if convertText and isinstance(content, string_or_bytes):
            content = Text(content)

        content.setParent(self)

        if isinstance(content, LrsObject):
            content.assignId()

        self.contents.append(content)
        return self

    def get_all(self, predicate=lambda x: x):
        for child in self.contents:
            if predicate(child):
                yield child
            if hasattr(child, 'get_all'):
                for grandchild in child.get_all(predicate):
                    yield grandchild


class LrsObject(object):
    """ A mixin class for elements that need an object id. """
    nextObjId = 0

    @classmethod
    def getNextObjId(selfClass):
        selfClass.nextObjId += 1
        return selfClass.nextObjId

    def __init__(self, assignId=False):
        if assignId:
            self.objId = LrsObject.getNextObjId()
        else:
            self.objId = 0

    def assignId(self):
        if self.objId != 0:
            raise LrsError("id already assigned to " + self.__class__.__name__)

        self.objId = LrsObject.getNextObjId()

    def lrsObjectElement(self, name, objlabel="objlabel", labelName=None,
            labelDecorate=True, **settings):
        element = Element(name)
        element.attrib["objid"] = unicode_type(self.objId)
        if labelName is None:
            labelName = name
        if labelDecorate:
            label = "%s.%d" % (labelName, self.objId)
        else:
            label = unicode_type(self.objId)
        element.attrib[objlabel] = label
        element.attrib.update(settings)
        return element


class Book(Delegator):
    """
        Main class for any lrs or lrf.  All objects must be appended to
        the Book class in some way or another in order to be rendered as
        an LRS or LRF file.

        The following settings are available on the contructor of Book:

        author="book author" or author=("book author", "sort as")
        Author of the book.

        title="book title" or title=("book title", "sort as")
        Title of the book.

        sourceencoding="codec"
        Gives the assumed encoding for all non-unicode strings.


        thumbnail="thumbnail file name"
        A small (80x80?) graphics file with a thumbnail of the book's cover.

        bookid="book id"
        A unique id for the book.

        textstyledefault=<dictionary of settings>
        Sets the default values for all TextStyles.

        pagetstyledefault=<dictionary of settings>
        Sets the default values for all PageStyles.

        blockstyledefault=<dictionary of settings>
        Sets the default values for all BlockStyles.

        booksetting=BookSetting()
        Override the default BookSetting.

        setdefault=StyleDefault()
        Override the default SetDefault.

        There are several other settings -- see the BookInfo class for more.
    """

    def __init__(self, textstyledefault=None, blockstyledefault=None,
                       pagestyledefault=None,
                       optimizeTags=False,
                       optimizeCompression=False,
                       **settings):

        self.parent = None  # we are the top of the parent chain

        if "thumbnail" in settings:
            _checkExists(settings["thumbnail"])

        # highly experimental -- use with caution
        self.optimizeTags = optimizeTags
        self.optimizeCompression = optimizeCompression

        pageStyle  = PageStyle(**PageStyle.baseDefaults.copy())
        blockStyle = BlockStyle(**BlockStyle.baseDefaults.copy())
        textStyle  = TextStyle(**TextStyle.baseDefaults.copy())

        if textstyledefault is not None:
            textStyle.update(textstyledefault)

        if blockstyledefault is not None:
            blockStyle.update(blockstyledefault)

        if pagestyledefault is not None:
            pageStyle.update(pagestyledefault)

        self.defaultPageStyle = pageStyle
        self.defaultTextStyle = textStyle
        self.defaultBlockStyle = blockStyle
        LrsObject.nextObjId += 1

        styledefault = StyleDefault()
        if 'setdefault' in settings:
            styledefault = settings.pop('setdefault')
        Delegator.__init__(self, [BookInformation(), Main(),
            Template(), Style(styledefault), Solos(), Objects()])

        self.sourceencoding = None

        # apply default settings
        self.applySetting("genreading", DEFAULT_GENREADING)
        self.applySetting("sourceencoding", DEFAULT_SOURCE_ENCODING)

        self.applySettings(settings, testValid=True)

        self.allow_new_page = True  # : If False L{create_page} raises an exception
        self.gc_count = 0

    def set_title(self, title):
        ot = self.delegates[0].delegates[0].delegates[0].title
        self.delegates[0].delegates[0].delegates[0].title = (title, ot[1])

    def set_author(self, author):
        ot = self.delegates[0].delegates[0].delegates[0].author
        self.delegates[0].delegates[0].delegates[0].author = (author, ot[1])

    def create_text_style(self, **settings):
        ans = TextStyle(**self.defaultTextStyle.attrs.copy())
        ans.update(settings)
        return ans

    def create_block_style(self, **settings):
        ans = BlockStyle(**self.defaultBlockStyle.attrs.copy())
        ans.update(settings)
        return ans

    def create_page_style(self, **settings):
        if not self.allow_new_page:
            raise ContentError
        ans = PageStyle(**self.defaultPageStyle.attrs.copy())
        ans.update(settings)
        return ans

    def create_page(self, pageStyle=None, **settings):
        '''
        Return a new L{Page}. The page has not been appended to this book.
        @param pageStyle: If None the default pagestyle is used.
        @type pageStyle: L{PageStyle}
        '''
        if not pageStyle:
            pageStyle = self.defaultPageStyle
        return Page(pageStyle=pageStyle, **settings)

    def create_text_block(self, textStyle=None, blockStyle=None, **settings):
        '''
        Return a new L{TextBlock}. The block has not been appended to this
        book.
        @param textStyle: If None the default text style is used
        @type textStyle: L{TextStyle}
        @param blockStyle: If None the default block style is used.
        @type blockStyle: L{BlockStyle}
        '''
        if not textStyle:
            textStyle = self.defaultTextStyle
        if not blockStyle:
            blockStyle = self.defaultBlockStyle
        return TextBlock(textStyle=textStyle, blockStyle=blockStyle, **settings)

    def pages(self):
        '''Return list of Page objects in this book '''
        ans = []
        for item in self.delegates:
            if isinstance(item, Main):
                for candidate in item.contents:
                    if isinstance(candidate, Page):
                        ans.append(candidate)
                break
        return ans

    def last_page(self):
        '''Return last Page in this book '''
        for item in self.delegates:
            if isinstance(item, Main):
                temp = list(item.contents)
                temp.reverse()
                for candidate in temp:
                    if isinstance(candidate, Page):
                        return candidate

    def embed_font(self, file, facename):
        f = Font(file, facename)
        self.append(f)

    def getSettings(self):
        return ["sourceencoding"]

    def append(self, content):
        """ Find and invoke the correct appender for this content. """

        className = content.__class__.__name__
        try:
            method = getattr(self, "append" + className)
        except AttributeError:
            raise LrsError("can't append %s to Book" % className)

        method(content)

    def rationalize_font_sizes(self, base_font_size=10):
        base_font_size *= 10.
        main = None
        for obj in self.delegates:
            if isinstance(obj, Main):
                main = obj
                break

        fonts = {}
        for text in main.get_all(lambda x: isinstance(x, Text)):
            fs = base_font_size
            ancestor = text.parent
            while ancestor:
                try:
                    fs = int(ancestor.attrs['fontsize'])
                    break
                except (AttributeError, KeyError):
                    pass
                try:
                    fs = int(ancestor.textSettings['fontsize'])
                    break
                except (AttributeError, KeyError):
                    pass
                try:
                    fs = int(ancestor.textStyle.attrs['fontsize'])
                    break
                except (AttributeError, KeyError):
                    pass
                ancestor = ancestor.parent
            length = len(text.text)
            fonts[fs] = fonts.get(fs, 0) + length
        if not fonts:
            print('WARNING: LRF seems to have no textual content. Cannot rationalize font sizes.')
            return

        old_base_font_size = float(max(fonts.items(), key=operator.itemgetter(1))[0])
        factor = base_font_size / old_base_font_size

        def rescale(old):
            return unicode_type(int(int(old) * factor))

        text_blocks = list(main.get_all(lambda x: isinstance(x, TextBlock)))
        for tb in text_blocks:
            if 'fontsize' in tb.textSettings:
                tb.textSettings['fontsize'] = rescale(tb.textSettings['fontsize'])
            for span in tb.get_all(lambda x: isinstance(x, Span)):
                if 'fontsize' in span.attrs:
                    span.attrs['fontsize'] = rescale(span.attrs['fontsize'])
                if 'baselineskip' in span.attrs:
                    span.attrs['baselineskip'] = rescale(span.attrs['baselineskip'])

        text_styles = set(tb.textStyle for tb in text_blocks)
        for ts in text_styles:
            ts.attrs['fontsize'] = rescale(ts.attrs['fontsize'])
            ts.attrs['baselineskip'] = rescale(ts.attrs['baselineskip'])

    def renderLrs(self, lrsFile, encoding="UTF-8"):
        if isinstance(lrsFile, string_or_bytes):
            lrsFile = codecs.open(lrsFile, "wb", encoding=encoding)
        self.render(lrsFile, outputEncodingName=encoding)
        lrsFile.close()

    def renderLrf(self, lrfFile):
        self.appendReferencedObjects(self)
        if isinstance(lrfFile, string_or_bytes):
            lrfFile = open(lrfFile, "wb")
        lrfWriter = LrfWriter(self.sourceencoding)

        lrfWriter.optimizeTags = self.optimizeTags
        lrfWriter.optimizeCompression = self.optimizeCompression

        self.toLrf(lrfWriter)
        lrfWriter.writeFile(lrfFile)
        lrfFile.close()

    def toElement(self, se):
        root = Element("BBeBXylog", version="1.0")
        root.append(Element("Property"))
        self.appendDelegates(root, self.sourceencoding)
        return root

    def render(self, f, outputEncodingName='UTF-8'):
        """ Write the book as an LRS to file f. """

        self.appendReferencedObjects(self)

        # create the root node, and populate with the parts of the book

        root = self.toElement(self.sourceencoding)

        # now, add some newlines to make it easier to look at

        _formatXml(root)
        tree = ElementTree(element=root)
        tree.write(f, encoding=native_string_type(outputEncodingName), xml_declaration=True)


class BookInformation(Delegator):
    """ Just a container for the Info and TableOfContents elements. """

    def __init__(self):
        Delegator.__init__(self, [Info(), TableOfContents()])

    def toElement(self, se):
        bi = Element("BookInformation")
        self.appendDelegates(bi, se)
        return bi


class Info(Delegator):
    """ Just a container for the BookInfo and DocInfo elements. """

    def __init__(self):
        self.genreading = DEFAULT_GENREADING
        Delegator.__init__(self, [BookInfo(), DocInfo()])

    def getSettings(self):
        return ["genreading"]  # + self.delegatedSettings

    def toElement(self, se):
        info = Element("Info", version="1.1")
        info.append(
            self.delegates[0].toElement(se, reading="s" in self.genreading))
        info.append(self.delegates[1].toElement(se))
        return info

    def toLrf(self, lrfWriter):
        # this info is set in XML form in the LRF
        info = Element("Info", version="1.1")
        # self.appendDelegates(info)
        info.append(
            self.delegates[0].toElement(lrfWriter.getSourceEncoding(), reading="f" in self.genreading))
        info.append(self.delegates[1].toElement(lrfWriter.getSourceEncoding()))

        # look for the thumbnail file and get the filename
        tnail = info.find("DocInfo/CThumbnail")
        if tnail is not None:
            lrfWriter.setThumbnailFile(tnail.get("file"))
            # does not work: info.remove(tnail)

        _formatXml(info)

        # fix up the doc info to match the LRF format
        # NB: generates an encoding attribute, which lrs2lrf does not
        tree = ElementTree(element=info)
        f = io.BytesIO()
        tree.write(f, encoding=native_string_type('utf-8'), xml_declaration=True)
        xmlInfo = f.getvalue().decode('utf-8')
        xmlInfo = re.sub(r"<CThumbnail.*?>\n", "", xmlInfo)
        xmlInfo = xmlInfo.replace("SumPage>", "Page>")
        lrfWriter.docInfoXml = xmlInfo


class TableOfContents(object):

    def __init__(self):
        self.tocEntries = []

    def appendReferencedObjects(self, parent):
        pass

    def getMethods(self):
        return ["addTocEntry"]

    def getSettings(self):
        return []

    def addTocEntry(self, tocLabel, textBlock):
        if not isinstance(textBlock, (Canvas, TextBlock, ImageBlock, RuledLine)):
            raise LrsError("TOC destination must be a Canvas, TextBlock, ImageBlock or RuledLine"+
                            " not a " + unicode_type(type(textBlock)))

        if textBlock.parent is None:
            raise LrsError("TOC text block must be already appended to a page")

        if False and textBlock.parent.parent is None:
            raise LrsError("TOC destination page must be already appended to a book")

        if not hasattr(textBlock.parent, 'objId'):
            raise LrsError("TOC destination must be appended to a container with an objID")

        for tl in self.tocEntries:
            if tl.label == tocLabel and tl.textBlock == textBlock:
                return

        self.tocEntries.append(TocLabel(tocLabel, textBlock))
        textBlock.tocLabel = tocLabel

    def toElement(self, se):
        if len(self.tocEntries) == 0:
            return None

        toc = Element("TOC")

        for t in self.tocEntries:
            toc.append(t.toElement(se))

        return toc

    def toLrf(self, lrfWriter):
        if len(self.tocEntries) == 0:
            return

        toc = []
        for t in self.tocEntries:
            toc.append((t.textBlock.parent.objId, t.textBlock.objId, t.label))

        lrfToc = LrfToc(LrsObject.getNextObjId(), toc, lrfWriter.getSourceEncoding())
        lrfWriter.append(lrfToc)
        lrfWriter.setTocObject(lrfToc)


class TocLabel(object):

    def __init__(self, label, textBlock):
        self.label = escape(re.sub(r'&(\S+?);', entity_to_unicode, label))
        self.textBlock = textBlock

    def toElement(self, se):
        return ElementWithText("TocLabel", self.label,
                 refobj=unicode_type(self.textBlock.objId),
                 refpage=unicode_type(self.textBlock.parent.objId))


class BookInfo(object):

    def __init__(self):
        self.title = "Untitled"
        self.author = "Anonymous"
        self.bookid = None
        self.pi = None
        self.isbn = None
        self.publisher = None
        self.freetext = "\n\n"
        self.label = None
        self.category = None
        self.classification = None

    def appendReferencedObjects(self, parent):
        pass

    def getMethods(self):
        return []

    def getSettings(self):
        return ["author", "title", "bookid", "isbn", "publisher",
                "freetext", "label", "category", "classification"]

    def _appendISBN(self, bi):
        pi = Element("ProductIdentifier")
        isbnElement = ElementWithText("ISBNPrintable", self.isbn)
        isbnValueElement = ElementWithText("ISBNValue",
                self.isbn.replace("-", ""))

        pi.append(isbnElement)
        pi.append(isbnValueElement)
        bi.append(pi)

    def toElement(self, se, reading=True):
        bi = Element("BookInfo")
        bi.append(ElementWithReading("Title", self.title, reading=reading))
        bi.append(ElementWithReading("Author", self.author, reading=reading))
        bi.append(ElementWithText("BookID", self.bookid))
        if self.isbn is not None:
            self._appendISBN(bi)

        if self.publisher is not None:
            bi.append(ElementWithReading("Publisher", self.publisher))

        bi.append(ElementWithReading("Label", self.label, reading=reading))
        bi.append(ElementWithText("Category", self.category))
        bi.append(ElementWithText("Classification", self.classification))
        bi.append(ElementWithText("FreeText", self.freetext))
        return bi


class DocInfo(object):

    def __init__(self):
        self.thumbnail = None
        self.language = "en"
        self.creator  = None
        self.creationdate = unicode_type(isoformat(date.today()))
        self.producer = "%s v%s"%(__appname__, __version__)
        self.numberofpages = "0"

    def appendReferencedObjects(self, parent):
        pass

    def getMethods(self):
        return []

    def getSettings(self):
        return ["thumbnail", "language", "creator", "creationdate",
                "producer", "numberofpages"]

    def toElement(self, se):
        docInfo = Element("DocInfo")

        if self.thumbnail is not None:
            docInfo.append(Element("CThumbnail", file=self.thumbnail))

        docInfo.append(ElementWithText("Language", self.language))
        docInfo.append(ElementWithText("Creator", self.creator))
        docInfo.append(ElementWithText("CreationDate", self.creationdate))
        docInfo.append(ElementWithText("Producer", self.producer))
        docInfo.append(ElementWithText("SumPage", unicode_type(self.numberofpages)))
        return docInfo


class Main(LrsContainer):

    def __init__(self):
        LrsContainer.__init__(self, [Page])

    def getMethods(self):
        return ["appendPage", "Page"]

    def getSettings(self):
        return []

    def Page(self, *args, **kwargs):
        p = Page(*args, **kwargs)
        self.append(p)
        return p

    def appendPage(self, page):
        self.append(page)

    def toElement(self, sourceEncoding):
        main = Element(self.__class__.__name__)

        for page in self.contents:
            main.append(page.toElement(sourceEncoding))

        return main

    def toLrf(self, lrfWriter):
        pageIds = []

        # set this id now so that pages can see it
        pageTreeId = LrsObject.getNextObjId()
        lrfWriter.setPageTreeId(pageTreeId)

        # create a list of all the page object ids while dumping the pages

        for p in self.contents:
            pageIds.append(p.objId)
            p.toLrf(lrfWriter)

        # create a page tree object

        pageTree = LrfObject("PageTree", pageTreeId)
        pageTree.appendLrfTag(LrfTag("PageList", pageIds))

        lrfWriter.append(pageTree)


class Solos(LrsContainer):

    def __init__(self):
        LrsContainer.__init__(self, [Solo])

    def getMethods(self):
        return ["appendSolo", "Solo"]

    def getSettings(self):
        return []

    def Solo(self, *args, **kwargs):
        p = Solo(*args, **kwargs)
        self.append(p)
        return p

    def appendSolo(self, solo):
        self.append(solo)

    def toLrf(self, lrfWriter):
        for s in self.contents:
            s.toLrf(lrfWriter)

    def toElement(self, se):
        solos = []
        for s in self.contents:
            solos.append(s.toElement(se))

        if len(solos) == 0:
            return None

        return solos


class Solo(Main):
    pass


class Template(object):
    """ Does nothing that I know of. """

    def appendReferencedObjects(self, parent):
        pass

    def getMethods(self):
        return []

    def getSettings(self):
        return []

    def toElement(self, se):
        t = Element("Template")
        t.attrib["version"] = "1.0"
        return t

    def toLrf(self, lrfWriter):
        # does nothing
        pass


class StyleDefault(LrsAttributes):
    """
        Supply some defaults for all TextBlocks.
        The legal values are a subset of what is allowed on a
        TextBlock -- ruby, emphasis, and waitprop settings.
    """
    defaults = dict(rubyalign="start", rubyadjust="none",
                rubyoverhang="none", empdotsposition="before",
                empdotsfontname="Dutch801 Rm BT Roman",
                empdotscode="0x002e", emplineposition="after",
                emplinetype="solid", setwaitprop="noreplay")

    alsoAllow = ["refempdotsfont", "rubyAlignAndAdjust"]

    def __init__(self, **settings):
        LrsAttributes.__init__(self, self.defaults,
                alsoAllow=self.alsoAllow, **settings)

    def toElement(self, se):
        return Element("SetDefault", self.attrs)


class Style(LrsContainer, Delegator):

    def __init__(self, styledefault=StyleDefault()):
        LrsContainer.__init__(self, [PageStyle, TextStyle, BlockStyle])
        Delegator.__init__(self, [BookStyle(styledefault=styledefault)])
        self.bookStyle = self.delegates[0]
        self.appendPageStyle = self.appendTextStyle = \
                self.appendBlockStyle = self.append

    def appendReferencedObjects(self, parent):
        LrsContainer.appendReferencedObjects(self, parent)

    def getMethods(self):
        return ["PageStyle", "TextStyle", "BlockStyle",
                "appendPageStyle", "appendTextStyle", "appendBlockStyle"] + \
                        self.delegatedMethods

    def getSettings(self):
        return [(self.bookStyle, x) for x in self.bookStyle.getSettings()]

    def PageStyle(self, *args, **kwargs):
        ps = PageStyle(*args, **kwargs)
        self.append(ps)
        return ps

    def TextStyle(self, *args, **kwargs):
        ts = TextStyle(*args, **kwargs)
        self.append(ts)
        return ts

    def BlockStyle(self, *args, **kwargs):
        bs = BlockStyle(*args, **kwargs)
        self.append(bs)
        return bs

    def toElement(self, se):
        style = Element("Style")
        style.append(self.bookStyle.toElement(se))

        for content in self.contents:
            style.append(content.toElement(se))

        return style

    def toLrf(self, lrfWriter):
        self.bookStyle.toLrf(lrfWriter)

        for s in self.contents:
            s.toLrf(lrfWriter)


class BookStyle(LrsObject, LrsContainer):

    def __init__(self, styledefault=StyleDefault()):
        LrsObject.__init__(self, assignId=True)
        LrsContainer.__init__(self, [Font])
        self.styledefault = styledefault
        self.booksetting = BookSetting()
        self.appendFont = self.append

    def getSettings(self):
        return ["styledefault", "booksetting"]

    def getMethods(self):
        return ["Font", "appendFont"]

    def Font(self, *args, **kwargs):
        f = Font(*args, **kwargs)
        self.append(f)
        return

    def toElement(self, se):
        bookStyle = self.lrsObjectElement("BookStyle", objlabel="stylelabel",
                labelDecorate=False)
        bookStyle.append(self.styledefault.toElement(se))
        bookStyle.append(self.booksetting.toElement(se))
        for font in self.contents:
            bookStyle.append(font.toElement(se))

        return bookStyle

    def toLrf(self, lrfWriter):
        bookAtr = LrfObject("BookAtr", self.objId)
        bookAtr.appendLrfTag(LrfTag("ChildPageTree", lrfWriter.getPageTreeId()))
        bookAtr.appendTagDict(self.styledefault.attrs)

        self.booksetting.toLrf(lrfWriter)

        lrfWriter.append(bookAtr)
        lrfWriter.setRootObject(bookAtr)

        for font in self.contents:
            font.toLrf(lrfWriter)


class BookSetting(LrsAttributes):

    def __init__(self, **settings):
        defaults = dict(bindingdirection="Lr", dpi="1660",
                screenheight="800", screenwidth="600", colordepth="24")
        LrsAttributes.__init__(self, defaults, **settings)

    def toLrf(self, lrfWriter):
        a = self.attrs
        lrfWriter.dpi = int(a["dpi"])
        lrfWriter.bindingdirection = \
                BINDING_DIRECTION_ENCODING[a["bindingdirection"]]
        lrfWriter.height = int(a["screenheight"])
        lrfWriter.width = int(a["screenwidth"])
        lrfWriter.colorDepth = int(a["colordepth"])

    def toElement(self, se):
        return Element("BookSetting", self.attrs)


class LrsStyle(LrsObject, LrsAttributes, LrsContainer):
    """ A mixin class for styles. """

    def __init__(self, elementName, defaults=None, alsoAllow=None, **overrides):
        if defaults is None:
            defaults = {}

        LrsObject.__init__(self)
        LrsAttributes.__init__(self, defaults, alsoAllow=alsoAllow, **overrides)
        LrsContainer.__init__(self, [])
        self.elementName = elementName
        self.objectsAppended = False
        # self.label = "%s.%d" % (elementName, self.objId)
        # self.label = unicode_type(self.objId)
        # self.parent = None

    def update(self, settings):
        for name, value in settings.items():
            if name not in self.__class__.validSettings:
                raise LrsError("%s not a valid setting for %s" % (name, self.__class__.__name__))
            self.attrs[name] = value

    def getLabel(self):
        return unicode_type(self.objId)

    def toElement(self, se):
        element = Element(self.elementName, stylelabel=self.getLabel(),
                objid=unicode_type(self.objId))
        element.attrib.update(self.attrs)
        return element

    def toLrf(self, lrfWriter):
        obj = LrfObject(self.elementName, self.objId)
        obj.appendTagDict(self.attrs, self.__class__.__name__)
        lrfWriter.append(obj)

    def __eq__(self, other):
        if hasattr(other, 'attrs'):
            return self.__class__ == other.__class__ and self.attrs == other.attrs
        return False


class TextStyle(LrsStyle):
    """
        The text style of a TextBlock.  Default is 10 pt. Times Roman.

        Setting         Value                   Default
        --------        -----                   -------
        align           "head","center","foot"  "head" (left aligned)
        baselineskip    points * 10             120 (12 pt. distance between
                                                  bottoms of lines)
        fontsize        points * 10             100 (10 pt.)
        fontweight      1 to 1000               400 (normal, 800 is bold)
        fontwidth       points * 10 or -10      -10 (use values from font)
        linespace       points * 10             10 (min space btw. lines?)
        wordspace       points * 10             25 (min space btw. each word)

    """
    baseDefaults = dict(
            columnsep="0", charspace="0",
            textlinewidth="2", align="head", linecolor="0x00000000",
            column="1", fontsize="100", fontwidth="-10", fontescapement="0",
            fontorientation="0", fontweight="400",
            fontfacename="Dutch801 Rm BT Roman",
            textcolor="0x00000000", wordspace="25", letterspace="0",
            baselineskip="120", linespace="10", parindent="0", parskip="0",
            textbgcolor="0xFF000000")

    alsoAllow = ["empdotscode", "empdotsfontname", "refempdotsfont",
                 "rubyadjust", "rubyalign", "rubyoverhang",
                 "empdotsposition", 'emplinetype', 'emplineposition']

    validSettings = list(baseDefaults) + alsoAllow

    defaults = baseDefaults.copy()

    def __init__(self, **overrides):
        LrsStyle.__init__(self, "TextStyle", self.defaults,
                alsoAllow=self.alsoAllow, **overrides)

    def copy(self):
        tb = TextStyle()
        tb.attrs = self.attrs.copy()
        return tb


class BlockStyle(LrsStyle):
    """
        The block style of a TextBlock.  Default is an expandable 560 pixel
        wide area with no space for headers or footers.

        Setting      Value                  Default
        --------     -----                  -------
        blockwidth   pixels                 560
        sidemargin   pixels                 0
    """

    baseDefaults = dict(
            bgimagemode="fix", framemode="square", blockwidth="560",
            blockheight="100", blockrule="horz-adjustable", layout="LrTb",
            framewidth="0", framecolor="0x00000000", topskip="0",
            sidemargin="0", footskip="0", bgcolor="0xFF000000")

    validSettings = baseDefaults.keys()
    defaults = baseDefaults.copy()

    def __init__(self, **overrides):
        LrsStyle.__init__(self, "BlockStyle", self.defaults, **overrides)

    def copy(self):
        tb = BlockStyle()
        tb.attrs = self.attrs.copy()
        return tb


class PageStyle(LrsStyle):
    """
        Setting         Value                   Default
        --------        -----                   -------
        evensidemargin  pixels                  20
        oddsidemargin   pixels                  20
        topmargin       pixels                  20
    """
    baseDefaults = dict(
            topmargin="20", headheight="0", headsep="0",
            oddsidemargin="20", textheight="747", textwidth="575",
            footspace="0", evensidemargin="20", footheight="0",
            layout="LrTb", bgimagemode="fix", pageposition="any",
            setwaitprop="noreplay", setemptyview="show")

    alsoAllow = ["header", "evenheader", "oddheader",
                 "footer", "evenfooter", "oddfooter"]

    validSettings = list(baseDefaults) + alsoAllow
    defaults = baseDefaults.copy()

    @classmethod
    def translateHeaderAndFooter(selfClass, parent, settings):
        selfClass._fixup(parent, "header", settings)
        selfClass._fixup(parent, "footer", settings)

    @classmethod
    def _fixup(selfClass, parent, basename, settings):
        evenbase = "even" + basename
        oddbase = "odd" + basename
        if basename in settings:
            baseObj = settings[basename]
            del settings[basename]
            settings[evenbase] = settings[oddbase] = baseObj

        if evenbase in settings:
            evenObj = settings[evenbase]
            del settings[evenbase]
            if evenObj.parent is None:
                parent.append(evenObj)
            settings[evenbase + "id"] = unicode_type(evenObj.objId)

        if oddbase in settings:
            oddObj = settings[oddbase]
            del settings[oddbase]
            if oddObj.parent is None:
                parent.append(oddObj)
            settings[oddbase + "id"] = unicode_type(oddObj.objId)

    def appendReferencedObjects(self, parent):
        if self.objectsAppended:
            return
        PageStyle.translateHeaderAndFooter(parent, self.attrs)
        self.objectsAppended = True

    def __init__(self, **settings):
        # self.fixHeaderSettings(settings)
        LrsStyle.__init__(self, "PageStyle", self.defaults,
                alsoAllow=self.alsoAllow, **settings)


class Page(LrsObject, LrsContainer):
    """
        Pages are added to Books.  Pages can be supplied a PageStyle.
        If they are not, Page.defaultPageStyle will be used.
    """
    defaultPageStyle = PageStyle()

    def __init__(self, pageStyle=defaultPageStyle, **settings):
        LrsObject.__init__(self)
        LrsContainer.__init__(self, [TextBlock, BlockSpace, RuledLine,
            ImageBlock, Canvas])

        self.pageStyle = pageStyle

        for settingName in settings.keys():
            if settingName not in PageStyle.defaults and \
                    settingName not in PageStyle.alsoAllow:
                raise LrsError("setting %s not allowed on Page" % settingName)

        self.settings = settings.copy()

    def appendReferencedObjects(self, parent):
        PageStyle.translateHeaderAndFooter(parent, self.settings)

        self.pageStyle.appendReferencedObjects(parent)

        if self.pageStyle.parent is None:
            parent.append(self.pageStyle)

        LrsContainer.appendReferencedObjects(self, parent)

    def RuledLine(self, *args, **kwargs):
        rl = RuledLine(*args, **kwargs)
        self.append(rl)
        return rl

    def BlockSpace(self, *args, **kwargs):
        bs = BlockSpace(*args, **kwargs)
        self.append(bs)
        return bs

    def TextBlock(self, *args, **kwargs):
        """ Create and append a new text block (shortcut). """
        tb = TextBlock(*args, **kwargs)
        self.append(tb)
        return tb

    def ImageBlock(self, *args, **kwargs):
        """ Create and append and new Image block (shorthand). """
        ib = ImageBlock(*args, **kwargs)
        self.append(ib)
        return ib

    def addLrfObject(self, objId):
        self.stream.appendLrfTag(LrfTag("Link", objId))

    def appendLrfTag(self, lrfTag):
        self.stream.appendLrfTag(lrfTag)

    def toLrf(self, lrfWriter):
        # tags:
        # ObjectList
        # Link to pagestyle
        # Parent page tree id
        # stream of tags

        p = LrfObject("Page", self.objId)
        lrfWriter.append(p)

        pageContent = set()
        self.stream = LrfTagStream(0)
        for content in self.contents:
            content.toLrfContainer(lrfWriter, self)
            if hasattr(content, "getReferencedObjIds"):
                pageContent.update(content.getReferencedObjIds())

        # print "page contents:", pageContent
        # ObjectList not needed and causes slowdown in SONY LRF renderer
        # p.appendLrfTag(LrfTag("ObjectList", pageContent))
        p.appendLrfTag(LrfTag("Link", self.pageStyle.objId))
        p.appendLrfTag(LrfTag("ParentPageTree", lrfWriter.getPageTreeId()))
        p.appendTagDict(self.settings)
        p.appendLrfTags(self.stream.getStreamTags(lrfWriter.getSourceEncoding()))

    def toElement(self, sourceEncoding):
        page = self.lrsObjectElement("Page")
        page.set("pagestyle", self.pageStyle.getLabel())
        page.attrib.update(self.settings)

        for content in self.contents:
            page.append(content.toElement(sourceEncoding))

        return page


class TextBlock(LrsObject, LrsContainer):
    """
        TextBlocks are added to Pages.  They hold Paragraphs or CRs.

        If a TextBlock is used in a header, it should be appended to
        the Book, not to a specific Page.
    """
    defaultTextStyle = TextStyle()
    defaultBlockStyle = BlockStyle()

    def __init__(self, textStyle=defaultTextStyle,
                       blockStyle=defaultBlockStyle,
                       **settings):
        '''
        Create TextBlock.
        @param textStyle: The L{TextStyle} for this block.
        @param blockStyle: The L{BlockStyle} for this block.
        @param settings: C{dict} of extra settings to apply to this block.
        '''
        LrsObject.__init__(self)
        LrsContainer.__init__(self, [Paragraph, CR])

        self.textSettings = {}
        self.blockSettings = {}

        for name, value in settings.items():
            if name in TextStyle.validSettings:
                self.textSettings[name] = value
            elif name in BlockStyle.validSettings:
                self.blockSettings[name] = value
            elif name == 'toclabel':
                self.tocLabel = value
            else:
                raise LrsError("%s not a valid setting for TextBlock" % name)

        self.textStyle = textStyle
        self.blockStyle = blockStyle

        # create a textStyle with our current text settings (for Span to find)
        self.currentTextStyle = textStyle.copy() if self.textSettings else textStyle
        self.currentTextStyle.attrs.update(self.textSettings)

    def appendReferencedObjects(self, parent):
        if self.textStyle.parent is None:
            parent.append(self.textStyle)

        if self.blockStyle.parent is None:
            parent.append(self.blockStyle)

        LrsContainer.appendReferencedObjects(self, parent)

    def Paragraph(self, *args, **kwargs):
        """
            Create and append a Paragraph to this TextBlock.  A CR is
            automatically inserted after the Paragraph.  To avoid this
            behavior, create the Paragraph and append it to the TextBlock
            in a separate call.
        """
        p = Paragraph(*args, **kwargs)
        self.append(p)
        self.append(CR())
        return p

    def toElement(self, sourceEncoding):
        tb = self.lrsObjectElement("TextBlock", labelName="Block")
        tb.attrib.update(self.textSettings)
        tb.attrib.update(self.blockSettings)
        tb.set("textstyle", self.textStyle.getLabel())
        tb.set("blockstyle", self.blockStyle.getLabel())
        if hasattr(self, "tocLabel"):
            tb.set("toclabel", self.tocLabel)

        for content in self.contents:
            tb.append(content.toElement(sourceEncoding))

        return tb

    def getReferencedObjIds(self):
        ids = [self.objId, self.extraId, self.blockStyle.objId,
                self.textStyle.objId]
        for content in self.contents:
            if hasattr(content, "getReferencedObjIds"):
                ids.extend(content.getReferencedObjIds())

        return ids

    def toLrf(self, lrfWriter):
        self.toLrfContainer(lrfWriter, lrfWriter)

    def toLrfContainer(self, lrfWriter, container):
        # id really belongs to the outer block
        extraId = LrsObject.getNextObjId()

        b = LrfObject("Block", self.objId)
        b.appendLrfTag(LrfTag("Link", self.blockStyle.objId))
        b.appendLrfTags(
                LrfTagStream(0, [LrfTag("Link", extraId)]).getStreamTags(lrfWriter.getSourceEncoding()))
        b.appendTagDict(self.blockSettings)
        container.addLrfObject(b.objId)
        lrfWriter.append(b)

        tb = LrfObject("TextBlock", extraId)
        tb.appendLrfTag(LrfTag("Link", self.textStyle.objId))
        tb.appendTagDict(self.textSettings)

        stream = LrfTagStream(STREAM_COMPRESSED)
        for content in self.contents:
            content.toLrfContainer(lrfWriter, stream)

        if lrfWriter.saveStreamTags:  # true only if testing
            tb.saveStreamTags = stream.tags

        tb.appendLrfTags(
                stream.getStreamTags(lrfWriter.getSourceEncoding(),
                    optimizeTags=lrfWriter.optimizeTags,
                    optimizeCompression=lrfWriter.optimizeCompression))
        lrfWriter.append(tb)

        self.extraId = extraId


class Paragraph(LrsContainer):
    """
        Note: <P> alone does not make a paragraph.  Only a CR inserted
        into a text block right after a <P> makes a real paragraph.
        Two Paragraphs appended in a row act like a single Paragraph.

        Also note that there are few autoappenders for Paragraph (and
        the things that can go in it.)  It's less confusing (to me) to use
        explicit .append methods to build up the text stream.
    """

    def __init__(self, text=None):
        LrsContainer.__init__(self, [Text, CR, DropCaps, CharButton,
                                     LrsSimpleChar1, bytes, unicode_type])
        if text is not None:
            if isinstance(text, string_or_bytes):
                text = Text(text)
            self.append(text)

    def CR(self):
        # Okay, here's a single autoappender for this common operation
        cr = CR()
        self.append(cr)
        return cr

    def getReferencedObjIds(self):
        ids = []
        for content in self.contents:
            if hasattr(content, "getReferencedObjIds"):
                ids.extend(content.getReferencedObjIds())

        return ids

    def toLrfContainer(self, lrfWriter, parent):
        parent.appendLrfTag(LrfTag("pstart", 0))
        for content in self.contents:
            content.toLrfContainer(lrfWriter, parent)
        parent.appendLrfTag(LrfTag("pend"))

    def toElement(self, sourceEncoding):
        p = Element("P")
        appendTextElements(p, self.contents, sourceEncoding)
        return p


class LrsTextTag(LrsContainer):

    def __init__(self, text, validContents):
        LrsContainer.__init__(self, [Text, bytes, unicode_type] + validContents)
        if text is not None:
            self.append(text)

    def toLrfContainer(self, lrfWriter, parent):
        if hasattr(self, "tagName"):
            tagName = self.tagName
        else:
            tagName = self.__class__.__name__

        parent.appendLrfTag(LrfTag(tagName))

        for content in self.contents:
            content.toLrfContainer(lrfWriter, parent)

        parent.appendLrfTag(LrfTag(tagName + "End"))

    def toElement(self, se):
        if hasattr(self, "tagName"):
            tagName = self.tagName
        else:
            tagName = self.__class__.__name__

        p = Element(tagName)
        appendTextElements(p, self.contents, se)
        return p


class LrsSimpleChar1(object):

    def isEmpty(self):
        for content in self.contents:
            if not content.isEmpty():
                return False
        return True

    def hasFollowingContent(self):
        foundSelf = False
        for content in self.parent.contents:
            if content == self:
                foundSelf = True
            elif foundSelf:
                if not content.isEmpty():
                    return True
        return False


class DropCaps(LrsTextTag):

    def __init__(self, line=1):
        LrsTextTag.__init__(self, None, [LrsSimpleChar1])
        if int(line) <= 0:
            raise LrsError('A DrawChar must span at least one line.')
        self.line = int(line)

    def isEmpty(self):
        return self.text is None or not self.text.strip()

    def toElement(self, se):
        elem =  Element('DrawChar', line=unicode_type(self.line))
        appendTextElements(elem, self.contents, se)
        return elem

    def toLrfContainer(self, lrfWriter, parent):
        parent.appendLrfTag(LrfTag('DrawChar', (int(self.line),)))

        for content in self.contents:
            content.toLrfContainer(lrfWriter, parent)

        parent.appendLrfTag(LrfTag("DrawCharEnd"))


class Button(LrsObject, LrsContainer):

    def __init__(self, **settings):
        LrsObject.__init__(self, **settings)
        LrsContainer.__init__(self, [PushButton])

    def findJumpToRefs(self):
        for sub1 in self.contents:
            if isinstance(sub1, PushButton):
                for sub2 in sub1.contents:
                    if isinstance(sub2, JumpTo):
                        return (sub2.textBlock.objId, sub2.textBlock.parent.objId)
        raise LrsError("%s has no PushButton or JumpTo subs"%self.__class__.__name__)

    def toLrf(self, lrfWriter):
        (refobj, refpage) = self.findJumpToRefs()
        # print "Button writing JumpTo refobj=", jumpto.refobj, ", and refpage=", jumpto.refpage
        button = LrfObject("Button", self.objId)
        button.appendLrfTag(LrfTag("buttonflags", 0x10))  # pushbutton
        button.appendLrfTag(LrfTag("PushButtonStart"))
        button.appendLrfTag(LrfTag("buttonactions"))
        button.appendLrfTag(LrfTag("jumpto", (int(refpage), int(refobj))))
        button.append(LrfTag("endbuttonactions"))
        button.appendLrfTag(LrfTag("PushButtonEnd"))
        lrfWriter.append(button)

    def toElement(self, se):
        b = self.lrsObjectElement("Button")

        for content in self.contents:
            b.append(content.toElement(se))

        return b


class ButtonBlock(Button):
    pass


class PushButton(LrsContainer):

    def __init__(self, **settings):
        LrsContainer.__init__(self, [JumpTo])

    def toElement(self, se):
        b = Element("PushButton")

        for content in self.contents:
            b.append(content.toElement(se))

        return b


class JumpTo(LrsContainer):

    def __init__(self, textBlock):
        LrsContainer.__init__(self, [])
        self.textBlock=textBlock

    def setTextBlock(self, textBlock):
        self.textBlock = textBlock

    def toElement(self, se):
        return Element("JumpTo", refpage=unicode_type(self.textBlock.parent.objId), refobj=unicode_type(self.textBlock.objId))


class Plot(LrsSimpleChar1, LrsContainer):

    ADJUSTMENT_VALUES = {'center':1, 'baseline':2, 'top':3, 'bottom':4}

    def __init__(self, obj, xsize=0, ysize=0, adjustment=None):
        LrsContainer.__init__(self, [])
        if obj is not None:
            self.setObj(obj)
        if xsize < 0 or ysize < 0:
            raise LrsError('Sizes must be positive semi-definite')
        self.xsize = int(xsize)
        self.ysize = int(ysize)
        if adjustment and adjustment not in Plot.ADJUSTMENT_VALUES.keys():
            raise LrsError('adjustment must be one of' + Plot.ADJUSTMENT_VALUES.keys())
        self.adjustment = adjustment

    def setObj(self, obj):
        if not isinstance(obj, (Image, Button)):
            raise LrsError('Plot elements can only refer to Image or Button elements')
        self.obj = obj

    def getReferencedObjIds(self):
        return [self.obj.objId]

    def appendReferencedObjects(self, parent):
        if self.obj.parent is None:
            parent.append(self.obj)

    def toElement(self, se):
        elem =  Element('Plot', xsize=unicode_type(self.xsize), ysize=unicode_type(self.ysize),
                                refobj=unicode_type(self.obj.objId))
        if self.adjustment:
            elem.set('adjustment', self.adjustment)
        return elem

    def toLrfContainer(self, lrfWriter, parent):
        adj = self.adjustment if self.adjustment else 'bottom'
        params = (int(self.xsize), int(self.ysize), int(self.obj.objId),
                  Plot.ADJUSTMENT_VALUES[adj])
        parent.appendLrfTag(LrfTag("Plot", params))


class Text(LrsContainer):
    """ A object that represents raw text.  Does not have a toElement. """

    def __init__(self, text):
        LrsContainer.__init__(self, [])
        self.text = text

    def isEmpty(self):
        return not self.text or not self.text.strip()

    def toLrfContainer(self, lrfWriter, parent):
        if self.text:
            if isinstance(self.text, bytes):
                parent.appendLrfTag(LrfTag("rawtext", self.text))
            else:
                parent.appendLrfTag(LrfTag("textstring", self.text))


class CR(LrsSimpleChar1, LrsContainer):
    """
        A line break (when appended to a Paragraph) or a paragraph break
        (when appended to a TextBlock).
    """

    def __init__(self):
        LrsContainer.__init__(self, [])

    def toElement(self, se):
        return Element("CR")

    def toLrfContainer(self, lrfWriter, parent):
        parent.appendLrfTag(LrfTag("CR"))


class Italic(LrsSimpleChar1, LrsTextTag):

    def __init__(self, text=None):
        LrsTextTag.__init__(self, text, [LrsSimpleChar1])


class Sub(LrsSimpleChar1, LrsTextTag):

    def __init__(self, text=None):
        LrsTextTag.__init__(self, text, [])


class Sup(LrsSimpleChar1, LrsTextTag):

    def __init__(self, text=None):
        LrsTextTag.__init__(self, text, [])


class NoBR(LrsSimpleChar1, LrsTextTag):

    def __init__(self, text=None):
        LrsTextTag.__init__(self, text, [LrsSimpleChar1])


class Space(LrsSimpleChar1, LrsContainer):

    def __init__(self, xsize=0, x=0):
        LrsContainer.__init__(self, [])
        if xsize == 0 and x != 0:
            xsize = x
        self.xsize = xsize

    def toElement(self, se):
        if self.xsize == 0:
            return

        return Element("Space", xsize=unicode_type(self.xsize))

    def toLrfContainer(self, lrfWriter, container):
        if self.xsize != 0:
            container.appendLrfTag(LrfTag("Space", self.xsize))


class Box(LrsSimpleChar1, LrsContainer):
    """
        Draw a box around text.  Unfortunately, does not seem to do
        anything on the PRS-500.
    """

    def __init__(self, linetype="solid"):
        LrsContainer.__init__(self, [Text, bytes, unicode_type])
        if linetype not in LINE_TYPE_ENCODING:
            raise LrsError(linetype + " is not a valid line type")
        self.linetype = linetype

    def toElement(self, se):
        e = Element("Box", linetype=self.linetype)
        appendTextElements(e, self.contents, se)
        return e

    def toLrfContainer(self, lrfWriter, container):
        container.appendLrfTag(LrfTag("Box", self.linetype))
        for content in self.contents:
            content.toLrfContainer(lrfWriter, container)
        container.appendLrfTag(LrfTag("BoxEnd"))


class Span(LrsSimpleChar1, LrsContainer):

    def __init__(self, text=None, **attrs):
        LrsContainer.__init__(self, [LrsSimpleChar1, Text, bytes, unicode_type])
        if text is not None:
            if isinstance(text, string_or_bytes):
                text = Text(text)
            self.append(text)

        for attrname in attrs.keys():
            if attrname not in TextStyle.defaults and \
                    attrname not in TextStyle.alsoAllow:
                raise LrsError("setting %s not allowed on Span" % attrname)
        self.attrs = attrs

    def findCurrentTextStyle(self):
        parent = self.parent
        while 1:
            if parent is None or hasattr(parent, "currentTextStyle"):
                break
            parent = parent.parent

        if parent is None:
            raise LrsError("no enclosing current TextStyle found")

        return parent.currentTextStyle

    def toLrfContainer(self, lrfWriter, container):

        # find the currentTextStyle
        oldTextStyle = self.findCurrentTextStyle()

        # set the attributes we want changed
        for (name, value) in tuple(iteritems(self.attrs)):
            if name in oldTextStyle.attrs and oldTextStyle.attrs[name] == self.attrs[name]:
                self.attrs.pop(name)
            else:
                container.appendLrfTag(LrfTag(name, value))

        # set a currentTextStyle so nested span can put things back
        oldTextStyle = self.findCurrentTextStyle()
        self.currentTextStyle = oldTextStyle.copy()
        self.currentTextStyle.attrs.update(self.attrs)

        for content in self.contents:
            content.toLrfContainer(lrfWriter, container)

        # put the attributes back the way we found them
        # the attributes persist beyond the next </P>
        # if self.hasFollowingContent():
        for name in self.attrs.keys():
            container.appendLrfTag(LrfTag(name, oldTextStyle.attrs[name]))

    def toElement(self, se):
        element = Element('Span')
        for (key, value) in self.attrs.items():
            element.set(key, unicode_type(value))

        appendTextElements(element, self.contents, se)
        return element


class EmpLine(LrsTextTag, LrsSimpleChar1):
    emplinetypes = ['none', 'solid', 'dotted', 'dashed', 'double']
    emplinepositions = ['before', 'after']

    def __init__(self, text=None, emplineposition='before', emplinetype='solid'):
        LrsTextTag.__init__(self, text, [LrsSimpleChar1])
        if emplineposition not in self.__class__.emplinepositions:
            raise LrsError('emplineposition for an EmpLine must be one of: '+unicode_type(self.__class__.emplinepositions))
        if emplinetype not in self.__class__.emplinetypes:
            raise LrsError('emplinetype for an EmpLine must be one of: '+unicode_type(self.__class__.emplinetypes))

        self.emplinetype     = emplinetype
        self.emplineposition = emplineposition

    def toLrfContainer(self, lrfWriter, parent):
        parent.appendLrfTag(LrfTag(self.__class__.__name__, (self.emplineposition, self.emplinetype)))
        parent.appendLrfTag(LrfTag('emplineposition', self.emplineposition))
        parent.appendLrfTag(LrfTag('emplinetype', self.emplinetype))
        for content in self.contents:
            content.toLrfContainer(lrfWriter, parent)

        parent.appendLrfTag(LrfTag(self.__class__.__name__ + "End"))

    def toElement(self, se):
        element = Element(self.__class__.__name__)
        element.set('emplineposition', self.emplineposition)
        element.set('emplinetype', self.emplinetype)

        appendTextElements(element, self.contents, se)
        return element


class Bold(Span):
    """
        There is no known "bold" lrf tag. Use Span with a fontweight in LRF,
        but use the word Bold in the LRS.
    """

    def __init__(self, text=None):
        Span.__init__(self, text, fontweight=800)

    def toElement(self, se):
        e = Element("Bold")
        appendTextElements(e, self.contents, se)
        return e


class BlockSpace(LrsContainer):
    """ Can be appended to a page to move the text point. """

    def __init__(self, xspace=0, yspace=0, x=0, y=0):
        LrsContainer.__init__(self, [])
        if xspace == 0 and x != 0:
            xspace = x
        if yspace == 0 and y != 0:
            yspace = y
        self.xspace = xspace
        self.yspace = yspace

    def toLrfContainer(self, lrfWriter, container):
        if self.xspace != 0:
            container.appendLrfTag(LrfTag("xspace", self.xspace))
        if self.yspace != 0:
            container.appendLrfTag(LrfTag("yspace", self.yspace))

    def toElement(self, se):
        element = Element("BlockSpace")

        if self.xspace != 0:
            element.attrib["xspace"] = unicode_type(self.xspace)
        if self.yspace != 0:
            element.attrib["yspace"] = unicode_type(self.yspace)

        return element


class CharButton(LrsSimpleChar1, LrsContainer):
    """
        Define the text and target of a CharButton.  Must be passed a
        JumpButton that is the destination of the CharButton.

        Only text or SimpleChars can be appended to the CharButton.
    """

    def __init__(self, button, text=None):
        LrsContainer.__init__(self, [bytes, unicode_type, Text, LrsSimpleChar1])
        self.button = None
        if button is not None:
            self.setButton(button)

        if text is not None:
            self.append(text)

    def setButton(self, button):
        if not isinstance(button, (JumpButton, Button)):
            raise LrsError("CharButton button must be a JumpButton or Button")

        self.button = button

    def appendReferencedObjects(self, parent):
        if self.button.parent is None:
            parent.append(self.button)

    def getReferencedObjIds(self):
        return [self.button.objId]

    def toLrfContainer(self, lrfWriter, container):
        container.appendLrfTag(LrfTag("CharButton", self.button.objId))

        for content in self.contents:
            content.toLrfContainer(lrfWriter, container)

        container.appendLrfTag(LrfTag("CharButtonEnd"))

    def toElement(self, se):
        cb = Element("CharButton", refobj=unicode_type(self.button.objId))
        appendTextElements(cb, self.contents, se)
        return cb


class Objects(LrsContainer):

    def __init__(self):
        LrsContainer.__init__(self, [JumpButton, TextBlock, HeaderOrFooter,
            ImageStream, Image, ImageBlock, Button, ButtonBlock])
        self.appendJumpButton = self.appendTextBlock = self.appendHeader = \
                self.appendFooter = self.appendImageStream = \
                self.appendImage = self.appendImageBlock = self.append

    def getMethods(self):
        return ["JumpButton", "appendJumpButton", "TextBlock",
                "appendTextBlock", "Header", "appendHeader",
                "Footer", "appendFooter", "ImageBlock",
                "ImageStream", "appendImageStream",
                'Image','appendImage', 'appendImageBlock']

    def getSettings(self):
        return []

    def ImageBlock(self, *args, **kwargs):
        ib = ImageBlock(*args, **kwargs)
        self.append(ib)
        return ib

    def JumpButton(self, textBlock):
        b = JumpButton(textBlock)
        self.append(b)
        return b

    def TextBlock(self, *args, **kwargs):
        tb = TextBlock(*args, **kwargs)
        self.append(tb)
        return tb

    def Header(self, *args, **kwargs):
        h = Header(*args, **kwargs)
        self.append(h)
        return h

    def Footer(self, *args, **kwargs):
        h = Footer(*args, **kwargs)
        self.append(h)
        return h

    def ImageStream(self, *args, **kwargs):
        i = ImageStream(*args, **kwargs)
        self.append(i)
        return i

    def Image(self, *args, **kwargs):
        i = Image(*args, **kwargs)
        self.append(i)
        return i

    def toElement(self, se):
        o = Element("Objects")

        for content in self.contents:
            o.append(content.toElement(se))

        return o

    def toLrf(self, lrfWriter):
        for content in self.contents:
            content.toLrf(lrfWriter)


class JumpButton(LrsObject, LrsContainer):
    """
        The target of a CharButton.  Needs a parented TextBlock to jump to.
        Actually creates several elements in the XML.  JumpButtons must
        be eventually appended to a Book (actually, an Object.)
    """

    def __init__(self, textBlock):
        LrsObject.__init__(self)
        LrsContainer.__init__(self, [])
        self.textBlock = textBlock

    def setTextBlock(self, textBlock):
        self.textBlock = textBlock

    def toLrf(self, lrfWriter):
        button = LrfObject("Button", self.objId)
        button.appendLrfTag(LrfTag("buttonflags", 0x10))  # pushbutton
        button.appendLrfTag(LrfTag("PushButtonStart"))
        button.appendLrfTag(LrfTag("buttonactions"))
        button.appendLrfTag(LrfTag("jumpto",
            (self.textBlock.parent.objId, self.textBlock.objId)))
        button.append(LrfTag("endbuttonactions"))
        button.appendLrfTag(LrfTag("PushButtonEnd"))
        lrfWriter.append(button)

    def toElement(self, se):
        b = self.lrsObjectElement("Button")
        pb = SubElement(b, "PushButton")
        SubElement(pb, "JumpTo",
            refpage=unicode_type(self.textBlock.parent.objId),
            refobj=unicode_type(self.textBlock.objId))
        return b


class RuledLine(LrsContainer, LrsAttributes, LrsObject):
    """ A line.  Default is 500 pixels long, 2 pixels wide. """

    defaults = dict(
            linelength="500", linetype="solid", linewidth="2",
            linecolor="0x00000000")

    def __init__(self, **settings):
        LrsContainer.__init__(self, [])
        LrsAttributes.__init__(self, self.defaults, **settings)
        LrsObject.__init__(self)

    def toLrfContainer(self, lrfWriter, container):
        a = self.attrs
        container.appendLrfTag(LrfTag("RuledLine",
            (a["linelength"], a["linetype"], a["linewidth"], a["linecolor"])))

    def toElement(self, se):
        return Element("RuledLine", self.attrs)


class HeaderOrFooter(LrsObject, LrsContainer, LrsAttributes):
    """
        Creates empty header or footer objects.  Append PutObj objects to
        the header or footer to create the text.

        Note: it seems that adding multiple PutObjs to a header or footer
              only shows the last one.
    """
    defaults = dict(framemode="square", layout="LrTb", framewidth="0",
                framecolor="0x00000000", bgcolor="0xFF000000")

    def __init__(self, **settings):
        LrsObject.__init__(self)
        LrsContainer.__init__(self, [PutObj])
        LrsAttributes.__init__(self, self.defaults, **settings)

    def put_object(self, obj, x1, y1):
        self.append(PutObj(obj, x1, y1))

    def PutObj(self, *args, **kwargs):
        p = PutObj(*args, **kwargs)
        self.append(p)
        return p

    def toLrf(self, lrfWriter):
        hd = LrfObject(self.__class__.__name__, self.objId)
        hd.appendTagDict(self.attrs)

        stream = LrfTagStream(0)
        for content in self.contents:
            content.toLrfContainer(lrfWriter, stream)

        hd.appendLrfTags(stream.getStreamTags(lrfWriter.getSourceEncoding()))
        lrfWriter.append(hd)

    def toElement(self, se):
        name = self.__class__.__name__
        labelName = name.lower() + "label"
        hd = self.lrsObjectElement(name, objlabel=labelName)
        hd.attrib.update(self.attrs)

        for content in self.contents:
            hd.append(content.toElement(se))

        return hd


class Header(HeaderOrFooter):
    pass


class Footer(HeaderOrFooter):
    pass


class Canvas(LrsObject, LrsContainer, LrsAttributes):
    defaults = dict(framemode="square", layout="LrTb", framewidth="0",
                framecolor="0x00000000", bgcolor="0xFF000000",
                canvasheight=0, canvaswidth=0, blockrule='block-adjustable')

    def __init__(self, width, height, **settings):
        LrsObject.__init__(self)
        LrsContainer.__init__(self, [PutObj])
        LrsAttributes.__init__(self, self.defaults, **settings)

        self.settings = self.defaults.copy()
        self.settings.update(settings)
        self.settings['canvasheight'] = int(height)
        self.settings['canvaswidth']  = int(width)

    def put_object(self, obj, x1, y1):
        self.append(PutObj(obj, x1, y1))

    def toElement(self, source_encoding):
        el = self.lrsObjectElement("Canvas", **self.settings)
        for po in self.contents:
            el.append(po.toElement(source_encoding))
        return el

    def toLrf(self, lrfWriter):
        self.toLrfContainer(lrfWriter, lrfWriter)

    def toLrfContainer(self, lrfWriter, container):
        c = LrfObject("Canvas", self.objId)
        c.appendTagDict(self.settings)
        stream = LrfTagStream(STREAM_COMPRESSED)
        for content in self.contents:
            content.toLrfContainer(lrfWriter, stream)
        if lrfWriter.saveStreamTags:  # true only if testing
            c.saveStreamTags = stream.tags

        c.appendLrfTags(
                stream.getStreamTags(lrfWriter.getSourceEncoding(),
                    optimizeTags=lrfWriter.optimizeTags,
                    optimizeCompression=lrfWriter.optimizeCompression))
        container.addLrfObject(c.objId)
        lrfWriter.append(c)

    def has_text(self):
        return bool(self.contents)


class PutObj(LrsContainer):
    """ PutObj holds other objects that are drawn on a Canvas or Header. """

    def __init__(self, content, x1=0, y1=0):
        LrsContainer.__init__(self, [TextBlock, ImageBlock])
        self.content = content
        self.x1 = int(x1)
        self.y1 = int(y1)

    def setContent(self, content):
        self.content = content

    def appendReferencedObjects(self, parent):
        if self.content.parent is None:
            parent.append(self.content)

    def toLrfContainer(self, lrfWriter, container):
        container.appendLrfTag(LrfTag("PutObj", (self.x1, self.y1,
            self.content.objId)))

    def toElement(self, se):
        el = Element("PutObj", x1=unicode_type(self.x1), y1=unicode_type(self.y1),
                    refobj=unicode_type(self.content.objId))
        return el


class ImageStream(LrsObject, LrsContainer):
    """
        Embed an image file into an Lrf.
    """

    VALID_ENCODINGS = ["JPEG", "GIF", "BMP", "PNG"]

    def __init__(self, file=None, encoding=None, comment=None):
        LrsObject.__init__(self)
        LrsContainer.__init__(self, [])
        _checkExists(file)
        self.filename = file
        self.comment = comment
        # TODO: move encoding from extension to lrf module
        if encoding is None:
            extension = os.path.splitext(file)[1]
            if not extension:
                raise LrsError("file must have extension if encoding is not specified")
            extension = extension[1:].upper()

            if extension == "JPG":
                extension = "JPEG"

            encoding = extension
        else:
            encoding = encoding.upper()

        if encoding not in self.VALID_ENCODINGS:
            raise LrsError("encoding or file extension not JPEG, GIF, BMP, or PNG")

        self.encoding = encoding

    def toLrf(self, lrfWriter):
        with open(self.filename, "rb") as f:
            imageData = f.read()

        isObj = LrfObject("ImageStream", self.objId)
        if self.comment is not None:
            isObj.appendLrfTag(LrfTag("comment", self.comment))

        streamFlags = IMAGE_TYPE_ENCODING[self.encoding]
        stream = LrfStreamBase(streamFlags, imageData)
        isObj.appendLrfTags(stream.getStreamTags())
        lrfWriter.append(isObj)

    def toElement(self, se):
        element = self.lrsObjectElement("ImageStream",
                                objlabel="imagestreamlabel",
                                encoding=self.encoding, file=self.filename)
        element.text = self.comment
        return element


class Image(LrsObject, LrsContainer, LrsAttributes):

    defaults = dict()

    def __init__(self, refstream, x0=0, x1=0,
                 y0=0, y1=0, xsize=0, ysize=0, **settings):
        LrsObject.__init__(self)
        LrsContainer.__init__(self, [])
        LrsAttributes.__init__(self, self.defaults, settings)
        self.x0, self.y0, self.x1, self.y1 = int(x0), int(y0), int(x1), int(y1)
        self.xsize, self.ysize = int(xsize), int(ysize)
        self.setRefstream(refstream)

    def setRefstream(self, refstream):
        self.refstream = refstream

    def appendReferencedObjects(self, parent):
        if self.refstream.parent is None:
            parent.append(self.refstream)

    def getReferencedObjIds(self):
        return [self.objId, self.refstream.objId]

    def toElement(self, se):
        element = self.lrsObjectElement("Image", **self.attrs)
        element.set("refstream", unicode_type(self.refstream.objId))
        for name in ["x0", "y0", "x1", "y1", "xsize", "ysize"]:
            element.set(name, unicode_type(getattr(self, name)))
        return element

    def toLrf(self, lrfWriter):
        ib = LrfObject("Image", self.objId)
        ib.appendLrfTag(LrfTag("ImageRect",
            (self.x0, self.y0, self.x1, self.y1)))
        ib.appendLrfTag(LrfTag("ImageSize", (self.xsize, self.ysize)))
        ib.appendLrfTag(LrfTag("RefObjId", self.refstream.objId))
        lrfWriter.append(ib)


class ImageBlock(LrsObject, LrsContainer, LrsAttributes):
    """ Create an image on a page. """
    # TODO: allow other block attributes

    defaults = BlockStyle.baseDefaults.copy()

    def __init__(self, refstream, x0="0", y0="0", x1="600", y1="800",
                       xsize="600", ysize="800",
                       blockStyle=BlockStyle(blockrule='block-fixed'),
                       alttext=None, **settings):
        LrsObject.__init__(self)
        LrsContainer.__init__(self, [Text, Image])
        LrsAttributes.__init__(self, self.defaults, **settings)
        self.x0, self.y0, self.x1, self.y1 = int(x0), int(y0), int(x1), int(y1)
        self.xsize, self.ysize = int(xsize), int(ysize)
        self.setRefstream(refstream)
        self.blockStyle = blockStyle
        self.alttext = alttext

    def setRefstream(self, refstream):
        self.refstream = refstream

    def appendReferencedObjects(self, parent):
        if self.refstream.parent is None:
            parent.append(self.refstream)

        if self.blockStyle is not None and self.blockStyle.parent is None:
            parent.append(self.blockStyle)

    def getReferencedObjIds(self):
        objects =  [self.objId, self.extraId, self.refstream.objId]
        if self.blockStyle is not None:
            objects.append(self.blockStyle.objId)

        return objects

    def toLrf(self, lrfWriter):
        self.toLrfContainer(lrfWriter, lrfWriter)

    def toLrfContainer(self, lrfWriter, container):
        # id really belongs to the outer block

        extraId = LrsObject.getNextObjId()

        b = LrfObject("Block", self.objId)
        if self.blockStyle is not None:
            b.appendLrfTag(LrfTag("Link", self.blockStyle.objId))
        b.appendTagDict(self.attrs)

        b.appendLrfTags(
            LrfTagStream(0,
                [LrfTag("Link", extraId)]).getStreamTags(lrfWriter.getSourceEncoding()))
        container.addLrfObject(b.objId)
        lrfWriter.append(b)

        ib = LrfObject("Image", extraId)

        ib.appendLrfTag(LrfTag("ImageRect",
            (self.x0, self.y0, self.x1, self.y1)))
        ib.appendLrfTag(LrfTag("ImageSize", (self.xsize, self.ysize)))
        ib.appendLrfTag(LrfTag("RefObjId", self.refstream.objId))
        if self.alttext:
            ib.appendLrfTag("Comment", self.alttext)

        lrfWriter.append(ib)
        self.extraId = extraId

    def toElement(self, se):
        element = self.lrsObjectElement("ImageBlock", **self.attrs)
        element.set("refstream", unicode_type(self.refstream.objId))
        for name in ["x0", "y0", "x1", "y1", "xsize", "ysize"]:
            element.set(name, unicode_type(getattr(self, name)))
        element.text = self.alttext
        return element


class Font(LrsContainer):
    """ Allows a TrueType file to be embedded in an Lrf. """

    def __init__(self, file=None, fontname=None, fontfilename=None, encoding=None):
        LrsContainer.__init__(self, [])
        try:
            _checkExists(fontfilename)
            self.truefile = fontfilename
        except:
            try:
                _checkExists(file)
                self.truefile = file
            except:
                raise LrsError("neither '%s' nor '%s' exists"%(fontfilename, file))

        self.file = file
        self.fontname = fontname
        self.fontfilename = fontfilename
        self.encoding = encoding

    def toLrf(self, lrfWriter):
        font = LrfObject("Font", LrsObject.getNextObjId())
        lrfWriter.registerFontId(font.objId)
        font.appendLrfTag(LrfTag("FontFilename",
                                 lrfWriter.toUnicode(self.truefile)))
        font.appendLrfTag(LrfTag("FontFacename",
                                 lrfWriter.toUnicode(self.fontname)))

        stream = LrfFileStream(STREAM_FORCE_COMPRESSED, self.truefile)
        font.appendLrfTags(stream.getStreamTags())

        lrfWriter.append(font)

    def toElement(self, se):
        element = Element("RegistFont", encoding="TTF", fontname=self.fontname,
                file=self.file, fontfilename=self.file)
        return element
