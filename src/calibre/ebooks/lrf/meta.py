__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

"""
This module presents an easy to use interface for getting and setting
meta information in LRF files.
Just create an L{LRFMetaFile} object and use its properties
to get and set meta information. For example:

>>> lrf = LRFMetaFile("mybook.lrf")
>>> print lrf.title, lrf.author
>>> lrf.category = "History"
"""

import struct, zlib, sys, os
from shutil import copyfileobj
from cStringIO import StringIO
import xml.dom.minidom as dom
from functools import wraps

from calibre.ebooks.metadata import MetaInformation, string_to_authors

BYTE      = "<B"  #: Unsigned char little endian encoded in 1 byte
WORD      = "<H"  #: Unsigned short little endian encoded in 2 bytes
DWORD     = "<I"  #: Unsigned integer little endian encoded in 4 bytes
QWORD     = "<Q"  #: Unsigned long long little endian encoded in 8 bytes


class field(object):
    """ A U{Descriptor<http://www.cafepy.com/article/python_attributes_and_methods/python_attributes_and_methods.html>}, that implements access
    to protocol packets in a human readable way.
    """

    def __init__(self, start=16, fmt=DWORD):
        """
        @param start: The byte at which this field is stored in the buffer
        @param fmt:   The packing format for this field.
        See U{struct<http://docs.python.org/lib/module-struct.html>}.
        """
        self._fmt, self._start = fmt, start

    def __get__(self, obj, typ=None):
        return obj.unpack(start=self._start, fmt=self._fmt)[0]

    def __set__(self, obj, val):
        obj.pack(val, start=self._start, fmt=self._fmt)

    def __repr__(self):
        typ = ""
        if self._fmt == DWORD:
            typ  = "unsigned int"
        if self._fmt == QWORD:
            typ = "unsigned long long"
        return "An " + typ + " stored in " + \
        str(struct.calcsize(self._fmt)) + \
        " bytes starting at byte " + str(self._start)


class versioned_field(field):

    def __init__(self, vfield, version, start=0, fmt=WORD):
        field.__init__(self, start=start, fmt=fmt)
        self.vfield, self.version = vfield, version

    def enabled(self):
        return self.vfield > self.version

    def __get__(self, obj, typ=None):
        if self.enabled():
            return field.__get__(self, obj, typ=typ)
        else:
            return None

    def __set__(self, obj, val):
        if not self.enabled():
            raise LRFException("Trying to set disabled field")
        else:
            field.__set__(self, obj, val)


class LRFException(Exception):
    pass


class fixed_stringfield(object):
    """ A field storing a variable length string. """

    def __init__(self, length=8, start=0):
        """
        @param length: Size of this string
        @param start: The byte at which this field is stored in the buffer
        """
        self._length = length
        self._start = start

    def __get__(self, obj, typ=None):
        length = str(self._length)
        return obj.unpack(start=self._start, fmt="<"+length+"s")[0]

    def __set__(self, obj, val):
        if val.__class__.__name__ != 'str':
            val = str(val)
        if len(val) != self._length:
            raise LRFException("Trying to set fixed_stringfield with a " +
                               "string of  incorrect length")
        obj.pack(val, start=self._start, fmt="<"+str(len(val))+"s")

    def __repr__(self):
        return "A string of length " + str(self._length) + \
                " starting at byte " + str(self._start)


class xml_attr_field(object):

    def __init__(self, tag_name, attr, parent='BookInfo'):
        self.tag_name = tag_name
        self.parent = parent
        self.attr= attr

    def __get__(self, obj, typ=None):
        """ Return the data in this field or '' if the field is empty """
        document = obj.info
        elems = document.getElementsByTagName(self.tag_name)
        if len(elems):
            elem = None
            for candidate in elems:
                if candidate.parentNode.nodeName == self.parent:
                    elem = candidate
            if elem and elem.hasAttribute(self.attr):
                return elem.getAttribute(self.attr)
        return ''

    def __set__(self, obj, val):
        if val is None:
            val = ""
        document = obj.info
        elems = document.getElementsByTagName(self.tag_name)
        if len(elems):
            elem = None
            for candidate in elems:
                if candidate.parentNode.nodeName == self.parent:
                    elem = candidate
        if elem:
            elem.setAttribute(self.attr, val)
        obj.info = document

    def __repr__(self):
        return "XML Attr Field: " + self.tag_name + " in " + self.parent

    def __str__(self):
        return self.tag_name+'.'+self.attr


