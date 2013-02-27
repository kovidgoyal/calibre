# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Generic USB Mass storage device driver. This is not a complete stand alone
driver. It is intended to be subclassed with the relevant parts implemented
for a particular device.
'''

import os, time, json, shutil
from itertools import cycle

from calibre.constants import numeric_version
from calibre import prints, isbytestring
from calibre.constants import filesystem_encoding, DEBUG
from calibre.devices.usbms.cli import CLI
from calibre.devices.usbms.device import Device
from calibre.devices.usbms.books import BookList, Book
from calibre.ebooks.metadata.book.json_codec import JsonCodec
from calibre.utils.config import from_json, to_json
from calibre.utils.date import now, isoformat

BASE_TIME = None
def debug_print(*args):
    global BASE_TIME
    if BASE_TIME is None:
        BASE_TIME = time.time()
    if DEBUG:
        prints('DEBUG: %6.1f'%(time.time()-BASE_TIME), *args)

# CLI must come before Device as it implements the CLI functions that
# are inherited from the device interface in Device.
class USBMS(CLI, Device):
    '''
    The base class for all USBMS devices. Implements the logic for
    sending/getting/updating metadata/caching metadata/etc.
    '''

    description    = _('Communicate with an eBook reader.')
    author         = 'John Schember'
    supported_platforms = ['windows', 'osx', 'linux']

    # Store type instances of BookList and Book. We must do this because
    # a) we need to override these classes in some device drivers, and
    # b) the classmethods seem only to see real attributes declared in the
    #    class, not attributes stored in the class
    booklist_class = BookList
    book_class = Book

    FORMATS = []
    CAN_SET_METADATA = []
    METADATA_CACHE = 'metadata.calibre'
    DRIVEINFO = 'driveinfo.calibre'

    SCAN_FROM_ROOT = False

    def _update_driveinfo_record(self, dinfo, prefix, location_code, name=None):
        import uuid
        if not isinstance(dinfo, dict):
            dinfo = {}
        if dinfo.get('device_store_uuid', None) is None:
            dinfo['device_store_uuid'] = unicode(uuid.uuid4())
        if dinfo.get('device_name', None) is None:
            dinfo['device_name'] = self.get_gui_name()
        if name is not None:
            dinfo['device_name'] = name
        dinfo['location_code'] = location_code
        dinfo['last_library_uuid'] = getattr(self, 'current_library_uuid', None)
        dinfo['calibre_version'] = '.'.join([unicode(i) for i in numeric_version])
        dinfo['date_last_connected'] = isoformat(now())
        dinfo['prefix'] = prefix.replace('\\', '/')
        return dinfo

    def _update_driveinfo_file(self, prefix, location_code, name=None):
        if os.path.exists(os.path.join(prefix, self.DRIVEINFO)):
            with open(os.path.join(prefix, self.DRIVEINFO), 'rb') as f:
                try:
                    driveinfo = json.loads(f.read(), object_hook=from_json)
                except:
                    driveinfo = None
                driveinfo = self._update_driveinfo_record(driveinfo, prefix,
                                                          location_code, name)
            with open(os.path.join(prefix, self.DRIVEINFO), 'wb') as f:
                f.write(json.dumps(driveinfo, default=to_json))
        else:
            driveinfo = self._update_driveinfo_record({}, prefix, location_code, name)
            with open(os.path.join(prefix, self.DRIVEINFO), 'wb') as f:
                f.write(json.dumps(driveinfo, default=to_json))
        return driveinfo

    def get_device_information(self, end_session=True):
        self.report_progress(1.0, _('Get device information...'))
        self.driveinfo = {}
        if self._main_prefix is not None:
            try:
                self.driveinfo['main'] = self._update_driveinfo_file(self._main_prefix, 'main')
            except (IOError, OSError) as e:
                raise IOError(_('Failed to access files in the main memory of'
                        ' your device. You should contact the device'
                        ' manufacturer for support. Common fixes are:'
                        ' try a different USB cable/USB port on your computer.'
                        ' If you device has a "Reset to factory defaults" type'
                        ' of setting somewhere, use it. Underlying error: %s')
                        % e)
        try:
            if self._card_a_prefix is not None:
                self.driveinfo['A'] = self._update_driveinfo_file(self._card_a_prefix, 'A')
            if self._card_b_prefix is not None:
                self.driveinfo['B'] = self._update_driveinfo_file(self._card_b_prefix, 'B')
        except (IOError, OSError) as e:
            raise IOError(_('Failed to access files on the SD card in your'
                ' device. This can happen for many reasons. The SD card may be'
                ' corrupted, it may be too large for your device, it may be'
                ' write-protected, etc. Try a different SD card, or reformat'
                ' your SD card using the FAT32 filesystem. Also make sure'
                ' there are not too many files in the root of your SD card.'
                ' Underlying error: %s') % e)
        return (self.get_gui_name(), '', '', '', self.driveinfo)

    def set_driveinfo_name(self, location_code, name):
        if location_code == 'main':
            self._update_driveinfo_file(self._main_prefix, location_code, name)
        elif location_code == 'A':
            self._update_driveinfo_file(self._card_a_prefix, location_code, name)
        elif location_code == 'B':
            self._update_driveinfo_file(self._card_b_prefix, location_code, name)

    def formats_to_scan_for(self):
        return set(self.settings().format_map) | set(self.FORMATS)

    def books(self, oncard=None, end_session=True):
        from calibre.ebooks.metadata.meta import path_to_ext

        debug_print ('USBMS: Fetching list of books from device. Device=',
                     self.__class__.__name__,
                     'oncard=', oncard)

        dummy_bl = self.booklist_class(None, None, None)

        if oncard == 'carda' and not self._card_a_prefix:
            self.report_progress(1.0, _('Getting list of books on device...'))
            return dummy_bl
        elif oncard == 'cardb' and not self._card_b_prefix:
            self.report_progress(1.0, _('Getting list of books on device...'))
            return dummy_bl
        elif oncard and oncard != 'carda' and oncard != 'cardb':
            self.report_progress(1.0, _('Getting list of books on device...'))
            return dummy_bl

        prefix = self._card_a_prefix if oncard == 'carda' else \
                                     self._card_b_prefix if oncard == 'cardb' \
                                                         else self._main_prefix

        ebook_dirs = self.get_carda_ebook_dir() if oncard == 'carda' else \
            self.EBOOK_DIR_CARD_B if oncard == 'cardb' else \
            self.get_main_ebook_dir()

        debug_print ('USBMS: dirs are:', prefix, ebook_dirs)

        # get the metadata cache
        bl = self.booklist_class(oncard, prefix, self.settings)
        need_sync = self.parse_metadata_cache(bl, prefix, self.METADATA_CACHE)

        # make a dict cache of paths so the lookup in the loop below is faster.
        bl_cache = {}
        for idx, b in enumerate(bl):
            bl_cache[b.lpath] = idx

        all_formats = self.formats_to_scan_for()

        def update_booklist(filename, path, prefix):
            changed = False
            if path_to_ext(filename) in all_formats:
                try:
                    lpath = os.path.join(path, filename).partition(self.normalize_path(prefix))[2]
                    if lpath.startswith(os.sep):
                        lpath = lpath[len(os.sep):]
                    lpath = lpath.replace('\\', '/')
                    idx = bl_cache.get(lpath, None)
                    if idx is not None:
                        bl_cache[lpath] = None
                        if self.update_metadata_item(bl[idx]):
                            #print 'update_metadata_item returned true'
                            changed = True
                    else:
                        if bl.add_book(self.book_from_path(prefix, lpath),
                                              replace_metadata=False):
                            changed = True
                except: # Probably a filename encoding error
                    import traceback
                    traceback.print_exc()
            return changed
        if isinstance(ebook_dirs, basestring):
            ebook_dirs = [ebook_dirs]
        for ebook_dir in ebook_dirs:
            ebook_dir = self.path_to_unicode(ebook_dir)
            if self.SCAN_FROM_ROOT:
                ebook_dir = self.normalize_path(prefix)
            else:
                ebook_dir = self.normalize_path( \
                            os.path.join(prefix, *(ebook_dir.split('/'))) \
                                    if ebook_dir else prefix)
            debug_print('USBMS: scan from root', self.SCAN_FROM_ROOT, ebook_dir)
            if not os.path.exists(ebook_dir): continue
            # Get all books in the ebook_dir directory
            if self.SUPPORTS_SUB_DIRS or self.SUPPORTS_SUB_DIRS_FOR_SCAN:
                # build a list of files to check, so we can accurately report progress
                flist = []
                for path, dirs, files in os.walk(ebook_dir):
                    for filename in files:
                        if filename != self.METADATA_CACHE:
                            flist.append({'filename': self.path_to_unicode(filename),
                                          'path':self.path_to_unicode(path)})
                for i, f in enumerate(flist):
                    self.report_progress(i/float(len(flist)), _('Getting list of books on device...'))
                    changed = update_booklist(f['filename'], f['path'], prefix)
                    if changed:
                        need_sync = True
            else:
                paths = os.listdir(ebook_dir)
                for i, filename in enumerate(paths):
                    self.report_progress((i+1) / float(len(paths)), _('Getting list of books on device...'))
                    changed = update_booklist(self.path_to_unicode(filename), ebook_dir, prefix)
                    if changed:
                        need_sync = True

        # Remove books that are no longer in the filesystem. Cache contains
        # indices into the booklist if book not in filesystem, None otherwise
        # Do the operation in reverse order so indices remain valid
        for idx in sorted(bl_cache.itervalues(), reverse=True):
            if idx is not None:
                need_sync = True
                del bl[idx]

        debug_print('USBMS: count found in cache: %d, count of files in metadata: %d, need_sync: %s' % \
            (len(bl_cache), len(bl), need_sync))
        if need_sync: #self.count_found_in_bl != len(bl) or need_sync:
            if oncard == 'cardb':
                self.sync_booklists((None, None, bl))
            elif oncard == 'carda':
                self.sync_booklists((None, bl, None))
            else:
                self.sync_booklists((bl, None, None))

        self.report_progress(1.0, _('Getting list of books on device...'))
        debug_print('USBMS: Finished fetching list of books from device. oncard=', oncard)
        return bl

    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):
        debug_print('USBMS: uploading %d books'%(len(files)))

        path = self._sanity_check(on_card, files)

        paths = []
        names = iter(names)
        metadata = iter(metadata)

        for i, infile in enumerate(files):
            mdata, fname = metadata.next(), names.next()
            filepath = self.normalize_path(self.create_upload_path(path, mdata, fname))
            if not hasattr(infile, 'read'):
                infile = self.normalize_path(infile)
            filepath = self.put_file(infile, filepath, replace_file=True)
            paths.append(filepath)
            try:
                self.upload_cover(os.path.dirname(filepath),
                                  os.path.splitext(os.path.basename(filepath))[0],
                                  mdata, filepath)
            except: # Failure to upload cover is not catastrophic
                import traceback
                traceback.print_exc()

            self.report_progress((i+1) / float(len(files)), _('Transferring books to device...'))

        self.report_progress(1.0, _('Transferring books to device...'))
        debug_print('USBMS: finished uploading %d books'%(len(files)))
        return zip(paths, cycle([on_card]))

    def upload_cover(self, path, filename, metadata, filepath):
        '''
        Upload book cover to the device. Default implementation does nothing.

        :param path: The full path to the directory where the associated book is located.
        :param filename: The name of the book file without the extension.
        :param metadata: metadata belonging to the book. Use metadata.thumbnail
                         for cover
        :param filepath: The full path to the ebook file

        '''
        pass

    def add_books_to_metadata(self, locations, metadata, booklists):
        debug_print('USBMS: adding metadata for %d books'%(len(metadata)))

        metadata = iter(metadata)
        for i, location in enumerate(locations):
            self.report_progress((i+1) / float(len(locations)), _('Adding books to device metadata listing...'))
            info = metadata.next()
            blist = 2 if location[1] == 'cardb' else 1 if location[1] == 'carda' else 0

            # Extract the correct prefix from the pathname. To do this correctly,
            # we must ensure that both the prefix and the path are normalized
            # so that the comparison will work. Book's __init__ will fix up
            # lpath, so we don't need to worry about that here.
            path = self.normalize_path(location[0])
            if self._main_prefix:
                prefix = self._main_prefix if \
                           path.startswith(self.normalize_path(self._main_prefix)) else None
            if not prefix and self._card_a_prefix:
                prefix = self._card_a_prefix if \
                           path.startswith(self.normalize_path(self._card_a_prefix)) else None
            if not prefix and self._card_b_prefix:
                prefix = self._card_b_prefix if \
                           path.startswith(self.normalize_path(self._card_b_prefix)) else None
            if prefix is None:
                prints('in add_books_to_metadata. Prefix is None!', path,
                        self._main_prefix)
                continue
            lpath = path.partition(prefix)[2]
            if lpath.startswith('/') or lpath.startswith('\\'):
                lpath = lpath[1:]
            book = self.book_class(prefix, lpath, other=info)
            if book.size is None:
                book.size = os.stat(self.normalize_path(path)).st_size
            b = booklists[blist].add_book(book, replace_metadata=True)
            if b:
                b._new_book = True
        self.report_progress(1.0, _('Adding books to device metadata listing...'))
        debug_print('USBMS: finished adding metadata')

    def delete_books(self, paths, end_session=True):
        debug_print('USBMS: deleting %d books'%(len(paths)))
        for i, path in enumerate(paths):
            self.report_progress((i+1) / float(len(paths)), _('Removing books from device...'))
            path = self.normalize_path(path)
            if os.path.exists(path):
                # Delete the ebook
                os.unlink(path)

                filepath = os.path.splitext(path)[0]
                for ext in self.DELETE_EXTS:
                    for x in (filepath, path):
                        x += ext
                        if os.path.exists(x):
                            if os.path.isdir(x):
                                shutil.rmtree(x, ignore_errors=True)
                            else:
                                os.unlink(x)

                if self.SUPPORTS_SUB_DIRS:
                    try:
                        os.removedirs(os.path.dirname(path))
                    except:
                        pass
        self.report_progress(1.0, _('Removing books from device...'))
        debug_print('USBMS: finished deleting %d books'%(len(paths)))

    def remove_books_from_metadata(self, paths, booklists):
        debug_print('USBMS: removing metadata for %d books'%(len(paths)))

        for i, path in enumerate(paths):
            self.report_progress((i+1) / float(len(paths)), _('Removing books from device metadata listing...'))
            for bl in booklists:
                for book in bl:
                    if path.endswith(book.path):
                        bl.remove_book(book)
        self.report_progress(1.0, _('Removing books from device metadata listing...'))
        debug_print('USBMS: finished removing metadata for %d books'%(len(paths)))

    # If you override this method and you use book._new_book, then you must
    # complete the processing before you call this method. The flag is cleared
    # at the end just before the return
    def sync_booklists(self, booklists, end_session=True):
        debug_print('USBMS: starting sync_booklists')
        json_codec = JsonCodec()

        if not os.path.exists(self.normalize_path(self._main_prefix)):
            os.makedirs(self.normalize_path(self._main_prefix))

        def write_prefix(prefix, listid):
            if (prefix is not None and len(booklists) > listid and
                    isinstance(booklists[listid], self.booklist_class)):
                if not os.path.exists(prefix):
                    os.makedirs(self.normalize_path(prefix))
                with open(self.normalize_path(os.path.join(prefix, self.METADATA_CACHE)), 'wb') as f:
                    json_codec.encode_to_file(f, booklists[listid])
        write_prefix(self._main_prefix, 0)
        write_prefix(self._card_a_prefix, 1)
        write_prefix(self._card_b_prefix, 2)

        # Clear the _new_book indication, as we are supposed to be done with
        # adding books at this point
        for blist in booklists:
            if blist is not None:
                for book in blist:
                    book._new_book = False

        self.report_progress(1.0, _('Sending metadata to device...'))
        debug_print('USBMS: finished sync_booklists')

    @classmethod
    def build_template_regexp(cls):
        from calibre.devices.utils import build_template_regexp
        return build_template_regexp(cls.save_template())

    @classmethod
    def path_to_unicode(cls, path):
        if isbytestring(path):
            path = path.decode(filesystem_encoding)
        return path

    @classmethod
    def normalize_path(cls, path):
        'Return path with platform native path separators'
        if path is None:
            return None
        if os.sep == '\\':
            path = path.replace('/', '\\')
        else:
            path = path.replace('\\', '/')
        return cls.path_to_unicode(path)

    @classmethod
    def parse_metadata_cache(cls, bl, prefix, name):
        json_codec = JsonCodec()
        need_sync = False
        cache_file = cls.normalize_path(os.path.join(prefix, name))
        if os.access(cache_file, os.R_OK):
            try:
                with open(cache_file, 'rb') as f:
                    json_codec.decode_from_file(f, bl, cls.book_class, prefix)
            except:
                import traceback
                traceback.print_exc()
                bl = []
                need_sync = True
        else:
            need_sync = True
        return need_sync

    @classmethod
    def update_metadata_item(cls, book):
        changed = False
        size = os.stat(cls.normalize_path(book.path)).st_size
        if size != book.size:
            changed = True
            mi = cls.metadata_from_path(book.path)
            book.smart_update(mi)
            book.size = size
        return changed

    @classmethod
    def metadata_from_path(cls, path):
        return cls.metadata_from_formats([path])

    @classmethod
    def metadata_from_formats(cls, fmts):
        from calibre.ebooks.metadata.meta import metadata_from_formats
        from calibre.customize.ui import quick_metadata
        with quick_metadata:
            return metadata_from_formats(fmts, force_read_metadata=True,
                                         pattern=cls.build_template_regexp())

    @classmethod
    def book_from_path(cls, prefix, lpath):
        from calibre.ebooks.metadata.book.base import Metadata

        if cls.settings().read_metadata or cls.MUST_READ_METADATA:
            mi = cls.metadata_from_path(cls.normalize_path(os.path.join(prefix, lpath)))
        else:
            from calibre.ebooks.metadata.meta import metadata_from_filename
            mi = metadata_from_filename(cls.normalize_path(os.path.basename(lpath)),
                                        cls.build_template_regexp())
        if mi is None:
            mi = Metadata(os.path.splitext(os.path.basename(lpath))[0],
                    [_('Unknown')])
        size = os.stat(cls.normalize_path(os.path.join(prefix, lpath))).st_size
        book = cls.book_class(prefix, lpath, other=mi, size=size)
        return book
