#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>

from functools import partial
from typing import TYPE_CHECKING, Any

from qt.core import QCheckBox, QComboBox, QFormLayout, QGroupBox, QLabel, QLineEdit, QWidget

from calibre.ai import AICapabilities
from calibre.ai.openai import OpenAI
from calibre.ai.prefs import decode_secret, encode_secret, pref_for_provider, set_prefs_for_provider
from calibre.ai.utils import (
    configure,
    image_quality_config_widget,
    model_choice_config_widget,
    model_choice_strategy_config_widget,
    plugin_for_name,
    reasoning_strategy_config_widget,
)
from calibre.gui2 import error_dialog
from calibre.utils.icu import primary_sort_key
from calibre.utils.localization import _

if TYPE_CHECKING:
    from calibre.ai.openai.backend import Model as AIModel
else:
    AIModel = object

pref = partial(pref_for_provider, OpenAI.name)


def backend() -> Any:  # noqa: ANN401
    return plugin_for_name(OpenAI.name).builtin_live_module


def available_models() -> dict[str, AIModel] | None:
    # Listing the models OpenAI offers needs both an API key and a network
    # request, either of which can fail, in particular when the AI is being
    # configured for the first time. None means the list is unavailable, as
    # opposed to an empty list of models.
    try:
        return backend().get_available_models()
    except Exception:
        return None


def models_for(for_image: bool) -> tuple[tuple[str, str], ...]:
    # The (id, name) pairs of the models usable for the given kind of task,
    # newest model family first. OpenAI has no human readable model names,
    # see human_readable_model_name() in the backend, so the id is used as
    # the name.
    if (models := available_models()) is None:
        return ()
    b = backend()
    matches = b.is_image_model if for_image else b.is_chat_model
    return tuple((m.id, m.id) for m in sorted((m for m in models.values() if matches(m)), key=lambda m: (-m.version, primary_sort_key(m.id))))


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
        self.text_model_choice = tm = model_choice_config_widget(models_for(for_image=False), pref('text_model', ''), parent=self)
        tm.setToolTip(
            '<p>' + _('The model to use for text queries. If not specified, an appropriate model is chosen automatically based on the "Model choice strategy".')
        )
        l.addRow(_('Model for &text tasks:'), tm)
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
        gl.addRow(_('Image model &strategy:'), ims)
        self.image_model_choice = imc = model_choice_config_widget(
            models_for(for_image=True), pref('text_to_image_model', ''), _('Automatic (based on the image model strategy)'), self
        )
        imc.setToolTip(
            '<p>'
            + _(
                'The model to use for generating and editing images. If not specified, an appropriate'
                ' model is chosen automatically based on the "Image model strategy".'
            )
        )
        gl.addRow(_('Model for i&mage tasks:'), imc)
        self.image_quality_choice = iq = image_quality_config_widget(pref('image_quality', 'auto'), self)
        gl.addRow(_('Image &quality:'), iq)
        l.addRow(gb)

    def restrict_to_purpose(self, purpose: AICapabilities) -> None:
        # Hide the settings irrelevant to the given purpose, e.g. the image
        # generation settings when configuring the AI for text only use.
        lay = self.layout()
        assert isinstance(lay, QFormLayout)
        lay.setRowVisible(self.image_gb, purpose.supports_text_to_image)
        for w in (self.model_strategy, self.text_model_choice, self._allow_web_searches, self.reasoning_strat):
            lay.setRowVisible(w, purpose.supports_text_to_text)

    def set_model(self, model_id: str, purpose: AICapabilities) -> bool:
        # Make the specified model be used for the specified purpose,
        # returning False if OpenAI does not offer that model.
        target = self.image_model_choice if purpose.supports_text_to_image else self.text_model_choice
        idx = target.findData(model_id)
        if idx < 0:
            models = available_models()
            if models is not None and model_id not in models:
                return False
            # either the model is offered but filtered out of the combo box,
            # or the list of models could not be fetched, so trust the caller
            target.addItem(model_id, model_id)
            idx = target.count() - 1
        target.setCurrentIndex(idx)
        return True

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
    def text_model(self) -> str:
        return self.text_model_choice.currentData()

    @property
    def image_model_strategy(self) -> str:
        return self.image_model_strategy_choice.currentData()

    @property
    def text_to_image_model(self) -> str:
        return self.image_model_choice.currentData()

    @property
    def image_quality(self) -> str:
        return self.image_quality_choice.currentData()

    @property
    def settings(self) -> dict[str, str | bool]:
        ans: dict[str, str | bool] = {
            'api_key': encode_secret(self.api_key),
            'model_choice_strategy': self.model_choice_strategy,
            'text_model': self.text_model,
            'reasoning_strategy': self.reasoning_strategy,
            'allow_web_searches': self.allow_web_searches,
            'image_model_strategy': self.image_model_strategy,
            'text_to_image_model': self.text_to_image_model,
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