class xml_field(object):
    """
    Descriptor that gets and sets XML based meta information from an LRF file.
    Works for simple XML fields of the form <tagname>data</tagname>
    """

    def __init__(self, tag_name, parent="BookInfo"):
        """
        @param tag_name: The XML tag whose data we operate on
        @param parent: The tagname of the parent element of C{tag_name}
        """
        self.tag_name = tag_name
        self.parent = parent

    def __get__(self, obj, typ=None):
        """ Return the data in this field or '' if the field is empty """
        document = obj.info

        elems = document.getElementsByTagName(self.tag_name)
        if len(elems):
            elem = None
            for candidate in elems:
                if candidate.parentNode.nodeName == self.parent:
                    elem = candidate
            if elem:
                elem.normalize()
                if elem.hasChildNodes():
                    return elem.firstChild.data.strip()
        return ''

    def __set__(self, obj, val):
        if not val:
            val = ''
        document = obj.info

        def create_elem():
            elem = document.createElement(self.tag_name)
            parent = document.getElementsByTagName(self.parent)[0]
            parent.appendChild(elem)
            return elem

        if not val:
            val = u''
        if type(val).__name__ != 'unicode':
            val = unicode(val, 'utf-8')

        elems = document.getElementsByTagName(self.tag_name)
        elem = None
        if len(elems):
            for candidate in elems:
                if candidate.parentNode.nodeName == self.parent:
                    elem = candidate
            if not elem:
                elem = create_elem()
            else:
                elem.normalize()
                while elem.hasChildNodes():
                    elem.removeChild(elem.lastChild)
        else:
            elem = create_elem()
        elem.appendChild(document.createTextNode(val))

        obj.info = document

    def __str__(self):
        return self.tag_name

    def __repr__(self):
        return "XML Field: " + self.tag_name + " in " + self.parent


def insert_into_file(fileobj, data, start, end):
    """
    Insert data into fileobj at position C{start}.

    This function inserts data into a file, overwriting all data between start
    and end. If end == start no data is overwritten. Do not use this function to
    append data to a file.

    @param fileobj: file like object
    @param data:    data to be inserted into fileobj
    @param start:   The position at which to start inserting data
    @param end:     The position in fileobj of data that must not be overwritten
    @return:        C{start + len(data) - end}
    """
    buffer = StringIO()
    fileobj.seek(end)
    copyfileobj(fileobj, buffer, -1)
    buffer.flush()
    buffer.seek(0)
    fileobj.seek(start)
    fileobj.write(data)
    fileobj.flush()
    fileobj.truncate()
    delta = fileobj.tell() - end  # < 0 if len(data) < end-start
    copyfileobj(buffer, fileobj, -1)
    fileobj.flush()
    buffer.close()
    return delta


def get_metadata(stream):
    """
    Return basic meta-data about the LRF file in C{stream} as a
    L{MetaInformation} object.
    @param stream: A file like object or an instance of L{LRFMetaFile}
    """
    lrf = stream if isinstance(stream, LRFMetaFile) else LRFMetaFile(stream)
    authors = string_to_authors(lrf.author)
    mi = MetaInformation(lrf.title.strip(), authors)
    mi.author = lrf.author.strip()
    mi.comments = lrf.free_text.strip()
    mi.category = lrf.category.strip()+', '+lrf.classification.strip()
    tags = [x.strip() for x in mi.category.split(',') if x.strip()]
    if tags:
        mi.tags = tags
    if mi.category.strip() == ',':
        mi.category = None
    mi.publisher = lrf.publisher.strip()
    mi.cover_data = lrf.get_cover()
    try:
        mi.title_sort = lrf.title_reading.strip()
        if not mi.title_sort:
            mi.title_sort = None
    except:
        pass
    try:
        mi.author_sort = lrf.author_reading.strip()
        if not mi.author_sort:
            mi.author_sort = None
    except:
        pass
    if not mi.title or 'unknown' in mi.title.lower():
        mi.title = None
    if not mi.authors:
        mi.authors = None
    if not mi.author or 'unknown' in mi.author.lower():
        mi.author = None
    if not mi.category or 'unknown' in mi.category.lower():
        mi.category = None
    if not mi.publisher or 'unknown' in mi.publisher.lower() or \
            'some publisher' in mi.publisher.lower():
        mi.publisher = None

    return mi


