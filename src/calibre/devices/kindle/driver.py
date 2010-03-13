# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Amazon's Kindle
'''
import datetime, os, re, sys
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
    DELETE_EXTS = ['.mbp','.tan','.pdr']
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
        MBP_FORMATS = [u'azw', u'mobi', u'prc', u'txt']
        mbp_formats = set(MBP_FORMATS)
        PDR_FORMATS = [u'pdf']
        pdr_formats = set(PDR_FORMATS)
        TAN_FORMATS = [u'tpz', u'azw1']
        tan_formats = set(TAN_FORMATS)

        def get_storage():
            storage = []
            if self._main_prefix:
                storage.append(os.path.join(self._main_prefix, self.EBOOK_DIR_MAIN))
            if self._card_a_prefix:
                storage.append(os.path.join(self._card_a_prefix, self.EBOOK_DIR_CARD_A))
            if self._card_b_prefix:
                storage.append(os.path.join(self._card_b_prefix, self.EBOOK_DIR_CARD_B))
            return storage

        def resolve_bookmark_paths(storage, path_map):
            pop_list = []
            book_ext = {}
            for id in path_map:
                file_fmts = set()
                for fmt in path_map[id]['fmts']:
                    file_fmts.add(fmt)
                bookmark_extension = None
                if file_fmts.intersection(mbp_formats):
                    book_extension = list(file_fmts.intersection(mbp_formats))[0]
                    bookmark_extension = 'mbp'
                elif file_fmts.intersection(tan_formats):
                    book_extension = list(file_fmts.intersection(tan_formats))[0]
                    bookmark_extension = 'tan'
                elif file_fmts.intersection(pdr_formats):
                    book_extension = list(file_fmts.intersection(pdr_formats))[0]
                    bookmark_extension = 'pdr'

                if bookmark_extension:
                    for vol in storage:
                        bkmk_path = path_map[id]['path'].replace(os.path.abspath('/<storage>'),vol)
                        bkmk_path = bkmk_path.replace('bookmark',bookmark_extension)
                        if os.path.exists(bkmk_path):
                            path_map[id] = bkmk_path
                            book_ext[id] = book_extension
                            break
                    else:
                        pop_list.append(id)
                else:
                    pop_list.append(id)

            # Remove non-existent bookmark templates
            for id in pop_list:
                path_map.pop(id)
            return path_map, book_ext

        def get_my_clippings(storage, bookmarked_books):
            # add an entry for 'My Clippings.txt'
            for vol in storage:
                mc_path = os.path.join(vol,'My Clippings.txt')
                if os.path.exists(mc_path):
                    return mc_path
            return None

        storage = get_storage()
        path_map, book_ext = resolve_bookmark_paths(storage, path_map)

        bookmarked_books = {}
        for id in path_map:
            bookmark_ext = path_map[id].rpartition('.')[2]
            myBookmark = Bookmark(path_map[id], id, book_ext[id], bookmark_ext)
            bookmarked_books[id] = self.UserAnnotation(type='kindle_bookmark', value=myBookmark)

        mc_path = get_my_clippings(storage, bookmarked_books)
        if mc_path:
            timestamp = datetime.datetime.utcfromtimestamp(os.path.getmtime(mc_path))
            bookmarked_books['clippings'] = self.UserAnnotation(type='kindle_clippings',
                                              value=dict(path=mc_path,timestamp=timestamp))

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
    def __init__(self, path, id, book_format, bookmark_extension):
        self.book_format = book_format
        self.bookmark_extension = bookmark_extension
        self.book_length = 0
        self.id = id
        self.last_read = 0
        self.last_read_location = 0
        self.path = path
        self.timestamp = 0
        self.user_notes = None

        self.get_bookmark_data()
        self.get_book_length()
        try:
            self.percent_read = float(100*self.last_read / self.book_length)
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

    def get_bookmark_data(self):
        ''' Return the timestamp and last_read_location '''
        from calibre.ebooks.metadata.mobi import StreamSlicer
        user_notes = {}
        if self.bookmark_extension == 'mbp':
            MAGIC_MOBI_CONSTANT = 150
            with open(self.path,'rb') as f:
                stream = StringIO(f.read())
                data = StreamSlicer(stream)
                self.timestamp, = unpack('>I', data[0x24:0x28])
                bpar_offset, = unpack('>I', data[0x4e:0x52])
                lrlo = bpar_offset + 0x0c
                self.last_read = int(unpack('>I', data[lrlo:lrlo+4])[0])
                self.last_read_location = self.last_read/MAGIC_MOBI_CONSTANT + 1
                entries, = unpack('>I', data[0x4a:0x4e])

                # Store the annotations/locations
                bpl = bpar_offset + 4
                bpar_len, = unpack('>I', data[bpl:bpl+4])
                bpar_len += 8
                #print "bpar_len: 0x%x" % bpar_len
                eo = bpar_offset + bpar_len

                # Walk bookmark entries
                #print " --- %s --- " % self.path
                current_entry = 1
                sig = data[eo:eo+4]
                previous_block = None

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
                        displayed_location = location/MAGIC_MOBI_CONSTANT + 1
                        user_notes[location] = dict(id=self.id,
                                                    displayed_location=displayed_location,
                                                    type=entry_type,
                                                    text=text)

                    eo += rec_len + 8
                    current_entry += 1
                    previous_block = current_block
                    sig = data[eo:eo+4]

                while sig == 'BKMK':
                    # Fix start location for Highlights using BKMK data
                    end_loc, = unpack('>I', data[eo+0x10:eo+0x14])

                    if end_loc in user_notes and \
                       (user_notes[end_loc]['type'] == 'Highlight' or \
                        user_notes[end_loc]['type'] == 'Note'):
                        # Switch location to start (0x08:0x0c)
                        start, = unpack('>I', data[eo+8:eo+12])
                        user_notes[start] = user_notes[end_loc]
                        '''
                        print " %s: swapping 0x%x (%d) to 0x%x (%d)" % (user_notes[end_loc]['type'],
                                                                    end_loc,
                                                                    end_loc/MAGIC_MOBI_CONSTANT + 1,
                                                                    start,
                                                                    start//MAGIC_MOBI_CONSTANT + 1)
                        '''
                        user_notes[start]['displayed_location'] = start/MAGIC_MOBI_CONSTANT + 1
                        user_notes.pop(end_loc)
                    else:
                        # If a bookmark coincides with a user annotation, the locs could
                        # be the same - cheat by nudging -1
                        # Skip bookmark for last_read_location
                        if end_loc != self.last_read:
                            # print " adding Bookmark at 0x%x (%d)" % (end_loc, end_loc/MAGIC_MOBI_CONSTANT + 1)
                            displayed_location = end_loc/MAGIC_MOBI_CONSTANT + 1
                            user_notes[end_loc - 1] = dict(id=self.id,
                                                           displayed_location=displayed_location,
                                                           type='Bookmark',
                                                           text=None)
                    rec_len, = unpack('>I', data[eo+4:eo+8])
                    eo += rec_len + 8
                    sig = data[eo:eo+4]

        elif self.bookmark_extension == 'tan':
            from calibre.ebooks.metadata.topaz import get_metadata as get_topaz_metadata

            def get_topaz_highlight(displayed_location):
                # Parse My Clippings.txt for a matching highlight
                # Search looks for book title match, highlight match, and location match
                # Author is not matched
                # This will find the first instance of a clipping only
                book_fs = self.path.replace('.%s' % self.bookmark_extension,'.%s' % self.book_format)
                with open(book_fs,'rb') as f2:
                    stream = StringIO(f2.read())
                    mi = get_topaz_metadata(stream)
                my_clippings = self.path
                split = my_clippings.find('documents') + len('documents/')
                my_clippings = my_clippings[:split] + "My Clippings.txt"
                try:
                    with open(my_clippings, 'r') as f2:
                        marker_found = 0
                        text = ''
                        search_str1 = '%s' % (mi.title)
                        search_str2 = '- Highlight Loc. %d' % (displayed_location)
                        for line in f2:
                            if marker_found == 0:
                                if line.startswith(search_str1):
                                    marker_found = 1
                            elif marker_found == 1:
                                if line.startswith(search_str2):
                                    marker_found = 2
                            elif marker_found == 2:
                                if line.startswith('=========='):
                                    break
                                text += line.strip()
                        else:
                            raise Exception('error')
                except:
                    text = '(Unable to extract highlight text from My Clippings.txt)'
                return text

            MAGIC_TOPAZ_CONSTANT = 33.33
            self.timestamp = os.path.getmtime(self.path)
            with open(self.path,'rb') as f:
                stream = StringIO(f.read())
                data = StreamSlicer(stream)
                self.last_read = int(unpack('>I', data[5:9])[0])
                self.last_read_location = self.last_read/MAGIC_TOPAZ_CONSTANT + 1
                entries, = unpack('>I', data[9:13])
                current_entry = 0
                e_base = 0x0d
                while current_entry < entries:
                    location, = unpack('>I', data[e_base+2:e_base+6])
                    text = None
                    text_len, = unpack('>I', data[e_base+0xA:e_base+0xE])
                    e_type, = unpack('>B', data[e_base+1])
                    if e_type == 0:
                        e_type = 'Bookmark'
                    elif e_type == 1:
                        e_type = 'Highlight'
                        text = get_topaz_highlight(location/MAGIC_TOPAZ_CONSTANT + 1)
                    elif e_type == 2:
                        e_type = 'Note'
                        text = data[e_base+0x10:e_base+0x10+text_len]
                    else:
                        e_type = 'Unknown annotation type'

                    displayed_location = location/MAGIC_TOPAZ_CONSTANT + 1
                    user_notes[location] = dict(id=self.id,
                                                displayed_location=displayed_location,
                                                type=e_type,
                                                text=text)
                    if text_len == 0xFFFFFFFF:
                        e_base = e_base + 14
                    else:
                        e_base = e_base + 14 + 2 + text_len
                    current_entry += 1
                for location in user_notes:
                    if location == self.last_read:
                        user_notes.pop(location)
                        break

        elif self.bookmark_extension == 'pdr':
            self.timestamp = os.path.getmtime(self.path)
            with open(self.path,'rb') as f:
                stream = StringIO(f.read())
                data = StreamSlicer(stream)
                self.last_read = int(unpack('>I', data[5:9])[0])
                entries, = unpack('>I', data[9:13])
                current_entry = 0
                e_base = 0x0d
                while current_entry < entries:
                    '''
                    location, = unpack('>I', data[e_base+2:e_base+6])
                    text = None
                    text_len, = unpack('>I', data[e_base+0xA:e_base+0xE])
                    e_type, = unpack('>B', data[e_base+1])
                    if e_type == 0:
                        e_type = 'Bookmark'
                    elif e_type == 1:
                        e_type = 'Highlight'
                        text = get_topaz_highlight(location/MAGIC_TOPAZ_CONSTANT + 1)
                    elif e_type == 2:
                        e_type = 'Note'
                        text = data[e_base+0x10:e_base+0x10+text_len]
                    else:
                        e_type = 'Unknown annotation type'

                    if self.book_format in ['tpz','azw1']:
                        displayed_location = location/MAGIC_TOPAZ_CONSTANT + 1
                    elif self.book_format == 'pdf':
                        # *** This needs implementation
                        displayed_location = location
                    user_notes[location] = dict(id=self.id,
                                                displayed_location=displayed_location,
                                                type=e_type,
                                                text=text)
                    if text_len == 0xFFFFFFFF:
                        e_base = e_base + 14
                    else:
                        e_base = e_base + 14 + 2 + text_len
                    current_entry += 1
                    '''
                    # Use label as page number
                    pdf_location, = unpack('>I', data[e_base+1:e_base+5])
                    label_len, = unpack('>H', data[e_base+5:e_base+7])
                    location = int(data[e_base+7:e_base+7+label_len])
                    displayed_location = location
                    e_type = 'Bookmark'
                    text = None
                    user_notes[location] = dict(id=self.id,
                                                displayed_location=displayed_location,
                                                type=e_type,
                                                text=text)
                    self.pdf_page_offset = pdf_location - location
                    e_base += (7 + label_len)
                    current_entry += 1

                self.last_read_location = self.last_read - self.pdf_page_offset

        else:
            print "unsupported bookmark_extension: %s" % self.bookmark_extension
        self.user_notes = user_notes

    def get_book_length(self):
        from calibre.ebooks.metadata.mobi import StreamSlicer
        book_fs = self.path.replace('.%s' % self.bookmark_extension,'.%s' % self.book_format)

        self.book_length = 0
        if self.bookmark_extension == 'mbp':
            # Read the book len from the header
            try:
                with open(book_fs,'rb') as f:
                    self.stream = StringIO(f.read())
                    self.data = StreamSlicer(self.stream)
                    self.nrecs, = unpack('>H', self.data[76:78])
                    record0 = self.record(0)
                    self.book_length = int(unpack('>I', record0[0x04:0x08])[0])
            except:
                pass
        elif self.bookmark_extension == 'tan':
            # Read bookLength from metadata
            from calibre.ebooks.metadata.topaz import MetadataUpdater
            try:
                with open(book_fs,'rb') as f:
                    mu = MetadataUpdater(f)
                    self.book_length = mu.book_length
            except:
                pass
        elif self.bookmark_extension == 'pdr':
            from calibre import plugins
            try:
                self.book_length = plugins['pdfreflow'][0].get_numpages(open(book_fs).read())
            except:
                pass

        else:
            print "unsupported bookmark_extension: %s" % self.bookmark_extension
