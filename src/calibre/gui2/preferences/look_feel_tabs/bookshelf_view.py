#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2025, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from functools import partial

from qt.core import QTabWidget, pyqtSignal

from calibre.gui2 import gprefs
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.preferences import LazyConfigWidgetBase
from calibre.gui2.preferences.look_feel_tabs.bookshelf_view_ui import Ui_Form


class BookshelfTab(QTabWidget, LazyConfigWidgetBase, Ui_Form):

    changed_signal = pyqtSignal()
    restart_now = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

    def genesis(self, gui):
        self.gui = gui
        db = self.gui.current_db
        r = self.register

        r('bookshelf_shadow', gprefs)
        r('bookshelf_thumbnail', gprefs)
        r('bookshelf_centered', gprefs)
        r('bookshelf_variable_height', gprefs)
        r('bookshelf_fade_time', gprefs)
        r('bookshelf_hover_shift', gprefs)
        r('bookshelf_hover_above', gprefs)

        r('bookshelf_title_template', db.prefs)
        r('bookshelf_pages_template', db.prefs)
        r('bookshelf_use_book_size', db.prefs)

        self.bs_background_box.link_config('bookshelf_background')

        self.template_title_button.clicked.connect(partial(self.edit_template_button, self.opt_bookshelf_title_template))
        self.template_pages_button.clicked.connect(partial(self.edit_template_button, self.opt_bookshelf_pages_template))

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
        gui.bookshelf_view.refresh_settings()
        gui.bookshelf_view.template_inited = False
