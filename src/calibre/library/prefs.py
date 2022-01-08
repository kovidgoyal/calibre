#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json, os

from calibre.constants import preferred_encoding
from calibre.utils.config import to_json, from_json
from calibre import prints
from polyglot.builtins import iteritems


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
        if not isinstance(raw, str):
            raw = raw.decode(preferred_encoding)
        return json.loads(raw, object_hook=from_json)

    def to_raw(self, val):
        return json.dumps(val, indent=2, default=to_json)

    def has_setting(self, key):
        return key in self

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
        key = 'namespaced:%s:%s'%(namespace, key)
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return default

    def set_namespaced(self, namespace, key, val):
        if ':' in key:
            raise KeyError('Colons are not allowed in keys')
        if ':' in namespace:
            raise KeyError('Colons are not allowed in'
                ' the namespace')
        key = 'namespaced:%s:%s'%(namespace, key)
        self[key] = val

    def write_serialized(self, library_path):
        try:
            to_filename = os.path.join(library_path, 'metadata_db_prefs_backup.json')
            data = json.dumps(self, indent=2, default=to_json)
            if not isinstance(data, bytes):
                data = data.encode('utf-8')
            with open(to_filename, "wb") as f:
                f.write(data)
        except:
            import traceback
            traceback.print_exc()

    @classmethod
    def read_serialized(cls, library_path, recreate_prefs=False):
        try:
            from_filename = os.path.join(library_path,
                    'metadata_db_prefs_backup.json')
            with open(from_filename, "rb") as f:
                d = json.load(f, object_hook=from_json)
                if not recreate_prefs:
                    return d
                cls.clear()
                cls.db.conn.execute('DELETE FROM preferences')
                for k,v in iteritems(d):
                    raw = cls.to_raw(v)
                    cls.db.conn.execute(
                        'INSERT INTO preferences (key,val) VALUES (?,?)', (k, raw))
                cls.db.conn.commit()
                cls.clear()
                cls.update(d)
                return d
        except:
            import traceback
            traceback.print_exc()
            raise
        return None
