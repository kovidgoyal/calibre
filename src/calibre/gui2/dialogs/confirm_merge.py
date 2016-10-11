#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt5.Qt import (
    QVBoxLayout, QSplitter, QWidget, QLabel, QCheckBox, QTextBrowser
)

from calibre.ebooks.metadata import authors_to_string
from calibre.ebooks.metadata.book.base import field_metadata
from calibre.gui2 import dynamic
from calibre.gui2.widgets2 import Dialog
from calibre.gui2.dialogs.confirm_delete import confirm_config_name
from calibre.utils.config import tweaks
from calibre.utils.date import format_date


class ConfirmMerge(Dialog):

    def __init__(self, msg, name, parent, mi):
        self.msg, self.mi, self.conf_name = msg, mi, name
        Dialog.__init__(self, _('Are you sure?'), 'confirm-merge-dialog', parent)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.splitter = s = QSplitter(self)
        s.setChildrenCollapsible(False)
        l.addWidget(s), l.addWidget(self.bb)
        self.bb.setStandardButtons(self.bb.Yes | self.bb.No)

        self.left = w = QWidget(self)
        s.addWidget(w)
        w.l = l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)
        self.la = la = QLabel(self.msg)
        la.setWordWrap(True)
        l.addWidget(la)
        self.confirm = c = QCheckBox(_('Show this confirmation again'), self)
        c.setChecked(True)
        c.stateChanged.connect(self.toggle)
        l.addWidget(c)

        self.right = r = QTextBrowser(self)
        series = ''
        mi, fm = self.mi, field_metadata
        if mi.series:
            series = _('{num} of {series}').format(num=mi.format_series_index(), series='<i>%s</i>' % mi.series)
        r.setHtml('''
<h3 style="text-align:center">{mb}</h3>
<p><b>{title}</b> - <i>{authors}</i><br></p>
<table>
<tr><td>{fm[timestamp][name]}:</td><td>{date}</td></tr>
<tr><td>{fm[pubdate][name]}:</td><td>{published}</td></tr>
<tr><td>{fm[formats][name]}:</td><td>{formats}</td></tr>
<tr><td>{fm[series][name]}:</td><td>{series}</td></tr>
</table>
        '''.format(
            mb=_('Target book'),
            title=mi.title,
            authors=authors_to_string(mi.authors),
            date=format_date(mi.timestamp, tweaks['gui_timestamp_display_format']), fm=fm,
            published=(format_date(mi.pubdate, tweaks['gui_pubdate_display_format']) if mi.pubdate else ''),
            formats=', '.join(mi.formats or ()),
            series=series
        ))
        s.addWidget(r)

    def toggle(self):
        dynamic[confirm_config_name(self.conf_name)] = self.confirm.isChecked()

    def sizeHint(self):
        ans = Dialog.sizeHint(self)
        ans.setWidth(max(700, ans.width()))
        return ans


def confirm_merge(msg, name, parent, mi):
    config_set = dynamic
    if not config_set.get(confirm_config_name(name), True):
        return True
    d = ConfirmMerge(msg, name, parent, mi)
    return d.exec_() == d.Accepted
