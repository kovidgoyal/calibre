#!/usr/bin/env python
# License: GPLv3 Copyright: 2024, Kovid Goyal <kovid at kovidgoyal.net>

from qt.core import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFont,
    QFormLayout,
    QHBoxLayout,
    QIcon,
    QLabel,
    QLocale,
    QMediaDevices,
    QPushButton,
    QSize,
    QSlider,
    QStyle,
    QStyleOptionViewItem,
    Qt,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre.gui2.tts.types import (
    TTS_EMBEDED_CONFIG,
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


class SentenceDelay(QDoubleSpinBox):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0., 2.)
        self.setDecimals(2)
        self.setSuffix(_(' seconds'))
        self.setToolTip(_('The number of seconds to pause for at the end of a sentence.'))
        self.setSpecialValueText(_('no pause'))
        self.setSingleStep(0.05)

    @property
    def val(self) -> str:
        return max(0.0, self.value())

    @val.setter
    def val(self, v) -> None:
        self.setValue(float(v))


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

    def __init__(self, parent=None, for_embedding=False):
        self.for_embedding = for_embedding
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.system_default_voice = Voice()
        self.currentItemChanged.connect(self.voice_changed)
        self.normal_font = f = self.font()
        self.highlight_font = f = QFont(f)
        f.setBold(True), f.setItalic(True)
        self.ignore_item_changes = False
        if self.for_embedding:
            self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
            self.itemChanged.connect(self.item_changed)

    def item_changed(self, item: QTreeWidgetItem, column: int):
        if column == 0 and item.parent() is not self.invisibleRootItem() and not self.ignore_item_changes:
            if item.checkState(0) == Qt.CheckState.Checked:
                p = item.parent()
                for child in (p.child(i) for i in range(p.childCount())):
                    if child is not item and child.checkState(0) == Qt.CheckState.Checked:
                        self.ignore_item_changes = True
                        child.setCheckState(0, Qt.CheckState.Unchecked)
                        self.ignore_item_changes = False

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if self.for_embedding and item and item.parent() is not self.invisibleRootItem():
            rect = self.visualItemRect(item)
            x = event.pos().x() - (rect.x() + self.frameWidth())
            option = QStyleOptionViewItem()
            self.initViewItemOption(option)
            option.rect = rect
            option.features |= QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
            checkbox_rect = self.style().subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, option, self)
            if x > checkbox_rect.width():
                item.setCheckState(0, Qt.CheckState.Checked if item.checkState(0) != Qt.CheckState.Checked else Qt.CheckState.Unchecked)
        super().mousePressEvent(event)

    def sizeHint(self) -> QSize:
        return QSize(400, 500)

    def set_item_downloaded_state(self, ans: QTreeWidgetItem) -> None:
        voice = ans.data(0, Qt.ItemDataRole.UserRole)
        is_downloaded = bool(voice and voice.engine_data and voice.engine_data.get('is_downloaded'))
        ans.setFont(0, self.highlight_font if is_downloaded else self.normal_font)

    def set_voices(
        self, all_voices: tuple[Voice, ...], current_voice: str, engine_metadata: EngineMetadata,
        preferred_voices: dict[str, str] | None = None
    ) -> None:
        self.clear()
        if self.for_embedding:
            current_voice = ''
            preferred_voices = preferred_voices or {}
        current_item = None
        def qv(parent, voice):
            nonlocal current_item
            text = voice.short_text(engine_metadata)
            ans = QTreeWidgetItem(parent, [text])
            ans.setData(0, Qt.ItemDataRole.UserRole, voice)
            ans.setToolTip(0, voice.tooltip(engine_metadata))
            if self.for_embedding:
                ans.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                ans.setCheckState(0, Qt.CheckState.Unchecked)
            if current_voice == voice.name:
                current_item = ans
            self.set_item_downloaded_state(ans)
            return ans
        if not self.for_embedding:
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
                parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable & ~Qt.ItemFlag.ItemIsUserCheckable)
                parent.setData(0, Qt.ItemDataRole.UserRole, langcode)
            for voice in vmap[langcode]:
                v = qv(parent, voice)
                if self.for_embedding and voice.name and preferred_voices.get(langcode) == voice.name:
                    v.setCheckState(0, Qt.CheckState.Checked)
        if current_item is not None:
            self.setCurrentItem(current_item)

    @property
    def val(self) -> str:
        voice = self.current_voice
        return voice.name if voice else ''

    @property
    def preferred_voices(self) -> dict[str, str] | None:
        r = self.invisibleRootItem()
        ans = {}
        for parent in (r.child(i) for i in range(r.childCount())):
            langcode = parent.data(0, Qt.ItemDataRole.UserRole)
            for child in (parent.child(i) for i in range(parent.childCount())):
                if child.checkState(0) == Qt.CheckState.Checked:
                    voice = child.data(0, Qt.ItemDataRole.UserRole)
                    if voice.name:
                        ans[langcode] = voice.name
        return ans or None

    @property
    def current_voice(self) -> Voice | None:
        ci = self.currentItem()
        if ci is not None:
            return ci.data(0, Qt.ItemDataRole.UserRole)

    def refresh_current_item(self) -> None:
        ci = self.currentItem()
        if ci is not None:
            self.set_item_downloaded_state(ci)


