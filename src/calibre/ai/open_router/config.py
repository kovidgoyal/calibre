#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from functools import partial
from typing import Any

from qt.core import QAbstractListModel, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSortFilterProxyModel, Qt, QWidget, pyqtSignal

from calibre.ai.prefs import pref_for_provider, set_prefs_for_provider
from calibre.customize.ui import available_ai_provider_plugins
from calibre.gui2 import error_dialog

from . import OpenRouterAI

pref = partial(pref_for_provider, OpenRouterAI.name)


class Model(QWidget):

    select_model = pyqtSignal(str, bool)

    def __init__(self, for_text: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        l = QHBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.for_text = for_text
        self.model_id, self.model_name = pref(
            'text_model' if for_text else 'text_to_image_model', ('', _('Automatic (low cost)')))
        self.la = la = QLabel(self.model_name)
        self.setToolTip(_('The model to use for text related tasks') if for_text else _(
            'The model to use for generating images from text'))
        self.setToolTip(self.toolTip() + '\n\n' + _(
            'If not specified an appropriate free to use model is chosen automatically.\n'
            'If no free model is available then cheaper ones are preferred.'))
        self.b = b = QPushButton(_('&Change'))
        b.setToolTip(_('Choose a model'))
        l.addWidget(la), l.addWidget(b)
        b.clicked.connect(self._select_model)

    def _select_model(self):
        self.select_model.emit(self.model_id, self.for_text)


class ModelsModel(QAbstractListModel):

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        for plugin in available_ai_provider_plugins():
            if plugin.name == OpenRouterAI.name:
                self.backend = plugin.builtin_live_module
                break
        else:
            raise ValueError('Could not find OpenRouterAI plugin')
        self.all_models_map = self.backend.get_available_models()
        self.all_models = sorted(self.all_models_map.values(), key=lambda m: m.created, reverse=True)

    def rowCount(self, parent):
        return len(self.all_models)

    def data(self, index, role):
        try:
            m = self.all_models[index.row()]
        except IndexError:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return m.name
        if role == Qt.ItemDataRole.UserRole:
            return m
        return None


class ProxyModels(QSortFilterProxyModel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.source_model = ModelsModel(self)
        self.setSourceModel(self.source_model)
        self.filters = []

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        try:
            m = self.source_model.all_models[source_row]
        except IndexError:
            return False
        for f in self.filters:
            if not f(m):
                return False
        return True


class ChooseModel(QWidget):

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)


class ConfigWidget(QWidget):

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        l = QFormLayout(self)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        la = QLabel('<p>'+_(
            'You have to create an account at {0}, then generate an'
            ' API key and purchase a token amount of credits. After that, you can use any '
            ' <a href="{1}">AI model</a> you like, including free ones.'
        ).format('<a href="https://openrouter.ai">OpenRouter.ai</a>', 'https://openrouter.ai/rankings'))
        la.setWordWrap(True)
        la.setOpenExternalLinks(True)
        l.addRow(la)
        self.api_key_edit = a = QLineEdit(self)
        a.setPlaceholderText(_('An API key is required to use OpenRouter'))
        l.addRow(_('API &key:'), a)
        if key := pref('api_key'):
            a.setText(key)
        self.text_model = tm = Model(parent=self)
        tm.select_model.connect(self.select_model)
        l.addRow(_('Model for &text tasks:'), tm)
        self.choose_model = cm = ChooseModel(self)
        cm.setVisible(False)
        l.addRow(cm)

    def select_model(self, model_id: str, for_text: bool) -> None:
        self.model_choice_target = self.sender()

    @property
    def api_key(self) -> str:
        return self.api_key_edit.text().strip()

    @property
    def settings(self) -> dict[str, Any]:
        return {'api_key': self.api_key}

    def validate(self) -> bool:
        if self.api_key:
            return True
        error_dialog(self, _('No API key'), _(
            'You must supply an API key to use OpenRouter. Remember to also buy a few credits, even if you'
            ' plan on using only free models.'), show=True)
        return False

    def save_settings(self):
        set_prefs_for_provider(OpenRouterAI.name, self.settings)
