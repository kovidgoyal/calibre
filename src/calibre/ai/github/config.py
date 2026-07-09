#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from collections.abc import Sequence
from functools import partial

from qt.core import QFormLayout, QHBoxLayout, QLabel, QLineEdit, QWidget

from calibre.ai.github import GitHubAI
from calibre.ai.prefs import decode_secret, encode_secret, pref_for_provider, set_prefs_for_provider
from calibre.ai.utils import configure, model_choice_strategy_config_widget, plugin_for_name
from calibre.gui2 import error_dialog

pref = partial(pref_for_provider, GitHubAI.name)


class ConfigWidget(QWidget):

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        l = QFormLayout(self)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        la = QLabel('<p>'+_(
            'You have to create an account at {0}, then generate a <a href="{1}">Personal access token</a>'
            ' with the <code>models:read</code> permission.'
            ' After that, you can use the GitHub AI services a limited number of times a day for free.'
            ' For more extensive use, you will need to setup <a href="{2}">GitHub models billing</a>.'
        ).format(
            '<a href="https://github.com">GitHub</a>',
            'https://docs.github.com/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens',
            'https://docs.github.com/billing/concepts/product-billing/github-models',
        ))
        la.setWordWrap(True)
        la.setOpenExternalLinks(True)
        l.addRow(la)

        self.api_key_edit = a = QLineEdit(self)
        a.setPlaceholderText(_('A personal access token is required'))
        l.addRow(_('Access &token:'), a)
        if key := pref('api_key'):
            a.setText(decode_secret(key))
        self.model_strategy = ms = model_choice_strategy_config_widget(pref('model_choice_strategy', 'medium'), self)
        l.addRow(_('Model &choice strategy:'), ms)
        self.text_model_edit = lm = QLineEdit(self)
        lm.setClearButtonEnabled(True)
        lm.setToolTip(_(
            'Enter a name of the model to use for text based tasks.'
            ' If not specified, one is chosen automatically.'
        ))
        lm.setPlaceholderText(_('Optionally, enter name of model to use'))
        self.browse_label = la = QLabel(f'<a href="https://github.com/marketplace?type=models">{_("Browse")}</a>')
        tm = QWidget()
        la.setOpenExternalLinks(True)
        h = QHBoxLayout(tm)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(lm), h.addWidget(la)
        l.addRow(_('Model for &text tasks:'), tm)
        self.initial_text_model = pm = pref('text_model') or {'name': '', 'id': ''}
        if pm:
            lm.setText(pm['name'])

    @property
    def api_key(self) -> str:
        return self.api_key_edit.text().strip()

    @property
    def model_choice_strategy(self) -> str:
        return self.model_strategy.currentData()

    @property
    def settings(self) -> dict[str, str]:
        name = self.text_model_edit.text().strip()
        ans = {
            'api_key': encode_secret(self.api_key), 'model_choice_strategy': self.model_choice_strategy,
        }
        if name:
            ans['text_model'] = {'name': name, 'id': self.model_ids_for_name(name)[0]}
        return ans

    @property
    def is_ready_for_use(self) -> bool:
        return bool(self.api_key)

    def model_ids_for_name(self, name: str) -> Sequence[str]:
        if name and name == self.initial_text_model['name']:
            return (self.initial_text_model['id'],)
        plugin = plugin_for_name(GitHubAI.name)
        return tuple(plugin.builtin_live_module.find_models_matching_name(name))

    def validate(self) -> bool:
        if not self.is_ready_for_use:
            error_dialog(self, _('No API key'), _('You must supply a Personal access token to use GitHub AI.'), show=True)
            return False
        if (name := self.text_model_edit.text().strip()) and name:
            num = len(self.model_ids_for_name(name))
            if num == 0:
                error_dialog(self, _('No matching model'), _('No model named {} found on GitHub').format(name), show=True)
                return False
            if num > 1:
                error_dialog(self, _('Ambiguous model name'), _('The name {} matches more than one model on GitHub').format(name), show=True)
                return False
        return True

    def save_settings(self):
        set_prefs_for_provider(GitHubAI.name, self.settings)


if __name__ == '__main__':
    configure(GitHubAI.name)
