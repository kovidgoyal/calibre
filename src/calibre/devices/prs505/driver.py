__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Device driver for the SONY devices
'''

import os, time, re

from calibre.devices.usbms.driver import USBMS, debug_print
from calibre.devices.prs505 import MEDIA_XML
from calibre.devices.prs505 import CACHE_XML
from calibre.devices.prs505.sony_cache import XMLCache
from calibre import __appname__
from calibre.devices.usbms.books import CollectionsBookList

class PRS505(USBMS):

    name           = 'SONY Device Interface'
    gui_name       = 'SONY Reader'
    description    = _('Communicate with all the Sony eBook readers.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']
    path_sep = '/'
    booklist_class = CollectionsBookList


    FORMATS      = ['epub', 'lrf', 'lrx', 'rtf', 'pdf', 'txt']
    CAN_SET_METADATA = ['title', 'authors', 'collections']

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
    SUPPORTS_USE_AUTHOR_SORT = True
    EBOOK_DIR_MAIN = 'database/media/books'

    EXTRA_CUSTOMIZATION_MESSAGE = _('Comma separated list of metadata fields '
            'to turn into collections on the device. Possibilities include: ')+\
                    'series, tags, authors'
    EXTRA_CUSTOMIZATION_DEFAULT = ', '.join(['series', 'tags'])

    plugboard = None
    plugboard_func = None

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

    def get_device_information(self, end_session=True):
        return (self.gui_name, '', '', '')

    def filename_callback(self, fname, mi):
        if getattr(mi, 'application_id', None) is not None:
            base = fname.rpartition('.')[0]
            suffix = '_%s'%mi.application_id
            if not base.endswith(suffix):
                fname = base + suffix + '.' + fname.rpartition('.')[-1]
        return fname

    def initialize_XML_cache(self):
        paths, prefixes = {}, {}
        for prefix, path, source_id in [
                ('main', MEDIA_XML, 0),
                ('card_a', CACHE_XML, 1),
                ('card_b', CACHE_XML, 2)
                ]:
            prefix = getattr(self, '_%s_prefix'%prefix)
            if prefix is not None and os.path.exists(prefix):
                paths[source_id] = os.path.join(prefix, *(path.split('/')))
                prefixes[source_id] = prefix
                d = os.path.dirname(paths[source_id])
                if not os.path.exists(d):
                    os.makedirs(d)
        return XMLCache(paths, prefixes, self.settings().use_author_sort)

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
            if booklists[i] is not None:
                blists[i] = booklists[i]
        opts = self.settings()
        if opts.extra_customization:
            collections = [x.lower().strip() for x in
                    opts.extra_customization.split(',')]
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
