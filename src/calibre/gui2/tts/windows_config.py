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

    system_default_voice = ''

    def __init__(self, voice_data, parent=None):
        super().__init__(parent)
        self.voice_data = voice_data

        def language(x):
            return x.get('language_display_name') or x['language'] or ''

        self.current_voices = tuple((x['name'], language(x), x.get('age', ''), x.get('gender', ''), x['id']) for x in voice_data)
        self.column_headers = _('Name'), _('Language'), _('Age'), _('Gender')

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
                    return (_('System default'), '', '', '')[index.column()]
                data = self.current_voices[row - 1]
                col = index.column()
                ans = data[col] or ''
                return ans
        if role == Qt.ItemDataRole.UserRole:
            row = index.row()
            with suppress(IndexError):
                if row == 0:
                    return self.system_default_voice
                return self.current_voices[row - 1][4]

    def index_for_voice(self, v):
        r = 0
        if v != self.system_default_voice:
            for i, x in enumerate(self.current_voices):
                if x[4] == v:
                    r = i + 1
                    break
            else:
                return
        return self.index(r, 0)


class Widget(QWidget):

    def __init__(self, tts_client, initial_backend_settings=None, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QFormLayout(self)
        self.tts_client = tts_client

        with BusyCursor():
            self.voice_data = self.tts_client.get_voice_data()
            self.default_system_rate = self.tts_client.default_system_rate
            self.all_sound_outputs = self.tts_client.get_sound_outputs()

        self.speed = s = QSlider(Qt.Orientation.Horizontal, self)
        s.setMinimumWidth(200)
        l.addRow(_('&Speed of speech (words per minute):'), s)
        s.setRange(self.tts_client.min_rate, self.tts_client.max_rate)
        s.setSingleStep(1)
        s.setPageStep(2)

        self.voices = v = QTableView(self)
        self.voices_model = VoicesModel(self.voice_data, parent=v)
        self.proxy_model = p = QSortFilterProxyModel(self)
        p.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        p.setSourceModel(self.voices_model)
        v.setModel(p)
        v.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        v.setSortingEnabled(True)
        v.horizontalHeader().resizeSection(0, QFontMetrics(self.font()).averageCharWidth() * 25)
        v.horizontalHeader().resizeSection(1, QFontMetrics(self.font()).averageCharWidth() * 30)
        v.verticalHeader().close()
        v.verticalHeader().close()
        v.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        v.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        l.addRow(v)

        self.sound_outputs = so = QComboBox(self)
        so.addItem(_('System default'), '')
        for x in self.all_sound_outputs:
            so.addItem(x.get('description') or x['id'], x['id'])
        l.addRow(_('Sound output:'), so)

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
        ans.setWidth(max(ans.width(), 500))
        return ans

    @property
    def selected_voice(self):
        for x in self.voices.selectedIndexes():
            return x.data(Qt.ItemDataRole.UserRole)

    @selected_voice.setter
    def selected_voice(self, val):
        val = val or VoicesModel.system_default_voice
        idx = self.voices_model.index_for_voice(val)
        if idx is not None:
            idx = self.proxy_model.mapFromSource(idx)
            self.voices.selectionModel().select(idx, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)
            self.voices.scrollTo(idx)

    @property
    def rate(self):
        return self.speed.value()

    @rate.setter
    def rate(self, val):
        val = int(val or self.default_system_rate)
        self.speed.setValue(val)

    @property
    def sound_output(self):
        return self.sound_outputs.currentData()

    @sound_output.setter
    def sound_output(self, val):
        val = val or ''
        idx = 0
        if val:
            q = self.sound_outputs.findData(val)
            if q > -1:
                idx = q
        self.sound_outputs.setCurrentIndex(idx)

    @property
    def backend_settings(self):
        ans = {}
        voice = self.selected_voice
        if voice and voice != VoicesModel.system_default_voice:
            ans['voice'] = voice
        rate = self.rate
        if rate and rate != self.default_system_rate:
            ans['rate'] = rate
        so = self.sound_output
        if so:
            ans['sound_output'] = so
        return ans

    @backend_settings.setter
    def backend_settings(self, val):
        voice = val.get('voice') or VoicesModel.system_default_voice
        self.selected_voice = voice
        self.rate = val.get('rate') or self.default_system_rate
        self.sound_output = val.get('sound_output') or ''


def develop():
    from calibre.gui2 import Application
    from calibre.gui2.tts.implementation import Client
    app = Application([])
    c = Client()
    w = Widget(c, {})
    w.show()
    app.exec()
    print(w.backend_settings)


if __name__ == '__main__':
    develop()
