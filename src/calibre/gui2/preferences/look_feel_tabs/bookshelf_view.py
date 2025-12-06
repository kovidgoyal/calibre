#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2025, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from qt.core import QKeySequence

from calibre import partial
from calibre.gui2 import config, gprefs
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.preferences import LazyConfigWidgetBase, set_help_tips
from calibre.gui2.preferences.look_feel_tabs import BROWSER_NARROW_VIEW_POSITION, BROWSER_NARROW_VIEW_POSITION_TIPS
from calibre.gui2.preferences.look_feel_tabs.bookshelf_view_ui import Ui_Form


class BookshelfView(LazyConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        db = self.gui.library_view.model().db
        r = self.register

        r('separate_cover_flow', config, restart_required=True)
        r('cb_fullscreen', gprefs)

        r('bs_shadow', gprefs)
        r('bs_thumbnail', gprefs)
        r('bs_centered', gprefs)
        r('bs_fade_time', gprefs)
        r('bs_hover_shift', gprefs)
        r('bs_hover_above', gprefs)

        r('bs_title_template', db.prefs)
        r('bs_statue_template', db.prefs)
        r('bs_pages_template', db.prefs)
        r('bs_use_book_size', db.prefs)

        self.template_title_button.clicked.connect(partial(self.edit_template_button, self.opt_bs_title_template))
        self.template_statue_button.clicked.connect(partial(self.edit_template_button, self.opt_bs_statue_template))
        self.template_pages_button.clicked.connect(partial(self.edit_template_button, self.opt_bs_pages_template))

        self.fs_help_msg.setText(self.fs_help_msg.text()%(
            QKeySequence(QKeySequence.StandardKey.FullScreen).toString(QKeySequence.SequenceFormat.NativeText)))

        r('cover_browser_narrow_view_position', gprefs, choices=BROWSER_NARROW_VIEW_POSITION)
        set_help_tips(self.opt_cover_browser_narrow_view_position, BROWSER_NARROW_VIEW_POSITION_TIPS)

    def edit_template_button(self, line_edit):
        rows = self.gui.library_view.selectionModel().selectedRows()
        mi = None
        db = self.gui.current_db.new_api
        if rows:
            ids = list(map(self.gui.library_view.model().id, rows))
            mi = []
            for bk in ids[0:min(10, len(ids))]:
                mi.append(db.get_proxy_metadata(bk))
        t = TemplateDialog(self, line_edit.text(), mi=mi, fm=db.field_metadata)
        t.setWindowTitle(_('Edit template for caption'))
        if t.exec():
            line_edit.setText(t.rule[1])

    def refresh_gui(self, gui):
        gui.bookshelf_view.enableShadow(gprefs['bs_shadow'])
        gui.bookshelf_view.enableThumbnail(gprefs['bs_thumbnail'])
        gui.bookshelf_view.enableCentered(gprefs['bs_centered'])
        gui.bookshelf_view.enableHoverShift(gprefs['bs_hover_shift'])
        gui.bookshelf_view.setFadeTime(gprefs['bs_fade_time'])
        gui.bookshelf_view.template_inited = False
