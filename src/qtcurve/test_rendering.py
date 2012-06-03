#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.gui2 import Application
from PyQt4.Qt import (QDialog, QGridLayout, QListWidget, QDialogButtonBox)

app = Application([], force_calibre_style=True)

d = QDialog()
d.l = l = QGridLayout()
d.setLayout(l)
lw = QListWidget()
lw.addItem('Some text guy')
l.addWidget(lw, 0, 0, 2, 1)
bb = QDialogButtonBox()
bb.setStandardButtons(bb.Close)
bb.accepted.connect(d.accept)
bb.rejected.connect(d.reject)
l.addWidget(bb, 2, 0, 1, 2)

d.exec_()

