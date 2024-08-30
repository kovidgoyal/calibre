#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>


from qt.core import QCheckBox, QFormLayout, QLabel, QLocale, QSize, QSlider, Qt, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, pyqtSignal

from calibre.gui2.tts2.types import (
    EngineMetadata,
    EngineSpecificSettings,
    TrackingCapability,
    Voice,
    available_engines,
    create_tts_backend,
    default_engine_name,
    load_config,
)
from calibre.gui2.widgets2 import Dialog, QComboBox


class EngineChoice(QWidget):

    changed = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.l = l = QFormLayout(self)
        self.engine_choice = ec = QComboBox(self)
        l.addRow(_('Text-to-Speech &engine:'), ec)
        configured_engine_name = load_config().get('engine', '')
        l.addItem(_('Automatically select (currently {})').format(default_engine_name()), '')
        for engine_name in available_engines():
            l.addItem(engine_name)
        idx = ec.findData(configured_engine_name)
        if idx > -1:
            ec.setCurrentIndex(idx)
        self.engine_description = la = QLabel(self)
        la.setWordWrap(True)
        l.addWidget(la)
        ec.currentIndexChanged.connect(self.current_changed)
        self.update_description()

    @property
    def value(self) -> str:
        return self.engine_choice.currentData()

    def current_changed(self):
        self.changed.emit(self.value)
        self.update_description(self)

    def update_description(self):
        engine = self.value or default_engine_name()
        metadata = available_engines()[engine]
        if metadata.tracking_capability is TrackingCapability.NoTracking:
            text = _('The {} engine does not highlight words on the screen as they are spoken')
        elif metadata.tracking_capability is TrackingCapability.WordByWord:
            text = _('The {} engine highlights words on the screen as they are spoken')
        else:
            text = _('The {} engine highlights sentences on the screen as they are spoken')
        self.engine_description.setText(text)


class FloatSlider(QSlider):

    def __init__(self, minimum: float = -1, maximum: float = 1, factor: int = 10, parent=None):
        QSlider.__init__(parent)
        self.setRange(int(minimum * factor), int(maximum * factor))
        self.setSingleStep(int((self.maximum() - self.minimum()) / (2 * factor)))
        self.setPageStep(5 * self.singleStep())
        self.setTicksPosition(QSlider.TickPosition.TicksBelow)
        if maximum - minimum >= 2:
            self.setTickInterval((self.maximum() - self.minimum()) // 2)
        else:
            self.setTickInterval(self.maximum() - self.minimum())
        self.factor = factor

    @property
    def val(self) -> float:
        return self.value() / self.factor

    @val.setter
    def val(self, v) -> None:
        self.setValue(int(v * self.factor))


class Volume(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.l = l = QFormLayout(self)
        self.system = e = QCheckBox(_('Use system default volume'), self)
        l.addWidget(e)
        self.vol = v = FloatSlider(minimum=0, parent=self)
        l.addRow(_('&Volume of speech'), v)
        self.e.toggled.connect(self.update_state)
        self.update_state()

    def update_state(self):
        self.vol.setEnabled(not self.system.isChecked())

    @property
    def val(self):
        if self.system.isChecked():
            return None
        return self.vol.val

    @val.setter
    def val(self, v):
        self.system.setChecked(v is None)
        if v is not None:
            self.vol.val = v


class Voices(QTreeWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.system_default_voice = Voice()

    def sizeHint(self) -> QSize:
        return QSize(400, 600)

    def set_voices(self, all_voices: tuple[Voice, ...], current_voice: str, engine_metadata: EngineMetadata) -> None:
        self.clear()
        def qv(parent, voice):
            ans = QTreeWidgetItem(parent, voice.short_text)
            ans.setData(0, Qt.ItemDataRole.UserRole, voice)
            return ans
        qv(self.invisibleRootItem(), self.system_default_voice)
        vmap = {}
        for v in all_voices:
            vmap.setdefault(v.language_code, []).append(v)
        for vs in vmap.values():
            vs.sort(key=lambda v: v.sort_key())
        parent_map = {}
        def lang(langcode):
            return QLocale.languageToString(QLocale.codeToLanguage(langcode))

        for langcode in sorted(vmap, key=lambda lc: lang(lc).lower()):
            parent = parent_map.get(langcode)
            if parent is None:
                parent_map[langcode] = parent = QTreeWidgetItem(self.invisibleRootItem(), lang(langcode))
            for voice in vmap[langcode]:
                qv(parent, voice)


class EngineSpecificConfig(QWidget):

    def __init__(self, parent):
        super().__init__(parent)
        self.l = l = QFormLayout(self)
        self.output_module = om = QComboBox(self)
        l.addRow(_('&Output module:'), om)
        self.engine_name = ''
        om.currentIndexChanged.connect(self.rebuild_voices)
        self.engine_instances = {}
        self.voice_data = {}
        self.engine_specific_settings = {}
        self.rate = r = FloatSlider(parent=self)
        l.addRow(_('&Speed of speech:'), r)
        self.pitch = p = FloatSlider(parent=self)
        l.addRow(_('&Pitch of speech:'), p)
        self.volume = v = Volume(self)
        l.addWidget(v)
        self.voices = v = Voices(self)
        la = QLabel(_('V&oices:'))
        la.setBuddy(v)
        l.addWidget(la)
        l.addWidget(v)

    def set_engine(self, engine_name):
        self.engine_name = engine_name
        metadata = available_engines()[engine_name]
        if engine_name not in self.engine_instances:
            self.engine_instances[engine_name] = tts = create_tts_backend(force_engine=engine_name)
            self.voice_data[engine_name] = tts.available_voices
            self.engine_specific_settings[engine_name] = EngineSpecificSettings.create_from_config(engine_name)
        else:
            tts = self.engine_instances[engine_name]
        self.output_module.blockSignals(True)
        self.output_module.clear()
        if metadata.has_multiple_output_modules and len(self.voice_data[engine_name]) > 1:
            self.output_module.setVisible(True)
            self.layout().setRowVisible(self.output_module, True)
            self.output_module.clear()
            self.output_module.addItem(_('System default (currently {})').format(tts.default_output_module), '')
            for om in self.voice_data[engine_name]:
                self.output_module.addItem(om, om)
            if (idx := self.output_module.findData(self.engine_specific_settings[engine_name].output_module)) > -1:
                self.output_module.setCurrentIndex(idx)
        else:
            self.layout().setRowVisible(self.output_module, False)
        self.output_module.blockSignals(False)
        try:
            s = self.engine_specific_settings[self.engine_name]
        except KeyError:
            return
        self.rate.val = s.rate
        self.pitch.val = s.pitch
        self.layout().setRowVisible(self.pitch, metadata.can_change_pitch)
        self.volume.val = s.volume
        self.rebuild_voice_table()

    def rebuild_voices(self):
        try:
            s = self.engine_specific_settings[self.engine_name]
        except KeyError:
            return
        metadata = available_engines()[self.engine_name]
        output_module = self.output_module.currentData()
        if metadata.has_multiple_output_modules:
            output_module = output_module or self.engine_instances.default_output_module
        all_voices = self.voice_data[self.engine_name][output_module]
        self.voices.set_voices(all_voices, s.voice_name, metadata)


class ConfigDialog(Dialog):

    def __init__(self, current_tts_backend, parent=None):
        self.current_tts_backend = current_tts_backend
        super().__init__(_('Configure Read aloud'), 'configure-read-aloud2', parent=parent)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.engine_choice = ec = EngineChoice(self)
        l.addWidget(ec)
