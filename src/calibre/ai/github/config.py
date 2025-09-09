#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>


from functools import partial

from qt.core import QComboBox, QFormLayout, QLabel, QLineEdit, QWidget

from calibre.ai.github import GitHubAI
from calibre.ai.prefs import decode_secret, encode_secret, pref_for_provider, set_prefs_for_provider
from calibre.ai.utils import configure
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
        self.model_strategy = ms = QComboBox(self)
        l.addRow(_('Model &choice strategy:'), ms)
        ms.addItem(_('Cheap and fastest'), 'low')
        ms.addItem(_('Medium'), 'medium')
        ms.addItem(_('High quality, expensive and slower'), 'high')
        if strat := pref('model_choice_strategy', 'medium'):
            ms.setCurrentIndex(max(0, ms.findData(strat)))
        ms.setToolTip('<p>' + _(
            'The model choice strategy controls how a model to query is chosen. Cheaper and faster models give lower'
            ' quality results.'
        ))

    @property
    def api_key(self) -> str:
        return self.api_key_edit.text().strip()

    @property
    def model_choice_strategy(self) -> str:
        return self.model_strategy.currentData()

    @property
    def settings(self) -> dict[str, str]:
        return {
            'api_key': encode_secret(self.api_key), 'model_choice_strategy': self.model_choice_strategy,
        }

    @property
    def is_ready_for_use(self) -> bool:
        return bool(self.api_key)

    def validate(self) -> bool:
        if self.is_ready_for_use:
            return True
        error_dialog(self, _('No API key'), _('You must supply a Personal access token to use GitHub AI.'), show=True)
        return False

    def save_settings(self):
        set_prefs_for_provider(GitHubAI.name, self.settings)


if __name__ == '__main__':
    configure(GitHubAI.name)
