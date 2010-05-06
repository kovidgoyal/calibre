__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''Dialog to edit metadata in bulk'''

from PyQt4.QtCore import SIGNAL, QObject
from PyQt4.QtGui import QDialog, QGridLayout

from calibre.gui2.dialogs.metadata_bulk_ui import Ui_MetadataBulkDialog
from calibre.gui2.dialogs.tag_editor import TagEditor
from calibre.ebooks.metadata import string_to_authors, authors_to_sort_string, \
    authors_to_string
from calibre.gui2.custom_column_widgets import populate_bulk_metadata_page

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
        QObject.connect(self.button_box, SIGNAL("accepted()"), self.sync)

        self.tags.update_tags_cache(self.db.all_tags())
        self.remove_tags.update_tags_cache(self.db.all_tags())

        self.initialize_combos()

        for f in self.db.all_formats():
            self.remove_format.addItem(f)

        self.remove_format.setCurrentIndex(-1)

        QObject.connect(self.series, SIGNAL('currentIndexChanged(int)'), self.series_changed)
        QObject.connect(self.series, SIGNAL('editTextChanged(QString)'), self.series_changed)
        QObject.connect(self.tag_editor_button, SIGNAL('clicked()'), self.tag_editor)
        if len(db.custom_column_label_map) == 0:
            self.central_widget.tabBar().setVisible(False)
        else:
            self.create_custom_column_editors()

        self.exec_()

    def create_custom_column_editors(self):
        w = self.central_widget.widget(1)
        layout = QGridLayout()

        self.custom_column_widgets, self.__cc_spacers = populate_bulk_metadata_page(
                layout, self.db, self.ids, w)
        w.setLayout(layout)
        self.__custom_col_layouts = [layout]
        ans = self.custom_column_widgets
        for i in range(len(ans)-1):
            w.setTabOrder(ans[i].widgets[1], ans[i+1].widgets[1])

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

    def tag_editor(self):
        d = TagEditor(self, self.db, None)
        d.exec_()
        if d.result() == QDialog.Accepted:
            tag_string = ', '.join(d.tags)
            self.tags.setText(tag_string)
            self.tags.update_tags_cache(self.db.all_tags())
            self.remove_tags.update_tags_cache(self.db.all_tags())

    def sync(self):
        for id in self.ids:
            au = unicode(self.authors.text())
            if au:
                au = string_to_authors(au)
                self.db.set_authors(id, au, notify=False)
            if self.auto_author_sort.isChecked():
                aut = self.db.authors(id, index_is_id=True)
                aut = aut if aut else ''
                aut = [a.strip().replace('|', ',') for a in aut.strip().split(',')]
                x = authors_to_sort_string(aut)
                if x:
                    self.db.set_author_sort(id, x, notify=False)
            aus = unicode(self.author_sort.text())
            if aus and self.author_sort.isEnabled():
                self.db.set_author_sort(id, aus, notify=False)
            if self.rating.value() != -1:
                self.db.set_rating(id, 2*self.rating.value(), notify=False)
            pub = unicode(self.publisher.text())
            if pub:
                self.db.set_publisher(id, pub, notify=False)
            remove_tags = unicode(self.remove_tags.text()).strip()
            if remove_tags:
                remove_tags = [i.strip() for i in remove_tags.split(',')]
                self.db.unapply_tags(id, remove_tags, notify=False)
            tags = unicode(self.tags.text()).strip()
            if tags:
                tags = map(lambda x: x.strip(), tags.split(','))
                self.db.set_tags(id, tags, append=True, notify=False)
            if self.write_series:
                series = unicode(self.series.currentText()).strip()
                next = self.db.get_next_series_num_for(series)
                self.db.set_series(id, series, notify=False)
                num = next if self.autonumber_series.isChecked() and series else 1.0
                self.db.set_series_index(id, num, notify=False)

            if self.remove_format.currentIndex() > -1:
                self.db.remove_format(id, unicode(self.remove_format.currentText()), index_is_id=True, notify=False)

            if self.swap_title_and_author.isChecked():
                title = self.db.title(id, index_is_id=True)
                aum = self.db.authors(id, index_is_id=True)
                if aum:
                    aum = [a.strip().replace('|', ',') for a in aum.split(',')]
                    new_title = authors_to_string(aum)
                    self.db.set_title(id, new_title, notify=False)
                if title:
                    new_authors = string_to_authors(title)
                    self.db.set_authors(id, new_authors, notify=False)

            if self.remove_conversion_settings.isChecked():
                self.db.delete_conversion_options(id, 'PIPE')

            self.changed = True
        for w in getattr(self, 'custom_column_widgets', []):
            w.commit(self.ids)


    def series_changed(self):
        self.write_series = True

