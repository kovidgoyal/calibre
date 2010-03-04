# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Amazon's Kindle
'''
import os, re, sys
from cStringIO import StringIO
from struct import unpack

from calibre.devices.usbms.driver import USBMS

class KINDLE(USBMS):

    name           = 'Kindle Device Interface'
    gui_name       = 'Amazon Kindle'
    icon           = I('devices/kindle.jpg')
    description    = _('Communicate with the Kindle eBook reader.')
    author         = 'John Schember'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['azw', 'mobi', 'prc', 'azw1', 'tpz', 'txt']

    VENDOR_ID   = [0x1949]
    PRODUCT_ID  = [0x0001]
    BCD         = [0x399]

    VENDOR_NAME = 'KINDLE'
    WINDOWS_MAIN_MEM = 'INTERNAL_STORAGE'
    WINDOWS_CARD_A_MEM = 'CARD_STORAGE'

    OSX_MAIN_MEM = 'Kindle Internal Storage Media'
    OSX_CARD_A_MEM = 'Kindle Card Storage Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'Kindle Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Kindle Storage Card'

    EBOOK_DIR_MAIN = 'documents'
    EBOOK_DIR_CARD_A = 'documents'
    DELETE_EXTS = ['.mbp']
    SUPPORTS_SUB_DIRS = True
    SUPPORTS_ANNOTATIONS = True

    WIRELESS_FILE_NAME_PATTERN = re.compile(
    r'(?P<title>[^-]+)-asin_(?P<asin>[a-zA-Z\d]{10,})-type_(?P<type>\w{4})-v_(?P<index>\d+).*')

    @classmethod
    def metadata_from_path(cls, path):
        mi = cls.metadata_from_formats([path])
        if mi.title == _('Unknown') or ('-asin' in mi.title and '-type' in mi.title):
            match = cls.WIRELESS_FILE_NAME_PATTERN.match(os.path.basename(path))
            if match is not None:
                mi.title = match.group('title')
                if not isinstance(mi.title, unicode):
                    mi.title = mi.title.decode(sys.getfilesystemencoding(),
                                               'replace')
        return mi

    def get_annotations(self, path_map):
        def get_storage():
            storage = []
            if self._main_prefix:
                storage.append(os.path.join(self._main_prefix, self.EBOOK_DIR_MAIN))
            if self._card_a_prefix:
                storage.append(os.path.join(self._card_a_prefix, self.EBOOK_DIR_CARD_A))
            if self._card_b_prefix:
                storage.append(os.path.join(self._card_b_prefix, self.EBOOK_DIR_CARD_B))
            return storage

        def resolve_mbp_paths(storage, path_map):
            pop_list = []
            for id in path_map:
                for vol in storage:
                    #print "path_map[id]: %s" % path_map[id]
                    mbp_path = path_map[id].replace(os.path.abspath('/<storage>'),vol)
                    #print "looking for mbp_path: %s" % mbp_path
                    if os.path.exists(mbp_path):
                        #print "mbp_path found"
                        path_map[id] = mbp_path
                        break
                else:
                    #print "mbp_path not found"
                    pop_list.append(id)

            # Remove non-existent mbp files
            for id in pop_list:
                path_map.pop(id)
            return path_map

        storage = get_storage()
        path_map = resolve_mbp_paths(storage, path_map)

        # path_map is now a mapping of valid mbp files
        # Not yet implemented - Topaz annotations
        bookmarked_books = {}
        MBP_FORMATS = ['azw', 'mobi', 'prc', 'txt']
        for id in path_map:
            myBookmark = Bookmark(path_map[id], MBP_FORMATS, id)
            bookmarked_books[id] = self.UserAnnotation(type='mobi', bookmark=myBookmark)

        # This returns as job.result in gui2.ui.annotations_fetched(self,job)
        return bookmarked_books


class KINDLE2(KINDLE):

    name           = 'Kindle 2 Device Interface'
    description    = _('Communicate with the Kindle 2 eBook reader.')

    FORMATS        = KINDLE.FORMATS + ['pdf']
    PRODUCT_ID = [0x0002]
    BCD        = [0x0100]


class KINDLE_DX(KINDLE2):

    name           = 'Kindle DX Device Interface'
    description    = _('Communicate with the Kindle DX eBook reader.')


    PRODUCT_ID = [0x0003]
    BCD        = [0x0100]

class Bookmark():
    '''
    A simple class fetching bookmark data
    Kindle-specific
    '''
    def __init__(self, path, formats, id):
        self.book_format = None
        self.book_length = 0
        self.id = id
        self.last_read_location = 0
        self.timestamp = 0
        self.user_notes = None

        self.get_bookmark_data(path)
        self.get_book_length(path, formats)
        try:
            self.percent_read = float(100*self.last_read_location / self.book_length)
        except:
            self.percent_read = 0

    def record(self, n):
        from calibre.ebooks.metadata.mobi import StreamSlicer
        if n >= self.nrecs:
            raise ValueError('non-existent record %r' % n)
        offoff = 78 + (8 * n)
        start, = unpack('>I', self.data[offoff + 0:offoff + 4])
        stop = None
        if n < (self.nrecs - 1):
            stop, = unpack('>I', self.data[offoff + 8:offoff + 12])
        return StreamSlicer(self.stream, start, stop)

    def get_bookmark_data(self, path, fetchUserNotes=True):
        ''' Return the timestamp and last_read_location '''
        from calibre.ebooks.metadata.mobi import StreamSlicer
        with open(path,'rb') as f:
            stream = StringIO(f.read())
            data = StreamSlicer(stream)
            self.timestamp, = unpack('>I', data[0x24:0x28])
            bpar_offset, = unpack('>I', data[0x4e:0x52])
            lrlo = bpar_offset + 0x0c
            self.last_read_location = int(unpack('>I', data[lrlo:lrlo+4])[0])
            entries, = unpack('>I', data[0x4a:0x4e])

            # Store the annotations/locations
            if fetchUserNotes:
                bpl = bpar_offset + 4
                bpar_len, = unpack('>I', data[bpl:bpl+4])
                bpar_len += 8
                #print "bpar_len: 0x%x" % bpar_len
                eo = bpar_offset + bpar_len

                # Walk bookmark entries
                #print " --- %s --- " % path
                #print "  last_read_location: %d" % self.magicKindleLocationCalculator(last_read_location)
                current_entry = 1
                sig = data[eo:eo+4]
                previous_block = None
                user_notes = {}

                while sig == 'DATA':
                    text = None
                    entry_type = None
                    rec_len, = unpack('>I', data[eo+4:eo+8])
                    if rec_len == 0:
                        current_block = "empty_data"
                    elif  data[eo+8:eo+12] == "EBAR":
                        current_block = "data_header"
                        #entry_type = "data_header"
                        location, = unpack('>I', data[eo+0x34:eo+0x38])
                        #print "data_header location: %d" % location
                    else:
                        current_block = "text_block"
                        if previous_block == 'empty_data':
                            entry_type = 'Note'
                        elif previous_block == 'data_header':
                            entry_type = 'Highlight'
                        text = data[eo+8:eo+8+rec_len].decode('utf-16-be')

                    if entry_type:
                        user_notes[location] = dict(type=entry_type, id=self.id,
                                                    text=text)
                        #print " %2d: %s %s" % (current_entry, entry_type,'at %d' % location if location else '')
                    #if current_block == 'text_block':
                        #self.textdump(text)

                    eo += rec_len + 8
                    current_entry += 1
                    previous_block = current_block
                    sig = data[eo:eo+4]

                while sig == 'BKMK':
                    # Fix start location for Highlights using BKMK data
                    end_loc, = unpack('>I', data[eo+0x10:eo+0x14])
                    if end_loc in user_notes and user_notes[end_loc]['type'] != 'Note':
                        start, = unpack('>I', data[eo+8:eo+12])
                        user_notes[start] = user_notes[end_loc]
                        user_notes.pop(end_loc)
                        #print "changing start location of %d to %d" % (end_loc,start)
                    else:
                        # If a bookmark coincides with a user annotation, the locs could
                        # be the same - cheat by nudging -1
                        # Skip bookmark for last_read_location
                        if end_loc != self.last_read_location:
                            user_notes[end_loc - 1] = dict(type='Bookmark',id=self.id,text=None)
                    rec_len, = unpack('>I', data[eo+4:eo+8])
                    eo += rec_len + 8
                    sig = data[eo:eo+4]

        '''
        for location in sorted(user_notes):
            print '  Location %d: %s\n%s' % self.magicKindleLocationCalculator(location),
                                                     user_notes[location]['type'],
                                    '\n'.join(self.textdump(user_notes[location]['text'])))
        '''
        self.user_notes = user_notes

    def get_book_length(self, path, formats):
        from calibre.ebooks.metadata.mobi import StreamSlicer
        # This assumes only one of the possible formats exists on the Kindle
        book_fs = None
        for format in formats:
            fmt = format.rpartition('.')[2]
            book_fs = path.replace('.mbp','.%s' % fmt)
            if os.path.exists(book_fs):
                self.book_format = fmt
                break
        else:
            #print "no files matching library formats exist on device"
            self.book_length = 0
            return

        # Read the book len from the header
        with open(book_fs,'rb') as f:
            self.stream = StringIO(f.read())
            self.data = StreamSlicer(self.stream)
            self.nrecs, = unpack('>H', self.data[76:78])
            record0 = self.record(0)
            self.book_length = int(unpack('>I', record0[0x04:0x08])[0])
