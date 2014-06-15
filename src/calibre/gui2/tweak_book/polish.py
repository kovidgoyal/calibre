#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial

from PyQt4.Qt import (
    QTextBrowser, QVBoxLayout, QDialog, QDialogButtonBox, QIcon, QLabel, QCheckBox)

from calibre.ebooks.oeb.polish.main import CUSTOMIZATION
from calibre.gui2.tweak_book import tprefs

class Abort(Exception):
    pass

def customize_remove_unused_css(name, parent, ans):
    d = QDialog(parent)
    d.l = l = QVBoxLayout()
    d.setLayout(d.l)
    d.setWindowTitle(_('Remove unused CSS'))
    d.la = la = QLabel(_(
        'This will remove all CSS rules that do not match any actual content. You'
        ' can also have it automatically remove any class attributes from the HTML'
        ' that do not match any CSS rules, by using the check box below:'))
    la.setWordWrap(True), l.addWidget(la)
    d.c = c = QCheckBox(_('Remove unused &class attributes'))
    c.setChecked(tprefs['remove_unused_classes'])
    l.addWidget(c)
    d.bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    d.l.addWidget(d.bb)
    d.bb.rejected.connect(d.reject)
    d.bb.accepted.connect(d.accept)
    if d.exec_() != d.Accepted:
        raise Abort()
    ans['remove_unused_classes'] = tprefs['remove_unused_classes'] = c.isChecked()

def get_customization(action, name, parent):
    ans = CUSTOMIZATION.copy()
    try:
        if action == 'remove_unused_css':
            customize_remove_unused_css(name, parent, ans)
    except Abort:
        return None
    return ans

def format_report(title, report):
    from calibre.ebooks.markdown import markdown
    return markdown('# %s\n\n'%title + '\n\n'.join(report), output_format='html4')

def show_report(changed, title, report, parent, show_current_diff):
    report = format_report(title, report)
    d = QDialog(parent)
    d.l = QVBoxLayout()
    d.setLayout(d.l)
    d.e = QTextBrowser(d)
    d.l.addWidget(d.e)
    d.e.setHtml(report)
    d.bb = QDialogButtonBox(QDialogButtonBox.Close)
    if changed:
        b = d.b = d.bb.addButton(_('See what &changed'), d.bb.AcceptRole)
        b.setIcon(QIcon(I('diff.png'))), b.setAutoDefault(False)
        b.clicked.connect(partial(show_current_diff, allow_revert=True))
    d.bb.button(d.bb.Close).setDefault(True)
    d.l.addWidget(d.bb)
    d.bb.rejected.connect(d.reject)
    d.bb.accepted.connect(d.accept)
    d.resize(600, 400)
    d.exec_()
