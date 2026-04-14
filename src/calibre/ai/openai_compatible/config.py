#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, OpenAI

from functools import partial
from typing import Any

from qt.core import (
    QComboBox,
    QCompleter,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    Qt,
    QWidget,
)

from calibre.ai.openai_compatible import OpenAICompatible
from calibre.ai.prefs import decode_secret, encode_secret, pref_for_provider, set_prefs_for_provider
from calibre.ai.utils import configure, plugin_for_name
from calibre.gui2 import error_dialog
from calibre.gui2.widgets import BusyCursor

pref = partial(pref_for_provider, OpenAICompatible.name)


class ConfigWidget(QWidget):

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        l = QFormLayout(self)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        la = QLabel('<p>' + _(
            'Connect calibre to any self-hosted or third-party service that implements the OpenAI compatible'
            ' <code>/v1/chat/completions</code> API. This is useful for gateways, local servers and other'
            ' services that are not listed as dedicated providers.'
        ))
        la.setWordWrap(True)
        l.addRow(la)

        self.api_url_edit = a = QLineEdit(self)
        a.setClearButtonEnabled(True)
        a.setPlaceholderText(_('For example: {}').format('https://example.com/v1'))
        l.addRow(_('API &URL:'), a)
        a.setText(pref('api_url') or '')

        self.api_key_edit = ak = QLineEdit(self)
        ak.setClearButtonEnabled(True)
        ak.setPlaceholderText(_('Optional. Sent as Authorization: Bearer <key>'))
        l.addRow(_('API &key:'), ak)
        if key := pref('api_key'):
            ak.setText(decode_secret(key))

        self.headers_edit = he = QPlainTextEdit(self)
        he.setPlaceholderText(_('Optional HTTP headers, one per line, in the format: Header-Name: Value'))
        l.addRow(_('HTTP &headers:'), he)
        he.setPlainText('\n'.join(f'{k}: {v}' for (k, v) in pref('headers') or ()))

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
        temp.setToolTip(_('Controls randomness. Lower values are more deterministic.'))
        l.addRow(_('T&emperature:'), temp)

        w = QWidget(self)
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

        if saved_model := pref('text_model') or '':
            mc.addItem(saved_model)
            mc.setCurrentText(saved_model)

        self.refresh_btn = rb = QPushButton(_('&Refresh models'), w)
        rb.clicked.connect(self.refresh_models)
        h.addWidget(mc, stretch=10)
        h.addWidget(rb)
        l.addRow(_('Model for &text tasks:'), w)

        self.model_status = ms = QLabel('', self)
        ms.setWordWrap(True)
        ms.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        l.addRow('', ms)

    def refresh_models(self):
        with BusyCursor():
            try:
                plugin = plugin_for_name(OpenAICompatible.name)
                backend = plugin.builtin_live_module
                backend.get_available_models.cache_clear()
                encoded_key = encode_secret(self.api_key) if self.api_key else ''
                models_dict = backend.get_available_models(self.api_url, encoded_key, self.headers)
                current_text = self.text_model
                model_ids = sorted(models_dict, key=lambda x: x.lower())
                self.model_combo.blockSignals(True)
                self.model_combo.clear()
                for model_id in model_ids:
                    self.model_combo.addItem(model_id)
                self.model_combo.setCurrentText(current_text or (model_ids[0] if model_ids else ''))
                self.model_combo.blockSignals(False)
                if model_ids:
                    sample = ', '.join(model_ids[:3])
                    msg = _('Found {} models. e.g.: {}').format(len(model_ids), sample)
                    if len(model_ids) > 3:
                        msg += _(' (and more)')
                    self.model_status.setText(msg)
                    self.model_status.setToolTip('\n'.join(model_ids))
                else:
                    self.model_status.setText(_('The server responded, but returned no models.'))
                    self.model_status.setToolTip('')
            except Exception as e:
                self.model_status.setText(_('Failed to refresh models: {}').format(e))
                self.model_status.setToolTip('')

    @property
    def api_url(self) -> str:
        return self.api_url_edit.text().strip()

    @property
    def api_key(self) -> str:
        return self.api_key_edit.text().strip()

    @property
    def text_model(self) -> str:
        return self.model_combo.currentText().strip()

    @property
    def timeout(self) -> int:
        return self.timeout_sb.value()

    @property
    def temperature(self) -> float:
        return self.temp_sb.value()

    @property
    def headers(self) -> tuple[tuple[str, str], ...]:
        ans = []
        for line in self.headers_edit.toPlainText().splitlines():
            if line := line.strip():
                key, sep, val = line.partition(':')
                key, val = key.strip(), val.strip()
                if key and sep and val:
                    ans.append((key, val))
        return tuple(ans)

    @property
    def settings(self) -> dict[str, Any]:
        ans = {
            'api_url': self.api_url,
            'api_key': encode_secret(self.api_key),
            'text_model': self.text_model,
            'timeout': self.timeout,
            'temperature': self.temperature,
        }
        if self.headers:
            ans['headers'] = self.headers
        return ans

    @property
    def is_ready_for_use(self) -> bool:
        return bool(self.api_url and self.text_model)

    def validate(self) -> bool:
        if not self.api_url:
            error_dialog(self, _('No API URL'), _('You must specify the URL of the OpenAI compatible API endpoint.'), show=True)
            return False
        if not self.text_model:
            error_dialog(self, _('No model specified'), _('You must specify a model ID to use for text based tasks.'), show=True)
            return False
        return True

    def save_settings(self):
        set_prefs_for_provider(OpenAICompatible.name, self.settings)


if __name__ == '__main__':
    configure(OpenAICompatible.name)
