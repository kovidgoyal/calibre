#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Ali Sheikhizadeh (Al00X) <al00x@outlook.com> <https://al00x.com>
# Based on code Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from functools import partial
from typing import Any

from qt.core import QComboBox, QCompleter, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListView, QPushButton, QSpinBox, Qt, QWidget

from calibre.ai.lm_studio import LMStudioAI
from calibre.ai.prefs import pref_for_provider, set_prefs_for_provider
from calibre.ai.utils import configure, plugin_for_name
from calibre.gui2 import error_dialog
from calibre.gui2.widgets import BusyCursor

pref = partial(pref_for_provider, LMStudioAI.name)


class ConfigWidget(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        l = QFormLayout(self)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        la = QLabel('<p>' + _('LM Studio allows you to run AI models locally. Start the LM Studio server (usually on port 1234) and ensure a model is loaded.'))
        la.setWordWrap(True)
        l.addRow(la)

        self.api_url_edit = a = QLineEdit()
        a.setClearButtonEnabled(True)
        a.setPlaceholderText(_('The LM Studio URL, defaults to {}').format(LMStudioAI.DEFAULT_URL))
        l.addRow(_('LM Studio &URL:'), a)
        a.setText(pref('api_url') or '')

        self.timeout_sb = t = QSpinBox(self)
        t.setRange(15, 600)
        t.setSingleStep(1)
        t.setSuffix(_(' seconds'))
        t.setValue(pref('timeout', 120))
        l.addRow(_('&Timeout:'), t)

        self.temp_sb = temp = QDoubleSpinBox(self)
        temp.setRange(0.0, 2.0)
        temp.setSingleStep(0.1)
        temp.setValue(pref('temperature', 0.7))
        temp.setToolTip(_('Controls randomness. 0 is deterministic, higher is more creative.'))
        l.addRow(_('T&emperature:'), temp)

        # --- Model selector field (ComboBox dropdown) ---
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)

        self.model_combo = mc = QComboBox(w)
        mc.setEditable(True)
        mc.setInsertPolicy(QComboBox.NoInsert)
        mc.setView(QListView(mc))
        mc.setSizeAdjustPolicy(QComboBox.AdjustToContentsOnFirstShow)

        completer = QCompleter(mc)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        mc.setCompleter(completer)

        saved_model = pref('text_model') or ''
        if saved_model:
            mc.addItem(saved_model)
            mc.setCurrentText(saved_model)
        else:
            mc.setCurrentText('')

        self.refresh_btn = rb = QPushButton(_('&Refresh models'))
        rb.clicked.connect(self.refresh_models)

        h.addWidget(mc, stretch=10)
        h.addWidget(rb)
        l.addRow(_('&Model:'), w)

        self.model_status = ms = QLabel('')
        ms.setWordWrap(True)
        ms.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        l.addRow('', ms)

        # Store last loaded models for tooltip
        self._last_models: list[str] = []

        mc.activated.connect(self._on_model_selected)

    def refresh_models(self):
        with BusyCursor():
            try:
                plugin = plugin_for_name(LMStudioAI.name)
                backend = plugin.builtin_live_module
                models_dict = backend.get_available_models(self.api_url)
                keys = list(models_dict.keys()) if models_dict else []
                self._last_models = keys

                self.model_combo.blockSignals(True)
                self.model_combo.clear()
                for k in keys:
                    self.model_combo.addItem(k)
                # If the current combo is empty and models exist, select the first one
                if not self.model_combo.currentText() and keys:
                    self.model_combo.setCurrentText(keys[0])
                # Restore previous selection if it exists in new list
                current_text = (pref('text_model') or '').strip()
                if current_text and current_text in keys:
                    self.model_combo.setCurrentText(current_text)
                self.model_combo.blockSignals(False)

                if keys:
                    display_count = 3
                    sample = ', '.join(keys[:display_count])
                    msg = _('Found {} models. e.g.: {}').format(len(keys), sample)
                    if len(keys) > display_count:
                        msg += _(' (and more)')
                    self.model_status.setText(msg)
                    self.model_status.setToolTip(', '.join(keys))  # Full list in tooltip
                else:
                    self.model_status.setText(_('No models found. Ensure a model is loaded in LM Studio.'))
                    self.model_status.setToolTip('')
            except Exception as e:
                self.model_status.setText(_('Connection failed: {}').format(str(e)))
                self.model_status.setToolTip('')

    @property
    def api_url(self) -> str:
        return self.api_url_edit.text().strip()

    @property
    def text_model(self) -> str:
        return self.model_combo.currentText().strip()

    @property
    def settings(self) -> dict[str, Any]:
        ans = {
            'text_model': self.text_model,
            'timeout': self.timeout_sb.value(),
            'temperature': self.temp_sb.value(),
        }
        url = self.api_url
        if url:
            ans['api_url'] = url
        return ans

    @property
    def is_ready_for_use(self) -> bool:
        return bool(self.text_model)

    def validate(self) -> bool:
        if not self.text_model:
            error_dialog(self, _('No model specified'), _('You must specify a model ID.'), show=True)
            return False
        return True

    def save_settings(self):
        set_prefs_for_provider(LMStudioAI.name, self.settings)

    def _on_model_selected(self, index: int):
        model_id = self.model_combo.itemText(index)
        self.model_status.setText(_('Selected model: {0}').format(model_id))


if __name__ == '__main__':
    configure(LMStudioAI.name)
