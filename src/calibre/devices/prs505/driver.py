__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Device driver for the SONY devices
'''

import os, time, re

from calibre.devices.usbms.driver import USBMS, debug_print
from calibre.devices.prs505 import MEDIA_XML, MEDIA_EXT, CACHE_XML, CACHE_EXT, \
            MEDIA_THUMBNAIL, CACHE_THUMBNAIL
from calibre.devices.prs505.sony_cache import XMLCache
from calibre import __appname__, prints
from calibre.devices.usbms.books import CollectionsBookList

class PRS505(USBMS):

    name           = 'SONY Device Interface'
    gui_name       = 'SONY Reader'
    description    = _('Communicate with Sony eBook readers older than the'
            ' PRST1.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']
    path_sep = '/'
    booklist_class = CollectionsBookList


    FORMATS      = ['epub', 'lrf', 'lrx', 'rtf', 'pdf', 'txt', 'zbf']
    CAN_SET_METADATA = ['title', 'authors', 'collections']
    CAN_DO_DEVICE_DB_PLUGBOARD = True

    VENDOR_ID    = [0x054c]   #: SONY Vendor Id
    PRODUCT_ID   = [0x031e]
    BCD          = [0x229, 0x1000, 0x22a, 0x31a]

    VENDOR_NAME        = 'SONY'
    WINDOWS_MAIN_MEM   = re.compile(
            r'(PRS-(505|500|300))|'
            r'(PRS-((700[#/])|((6|9|3)(0|5)0&)))'
            )
    WINDOWS_CARD_A_MEM = re.compile(
            r'(PRS-(505|500)[#/]\S+:MS)|'
            r'(PRS-((700[/#]\S+:)|((6|9)(0|5)0[#_]))MS)'
            )
    WINDOWS_CARD_B_MEM = re.compile(
            r'(PRS-(505|500)[#/]\S+:SD)|'
            r'(PRS-((700[/#]\S+:)|((6|9)(0|5)0[#_]))SD)'
            )


    MAIN_MEMORY_VOLUME_LABEL  = 'Sony Reader Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Sony Reader Storage Card'

    CARD_PATH_PREFIX          = __appname__

    SUPPORTS_SUB_DIRS = True
    MUST_READ_METADATA = True
    NUKE_COMMENTS = _('Comments have been removed as the SONY reader'
            ' chokes on them')
    SUPPORTS_USE_AUTHOR_SORT = True
    EBOOK_DIR_MAIN = 'database/media/books'
    SCAN_FROM_ROOT = False

    ALL_BY_TITLE  = _('All by title')
    ALL_BY_AUTHOR = _('All by author')

    EXTRA_CUSTOMIZATION_MESSAGE = [
        _('Comma separated list of metadata fields '
            'to turn into collections on the device. Possibilities include: ')+\
                    'series, tags, authors' +\
            _('. Two special collections are available: %(abt)s:%(abtv)s and %(aba)s:%(abav)s. Add  '
            'these values to the list to enable them. The collections will be '
            'given the name provided after the ":" character.')%dict(
                            abt='abt', abtv=ALL_BY_TITLE, aba='aba', abav=ALL_BY_AUTHOR),
            _('Upload separate cover thumbnails for books (newer readers)') +
            ':::'+_('Normally, the SONY readers get the cover image from the'
                ' ebook file itself. With this option, calibre will send a '
                'separate cover image to the reader, useful if you are '
                'sending DRMed books in which you cannot change the cover.'
                ' WARNING: This option should only be used with newer '
                'SONY readers: 350, 650, 950 and newer.'),
            _('Refresh separate covers when using automatic management (newer readers)') +
                ':::' +
                _('Set this option to have separate book covers uploaded '
                  'every time you connect your device. Unset this option if '
                  'you have so many books on the reader that performance is '
                  'unacceptable.'),
            _('Preserve cover aspect ratio when building thumbnails') +
                ':::' +
                _('Set this option if you want the cover thumbnails to have '
                  'the same aspect ratio (width to height) as the cover. '
                  'Unset it if you want the thumbnail to be the maximum size, '
                  'ignoring aspect ratio.'),
            _('Search for books in all folders') +
                ':::' +
                _('Setting this option tells calibre to look for books in all '
                  'folders on the device and its cards. This permits calibre to '
                  'find books put on the device by other software and by '
                  'wireless download.')
    ]
    EXTRA_CUSTOMIZATION_DEFAULT = [
                ', '.join(['series', 'tags']),
                False,
                False,
                True,
                True
    ]

    OPT_COLLECTIONS    = 0
    OPT_UPLOAD_COVERS  = 1
    OPT_REFRESH_COVERS = 2
    OPT_PRESERVE_ASPECT_RATIO = 3
    OPT_SCAN_FROM_ROOT = 4

    plugboard = None
    plugboard_func = None

    THUMBNAIL_HEIGHT = 217

    MAX_PATH_LEN = 201 # 250 - (max(len(CACHE_THUMBNAIL), len(MEDIA_THUMBNAIL)) +
                       # len('main_thumbnail.jpg') + 1)

    def windows_filter_pnp_id(self, pnp_id):
        return '_LAUNCHER' in pnp_id

    def post_open_callback(self):

        def write_cache(prefix):
            try:
                cachep = os.path.join(prefix, *(CACHE_XML.split('/')))
                if not os.path.exists(cachep):
                    dname = os.path.dirname(cachep)
                    if not os.path.exists(dname):
                        try:
                            os.makedirs(dname, mode=0777)
                        except:
                            time.sleep(5)
                            os.makedirs(dname, mode=0777)
                    with open(cachep, 'wb') as f:
                        f.write(u'''<?xml version="1.0" encoding="UTF-8"?>
                            <cache xmlns="http://www.kinoma.com/FskCache/1">
                            </cache>
                            '''.encode('utf8'))
                return True
            except:
                import traceback
                traceback.print_exc()
            return False

        # Make sure we don't have the launcher partition
        # as one of the cards

        if self._card_a_prefix is not None:
            if not write_cache(self._card_a_prefix):
                self._card_a_prefix = None
        if self._card_b_prefix is not None:
            if not write_cache(self._card_b_prefix):
                self._card_b_prefix = None
        self.booklist_class.rebuild_collections = self.rebuild_collections
        # Set the thumbnail width to the theoretical max if the user has asked
        # that we do not preserve aspect ratio
        if not self.settings().extra_customization[self.OPT_PRESERVE_ASPECT_RATIO]:
            self.THUMBNAIL_WIDTH = 168
        # Set WANTS_UPDATED_THUMBNAILS if the user has asked that thumbnails be
        # updated on every connect
        self.WANTS_UPDATED_THUMBNAILS = \
                self.settings().extra_customization[self.OPT_REFRESH_COVERS]
        self.SCAN_FROM_ROOT = self.settings().extra_customization[self.OPT_SCAN_FROM_ROOT]

    def filename_callback(self, fname, mi):
        if getattr(mi, 'application_id', None) is not None:
            base = fname.rpartition('.')[0]
            suffix = '_%s'%mi.application_id
            if not base.endswith(suffix):
                fname = base + suffix + '.' + fname.rpartition('.')[-1]
        return fname

    def initialize_XML_cache(self):
        paths, prefixes, ext_paths = {}, {}, {}
        for prefix, path, ext_path, source_id in [
                ('main', MEDIA_XML, MEDIA_EXT, 0),
                ('card_a', CACHE_XML, CACHE_EXT, 1),
                ('card_b', CACHE_XML, CACHE_EXT, 2)
                ]:
            prefix = getattr(self, '_%s_prefix'%prefix)
            if prefix is not None and os.path.exists(prefix):
                paths[source_id] = os.path.join(prefix, *(path.split('/')))
                ext_paths[source_id] = os.path.join(prefix, *(ext_path.split('/')))
                prefixes[source_id] = prefix
                d = os.path.dirname(paths[source_id])
                if not os.path.exists(d):
                    os.makedirs(d)
        return XMLCache(paths, ext_paths, prefixes, self.settings().use_author_sort)

    def books(self, oncard=None, end_session=True):
        debug_print('PRS505: starting fetching books for card', oncard)
        bl = USBMS.books(self, oncard=oncard, end_session=end_session)
        c = self.initialize_XML_cache()
        c.update_booklist(bl, {'carda':1, 'cardb':2}.get(oncard, 0))
        debug_print('PRS505: finished fetching books for card', oncard)
        return bl

    def sync_booklists(self, booklists, end_session=True):
        debug_print('PRS505: started sync_booklists')
        c = self.initialize_XML_cache()
        blists = {}
        for i in c.paths:
            try:
                if booklists[i] is not None:
                    blists[i] = booklists[i]
            except IndexError:
                pass
        opts = self.settings()
        if opts.extra_customization:
            collections = [x.strip() for x in
                    opts.extra_customization[self.OPT_COLLECTIONS].split(',')]
        else:
            collections = []
        debug_print('PRS505: collection fields:', collections)
        pb = None
        if self.plugboard_func:
            pb = self.plugboard_func(self.__class__.__name__,
                                     'device_db', self.plugboards)
        debug_print('PRS505: use plugboards', pb)
        c.update(blists, collections, pb)
        c.write()

        if opts.extra_customization[self.OPT_REFRESH_COVERS]:
            debug_print('PRS505: uploading covers in sync_booklists')
            for idx,bl in blists.items():
                prefix = self._card_a_prefix if idx == 1 else \
                                self._card_b_prefix if idx == 2 \
                                    else self._main_prefix
                for book in bl:
                    try:
                        p = os.path.join(prefix, book.lpath)
                        self._upload_cover(os.path.dirname(p),
                                          os.path.splitext(os.path.basename(p))[0],
                                          book, p)
                    except:
                        debug_print('FAILED to upload cover',
                                prefix, book.lpath)
        else:
            debug_print('PRS505: NOT uploading covers in sync_booklists')

        USBMS.sync_booklists(self, booklists, end_session=end_session)
        debug_print('PRS505: finished sync_booklists')

    def rebuild_collections(self, booklist, oncard):
        debug_print('PRS505: started rebuild_collections on card', oncard)
        c = self.initialize_XML_cache()
        c.rebuild_collections(booklist, {'carda':1, 'cardb':2}.get(oncard, 0))
        c.write()
        debug_print('PRS505: finished rebuild_collections')

    def set_plugboards(self, plugboards, pb_func):
        self.plugboards = plugboards
        self.plugboard_func = pb_func

    def upload_cover(self, path, filename, metadata, filepath):
        opts = self.settings()
        if not opts.extra_customization[self.OPT_UPLOAD_COVERS]:
            # Building thumbnails disabled
            debug_print('PRS505: not uploading cover')
            return
        debug_print('PRS505: uploading cover')
        try:
            self._upload_cover(path, filename, metadata, filepath)
        except:
            debug_print('FAILED to upload cover', filepath)

    def _upload_cover(self, path, filename, metadata, filepath):
        if metadata.thumbnail and metadata.thumbnail[-1]:
            path = path.replace('/', os.sep)
            is_main = path.startswith(self._main_prefix)
            thumbnail_dir = MEDIA_THUMBNAIL if is_main else CACHE_THUMBNAIL
            prefix = None
            if is_main:
                prefix = self._main_prefix
            else:
                if self._card_a_prefix and \
                    path.startswith(self._card_a_prefix):
                    prefix = self._card_a_prefix
                elif self._card_b_prefix and \
                        path.startswith(self._card_b_prefix):
                    prefix = self._card_b_prefix
            if prefix is None:
                prints('WARNING: Failed to find prefix for:', filepath)
                return
            thumbnail_dir = os.path.join(prefix, *thumbnail_dir.split('/'))

            relpath = os.path.relpath(filepath, prefix)
            if relpath.startswith('..\\'):
                relpath = relpath[3:]
            thumbnail_dir = os.path.join(thumbnail_dir, relpath)
            if not os.path.exists(thumbnail_dir):
                os.makedirs(thumbnail_dir)
            cpath = os.path.join(thumbnail_dir, 'main_thumbnail.jpg')
            with open(cpath, 'wb') as f:
                f.write(metadata.thumbnail[-1])
            debug_print('Cover uploaded to: %r'%cpath)

