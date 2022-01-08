#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from qt.core import (
    QVBoxLayout, QSplitter, QWidget, QLabel, QCheckBox, QTextBrowser, Qt, QDialog, QDialogButtonBox
)

from calibre.ebooks.metadata import authors_to_string
from calibre.ebooks.metadata.book.base import field_metadata
from calibre.gui2 import dynamic, gprefs
from calibre.gui2.widgets2 import Dialog
from calibre.gui2.dialogs.confirm_delete import confirm_config_name
from calibre.utils.config import tweaks
from calibre.utils.date import format_date


class Target(QTextBrowser):

    def __init__(self, mi, parent=None):
        QTextBrowser.__init__(self, parent)
        series = ''
        fm = field_metadata
        if mi.series:
            series = _('{num} of {series}').format(num=mi.format_series_index(), series='<i>%s</i>' % mi.series)
        self.setHtml('''
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


class ConfirmMerge(Dialog):

    def __init__(self, msg, name, parent, mi):
        self.msg, self.mi, self.conf_name = msg, mi, name
        Dialog.__init__(self, _('Are you sure?'), 'confirm-merge-dialog', parent)
        needed, sz = self.sizeHint(), self.size()
        if needed.width() > sz.width() or needed.height() > sz.height():
            self.resize(needed)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.splitter = s = QSplitter(self)
        s.setChildrenCollapsible(False)
        l.addWidget(s), l.addWidget(self.bb)
        self.bb.setStandardButtons(QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No)

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

        self.right = r = Target(self.mi, self)
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
    return d.exec() == QDialog.DialogCode.Accepted


class ChooseMerge(Dialog):

    def __init__(self, dest_id, src_ids, gui):
        self.dest_id, self.src_ids = dest_id, src_ids
        self.mi = gui.current_db.new_api.get_metadata(dest_id)
        Dialog.__init__(self, _('Merge books'), 'choose-merge-dialog', parent=gui)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.splitter = s = QSplitter(self)
        s.setChildrenCollapsible(False)
        l.addWidget(s), l.addWidget(self.bb)
        self.bb.setStandardButtons(QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No)
        self.left = w = QWidget(self)
        s.addWidget(w)
        w.l = l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)

        def cb(name, text, tt=''):
            ans = QCheckBox(text)
            l.addWidget(ans)
            prefs_key = ans.prefs_key = 'choose-merge-cb-' + name
            ans.setChecked(gprefs.get(prefs_key, True))
            connect_lambda(ans.stateChanged, self, lambda self, state: self.state_changed(getattr(self, name), state), type=Qt.ConnectionType.QueuedConnection)
            if tt:
                ans.setToolTip(tt)
            setattr(self, name, ans)
            return ans

        cb('merge_metadata', _('Merge metadata'), _(
            'Merge the metadata of the selected books into the target book'))
        cb('merge_formats', _('Merge formats'), _(
            'Merge the book files of the selected books into the target book'))
        cb('delete_books', _('Delete merged books'), _(
            'Delete the selected books after merging'))
        l.addStretch(10)
        self.msg = la = QLabel(self)
        la.setWordWrap(True)
        l.addWidget(la)
        self.update_msg()

        self.right = r = Target(self.mi, self)
        s.addWidget(r)

    def state_changed(self, cb, state):
        mm = self.merge_metadata.isChecked()
        mf = self.merge_formats.isChecked()
        if not mm and not mf:
            (self.merge_metadata if cb is self.merge_formats else self.merge_formats).setChecked(True)
        gprefs[cb.prefs_key] = cb.isChecked()
        self.update_msg()

    def update_msg(self):
        mm = self.merge_metadata.isChecked()
        mf = self.merge_formats.isChecked()
        rm = self.delete_books.isChecked()
        msg = '<p>'
        if mm and mf:
            msg += _(
                'Book formats and metadata from the selected books'
                ' will be merged into the target book ({title}).')
        elif mf:
            msg += _('Book formats from the selected books '
            'will be merged into to the target book ({title}).'
            ' Metadata in the target book will not be changed.')
        elif mm:
            msg += _('Metadata from the selected books '
            'will be merged into to the target book ({title}).'
            ' Formats will not be merged.')
        msg += '<br>'
        msg += _('All book formats of the first selected book will be kept.') + '<br><br>'
        if rm:
            msg += _('After being merged, the selected books will be <b>deleted</b>.')
            if mf:
                msg += '<br><br>' + _(
                'Any duplicate formats in the selected books '
                'will be permanently <b>deleted</b> from your calibre library.')
        else:
            if mf:
                msg += _(
                    'Any formats not in the target book will be added to it from the selected books.')
        if not msg.endswith('<br>'):
            msg += '<br><br>'

        msg += _('Are you <b>sure</b> you want to proceed?') + '</p>'
        msg = msg.format(title=self.mi.title)
        self.msg.setText(msg)

    @property
    def merge_type(self):
        return self.merge_metadata.isChecked(), self.merge_formats.isChecked(), self.delete_books.isChecked()


def merge_drop(dest_id, src_ids, gui):
    d = ChooseMerge(dest_id, src_ids, gui)
    if d.exec() != QDialog.DialogCode.Accepted:
        return None, None, None
    return d.merge_type
