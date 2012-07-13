#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import zipfile

from PyQt4.Qt import QFont, QVariant, QDialog

from calibre.constants import iswindows, isxp
from calibre.utils.config import Config, StringConfig
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

class ConfigDialog(QDialog, Ui_Dialog):

    def __init__(self, shortcuts, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)

        opts = config().parse()
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
        self.standard_font.setCurrentIndex({'serif':0, 'sans':1, 'mono':2}[opts.standard_font])
        self.css.setPlainText(opts.user_css)
        self.css.setToolTip(_('Set the user CSS stylesheet. This can be used to customize the look of all books.'))
        self.max_fs_width.setValue(opts.max_fs_width)
        with zipfile.ZipFile(P('viewer/hyphenate/patterns.zip',
            allow_user_override=False), 'r') as zf:
            pats = [x.split('.')[0].replace('-', '_') for x in zf.namelist()]
        names = list(map(get_language, pats))
        pmap = {}
        for i in range(len(pats)):
            pmap[names[i]] = pats[i]
        for x in sorted(names):
            self.hyphenate_default_lang.addItem(x, QVariant(pmap[x]))
        try:
            idx = pats.index(opts.hyphenate_default_lang)
        except ValueError:
            idx = pats.index('en_us')
        idx = self.hyphenate_default_lang.findText(names[idx])
        self.hyphenate_default_lang.setCurrentIndex(idx)
        self.hyphenate.setChecked(opts.hyphenate)
        self.hyphenate_default_lang.setEnabled(opts.hyphenate)
        self.shortcuts = shortcuts
        self.shortcut_config = ShortcutConfig(shortcuts, parent=self)
        p = self.tabs.widget(1)
        p.layout().addWidget(self.shortcut_config)
        self.opt_fit_images.setChecked(opts.fit_images)
        if isxp:
            self.hyphenate.setVisible(False)
            self.hyphenate_default_lang.setVisible(False)
            self.hyphenate_label.setVisible(False)
        self.opt_fullscreen_clock.setChecked(opts.fullscreen_clock)

    def accept(self, *args):
        if self.shortcut_config.is_editing:
            from calibre.gui2 import info_dialog
            info_dialog(self, _('Still editing'),
                    _('You are in the middle of editing a keyboard shortcut'
                        ' first complete that, by clicking outside the '
                        ' shortcut editing box.'), show=True)
            return
        c = config()
        c.set('serif_family', unicode(self.serif_family.currentFont().family()))
        c.set('sans_family', unicode(self.sans_family.currentFont().family()))
        c.set('mono_family', unicode(self.mono_family.currentFont().family()))
        c.set('default_font_size', self.default_font_size.value())
        c.set('mono_font_size', self.mono_font_size.value())
        c.set('standard_font', {0:'serif', 1:'sans', 2:'mono'}[self.standard_font.currentIndex()])
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
        return QDialog.accept(self, *args)



