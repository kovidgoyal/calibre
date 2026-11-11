#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Loc Nguyen

from typing import Any

from qt.core import QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from calibre.ai.liquid_inference import LiquidInference
from calibre.ai.liquid_inference.backend import DEFAULT_CAP_USD, DEFAULT_MODEL, pref
from calibre.ai.prefs import decode_secret, encode_secret, set_prefs_for_provider
from calibre.ai.utils import plugin_for_name
from calibre.gui2 import error_dialog
from calibre.gui2.widgets import BusyCursor
from calibre.utils.localization import _


class ConfigWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        label = QLabel(
            _('<p>Get a <a href="https://inference.ai.exchange/">Liquid Inference API key</a> with the spend scope. Add funds to your workspace.')
            + _(' The selected text and conversation go to Liquid Inference and the provider that serves the request.')
        )
        label.setWordWrap(True)
        label.setOpenExternalLinks(True)
        layout.addRow(label)

        self.api_key_edit = key = QLineEdit(self)
        key.setEchoMode(QLineEdit.EchoMode.Password)
        key.setText(decode_secret(pref('api_key')) if pref('api_key') else '')
        key.setPlaceholderText('sk-liquid-...')
        layout.addRow(_('API &key:'), key)

        row = QHBoxLayout()
        self.model_combo = model = QComboBox(self)
        model.setEditable(True)
        model.addItem(pref('text_model') or DEFAULT_MODEL)
        row.addWidget(model, stretch=1)
        refresh = QPushButton(_('&Refresh models'), self)
        refresh.clicked.connect(self.refresh_models)
        row.addWidget(refresh)
        layout.addRow(_('Model for text tasks:'), row)

        self.cap_sb = cap = QDoubleSpinBox(self)
        cap.setDecimals(2)
        cap.setRange(0.01, 100.0)
        cap.setSuffix(' USD')
        cap.setValue(pref('cap_usd', DEFAULT_CAP_USD))
        layout.addRow(_('Maximum charge per &request:'), cap)
        help_text = QLabel(_('This cap limits one request. Set a spend limit on the API key to limit total use. Check Liquid receipts for actual charges.'))
        help_text.setWordWrap(True)
        layout.addRow(help_text)
        self.status = QLabel('', self)
        self.status.setWordWrap(True)
        layout.addRow(self.status)

    @property
    def api_key(self) -> str:
        return self.api_key_edit.text().strip()

    @property
    def text_model(self) -> str:
        return self.model_combo.currentText().strip()

    @property
    def is_ready_for_use(self) -> bool:
        return bool(self.api_key and self.text_model)

    def refresh_models(self) -> None:
        if not self.api_key:
            self.status.setText(_('Enter an API key first.'))
            return
        with BusyCursor():
            try:
                backend = plugin_for_name(LiquidInference.name).builtin_live_module
                assert backend is not None
                backend.get_available_models.cache_clear()
                models = backend.get_available_models(encode_secret(self.api_key))
                current = self.text_model
                self.model_combo.clear()
                self.model_combo.addItems(sorted(models, key=str.casefold))
                self.model_combo.setCurrentText(current or DEFAULT_MODEL)
                self.status.setText(_('Found {} text models.').format(len(models)))
            except Exception as e:
                self.status.setText(_('Could not refresh models: {}').format(e))

    def validate(self) -> bool:
        if not self.is_ready_for_use:
            error_dialog(self, _('Incomplete configuration'), _('Enter an API key and a model ID.'), show=True)
            return False
        return True

    @property
    def settings(self) -> dict[str, Any]:
        return {
            'api_key': encode_secret(self.api_key),
            'text_model': self.text_model,
            'cap_usd': self.cap_sb.value(),
        }

    def save_settings(self) -> None:
        set_prefs_for_provider(LiquidInference.name, self.settings)
