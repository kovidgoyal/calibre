#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

import json
import os
import tempfile

from calibre.constants import cache_dir, config_dir
from calibre.utils.config import JSONConfig
from calibre.utils.date import isoformat, utcnow
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


def expand_profile_user_names(user_names):
    user_names = set(user_names)
    sau = get_session_pref('sync_annots_user', default='')
    if sau:
        if sau == '*':
            sau = 'user:'
        if 'viewer:' in user_names:
            user_names.add(sau)
        elif sau in user_names:
            user_names.add('viewer:')
    return user_names


def load_viewer_profiles(*user_names: str):
    user_names = expand_profile_user_names(user_names)
    ans = {}
    try:
        with open(os.path.join(viewer_config_dir, 'profiles.json'), 'rb') as f:
            raw = json.loads(f.read())
    except FileNotFoundError:
        return ans
    for uname, profiles in raw.items():
        if uname in user_names:
            for profile_name, profile in profiles.items():
                if profile_name not in ans or ans[profile_name]['__timestamp__'] <= profile['__timestamp__']:
                    ans[profile_name] = profile
    return ans


def save_viewer_profile(profile_name, profile, *user_names: str):
    user_names = expand_profile_user_names(user_names)
    if isinstance(profile, (str, bytes)):
        profile = json.loads(profile)
    if isinstance(profile, dict):
        profile['__timestamp__'] = isoformat(utcnow())
        from calibre.gui2.viewer.toolbars import current_actions, DEFAULT_ACTIONS
        ca = current_actions()
        s = {}
        if ca != DEFAULT_ACTIONS:
            s['toolbar-actions'] = ca
        if s:
            profile['__standalone_extra_settings__'] = s
    try:
        with open(os.path.join(viewer_config_dir, 'profiles.json'), 'rb') as f:
            raw = json.loads(f.read())
    except FileNotFoundError:
        raw = {}
    for name in user_names:
        if isinstance(profile, dict):
            raw.setdefault(name, {})[profile_name] = profile
        else:
            if name in raw:
                raw[name].pop(profile_name, None)
    with open(os.path.join(viewer_config_dir, 'profiles.json'), 'wb') as f:
        f.write(json.dumps(raw, indent=2, sort_keys=True).encode())
