__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.devices.kindle.apnx import APNXBuilder

'''
Device driver for Amazon's Kindle
'''

import datetime, os, re, json, hashlib, errno

from calibre.constants import DEBUG, filesystem_encoding
from calibre.devices.interface import OpenPopupMessage
from calibre.devices.kindle.bookmark import Bookmark
from calibre.devices.usbms.driver import USBMS
from calibre import strftime, fsync, prints
from polyglot.builtins import as_bytes, as_unicode

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


def get_files_in(path):
    if hasattr(os, 'scandir'):
        for dir_entry in os.scandir(path):
            if dir_entry.is_file(follow_symlinks=False):
                yield dir_entry.name, dir_entry.stat(follow_symlinks=False)
    else:
        import stat
        for x in os.listdir(path):
            xp = os.path.join(path, x)
            s = os.lstat(xp)
            if stat.S_ISREG(s.st_mode):
                yield x, s


class KINDLE(USBMS):

    name           = 'Kindle Device Interface'
    gui_name       = 'Amazon Kindle'
    icon           = 'devices/kindle.png'
    description    = _('Communicate with the Kindle e-book reader.')
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

    VIRTUAL_BOOK_EXTENSIONS = frozenset({'kfx'})
    VIRTUAL_BOOK_EXTENSION_MESSAGE = _(
        'The following books are in KFX format. KFX is a virtual book format, and cannot'
        ' be transferred from the device. Instead, you should go to your "Manage my'
        ' content and devices" page on the Amazon homepage and download the book to your computer from there.'
        ' That will give you a regular AZW3 file that you can add to calibre normally.'
        ' Click "Show details" to see the list of books.'
    )

    @classmethod
    def get_open_popup_message(cls):
        from calibre.utils.localization import localize_website_link
        return OpenPopupMessage(title=_('WARNING: E-book covers'), message=_(
            'Amazon has <b>broken display of covers</b> for books sent to the Kindle by USB cable. To workaround it,'
            ' you have to either keep your Kindle in Airplane mode, or:'
            '<ol><li>Send the books to the Kindle</li><li>Disconnect the Kindle and wait for the covers to be deleted'
            ' by Amazon</li><li>Reconnect the Kindle and calibre will restore the covers.</li></ol> After this the'
            ' covers for those books should stay put. <a href="{}">Click here</a> for details.').format(localize_website_link(
                'https://manual.calibre-ebook.com/faq.html#covers-for-books-i'
                '-send-to-my-e-ink-kindle-show-up-momentarily-and-then-are-replaced-by-a-generic-cover')
        ))

    def is_allowed_book_file(self, filename, path, prefix):
        lpath = os.path.join(path, filename).partition(self.normalize_path(prefix))[2].replace('\\', '/')
        return '.sdr/' not in lpath

    @classmethod
    def metadata_from_path(cls, path):
        if path.endswith('.kfx'):
            from calibre.ebooks.metadata.kfx import read_metadata_kfx
            try:
                kfx_path = path
                with lopen(kfx_path, 'rb') as f:
                    if f.read(8) != b'\xeaDRMION\xee':
                        f.seek(0)
                        mi = read_metadata_kfx(f)
                    else:
                        kfx_path = os.path.join(path.rpartition('.')[0] + '.sdr', 'assets', 'metadata.kfx')
                        with lopen(kfx_path, 'rb') as mf:
                            mi = read_metadata_kfx(mf)
            except Exception:
                import traceback
                traceback.print_exc()
                if DEBUG:
                    prints('failed kfx path:', kfx_path)
                mi = cls.metadata_from_formats([path])
        else:
            mi = cls.metadata_from_formats([path])
        if mi.title == _('Unknown') or ('-asin' in mi.title and '-type' in mi.title):
            path = as_unicode(path, filesystem_encoding, 'replace')
            match = cls.WIRELESS_FILE_NAME_PATTERN.match(os.path.basename(path))
            if match is not None:
                mi.title = match.group('title')
        return mi

    def get_annotations(self, path_map):
        MBP_FORMATS = ['azw', 'mobi', 'prc', 'txt']
        mbp_formats = set(MBP_FORMATS)
        PDR_FORMATS = ['pdf']
        pdr_formats = set(PDR_FORMATS)
        TAN_FORMATS = ['tpz', 'azw1']
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
        from calibre.ebooks.BeautifulSoup import BeautifulSoup
        # Returns <div class="user_annotations"> ... </div>
        last_read_location = bookmark.last_read_location
        timestamp = datetime.datetime.utcfromtimestamp(bookmark.timestamp)
        percent_read = bookmark.percent_read

        ka_soup = BeautifulSoup()
        dtc = 0
        divTag = ka_soup.new_tag('div')
        divTag['class'] = 'user_annotations'

        # Add the last-read location
        if bookmark.book_format == 'pdf':
            markup = _("%(time)s<br />Last page read: %(loc)d (%(pr)d%%)") % dict(
                    time=strftime('%x', timestamp.timetuple()),
                    loc=last_read_location,
                    pr=percent_read)
        else:
            markup = _("%(time)s<br />Last page read: Location %(loc)d (%(pr)d%%)") % dict(
                    time=strftime('%x', timestamp.timetuple()),
                    loc=last_read_location,
                    pr=percent_read)
        spanTag = BeautifulSoup('<span style="font-weight:bold">' + markup + '</span>').find('span')

        divTag.insert(dtc, spanTag)
        dtc += 1
        divTag.insert(dtc, ka_soup.new_tag('br'))
        dtc += 1

        if bookmark.user_notes:
            user_notes = bookmark.user_notes
            annotations = []

            # Add the annotations sorted by location
            # Italicize highlighted text
            for location in sorted(user_notes):
                if user_notes[location]['text']:
                    annotations.append(
                            _('<b>Location %(dl)d &bull; %(typ)s</b><br />%(text)s<br />') % dict(
                                dl=user_notes[location]['displayed_location'],
                                typ=user_notes[location]['type'],
                                text=(user_notes[location]['text'] if
                                      user_notes[location]['type'] == 'Note' else
                                      '<i>%s</i>' % user_notes[location]['text'])))
                else:
                    if bookmark.book_format == 'pdf':
                        annotations.append(
                                _('<b>Page %(dl)d &bull; %(typ)s</b><br />') % dict(
                                    dl=user_notes[location]['displayed_location'],
                                    typ=user_notes[location]['type']))
                    else:
                        annotations.append(
                                _('<b>Location %(dl)d &bull; %(typ)s</b><br />') % dict(
                                    dl=user_notes[location]['displayed_location'],
                                    typ=user_notes[location]['type']))

            for annotation in annotations:
                annot = BeautifulSoup('<span>' + annotation + '</span>').find('span')
                divTag.insert(dtc, annot)
                dtc += 1

        ka_soup.insert(0,divTag)
        return ka_soup

    def add_annotation_to_library(self, db, db_id, annotation):
        from calibre.ebooks.metadata import MetaInformation
        from calibre.ebooks.BeautifulSoup import prettify

        bm = annotation
        ignore_tags = {'Catalog', 'Clippings'}

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
                    hrTag = user_notes_soup.new_tag('hr')
                    hrTag['class'] = 'annotations_divider'
                    user_notes_soup.insert(0, hrTag)

                mi.comments += prettify(user_notes_soup)
            else:
                mi.comments = prettify(user_notes_soup)
            # Update library comments
            db.set_comment(db_id, mi.comments)

            # Add bookmark file to db_id
            db.add_format_with_hooks(db_id, bm.value.bookmark_extension,
                                            bm.value.path, index_is_id=True)
        elif bm.type == 'kindle_clippings':
            # Find 'My Clippings' author=Kindle in database, or add
            last_update = 'Last modified %s' % strftime('%x %X',bm.value['timestamp'].timetuple())
            mc_id = list(db.data.search_getting_ids('title:"My Clippings"', '', sort_results=False))
            if mc_id:
                db.add_format_with_hooks(mc_id[0], 'TXT', bm.value['path'],
                        index_is_id=True)
                mi = db.get_metadata(mc_id[0], index_is_id=True)
                mi.comments = last_update
                db.set_metadata(mc_id[0], mi)
            else:
                mi = MetaInformation('My Clippings', authors=['Kindle'])
                mi.tags = ['Clippings']
                mi.comments = last_update
                db.add_books([bm.value['path']], ['txt'], [mi])


