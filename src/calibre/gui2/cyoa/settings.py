#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Settings dialogs for the "Create Your Own Adventure" game: the main game
# settings dialog (AI providers and look & feel) and the configure-image-AI
# dialog shown the first time the player enables scene images.

from functools import partial

from qt.core import QFormLayout, QGroupBox, QHBoxLayout, QIcon, QLabel, QSpinBox, QTabWidget, QToolButton, QVBoxLayout, QWidget

from calibre.ai import AICapabilities
from calibre.ai.config import AIConfigWidget, ConfigureAI
from calibre.customize import AIProviderPlugin
from calibre.gui2.cyoa import data
from calibre.gui2.cyoa.text_display import apply_text_display_settings
from calibre.gui2.font_family_chooser import FontFamilyChooser
from calibre.gui2.widgets2 import ColorButton, Dialog
from calibre.utils.localization import _


class LookAndFeelTab(QWidget):
    # Controls the appearance of every widget that displays the text of the
    # story: the font it is displayed in, the colors used for it and how
    # long the lines of the main story text are allowed to get.

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        s = data.text_display_settings()
        l = QFormLayout(self)
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.family_chooser = fc = FontFamilyChooser(self)
        fc.font_family = s.font_family
        fc.setToolTip('<p>' + _('The font used to display the text of the story. Clear it to use the standard calibre font.'))
        l.addRow(_('&Font:'), fc)

        self.size_spin = ss = QSpinBox(self)
        ss.setRange(0, data.MAX_FONT_SIZE)
        ss.setSpecialValueText(_('Standard size'))
        ss.setSuffix(' ' + _('pt'))
        ss.setValue(s.font_size)
        ss.setToolTip(
            '<p>'
            + _(
                'The size of the text of the story. It can also be changed at any time with {0} and {1}, or by holding Ctrl and turning the mouse wheel.'
            ).format('Ctrl++', 'Ctrl+-')
        )
        l.addRow(_('Font &size:'), ss)

        self.foreground_button = fg = self.add_color_row(l, _('&Text color:'), s.foreground)
        self.background_button = bg = self.add_color_row(l, _('&Background color:'), s.background)
        for b in (fg, bg):
            b.setToolTip('<p>' + _('Leave this unset to follow the standard calibre colors, which adapt to the light or dark theme in use.'))

        self.line_width_spin = lw = QSpinBox(self)
        lw.setRange(0, data.MAX_LINE_WIDTH_LIMIT)
        lw.setSpecialValueText(_('No limit'))
        lw.setSuffix(' ' + _('characters'))
        lw.setValue(s.max_line_width)
        lw.setToolTip(
            '<p>'
            + _(
                'Very long lines of text are tiring to read, so the text of the story is limited to this many characters per line,'
                ' centered in the space available to it. Set it to zero to use the full width.'
            )
        )
        l.addRow(_('Maximum &line length:'), lw)

    def add_color_row(self, l: QFormLayout, label: str, color: str) -> ColorButton:
        # A color button with a button next to it to go back to the standard
        # color, which is what an unset color means.
        b = ColorButton(color, self, choose_text=_('Standard color'))
        la = QLabel(label, self)
        la.setBuddy(b)
        h = QHBoxLayout()
        h.addWidget(b)
        clear = QToolButton(self)
        clear.setIcon(QIcon.ic('edit-clear.png'))
        clear.setToolTip(_('Use the standard color'))
        clear.clicked.connect(partial(setattr, b, 'color', None))
        h.addWidget(clear), h.addStretch(10)
        l.addRow(la, h)
        return b

    @property
    def settings(self) -> data.TextDisplaySettings:
        return data.TextDisplaySettings(
            font_family=self.family_chooser.font_family or '',
            font_size=self.size_spin.value(),
            foreground=self.foreground_button.color or '',
            background=self.background_button.color or '',
            max_line_width=self.line_width_spin.value(),
        )


