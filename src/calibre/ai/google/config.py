#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>


from functools import partial

from qt.core import QCheckBox, QFormLayout, QLabel, QLineEdit, QWidget

from calibre.ai.google import GoogleAI
from calibre.ai.prefs import decode_secret, encode_secret, pref_for_provider, set_prefs_for_provider
from calibre.ai.utils import configure, model_choice_strategy_config_widget, reasoning_strategy_config_widget
from calibre.gui2 import error_dialog

pref = partial(pref_for_provider, GoogleAI.name)


class ConfigWidget(QWidget):

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        l = QFormLayout(self)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        la = QLabel('<p>'+_(
            'You have to create an account at {0}, then generate an'
            ' API key. After that, you can use the Google AI services a limited number of times a day for free.'
            ' For more extensive use, you will need to setup a <a href="{1}">Google Cloud billing account</a>.'
            ' Note that Google will use your prompts for their training data unless you setup the billing account.'
            ' <a href="{2}>Pricing details</a> for different models.'
        ).format(
            '<a href="https://aistudio.google.com/">Google AI Studio</a>',
            'https://aistudio.google.com/usage', 'https://ai.google.dev/gemini-api/docs/pricing',
        ))
        la.setWordWrap(True)
        la.setOpenExternalLinks(True)
        l.addRow(la)

        self.api_key_edit = a = QLineEdit(self)
        a.setPlaceholderText(_('An API key is required to use Google AI'))
        l.addRow(_('API &key:'), a)
        if key := pref('api_key'):
            a.setText(decode_secret(key))
        self.model_strategy = ms = model_choice_strategy_config_widget(pref('model_choice_strategy', 'medium'), self)
        l.addRow(_('Model &choice strategy:'), ms)
        self._allow_web_searches = aws = QCheckBox(_('Allow &searching the web when generating responses'))
        aws.setChecked(pref('allow_web_searches', True))
        aws.setToolTip(_('If enabled, Gemini will use Google Web searches to return accurate and up-to-date information for queries, where possible'))
        self.reasoning_strat = rs = reasoning_strategy_config_widget(pref('reasoning_strategy'), self)
        l.addRow(_('&Reasoning effort:'), rs)

    @property
    def api_key(self) -> str:
        return self.api_key_edit.text().strip()

    @property
    def model_choice_strategy(self) -> str:
        return self.model_strategy.currentData()

    @property
    def reasoning_strategy(self) -> str:
        return self.reasoning_strat.currentData()

    @property
    def allow_web_searches(self) -> bool:
        return self._allow_web_searches.isChecked()

    @property
    def settings(self) -> dict[str, str]:
        return {
            'api_key': encode_secret(self.api_key), 'model_choice_strategy': self.model_choice_strategy,
            'reasoning_strategy': self.reasoning_strategy, 'allow_web_searches': self.allow_web_searches,
        }

    @property
    def is_ready_for_use(self) -> bool:
        return bool(self.api_key)

    def validate(self) -> bool:
        if self.is_ready_for_use:
            return True
        error_dialog(self, _('No API key'), _('You must supply an API key to use Google AI.'), show=True)
        return False

    def save_settings(self):
        set_prefs_for_provider(GoogleAI.name, self.settings)


if __name__ == '__main__':
    configure(GoogleAI.name)
