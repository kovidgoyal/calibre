#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re
from calibre.ebooks.oeb.base import XPath, urlunquote


class DataURL(object):

    def __call__(self, oeb, opts):
        self.log = oeb.log
        attr_path = XPath('//h:img[@src]')
        for item in oeb.spine:
            root = item.data
            if not hasattr(root, 'xpath'):
                continue
            for img in attr_path(root):
                raw = img.get('src', '')
                if not raw.startswith('data:'):
                    continue
                header, data = raw.partition(',')[0::2]
                if not header.startswith('data:image/') or not data:
                    continue
                if ';base64' in header:
                    data = re.sub(r'\s+', '', data)
                    from base64 import b64decode
                    try:
                        data = b64decode(data)
                    except Exception:
                        self.log.error('Found invalid base64 encoded data URI, ignoring it')
                        continue
                else:
                    data = urlunquote(data)
                from imghdr import what
                fmt = what(None, data)
                if not fmt:
                    self.log.warn('Image encoded as data URL has unknown format, ignoring')
                    continue
                img.set('src', item.relhref(self.convert_image_data_uri(data, fmt, oeb)))

    def convert_image_data_uri(self, data, fmt, oeb):
        self.log('Found image encoded as data URI converting it to normal image')
        from calibre import guess_type
        item_id, item_href = oeb.manifest.generate('data-url-image', 'data-url-image.' + fmt)
        oeb.manifest.add(item_id, item_href, guess_type(item_href)[0], data=data)
        return item_href
