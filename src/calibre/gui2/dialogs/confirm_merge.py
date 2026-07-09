#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os
from typing import NamedTuple

from qt.core import QCheckBox, QDialog, QDialogButtonBox, QLabel, QSplitter, Qt, QTextBrowser, QUrl, QVBoxLayout, QWidget

from calibre.ebooks.metadata import authors_to_string
from calibre.ebooks.metadata.book.base import field_metadata
from calibre.gui2 import dynamic, gprefs
from calibre.gui2.dialogs.confirm_delete import confirm_config_name
from calibre.gui2.widgets2 import Dialog, FlowLayout
from calibre.startup import connect_lambda
from calibre.utils.config import tweaks
from calibre.utils.date import format_date


class Target(QTextBrowser):

    def __init__(self, mi, parent=None):
        QTextBrowser.__init__(self, parent)
        series = ''
        fm = field_metadata
        if mi.series:
            series = _('{num} of {series}').format(num=mi.format_series_index(), series=f'<i>{mi.series}</i>')
            series = f'<tr><td>{fm["series"]["name"]}:</td><td>{series}</td></tr>'
        cover_html = has_cover_row = ''
        if mi.cover:
            cover_html = f'<img src="{QUrl.fromLocalFile(mi.cover).toString()}">'.format()
            self.document().setDefaultStyleSheet(
                'img { max-width: 100%; width: 100%; height: auto; display: block; }'
            )
        else:
            has_cover_row = f"<tr><td>{_('Has cover')}:</td><td>{_('Yes') if mi.has_cover else _('No')}</td></tr>"
        self.setHtml('''
<h3 style="text-align:center">{mb}</h3>
<p><b>{title}</b> - <i>{authors}</i><br></p>
<table>
<tr><td>{fm[timestamp][name]}:</td><td>{date}</td></tr>
<tr><td>{fm[pubdate][name]}:</td><td>{published}</td></tr>
<tr><td>{fm[formats][name]}:</td><td>{formats}</td></tr>
<tr><td>{fm[id][name]}:</td><td>{book_id}</td></tr>
{series}
{has_cover_row}
</table>
{cover_html}
        '''.format(
            mb=_('Target book'),
            title=mi.title, book_id=getattr(mi, 'id', ''),
            has_cover_row=has_cover_row,
            authors=authors_to_string(mi.authors),
            date=format_date(mi.timestamp, tweaks['gui_timestamp_display_format']), fm=fm,
            published=(format_date(mi.pubdate, tweaks['gui_pubdate_display_format']) if mi.pubdate else ''),
            formats=', '.join(mi.formats or ()),
            series=series, cover_html=cover_html,
        ))

    def sizeHint(self):
        ans = super().sizeHint()
        ans.setHeight(max(600, ans.height()))
        return ans


class ConfirmMerge(Dialog):

    def __init__(self, msg, name, parent, mi, ask_about_save_alternate_cover=False):
        self.msg, self.mi, self.conf_name = msg, mi, name
        self.ask_about_save_alternate_cover = ask_about_save_alternate_cover
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
        self.save_alternate_cover_cb = c = QCheckBox(_('Save replaced or discarded &cover'), self)
        c.setToolTip(_('Save the replaced or discarded cover in the data files associated with the target book as an alternate cover'))
        c.setObjectName('choose-merge-cb-save_alternate_cover')
        c.setChecked(bool(gprefs.get(c.objectName(), False)))
        l.addWidget(c)
        c.setVisible(self.ask_about_save_alternate_cover)
        c.toggled.connect(self.alternate_covers_toggled)
        self.confirm = c = QCheckBox(_('Show this confirmation again'), self)
        c.setChecked(True)
        c.stateChanged.connect(self.toggle)
        l.addWidget(c)

        self.right = r = Target(self.mi, self)
        s.addWidget(r)

    def alternate_covers_toggled(self):
        gprefs.set(self.save_alternate_cover_cb.objectName(), self.save_alternate_cover_cb.isChecked())

    def toggle(self):
        dynamic[confirm_config_name(self.conf_name)] = self.confirm.isChecked()

    def sizeHint(self):
        ans = Dialog.sizeHint(self)
        ans.setWidth(max(700, ans.width()))
        return ans


