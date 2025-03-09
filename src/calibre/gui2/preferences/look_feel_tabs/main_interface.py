#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2025, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from qt.core import QApplication, QDialog, QFont, QFontDialog, QFontInfo

from calibre.constants import ismacos, iswindows
from calibre.gui2 import config, gprefs, icon_resource_manager
from calibre.gui2.preferences import LazyConfigWidgetBase, Setting, set_help_tips
from calibre.gui2.preferences.look_feel_tabs.main_interface_ui import Ui_main_interface_tab as Ui_Form
from calibre.gui2.widgets import BusyCursor
from calibre.utils.config import prefs
from calibre.utils.localization import available_translations, get_lang, get_language


class LanguageSetting(Setting):

    def commit(self):
        val = self.get_gui_val()
        oldval = self.get_config_val()
        if val != oldval:
            gprefs.set('last_used_language', oldval)
        return super().commit()


class MainInterfaceTab(LazyConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        self.ui_style_available = True
        if not ismacos and not iswindows:
            self.label_widget_style.setVisible(False)
            self.opt_ui_style.setVisible(False)
            self.ui_style_available = False

        r = self.register

        try:
            self.icon_theme_title = icon_resource_manager.user_theme_title
        except Exception:
            self.icon_theme_title = _('Default icons')
        self.icon_theme.setText(_('Icon theme: <b>%s</b>') % self.icon_theme_title)
        self.commit_icon_theme = None
        self.icon_theme_button.clicked.connect(self.choose_icon_theme)

        r('ui_style', gprefs, restart_required=True, choices=[(_('System default'), 'system'), (_('calibre style'), 'calibre')])
        r('book_list_tooltips', gprefs)
        r('dnd_merge', gprefs)
        r('wrap_toolbar_text', gprefs, restart_required=True)
        r('show_layout_buttons', gprefs)
        r('show_sb_all_actions_button', gprefs)
        # r('show_sb_preference_button', gprefs)
        r('row_numbers_in_book_list', gprefs)
        r('cover_corner_radius', gprefs)
        r('cover_corner_radius_unit', gprefs, choices=[(_('Pixels'), 'px'), (_('Percentage'), '%')])
        r('book_list_extra_row_spacing', gprefs)
        r('booklist_grid', gprefs)

        def get_esc_lang(l):
            if l == 'en':
                return 'English'
            return get_language(l)

        lang = get_lang()
        if lang is None or lang not in available_translations():
            lang = 'en'
        items = [(l, get_esc_lang(l)) for l in available_translations()
                 if l != lang]
        if lang != 'en':
            items.append(('en', get_esc_lang('en')))
        items.sort(key=lambda x: x[1].lower())
        choices = [(y, x) for x, y in items]
        # Default language is the autodetected one
        choices = [(get_language(lang), lang)] + choices
        lul = gprefs.get('last_used_language')
        if lul and (lul in available_translations() or lul in ('en', 'eng')):
            choices.insert(1, ((get_language(lul), lul)))
        r('language', prefs, choices=choices, restart_required=True, setting=LanguageSetting)

        r('disable_animations', config)
        r('systray_icon', config, restart_required=True)
        r('show_splash_screen', gprefs)
        r('disable_tray_notification', config)

        choices = [(_('Off'), 'off'), (_('Small'), 'small'),
            (_('Medium-small'), 'mid-small'), (_('Medium'), 'medium'), (_('Large'), 'large')]
        r('toolbar_icon_size', gprefs, choices=choices)

        choices = [(_('If there is enough room'), 'auto'), (_('Always'), 'always'),
            (_('Never'), 'never')]
        r('toolbar_text', gprefs, choices=choices)

        self.current_font = self.initial_font = None
        self.change_font_button.clicked.connect(self.change_font)

        self.opt_ui_style.currentIndexChanged.connect(self.update_color_palette_state)
        self.opt_gui_layout.addItem(_('Wide'), 'wide')
        self.opt_gui_layout.addItem(_('Narrow'), 'narrow')
        self.opt_gui_layout.currentIndexChanged.connect(self.changed_signal)
        set_help_tips(self.opt_gui_layout, config.help('gui_layout'))
        self.button_adjust_colors.clicked.connect(self.adjust_colors)

    def lazy_initialize(self):
        font = gprefs['font']
        if font is not None:
            font = list(font)
            font.append(gprefs.get('font_stretch', QFont.Stretch.Unstretched))
        self.current_font = self.initial_font = font
        self.update_font_display()
        self.update_color_palette_state()
        self.opt_gui_layout.setCurrentIndex(0 if self.gui.layout_container.is_wide else 1)

    def adjust_colors(self):
        from calibre.gui2.dialogs.palette import PaletteConfig
        d = PaletteConfig(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            d.apply_settings()
            self.changed_signal.emit()

    def update_color_palette_state(self):
        if self.ui_style_available:
            enabled = self.opt_ui_style.currentData() == 'calibre'
            self.button_adjust_colors.setEnabled(enabled)

    def choose_icon_theme(self):
        from calibre.gui2.icon_theme import ChooseTheme
        d = ChooseTheme(self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.commit_icon_theme = d.commit_changes
            self.icon_theme_title = d.new_theme_title or _('Default icons')
            self.icon_theme.setText(_('Icon theme: <b>%s</b>') % self.icon_theme_title)
            self.changed_signal.emit()

    def build_font_obj(self):
        font_info = QApplication.instance().original_font if self.current_font is None else self.current_font
        font = QFont(*(font_info[:4]))
        font.setStretch(font_info[4])
        return font

    def change_font(self, *args):
        fd = QFontDialog(self.build_font_obj(), self)
        if fd.exec() == QDialog.DialogCode.Accepted:
            font = fd.selectedFont()
            fi = QFontInfo(font)
            self.current_font = [str(fi.family()), fi.pointSize(),
                    fi.weight(), fi.italic(), font.stretch()]
            self.update_font_display()
            self.changed_signal.emit()

    def update_font_display(self):
        font = self.build_font_obj()
        fi = QFontInfo(font)
        name = str(fi.family())

        self.font_display.setFont(font)
        self.font_display.setText(name + f' [{fi.pointSize()}pt]')

    def commit(self):
        rr = LazyConfigWidgetBase.commit(self)
        with BusyCursor():
            if self.current_font != self.initial_font:
                gprefs['font'] = (self.current_font[:4] if self.current_font else None)
                gprefs['font_stretch'] = (self.current_font[4] if self.current_font
                        is not None else QFont.Stretch.Unstretched)
                QApplication.setFont(self.font_display.font())
                rr = True
            if self.commit_icon_theme is not None:
                self.commit_icon_theme()
            self.gui.layout_container.change_layout(self.gui, self.opt_gui_layout.currentIndex() == 0)
        return rr

    def restore_defaults(self):
        LazyConfigWidgetBase.restore_defaults(self)
        ofont = self.current_font
        self.current_font = None
        if ofont is not None:
            self.changed_signal.emit()
            self.main_interface_tab.update_font_display()
        self.opt_gui_layout.setCurrentIndex(0)
        self.changed_signal.emit()

    def refresh_gui(self, gui):
        gui.place_layout_buttons()
        self.update_font_display()
        gui.library_view.set_row_header_visibility()
        for view in 'library memory card_a card_b'.split():
            getattr(gui, view + '_view').set_row_header_visibility()
        gui.library_view.refresh_row_sizing()
        gui.sb_all_gui_actions_button.setVisible(gprefs['show_sb_all_actions_button'])
        # gui.sb_preferences_button.setVisible(gprefs['show_sb_preference_button'])
