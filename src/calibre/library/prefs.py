#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json

from calibre.constants import preferred_encoding
from calibre.utils.config import to_json, from_json
from calibre import prints

class DBPrefs(dict):

    def __init__(self, db):
        dict.__init__(self)
        self.db = db
        self.defaults = {}
        self.disable_setting = False
        for key, val in self.db.conn.get('SELECT key,val FROM preferences'):
            try:
                val = self.raw_to_object(val)
            except:
                prints('Failed to read value for:', key, 'from db')
                continue
            dict.__setitem__(self, key, val)

    def raw_to_object(self, raw):
        if not isinstance(raw, unicode):
            raw = raw.decode(preferred_encoding)
        return json.loads(raw, object_hook=from_json)

    def to_raw(self, val):
        return json.dumps(val, indent=2, default=to_json)

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults[key]

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        self.db.conn.execute('DELETE FROM preferences WHERE key=?', (key,))
        self.db.conn.commit()

    def __setitem__(self, key, val):
        if self.disable_setting:
            return
        raw = self.to_raw(val)
        self.db.conn.execute('INSERT OR REPLACE INTO preferences (key,val) VALUES (?,?)', (key,
            raw))
        self.db.conn.commit()
        dict.__setitem__(self, key, val)

    def set(self, key, val):
        self.__setitem__(key, val)

    def get_namespaced(self, namespace, key, default=None):
        key = u'namespaced:%s:%s'%(namespace, key)
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return default

    def set_namespaced(self, namespace, key, val):
        key = u'namespaced:%s:%s'%(namespace, key)
        self[key] = val

