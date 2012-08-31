#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from functools import wraps, partial

from calibre import prints
from calibre.constants import DEBUG
from calibre.devices.interface import DevicePlugin

def debug(*args, **kwargs):
    if DEBUG:
        prints('MTP:', *args, **kwargs)

def synchronous(func):
    @wraps(func)
    def synchronizer(self, *args, **kwargs):
        with self.lock:
            return func(self, *args, **kwargs)
    return synchronizer

class MTPDeviceBase(DevicePlugin):
    name = 'SmartDevice App Interface'
    gui_name = _('MTP Device')
    icon = I('devices/galaxy_s3.png')
    description = _('Communicate with MTP devices')
    author = 'Kovid Goyal'
    version = (1, 0, 0)

    THUMBNAIL_HEIGHT = 128
    CAN_SET_METADATA = []

    BACKLOADING_ERROR_MESSAGE = None

    def __init__(self, *args, **kwargs):
        DevicePlugin.__init__(self, *args, **kwargs)
        self.progress_reporter = None
        self.current_friendly_name = None
        self.report_progress = lambda x, y: None

    def reset(self, key='-1', log_packets=False, report_progress=None,
            detected_device=None):
        pass

    def set_progress_reporter(self, report_progress):
        self.report_progress = report_progress

    def get_gui_name(self):
        return self.current_friendly_name or self.name

    def is_usb_connected(self, devices_on_system, debug=False,
            only_presence=False):
        # We manage device presence ourselves, so this method should always
        # return False
        return False

    def build_template_regexp(self):
        return None
        # TODO: Implement this
        def replfunc(match, seen=None):
            v = match.group(1)
            if v in ['authors', 'author_sort']:
                v = 'author'
            if v in ('title', 'series', 'series_index', 'isbn', 'author'):
                if v not in seen:
                    seen.add(v)
                    return '(?P<' + v + '>.+?)'
            return '(.+?)'
        s = set()
        f = partial(replfunc, seen=s)
        template = None
        try:
            template = self.save_template().rpartition('/')[2]
            return re.compile(re.sub('{([^}]*)}', f, template) + '([_\d]*$)')
        except:
            prints(u'Failed to parse template: %r'%template)
            template = u'{title} - {authors}'
            return re.compile(re.sub('{([^}]*)}', f, template) + '([_\d]*$)')



