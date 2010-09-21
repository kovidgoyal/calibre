#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys

from calibre import prints as prints_
from calibre.utils.config import Config, StringConfig


def console_config(defaults=None):
    desc=_('Settings to control the calibre content server')
    c = Config('console', desc) if defaults is None else StringConfig(defaults, desc)

    c.add_opt('--theme', default='default', help='The color theme')


def prints(*args, **kwargs):
    kwargs['file'] = sys.__stdout__
    prints_(*args, **kwargs)


