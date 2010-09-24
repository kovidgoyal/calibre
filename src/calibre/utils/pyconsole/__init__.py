#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os

from calibre import prints as prints_, preferred_encoding, isbytestring
from calibre.utils.config import Config, ConfigProxy, JSONConfig
from calibre.utils.ipc.launch import Worker
from calibre.constants import __appname__, __version__, iswindows
from calibre.gui2 import error_dialog

# Time to wait for communication to/from the interpreter process
POLL_TIMEOUT = 0.01 # seconds

preferred_encoding, isbytestring, __appname__, __version__, error_dialog, \
iswindows

def console_config():
    desc='Settings to control the calibre console'
    c = Config('console', desc)

    c.add_opt('theme', default='native', help='The color theme')
    c.add_opt('scrollback', default=10000,
            help='Max number of lines to keep in the scrollback buffer')

    return c

prefs = ConfigProxy(console_config())
dynamic = JSONConfig('console')

def prints(*args, **kwargs):
    kwargs['file'] = sys.__stdout__
    prints_(*args, **kwargs)

class Process(Worker):

    @property
    def env(self):
        env = dict(os.environ)
        env.update(self._env)
        return env


