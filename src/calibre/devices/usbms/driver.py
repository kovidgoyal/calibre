# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Generic USB Mass storage device driver. This is not a complete stand alone
driver. It is intended to be subclassed with the relevant parts implemented
for a particular device.
'''

import os
import re
import json
from itertools import cycle

from calibre import prints
from calibre.devices.usbms.cli import CLI
from calibre.devices.usbms.device import Device
from calibre.devices.usbms.books import BookList, Book

# CLI must come before Device as it implements the CLI functions that
# are inherited from the device interface in Device.
class USBMS(CLI, Device):

    description    = _('Communicate with an eBook reader.')
    author         = _('John Schember')
    supported_platforms = ['windows', 'osx', 'linux']

    # Store type instances of BookList and Book. We must do this because
    # a) we need to override these classes in some device drivers, and
    # b) the classmethods seem only to see real attributes declared in the
    #    class, not attributes stored in the class
    booklist_class = BookList
    book_class = Book

    FORMATS = []
    CAN_SET_METADATA = True
    METADATA_CACHE = 'metadata.calibre'

    def get_device_information(self, end_session=True):
        self.report_progress(1.0, _('Get device information...'))
        return (self.get_gui_name(), '', '', '')

    def books(self, oncard=None, end_session=True):
        from calibre.ebooks.metadata.meta import path_to_ext

        dummy_bl = BookList(None, None, None)

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

        ebook_dirs = self.EBOOK_DIR_CARD_A if oncard == 'carda' else \
            self.EBOOK_DIR_CARD_B if oncard == 'cardb' else \
            self.get_main_ebook_dir()

        # build a temporary list of books from the metadata cache
        bl, need_sync = self.parse_metadata_cache(prefix, self.METADATA_CACHE)
        # make a dict cache of paths so the lookup in the loop below is faster.
        bl_cache = {}
        for idx,b in enumerate(bl):
            bl_cache[b.lpath] = idx
        self.count_found_in_bl = 0

        # Make the real booklist that will be filled in below
        metadata = self.booklist_class(oncard, prefix, self.settings)

        def update_booklist(filename, path, prefix):
            changed = False
            if path_to_ext(filename) in self.FORMATS:
                try:
                    lpath = os.path.join(path, filename).partition(self.normalize_path(prefix))[2]
                    if lpath.startswith(os.sep):
                        lpath = lpath[len(os.sep):]
                    idx = bl_cache.get(lpath.replace('\\', '/'), None)
                    if idx is not None:
                        item, changed = self.update_metadata_item(bl[idx])
                        self.count_found_in_bl += 1
                    else:
                        item = self.book_from_path(prefix, lpath)
                        changed = True
                    if metadata.add_book(item, replace_metadata=False):
                        changed = True
                except: # Probably a filename encoding error
                    import traceback
                    traceback.print_exc()
            return changed

        if isinstance(ebook_dirs, basestring):
            ebook_dirs = [ebook_dirs]
        for ebook_dir in ebook_dirs:
            ebook_dir = self.normalize_path( \
                            os.path.join(prefix, *(ebook_dir.split('/'))) \
                                    if ebook_dir else prefix)
            if not os.path.exists(ebook_dir): continue
            # Get all books in the ebook_dir directory
            if self.SUPPORTS_SUB_DIRS:
                # build a list of files to check, so we can accurately report progress
                flist = []
                for path, dirs, files in os.walk(ebook_dir):
                    for filename in files:
                        if filename != self.METADATA_CACHE:
                            flist.append({'filename':filename, 'path': path})
                for i, f in enumerate(flist):
                    self.report_progress(i/float(len(flist)), _('Getting list of books on device...'))
                    changed = update_booklist(f['filename'], f['path'], prefix)
                    if changed:
                        need_sync = True
            else:
                paths = os.listdir(ebook_dir)
                for i, filename in enumerate(paths):
                    self.report_progress((i+1) / float(len(paths)), _('Getting list of books on device...'))
                    changed = update_booklist(filename, ebook_dir, prefix)
                    if changed:
                        need_sync = True

        # if count != len(bl) then there were items in it that we did not
        # find on the device. If need_sync is True then there were either items
        # on the device that were not in bl or some of the items were changed.

        #print "count found in cache: %d, count of files in cache: %d, need_sync: %s, must_sync_cache: %s" % \
        #    (self.count_found_in_bl, len(bl), need_sync,
        #     need_sync or self.count_found_in_bl != len(bl))
        if self.count_found_in_bl != len(bl) or need_sync:
            if oncard == 'cardb':
                self.sync_booklists((None, None, metadata))
            elif oncard == 'carda':
                self.sync_booklists((None, metadata, None))
            else:
                self.sync_booklists((metadata, None, None))

        self.report_progress(1.0, _('Getting list of books on device...'))
        return metadata

    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):
        path = self._sanity_check(on_card, files)

        paths = []
        names = iter(names)
        metadata = iter(metadata)

        for i, infile in enumerate(files):
            mdata, fname = metadata.next(), names.next()
            filepath = self.normalize_path(self.create_upload_path(path, mdata, fname))
            paths.append(filepath)
            if not hasattr(infile, 'read'):
                infile = self.normalize_path(infile)
            self.put_file(infile, filepath, replace_file=True)
            try:
                self.upload_cover(os.path.dirname(filepath),
                                  os.path.splitext(os.path.basename(filepath))[0], mdata)
            except: # Failure to upload cover is not catastrophic
                import traceback
                traceback.print_exc()

            self.report_progress((i+1) / float(len(files)), _('Transferring books to device...'))

        self.report_progress(1.0, _('Transferring books to device...'))
        return zip(paths, cycle([on_card]))

    def upload_cover(self, path, filename, metadata):
        '''
        :path: the full path were the associated book is located.
        :filename: the name of the book file without the extension.
        :metadata: metadata belonging to the book. Use metadata.thumbnail
        for cover
        '''
        pass

    def add_books_to_metadata(self, locations, metadata, booklists):
        metadata = iter(metadata)
        for i, location in enumerate(locations):
            self.report_progress((i+1) / float(len(locations)), _('Adding books to device metadata listing...'))
            info = metadata.next()
            path = location[0]
            blist = 2 if location[1] == 'cardb' else 1 if location[1] == 'carda' else 0

            if self._main_prefix:
                # Normalize path and prefix
                if self._main_prefix.find('\\') >= 0:
                    path = path.replace('/', '\\')
                else:
                    path = path.replace('\\', '/')
                prefix = self._main_prefix if path.startswith(self._main_prefix) else None
            if not prefix and self._card_a_prefix:
                prefix = self._card_a_prefix if path.startswith(self._card_a_prefix) else None
            if not prefix and self._card_b_prefix:
                prefix = self._card_b_prefix if path.startswith(self._card_b_prefix) else None
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
            booklists[blist].add_book(book, replace_metadata=True)
        self.report_progress(1.0, _('Adding books to device metadata listing...'))

    def delete_books(self, paths, end_session=True):
        for i, path in enumerate(paths):
            self.report_progress((i+1) / float(len(paths)), _('Removing books from device...'))
            path = self.normalize_path(path)
            if os.path.exists(path):
                # Delete the ebook
                os.unlink(path)

                filepath = os.path.splitext(path)[0]
                for ext in self.DELETE_EXTS:
                    if os.path.exists(filepath + ext):
                        os.unlink(filepath + ext)
                    if os.path.exists(path + ext):
                        os.unlink(path + ext)

                if self.SUPPORTS_SUB_DIRS:
                    try:
                        os.removedirs(os.path.dirname(path))
                    except:
                        pass
        self.report_progress(1.0, _('Removing books from device...'))

    def remove_books_from_metadata(self, paths, booklists):
        for i, path in enumerate(paths):
            self.report_progress((i+1) / float(len(paths)), _('Removing books from device metadata listing...'))
            for bl in booklists:
                for book in bl:
                    if path.endswith(book.path):
                        bl.remove_book(book)
        self.report_progress(1.0, _('Removing books from device metadata listing...'))

    def sync_booklists(self, booklists, end_session=True):
        if not os.path.exists(self.normalize_path(self._main_prefix)):
            os.makedirs(self.normalize_path(self._main_prefix))

        def write_prefix(prefix, listid):
            if prefix is not None and isinstance(booklists[listid], self.booklist_class):
                if not os.path.exists(prefix):
                    os.makedirs(self.normalize_path(prefix))
                js = [item.to_json() for item in booklists[listid] if
                        hasattr(item, 'to_json')]
                with open(self.normalize_path(os.path.join(prefix, self.METADATA_CACHE)), 'wb') as f:
                    json.dump(js, f, indent=2, encoding='utf-8')
        write_prefix(self._main_prefix, 0)
        write_prefix(self._card_a_prefix, 1)
        write_prefix(self._card_b_prefix, 2)

        self.report_progress(1.0, _('Sending metadata to device...'))

    @classmethod
    def normalize_path(cls, path):
        'Return path with platform native path separators'
        if path is None:
            return None
        if os.sep == '\\':
            path = path.replace('/', '\\')
        else:
            path = path.replace('\\', '/')
        return path

    @classmethod
    def parse_metadata_cache(cls, prefix, name):
        bl = []
        js = []
        need_sync = False
        try:
            with open(cls.normalize_path(os.path.join(prefix, name)), 'rb') as f:
                js = json.load(f, encoding='utf-8')
            for item in js:
                book = cls.book_class(prefix, item.get('lpath', None))
                for key in item.keys():
                    setattr(book, key, item[key])
                bl.append(book)
        except:
            import traceback
            traceback.print_exc()
            bl = []
            need_sync = True
        return bl, need_sync

    @classmethod
    def update_metadata_item(cls, item):
        changed = False
        size = os.stat(cls.normalize_path(item.path)).st_size
        if size != item.size:
            changed = True
            mi = cls.metadata_from_path(item.path)
            item.smart_update(mi)
            item.size = size
        return item, changed

    @classmethod
    def metadata_from_path(cls, path):
        return cls.metadata_from_formats([path])

    @classmethod
    def metadata_from_formats(cls, fmts):
        from calibre.ebooks.metadata.meta import metadata_from_formats
        from calibre.customize.ui import quick_metadata
        with quick_metadata:
            return metadata_from_formats(fmts)

    @classmethod
    def book_from_path(cls, prefix, path):
        from calibre.ebooks.metadata import MetaInformation

        if cls.settings().read_metadata or cls.MUST_READ_METADATA:
            mi = cls.metadata_from_path(cls.normalize_path(os.path.join(prefix, path)))
        else:
            from calibre.ebooks.metadata.meta import metadata_from_filename
            mi = metadata_from_filename(cls.normalize_path(os.path.basename(path)),
                re.compile(r'^(?P<title>[ \S]+?)[ _]-[ _](?P<author>[ \S]+?)_+\d+'))

        if mi is None:
            mi = MetaInformation(os.path.splitext(os.path.basename(path))[0],
                    [_('Unknown')])
        size = os.stat(cls.normalize_path(os.path.join(prefix, path))).st_size
        book = cls.book_class(prefix, path, other=mi, size=size)
        return book
