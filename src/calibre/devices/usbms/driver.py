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
import fnmatch
import re
from itertools import cycle

from calibre.ebooks.metadata import authors_to_string
from calibre.devices.usbms.cli import CLI
from calibre.devices.usbms.device import Device
from calibre.devices.usbms.books import BookList, Book
from calibre.devices.mime import mime_type_ext

# CLI must come before Device as it implements the CLI functions that
# are inherited from the device interface in Device.
class USBMS(CLI, Device):

    description    = _('Communicate with an eBook reader.')
    author         = _('John Schember')
    supported_platforms = ['windows', 'osx', 'linux']

    FORMATS = []
    CAN_SET_METADATA = False

    def get_device_information(self, end_session=True):
        self.report_progress(1.0, _('Get device information...'))
        return (self.get_gui_name(), '', '', '')

    def books(self, oncard=None, end_session=True):
        from calibre.ebooks.metadata.meta import path_to_ext
        bl = BookList()

        if oncard == 'carda' and not self._card_a_prefix:
            self.report_progress(1.0, _('Getting list of books on device...'))
            return bl
        elif oncard == 'cardb' and not self._card_b_prefix:
            self.report_progress(1.0, _('Getting list of books on device...'))
            return bl
        elif oncard and oncard != 'carda' and oncard != 'cardb':
            self.report_progress(1.0, _('Getting list of books on device...'))
            return bl

        prefix = self._card_a_prefix if oncard == 'carda' else self._card_b_prefix if oncard == 'cardb' else self._main_prefix
        ebook_dirs = self.EBOOK_DIR_CARD_A if oncard == 'carda' else \
            self.EBOOK_DIR_CARD_B if oncard == 'cardb' else \
            self.get_main_ebook_dir()

        if isinstance(ebook_dirs, basestring):
            ebook_dirs = [ebook_dirs]
        for ebook_dir in ebook_dirs:
            ebook_dir = os.path.join(prefix, *(ebook_dir.split('/'))) if ebook_dir else prefix
            if not os.path.exists(ebook_dir): continue
            # Get all books in the ebook_dir directory
            if self.SUPPORTS_SUB_DIRS:
                for path, dirs, files in os.walk(ebook_dir):
                    # Filter out anything that isn't in the list of supported ebook types
                    for book_type in self.FORMATS:
                        match = fnmatch.filter(files, '*.%s' % (book_type))
                        for i, filename in enumerate(match):
                            self.report_progress((i+1) / float(len(match)), _('Getting list of books on device...'))
                            try:
                                bl.append(self.__class__.book_from_path(os.path.join(path, filename)))
                            except: # Probably a filename encoding error
                                import traceback
                                traceback.print_exc()
                                continue
            else:
                paths = os.listdir(ebook_dir)
                for i, filename in enumerate(paths):
                    self.report_progress((i+1) / float(len(paths)), _('Getting list of books on device...'))
                    if path_to_ext(filename) in self.FORMATS:
                        try:
                            bl.append(self.__class__.book_from_path(os.path.join(ebook_dir, filename)))
                        except: # Probably a file name encoding error
                            import traceback
                            traceback.print_exc()
                            continue

        self.report_progress(1.0, _('Getting list of books on device...'))

        return bl

    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):

        path = self._sanity_check(on_card, files)

        paths = []
        names = iter(names)
        metadata = iter(metadata)

        for i, infile in enumerate(files):
            mdata, fname = metadata.next(), names.next()
            filepath = self.create_upload_path(path, mdata, fname)

            paths.append(filepath)

            self.put_file(infile, filepath, replace_file=True)
            try:
                self.upload_cover(os.path.dirname(filepath), os.path.splitext(os.path.basename(filepath))[0], mdata)
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
        for i, location in enumerate(locations):
            self.report_progress((i+1) / float(len(locations)), _('Adding books to device metadata listing...'))
            path = location[0]
            blist = 2 if location[1] == 'cardb' else 1 if location[1] == 'carda' else 0

            book = self.book_from_path(path)

            if not book in booklists[blist]:
                booklists[blist].append(book)
        self.report_progress(1.0, _('Adding books to device metadata listing...'))

    def delete_books(self, paths, end_session=True):
        for i, path in enumerate(paths):
            self.report_progress((i+1) / float(len(paths)), _('Removing books from device...'))
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
                        bl.remove(book)
        self.report_progress(1.0, _('Removing books from device metadata listing...'))

    def sync_booklists(self, booklists, end_session=True):
        # There is no meta data on the device to update. The device is treated
        # as a mass storage device and does not use a meta data xml file like
        # the Sony Readers.
        self.report_progress(1.0, _('Sending metadata to device...'))

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
    def book_from_path(cls, path):
        from calibre.ebooks.metadata.meta import path_to_ext
        from calibre.ebooks.metadata import MetaInformation
        mime = mime_type_ext(path_to_ext(path))

        if cls.settings().read_metadata or cls.MUST_READ_METADATA:
            mi = cls.metadata_from_path(path)
        else:
            from calibre.ebooks.metadata.meta import metadata_from_filename
            mi = metadata_from_filename(os.path.basename(path),
                re.compile(r'^(?P<title>[ \S]+?)[ _]-[ _](?P<author>[ \S]+?)_+\d+'))

        if mi is None:
            mi = MetaInformation(os.path.splitext(os.path.basename(path))[0],
                    [_('Unknown')])

        authors = authors_to_string(mi.authors)

        book = Book(path, mi.title, authors, mime)
        return book
