#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from functools import partial

from qt.core import QCheckBox, QComboBox, QFormLayout, QGroupBox, QLabel, QLineEdit, QWidget

from calibre.ai.openai import OpenAI
from calibre.ai.prefs import decode_secret, encode_secret, pref_for_provider, set_prefs_for_provider
from calibre.ai.utils import configure, image_quality_config_widget, model_choice_strategy_config_widget, reasoning_strategy_config_widget
from calibre.gui2 import error_dialog
from calibre.utils.localization import _

pref = partial(pref_for_provider, OpenAI.name)


class ConfigWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        l = QFormLayout(self)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        la = QLabel(
            '<p>'
            + _(
                'You have to create an account at {0}, then generate an <i>API key</i>.'
                ' Then, buy some credits. Finally, <a href="{1}">{1}</a>'
                '. OpenAI models cannot be used free of charge via this plugin.'
                ' OpenAI <a href="{2}">claims not to store prompts</a> and other data and not use it'
                ' for training except for a small period of retention to prevent abuse and misuse.'
            ).format(
                '<a href="https://platform.openai.com">OpenAI</a>',
                'https://platform.openai.com/settings/organization/general',
                'https://platform.openai.com/docs/guides/your-data',
            )
        )
        la.setWordWrap(True)
        la.setOpenExternalLinks(True)
        l.addRow(la)

        self.api_key_edit = a = QLineEdit(self)
        a.setPlaceholderText(_('An API key is required'))
        l.addRow(_('API &key:'), a)
        if key := pref('api_key'):
            a.setText(decode_secret(key))
        self.model_strategy = ms = model_choice_strategy_config_widget(pref('model_choice_strategy', 'medium'), self)
        l.addRow(_('Model &choice strategy:'), ms)
        self._allow_web_searches = aws = QCheckBox(_('Allow &searching the web when generating responses'))
        aws.setChecked(pref('allow_web_searches', True))
        aws.setToolTip(_('If enabled, OpenAI will use web searches to return accurate and up-to-date information for queries, where possible'))
        l.addRow(aws)
        self.reasoning_strat = rs = reasoning_strategy_config_widget(pref('reasoning_strategy', 'auto'), self)
        l.addRow(_('&Reasoning effort:'), rs)

        self.image_gb = gb = QGroupBox(_('Image generation'), self)
        gl = QFormLayout(gb)
        gl.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.image_model_strategy_choice = ims = QComboBox(self)
        ims.addItem(_('Best quality'), 'high')
        ims.addItem(_('Cheaper and faster'), 'low')
        ims.setCurrentIndex(max(0, ims.findData(pref('image_model_strategy', 'high'))))
        ims.setToolTip('<p>' + _('The model used to generate and edit images. The cheaper model produces lower quality images.'))
        gl.addRow(_('&Image model:'), ims)
        self.image_quality_choice = iq = image_quality_config_widget(pref('image_quality', 'auto'), self)
        gl.addRow(_('Image &quality:'), iq)
        l.addRow(gb)

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
    def image_model_strategy(self) -> str:
        return self.image_model_strategy_choice.currentData()

    @property
    def image_quality(self) -> str:
        return self.image_quality_choice.currentData()

    @property
    def settings(self) -> dict[str, str | bool]:
        ans: dict[str, str | bool] = {
            'api_key': encode_secret(self.api_key),
            'model_choice_strategy': self.model_choice_strategy,
            'reasoning_strategy': self.reasoning_strategy,
            'allow_web_searches': self.allow_web_searches,
            'image_model_strategy': self.image_model_strategy,
            'image_quality': self.image_quality,
        }
        return ans

    @property
    def is_ready_for_use(self) -> bool:
        return bool(self.api_key)

    def validate(self) -> bool:
        if not self.is_ready_for_use:
            error_dialog(self, _('No API key'), _('You must supply an API key to use OpenAI.'), show=True)
            return False
        return True

    def save_settings(self) -> None:
        set_prefs_for_provider(OpenAI.name, self.settings)


if __name__ == '__main__':
    configure(OpenAI.name)
