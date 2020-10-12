

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt5.Qt import Qt, QDialog, QAbstractItemView, QApplication

from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.dialogs.tag_editor_ui import Ui_TagEditor
from calibre.gui2 import question_dialog, error_dialog, gprefs
from calibre.constants import islinux
from calibre.utils.icu import sort_key, primary_contains
from polyglot.builtins import unicode_type, range


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
            for tag in tags:
                self.applied_tags.addItem(tag)
        else:
            tags = []

        if self.is_names:
            self.applied_tags.setDragDropMode(QAbstractItemView.InternalMove)
            self.applied_tags.setSelectionMode(QAbstractItemView.ExtendedSelection)

        if key:
            all_tags = [tag for tag in self.db.all_custom(label=key)]
        else:
            all_tags = [tag for tag in self.db.all_tags()]
        all_tags = sorted(set(all_tags), key=sort_key)
        q = set(tags)
        for tag in all_tags:
            if tag not in q:
                self.available_tags.addItem(tag)

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

        if islinux:
            self.available_tags.itemDoubleClicked.connect(self.apply_tags)
        else:
            self.available_tags.itemActivated.connect(self.apply_tags)
        self.applied_tags.itemActivated.connect(self.unapply_tags)

        geom = gprefs.get('tag_editor_geometry', None)
        if geom is not None:
            QApplication.instance().safe_restore_geometry(self, geom)

    def edit_box_changed(self, which):
        gprefs['tag_editor_last_filter'] = which

    def delete_tags(self, item=None):
        confirms, deletes = [], []
        items = self.available_tags.selectedItems() if item is None else [item]
        if not items:
            error_dialog(self, 'No tags selected', 'You must select at least one tag from the list of Available tags.').exec_()
            return
        if not confirm(
            _('Deleting tags is done immediately and there is no undo.'),
            'tag_editor_delete'):
            return
        pos = self.available_tags.verticalScrollBar().value()
        for item in items:
            used = self.db.is_tag_used(unicode_type(item.text())) \
                if self.key is None else \
                self.db.is_item_used_in_multiple(unicode_type(item.text()), label=self.key)
            if used:
                confirms.append(item)
            else:
                deletes.append(item)
        if confirms:
            ct = ', '.join([unicode_type(item.text()) for item in confirms])
            if question_dialog(self, _('Are your sure?'),
                '<p>'+_('The following tags are used by one or more books. '
                    'Are you certain you want to delete them?')+'<br>'+ct):
                deletes += confirms

        for item in deletes:
            if self.key is None:
                self.db.delete_tag(unicode_type(item.text()))
            else:
                bks = self.db.delete_item_from_multiple(unicode_type(item.text()),
                                                        label=self.key)
                self.db.refresh_ids(bks)
            self.available_tags.takeItem(self.available_tags.row(item))
        self.available_tags.verticalScrollBar().setValue(pos)

    def apply_tags(self, item=None):
        items = self.available_tags.selectedItems() if item is None else [item]
        rows = [self.available_tags.row(i) for i in items]
        if not rows:
            return
        row = max(rows)
        tags = self._get_applied_tags_box_contents()
        for item in items:
            tag = unicode_type(item.text())
            tags.append(tag)
            self.available_tags.takeItem(self.available_tags.row(item))

        if not self.is_names:
            tags.sort(key=sort_key)
        self.applied_tags.clear()
        for tag in tags:
            self.applied_tags.addItem(tag)

        if row >= self.available_tags.count():
            row = self.available_tags.count() - 1

        if row > 2:
            item = self.available_tags.item(row)
            self.available_tags.scrollToItem(item)

        # use the filter again when the applied tags were changed
        self.filter_tags(self.applied_filter_input.text(), which='applied_tags')

    def _get_applied_tags_box_contents(self):
        tags = []
        for i in range(0, self.applied_tags.count()):
            tags.append(unicode_type(self.applied_tags.item(i).text()))
        return tags

    def unapply_tags(self, item=None):
        tags = self._get_applied_tags_box_contents()
        items = self.applied_tags.selectedItems() if item is None else [item]
        for item in items:
            tag = unicode_type(item.text())
            tags.remove(tag)
            self.available_tags.addItem(tag)

        if not self.is_names:
            tags.sort(key=sort_key)
        self.applied_tags.clear()
        for tag in tags:
            self.applied_tags.addItem(tag)

        items = [unicode_type(self.available_tags.item(x).text()) for x in
                range(self.available_tags.count())]
        items.sort(key=sort_key)
        self.available_tags.clear()
        for item in items:
            self.available_tags.addItem(item)

        # use the filter again when the applied tags were changed
        self.filter_tags(self.applied_filter_input.text(), which='applied_tags')
        self.filter_tags(self.available_filter_input.text())

    def add_tag(self):
        tags = unicode_type(self.add_tag_input.text()).split(self.sep)
        tags_in_box = self._get_applied_tags_box_contents()
        for tag in tags:
            tag = tag.strip()
            if not tag:
                continue
            for item in self.available_tags.findItems(tag, Qt.MatchFixedString):
                self.available_tags.takeItem(self.available_tags.row(item))
            if tag not in tags_in_box:
                tags_in_box.append(tag)

        if not self.is_names:
            tags_in_box.sort(key=sort_key)
        self.applied_tags.clear()
        for tag in tags_in_box:
            self.applied_tags.addItem(tag)

        self.add_tag_input.setText('')
        # use the filter again when the applied tags were changed
        self.filter_tags(self.applied_filter_input.text(), which='applied_tags')

    # filter tags
    def filter_tags(self, filter_value, which='available_tags'):
        collection = getattr(self, which)
        q = icu_lower(unicode_type(filter_value))
        for i in range(collection.count()):  # on every available tag
            item = collection.item(i)
            item.setHidden(bool(q and not primary_contains(q, unicode_type(item.text()))))

    def accept(self):
        self.tags = self._get_applied_tags_box_contents()
        self.save_state()
        return QDialog.accept(self)

    def reject(self):
        self.save_state()
        return QDialog.reject(self)

    def save_state(self):
        gprefs['tag_editor_geometry'] = bytearray(self.saveGeometry())


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.library import db
    db = db()
    app = Application([])
    d = TagEditor(None, db, current_tags='a b c'.split())
    if d.exec_() == d.Accepted:
        print(d.tags)
