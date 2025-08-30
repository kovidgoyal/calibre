#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from functools import partial

from qt.core import QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from calibre.ai.config import pref_for_provider

from . import OpenRouterAI

pref = partial(pref_for_provider, OpenRouterAI.name)


class Model(QWidget):

    def __init__(self, for_text: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        l = QHBoxLayout(self)
        self.model_id, self.model_name = pref(
            'text_model' if for_text else 'text_to_image_model', ('', _('Automatic (free)')))
        self.la = la = QLabel(self.model_name)
        self.setToolTip(_('The model to use for text related tasks') if for_text else _(
            'The model to use for generating iamges from text'))
        self.setToolTip(self.toolTip() + '\n\n' + _(
            'If not specified an appropriate free to use model is chosen automatically.\n'
            'If no free model is available then cheaper ones are preferred.'))
        self.b = b = QPushButton(_('&Select'))
        b.setToolTip(_('Choose a model'))
        l.addWidget(la), l.addWidget(b)
        b.clicked.connect(self.select_model)

    def select_model(self):
        pass


class ConfigWidget(QWidget):

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        l = QFormLayout(self)
        la = QLabel('<p>'+_(
            'You have to create an account at {}, then generate an'
            ' API key and purchase a token amount of credits. After that, you can use any AI'
            ' model you like, including free ones.').format('<a href="https://openrouter.ai">OpenRouter.ai</a>'))
        la.setWordWrap(True)
        la.setOpenExternalLinks(True)
        l.addRow(la)
        self.api_key_edit = a = QLineEdit(self)
        a.setPlaceholderText(_('An API key is required to use OpenRouter'))
        l.addRow(_('API &key:'), a)
