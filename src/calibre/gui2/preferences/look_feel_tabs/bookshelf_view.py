#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2025, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from contextlib import suppress
from functools import partial

from qt.core import QDialog, QDialogButtonBox, QInputDialog, QLabel, QTabWidget, QTextBrowser, QVBoxLayout, pyqtSignal

from calibre.gui2 import gprefs
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.preferences import LazyConfigWidgetBase
from calibre.gui2.preferences.look_feel_tabs.bookshelf_view_ui import Ui_bookshelf_tab as Ui_Form
from calibre.utils.filenames import make_long_path_useable


class LogViewer(QDialog):

    def __init__(self, path: str, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_('Log of page count failures'))
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(_('The log is stored at: {}').format(path))
        la.setWordWrap(True)
        l.addWidget(la)
        self.text = t = QTextBrowser(self)
        t.setPlainText(text)
        l.addWidget(t)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        l.addWidget(bb)
        self.resize(600, 500)


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
        r('bookshelf_variable_height', gprefs)
        r('bookshelf_fade_time', gprefs)
        r('bookshelf_up_to_down', gprefs)
        r('bookshelf_height', gprefs)

        r('bookshelf_thumbnail', gprefs, choices=[
            (_('Full'), 'full'),
            (_('Cropped'), 'crops'),
            (_('Edge'), 'edge'),
            (_('Disable'), 'none'),
        ])
        self.opt_bookshelf_thumbnail.setToolTip(_('''\
<p><i>Full</i> - shows the full cover on the spine.
<p><i>Cropped</i> - shows only as much of the cover as will fit on the spine.
<p><i>Edge</i> - same as <i>Cropped</i> except only part of the spine is covered, the rest is a solid color.
<p><i>Disable</i> - The spine will be only the dominant color from the cover.'''))

        r('bookshelf_hover', gprefs, choices=[
            (_('Shift books on the shelf to make room'), 'shift'),
            (_('Above other books on the shelf'), 'above'),
            (_('Disable'), 'none'),
        ])

        r('bookshelf_title_template', db.prefs)
        r('bookshelf_author_template', db.prefs)
        r('bookshelf_spine_size_template', db.prefs)

        self.config_cache.link(
            self.gui.bookshelf_view.cover_cache,
            'bookshelf_disk_cache_size', 'bookshelf_cache_size_multiple',
        )
        self.opt_bookshelf_spine_size_template.setToolTip(_('''
<p>The template used to calculate a width for the displayed spine.
The template must evaluate to a decimal number between 0.0 and 1.0, which will be used to set the width of the books spine.
An empty template means a fixed spine size for all books.
<p>The special template {2} calculates the number of pages in the book and uses that. Note that
the page size calculation happens in the background, so until the count is completed, the
book size is used as a proxy.
<p>The special template {0} uses the book size to estimate a spine size.
The special template {1} uses a random size.
You can also use a number between 0.0 and 1.0 to pick a fixed size.
<p>
Note that this setting is per-library, which means that you have to set it again for every
different calibre library you use.</p>''').format('{size}', '{random}', '{pages}'))

        self.template_title_button.clicked.connect(partial(self.edit_template_button, self.opt_bookshelf_title_template, _('Edit template for title')))
        self.template_author_button.clicked.connect(partial(self.edit_template_button, self.opt_bookshelf_author_template, _('Edit template for author')))
        self.template_pages_button.clicked.connect(partial(self.edit_template_button, self.opt_bookshelf_spine_size_template, _('Edit template for book size')))
        self.use_pages_button.clicked.connect(self.use_pages)
        self.recount_button.clicked.connect(self.recount_pages)
        self.show_log_button.clicked.connect(self.show_log)

    def show_log(self) -> None:
        db = self.gui.current_db.new_api
        path = db.page_count_failures_log_path
        txt = ''
        with suppress(FileNotFoundError), open(make_long_path_useable(path)) as f:
            txt = f.read()
        LogViewer(path, txt, self).exec()

    def recount_pages(self) -> None:
        from calibre.gui2.dialogs.confirm_delete import confirm
        if confirm(_('This will cause calibre to rescan all books in your library and update page counts, where changed.'
                     ' The scanning happens in the background and can take up to an hour per thousand books'
                     ' depending on the size of the books and the power of your computer. This is'
                     ' typically never needed and is present mainly to aid debugging and testing. Are you sure?'),
                   'confirm-pages-recount', parent=self):
            db = self.gui.current_db.new_api
            db.mark_for_pages_recount()
            db.queue_pages_scan()
            self.gui.library_view.model().zero_page_cache.clear()
            self.gui.bookshelf_view.invalidate()

    def edit_template_button(self, line_edit, title):
        rows = self.gui.library_view.selectionModel().selectedRows()
        mi = None
        db = self.gui.current_db.new_api
        if rows:
            ids = list(map(self.gui.library_view.model().id, rows))
            mi = []
            for bk in ids[0:min(10, len(ids))]:
                mi.append(db.get_proxy_metadata(bk))
        t = TemplateDialog(self, line_edit.text(), mi=mi, fm=db.field_metadata)
        t.setWindowTitle(title)
        if t.exec():
            line_edit.setText(t.rule[1])

    def use_pages(self):
        fm = self.gui.current_db.new_api.field_metadata
        keys = tuple(k for k in fm.all_field_keys() if fm[k].get('name'))
        names = [fm[k]['name'] for k in keys]
        try:
            idx = keys.index('#pages')
        except ValueError:
            idx = 0
        item, ok = QInputDialog.getItem(self, _('Choose a column for pages'), _(
            'Choose a column from which to get the page count for the book, such as generated by the Count Pages plugin'),
                             names, idx)
        if item and ok and item in names:
            key = keys[names.index(item)]
            template = f'''\
python:
from calibre.gui2.library.bookshelf_view import width_from_pages

def evaluate(book, context):
    val = book.get({key!r})
    try:
        pages = max(0, int(val))
    except Exception:
        return '0.3'
    return str(width_from_pages(pages, num_of_pages_for_max_width=1500, logarithmic_factor=2))
'''
            self.opt_bookshelf_spine_size_template.setText(template)

    def refresh_gui(self, gui):
        gui.bookshelf_view.refresh_settings()
        gui.bookshelf_view.template_inited = False