def confirm_merge(msg, name, parent, mi, ask_about_save_alternate_cover=False):
    if not dynamic.get(confirm_config_name(name), True):
        return True, bool(gprefs.get('choose-merge-cb-save_alternate_cover', False))
    d = ConfirmMerge(msg, name, parent, mi, ask_about_save_alternate_cover)
    return d.exec() == QDialog.DialogCode.Accepted, d.save_alternate_cover_cb.isChecked()


class ChooseMerge(Dialog):

    def __init__(self, dest_id, src_ids, gui):
        self.dest_id, self.src_ids = dest_id, src_ids
        self.mi = gui.current_db.new_api.get_metadata(dest_id, get_cover=True)
        Dialog.__init__(self, _('Merge books'), 'choose-merge-dialog', parent=gui)
        self.finished.connect(self.cleanup_resources)

    def cleanup_resources(self):
        if self.mi.cover:
            os.remove(self.mi.cover)

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
        w.fl = fl = FlowLayout()
        l.addLayout(fl)

        def cb(name, text, tt='', defval=True):
            ans = QCheckBox(text)
            fl.addWidget(ans)
            prefs_key = ans.prefs_key = 'choose-merge-cb-' + name
            ans.setChecked(gprefs.get(prefs_key, defval))
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
        cb('replace_cover', _('Replace existing cover'), _(
            'Replace the cover in the target book with the dragged cover'))
        cb('save_alternate_cover', _('Save alternate cover'), _(
            'Save the replaced or discarded cover in the data files associated with the target book as an alternate cover'), defval=False)
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
        rc = self.replace_cover.isChecked()
        msg = '<p>'
        if mm and mf:
            msg += _(
                'Book formats and metadata from the selected books'
                ' will be merged into the target book ({title}).')
            if rc or not self.mi.has_cover:
                msg += ' ' + _('The dragged cover will be used.')
        elif mf:
            msg += _('Book formats from the selected books '
            'will be merged into to the target book ({title}).'
            ' Metadata and cover in the target book will not be changed.')
        elif mm:
            msg += _('Metadata from the selected books '
            'will be merged into to the target book ({title}).'
            ' Formats will not be merged.')
            if rc or not self.mi.has_cover:
                msg += ' ' + _('The dragged cover will be used.')
        msg += '<br>'
        msg += _('All book formats of the target book will be kept.') + '<br><br>'
        if rm:
            msg += _('After being merged, the selected books will be <b>deleted</b>.')
            if mf:
                msg += '<br><br>' + _(
                'Any duplicate formats in the selected books '
                'will be permanently <b>deleted</b> from your calibre library.')
        elif mf:
            msg += _(
                'Any formats not in the target book will be added to it from the selected books.')
        if not msg.endswith('<br>'):
            msg += '<br><br>'

        msg += _('Are you <b>sure</b> you want to proceed?') + '</p>'
        msg = msg.format(title=self.mi.title)
        self.msg.setText(msg)

    @property
    def merge_type(self):
        return MergeData(
            self.merge_metadata.isChecked(), self.merge_formats.isChecked(), self.delete_books.isChecked(),
            self.replace_cover.isChecked(), self.save_alternate_cover.isChecked(),
        )


class MergeData(NamedTuple):
    merge_metadata: bool = False
    merge_formats: bool = False
    delete_books: bool = False
    replace_cover: bool = False
    save_alternate_cover: bool = False


def merge_drop(dest_id, src_ids, gui):
    d = ChooseMerge(dest_id, src_ids, gui)
    if d.exec() != QDialog.DialogCode.Accepted:
        return None
    return d.merge_type
