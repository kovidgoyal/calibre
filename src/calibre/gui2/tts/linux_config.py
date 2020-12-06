#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from PyQt5.Qt import (
    QAbstractTableModel, QComboBox, QFontMetrics, QFormLayout, Qt, QTableView,
    QWidget
)

from calibre.gui2.preferences.look_feel import BusyCursor


class VoicesModel(QAbstractTableModel):

    def __init__(self, voice_data, default_output_module, parent=None):
        super().__init__(parent)
        self.voice_data = voice_data
        self.current_voices = voice_data[default_output_module]
        self.column_headers = (_('Name'), _('Language'), _('Variant'))

    def rowCount(self, parent=None):
        return len(self.current_voices)

    def columnCount(self, parent=None):
        return 3

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.column_headers[section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            row = index.row()
            try:
                data = self.current_voices[row]
                return data[index.column()]
            except IndexError:
                return

    def change_output_module(self, om):
        self.beginResetModel()
        try:
            self.current_voices = self.voice_data[om]
        finally:
            self.endResetModel()


class Widget(QWidget):

    def __init__(self, tts_client, initial_backend_settings, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QFormLayout(self)
        self.tts_client = tts_client

        self.output_modules = om = QComboBox(self)
        with BusyCursor():
            self.voice_data = self.tts_client.get_voice_data()
            self.system_default_output_module = self.tts_client.system_default_output_module
        om.addItem(_('System default'), self.system_default_output_module)
        l.addRow(_('Speech synthesizer:'), om)

        self.voices = v = QTableView(self)
        self.voices_model = VoicesModel(self.voice_data, self.system_default_output_module, parent=v)
        v.setModel(self.voices_model)
        v.horizontalHeader().resizeSection(0, QFontMetrics(self.font()).averageCharWidth() * 30)
        l.addRow(v)

    def sizeHint(self):
        ans = super().sizeHint()
        ans.setHeight(max(ans.height(), 600))
        return ans
