#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# The welcome screen for the "Create Your Own Adventure" game, where the
# game is introduced and the AIs used to run it are configured. It is a
# sequence of panels: an introduction, then the AI used to generate the
# story, then the optional AI used to generate pictures. Each of the AI
# panels has a panel of recommended models on its right, whose names are
# links that configure the provider and model when clicked. The API keys
# are saved into the common AI preferences, all other provider settings are
# saved into the dedicated CYOA preferences, see data.py.

from typing import NamedTuple

from qt.core import QFrame, QHBoxLayout, QIcon, QLabel, QPushButton, QScrollArea, QSize, QStackedLayout, QTextBrowser, QUrl, QVBoxLayout, QWidget, pyqtSignal

from calibre.ai import AICapabilities
from calibre.ai.config import AIConfigWidget, ConfigureAI
from calibre.customize import AIProviderPlugin
from calibre.gui2 import error_dialog, safe_open_url
from calibre.gui2.cyoa import data
from calibre.gui2.widgets import BusyCursor
from calibre.utils.localization import _

# The scheme used for the links that configure a provider and model. The
# rest of the link is the position of the model in the recommendation lists
# below, so that provider and model names need no escaping.
LINK_SCHEME = 'cyoa-model'


class RecommendedModel(NamedTuple):
    id: str  # the provider specific id of the model
    name: str  # the name of the model, as shown to the user, not translated
    note: str  # a short, translated, note on why the model is recommended


class Recommendations(NamedTuple):
    # A group of recommended models, all from a single AI provider. Groups
    # whose provider is unavailable, or that does not allow models to be
    # chosen explicitly, are not shown.
    provider: str  # the name of the AI provider plugin
    heading: str  # translated heading, {} is replaced by the provider name
    blurb: str  # translated explanation, {} is replaced by the provider name
    models: tuple[RecommendedModel, ...]


# Model names and ids are deliberately not translated, they are proper
# nouns. Only the notes explaining why a model is recommended are.
STORY_RECOMMENDATIONS = (
    Recommendations(
        'OpenRouter',
        _('Good all round choices (via {})'),
        _(
            'A single {} account gives you access to the models of every major AI company,'
            ' so you can switch between them freely. All the models below are a good balance'
            ' of story quality against cost.'
        ),
        (
            RecommendedModel('google/gemini-3.7-flash', 'Gemini 3.7 Flash', _('fast, with a huge memory for long games')),
            RecommendedModel('deepseek/deepseek-v4-pro', 'DeepSeek V4 Pro', _('the cheapest of these, good for long games')),
            RecommendedModel('z-ai/glm-5.2', 'GLM 5.2', _('particularly good at creative writing and role-play')),
            RecommendedModel('x-ai/grok-4.3', 'Grok 4.3', _('lively narration and less likely to refuse')),
            RecommendedModel('anthropic/claude-haiku-4.5', 'Claude Haiku 4.5', _('the most polished prose, somewhat pricier')),
        ),
    ),
    Recommendations(
        'Venice AI',
        _('For games with mature themes (via {})'),
        _(
            'Most AIs refuse to generate violent or sexual content. {} runs uncensored models'
            ' and does not store your chats, so use it if you want a game with mature themes.'
        ),
        (
            RecommendedModel('deepseek-v3.2', 'DeepSeek V3.2', _('very cheap and rarely refuses')),
            RecommendedModel('deepseek-v4-pro', 'DeepSeek V4 Pro', _('better writing, a few times the cost')),
            RecommendedModel('grok-4-3', 'Grok 4.3', _('lively narration with a huge memory')),
        ),
    ),
)

IMAGE_RECOMMENDATIONS = (
    Recommendations(
        'OpenRouter',
        _('Good all round choices (via {})'),
        _('The same {} account used for the story can generate the pictures as well.'),
        (
            RecommendedModel('google/gemini-3.1-flash-image', 'Nano Banana 2', _('the best all round choice, a few cents per picture')),
            RecommendedModel('openai/gpt-5-image-mini', 'GPT-5 Image Mini', _('a good alternative style')),
        ),
    ),
    Recommendations(
        'GoogleAI',
        _('If you want to try it for free (via {})'),
        _('{} lets you generate a small number of pictures per day for free, with only an API key, no credits needed.'),
        (RecommendedModel('gemini', 'Gemini', _('the same models as Nano Banana, but with a free tier')),),
    ),
    Recommendations(
        'Venice AI',
        _('For games with mature themes (via {})'),
        _('The image models run by {} are uncensored, unlike those of most other providers.'),
        (
            RecommendedModel('z-image-turbo', 'Z-Image Turbo', _('fast and very cheap, about a cent per picture')),
            RecommendedModel('qwen-image-3-pro', 'Qwen Image 3 Pro', _('higher quality, a few times the cost')),
        ),
    ),
)


