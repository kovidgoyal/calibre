# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for Amazon's Kindle
'''

import datetime, os, re, sys, json, hashlib

from calibre.devices.kindle.bookmark import Bookmark
from calibre.devices.usbms.driver import USBMS
from calibre import strftime, fsync

'''
Notes on collections:

A collections cache is stored at system/collections.json
The cache is read only, changes made to it are overwritten (it is regenerated)
on device disconnect

A log of collection creation/manipulation is available at
system/userannotationlog

collections.json refers to books via a SHA1 hash of the absolute path to the
book (prefix is /mnt/us on my Kindle). The SHA1 hash may or may not be prefixed
by some characters, use the last 40 characters. For books from Amazon, the ASIN
is used instead.

Changing the metadata and resending the file doesn't seem to affect collections

Adding a book to a collection on the Kindle does not change the book file at all
(i.e. it is binary identical). Therefore collection information is not stored in
file metadata.
'''

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
    DELETE_EXTS = ['.mbp', '.tan', '.pdr', '.ea', '.apnx', '.phl']
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

    def generate_annotation_html(self, bookmark):
        from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag, NavigableString
        # Returns <div class="user_annotations"> ... </div>
        last_read_location = bookmark.last_read_location
        timestamp = datetime.datetime.utcfromtimestamp(bookmark.timestamp)
        percent_read = bookmark.percent_read

        ka_soup = BeautifulSoup()
        dtc = 0
        divTag = Tag(ka_soup,'div')
        divTag['class'] = 'user_annotations'

        # Add the last-read location
        spanTag = Tag(ka_soup, 'span')
        spanTag['style'] = 'font-weight:bold'
        if bookmark.book_format == 'pdf':
            spanTag.insert(0,NavigableString(
                _("%(time)s<br />Last Page Read: %(loc)d (%(pr)d%%)") % \
                            dict(time=strftime(u'%x', timestamp.timetuple()),
                            loc=last_read_location,
                            pr=percent_read)))
        else:
            spanTag.insert(0,NavigableString(
                _("%(time)s<br />Last Page Read: Location %(loc)d (%(pr)d%%)") % \
                            dict(time=strftime(u'%x', timestamp.timetuple()),
                            loc=last_read_location,
                            pr=percent_read)))

        divTag.insert(dtc, spanTag)
        dtc += 1
        divTag.insert(dtc, Tag(ka_soup,'br'))
        dtc += 1

        if bookmark.user_notes:
            user_notes = bookmark.user_notes
            annotations = []

            # Add the annotations sorted by location
            # Italicize highlighted text
            for location in sorted(user_notes):
                if user_notes[location]['text']:
                    annotations.append(
                            _('<b>Location %(dl)d &bull; %(typ)s</b><br />%(text)s<br />') % \
                                        dict(dl=user_notes[location]['displayed_location'],
                                            typ=user_notes[location]['type'],
                                            text=(user_notes[location]['text'] if \
                                            user_notes[location]['type'] == 'Note' else \
                                            '<i>%s</i>' % user_notes[location]['text'])))
                else:
                    if bookmark.book_format == 'pdf':
                        annotations.append(
                                _('<b>Page %(dl)d &bull; %(typ)s</b><br />') % \
                                    dict(dl=user_notes[location]['displayed_location'],
                                        typ=user_notes[location]['type']))
                    else:
                        annotations.append(
                                _('<b>Location %(dl)d &bull; %(typ)s</b><br />') % \
                                    dict(dl=user_notes[location]['displayed_location'],
                                        typ=user_notes[location]['type']))

            for annotation in annotations:
                divTag.insert(dtc, annotation)
                dtc += 1

        ka_soup.insert(0,divTag)
        return ka_soup


    def add_annotation_to_library(self, db, db_id, annotation):
        from calibre.ebooks.BeautifulSoup import Tag
        from calibre.ebooks.metadata import MetaInformation

        bm = annotation
        ignore_tags = set(['Catalog', 'Clippings'])

        if bm.type == 'kindle_bookmark':
            mi = db.get_metadata(db_id, index_is_id=True)
            user_notes_soup = self.generate_annotation_html(bm.value)
            if mi.comments:
                a_offset = mi.comments.find('<div class="user_annotations">')
                ad_offset = mi.comments.find('<hr class="annotations_divider" />')

                if a_offset >= 0:
                    mi.comments = mi.comments[:a_offset]
                if ad_offset >= 0:
                    mi.comments = mi.comments[:ad_offset]
                if set(mi.tags).intersection(ignore_tags):
                    return
                if mi.comments:
                    hrTag = Tag(user_notes_soup,'hr')
                    hrTag['class'] = 'annotations_divider'
                    user_notes_soup.insert(0, hrTag)

                mi.comments += unicode(user_notes_soup.prettify())
            else:
                mi.comments = unicode(user_notes_soup.prettify())
            # Update library comments
            db.set_comment(db_id, mi.comments)

            # Add bookmark file to db_id
            db.add_format_with_hooks(db_id, bm.value.bookmark_extension,
                                            bm.value.path, index_is_id=True)
        elif bm.type == 'kindle_clippings':
            # Find 'My Clippings' author=Kindle in database, or add
            last_update = 'Last modified %s' % strftime(u'%x %X',bm.value['timestamp'].timetuple())
            mc_id = list(db.data.search_getting_ids('title:"My Clippings"', ''))
            if mc_id:
                db.add_format_with_hooks(mc_id[0], 'TXT', bm.value['path'],
                        index_is_id=True)
                mi = db.get_metadata(mc_id[0], index_is_id=True)
                mi.comments = last_update
                db.set_metadata(mc_id[0], mi)
            else:
                mi = MetaInformation('My Clippings', authors = ['Kindle'])
                mi.tags = ['Clippings']
                mi.comments = last_update
                db.add_books([bm.value['path']], ['txt'], [mi])

class KINDLE2(KINDLE):

    name           = 'Kindle 2/3/4/Touch/PaperWhite Device Interface'
    description    = _('Communicate with the Kindle 2/3/4/Touch/PaperWhite eBook reader.')

    FORMATS     = ['azw', 'mobi', 'azw3', 'prc', 'azw1', 'tpz', 'azw4', 'pobi', 'pdf', 'txt']
    DELETE_EXTS    = KINDLE.DELETE_EXTS + ['.mbp1', '.mbs', '.sdr', '.han']
    # On the Touch, there's also .asc files, but not using the same basename (for X-Ray & End Actions), azw3f & azw3r files, but all of them are in the .sdr sidecar folder

    PRODUCT_ID = [0x0002, 0x0004]
    BCD        = [0x0100]
    # SUPPORTS_SUB_DIRS = False # Apparently the Paperwhite doesn't like files placed in subdirectories
    # SUPPORTS_SUB_DIRS_FOR_SCAN = True

    EXTRA_CUSTOMIZATION_MESSAGE = [
        _('Send page number information when sending books') +
            ':::' +
            _('The Kindle 3 and newer versions can use page number information '
              'in MOBI files. With this option, calibre will calculate and send'
              ' this information to the Kindle when uploading MOBI files by'
              ' USB. Note that the page numbers do not correspond to any paper'
              ' book.'),
        _('Use slower but more accurate page number calculation') +
            ':::' +
            _('There are two ways to generate the page number information. Using the more accurate '
              'generator will produce pages that correspond better to a printed book. '
              'However, this method is slower and will slow down sending files '
              'to the Kindle.'),
        _('Custom column name to retrieve page counts from') +
            ':::' +
            _('If you have a custom column in your library that you use to '
              'store the page count of books, you can have calibre use that '
              'information, instead of calculating a page count. Specify the '
              'name of the custom column here, for example, #pages. '),

    ]
    EXTRA_CUSTOMIZATION_DEFAULT = [
        True,
        False,
        '',
    ]
    OPT_APNX           = 0
    OPT_APNX_ACCURATE  = 1
    OPT_APNX_CUST_COL  = 2
    # x330 on the PaperWhite
    THUMBNAIL_HEIGHT = 330
    # x262 on the Touch. Doesn't choke on x330, though.

    def formats_to_scan_for(self):
        ans = USBMS.formats_to_scan_for(self) | {'azw3'}
        return ans

    def books(self, oncard=None, end_session=True):
        bl = USBMS.books(self, oncard=oncard, end_session=end_session)
        # Read collections information
        collections = os.path.join(self._main_prefix, 'system', 'collections.json')
        if os.access(collections, os.R_OK):
            try:
                self.kindle_update_booklist(bl, collections)
            except:
                import traceback
                traceback.print_exc()
        return bl

    def kindle_update_booklist(self, bl, collections):
        with open(collections, 'rb') as f:
            collections = f.read()
        collections = json.loads(collections)
        path_map = {}
        for name, val in collections.items():
            col = name.split('@')[0]
            items = val.get('items', [])
            for x in items:
                x = x[-40:]
                if x not in path_map:
                    path_map[x] = set([])
                path_map[x].add(col)
        if path_map:
            for book in bl:
                path = '/mnt/us/'+book.lpath
                h = hashlib.sha1(path).hexdigest()
                if h in path_map:
                    book.device_collections = list(sorted(path_map[h]))

    # Detect if the product family needs .apnx files uploaded to sidecar folder
    def post_open_callback(self):
        product_id = self.device_being_opened[1]
        self.sidecar_apnx = False
        if product_id > 0x3:
            # Check if we need to put the apnx into a sidecar dir
            for _, dirnames, _ in os.walk(self._main_prefix):
                for x in dirnames:
                    if x.endswith('.sdr'):
                        self.sidecar_apnx = True
                        return

    def upload_cover(self, path, filename, metadata, filepath):
        '''
        Upload sidecar files: cover thumbnails and page count
        '''
        # Upload the cover thumbnail
        try:
            self.upload_kindle_thumbnail(metadata, filepath)
        except:
            import traceback
            traceback.print_exc()
        # Upload the apnx file
        self.upload_apnx(path, filename, metadata, filepath)

    def upload_kindle_thumbnail(self, metadata, filepath):
        from calibre.utils.logging import default_log
        coverdata = getattr(metadata, 'thumbnail', None)
        if not coverdata or not coverdata[2]:
            return
        thumb_dir = os.path.join(self._main_prefix, 'system', 'thumbnails')
        if not os.path.exists(thumb_dir): return

        from calibre.ebooks.mobi.reader.headers import MetadataHeader
        with lopen(filepath, 'rb') as f:
            mh = MetadataHeader(f, default_log)
        if mh.exth is None or not mh.exth.uuid or not mh.exth.cdetype:
            return
        thumbfile = os.path.join(thumb_dir,
                'thumbnail_{uuid}_{cdetype}_portrait.jpg'.format(
                    uuid=mh.exth.uuid, cdetype=mh.exth.cdetype))
        with open(thumbfile, 'wb') as f:
            f.write(coverdata[2])
            fsync(f)

    def upload_apnx(self, path, filename, metadata, filepath):
        from calibre.devices.kindle.apnx import APNXBuilder

        opts = self.settings()
        if not opts.extra_customization[self.OPT_APNX]:
            return

        if os.path.splitext(filepath.lower())[1] not in ('.azw', '.mobi',
                '.prc', '.azw3'):
            return

        # Create the sidecar folder if necessary
        if (self.sidecar_apnx):
            path = os.path.join(os.path.dirname(filepath), filename+".sdr")

            if not os.path.exists(path):
                os.makedirs(path)

        cust_col_name = opts.extra_customization[self.OPT_APNX_CUST_COL]
        custom_page_count = 0
        if cust_col_name:
            try:
                custom_page_count = int(metadata.get(cust_col_name, 0))
            except:
                pass

        apnx_path = '%s.apnx' % os.path.join(path, filename)
        apnx_builder = APNXBuilder()
        try:
            apnx_builder.write_apnx(filepath, apnx_path,
                                    accurate=opts.extra_customization[self.OPT_APNX_ACCURATE],
                                    page_count=custom_page_count)
        except:
            print 'Failed to generate APNX'
            import traceback
            traceback.print_exc()


class KINDLE_DX(KINDLE2):

    name           = 'Kindle DX Device Interface'
    description    = _('Communicate with the Kindle DX eBook reader.')

    FORMATS = ['azw', 'mobi', 'prc', 'azw1', 'tpz', 'azw4', 'pobi', 'pdf', 'txt']
    PRODUCT_ID = [0x0003]
    BCD        = [0x0100]

    def upload_kindle_thumbnail(self, metadata, filepath):
        pass

class KINDLE_FIRE(KINDLE2):

    name = 'Kindle Fire Device Interface'
    description = _('Communicate with the Kindle Fire')
    gui_name = 'Fire'
    FORMATS = ['azw3', 'azw', 'mobi', 'prc', 'azw1', 'tpz', 'azw4', 'pobi', 'pdf', 'txt']

    PRODUCT_ID = [0x0006]
    BCD = [0x216, 0x100]

    EBOOK_DIR_MAIN = 'Documents'
    SUPPORTS_SUB_DIRS = False
    SCAN_FROM_ROOT = True
    SUPPORTS_SUB_DIRS_FOR_SCAN = True
    VENDOR_NAME = 'AMAZON'
    WINDOWS_MAIN_MEM = 'KINDLE'

    def upload_kindle_thumbnail(self, metadata, filepath):
        pass

