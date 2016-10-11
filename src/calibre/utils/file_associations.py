#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'


def file_assoc_windows(ft):
    # See the IQueryAssociations::GetString method documentation on MSDN
    from win32com.shell import shell, shellcon
    a = shell.AssocCreate()
    a.Init(0, '.' + ft.lower())
    return a.GetString(0, shellcon.ASSOCSTR_EXECUTABLE)

