#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from contextlib import suppress
from qt.core import (
    QAbstractItemView, QAbstractTableModel, QByteArray, QComboBox, QFontMetrics,
    QFormLayout, QItemSelectionModel, QSlider, QSortFilterProxyModel, Qt, QTableView,
    QWidget
)

from calibre.gui2.widgets import BusyCursor


class VoicesModel(QAbstractTableModel):

    system_default_voice = ('', '', '')

    def __init__(self, voice_data, default_output_module, parent=None):
        super().__init__(parent)
        self.voice_data = voice_data
        try:
            self.current_voices = voice_data[default_output_module]
        except KeyError as e:
            raise ValueError(_('Speech dispatcher on this system is not configured with any available voices. Install some voices first.')) from e
        self.column_headers = (_('Name'), _('Language'), _('Variant'))

    def rowCount(self, parent=None):
        return len(self.current_voices) + 1

    def columnCount(self, parent=None):
        return len(self.column_headers)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.column_headers[section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            row = index.row()
            with suppress(IndexError):
                if row == 0:
                    return (_('System default'), '', '')[index.column()]
                data = self.current_voices[row - 1]
                ans = data[index.column()]
                if not ans or ans == 'none':
                    ans = ''
                return ans
        if role == Qt.ItemDataRole.UserRole:
            row = index.row()
            with suppress(IndexError):
                if row == 0:
                    return self.system_default_voice
                return self.current_voices[row - 1]

    def change_output_module(self, om):
        self.beginResetModel()
        try:
            self.current_voices = self.voice_data[om]
        finally:
            self.endResetModel()

    def index_for_voice(self, v):
        r = 0
        if v != self.system_default_voice:
            try:
                idx = self.current_voices.index(v)
            except Exception:
                return
            r = idx + 1
        return self.index(r, 0)


class Widget(QWidget):

    def __init__(self, tts_client, initial_backend_settings=None, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QFormLayout(self)
        self.tts_client = tts_client

        self.speed = s = QSlider(Qt.Orientation.Horizontal, self)
        s.setTickPosition(QSlider.TickPosition.TicksAbove)
        s.setMinimumWidth(200)
        l.addRow(_('&Speed of speech:'), s)
        s.setRange(self.tts_client.min_rate, self.tts_client.max_rate)
        s.setSingleStep(10)
        s.setTickInterval((s.maximum() - s.minimum()) // 2)

        self.output_modules = om = QComboBox(self)
        with BusyCursor():
            self.voice_data = self.tts_client.get_voice_data()
            self.system_default_output_module = self.tts_client.system_default_output_module
        om.addItem(_('System default'), self.system_default_output_module)
        for x in self.voice_data:
            om.addItem(x, x)
        l.addRow(_('Speech s&ynthesizer:'), om)

        self.voices = v = QTableView(self)
        self.voices_model = VoicesModel(self.voice_data, self.system_default_output_module, parent=v)
        self.proxy_model = p = QSortFilterProxyModel(self)
        p.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        p.setSourceModel(self.voices_model)
        v.setModel(p)
        v.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        v.setSortingEnabled(True)
        h = v.horizontalHeader()
        h.resizeSection(0, QFontMetrics(self.font()).averageCharWidth() * 30)
        v.verticalHeader().close()
        v.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        v.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        om.currentIndexChanged.connect(self.output_module_changed)
        l.addRow(v)

        self.backend_settings = initial_backend_settings or {}

    def restore_state(self, prefs):
        data = prefs.get(f'{self.tts_client.name}-voice-table-state')
        if data is not None:
            self.voices.horizontalHeader().restoreState(QByteArray(data))

    def save_state(self, prefs):
        data = bytearray(self.voices.horizontalHeader().saveState())
        prefs.set(f'{self.tts_client.name}-voice-table-state', data)

    def restore_to_defaults(self):
        self.backend_settings = {}

    def sizeHint(self):
        ans = super().sizeHint()
        ans.setHeight(max(ans.height(), 600))
        return ans

    @property
    def selected_voice(self):
        for x in self.voices.selectedIndexes():
            return x.data(Qt.ItemDataRole.UserRole)

    @selected_voice.setter
    def selected_voice(self, val):
        val = val or VoicesModel.system_default_voice
        idx = self.voices_model.index_for_voice(tuple(val))
        if idx is not None:
            idx = self.proxy_model.mapFromSource(idx)
            self.voices.selectionModel().select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
            self.voices.scrollTo(idx)

    @property
    def selected_output_module(self):
        return self.output_modules.currentData()

    @selected_output_module.setter
    def selected_output_module(self, val):
        if not val:
            self.output_modules.setCurrentIndex(0)
            return
        idx = self.output_modules.findData(val)
        if idx < 0:
            idx = 0
        self.output_modules.setCurrentIndex(idx)

    def output_module_changed(self, idx):
        om = self.selected_output_module
        self.voices_model.change_output_module(om)

    @property
    def rate(self):
        return self.speed.value()

    @rate.setter
    def rate(self, val):
        val = int(val or 0)
        self.speed.setValue(val)

    @property
    def backend_settings(self):
        ans = {}
        om = self.selected_output_module
        if om != self.system_default_output_module:
            ans['output_module'] = om
        voice = self.selected_voice
        if voice and voice != VoicesModel.system_default_voice:
            ans['voice'] = voice
        rate = self.rate
        if rate:
            ans['rate'] = rate
        return ans

    @backend_settings.setter
    def backend_settings(self, val):
        om = val.get('output_module') or self.system_default_output_module
        self.selected_output_module = om
        voice = val.get('voice') or VoicesModel.system_default_voice
        self.selected_voice = voice
        self.rate = val.get('rate') or 0


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.gui2.tts.implementation import Client
    app = Application([])
    c = Client({})
    w = Widget(c, {})
    w.show()
    app.exec()
    print(w.backend_settings)
