__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''Dialog to edit metadata in bulk'''

from threading import Thread

from PyQt4.Qt import QDialog, QGridLayout

from calibre.gui2.dialogs.metadata_bulk_ui import Ui_MetadataBulkDialog
from calibre.gui2.dialogs.tag_editor import TagEditor
from calibre.ebooks.metadata import string_to_authors, \
    authors_to_string
from calibre.gui2.custom_column_widgets import populate_metadata_page
from calibre.gui2.dialogs.progress import BlockingBusy
from calibre.gui2 import error_dialog, Dispatcher

class Worker(Thread):

    def __init__(self, args, db, ids, cc_widgets, callback):
        Thread.__init__(self)
        self.args = args
        self.db = db
        self.ids = ids
        self.error = None
        self.callback = callback
        self.cc_widgets = cc_widgets

    def doit(self):
        remove, add, au, aus, do_aus, rating, pub, do_series, \
            do_autonumber, do_remove_format, remove_format, do_swap_ta, \
            do_remove_conv, do_auto_author, series = self.args

        # first loop: do author and title. These will commit at the end of each
        # operation, because each operation modifies the file system. We want to
        # try hard to keep the DB and the file system in sync, even in the face
        # of exceptions or forced exits.
        for id in self.ids:
            if do_swap_ta:
                title = self.db.title(id, index_is_id=True)
                aum = self.db.authors(id, index_is_id=True)
                if aum:
                    aum = [a.strip().replace('|', ',') for a in aum.split(',')]
                    new_title = authors_to_string(aum)
                    self.db.set_title(id, new_title, notify=False)
                if title:
                    new_authors = string_to_authors(title)
                    self.db.set_authors(id, new_authors, notify=False)

            if au:
                self.db.set_authors(id, string_to_authors(au), notify=False)

        # All of these just affect the DB, so we can tolerate a total rollback
        for id in self.ids:
            if do_auto_author:
                x = self.db.author_sort_from_book(id, index_is_id=True)
                if x:
                    self.db.set_author_sort(id, x, notify=False, commit=False)

            if aus and do_aus:
                self.db.set_author_sort(id, aus, notify=False, commit=False)

            if rating != -1:
                self.db.set_rating(id, 2*rating, notify=False, commit=False)

            if pub:
                self.db.set_publisher(id, pub, notify=False, commit=False)

            if do_series:
                next = self.db.get_next_series_num_for(series)
                self.db.set_series(id, series, notify=False, commit=False)
                num = next if do_autonumber and series else 1.0
                self.db.set_series_index(id, num, notify=False, commit=False)

            if do_remove_format:
                self.db.remove_format(id, remove_format, index_is_id=True, notify=False, commit=False)

            if do_remove_conv:
                self.db.delete_conversion_options(id, 'PIPE', commit=False)
        self.db.commit()

        for w in self.cc_widgets:
            w.commit(self.ids)
        self.db.bulk_modify_tags(self.ids, add=add, remove=remove,
                notify=False)
        self.db.clean()

    def run(self):
        try:
            self.doit()
        except Exception, err:
            import traceback
            try:
                err = unicode(err)
            except:
                err = repr(err)
            self.error = (err, traceback.format_exc())

        self.callback()


class MetadataBulkDialog(QDialog, Ui_MetadataBulkDialog):

    def __init__(self, window, rows, db):
        QDialog.__init__(self, window)
        Ui_MetadataBulkDialog.__init__(self)
        self.setupUi(self)
        self.db = db
        self.ids = [db.id(r) for r in rows]
        self.box_title.setText('<p>' +
                _('Editing meta information for <b>%d books</b>') %
                len(rows))
        self.write_series = False
        self.changed = False

        all_tags = self.db.all_tags()
        self.tags.update_tags_cache(all_tags)
        self.remove_tags.update_tags_cache(all_tags)

        self.initialize_combos()

        for f in self.db.all_formats():
            self.remove_format.addItem(f)

        self.remove_format.setCurrentIndex(-1)

        self.series.currentIndexChanged[int].connect(self.series_changed)
        self.series.editTextChanged.connect(self.series_changed)
        self.tag_editor_button.clicked.connect(self.tag_editor)
        if len(db.custom_column_label_map) == 0:
            self.central_widget.tabBar().setVisible(False)
        else:
            self.create_custom_column_editors()
        self.exec_()

    def create_custom_column_editors(self):
        w = self.central_widget.widget(1)
        layout = QGridLayout()
        self.custom_column_widgets, self.__cc_spacers = \
            populate_metadata_page(layout, self.db, self.ids, parent=w,
                                   two_column=False, bulk=True)
        w.setLayout(layout)
        self.__custom_col_layouts = [layout]
        ans = self.custom_column_widgets
        for i in range(len(ans)-1):
            w.setTabOrder(ans[i].widgets[-1], ans[i+1].widgets[1])
            for c in range(2, len(ans[i].widgets), 2):
                w.setTabOrder(ans[i].widgets[c-1], ans[i].widgets[c+1])

    def initialize_combos(self):
        self.initalize_authors()
        self.initialize_series()
        self.initialize_publisher()

    def initalize_authors(self):
        all_authors = self.db.all_authors()
        all_authors.sort(cmp=lambda x, y : cmp(x[1], y[1]))

        for i in all_authors:
            id, name = i
            name = authors_to_string([name.strip().replace('|', ',') for n in name.split(',')])
            self.authors.addItem(name)
        self.authors.setEditText('')

    def initialize_series(self):
        all_series = self.db.all_series()
        all_series.sort(cmp=lambda x, y : cmp(x[1], y[1]))

        for i in all_series:
            id, name = i
            self.series.addItem(name)
        self.series.setEditText('')

    def initialize_publisher(self):
        all_publishers = self.db.all_publishers()
        all_publishers.sort(cmp=lambda x, y : cmp(x[1], y[1]))

        for i in all_publishers:
            id, name = i
            self.publisher.addItem(name)
        self.publisher.setEditText('')

    def tag_editor(self, *args):
        d = TagEditor(self, self.db, None)
        d.exec_()
        if d.result() == QDialog.Accepted:
            tag_string = ', '.join(d.tags)
            self.tags.setText(tag_string)
            self.tags.update_tags_cache(self.db.all_tags())
            self.remove_tags.update_tags_cache(self.db.all_tags())

    def accept(self):
        if len(self.ids) < 1:
            return QDialog.accept(self)

        self.changed = bool(self.ids)
        # Cache values from GUI so that Qt widgets are not used in
        # non GUI thread
        for w in getattr(self, 'custom_column_widgets', []):
            w.gui_val

        if self.remove_all_tags.isChecked():
            remove = self.db.all_tags()
        else:
            remove = unicode(self.remove_tags.text()).strip().split(',')
        add = unicode(self.tags.text()).strip().split(',')
        au = unicode(self.authors.text())
        aus = unicode(self.author_sort.text())
        do_aus = self.author_sort.isEnabled()
        rating = self.rating.value()
        pub = unicode(self.publisher.text())
        do_series = self.write_series
        series = unicode(self.series.currentText()).strip()
        do_autonumber = self.autonumber_series.isChecked()
        do_remove_format = self.remove_format.currentIndex() > -1
        remove_format = unicode(self.remove_format.currentText())
        do_swap_ta = self.swap_title_and_author.isChecked()
        do_remove_conv = self.remove_conversion_settings.isChecked()
        do_auto_author = self.auto_author_sort.isChecked()

        args = (remove, add, au, aus, do_aus, rating, pub, do_series,
                do_autonumber, do_remove_format, remove_format, do_swap_ta,
                do_remove_conv, do_auto_author, series)

        bb = BlockingBusy(_('Applying changes to %d books. This may take a while.')
                %len(self.ids), parent=self)
        self.worker = Worker(args, self.db, self.ids,
                getattr(self, 'custom_column_widgets', []),
                Dispatcher(bb.accept, parent=bb))
        self.worker.start()
        bb.exec_()

        if self.worker.error is not None:
            return error_dialog(self, _('Failed'),
                    self.worker.error[0], det_msg=self.worker.error[1],
                    show=True)
        return QDialog.accept(self)


    def series_changed(self, *args):
        self.write_series = True

