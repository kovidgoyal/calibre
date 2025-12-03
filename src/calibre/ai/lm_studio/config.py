#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Ali Sheikhizadeh (Al00X) <al00x@outlook.com> <https://al00x.com>
# Based on code Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from functools import partial
from typing import Any

from qt.core import QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, Qt, QWidget

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
        t.setRange(15, 600), t.setSingleStep(1), t.setSuffix(_(' seconds'))
        t.setValue(pref('timeout', 120))
        l.addRow(_('&Timeout:'), t)

        self.temp_sb = temp = QDoubleSpinBox(self)
        temp.setRange(0.0, 2.0)
        temp.setSingleStep(0.1)
        temp.setValue(pref('temperature', 0.7))
        temp.setToolTip(_('Controls randomness. 0 is deterministic, higher is more creative.'))
        l.addRow(_('T&emperature:'), temp)

        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        self.model_edit = me = QLineEdit(w)
        me.setPlaceholderText(_('Enter model ID or click Refresh'))
        me.setText(pref('text_model') or '')

        self.refresh_btn = rb = QPushButton(_('&Refresh models'))
        rb.clicked.connect(self.refresh_models)

        h.addWidget(me)
        h.addWidget(rb)
        l.addRow(_('&Model:'), w)

        self.model_status = ms = QLabel('')
        ms.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        l.addRow('', ms)

    def refresh_models(self):
        with BusyCursor():
            try:
                plugin = plugin_for_name(LMStudioAI.name)
                backend = plugin.builtin_live_module
                models = backend.get_available_models(self.api_url)
                if models:
                    # We pick the first one if the current model is empty, or just show success
                    keys = list(models.keys())
                    self.model_status.setText(_('Found {} models: {}').format(len(keys), ', '.join(keys)))
                    if not self.model_edit.text() and keys:
                        self.model_edit.setText(keys[0])
                else:
                    self.model_status.setText(_('No models found. Ensure a model is loaded in LM Studio.'))
            except Exception as e:
                self.model_status.setText(_('Connection failed: {}').format(str(e)))

    @property
    def api_url(self) -> str:
        return self.api_url_edit.text().strip()

    @property
    def text_model(self) -> str:
        return self.model_edit.text().strip()

    @property
    def settings(self) -> dict[str, Any]:
        ans = {
            'text_model': self.text_model,
            'timeout': self.timeout_sb.value(),
            'temperature': self.temp_sb.value(),
        }
        if url := self.api_url:
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


if __name__ == '__main__':
    configure(LMStudioAI.name)
