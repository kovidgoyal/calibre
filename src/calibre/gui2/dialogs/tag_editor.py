__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from qt.core import (
    QAbstractItemView, QDialog, QSortFilterProxyModel, QStringListModel, Qt,
)

from calibre.constants import islinux
from calibre.gui2 import error_dialog, gprefs, question_dialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.dialogs.tag_editor_ui import Ui_TagEditor
from calibre.utils.icu import sort_key


class TagEditor(QDialog, Ui_TagEditor):

    def __init__(self, window, db, id_=None, key=None, current_tags=None):
        QDialog.__init__(self, window)
        Ui_TagEditor.__init__(self)
        self.setupUi(self)

        self.db = db
        self.sep = ','
        self.is_names = False
        if key:
            # Assume that if given a key then it is a custom column
            try:
                fm = db.field_metadata[key]
                self.is_names = fm['display'].get('is_names', False)
                if self.is_names:
                    self.sep = '&'
                self.setWindowTitle(self.windowTitle() + ': ' + fm['name'])
            except Exception:
                pass
            key = db.field_metadata.key_to_label(key)
        else:
            self.setWindowTitle(self.windowTitle() + ': ' + db.field_metadata['tags']['name'])

        if self.sep == '&':
            self.add_tag_input.setToolTip('<p>' +
                        _('If the item you want is not in the available list, '
                          'you can add it here. Accepts an ampersand-separated '
                          'list of items. The items will be applied to '
                          'the book.') + '</p>')
        else:
            self.add_tag_input.setToolTip('<p>' +
                        _('If the item you want is not in the available list, '
                          'you can add it here. Accepts a comma-separated '
                          'list of items. The items will be applied to '
                          'the book.') + '</p>')
        self.key = key
        self.index = db.row(id_) if id_ is not None else None
        if self.index is not None:
            if key is None:
                tags = self.db.tags(self.index)
                if tags:
                    tags = [tag.strip() for tag in tags.split(',') if tag.strip()]
            else:
                tags = self.db.get_custom(self.index, label=key)
        else:
            tags = []
        if current_tags is not None:
            tags = sorted(set(current_tags), key=sort_key)
        if tags:
            if not self.is_names:
                tags.sort(key=sort_key)
        else:
            tags = []
        self.applied_model = QStringListModel(tags)
        p = QSortFilterProxyModel()
        p.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        p.setSourceModel(self.applied_model)
        self.applied_tags.setModel(p)
        if self.is_names:
            self.applied_tags.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
            self.applied_tags.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        if key:
            all_tags = [tag for tag in self.db.all_custom(label=key)]
        else:
            all_tags = [tag for tag in self.db.all_tags()]
        all_tags = sorted(set(all_tags) - set(tags), key=sort_key)
        self.all_tags_model = QStringListModel(all_tags)
        p = QSortFilterProxyModel()
        p.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        p.setSourceModel(self.all_tags_model)
        self.available_tags.setModel(p)

        connect_lambda(self.apply_button.clicked, self, lambda self: self.apply_tags())
        connect_lambda(self.unapply_button.clicked, self, lambda self: self.unapply_tags())
        self.add_tag_button.clicked.connect(self.add_tag)
        connect_lambda(self.delete_button.clicked, self, lambda self: self.delete_tags())
        self.add_tag_input.returnPressed[()].connect(self.add_tag)
        # add the handlers for the filter input fields
        connect_lambda(self.available_filter_input.textChanged, self, lambda self, text: self.filter_tags(text))
        connect_lambda(self.applied_filter_input.textChanged, self, lambda self, text: self.filter_tags(text, which='applied_tags'))

        # Restore the focus to the last input box used (typed into)
        for x in ('add_tag_input', 'available_filter_input', 'applied_filter_input'):
            ibox = getattr(self, x)
            ibox.setObjectName(x)
            connect_lambda(ibox.textChanged, self, lambda self: self.edit_box_changed(self.sender().objectName()))
        getattr(self, gprefs.get('tag_editor_last_filter', 'add_tag_input')).setFocus()

        self.available_tags.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.applied_tags.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        if islinux:
            self.available_tags.doubleClicked.connect(self.apply_tags)
            self.applied_tags.doubleClicked.connect(self.unapply_tags)
        else:
            self.available_tags.activated.connect(self.apply_tags)
            self.applied_tags.activated.connect(self.unapply_tags)

        self.restore_geometry(gprefs, 'tag_editor_geometry')

    def edit_box_changed(self, which):
        gprefs['tag_editor_last_filter'] = which

    def delete_tags(self):
        confirms, deletes = [], []
        row_indices = list(self.available_tags.selectionModel().selectedRows())

        if not row_indices:
            error_dialog(self, _('No tags selected'), _('You must select at least one tag from the list of Available tags.')).exec()
            return
        if not confirm(
            _('Deleting tags is done immediately and there is no undo.'),
            'tag_editor_delete'):
            return
        pos = self.available_tags.verticalScrollBar().value()
        for ri in row_indices:
            tag = ri.data()
            used = self.db.is_tag_used(tag) \
                if self.key is None else \
                self.db.is_item_used_in_multiple(tag, label=self.key)
            if used:
                confirms.append(ri)
            else:
                deletes.append(ri)
        if confirms:
            ct = ', '.join(item.data() for item in confirms)
            if question_dialog(self, _('Are your sure?'),
                '<p>'+_('The following tags are used by one or more books. '
                    'Are you certain you want to delete them?')+'<br>'+ct):
                deletes += confirms

        for item in sorted(deletes, key=lambda r: r.row(), reverse=True):
            tag = item.data()
            if self.key is None:
                self.db.delete_tag(tag)
            else:
                bks = self.db.delete_item_from_multiple(tag, label=self.key)
                self.db.refresh_ids(bks)
            self.available_tags.model().removeRows(item.row(), 1)
        self.available_tags.verticalScrollBar().setValue(pos)

    def apply_tags(self, item=None):
        row_indices = list(self.available_tags.selectionModel().selectedRows())
        row_indices.sort(key=lambda r: r.row(), reverse=True)
        if not row_indices:
            text = self.available_filter_input.text()
            if text and text.strip():
                self.add_tag_input.setText(text)
                self.add_tag_input.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        pos = self.available_tags.verticalScrollBar().value()
        tags = self._get_applied_tags_box_contents()
        for item in row_indices:
            tag = item.data()
            tags.append(tag)
            self.available_tags.model().removeRows(item.row(), 1)
        self.available_tags.verticalScrollBar().setValue(pos)

        if not self.is_names:
            tags.sort(key=sort_key)
        self.applied_model.setStringList(tags)

    def _get_applied_tags_box_contents(self):
        return list(self.applied_model.stringList())

    def unapply_tags(self, item=None):
        row_indices = list(self.applied_tags.selectionModel().selectedRows())
        tags = [r.data() for r in row_indices]
        row_indices.sort(key=lambda r: r.row(), reverse=True)
        for item in row_indices:
            self.applied_model.removeRows(item.row(), 1)

        all_tags = self.all_tags_model.stringList() + tags
        all_tags.sort(key=sort_key)
        self.all_tags_model.setStringList(all_tags)

    def add_tag(self):
        tags = str(self.add_tag_input.text()).split(self.sep)
        tags_in_box = self._get_applied_tags_box_contents()
        for tag in tags:
            tag = tag.strip()
            if not tag:
                continue
            if self.all_tags_model.rowCount():
                for index in self.all_tags_model.match(self.all_tags_model.index(0), Qt.ItemDataRole.DisplayRole, tag, -1,
                                                    Qt.MatchFlag.MatchFixedString | Qt.MatchFlag.MatchCaseSensitive | Qt.MatchFlag.MatchWrap):
                    self.all_tags_model.removeRow(index.row())
            if tag not in tags_in_box:
                tags_in_box.append(tag)

        if not self.is_names:
            tags_in_box.sort(key=sort_key)
        self.applied_model.setStringList(tags_in_box)
        self.add_tag_input.setText('')

    def filter_tags(self, filter_value, which='available_tags'):
        collection = getattr(self, which)
        collection.model().setFilterFixedString(filter_value or '')

    def accept(self):
        if self.add_tag_input.text().strip():
            self.add_tag()
        self.tags = self._get_applied_tags_box_contents()
        self.save_state()
        return QDialog.accept(self)

    def reject(self):
        self.save_state()
        return QDialog.reject(self)

    def save_state(self):
        self.save_geometry(gprefs, 'tag_editor_geometry')


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.library import db
    db = db()
    app = Application([])
    d = TagEditor(None, db, current_tags='a b c'.split())

    if d.exec() == QDialog.DialogCode.Accepted:
        print(d.tags)
