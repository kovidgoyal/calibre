__license__   = 'GPL v3'
__copyright__ = '2009, James Ralston <jralston at mindspring.com>'
'''
Device driver for Ectaco Jetbook firmware >= JL04_v030e
'''

import os, re, sys, shutil
from itertools import cycle

from calibre.devices.usbms.driver import USBMS
from calibre import sanitize_file_name as sanitize

class JETBOOK(USBMS):
    name           = 'Ectaco JetBook Device Interface'
    description    = _('Communicate with the JetBook eBook reader.')
    author         = _('James Ralston')
    supported_platforms = ['windows', 'osx', 'linux']


    # Ordered list of supported formats
    # Be sure these have an entry in calibre.devices.mime
    FORMATS     = ['epub', 'mobi', 'prc', 'txt', 'rtf', 'pdf']

    VENDOR_ID   = [0x0525]
    PRODUCT_ID  = [0xa4a5]
    BCD         = [0x314]

    VENDOR_NAME      = 'LINUX'
    WINDOWS_MAIN_MEM = 'EBOOK'
    WINDOWS_CARD_MEM = 'EBOOK'

    OSX_MAIN_MEM = None
    OSX_CARD_MEM = None

    MAIN_MEMORY_VOLUME_LABEL  = 'Jetbook Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Jetbook Storage Card'

    EBOOK_DIR_MAIN = "Books"
    EBOOK_DIR_CARD = "Books"
    SUPPORTS_SUB_DIRS = True

    JETBOOK_FILE_NAME_PATTERN = re.compile(
            r'(?P<authors>.+)#(?P<title>.+)'
            )

    def upload_books(self, files, names, on_card=False, end_session=True,
                    metadata=None):

        path = self._sanity_check(on_card, files)

        paths = []
        names = iter(names)
        metadata = iter(metadata)

        for i, infile in enumerate(files):
            newpath = path

            mdata = metadata.next()

            if 'tags' in mdata.keys():
                for tag in mdata['tags']:
                    if tag.startswith(_('News')):
                        newpath = os.path.join(newpath, 'news')
                        newpath = os.path.join(newpath, mdata.get('title', ''))
                        newpath = os.path.join(newpath, mdata.get('timestamp', ''))
                        break
                    elif tag.startswith('/'):
                        newpath += tag
                        newpath = os.path.normpath(newpath)
                        break

            author = sanitize(mdata.get('authors','Unknown')).replace(' ', '_')
            title = sanitize(mdata.get('title', 'Unknown')).replace(' ', '_')
            fileext = os.path.splitext(os.path.basename(names.next()))[1]
            fname = '%s#%s%s' % (author, title, fileext)

            if newpath == path:
                newpath = os.path.join(newpath, author, title)

            if not os.path.exists(newpath):
                os.makedirs(newpath)

            filepath = os.path.join(newpath, fname)
            paths.append(filepath)

            if hasattr(infile, 'read'):
                infile.seek(0)

                dest = open(filepath, 'wb')
                shutil.copyfileobj(infile, dest, 10*1024*1024)

                dest.flush()
                dest.close()
            else:
                shutil.copy2(infile, filepath)

            self.report_progress((i+1) / float(len(files)), _('Transferring books to device...'))

        self.report_progress(1.0, _('Transferring books to device...'))

        return zip(paths, cycle([on_card]))

    @classmethod
    def metadata_from_path(cls, path):

        def check_unicode(txt):
            txt = txt.replace('_', ' ')
            if not isinstance(txt, unicode):
                return txt.decode(sys.getfilesystemencoding(), 'replace')

            return txt

        mi = cls.metadata_from_formats([path])

        if (mi.title==_('Unknown') or mi.authors==[_('Unknown')]) \
                and '#' in mi.title:
            fn = os.path.splitext(os.path.basename(path))[0]
            match = cls.JETBOOK_FILE_NAME_PATTERN.match(fn)
            if match is not None:
                mi.title = check_unicode(match.group('title'))
                authors = match.group('authors').split('&')
                mi.authors = map(check_unicode, authors)

        return mi

    def windows_sort_drives(self, drives):
        main = drives.get('main', None)
        card = drives.get('carda', None)
        if card and main and card < main:
            drives['main'] = card
            drives['carda'] = main

        return drives



