#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QApplication, QFont, QFontInfo, QFontDialog

from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.gui2.preferences.look_feel_ui import Ui_Form
from calibre.gui2 import config, gprefs, qt_app
from calibre.utils.localization import available_translations, \
    get_language, get_lang
from calibre.utils.config import prefs

class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui

        r = self.register

        r('gui_layout', config, restart_required=True, choices=
                [(_('Wide'), 'wide'), (_('Narrow'), 'narrow')])

        r('cover_flow_queue_length', config, restart_required=True)

        lang = get_lang()
        if lang is None or lang not in available_translations():
            lang = 'en'
        items = [(l, get_language(l)) for l in available_translations() \
                 if l != lang]
        if lang != 'en':
            items.append(('en', get_language('en')))
        items.sort(cmp=lambda x, y: cmp(x[1].lower(), y[1].lower()))
        choices = [(y, x) for x, y in items]
        # Default language is the autodetected one
        choices = [(get_language(lang), lang)] + choices
        r('language', prefs, choices=choices, restart_required=True)

        r('show_avg_rating', config)
        r('disable_animations', config)
        r('systray_icon', config, restart_required=True)
        r('show_splash_screen', gprefs)
        r('disable_tray_notification', config)
        r('use_roman_numerals_for_series_number', config)
        r('separate_cover_flow', config, restart_required=True)
        r('search_as_you_type', config)
        r('show_child_bar', gprefs)

        choices = [(_('Small'), 'small'), (_('Medium'), 'medium'),
            (_('Large'), 'large')]
        r('toolbar_icon_size', gprefs, choices=choices)

        choices = [(_('Automatic'), 'auto'), (_('Always'), 'always'),
            (_('Never'), 'never')]
        r('toolbar_text', gprefs, choices=choices)

        self.current_font = None
        self.change_font_button.clicked.connect(self.change_font)


    def initialize(self):
        ConfigWidgetBase.initialize(self)
        self.current_font = gprefs['font']
        self.update_font_display()

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        ofont = self.current_font
        self.current_font = None
        if ofont is not None:
            self.changed_signal.emit()
            self.update_font_display()

    def build_font_obj(self):
        font_info = self.current_font
        if font_info is not None:
            font = QFont(*font_info)
        else:
            font = qt_app.original_font
        return font

    def update_font_display(self):
        font = self.build_font_obj()
        fi = QFontInfo(font)
        name = unicode(fi.family())

        self.font_display.setFont(font)
        self.font_display.setText(_('Current font:') + ' ' + name +
                ' [%dpt]'%fi.pointSize())

    def change_font(self, *args):
        fd = QFontDialog(self.build_font_obj(), self)
        if fd.exec_() == fd.Accepted:
            font = fd.selectedFont()
            fi = QFontInfo(font)
            self.current_font = (unicode(fi.family()), fi.pointSize(),
                    fi.weight(), fi.italic())
            self.update_font_display()
            self.changed_signal.emit()

    def commit(self, *args):
        rr = ConfigWidgetBase.commit(self, *args)
        if self.current_font != gprefs['font']:
            gprefs['font'] = self.current_font
            QApplication.setFont(self.font_display.font())
            rr = True
        return rr


    def refresh_gui(self, gui):
        gui.search.search_as_you_type(config['search_as_you_type'])
        self.update_font_display()

if __name__ == '__main__':
    app = QApplication([])
    test_widget('Interface', 'Look & Feel')

