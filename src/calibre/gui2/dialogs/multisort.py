#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import (
    QAbstractItemView, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QSize, Qt,
    QVBoxLayout
)

from calibre import prepare_string_for_xml
from calibre.gui2 import error_dialog
from calibre.gui2.actions.sort import SORT_HIDDEN_PREF
from calibre.gui2.widgets2 import Dialog
from calibre.utils.icu import primary_sort_key

ascending_symbol = '⏷'
descending_symbol = '⏶'


class ChooseMultiSort(Dialog):

    def __init__(self, db, is_device_connected=False, parent=None, hidden_pref=SORT_HIDDEN_PREF):
        self.db = db.new_api
        self.hidden_fields = set(self.db.pref(SORT_HIDDEN_PREF, default=()) or ())
        if not is_device_connected:
            self.hidden_fields.add('ondevice')
        fm = self.db.field_metadata
        self.key_map = fm.ui_sortable_field_keys().copy()
        self.name_map = {v:k for k, v in self.key_map.items()}
        self.all_names = sorted(self.name_map, key=primary_sort_key)
        self.sort_order_map = dict.fromkeys(self.key_map, True)
        super().__init__(_('Sort by multiple columns'), 'multisort-chooser', parent=parent)

    def sizeHint(self):
        return QSize(600, 400)

    def setup_ui(self):
        self.vl = vl = QVBoxLayout(self)
        self.hl = hl = QHBoxLayout()
        self.la = la = QLabel(_(
            'Pick multiple columns to sort by. Drag and drop to re-arrange. Higher columns are more important.'
            ' Ascending or descending order can be toggled by clicking the column name at the bottom'
            ' of this dialog, after having selected it.'))
        la.setWordWrap(True)
        vl.addWidget(la)
        vl.addLayout(hl)
        self.order_label = la = QLabel('')
        la.setTextFormat(Qt.TextFormat.RichText)
        la.setWordWrap(True)
        la.linkActivated.connect(self.link_activated)
        vl.addWidget(la)
        vl.addWidget(self.bb)

        self.column_list = cl = QListWidget(self)
        hl.addWidget(cl)
        for name in self.all_names:
            i = QListWidgetItem(cl)
            i.setText(name)
            i.setData(Qt.ItemDataRole.UserRole, self.name_map[name])
            cl.addItem(i)
            i.setCheckState(Qt.CheckState.Unchecked)
            if self.name_map[name] in self.hidden_fields:
                i.setHidden(True)
        cl.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        cl.currentRowChanged.connect(self.current_changed)
        cl.itemDoubleClicked.connect(self.item_double_clicked)
        cl.setCurrentRow(0)
        cl.itemChanged.connect(self.update_order_label)
        cl.model().rowsMoved.connect(self.update_order_label)

    def item_double_clicked(self, item):
        cs = item.checkState()
        item.setCheckState(Qt.CheckState.Checked if cs == Qt.CheckState.Unchecked else Qt.CheckState.Unchecked)

    def current_changed(self):
        self.update_order_label()

    @property
    def current_sort_spec(self):
        ans = []
        cl = self.column_list
        for item in (cl.item(r) for r in range(cl.count())):
            if item.checkState() == Qt.CheckState.Checked:
                k = item.data(Qt.ItemDataRole.UserRole)
                ans.append((k, self.sort_order_map[k]))
        return ans

    def update_order_label(self):
        t = ''
        for i, (k, ascending) in enumerate(self.current_sort_spec):
            name = self.key_map[k]
            symbol = ascending_symbol if ascending else descending_symbol
            if i != 0:
                t += ' :: '
            q = bytes.hex(k.encode('utf-8'))
            dname = prepare_string_for_xml(name).replace(" ", "&nbsp;")
            t += f' <a href="{q}" style="text-decoration: none">{dname}&nbsp;{symbol}</a>'
        if t:
            t = _('Effective sort') + ': ' + t
        self.order_label.setText(t)

    def link_activated(self, url):
        key = bytes.fromhex(url).decode('utf-8')
        self.sort_order_map[key] ^= True
        self.update_order_label()

    def accept(self):
        if not self.current_sort_spec:
            return error_dialog(self, _('No sort selected'), _(
                'You must select at least one column on which to sort'), show=True)
        super().accept()


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    from calibre.library import db
    d = ChooseMultiSort(db())
    d.exec_()
    print(d.current_sort_spec)
    del d
    del app