class LRFMetaFile(object):
    """ Has properties to read and write all Meta information in a LRF file. """
    #: The first 6 bytes of all valid LRF files
    LRF_HEADER = 'LRF'.encode('utf-16le')

    lrf_header               = fixed_stringfield(length=6, start=0x0)
    version                  = field(fmt=WORD, start=0x8)
    xor_key                  = field(fmt=WORD, start=0xa)
    root_object_id           = field(fmt=DWORD, start=0xc)
    number_of_objects        = field(fmt=QWORD, start=0x10)
    object_index_offset      = field(fmt=QWORD, start=0x18)
    binding                  = field(fmt=BYTE, start=0x24)
    dpi                      = field(fmt=WORD, start=0x26)
    width                    = field(fmt=WORD, start=0x2a)
    height                   = field(fmt=WORD, start=0x2c)
    color_depth              = field(fmt=BYTE, start=0x2e)
    toc_object_id            = field(fmt=DWORD, start=0x44)
    toc_object_offset        = field(fmt=DWORD, start=0x48)
    compressed_info_size     = field(fmt=WORD, start=0x4c)
    thumbnail_type           = versioned_field(version, 800, fmt=WORD, start=0x4e)
    thumbnail_size           = versioned_field(version, 800, fmt=DWORD, start=0x50)
    uncompressed_info_size   = versioned_field(compressed_info_size, 0,
                                             fmt=DWORD, start=0x54)

    title                 = xml_field("Title", parent="BookInfo")
    title_reading         = xml_attr_field("Title", 'reading', parent="BookInfo")
    author                = xml_field("Author", parent="BookInfo")
    author_reading        = xml_attr_field("Author", 'reading', parent="BookInfo")
    # 16 characters. First two chars should be FB for personal use ebooks.
    book_id               = xml_field("BookID", parent="BookInfo")
    publisher             = xml_field("Publisher", parent="BookInfo")
    label                 = xml_field("Label", parent="BookInfo")
    category              = xml_field("Category", parent="BookInfo")
    classification        = xml_field("Classification", parent="BookInfo")
    free_text             = xml_field("FreeText", parent="BookInfo")
    # Should use ISO 639 language codes
    language              = xml_field("Language", parent="DocInfo")
    creator               = xml_field("Creator", parent="DocInfo")
    # Format is %Y-%m-%d
    creation_date         = xml_field("CreationDate", parent="DocInfo")
    producer              = xml_field("Producer", parent="DocInfo")
    page                  = xml_field("SumPage", parent="DocInfo")

    def safe(func):
        """
        Decorator that ensures that function calls leave the pos
        in the underlying file unchanged
        """
        @wraps(func)
        def restore_pos(*args, **kwargs):
            obj = args[0]
            pos = obj._file.tell()
            res = func(*args, **kwargs)
            obj._file.seek(0, 2)
            if obj._file.tell() >= pos:
                obj._file.seek(pos)
            return res
        return restore_pos

    def safe_property(func):
        """
        Decorator that ensures that read or writing a property leaves
        the position in the underlying file unchanged
        """
        def decorator(f):
            def restore_pos(*args, **kwargs):
                obj = args[0]
                pos = obj._file.tell()
                res = f(*args, **kwargs)
                obj._file.seek(0, 2)
                if obj._file.tell() >= pos:
                    obj._file.seek(pos)
                return res
            return restore_pos
        locals_ = func()
        if locals_.has_key("fget"):  # noqa
            locals_["fget"] = decorator(locals_["fget"])
        if locals_.has_key("fset"):  # noqa
            locals_["fset"] = decorator(locals_["fset"])
        return property(**locals_)

    @safe_property
    def info():
        doc = \
        """
        Document meta information as a minidom Document object.
        To set use a minidom document object.
        """

        def fget(self):
            if self.compressed_info_size == 0:
                raise LRFException("This document has no meta info")
            size = self.compressed_info_size - 4
            self._file.seek(self.info_start)
            try:
                src =  zlib.decompress(self._file.read(size))
                if len(src) != self.uncompressed_info_size:
                    raise LRFException("Decompression of document meta info\
                                        yielded unexpected results")
                try:
                    return dom.parseString(src)
                except:
                    try:
                        return dom.parseString(src.replace('\x00', '').strip())
                    except:
                        src = src.replace('\x00', '').strip().decode('latin1')
                        return dom.parseString(src.encode('utf-8'))
            except zlib.error:
                raise LRFException("Unable to decompress document meta information")

        def fset(self, document):
            info = document.toxml('utf-8')
            self.uncompressed_info_size = len(info)
            stream = zlib.compress(info)
            orig_size = self.compressed_info_size
            self.compressed_info_size = len(stream) + 4
            delta = insert_into_file(self._file, stream, self.info_start,
                                     self.info_start + orig_size - 4)

            if self.toc_object_offset > 0:
                self.toc_object_offset   += delta
            self.object_index_offset += delta
            self.update_object_offsets(delta)

        return {"fget":fget, "fset":fset, "doc":doc}

    @safe_property
    def thumbnail_pos():
        doc = """ The position of the thumbnail in the LRF file """

        def fget(self):
            return self.info_start + self.compressed_info_size-4
        return {"fget":fget, "doc":doc}

    @classmethod
    def _detect_thumbnail_type(cls, slice):
        """ @param slice: The first 16 bytes of the thumbnail """
        ttype = 0x14  # GIF
        if "PNG" in slice:
            ttype = 0x12
        if "BM" in slice:
            ttype = 0x13
        if "JFIF" in slice:
            ttype = 0x11
        return ttype

    @safe_property
    def thumbnail():
        doc = \
        """
        The thumbnail.
        Represented as a string.
        The string you would get from the file read function.
        """

        def fget(self):
            size = self.thumbnail_size
            if size:
                self._file.seek(self.thumbnail_pos)
                return self._file.read(size)

        def fset(self, data):
            if self.version <= 800:
                raise LRFException("Cannot store thumbnails in LRF files \
                                    of version <= 800")
            slice = data[0:16]
            orig_size = self.thumbnail_size
            self.thumbnail_size = len(data)
            delta = insert_into_file(self._file, data, self.thumbnail_pos,
                                     self.thumbnail_pos + orig_size)
            self.toc_object_offset += delta
            self.object_index_offset += delta
            self.thumbnail_type = self._detect_thumbnail_type(slice)
            self.update_object_offsets(delta)

        return {"fget":fget, "fset":fset, "doc":doc}

    def __init__(self, file):
        """ @param file: A file object opened in the r+b mode """
        file.seek(0, 2)
        self.size = file.tell()
        self._file = file
        if self.lrf_header != LRFMetaFile.LRF_HEADER:
            raise LRFException(file.name +
                " has an invalid LRF header. Are you sure it is an LRF file?")
        # Byte at which the compressed meta information starts
        self.info_start = 0x58 if self.version > 800 else 0x53

    @safe
    def update_object_offsets(self, delta):
        """ Run through the LRF Object index changing the offset by C{delta}. """
        self._file.seek(self.object_index_offset)
        count = self.number_of_objects
        while count > 0:
            raw = self._file.read(8)
            new_offset = struct.unpack(DWORD, raw[4:8])[0] + delta
            if new_offset >= (2**8)**4 or new_offset < 0x4C:
                raise LRFException(_('Invalid LRF file. Could not set metadata.'))
            self._file.seek(-4, os.SEEK_CUR)
            self._file.write(struct.pack(DWORD, new_offset))
            self._file.seek(8, os.SEEK_CUR)
            count -= 1
        self._file.flush()

    @safe
    def unpack(self, fmt=DWORD, start=0):
        """
        Return decoded data from file.

        @param fmt: See U{struct<http://docs.python.org/lib/module-struct.html>}
        @param start: Position in file from which to decode
        """
        end = start + struct.calcsize(fmt)
        self._file.seek(start)
        ret =  struct.unpack(fmt, self._file.read(end-start))
        return ret

    @safe
    def pack(self, *args, **kwargs):
        """
        Encode C{args} and write them to file.
        C{kwargs} must contain the keywords C{fmt} and C{start}

        @param args: The values to pack
        @param fmt: See U{struct<http://docs.python.org/lib/module-struct.html>}
        @param start: Position in file at which to write encoded data
        """
        encoded = struct.pack(kwargs["fmt"], *args)
        self._file.seek(kwargs["start"])
        self._file.write(encoded)
        self._file.flush()

    def thumbail_extension(self):
        """
        Return the extension for the thumbnail image type as specified
        by L{self.thumbnail_type}. If the LRF file was created by buggy
        software, the extension maye be incorrect. See L{self.fix_thumbnail_type}.
        """
        ext = "gif"
        ttype = self.thumbnail_type
        if ttype == 0x11:
            ext = "jpeg"
        elif ttype == 0x12:
            ext = "png"
        elif ttype == 0x13:
            ext = "bmp"
        return ext

    def fix_thumbnail_type(self):
        """
        Attempt to guess the thumbnail image format and set
        L{self.thumbnail_type} accordingly.
        """
        slice = self.thumbnail[0:16]
        self.thumbnail_type = self._detect_thumbnail_type(slice)

    def seek(self, *args):
        """ See L{file.seek} """
        return self._file.seek(*args)

    def tell(self):
        """ See L{file.tell} """
        return self._file.tell()

    def read(self):
        """ See L{file.read} """
        return self._file.read()

    def write(self, val):
        """ See L{file.write} """
        self._file.write(val)

    def _objects(self):
        self._file.seek(self.object_index_offset)
        c = self.number_of_objects
        while c > 0:
            c -= 1
            raw = self._file.read(16)
            pos = self._file.tell()
            yield struct.unpack('<IIII', raw)[:3]
            self._file.seek(pos)

    def get_objects_by_type(self, type):
        from calibre.ebooks.lrf.tags import Tag
        objects = []
        for id, offset, size in self._objects():
            self._file.seek(offset)
            tag = Tag(self._file)
            if tag.id == 0xF500:
                obj_id, obj_type = struct.unpack("<IH", tag.contents)
                if obj_type == type:
                    objects.append((obj_id, offset, size))
        return objects

    def get_object_by_id(self, tid):
        from calibre.ebooks.lrf.tags import Tag
        for id, offset, size in self._objects():
            self._file.seek(offset)
            tag = Tag(self._file)
            if tag.id == 0xF500:
                obj_id, obj_type = struct.unpack("<IH", tag.contents)
                if obj_id == tid:
                    return obj_id, offset, size, obj_type
        return (False, False, False, False)

    @safe
    def get_cover(self):
        from calibre.ebooks.lrf.objects import get_object

        for id, offset, size in self.get_objects_by_type(0x0C):
            image = get_object(None, self._file, id, offset, size, self.xor_key)
            id, offset, size = self.get_object_by_id(image.refstream)[:3]
            image_stream = get_object(None, self._file, id, offset, size, self.xor_key)
            return image_stream.file.rpartition('.')[-1], image_stream.stream
        return None


