#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from functools import partial

from qt.core import QFormLayout, QLabel, QLineEdit, QWidget

from calibre.ai.ollama import OllamaAI
from calibre.ai.prefs import pref_for_provider, set_prefs_for_provider
from calibre.ai.utils import configure, plugin_for_name
from calibre.gui2 import error_dialog

pref = partial(pref_for_provider, OllamaAI.name)


class ConfigWidget(QWidget):

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        l = QFormLayout(self)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        la = QLabel('<p>'+_(
            'Ollama allows you to run AI models locally on your own hardware. Once you have it running and properly'
            ' setup, fill in the fields below to have calibre use it as the AI provider.'
        ))
        la.setWordWrap(True)
        la.setOpenExternalLinks(True)
        l.addRow(la)

        self.api_url_edit = a = QLineEdit()
        a.setPlaceholderText(_('The Ollama URL, defaults to {}').format(OllamaAI.DEFAULT_URL))
        a.setToolTip(_('Enter the URL of the machine running your Ollama server, for example: {}').format(
            'https://my-ollama-server.com:11434'))
        self.text_model_edit = lm = QLineEdit(self)
        l.addRow(_('Ollama &URL:'), a)
        lm.setClearButtonEnabled(True)
        lm.setToolTip(_(
            'Enter the name of the model to use for text based tasks.'
        ))
        lm.setPlaceholderText(_('Enter name of model to use'))
        l.addRow(_('Model for &text tasks:'), lm)
        lm.setText(pref('text_model') or '')

    def does_model_exist_locally(self, model_name: str) -> bool:
        if not model_name:
            return False
        plugin = plugin_for_name(OllamaAI.name)
        return plugin.builtin_live_module.does_model_exist_locally(model_name)

    def available_models(self) -> list[str]:
        plugin = plugin_for_name(OllamaAI.name)
        return sorted(plugin.builtin_live_module.get_available_models(), key=lambda x: x.lower())

    @property
    def text_model(self) -> str:
        return self.text_model_edit.text().strip()

    @property
    def settings(self) -> dict[str, str]:
        ans = {
            'text_model': self.text_model,
        }
        url = self.api_url_edit.text().strip()
        if url:
            ans['api_url'] = url
        return ans

    @property
    def is_ready_for_use(self) -> bool:
        return bool(self.text_model)

    def validate(self) -> bool:
        if not self.text_model:
            error_dialog(self, _('No model specified'), _('You specify a model to use for text based tasks.'), show=True)
            return False
        if not self.does_model_exist_locally(self.text_model):
            try:
                avail = self.available_models()
            except Exception:
                import traceback
                det_msg = _('Failed to get list of available models with error:') + '\n' + traceback.format_exc()
            else:
                det_msg = _('Available models:') + '\n' + '\n'.join(avail)

            error_dialog(self, _('No matching model'), _(
                'No model named {} found in Ollama. Click "Show details" to see a list of available models.').format(
                    self.text_model), show=True, det_msg=det_msg)
            return False
        return True

    def save_settings(self):
        set_prefs_for_provider(OllamaAI.name, self.settings)


if __name__ == '__main__':
    configure(OllamaAI.name)
