#!/usr/bin/env python
# License: GPLv3 Copyright: 2020, Charles Haley

from qt.core import (
    QAbstractItemView,
    QColor,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHeaderView,
    QIcon,
    Qt,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
)

from calibre.gui2 import error_dialog, gprefs
from calibre.utils.localization import ngettext


class CountTableWidgetItem(QTableWidgetItem):

    def __init__(self, count):
        QTableWidgetItem.__init__(self, str(count) if count is not None else '0')
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        self.setFlags(self.flags() & ~(Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsEditable))
        self._count = count

    def set_count(self, count):
        self.setText(str(count) if count is not None else '0')


class EnumValuesEdit(QDialog):

    def __init__(self, parent, db, key):
        QDialog.__init__(self, parent)

        self.setWindowTitle(_('Edit permissible values for {0}').format(key))
        self.db = db
        l = QGridLayout()

        bbox = QVBoxLayout()
        bbox.addStretch(10)
        self.del_button = QToolButton()
        self.del_button.setIcon(QIcon.ic('trash.png'))
        self.del_button.setToolTip(_('Remove the currently selected value. Only '
                                     'values with a count of zero can be removed'))
        self.ins_button = QToolButton()
        self.ins_button.setIcon(QIcon.ic('plus.png'))
        self.ins_button.setToolTip(_('Add a new permissible value'))
        self.move_up_button= QToolButton()
        self.move_up_button.setIcon(QIcon.ic('arrow-up.png'))
        self.move_down_button= QToolButton()
        self.move_down_button.setIcon(QIcon.ic('arrow-down.png'))
        bbox.addWidget(self.del_button)
        bbox.addStretch(1)
        bbox.addWidget(self.ins_button)
        bbox.addStretch(1)
        bbox.addWidget(self.move_up_button)
        bbox.addStretch(1)
        bbox.addWidget(self.move_down_button)
        bbox.addStretch(10)
        l.addItem(bbox, 0, 0)

        self.del_button.clicked.connect(self.del_line)

        self.all_colors = {str(s) for s in list(QColor.colorNames())}

        tl = QVBoxLayout()
        l.addItem(tl, 0, 1)
        self.table = t = QTableWidget(parent)
        t.setColumnCount(3)
        t.setRowCount(1)
        t.setHorizontalHeaderLabels([_('Value'), _('Color'), _('Count')])
        t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tl.addWidget(t)

        counts = self.db.new_api.get_usage_count_by_id(key)
        self.name_to_count = {self.db.new_api.get_item_name(key, item_id):count for item_id,count in counts.items()}

        self.key = key
        self.fm = fm = db.field_metadata[key]
        permitted_values = fm.get('display', {}).get('enum_values', '')
        colors = fm.get('display', {}).get('enum_colors', '')
        t.setRowCount(len(permitted_values))
        for i,v in enumerate(permitted_values):
            self.make_name_item(i, v)
            c = self.make_color_combobox(i, -1)
            if colors:
                c.setCurrentIndex(c.findText(colors[i]))
            else:
                c.setCurrentIndex(0)
            self.make_count_item(i, v)

        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.setLayout(l)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(bb, 1, 0, 1, 2)

        self.table.cellChanged.connect(self.cell_changed)
        self.ins_button.clicked.connect(self.ins_button_clicked)
        self.move_down_button.clicked.connect(self.move_down_clicked)
        self.move_up_button.clicked.connect(self.move_up_clicked)
        self.restore_geometry(gprefs, 'enum-values-edit-geometry')

    def cell_changed(self, row, col):
        if col == 0:
            item = self.table.item(row, 2)
            if item is not None and self.table.item(row, 0) is not None:
                count = self.name_to_count.get(self.table.item(row, 0).text())
                item.set_count(count)

    def sizeHint(self):
        sz = QDialog.sizeHint(self)
        sz.setWidth(max(sz.width(), 600))
        sz.setHeight(max(sz.height(), 400))
        return sz

    def make_name_item(self, row, txt):
        it = QTableWidgetItem(txt)
        it.setData(Qt.ItemDataRole.UserRole, txt)
        it.setCheckState(Qt.CheckState.Unchecked)
        it.setToolTip('<p>' + _('Check the box if you change the value and want it renamed in books where it is used') + '</p>')
        self.table.setItem(row, 0, it)

    def make_color_combobox(self, row, dex):
        c = QComboBox(self)
        c.addItem('')
        c.addItems(QColor.colorNames())
        c.setToolTip('<p>' + _('Selects the color of the text when displayed in the book list. '
                               'Either all rows must have a color or no rows have a color') + '</p>')
        self.table.setCellWidget(row, 1, c)
        if dex >= 0:
            c.setCurrentIndex(dex)
        return c

    def make_count_item(self, row, txt):
        it = CountTableWidgetItem(self.name_to_count.get(txt))
        self.table.setItem(row, 2, it)

    def move_up_clicked(self):
        row = self.table.currentRow()
        if row < 0:
            error_dialog(self, _('Select a cell'),
                               _('Select a cell before clicking the button'), show=True)
            return
        if row == 0:
            return
        self.move_row(row, -1)

    def move_row(self, row, direction):
        t = self.table.takeItem(row, 0)
        c = self.table.cellWidget(row, 1).currentIndex()
        count = self.table.takeItem(row, 2)
        self.table.removeRow(row)
        row += direction
        self.table.insertRow(row)
        self.table.setItem(row, 0, t)
        self.make_color_combobox(row, c)
        self.table.setItem(row, 2, count)
        self.table.setCurrentCell(row, 0)

    def move_down_clicked(self):
        row = self.table.currentRow()
        if row < 0:
            error_dialog(self, _('Select a cell'),
                               _('Select a cell before clicking the button'), show=True)
            return
        if row >= self.table.rowCount() - 1:
            return
        self.move_row(row, 1)

    def del_line(self):
        row = self.table.currentRow()
        if row >= 0:
            txt = self.table.item(row, 0).text()
            count = self.name_to_count.get(txt, 0)
            if count > 0:
                error_dialog(self,
                    _('Cannot remove value "{}"').format(txt),
                    ngettext('The value "{0}" is used in {1} book and cannot be removed.',
                             'The value "{0}" is used in {1} books and cannot be removed.',
                             count).format(txt, count),
                    show=True)
                return
            self.table.removeRow(self.table.currentRow())

    def ins_button_clicked(self):
        row = self.table.currentRow()
        if row < 0:
            error_dialog(self, _('Select a cell'),
                               _('Select a cell before clicking the button'), show=True)
            return
        self.table.insertRow(row)
        self.make_name_item(row, '')
        self.make_color_combobox(row, -1)
        self.make_count_item(row, '')

    def save_geometry(self):
        super().save_geometry(gprefs, 'enum-values-edit-geometry')

    def accept(self):
        disp = self.fm['display']
        values = []
        colors = []
        id_map = {}
        for i in range(0, self.table.rowCount()):
            it = self.table.item(i, 0)
            v = str(it.text())
            if not v:
                error_dialog(self, _('Empty value'),
                                   _('Empty values are not allowed'), show=True)
                return
            ov = str(it.data(Qt.ItemDataRole.UserRole))
            if v != ov and it.checkState() == Qt.CheckState.Checked:
                fid = self.db.new_api.get_item_id(self.key, ov)
                id_map[fid] = v
            values.append(v)
            c = str(self.table.cellWidget(i, 1).currentText())
            if c:
                colors.append(c)

        l_lower = [v.lower() for v in values]
        for i,v in enumerate(l_lower):
            if v in l_lower[i+1:]:
                error_dialog(self, _('Duplicate value'),
                                   _('The value "{0}" is in the list more than '
                                     'once, perhaps with different case').format(values[i]),
                             show=True)
                return

        if colors and len(colors) != len(values):
            error_dialog(self, _('Invalid colors specification'), _(
                'Either all values or no values must have colors'), show=True)
            return

        disp['enum_values'] = values
        disp['enum_colors'] = colors
        self.db.set_custom_column_metadata(self.fm['colnum'], display=disp,
                                           update_last_modified=True)
        if id_map:
            self.db.new_api.rename_items(self.key, id_map)
        self.save_geometry()
        return QDialog.accept(self)

    def reject(self):
        self.save_geometry()
        return QDialog.reject(self)
