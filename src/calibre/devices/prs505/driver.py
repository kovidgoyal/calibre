# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net> ' \
                '2009, John Schember <john at nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Device driver for the SONY PRS-505
'''

import os
import re

from calibre.devices.usbms.driver import USBMS
from calibre.devices.prs505 import MEDIA_XML
from calibre.devices.prs505 import CACHE_XML
from calibre.devices.prs505.sony_cache import XMLCache
from calibre import __appname__

class PRS505(USBMS):

    name           = 'PRS-300/505 Device Interface'
    gui_name       = 'SONY Reader'
    description    = _('Communicate with the Sony PRS-300/505/500 eBook reader.')
    author         = 'Kovid Goyal and John Schember'
    supported_platforms = ['windows', 'osx', 'linux']
    path_sep = '/'

    FORMATS      = ['epub', 'lrf', 'lrx', 'rtf', 'pdf', 'txt']

    VENDOR_ID    = [0x054c]   #: SONY Vendor Id
    PRODUCT_ID   = [0x031e]   #: Product Id for the PRS 300/505/new 500
    BCD          = [0x229, 0x1000, 0x22a]

    VENDOR_NAME        = 'SONY'
    WINDOWS_MAIN_MEM   = re.compile('PRS-(505|300|500)')
    WINDOWS_CARD_A_MEM = re.compile(r'PRS-(505|500)[#/]\S+:MS')
    WINDOWS_CARD_B_MEM = re.compile(r'PRS-(505|500)[#/]\S+:SD')

    OSX_MAIN_MEM   = re.compile(r'Sony PRS-(((505|300|500)/[^:]+)|(300)) Media')
    OSX_CARD_A_MEM = re.compile(r'Sony PRS-(505|500)/[^:]+:MS Media')
    OSX_CARD_B_MEM = re.compile(r'Sony PRS-(505|500)/[^:]+:SD Media')

    MAIN_MEMORY_VOLUME_LABEL  = 'Sony Reader Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Sony Reader Storage Card'

    CARD_PATH_PREFIX          = __appname__

    SUPPORTS_SUB_DIRS = True
    MUST_READ_METADATA = True
    EBOOK_DIR_MAIN = 'database/media/books'

    EXTRA_CUSTOMIZATION_MESSAGE = _('Comma separated list of metadata fields '
            'to turn into collections on the device. Possibilities include: ')+\
                    'series, tags, authors'
    EXTRA_CUSTOMIZATION_DEFAULT = ', '.join(['series', 'tags'])

    def windows_filter_pnp_id(self, pnp_id):
        return '_LAUNCHER' in pnp_id

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
        return XMLCache(paths, prefixes)

    def books(self, oncard=None, end_session=True):
        bl = USBMS.books(self, oncard=oncard, end_session=end_session)
        c = self.initialize_XML_cache()
        c.update_booklist(bl, {'carda':1, 'cardb':2}.get(oncard, 0))
        return bl

    def sync_booklists(self, booklists, end_session=True):
        c = self.initialize_XML_cache()
        blists = {}
        for i in c.paths:
            if booklists[i] is not None:
                blists[i] = booklists[i]
        opts = self.settings()
        collections = ['series', 'tags']
        if opts.extra_customization:
            collections = opts.extra_customization.split(',')

        c.update(blists, collections)
        c.write()

        USBMS.sync_booklists(self, booklists, end_session=end_session)

class PRS700(PRS505):

    name           = 'PRS-600/700/900 Device Interface'
    description    = _('Communicate with the Sony PRS-600/700/900 eBook reader.')
    author         = 'Kovid Goyal and John Schember'
    gui_name       = 'SONY Reader'
    supported_platforms = ['windows', 'osx', 'linux']

    BCD          = [0x31a]

    WINDOWS_MAIN_MEM = re.compile('PRS-((700[#/])|((6|9)00&))')
    WINDOWS_CARD_A_MEM = re.compile(r'PRS-((700[/#]\S+:)|((6|9)00[#_]))MS')
    WINDOWS_CARD_B_MEM = re.compile(r'PRS-((700[/#]\S+:)|((6|9)00[#_]))SD')

    OSX_MAIN_MEM   = re.compile(r'Sony PRS-((700/[^:]+)|((6|9)00)) Media')
    OSX_CARD_A_MEM = re.compile(r'Sony PRS-((700/[^:]+:)|((6|9)00 ))MS Media')
    OSX_CARD_B_MEM = re.compile(r'Sony PRS-((700/[^:]+:)|((6|9)00 ))SD Media')