class KINDLE2(KINDLE):

    name           = 'Kindle 2/3/4/Touch/PaperWhite/Voyage Device Interface'
    description    = _('Communicate with the Kindle 2/3/4/Touch/Paperwhite/Voyage e-book reader.')

    FORMATS     = ['azw', 'mobi', 'azw3', 'prc', 'azw1', 'tpz', 'azw4', 'kfx', 'pobi', 'pdf', 'txt']
    DELETE_EXTS    = KINDLE.DELETE_EXTS + ['.mbp1', '.mbs', '.sdr', '.han']
    # On the Touch, there's also .asc files, but not using the same basename
    # (for X-Ray & End Actions), azw3f & azw3r files, but all of them are in
    # the .sdr sidecar folder

    PRODUCT_ID = [0x0002, 0x0004, 0x0324]
    BCD        = [0x0100, 0x0310, 0x401, 0x409]
    # SUPPORTS_SUB_DIRS = False # Apparently the Paperwhite doesn't like files placed in subdirectories
    # SUPPORTS_SUB_DIRS_FOR_SCAN = True

    EXTRA_CUSTOMIZATION_MESSAGE = [
        _('Send page number information when sending books') + ':::' + _(
            'The Kindle 3 and newer versions can use page number information'
            ' in MOBI files. With this option, calibre will calculate and send'
            ' this information to the Kindle when uploading MOBI files by'
            ' USB. Note that the page numbers do not correspond to any paper'
            ' book.'),
        _('Page count calculation method') + ':::' + '<p>' + _(
            'There are multiple ways to generate the page number information.'
            ' If a page count is given then the book will be divided into that many pages.'
            ' Otherwise the number of pages will be approximated using one of the following'
            ' methods.<ul>'
            ' <li>fast: 2300 characters of uncompressed text per page.\n\n'
            ' <li>accurate: Based on the number of chapters, paragraphs, and visible lines in the book.'
            ' This method is designed to simulate an average paperback book where there are 32 lines per'
            ' page and a maximum of 70 characters per line.\n\n'
            ' <li>pagebreak: The "pagebreak" method uses the presence of <mbp:pagebreak> tags within'
            ' the book to determine pages.</ul>'
            'Methods other than "fast" are going to be much slower.'
            ' Further, if "pagebreak" fails to determine a page count accurate will be used, and if '
            ' "accurate" fails fast will be used.'),
        _('Custom column name to retrieve page counts from') + ':::' + _(
            'If you have a custom column in your library that you use to'
            ' store the page count of books, you can have calibre use that'
            ' information, instead of calculating a page count. Specify the'
            ' name of the custom column here, for example, #pages.'),
        _('Custom column name to retrieve calculation method from') + ':::' + _(
            'If you have a custom column in your library that you use to'
            ' store the preferred method for calculating the number of pages'
            ' for a book, you can have calibre use that method instead of the'
            ' default one selected above.  Specify the name of the custom'
            ' column here, for example, #pagemethod. The custom column should have the '
            ' values: fast, accurate or pagebreak.'),
        _('Overwrite existing APNX on device') + ':::' + _(
            'Uncheck this option to allow an APNX file existing on the device'
            ' to have priority over the version which calibre would send.'
            ' Since APNX files are usually deleted when a book is removed from'
            ' the Kindle, this is mostly useful when resending a book to the'
            ' device which is already on the device (e.g. after making a'
            ' modification).'),

    ]
    EXTRA_CUSTOMIZATION_DEFAULT = [
        True,
        'fast',
        '',
        '',
        True,
    ]
    OPT_APNX                 = 0
    OPT_APNX_METHOD          = 1
    OPT_APNX_CUST_COL        = 2
    OPT_APNX_METHOD_COL      = 3
    OPT_APNX_OVERWRITE       = 4
    EXTRA_CUSTOMIZATION_CHOICES = {OPT_APNX_METHOD: set(APNXBuilder.generators.keys())}

    # x330 on the PaperWhite
    # x262 on the Touch. Doesn't choke on x330, though.
    # x470 on the Voyage, checked that it works on PW, Touch checked by eschwartz.
    # x500 on the Oasis 2017. checked that it works on the PW3
    THUMBNAIL_HEIGHT         = 500

    @classmethod
    def migrate_extra_customization(cls, vals):
        if isinstance(vals[cls.OPT_APNX_METHOD], bool):
            # Previously this option used to be a bool
            vals[cls.OPT_APNX_METHOD] = 'accurate' if vals[cls.OPT_APNX_METHOD] else 'fast'
        return vals

    def formats_to_scan_for(self):
        ans = USBMS.formats_to_scan_for(self) | {'azw3', 'kfx'}
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
        with lopen(collections, 'rb') as f:
            collections = f.read()
        collections = json.loads(collections)
        path_map = {}
        for name, val in collections.items():
            col = name.split('@')[0]
            items = val.get('items', [])
            for x in items:
                x = x[-40:]
                if x not in path_map:
                    path_map[x] = set()
                path_map[x].add(col)
        if path_map:
            for book in bl:
                path = '/mnt/us/'+book.lpath
                h = hashlib.sha1(as_bytes(path)).hexdigest()
                if h in path_map:
                    book.device_collections = list(sorted(path_map[h]))

    def post_open_callback(self):
        try:
            self.sync_cover_thumbnails()
        except Exception:
            import traceback
            traceback.print_exc()

        # Detect if the product family needs .apnx files uploaded to sidecar folder
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

    def amazon_system_thumbnails_dir(self):
        return os.path.join(self._main_prefix, 'system', 'thumbnails')

    def thumbpath_from_filepath(self, filepath):
        from calibre.ebooks.metadata.kfx import (CONTAINER_MAGIC, read_book_key_kfx)
        from calibre.ebooks.mobi.reader.headers import MetadataHeader
        from calibre.utils.logging import default_log
        thumb_dir = self.amazon_system_thumbnails_dir()
        if not os.path.exists(thumb_dir):
            return
        with lopen(filepath, 'rb') as f:
            is_kfx = f.read(4) == CONTAINER_MAGIC
            f.seek(0)
            uuid = cdetype = None
            if is_kfx:
                uuid, cdetype = read_book_key_kfx(f)
            else:
                mh = MetadataHeader(f, default_log)
                if mh.exth is not None:
                    uuid = mh.exth.uuid
                    cdetype = mh.exth.cdetype
        if not uuid or not cdetype:
            return
        return os.path.join(thumb_dir,
                'thumbnail_{uuid}_{cdetype}_portrait.jpg'.format(
                    uuid=uuid, cdetype=cdetype))

    def amazon_cover_bug_cache_dir(self):
        # see https://www.mobileread.com/forums/showthread.php?t=329945
        return os.path.join(self._main_prefix, 'amazon-cover-bug')

    def upload_kindle_thumbnail(self, metadata, filepath):
        coverdata = getattr(metadata, 'thumbnail', None)
        if not coverdata or not coverdata[2]:
            return

        tp = self.thumbpath_from_filepath(filepath)
        if tp:
            with lopen(tp, 'wb') as f:
                f.write(coverdata[2])
                fsync(f)
            cache_dir = self.amazon_cover_bug_cache_dir()
            try:
                os.mkdir(cache_dir)
            except OSError:
                pass
            with lopen(os.path.join(cache_dir, os.path.basename(tp)), 'wb') as f:
                f.write(coverdata[2])
                fsync(f)

    def sync_cover_thumbnails(self):
        import shutil
        # See https://www.mobileread.com/forums/showthread.php?t=329945
        # for why this is needed
        if DEBUG:
            prints('Syncing cover thumbnails to workaround amazon cover bug')
        dest_dir = self.amazon_system_thumbnails_dir()
        src_dir = self.amazon_cover_bug_cache_dir()
        if not os.path.exists(dest_dir) or not os.path.exists(src_dir):
            return
        count = 0
        for name, src_stat_result in get_files_in(src_dir):
            dest_path = os.path.join(dest_dir, name)
            try:
                dest_stat_result = os.lstat(dest_path)
            except OSError:
                needs_sync = True
            else:
                needs_sync = src_stat_result.st_size != dest_stat_result.st_size
            if needs_sync:
                count += 1
                if DEBUG:
                    prints('Restoring cover thumbnail:', name)
                with lopen(os.path.join(src_dir, name), 'rb') as src, lopen(dest_path, 'wb') as dest:
                    shutil.copyfileobj(src, dest)
                    fsync(dest)
        if DEBUG:
            prints(f'Restored {count} cover thumbnails that were destroyed by Amazon')

    def delete_single_book(self, path):
        try:
            tp1 = self.thumbpath_from_filepath(path)
            if tp1:
                tp2 = os.path.join(self.amazon_cover_bug_cache_dir(), os.path.basename(tp1))
                for tp in (tp1, tp2):
                    try:
                        os.remove(tp)
                    except OSError as err:
                        if err.errno != errno.ENOENT:
                            prints(f'Failed to delete thumbnail for {path!r} at {tp!r} with error: {err}')
        except Exception:
            import traceback
            traceback.print_exc()
        USBMS.delete_single_book(self, path)

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
        # Check to see if there is an existing apnx file on Kindle we should keep.
        if opts.extra_customization[self.OPT_APNX_OVERWRITE] or not os.path.exists(apnx_path):
            try:
                method = opts.extra_customization[self.OPT_APNX_METHOD]
                cust_col_name = opts.extra_customization[self.OPT_APNX_METHOD_COL]
                if cust_col_name:
                    try:
                        temp = str(metadata.get(cust_col_name)).lower()
                        if temp in self.EXTRA_CUSTOMIZATION_CHOICES[self.OPT_APNX_METHOD]:
                            method = temp
                        else:
                            print("Invalid method choice for this book (%r), ignoring." % temp)
                    except:
                        print('Could not retrieve override method choice, using default.')
                apnx_builder.write_apnx(filepath, apnx_path, method=method, page_count=custom_page_count)
            except:
                print('Failed to generate APNX')
                import traceback
                traceback.print_exc()


class KINDLE_DX(KINDLE2):

    name           = 'Kindle DX Device Interface'
    description    = _('Communicate with the Kindle DX e-book reader.')

    FORMATS = ['azw', 'mobi', 'prc', 'azw1', 'tpz', 'azw4', 'pobi', 'pdf', 'txt']
    PRODUCT_ID = [0x0003]
    BCD        = [0x0100]

    def upload_kindle_thumbnail(self, metadata, filepath):
        pass

    def delete_single_book(self, path):
        USBMS.delete_single_book(self, path)


class KINDLE_FIRE(KINDLE2):

    name = 'Kindle Fire Device Interface'
    description = _('Communicate with the Kindle Fire')
    gui_name = 'Fire'
    FORMATS = ['azw3', 'azw', 'mobi', 'prc', 'azw1', 'tpz', 'azw4', 'kfx', 'pobi', 'pdf', 'txt']

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

    def delete_single_book(self, path):
        USBMS.delete_single_book(self, path)
