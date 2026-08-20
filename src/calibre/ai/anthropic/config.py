#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from functools import partial
from typing import TYPE_CHECKING

from qt.core import QCheckBox, QComboBox, QFormLayout, QLabel, QLineEdit, QWidget

from calibre.ai.anthropic import AnthropicAI

if TYPE_CHECKING:
    from calibre.ai.anthropic.backend import Model as AIModel
else:
    AIModel = object
from calibre.ai.prefs import decode_secret, encode_secret, pref_for_provider, set_prefs_for_provider
from calibre.ai.utils import configure, model_choice_strategy_config_widget, reasoning_strategy_config_widget
from calibre.gui2 import error_dialog
from calibre.utils.icu import primary_sort_key
from calibre.utils.localization import _

pref = partial(pref_for_provider, AnthropicAI.name)


class ConfigWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        l = QFormLayout(self)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        la = QLabel(
            '<p>'
            + _(
                'You have to create an account at {0}, buy some credits and generate an'
                ' API key. Anthropic has no free models, you will be charged for every query'
                ' based on its size. See the <a href="{1}">pricing details</a> for the different models.'
            ).format(
                '<a href="https://console.anthropic.com">console.anthropic.com</a>',
                'https://docs.anthropic.com/en/docs/about-claude/pricing',
            )
        )
        la.setWordWrap(True)
        la.setOpenExternalLinks(True)
        l.addRow(la)

        self.api_key_edit = a = QLineEdit(self)
        a.setPlaceholderText(_('An API key is required to use Anthropic AI'))
        l.addRow(_('API &key:'), a)
        if key := pref('api_key'):
            a.setText(decode_secret(key))
        self.model_strategy = ms = model_choice_strategy_config_widget(pref('model_choice_strategy', 'medium'), self)
        l.addRow(_('Model &choice strategy:'), ms)
        self.model_choice = mc = QComboBox(self)
        mc.addItem(_('Automatic (based on model choice strategy)'), '')
        for m in self.available_models():
            mc.addItem(m.name, m.id)
        mc.setCurrentIndex(max(0, mc.findData(pref('model', ''))))
        mc.setToolTip(
            '<p>' + _('The model to use for all queries. If not specified, an appropriate model is chosen automatically based on the "Model choice strategy".')
        )
        l.addRow(_('&Model:'), mc)
        self.reasoning_strat = rs = reasoning_strategy_config_widget(pref('reasoning_strategy', 'auto'), self)
        l.addRow(_('&Reasoning effort:'), rs)
        self._allow_web_searches = aws = QCheckBox(_('Allow &searching the web when generating responses'))
        aws.setChecked(pref('allow_web_searches', False))
        aws.setToolTip(
            '<p>'
            + _(
                'If enabled, Claude will search the web to return accurate and up-to-date'
                ' information for queries, where possible. Note that web searches cost'
                ' extra per search, in addition to the normal query cost.'
            )
        )
        l.addRow(aws)

    def available_models(self) -> tuple[AIModel, ...]:
        from calibre.customize.ui import available_ai_provider_plugins

        for plugin in available_ai_provider_plugins():
            if plugin.name == AnthropicAI.name:
                backend = plugin.builtin_live_module
                break
        else:
            raise ValueError(f'Could not find the {AnthropicAI.name} plugin')
        return tuple(sorted(backend.get_available_models().values(), key=lambda m: (-m.family_version, primary_sort_key(m.name))))

    @property
    def api_key(self) -> str:
        return self.api_key_edit.text().strip()

    @property
    def model_choice_strategy(self) -> str:
        return self.model_strategy.currentData()

    @property
    def model(self) -> str:
        return self.model_choice.currentData()

    @property
    def reasoning_strategy(self) -> str:
        return self.reasoning_strat.currentData()

    @property
    def allow_web_searches(self) -> bool:
        return self._allow_web_searches.isChecked()

    @property
    def settings(self) -> dict[str, str | bool]:
        return {
            'api_key': encode_secret(self.api_key),
            'model_choice_strategy': self.model_choice_strategy,
            'model': self.model,
            'reasoning_strategy': self.reasoning_strategy,
            'allow_web_searches': self.allow_web_searches,
        }

    @property
    def is_ready_for_use(self) -> bool:
        return bool(self.api_key)

    def validate(self) -> bool:
        if self.is_ready_for_use:
            return True
        error_dialog(self, _('No API key'), _('You must supply an API key to use Anthropic AI.'), show=True)
        return False

    def save_settings(self) -> None:
        set_prefs_for_provider(AnthropicAI.name, self.settings)


if __name__ == '__main__':
    configure(AnthropicAI.name)
