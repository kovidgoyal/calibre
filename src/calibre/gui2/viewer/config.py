#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import os
from calibre.constants import config_dir
from calibre.utils.config import JSONConfig

vprefs = JSONConfig('viewer-webengine')
viewer_config_dir = os.path.join(config_dir, 'viewer')
vprefs.defaults['session_data'] = {}
vprefs.defaults['local_storage'] = {}
vprefs.defaults['main_window_state'] = None
vprefs.defaults['main_window_geometry'] = None
vprefs.defaults['old_prefs_migrated'] = False
vprefs.defaults['bookmarks_sort'] = 'title'


def get_session_pref(name, default=None, group='standalone_misc_settings'):
    sd = vprefs['session_data']
    g = sd.get(group, {}) if group else sd
    return g.get(name, default)
