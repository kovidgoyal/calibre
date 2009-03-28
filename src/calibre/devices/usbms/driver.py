from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
'''
Generic USB Mass storage device driver. This is not a complete stand alone
driver. It is intended to be subclassed with the relevant parts implemented
for a particular device.
'''

import os, fnmatch, shutil
from itertools import cycle

from calibre.ebooks.metadata.meta import metadata_from_formats, path_to_ext
from calibre.ebooks.metadata import authors_to_string
from calibre.devices.usbms.device import Device
from calibre.devices.usbms.books import BookList, Book
from calibre.devices.errors import FreeSpaceError, PathError
from calibre.devices.mime import mime_type_ext

class File(object):
    def __init__(self, path):
        stats = os.stat(path)
        self.is_dir = os.path.isdir(path)
        self.is_readonly = not os.access(path, os.W_OK)
        self.ctime = stats.st_ctime
        self.wtime = stats.st_mtime
        self.size  = stats.st_size
        if path.endswith(os.sep):
            path = path[:-1]
        self.path = path
        self.name = os.path.basename(path)

class USBMS(Device):
    FORMATS = []
    EBOOK_DIR_MAIN = ''
    EBOOK_DIR_CARD = ''
    SUPPORTS_SUB_DIRS = False
    CAN_SET_METADATA = False

    def __init__(self, key='-1', log_packets=False, report_progress=None):
        Device.__init__(self, key=key, log_packets=log_packets,
                        report_progress=report_progress)

    def get_device_information(self, end_session=True):
        """
        Ask device for device information. See L{DeviceInfoQuery}.
        @return: (device name, device version, software version on device, mime type)
        """
        return (self.__class__.__name__, '', '', '')

    def books(self, oncard=False, end_session=True):
        bl = BookList()

        if oncard and self._card_prefix is None:
            return bl

        prefix = self._card_prefix if oncard else self._main_prefix
        ebook_dir = self.EBOOK_DIR_CARD if oncard else self.EBOOK_DIR_MAIN

        # Get all books in all directories under the root ebook_dir directory
        for path, dirs, files in os.walk(os.path.join(prefix, ebook_dir)):
            # Filter out anything that isn't in the list of supported ebook
            # types
            for book_type in self.FORMATS:
                for filename in fnmatch.filter(files, '*.%s' % (book_type)):
                    bl.append(self.__class__.book_from_path(os.path.join(path, filename)))
        return bl

    def upload_books(self, files, names, on_card=False, end_session=True,
                     metadata=None):
        if on_card and not self._card_prefix:
            raise ValueError(_('The reader has no storage card connected.'))

        if not on_card:
            path = os.path.join(self._main_prefix, self.EBOOK_DIR_MAIN)
        else:
            path = os.path.join(self._card_prefix, self.EBOOK_DIR_CARD)

        def get_size(obj):
            if hasattr(obj, 'seek'):
                obj.seek(0, os.SEEK_END)
                size = obj.tell()
                obj.seek(0)
                return size
            return os.path.getsize(obj)

        sizes = [get_size(f) for f in files]
        size = sum(sizes)

        if on_card and size > self.free_space()[2] - 1024*1024:
            raise FreeSpaceError(_("There is insufficient free space on the storage card"))
        if not on_card and size > self.free_space()[0] - 2*1024*1024:
            raise FreeSpaceError(_("There is insufficient free space in main memory"))

        paths = []
        names = iter(names)
        metadata = iter(metadata)

        for infile in files:
            newpath = path

            if self.SUPPORTS_SUB_DIRS:
                mdata = metadata.next()

                if 'tags' in mdata.keys():
                    for tag in mdata['tags']:
                        if tag.startswith(_('News')):
                            newpath = os.path.join(newpath, 'news')
                            newpath = os.path.join(newpath, mdata.get('title', ''))
                            newpath = os.path.join(newpath, mdata.get('timestamp', ''))
                            break
                        elif tag.startswith('/'):
                            newpath = path
                            newpath += tag
                            newpath = os.path.normpath(newpath)
                            break
                            
                if newpath == path:
                    newpath = os.path.join(newpath, authors_to_string(mdata.get('authors', '')))
                    newpath = os.path.join(newpath, mdata.get('title', ''))

            if not os.path.exists(newpath):
                os.makedirs(newpath)

            filepath = os.path.join(newpath, names.next())
            paths.append(filepath)

            if hasattr(infile, 'read'):
                infile.seek(0)

                dest = open(filepath, 'wb')
                shutil.copyfileobj(infile, dest, 10*1024*1024)

                dest.flush()
                dest.close()
            else:
                shutil.copy2(infile, filepath)

        return zip(paths, cycle([on_card]))

    @classmethod
    def add_books_to_metadata(cls, locations, metadata, booklists):
        for location in locations:
            path = location[0]
            on_card = 1 if location[1] else 0

            book = cls.book_from_path(path)

            if not book in booklists[on_card]:
                booklists[on_card].append(book)


    def delete_books(self, paths, end_session=True):
        for path in paths:
            if os.path.exists(path):
                # Delete the ebook
                os.unlink(path)
                if self.SUPPORTS_SUB_DIRS:
                    try:
                        os.removedirs(os.path.dirname(path))
                    except:
                        pass

    @classmethod
    def remove_books_from_metadata(cls, paths, booklists):
        for path in paths:
            for bl in booklists:
                for book in bl:
                    if path.endswith(book.path):
                        bl.remove(book)

    def sync_booklists(self, booklists, end_session=True):
        # There is no meta data on the device to update. The device is treated
        # as a mass storage device and does not use a meta data xml file like
        # the Sony Readers.
        pass

    def get_file(self, path, outfile, end_session=True):
        path = self.munge_path(path)
        with open(path, 'rb') as src:
            shutil.copyfileobj(src, outfile, 10*1024*1024)

    def put_file(self, infile, path, replace_file=False, end_session=True):
        path = self.munge_path(path)
        if os.path.isdir(path):
            path = os.path.join(path, infile.name)
        if not replace_file and os.path.exists(path):
            raise PathError('File already exists: ' + path)
        dest = open(path, 'wb')
        shutil.copyfileobj(infile, dest, 10*1024*1024)
        dest.flush()
        dest.close()

    def munge_path(self, path):
        if path.startswith('/') and not (path.startswith(self._main_prefix) or \
            (self._card_prefix and path.startswith(self._card_prefix))):
            path = self._main_prefix + path[1:]
        elif path.startswith('card:'):
            path = path.replace('card:', self._card_prefix[:-1])
        return path

    def list(self, path, recurse=False, end_session=True, munge=True):
        if munge:
            path = self.munge_path(path)
        if os.path.isfile(path):
            return [(os.path.dirname(path), [File(path)])]
        entries = [File(os.path.join(path, f)) for f in os.listdir(path)]
        dirs = [(path, entries)]
        for _file in entries:
            if recurse and _file.is_dir:
                dirs[len(dirs):] = self.list(_file.path, recurse=True, munge=False)
        return dirs

    def mkdir(self, path, end_session=True):
        if self.SUPPORTS_SUB_DIRS:
            path = self.munge_path(path)
            os.mkdir(path)

    def rm(self, path, end_session=True):
        path = self.munge_path(path)
        self.delete_books([path])

    def touch(self, path, end_session=True):
        path = self.munge_path(path)
        if not os.path.exists(path):
            open(path, 'w').close()
        if not os.path.isdir(path):
            os.utime(path, None)

    @classmethod
    def metadata_from_path(cls, path):
        return metadata_from_formats([path])
    
    @classmethod
    def book_from_path(cls, path):
        fileext = path_to_ext(path)
        mi = cls.metadata_from_path(path)
        mime = mime_type_ext(fileext)
        authors = authors_to_string(mi.authors)
        
        book = Book(path, mi.title, authors, mime)
        return book

