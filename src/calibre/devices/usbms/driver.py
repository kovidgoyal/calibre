__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
'''
Generic USB Mass storage device driver. This is not a complete stand alone
driver. It is intended to be subclassed with the relevant parts implemented
for a particular device.
'''

import os, fnmatch, shutil
from itertools import cycle

from calibre.devices.usbms.device import Device
from calibre.devices.usbms.books import BookList, Book
from calibre.devices.errors import FreeSpaceError

class USBMS(Device):
    EBOOK_DIR = ''
    MIME_MAP = {}

    def __init__(self, key='-1', log_packets=False, report_progress=None):
        pass
            
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
        
        # Get all books in all directories under the root EBOOK_DIR directory
        for path, dirs, files in os.walk(os.path.join(prefix, self.EBOOK_DIR)):
            # Filter out anything that isn't in the list of supported ebook types
            for book_type in self.MIME_MAP.keys():
                for filename in fnmatch.filter(files, '*.%s' % (book_type)):
                    title, author, mime = self.__class__.extract_book_metadata_by_filename(filename)
                    
                    bl.append(Book(os.path.join(path, filename), title, author, mime))
        return bl
    
    def upload_books(self, files, names, on_card=False, end_session=True):
        if on_card and not self._card_prefix:
            raise ValueError(_('The reader has no storage card connected.'))
            
        if not on_card:
            path = os.path.join(self._main_prefix, self.EBOOK_DIR)
        else:
            path = os.path.join(self._card_prefix, self.EBOOK_DIR)
            
        sizes = map(os.path.getsize, files)
        size = sum(sizes)
    
        if on_card and size > self.free_space()[2] - 1024*1024: 
            raise FreeSpaceError(_("There is insufficient free space on the storage card"))
        if not on_card and size > self.free_space()[0] - 2*1024*1024: 
            raise FreeSpaceError(_("There is insufficient free space in main memory"))

        paths = []
        names = iter(names)
        
        for infile in files:
            filepath = os.path.join(path, names.next())
            paths.append(filepath)
            
            shutil.copy2(infile, filepath)
    
        return zip(paths, cycle([on_card]))
    
    @classmethod
    def add_books_to_metadata(cls, locations, metadata, booklists):
        for location in locations:
            path = location[0]
            on_card = 1 if location[1] else 0
            
            title, author, mime = cls.extract_book_metadata_by_filename(os.path.basename(path))
            booklists[on_card].append(Book(path, title, author, mime))
    
    def delete_books(self, paths, end_session=True):
        for path in paths:
            if os.path.exists(path):
                # Delete the ebook
                os.unlink(path)
    
    @classmethod
    def remove_books_from_metadata(cls, paths, booklists):
        for path in paths:
            for bl in booklists:
                for book in bl:
                    if path.endswith(book.path):
                        bl.remove(book)
                        break
        
    def sync_booklists(self, booklists, end_session=True):
        # There is no meta data on the device to update. The device is treated
        # as a mass storage device and does not use a meta data xml file like
        # the Sony Readers.
        pass
    
    def get_file(self, path, outfile, end_session=True): 
        path = self.munge_path(path)
        src = open(path, 'rb')
        shutil.copyfileobj(src, outfile, 10*1024*1024)
    
    def munge_path(self, path):
        if path.startswith('/') and not (path.startswith(self._main_prefix) or \
            (self._card_prefix and path.startswith(self._card_prefix))):
            path = self._main_prefix + path[1:]
        elif path.startswith('card:'):
            path = path.replace('card:', self._card_prefix[:-1])
        return path

    @classmethod
    def extract_book_metadata_by_filename(cls, filename):
        book_title = ''
        book_author = ''
        book_mime = ''
        # Calibre uses a specific format for file names. They take the form
        # title_-_author_number.extention We want to see if the file name is
        # in this format.
        if fnmatch.fnmatchcase(filename, '*_-_*.*'):
            # Get the title and author from the file name
            title, sep, author = filename.rpartition('_-_')
            author, sep, ext = author.rpartition('_')
            book_title = title.replace('_', ' ')
            book_author = author.replace('_', ' ')
        # if the filename did not match just set the title to
        # the filename without the extension
        else:
            book_title = os.path.splitext(filename)[0].replace('_', ' ')
           
        fileext = os.path.splitext(filename)[1]
        if fileext in cls.MIME_MAP.keys():
            book_mime = cls.MIME_MAP[fileext]
            
        return book_title, book_author, book_mime

# ls, rm, cp, mkdir, touch, cat

