#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.constants import plugins
pi, pi_error = plugins['progress_indicator']

if pi_error:
    raise RuntimeError('Failed to load the Progress Indicator plugin: '+\
            pi_error)

ProgressIndicator = pi.QProgressIndicator