class RecommendationsPanel(QTextBrowser):
    # Shows the recommended models for one AI purpose, as links that
    # configure the AI when clicked.

    def __init__(self, groups: tuple[Recommendations, ...], config: ConfigureAI, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.groups = groups
        self.config = config
        self.setOpenLinks(False)
        self.anchorClicked.connect(self.link_clicked)
        self.render_recommendations()

    def sizeHint(self) -> QSize:
        return QSize(300, 400)

    def render_recommendations(self) -> None:
        html = [
            '<h3>' + _('Recommended AIs') + '</h3>',
            '<p>'
            + _(
                'Click any model below to select it. You then only need to create an account'
                ' with the AI provider it uses and paste in the API key it gives you.'
            )
            + '</p>',
        ]
        num_shown = 0
        for gi, g in enumerate(self.groups):
            if not self.config.can_set_provider_and_model(g.provider):
                continue
            num_shown += 1
            html.append('<h3>' + g.heading.format(g.provider) + '</h3>')
            html.append('<p>' + g.blurb.format(g.provider) + '</p>')
            html.append('<ul>')
            for mi, m in enumerate(g.models):
                html.append(f'<li><a href="{LINK_SCHEME}:{gi}.{mi}">{m.name}</a> &mdash; {m.note}</li>')
            html.append('</ul>')
        if not num_shown:
            html.append('<p>' + _('No AI providers that allow choosing a model are available. Configure any of the providers below by hand.') + '</p>')
        self.setHtml('\n'.join(html))

    def link_clicked(self, url: QUrl) -> None:
        if url.scheme() != LINK_SCHEME:
            safe_open_url(url)
            return
        gi, mi = url.path().split('.')
        g = self.groups[int(gi)]
        m = g.models[int(mi)]
        with BusyCursor(), data.cyoa_ai_settings():
            # Fetching the list of models offered by the provider, needed to
            # display the name of the chosen model, can take a moment.
            ok = self.config.set_provider_and_model(g.provider, m.id)
        if not ok:
            error_dialog(
                self,
                _('Model not available'),
                _('{0} no longer offers the model {1}. Choose one of the other models instead.').format(g.provider, m.name),
                show=True,
            )


class WelcomeWidget(QWidget):
    configured = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.stack = s = QStackedLayout(self)
        self.intro_page = ip = self.create_intro_page()
        s.addWidget(ip)
        # Construct the provider config widgets inside the CYOA settings
        # overlay so they display the settings used for the game, with API
        # keys falling through to the common AI preferences.
        with data.cyoa_ai_settings():
            self.text_page = tp = self.create_text_page()
            s.addWidget(tp)
            self.image_page = imp = self.create_image_page()
            s.addWidget(imp)
        self.update_button_states()

    # Page construction {{{

    def create_intro_page(self) -> QWidget:
        ans = QWidget(self)
        l = QVBoxLayout(ans)
        self.intro_label = la = QLabel(
            '<h1>'
            + _('Create Your Own Adventure')
            + '</h1><p>'
            + _(
                'Create Your Own Adventure is an interactive storytelling game run by an AI.'
                ' Describe the world you want to play in and the AI expands it into a full'
                ' game world, complete with different characters you can choose to play as.'
                ' Then play the adventure turn-by-turn: the AI narrates what happens and you'
                ' decide what your character does next, with the story, and optionally'
                ' pictures of each scene, generated as you go.'
            )
            + '</p><p>'
            + _('To play, you need an account with an AI provider of your choice. The next screens recommend some good ones and help you set them up.')
        )
        la.setWordWrap(True)
        la.setMaximumWidth(700)  # long lines of text are hard to read
        l.addStretch(10)
        h = QHBoxLayout()
        h.addStretch(1), h.addWidget(la, stretch=10), h.addStretch(1)
        l.addLayout(h)
        l.addSpacing(30)
        h = QHBoxLayout()
        self.configure_button = b = QPushButton(QIcon.ic('ai.png'), _('&Configure the AI'), ans)
        b.clicked.connect(self.show_text_page)
        h.addStretch(), h.addWidget(b), h.addStretch()
        l.addLayout(h)
        l.addStretch(10)
        return ans

    def create_text_page(self) -> QWidget:
        ans = QWidget(self)
        l = QVBoxLayout(ans)
        la = QLabel('<h2>' + _('The AI that tells the story') + '</h2>')
        l.addWidget(la)
        self.text_config = tc = ConfigureAI(
            AICapabilities.text_to_text,
            parent=ans,
            save_hook=self.save_text_settings,
            initial_provider_name=data.configured_provider_name('text'),
        )
        tc.changed.connect(self.update_button_states)
        self.text_recommendations = tr = RecommendationsPanel(STORY_RECOMMENDATIONS, tc, ans)
        l.addLayout(self.config_and_recommendations(ans, tc, tr), stretch=10)

        h = QHBoxLayout()
        self.text_back_button = b = QPushButton(QIcon.ic('back.png'), _('&Back'), ans)
        b.clicked.connect(self.show_intro_page)
        h.addWidget(b), h.addStretch()
        self.text_next_button = b = QPushButton(QIcon.ic('forward.png'), _('&Next'), ans)
        b.clicked.connect(self.commit_text)
        h.addWidget(b)
        l.addLayout(h)
        return ans

    def create_image_page(self) -> QWidget:
        ans = QWidget(self)
        l = QVBoxLayout(ans)
        la = QLabel(
            '<h2>'
            + _('The AI that draws the pictures')
            + '</h2><p>'
            + _('This is optional, you can skip it and play a text only game. You can always configure it later.')
        )
        la.setWordWrap(True)
        l.addWidget(la)
        self.image_config = ic = ConfigureAI(
            AICapabilities.text_to_image,
            parent=ans,
            save_hook=self.save_image_settings,
            initial_provider_name=data.configured_provider_name('image'),
        )
        ic.changed.connect(self.update_button_states)
        self.image_recommendations = ir = RecommendationsPanel(IMAGE_RECOMMENDATIONS, ic, ans)
        l.addLayout(self.config_and_recommendations(ans, ic, ir), stretch=10)

        h = QHBoxLayout()
        self.image_back_button = b = QPushButton(QIcon.ic('back.png'), _('&Back'), ans)
        b.setToolTip('<p>' + _('Go back to change the AI used to tell the story'))
        b.clicked.connect(self.show_text_page)
        h.addWidget(b), h.addStretch()
        self.skip_button = b = QPushButton(QIcon.ic('edit-clear.png'), _('&Skip pictures'), ans)
        b.setToolTip('<p>' + _('Play a text only game, without pictures of the story'))
        b.clicked.connect(self.skip_images)
        h.addWidget(b)
        self.image_next_button = b = QPushButton(QIcon.ic('ok.png'), _('&Start playing'), ans)
        b.clicked.connect(self.commit_image)
        h.addWidget(b)
        l.addLayout(h)
        return ans

    def config_and_recommendations(self, parent: QWidget, config: ConfigureAI, recommendations: RecommendationsPanel) -> QHBoxLayout:
        # The provider settings on the left, scrolling as they can be tall,
        # with the panel of recommended models on the right.
        ans = QHBoxLayout()
        sa = QScrollArea(parent)
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.Shape.NoFrame)
        sa.setWidget(config)
        ans.addWidget(sa, stretch=2)
        ans.addWidget(recommendations, stretch=1)
        return ans

    # }}}

    # Navigation {{{

    def show_intro_page(self) -> None:
        self.stack.setCurrentWidget(self.intro_page)

    def show_text_page(self) -> None:
        self.stack.setCurrentWidget(self.text_page)

    def show_image_page(self) -> None:
        self.stack.setCurrentWidget(self.image_page)

    def update_button_states(self) -> None:
        # The user cannot move on until the AI of the current panel can
        # actually be used, i.e. has an API key or whatever else it needs.
        for b, config, ready_tt, unready_tt in (
            (
                self.text_next_button,
                self.text_config,
                _('Go on to choose the AI used to generate pictures of the story'),
                _('First finish configuring the AI used to tell the story'),
            ),
            (
                self.image_next_button,
                self.image_config,
                _('Start playing, with pictures of the story generated by this AI'),
                _('First finish configuring the AI used to draw the pictures, or click "Skip pictures"'),
            ),
        ):
            ready = config.is_ready_for_use
            b.setEnabled(ready)
            b.setToolTip('<p>' + (ready_tt if ready else unready_tt))

    # }}}

    def save_text_settings(self, plugin: AIProviderPlugin, config_widget: AIConfigWidget) -> None:
        data.save_ai_settings('text', plugin.name, config_widget.settings)

    def save_image_settings(self, plugin: AIProviderPlugin, config_widget: AIConfigWidget) -> None:
        data.save_ai_settings('image', plugin.name, config_widget.settings)

    def commit_text(self) -> None:
        if self.text_config.commit():
            self.show_image_page()

    def commit_image(self) -> None:
        if self.image_config.commit():
            data.mark_image_skipped(False)
            self.configured.emit()

    def skip_images(self) -> None:
        data.mark_image_skipped(True)
        self.configured.emit()


if __name__ == '__main__':
    from calibre.gui2 import Application

    app = Application([])
    w = WelcomeWidget()
    w.configured.connect(lambda: print('AIs configured'))
    w.resize(1000, 720)
    w.show()
    app.exec()
    del w
    del app
