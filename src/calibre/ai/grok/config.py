#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

from functools import partial

from qt.core import QCheckBox, QComboBox, QFormLayout, QGroupBox, QLabel, QLineEdit, QWidget

from calibre.ai.grok import GrokAI
from calibre.ai.prefs import decode_secret, encode_secret, pref_for_provider, set_prefs_for_provider
from calibre.ai.utils import configure, model_choice_strategy_config_widget, reasoning_strategy_config_widget
from calibre.gui2 import error_dialog
from calibre.utils.localization import _, pgettext

pref = partial(pref_for_provider, GrokAI.name)


class ConfigWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        l = QFormLayout(self)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        la = QLabel(
            '<p>'
            + _(
                'You have to create an account at {0}, then generate an <i>API key</i>'
                ' and buy some credits. Grok models cannot be used free of charge via this plugin.'
                ' See the xAI <a href="{1}">data privacy policy</a> for how your data is handled.'
            ).format(
                '<a href="https://console.x.ai">xAI</a>',
                'https://x.ai/legal/privacy-policy',
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
        aws.setChecked(pref('allow_web_searches', False))
        aws.setToolTip(
            '<p>'
            + _(
                'If enabled, Grok will use web searches to return accurate and up-to-date information for queries, where needed. Note that searches cost extra.'
            )
        )
        l.addRow(aws)
        self.reasoning_strat = rs = reasoning_strategy_config_widget(pref('reasoning_strategy', 'auto'), self)
        l.addRow(_('&Reasoning effort:'), rs)

        self.image_gb = gb = QGroupBox(_('Image generation'), self)
        gl = QFormLayout(gb)
        gl.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.image_resolution_choice = ir = QComboBox(self)
        ir.addItem(pgettext('image resolution', 'Standard'), '1k')
        ir.addItem(pgettext('image resolution', 'High'), '2k')
        ir.setCurrentIndex(max(0, ir.findData(pref('image_resolution', '1k'))))
        ir.setToolTip('<p>' + _('The resolution of generated images. Higher resolution images cost more and take longer to generate.'))
        gl.addRow(_('Image &resolution:'), ir)
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
    def image_resolution(self) -> str:
        return self.image_resolution_choice.currentData()

    @property
    def settings(self) -> dict[str, str | bool]:
        ans: dict[str, str | bool] = {
            'api_key': encode_secret(self.api_key),
            'model_choice_strategy': self.model_choice_strategy,
            'reasoning_strategy': self.reasoning_strategy,
            'allow_web_searches': self.allow_web_searches,
            'image_resolution': self.image_resolution,
        }
        return ans

    @property
    def is_ready_for_use(self) -> bool:
        return bool(self.api_key)

    def validate(self) -> bool:
        if not self.is_ready_for_use:
            error_dialog(self, _('No API key'), _('You must supply an API key to use Grok.'), show=True)
            return False
        return True

    def save_settings(self) -> None:
        set_prefs_for_provider(GrokAI.name, self.settings)


if __name__ == '__main__':
    configure(GrokAI.name)
