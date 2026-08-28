#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# The welcome screen for the "Create Your Own Adventure" game, where the
# game is introduced and the AIs used to run it are configured. The API keys
# are saved into the common AI preferences, all other provider settings are
# saved into the dedicated CYOA preferences, see data.py.

from qt.core import QFrame, QGroupBox, QHBoxLayout, QIcon, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget, pyqtSignal

from calibre.ai import AICapabilities
from calibre.ai.config import ConfigureAI
from calibre.customize import AIProviderPlugin
from calibre.gui2.cyoa import data
from calibre.utils.localization import _


class WelcomeWidget(QScrollArea):
    configured = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget(self)
        self.setWidget(inner)
        l = QVBoxLayout(inner)

        self.intro_label = la = QLabel(
            '<h1>'
            + _('Create Your Own Adventure')
            + '</h1><p>'
            + _(
                'Create Your Own Adventure is an interactive storytelling game run by an AI.'
                ' Describe the world you want to play in and the AI expands it into a full'
                ' game world, complete with characters to play as and a goal to achieve.'
                ' Then play the adventure turn-by-turn: the AI narrates what happens and you'
                ' decide what your character does next, with the story, and optionally'
                ' pictures of each scene, generated as you go.'
            )
        )
        la.setWordWrap(True)
        l.addWidget(la)

        self.ai_note_label = la = QLabel(
            '<p>'
            + _(
                'To play, first configure the AI used to generate the story text. Configuring an'
                ' AI to generate pictures of the story is optional, you can skip it and play a'
                ' text only game. Note that for games with mature themes it is best to use'
                ' <b>Grok</b>, or <b>OpenRouter</b> with <i>Llama 4 Scout</i> or <i>DeepSeek v3.2</i>'
                ' as the model, as other AIs tend to refuse to generate such content.'
            )
        )
        la.setWordWrap(True)
        l.addWidget(la)

        # Construct the provider config widgets inside the CYOA settings
        # overlay so they display the settings used for the game, with API
        # keys falling through to the common AI preferences.
        with data.cyoa_ai_settings():
            self.text_group = tg = QGroupBox(_('AI used to generate the story (required)'), inner)
            tv = QVBoxLayout(tg)
            self.text_config = tc = ConfigureAI(
                AICapabilities.text_to_text,
                parent=tg,
                save_hook=self.save_text_settings,
                initial_provider_name=data.configured_provider_name('text'),
            )
            tv.addWidget(tc)
            l.addWidget(tg)

            self.image_group = ig = QGroupBox(_('AI used to generate &pictures of the story (optional)'), inner)
            ig.setCheckable(True)
            ig.setToolTip('<p>' + _('Uncheck this to play a text only game. You can always configure it later.'))
            iv = QVBoxLayout(ig)
            self.image_config = ic = ConfigureAI(
                AICapabilities.text_to_image,
                parent=ig,
                save_hook=self.save_image_settings,
                initial_provider_name=data.configured_provider_name('image'),
            )
            iv.addWidget(ic)
            ig.setChecked(bool(data.configured_provider_name('image')) and not data.image_skipped())
            l.addWidget(ig)

        h = QHBoxLayout()
        self.continue_button = b = QPushButton(QIcon.ic('ok.png'), _('&Continue'), inner)
        b.clicked.connect(self.commit)
        h.addStretch(), h.addWidget(b), h.addStretch()
        l.addLayout(h)
        l.addStretch()

    def save_text_settings(self, plugin: AIProviderPlugin, config_widget: QWidget) -> None:
        data.save_ai_settings('text', plugin.name, config_widget.settings)

    def save_image_settings(self, plugin: AIProviderPlugin, config_widget: QWidget) -> None:
        data.save_ai_settings('image', plugin.name, config_widget.settings)

    def commit(self) -> None:
        if not self.text_config.commit():
            return
        if self.image_group.isChecked():
            if not self.image_config.commit():
                return
            data.mark_image_skipped(False)
        else:
            data.mark_image_skipped(True)
        self.configured.emit()


if __name__ == '__main__':
    from calibre.gui2 import Application

    app = Application([])
    w = WelcomeWidget()
    w.configured.connect(lambda: print('AIs configured'))
    w.resize(600, 700)
    w.show()
    app.exec()
    del w
    del app