class ConfigureImageAIDialog(Dialog):
    # Asks the player to configure the AI used to generate pictures of each
    # scene, saving the settings the same way as the welcome screen.

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(_('Configure image AI'), 'cyoa-configure-image-ai', parent)

    def setup_ui(self) -> None:
        l = QVBoxLayout(self)
        self.msg_label = la = QLabel(
            '<p>' + _('No AI for image generation has been configured for the game. To show pictures of each scene, configure one below:')
        )
        la.setWordWrap(True)
        l.addWidget(la)
        # Construct the provider config widget inside the CYOA settings
        # overlay so it displays the settings used for the game, with API
        # keys falling through to the common AI preferences.
        with data.cyoa_ai_settings():
            self.image_config = ic = ConfigureAI(
                AICapabilities.text_to_image,
                parent=self,
                save_hook=self.save_image_settings,
                initial_provider_name=data.configured_provider_name('image'),
            )
        l.addWidget(ic)
        l.addWidget(self.bb)

    def save_image_settings(self, plugin: AIProviderPlugin, config_widget: AIConfigWidget) -> None:
        data.save_ai_settings('image', plugin.name, config_widget.settings)

    def accept(self) -> None:
        if not self.image_config.commit():
            return
        super().accept()


class SettingsDialog(Dialog):
    # Lets the player change the AIs used to run the game mid-game: one tab
    # for the main AI that generates the story and one for the AI that
    # generates pictures of each scene, plus a tab controlling the look of
    # the widgets the story is displayed in. The AI settings are saved the
    # same way as on the welcome screen.

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(_('Game settings'), 'cyoa-settings', parent)

    def setup_ui(self) -> None:
        l = QVBoxLayout(self)
        self.tabs = tabs = QTabWidget(self)
        l.addWidget(tabs)
        # Construct the provider config widgets inside the CYOA settings
        # overlay so they display the settings used for the game, with API
        # keys falling through to the common AI preferences.
        with data.cyoa_ai_settings():
            text_tab = QWidget(self)
            tv = QVBoxLayout(text_tab)
            self.text_config = tc = ConfigureAI(
                AICapabilities.text_to_text,
                parent=text_tab,
                save_hook=self.save_text_settings,
                initial_provider_name=data.configured_provider_name('text'),
            )
            tv.addWidget(tc), tv.addStretch()
            tabs.addTab(text_tab, QIcon.ic('ai.png'), _('&Main AI'))

            image_tab = QWidget(self)
            iv = QVBoxLayout(image_tab)
            self.image_group = ig = QGroupBox(_('Generate &pictures of the story'), image_tab)
            ig.setCheckable(True)
            ig.setToolTip('<p>' + _('Uncheck this to play a text only game. You can always configure it later.'))
            gl = QVBoxLayout(ig)
            self.image_config = ic = ConfigureAI(
                AICapabilities.text_to_image,
                parent=ig,
                save_hook=self.save_image_settings,
                initial_provider_name=data.configured_provider_name('image'),
            )
            gl.addWidget(ic)
            ig.setChecked(bool(data.configured_provider_name('image')) and not data.image_skipped())
            iv.addWidget(ig), iv.addStretch()
            tabs.addTab(image_tab, QIcon.ic('view-image.png'), _('&Image generation AI'))

        look_tab = QWidget(self)
        lv = QVBoxLayout(look_tab)
        self.look_and_feel = laf = LookAndFeelTab(look_tab)
        lv.addWidget(laf), lv.addStretch()
        tabs.addTab(look_tab, QIcon.ic('format-text-color.png'), _('&Look && feel'))
        l.addWidget(self.bb)

    def save_text_settings(self, plugin: AIProviderPlugin, config_widget: AIConfigWidget) -> None:
        data.save_ai_settings('text', plugin.name, config_widget.settings)

    def save_image_settings(self, plugin: AIProviderPlugin, config_widget: AIConfigWidget) -> None:
        data.save_ai_settings('image', plugin.name, config_widget.settings)

    def accept(self) -> None:
        if not self.text_config.commit():
            self.tabs.setCurrentIndex(0)
            return
        if self.image_group.isChecked():
            if not self.image_config.commit():
                self.tabs.setCurrentIndex(1)
                return
            data.mark_image_skipped(False)
        else:
            data.mark_image_skipped(True)
        # Applied to every text display widget in the game, not just the ones
        # of the window this dialog was opened from.
        data.set_text_display_settings(self.look_and_feel.settings)
        apply_text_display_settings()
        super().accept()
