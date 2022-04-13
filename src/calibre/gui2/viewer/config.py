#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

import json
import os
import tempfile

from calibre.constants import cache_dir, config_dir
from calibre.utils.config import JSONConfig
from calibre.utils.filenames import atomic_rename

vprefs = JSONConfig('viewer-webengine')
viewer_config_dir = os.path.join(config_dir, 'viewer')
vprefs.defaults['session_data'] = {}
vprefs.defaults['local_storage'] = {}
vprefs.defaults['main_window_state'] = None
vprefs.defaults['main_window_geometry'] = None
vprefs.defaults['old_prefs_migrated'] = False
vprefs.defaults['bookmarks_sort'] = 'title'
vprefs.defaults['highlight_export_format'] = 'txt'
vprefs.defaults['auto_update_lookup'] = True


def get_session_pref(name, default=None, group='standalone_misc_settings'):
    sd = vprefs['session_data']
    g = sd.get(group, {}) if group else sd
    return g.get(name, default)


def get_pref_group(name):
    sd = vprefs['session_data']
    return sd.get(name) or {}


def reading_rates_path():
    return os.path.join(cache_dir(), 'viewer-reading-rates.json')


def get_existing_reading_rates():
    path = reading_rates_path()
    existing = {}
    try:
        with open(path, 'rb') as f:
            raw = f.read()
    except OSError:
        pass
    else:
        try:
            existing = json.loads(raw)
        except Exception:
            pass
    return existing


def save_reading_rates(key, rates):
    existing = get_existing_reading_rates()
    existing.pop(key, None)
    existing[key] = rates
    while len(existing) > 50:
        expired = next(iter(existing))
        del existing[expired]
    ddata = json.dumps(existing, indent=2).encode('utf-8')
    path = reading_rates_path()
    try:
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(path), delete=False) as f:
            f.write(ddata)
        atomic_rename(f.name, path)
    except Exception:
        import traceback
        traceback.print_exc()


def load_reading_rates(key):
    existing = get_existing_reading_rates()
    return existing.get(key)