def option_parser():
    from calibre.utils.config import OptionParser
    from calibre.constants import __appname__, __version__
    parser = OptionParser(usage=_('''%prog [options] mybook.lrf


Show/edit the metadata in an LRF file.\n\n'''),
      version=__appname__+' '+__version__,
      epilog='Created by Kovid Goyal')
    parser.add_option("-t", "--title", action="store", type="string",
                    dest="title", help=_("Set the book title"))
    parser.add_option('--title-sort', action='store', type='string', default=None,
                      dest='title_reading', help=_('Set sort key for the title'))
    parser.add_option("-a", "--author", action="store", type="string",
                    dest="author", help=_("Set the author"))
    parser.add_option('--author-sort', action='store', type='string', default=None,
                      dest='author_reading', help=_('Set sort key for the author'))
    parser.add_option("-c", "--category", action="store", type="string",
                    dest="category", help=_("The category this book belongs"
                    " to. E.g.: History"))
    parser.add_option("--thumbnail", action="store", type="string",
                    dest="thumbnail", help=_("Path to a graphic that will be"
                    " set as this files' thumbnail"))
    parser.add_option("--comment", action="store", type="string",
                    dest="comment", help=_("Path to a TXT file containing the "
                    "comment to be stored in the LRF file."))
    parser.add_option("--get-thumbnail", action="store_true",
                    dest="get_thumbnail", default=False,
                    help=_("Extract thumbnail from LRF file"))
    parser.add_option('--publisher', default=None, help=_('Set the publisher'))
    parser.add_option('--classification', default=None, help=_('Set the book classification'))
    parser.add_option('--creator', default=None, help=_('Set the book creator'))
    parser.add_option('--producer', default=None, help=_('Set the book producer'))
    parser.add_option('--get-cover', action='store_true', default=False,
                      help=_('Extract cover from LRF file. Note that the LRF format has no defined cover, so we use some heuristics to guess the cover.'))
    parser.add_option('--bookid', action='store', type='string', default=None,
                      dest='book_id', help=_('Set book ID'))
    # The SumPage element specifies the number of "View"s (visible pages for the BookSetting element conditions) of the content.
    # Basically, the total pages per the page size, font size, etc. when the
    # LRF is first created. Since this will change as the book is reflowed, it
    # is probably not worth using.
    # parser.add_option("-p", "--page", action="store", type="string", \
    #                dest="page", help=_("Don't know what this is for"))

    return parser


