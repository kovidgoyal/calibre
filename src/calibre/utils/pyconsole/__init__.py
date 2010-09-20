#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys

from calibre import prints as prints_

def prints(*args, **kwargs):
    kwargs['file'] = sys.__stdout__
    prints_(*args, **kwargs)


