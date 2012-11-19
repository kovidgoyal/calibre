#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import zipfile
from functools import partial

from PyQt4.Qt import (QFont, QVariant, QDialog, Qt, QColor, QColorDialog,
        QMenu, QInputDialog)

from calibre.constants import iswindows, isxp
from calibre.utils.config import Config, StringConfig, JSONConfig
from calibre.gui2.shortcuts import ShortcutConfig
from calibre.gui2.viewer.config_ui import Ui_Dialog
from calibre.utils.localization import get_language

def config(defaults=None):
    desc = _('Options to customize the ebook viewer')
    if defaults is None:
        c = Config('viewer', desc)
    else:
        c = StringConfig(defaults, desc)

    c.add_opt('remember_window_size', default=False,
        help=_('Remember last used window size'))
    c.add_opt('user_css', default='',
              help=_('Set the user CSS stylesheet. This can be used to customize the look of all books.'))
    c.add_opt('max_fs_width', default=800,
        help=_("Set the maximum width that the book's text and pictures will take"
        " when in fullscreen mode. This allows you to read the book text"
        " without it becoming too wide."))
    c.add_opt('fit_images', default=True,
            help=_('Resize images larger than the viewer window to fit inside it'))
    c.add_opt('hyphenate', default=False, help=_('Hyphenate text'))
    c.add_opt('hyphenate_default_lang', default='en',
            help=_('Default language for hyphenation rules'))
    c.add_opt('remember_current_page', default=True,
            help=_('Save the current position in the document, when quitting'))
    c.add_opt('wheel_flips_pages', default=False,
            help=_('Have the mouse wheel turn pages'))
    c.add_opt('line_scrolling_stops_on_pagebreaks', default=False,
            help=_('Prevent the up and down arrow keys from scrolling past '
                'page breaks'))
    c.add_opt('page_flip_duration', default=0.5,
            help=_('The time, in seconds, for the page flip animation. Default'
                ' is half a second.'))
    c.add_opt('font_magnification_step', default=0.2,
            help=_('The amount by which to change the font size when clicking'
                ' the font larger/smaller buttons. Should be a number between '
                '0 and 1.'))
    c.add_opt('fullscreen_clock', default=False, action='store_true',
            help=_('Show a clock in fullscreen mode.'))
    c.add_opt('fullscreen_pos', default=False, action='store_true',
            help=_('Show reading position in fullscreen mode.'))
    c.add_opt('fullscreen_scrollbar', default=True, action='store_false',
            help=_('Show the scrollbar in fullscreen mode.'))
    c.add_opt('start_in_fullscreen', default=False, action='store_true',
              help=_('Start viewer in full screen mode'))
    c.add_opt('show_fullscreen_help', default=True, action='store_false',
              help=_('Show full screen usage help'))
    c.add_opt('cols_per_screen', default=1)
    c.add_opt('use_book_margins', default=False, action='store_true')
    c.add_opt('top_margin', default=20)
    c.add_opt('side_margin', default=40)
    c.add_opt('bottom_margin', default=20)
    c.add_opt('text_color', default=None)
    c.add_opt('background_color', default=None)

    fonts = c.add_group('FONTS', _('Font options'))
    fonts('serif_family', default='Times New Roman' if iswindows else 'Liberation Serif',
          help=_('The serif font family'))
    fonts('sans_family', default='Verdana' if iswindows else 'Liberation Sans',
          help=_('The sans-serif font family'))
    fonts('mono_family', default='Courier New' if iswindows else 'Liberation Mono',
          help=_('The monospaced font family'))
    fonts('default_font_size', default=20, help=_('The standard font size in px'))
    fonts('mono_font_size', default=16, help=_('The monospaced font size in px'))
    fonts('standard_font', default='serif', help=_('The standard font type'))

    return c

def load_themes():
    return JSONConfig('viewer_themes')