def set_metadata(stream, mi):
    lrf = LRFMetaFile(stream)
    if mi.title:
        lrf.title = mi.title
    if mi.authors:
        lrf.author = ', '.join(mi.authors)
    if mi.tags:
        lrf.category = mi.tags[0]
    if getattr(mi, 'category', False):
        lrf.category = mi.category
    if mi.comments:
        lrf.free_text = mi.comments
    if mi.author_sort:
        lrf.author_reading = mi.author_sort
    if mi.publisher:
        lrf.publisher = mi.publisher


def main(args=sys.argv):
    parser = option_parser()
    options, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        print
        print 'No lrf file specified'
        return 1
    lrf = LRFMetaFile(open(args[1], "r+b"))

    if options.title:
        lrf.title        = options.title
    if options.title_reading is not None:
        lrf.title_reading = options.title_reading
    if options.author_reading is not None:
        lrf.author_reading = options.author_reading
    if options.author:
        lrf.author    = options.author
    if options.publisher:
        lrf.publisher = options.publisher
    if options.classification:
        lrf.classification = options.classification
    if options.category:
        lrf.category = options.category
    if options.creator:
        lrf.creator = options.creator
    if options.producer:
        lrf.producer = options.producer
    if options.thumbnail:
        path = os.path.expanduser(os.path.expandvars(options.thumbnail))
        f = open(path, "rb")
        lrf.thumbnail = f.read()
        f.close()
    if options.book_id is not None:
        lrf.book_id = options.book_id
    if options.comment:
        path = os.path.expanduser(os.path.expandvars(options.comment))
        lrf.free_text = open(path).read()
    if options.get_thumbnail:
        t = lrf.thumbnail
        td = "None"
        if t and len(t) > 0:
            td = os.path.basename(args[1])+"_thumbnail."+lrf.thumbail_extension()
            f = open(td, "w")
            f.write(t)
            f.close()

    fields = LRFMetaFile.__dict__.items()
    fields.sort()
    for f in fields:
        if "XML" in str(f):
            print str(f[1]) + ":", lrf.__getattribute__(f[0]).encode('utf-8')
    if options.get_thumbnail:
        print "Thumbnail:", td
    if options.get_cover:
        try:
            ext, data = lrf.get_cover()
        except:  # Fails on books created by LRFCreator 1.0
            ext, data = None, None
        if data:
            cover = os.path.splitext(os.path.basename(args[1]))[0]+"_cover."+ext
            open(cover, 'wb').write(data)
            print 'Cover:', cover
        else:
            print 'Could not find cover in the LRF file'


if __name__ == '__main__':
    sys.exit(main())
