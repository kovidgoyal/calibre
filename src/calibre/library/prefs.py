#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid@kovidgoyal.net>

import json
import os
from typing import TYPE_CHECKING, cast

from calibre import prints
from calibre.constants import preferred_encoding
from calibre.utils.config import from_json, to_json

if TYPE_CHECKING:
    from calibre.library.database2 import LibraryDatabase2


class DBPrefs(dict):
    def __init__(self, db: LibraryDatabase2) -> None:
        dict.__init__(self)
        self.db = db
        self.defaults: dict[str, object] = {}
        self.disable_setting = False
        for key, val in cast('list[list[str]]', self.db.conn.get('SELECT key,val FROM preferences')):
            try:
                val = self.raw_to_object(val)
            except Exception:
                prints('Failed to read value for:', key, 'from db')
                continue
            dict.__setitem__(self, key, val)

    def raw_to_object(self, raw: str | bytes) -> object:
        if not isinstance(raw, str):
            raw = raw.decode(preferred_encoding)
        return json.loads(raw, object_hook=from_json)

    def to_raw(self, val: object) -> str:
        return json.dumps(val, indent=2, default=to_json)

    def has_setting(self, key: str) -> bool:
        return key in self

    def __getitem__(self, key: str) -> object:
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults[key]

    def __delitem__(self, key: str) -> None:
        dict.__delitem__(self, key)
        self.db.conn.execute('DELETE FROM preferences WHERE key=?', (key,))
        self.db.conn.commit()

    def __setitem__(self, key: str, val: object) -> None:
        if self.disable_setting:
            return
        raw = self.to_raw(val)
        self.db.conn.execute('INSERT OR REPLACE INTO preferences (key,val) VALUES (?,?)', (key, raw))
        self.db.conn.commit()
        dict.__setitem__(self, key, val)

    def set(self, key: str, val: object) -> None:
        self.__setitem__(key, val)

    def get_namespaced(self, namespace: str, key: str, default: object = None) -> object:
        key = f'namespaced:{namespace}:{key}'
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return default

    def set_namespaced(self, namespace: str, key: str, val: object) -> None:
        if ':' in key:
            raise KeyError('Colons are not allowed in keys')
        if ':' in namespace:
            raise KeyError('Colons are not allowed in the namespace')
        key = f'namespaced:{namespace}:{key}'
        self[key] = val

    def write_serialized(self, library_path: str) -> None:
        try:
            to_filename = os.path.join(library_path, 'metadata_db_prefs_backup.json')
            data = json.dumps(self, indent=2, default=to_json)
            if not isinstance(data, bytes):
                data = data.encode('utf-8')
            with open(to_filename, 'wb') as f:
                f.write(data)
        except Exception:
            import traceback

            traceback.print_exc()

    @classmethod
    def read_serialized(cls, library_path: str, recreate_prefs: bool = False) -> dict[str, object]:
        try:
            from_filename = os.path.join(library_path, 'metadata_db_prefs_backup.json')
            with open(from_filename, 'rb') as f:
                d = json.load(f, object_hook=from_json)
                if not recreate_prefs:
                    return d
                # Recreating the prefs requires a database instance, which is
                # not available in this classmethod
                raise NotImplementedError('recreate_prefs is not supported')
        except Exception:
            import traceback

            traceback.print_exc()
            raise
