#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import imghdr

from calibre.ebooks.mobi import MAX_THUMB_DIMEN, MAX_THUMB_SIZE
from calibre.ebooks.mobi.utils import (rescale_image, mobify_image,
        write_font_record)
from calibre.ebooks import generate_masthead
from calibre.ebooks.oeb.base import OEB_RASTER_IMAGES

PLACEHOLDER_GIF = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00@\x02\x01D\x00;'

class Resources(object):

    def __init__(self, oeb, opts, is_periodical, add_fonts=False):
        self.oeb, self.log, self.opts = oeb, oeb.log, opts
        self.is_periodical = is_periodical

        self.item_map = {}
        self.records = []
        self.mime_map = {}
        self.masthead_offset = 0
        self.used_image_indices = set()
        self.image_indices = set()
        self.cover_offset = self.thumbnail_offset = None

        self.add_resources(add_fonts)

    def process_image(self, data):
        return (mobify_image(data) if self.opts.mobi_keep_original_images else
                rescale_image(data))

    def add_resources(self, add_fonts):
        oeb = self.oeb
        oeb.logger.info('Serializing resources...')
        index = 1

        mh_href = None
        if 'masthead' in oeb.guide and oeb.guide['masthead'].href:
            mh_href = oeb.guide['masthead'].href
            self.records.append(None)
            index += 1
            self.used_image_indices.add(0)
            self.image_indices.add(0)
        elif self.is_periodical:
            # Generate a default masthead
            data = generate_masthead(unicode(self.oeb.metadata['title'][0]))
            self.records.append(data)
            self.used_image_indices.add(0)
            self.image_indices.add(0)
            index += 1

        cover_href = self.cover_offset = self.thumbnail_offset = None
        if (oeb.metadata.cover and
                unicode(oeb.metadata.cover[0]) in oeb.manifest.ids):
            cover_id = unicode(oeb.metadata.cover[0])
            item = oeb.manifest.ids[cover_id]
            cover_href = item.href

        for item in self.oeb.manifest.values():
            if item.media_type not in OEB_RASTER_IMAGES: continue
            try:
                data = self.process_image(item.data)
            except:
                self.log.warn('Bad image file %r' % item.href)
                continue
            else:
                if mh_href and item.href == mh_href:
                    self.records[0] = data
                    continue

                self.image_indices.add(len(self.records))
                self.records.append(data)
                self.item_map[item.href] = index
                self.mime_map[item.href] = 'image/%s'%imghdr.what(None, data)
                index += 1

                if cover_href and item.href == cover_href:
                    self.cover_offset = self.item_map[item.href] - 1
                    self.used_image_indices.add(self.cover_offset)
                    try:
                        data = rescale_image(item.data, dimen=MAX_THUMB_DIMEN,
                            maxsizeb=MAX_THUMB_SIZE)
                    except:
                        self.log.warn('Failed to generate thumbnail')
                    else:
                        self.image_indices.add(len(self.records))
                        self.records.append(data)
                        self.thumbnail_offset = index - 1
                        self.used_image_indices.add(self.thumbnail_offset)
                        index += 1
            finally:
                item.unload_data_from_memory()

        if add_fonts:
            for item in self.oeb.manifest.values():
                if item.href and item.href.rpartition('.')[-1].lower() in {
                        'ttf', 'otf'} and isinstance(item.data, bytes):
                    self.records.append(write_font_record(item.data))
                    self.item_map[item.href] = len(self.records)

    def add_extra_images(self):
        '''
        Add any images that were created after the call to add_resources()
        '''
        for item in self.oeb.manifest.values():
            if (item.media_type not in OEB_RASTER_IMAGES or item.href in
                    self.item_map): continue
            try:
                data = self.process_image(item.data)
            except:
                self.log.warn('Bad image file %r' % item.href)
            else:
                self.records.append(data)
                self.item_map[item.href] = len(self.records)
            finally:
                item.unload_data_from_memory()

    def serialize(self, records, used_images):
        used_image_indices = self.used_image_indices | {
                v-1 for k, v in self.item_map.iteritems() if k in used_images}
        for i in self.image_indices-used_image_indices:
            self.records[i] = PLACEHOLDER_GIF
        records.extend(self.records)

    def __bool__(self):
        return bool(self.records)
    __nonzero__ = __bool__