class EngineSpecificConfig(QWidget):

    voice_changed = pyqtSignal()

    def __init__(self, parent: QWidget = None, for_embedding: bool = False):
        super().__init__(parent)
        self.for_embedding = for_embedding
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
        self.sentence_delay = d = SentenceDelay(parent=self)
        l.addRow(_('&Pause after sentence:'), d)
        self.pitch = p = FloatSlider(parent=self)
        l.addRow(_('&Pitch of speech:'), p)
        self.volume = v = Volume(self)
        l.addRow(v)
        self.audio_device = ad = QComboBox(self)
        l.addRow(_('Output a&udio to:'), ad)
        self.voices = v = Voices(self, self.for_embedding)
        v.voice_changed.connect(self.voice_changed)
        la = QLabel(_('Choose &default voice for language:') if self.for_embedding else _('V&oices:'))
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
            if self.for_embedding:
                self.engine_specific_settings[engine_name] = EngineSpecificSettings.create_from_config(engine_name, TTS_EMBEDED_CONFIG)
            else:
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
        self.layout().setRowVisible(self.sentence_delay, metadata.has_sentence_delay)
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
        if metadata.can_change_volume and not self.for_embedding:
            self.layout().setRowVisible(self.volume, True)
            self.volume.val = s.volume
        else:
            self.layout().setRowVisible(self.volume, False)
            self.volume.val = None
        if metadata.has_sentence_delay:
            self.sentence_delay.val = s.sentence_delay
        self.audio_device.clear()
        if metadata.allows_choosing_audio_device and not self.for_embedding:
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
        self.voices.set_voices(all_voices, s.voice_name, metadata, s.preferred_voices)

    def as_settings(self) -> EngineSpecificSettings:
        ans = EngineSpecificSettings(
            engine_name=self.engine_name,
            rate=self.rate.val, pitch=self.pitch.val, volume=self.volume.val)
        if self.for_embedding:
            ans = ans._replace(preferred_voices=self.voices.preferred_voices)
        else:
            ans = ans._replace(voice_name=self.voices.val)
        metadata = available_engines()[self.engine_name]
        if metadata.has_sentence_delay:
            ans = ans._replace(sentence_delay=self.sentence_delay.val)
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
        self.engine_specific_config.voices.refresh_current_item()

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


class EmbeddingConfig(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.l = l = QVBoxLayout(self)
        self.engine_specific_config = esc = EngineSpecificConfig(self, for_embedding=True)
        l.addWidget(esc)
        self.engine_specific_config.set_engine('piper')

    def save_settings(self):
        s = self.engine_specific_config.as_settings()
        prefs = load_config(TTS_EMBEDED_CONFIG)
        with prefs:
            s.save_to_config(prefs, TTS_EMBEDED_CONFIG)


def develop_embedding():
    class D(Dialog):
        def __init__(self, parent=None):
            super().__init__('Configure Text to speech audio generation', 'configure-tts-embed', parent=parent)

        def setup_ui(self):
            self.l = l = QVBoxLayout(self)
            self.conf = c = EmbeddingConfig(self)
            l.addWidget(c)
            l.addWidget(self.bb)

    from calibre.gui2 import Application
    app = Application([])
    d = D()
    if d.exec() == QDialog.DialogCode.Accepted:
        d.conf.save_settings()
    del d
    del app


def develop():
    from calibre.gui2 import Application
    app = Application([])
    d = ConfigDialog()
    d.exec()
    del d
    del app


if __name__ == '__main__':
    develop_embedding()