class ConfigDialog(QDialog, Ui_Dialog):

    def __init__(self, shortcuts, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)

        for x in ('text', 'background'):
            getattr(self, 'change_%s_color_button'%x).clicked.connect(
                            partial(self.change_color, x, reset=False))
            getattr(self, 'reset_%s_color_button'%x).clicked.connect(
                    partial(self.change_color, x, reset=True))
        self.css.setToolTip(_('Set the user CSS stylesheet. This can be used to customize the look of all books.'))

        self.shortcuts = shortcuts
        self.shortcut_config = ShortcutConfig(shortcuts, parent=self)
        bb = self.buttonBox
        bb.button(bb.RestoreDefaults).clicked.connect(self.restore_defaults)

        with zipfile.ZipFile(P('viewer/hyphenate/patterns.zip',
            allow_user_override=False), 'r') as zf:
            pats = [x.split('.')[0].replace('-', '_') for x in zf.namelist()]
        names = list(map(get_language, pats))
        pmap = {}
        for i in range(len(pats)):
            pmap[names[i]] = pats[i]
        for x in sorted(names):
            self.hyphenate_default_lang.addItem(x, QVariant(pmap[x]))
        self.hyphenate_pats = pats
        self.hyphenate_names = names
        p = self.tabs.widget(1)
        p.layout().addWidget(self.shortcut_config)

        if isxp:
            self.hyphenate.setVisible(False)
            self.hyphenate_default_lang.setVisible(False)
            self.hyphenate_label.setVisible(False)

        self.themes = load_themes()
        self.save_theme_button.clicked.connect(self.save_theme)
        self.load_theme_button.m = m = QMenu()
        self.load_theme_button.setMenu(m)
        m.triggered.connect(self.load_theme)
        self.delete_theme_button.m = m = QMenu()
        self.delete_theme_button.setMenu(m)
        m.triggered.connect(self.delete_theme)

        opts = config().parse()
        self.load_options(opts)
        self.init_load_themes()

    def save_theme(self):
        themename, ok = QInputDialog.getText(self, _('Theme name'),
                _('Choose a name for this theme'))
        if not ok: return
        themename = unicode(themename).strip()
        if not themename: return
        c = config('')
        c.add_opt('theme_name_xxx', default=themename)
        self.save_options(c)
        self.themes['theme_'+themename] = c.src
        self.init_load_themes()
        self.theming_message.setText(_('Saved settings as the theme named: %s')%
            themename)

    def init_load_themes(self):
        for x in ('load', 'delete'):
            m = getattr(self, '%s_theme_button'%x).menu()
            m.clear()
            for x in self.themes.iterkeys():
                title = x[len('theme_'):]
                ac = m.addAction(title)
                ac.theme_id = x

    def load_theme(self, ac):
        theme = ac.theme_id
        raw = self.themes[theme]
        self.load_options(config(raw).parse())
        self.theming_message.setText(_('Loaded settings from the theme %s')%
                theme[len('theme_'):])

    def delete_theme(self, ac):
        theme = ac.theme_id
        del self.themes[theme]
        self.init_load_themes()
        self.theming_message.setText(_('Deleted the theme named: %s')%
                theme[len('theme_'):])

    def restore_defaults(self):
        opts = config('').parse()
        self.load_options(opts)

    def load_options(self, opts):
        self.opt_remember_window_size.setChecked(opts.remember_window_size)
        self.opt_remember_current_page.setChecked(opts.remember_current_page)
        self.opt_wheel_flips_pages.setChecked(opts.wheel_flips_pages)
        self.opt_page_flip_duration.setValue(opts.page_flip_duration)
        fms = opts.font_magnification_step
        if fms < 0.01 or fms > 1:
            fms = 0.2
        self.opt_font_mag_step.setValue(int(fms*100))
        self.opt_line_scrolling_stops_on_pagebreaks.setChecked(
                opts.line_scrolling_stops_on_pagebreaks)
        self.serif_family.setCurrentFont(QFont(opts.serif_family))
        self.sans_family.setCurrentFont(QFont(opts.sans_family))
        self.mono_family.setCurrentFont(QFont(opts.mono_family))
        self.default_font_size.setValue(opts.default_font_size)
        self.mono_font_size.setValue(opts.mono_font_size)
        self.standard_font.setCurrentIndex(
                {'serif':0, 'sans':1, 'mono':2}[opts.standard_font])
        self.css.setPlainText(opts.user_css)
        self.max_fs_width.setValue(opts.max_fs_width)
        pats, names = self.hyphenate_pats, self.hyphenate_names
        try:
            idx = pats.index(opts.hyphenate_default_lang)
        except ValueError:
            idx = pats.index('en_us')
        idx = self.hyphenate_default_lang.findText(names[idx])
        self.hyphenate_default_lang.setCurrentIndex(idx)
        self.hyphenate.setChecked(opts.hyphenate)
        self.hyphenate_default_lang.setEnabled(opts.hyphenate)
        self.opt_fit_images.setChecked(opts.fit_images)
        self.opt_fullscreen_clock.setChecked(opts.fullscreen_clock)
        self.opt_fullscreen_scrollbar.setChecked(opts.fullscreen_scrollbar)
        self.opt_start_in_fullscreen.setChecked(opts.start_in_fullscreen)
        self.opt_show_fullscreen_help.setChecked(opts.show_fullscreen_help)
        self.opt_fullscreen_pos.setChecked(opts.fullscreen_pos)
        self.opt_cols_per_screen.setValue(opts.cols_per_screen)
        self.opt_override_book_margins.setChecked(not opts.use_book_margins)
        for x in ('top', 'bottom', 'side'):
            getattr(self, 'opt_%s_margin'%x).setValue(getattr(opts,
                x+'_margin'))
        for x in ('text', 'background'):
            setattr(self, 'current_%s_color'%x, getattr(opts, '%s_color'%x))
        self.update_sample_colors()

    def change_color(self, which, reset=False):
        if reset:
            setattr(self, 'current_%s_color'%which, None)
        else:
            initial = getattr(self, 'current_%s_color'%which)
            if initial:
                initial = QColor(initial)
            else:
                initial = Qt.black if which == 'text' else Qt.white
            title = (_('Choose text color') if which == 'text' else
                    _('Choose background color'))
            col = QColorDialog.getColor(initial, self,
                    title, QColorDialog.ShowAlphaChannel)
            if col.isValid():
                name = unicode(col.name())
                setattr(self, 'current_%s_color'%which, name)
        self.update_sample_colors()

    def update_sample_colors(self):
        for x in ('text', 'background'):
            val = getattr(self, 'current_%s_color'%x)
            if not val: val = 'inherit' if x == 'text' else 'transparent'
            ss = 'QLabel { %s: %s }'%('background-color' if x == 'background'
                    else 'color', val)
            getattr(self, '%s_color_sample'%x).setStyleSheet(ss)

    def accept(self, *args):
        if self.shortcut_config.is_editing:
            from calibre.gui2 import info_dialog
            info_dialog(self, _('Still editing'),
                    _('You are in the middle of editing a keyboard shortcut'
                        ' first complete that, by clicking outside the '
                        ' shortcut editing box.'), show=True)
            return
        self.save_options(config())
        return QDialog.accept(self, *args)

    def save_options(self, c):
        c.set('serif_family', unicode(self.serif_family.currentFont().family()))
        c.set('sans_family', unicode(self.sans_family.currentFont().family()))
        c.set('mono_family', unicode(self.mono_family.currentFont().family()))
        c.set('default_font_size', self.default_font_size.value())
        c.set('mono_font_size', self.mono_font_size.value())
        c.set('standard_font', {0:'serif', 1:'sans', 2:'mono'}[
            self.standard_font.currentIndex()])
        c.set('user_css', unicode(self.css.toPlainText()))
        c.set('remember_window_size', self.opt_remember_window_size.isChecked())
        c.set('fit_images', self.opt_fit_images.isChecked())
        c.set('max_fs_width', int(self.max_fs_width.value()))
        c.set('hyphenate', self.hyphenate.isChecked())
        c.set('remember_current_page', self.opt_remember_current_page.isChecked())
        c.set('wheel_flips_pages', self.opt_wheel_flips_pages.isChecked())
        c.set('page_flip_duration', self.opt_page_flip_duration.value())
        c.set('font_magnification_step',
                float(self.opt_font_mag_step.value())/100.)
        idx = self.hyphenate_default_lang.currentIndex()
        c.set('hyphenate_default_lang',
                str(self.hyphenate_default_lang.itemData(idx).toString()))
        c.set('line_scrolling_stops_on_pagebreaks',
                self.opt_line_scrolling_stops_on_pagebreaks.isChecked())
        c.set('fullscreen_clock', self.opt_fullscreen_clock.isChecked())
        c.set('fullscreen_pos', self.opt_fullscreen_pos.isChecked())
        c.set('fullscreen_scrollbar', self.opt_fullscreen_scrollbar.isChecked())
        c.set('show_fullscreen_help', self.opt_show_fullscreen_help.isChecked())
        c.set('cols_per_screen', int(self.opt_cols_per_screen.value()))
        c.set('use_book_margins', not
                self.opt_override_book_margins.isChecked())
        c.set('text_color', self.current_text_color)
        c.set('background_color', self.current_background_color)
        for x in ('top', 'bottom', 'side'):
            c.set(x+'_margin', int(getattr(self, 'opt_%s_margin'%x).value()))


