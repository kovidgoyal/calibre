#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

from qt.core import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QIcon,
    QLabel,
    QLocale,
    QMediaDevices,
    QPushButton,
    QSize,
    QSlider,
    Qt,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre.gui2.tts.types import (
    AudioDeviceId,
    EngineMetadata,
    EngineSpecificSettings,
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
        am = available_engines()
        ec.addItem(_('Automatically select (currently {})').format(am[default_engine_name()].human_name), '')
        for engine_name, metadata in am.items():
            ec.addItem(metadata.human_name, engine_name)
        idx = ec.findData(configured_engine_name)
        if idx > -1:
            ec.setCurrentIndex(idx)
        self.engine_description = la = QLabel(self)
        la.setWordWrap(True)
        l.addRow(la)
        ec.currentIndexChanged.connect(self.current_changed)
        self.update_description()

    @property
    def value(self) -> str:
        return self.engine_choice.currentData()

    def current_changed(self):
        self.changed.emit(self.value)
        self.update_description()

    def update_description(self):
        engine = self.value or default_engine_name()
        metadata = available_engines()[engine]
        self.engine_description.setText(metadata.description)


class FloatSlider(QSlider):

    def __init__(self, minimum: float = -1, maximum: float = 1, factor: int = 10, parent=None):
        super().__init__(parent)
        self.factor = factor
        self.setRange(int(minimum * factor), int(maximum * factor))
        self.setSingleStep(int((self.maximum() - self.minimum()) / (2 * factor)))
        self.setPageStep(5 * self.singleStep())
        self.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.setOrientation(Qt.Orientation.Horizontal)
        if maximum - minimum >= 2:
            self.setTickInterval((self.maximum() - self.minimum()) // 2)
        else:
            self.setTickInterval(self.maximum() - self.minimum())

    def sizeHint(self) -> QSize:
        ans = super().sizeHint()
        ans.setWidth(ans.width() * 2)
        return ans

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
        l.setContentsMargins(0, 0, 0, 0)
        self.system = e = QCheckBox(_('Use system default volume'), self)
        l.addRow(e)
        self.vol = v = FloatSlider(minimum=0, parent=self)
        l.addRow(_('&Volume of speech:'), v)
        e.toggled.connect(self.update_state)
        self.update_state()

    def update_state(self):
        self.layout().setRowVisible(self.vol, not self.system.isChecked())

    @property
    def val(self):
        if self.system.isChecked():
            return None
        return self.vol.val

    @val.setter
    def val(self, v):
        self.system.setChecked(v is None)
        self.vol.val = 0.5 if v is None else v


class Voices(QTreeWidget):

    voice_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.system_default_voice = Voice()
        self.currentItemChanged.connect(self.voice_changed)

    def sizeHint(self) -> QSize:
        return QSize(400, 500)

    def set_voices(self, all_voices: tuple[Voice, ...], current_voice: str, engine_metadata: EngineMetadata) -> None:
        self.clear()
        current_item = None
        def qv(parent, voice):
            nonlocal current_item
            ans = QTreeWidgetItem(parent, [voice.short_text(engine_metadata)])
            ans.setData(0, Qt.ItemDataRole.UserRole, voice)
            ans.setToolTip(0, voice.tooltip(engine_metadata))
            if current_voice == voice.name:
                current_item = ans
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
                parent_map[langcode] = parent = QTreeWidgetItem(self.invisibleRootItem(), [lang(langcode)])
                parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            for voice in vmap[langcode]:
                qv(parent, voice)
        if current_item is not None:
            self.setCurrentItem(current_item)

    @property
    def val(self) -> str:
        voice = self.current_voice
        return voice.name if voice else ''

    @property
    def current_voice(self) -> Voice | None:
        ci = self.currentItem()
        if ci is not None:
            return ci.data(0, Qt.ItemDataRole.UserRole)


class EngineSpecificConfig(QWidget):

    voice_changed = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        self.engine_name = ''
        self.l = l = QFormLayout(self)
        devs = QMediaDevices.audioOutputs()
        dad = QMediaDevices.defaultAudioOutput()
        self.all_audio_devices = [AudioDeviceId(bytes(x.id()), x.description()) for x in devs]
        self.default_audio_device = AudioDeviceId(bytes(dad.id()), dad.description())
        self.output_module = om = QComboBox(self)
        l.addRow(_('&Output module:'), om)
        self.engine_name = ''
        om.currentIndexChanged.connect(self.rebuild_voices)
        self.default_output_modules = {}
        self.voice_data = {}
        self.engine_specific_settings = {}
        self.rate = r = FloatSlider(parent=self)
        l.addRow(_('&Speed of speech:'), r)
        self.pitch = p = FloatSlider(parent=self)
        l.addRow(_('&Pitch of speech:'), p)
        self.volume = v = Volume(self)
        l.addRow(v)
        self.audio_device = ad = QComboBox(self)
        l.addRow(_('Output a&udio to:'), ad)
        self.voices = v = Voices(self)
        v.voice_changed.connect(self.voice_changed)
        la = QLabel(_('V&oices:'))
        la.setBuddy(v)
        l.addRow(la)
        l.addRow(v)

    def set_engine(self, engine_name):
        engine_name = engine_name or default_engine_name()
        if self.engine_name and self.engine_name != engine_name:
            self.engine_specific_settings[self.engine_name] = self.as_settings()
        self.engine_name = engine_name
        metadata = available_engines()[engine_name]
        tts = create_tts_backend(force_engine=engine_name)
        if engine_name not in self.voice_data:
            self.voice_data[engine_name] = tts.available_voices
            self.engine_specific_settings[engine_name] = EngineSpecificSettings.create_from_config(engine_name)
            self.default_output_modules[engine_name] = tts.default_output_module
        self.output_module.blockSignals(True)
        self.output_module.clear()
        if metadata.has_multiple_output_modules:
            self.layout().setRowVisible(self.output_module, True)
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
        if metadata.can_change_pitch:
            self.pitch.val = s.pitch
            self.layout().setRowVisible(self.pitch, True)
        else:
            self.pitch.val = 0
            self.layout().setRowVisible(self.pitch, False)
        self.layout().setRowVisible(self.pitch, metadata.can_change_pitch)
        if metadata.can_change_volume:
            self.layout().setRowVisible(self.volume, True)
            self.volume.val = s.volume
        else:
            self.layout().setRowVisible(self.volume, False)
            self.volume.val = None
        self.audio_device.clear()
        if metadata.allows_choosing_audio_device:
            self.audio_device.addItem(_('System default (currently {})').format(self.default_audio_device.description), '')
            for ad in self.all_audio_devices:
                self.audio_device.addItem(ad.description, ad.id.hex())
            if cad := self.engine_specific_settings[engine_name].audio_device_id:
                if (idx := self.audio_device.findData(cad.id.hex())):
                    self.audio_device.setCurrentIndex(idx)
            self.layout().setRowVisible(self.audio_device, True)
        else:
            self.layout().setRowVisible(self.audio_device, False)
        self.rebuild_voices()
        return metadata

    def rebuild_voices(self):
        try:
            s = self.engine_specific_settings[self.engine_name]
        except KeyError:
            return
        metadata = available_engines()[self.engine_name]
        output_module = self.output_module.currentData() or ''
        if metadata.has_multiple_output_modules:
            output_module = output_module or self.default_output_modules[self.engine_name]
        all_voices = self.voice_data[self.engine_name][output_module]
        self.voices.set_voices(all_voices, s.voice_name, metadata)

    def as_settings(self) -> EngineSpecificSettings:
        ans = EngineSpecificSettings(
            engine_name=self.engine_name,
            rate=self.rate.val, voice_name=self.voices.val, pitch=self.pitch.val, volume=self.volume.val)
        metadata = available_engines()[self.engine_name]
        if metadata.has_multiple_output_modules and self.output_module.currentIndex() > 0:
            ans = ans._replace(output_module=self.output_module.currentData())
        if metadata.allows_choosing_audio_device and self.audio_device.currentIndex() > 0:
            aid = bytes.fromhex(self.audio_device.currentData())
            for ad in self.all_audio_devices:
                if ad.id == aid:
                    ans = ans._replace(audio_device_id=ad)
                    break
        return ans

    def voice_action(self):
        v = self.voices.current_voice
        if v is None:
            return
        metadata = available_engines()[self.engine_name]
        if not metadata.has_managed_voices:
            return
        tts = create_tts_backend(self.engine_name)
        if tts.is_voice_downloaded(v):
            tts.delete_voice(v)
        else:
            tts.download_voice(v)

    def current_voice_is_downloaded(self) -> bool:
        v = self.voices.current_voice
        if v is None:
            return False
        metadata = available_engines()[self.engine_name]
        if not metadata.has_managed_voices:
            return False
        tts = create_tts_backend(self.engine_name)
        return tts.is_voice_downloaded(v)


class ConfigDialog(Dialog):

    def __init__(self, parent=None):
        super().__init__(_('Configure Read aloud'), 'configure-read-aloud2', parent=parent)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.engine_choice = ec = EngineChoice(self)
        self.engine_specific_config = esc = EngineSpecificConfig(self)
        ec.changed.connect(self.set_engine)
        esc.voice_changed.connect(self.update_voice_button)
        l.addWidget(ec)
        l.addWidget(esc)
        self.voice_button = b = QPushButton(self)
        b.clicked.connect(self.voice_action)
        h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(b), h.addStretch(10), h.addWidget(self.bb)
        self.initial_engine_choice = ec.value
        self.set_engine(self.initial_engine_choice)

    def set_engine(self, engine_name: str) -> None:
        metadata = self.engine_specific_config.set_engine(engine_name)
        self.voice_button.setVisible(metadata.has_managed_voices)
        self.update_voice_button()

    def update_voice_button(self):
        b = self.voice_button
        if self.engine_specific_config.current_voice_is_downloaded():
            b.setIcon(QIcon.ic('trash.png'))
            b.setText(_('Remove downloaded voice'))
        else:
            b.setIcon(QIcon.ic('download-metadata.png'))
            b.setText(_('Download voice'))

    def voice_action(self):
        self.engine_specific_config.voice_action()
        self.update_voice_button()

    @property
    def engine_changed(self) -> bool:
        return self.engine_choice.value != self.initial_engine_choice

    def accept(self):
        engine_name = self.engine_choice.value
        tts = create_tts_backend(engine_name)
        s = self.engine_specific_config.as_settings()
        if not tts.validate_settings(s, self):
            return
        prefs = load_config()
        with prefs:
            if engine_name:
                prefs['engine'] = engine_name
            else:
                prefs.pop('engine', None)
            s.save_to_config(prefs)
        super().accept()


def develop():
    from calibre.gui2 import Application
    app = Application([])
    d = ConfigDialog()
    d.exec()
    del d
    del app


if __name__ == '__main__':
    develop()
