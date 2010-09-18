__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''Dialog to edit metadata in bulk'''

from threading import Thread
import re

from PyQt4.Qt import QDialog, QGridLayout
from PyQt4 import QtGui

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

    s_r_functions = {
                    ''          : lambda x: x,
                    _('Lower Case') : lambda x: x.lower(),
                    _('Upper Case')     : lambda x: x.upper(),
                    _('Title Case')     : lambda x: x.title(),
            }

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
            self.central_widget.removeTab(1)
        else:
            self.create_custom_column_editors()

        self.prepare_search_and_replace()
        self.exec_()

    def prepare_search_and_replace(self):
        self.search_for.initialize('bulk_edit_search_for')
        self.replace_with.initialize('bulk_edit_replace_with')
        self.test_text.initialize('bulk_edit_test_test')
        fields = ['']
        fm = self.db.field_metadata
        for f in fm:
            if (f in ['author_sort'] or (
                fm[f]['datatype'] == 'text' or fm[f]['datatype'] == 'series')
                    and fm[f].get('search_terms', None)
                    and f not in ['formats', 'ondevice']):
                fields.append(f)
        fields.sort()
        self.search_field.addItems(fields)
        self.search_field.setMaxVisibleItems(min(len(fields), 20))
        offset = 10
        self.s_r_number_of_books = min(7, len(self.ids))
        for i in range(1,self.s_r_number_of_books+1):
            w = QtGui.QLabel(self.tabWidgetPage3)
            w.setText(_('Book %d:')%i)
            self.gridLayout1.addWidget(w, i+offset, 0, 1, 1)
            w = QtGui.QLineEdit(self.tabWidgetPage3)
            w.setReadOnly(True)
            name = 'book_%d_text'%i
            setattr(self, name, w)
            self.book_1_text.setObjectName(name)
            self.gridLayout1.addWidget(w, i+offset, 1, 1, 1)
            w = QtGui.QLineEdit(self.tabWidgetPage3)
            w.setReadOnly(True)
            name = 'book_%d_result'%i
            setattr(self, name, w)
            self.book_1_text.setObjectName(name)
            self.gridLayout1.addWidget(w, i+offset, 2, 1, 1)

        self.s_r_heading.setText('<p>'+
                           _('Search and replace in text fields using '
                             'regular expressions. The search text is an '
                             'arbitrary python-compatible regular expression. '
                             'The replacement text can contain backreferences '
                             'to parenthesized expressions in the pattern. '
                             'The search is not anchored, and can match and '
                             'replace multiple times on the same string. See '
                             '<a href="http://docs.python.org/library/re.html"> '
                             'this reference</a> '
                             'for more information, and in particular the \'sub\' '
                             'function.') + '<p>' + _(
                             'Note: <b>you can destroy your library</b> '
                             'using this feature. Changes are permanent. There '
                             'is no undo function. You are strongly encouraged '
                             'to back up your library before proceeding.'))
        self.s_r_error = None
        self.s_r_obj = None

        self.replace_func.addItems(sorted(self.s_r_functions.keys()))
        self.search_field.currentIndexChanged[str].connect(self.s_r_field_changed)
        self.replace_func.currentIndexChanged[str].connect(self.s_r_paint_results)
        self.search_for.editTextChanged[str].connect(self.s_r_paint_results)
        self.replace_with.editTextChanged[str].connect(self.s_r_paint_results)
        self.test_text.editTextChanged[str].connect(self.s_r_paint_results)
        self.central_widget.setCurrentIndex(0)

    def s_r_field_changed(self, txt):
        txt = unicode(txt)
        for i in range(0, self.s_r_number_of_books):
            if txt:
                fm = self.db.field_metadata[txt]
                id = self.ids[i]
                val = self.db.get_property(id, index_is_id=True,
                                           loc=fm['rec_index'])
                if val is None:
                    val = ''
                if fm['is_multiple']:
                    val = [t.strip() for t in val.split(fm['is_multiple']) if t.strip()]
                    if val:
                        val.sort(cmp=lambda x,y: cmp(x.lower(), y.lower()))
                        val = val[0]
                        if txt == 'authors':
                            val = val.replace('|', ',')
                    else:
                        val = ''
            else:
                val = ''
            w = getattr(self, 'book_%d_text'%(i+1))
            w.setText(val)
        self.s_r_paint_results(None)

    def s_r_set_colors(self):
        if self.s_r_error is not None:
            col = 'rgb(255, 0, 0, 20%)'
            self.test_result.setText(self.s_r_error.message)
        else:
            col = 'rgb(0, 255, 0, 20%)'
        self.test_result.setStyleSheet('QLineEdit { color: black; '
                                       'background-color: %s; }'%col)
        for i in range(0,self.s_r_number_of_books):
            getattr(self, 'book_%d_result'%(i+1)).setText('')

    def s_r_func(self, match):
        rf = self.s_r_functions[unicode(self.replace_func.currentText())]
        rv = unicode(self.replace_with.text())
        val = match.expand(rv)
        return rf(val)

    def s_r_paint_results(self, txt):
        self.s_r_error = None
        self.s_r_set_colors()
        try:
            self.s_r_obj = re.compile(unicode(self.search_for.text()))
        except re.error as e:
            self.s_r_obj = None
            self.s_r_error = e
            self.s_r_set_colors()
            return

        try:
            self.test_result.setText(self.s_r_obj.sub(self.s_r_func,
                                     unicode(self.test_text.text())))
        except re.error as e:
            self.s_r_error = e
            self.s_r_set_colors()
            return

        for i in range(0,self.s_r_number_of_books):
            wt = getattr(self, 'book_%d_text'%(i+1))
            wr = getattr(self, 'book_%d_result'%(i+1))
            try:
                wr.setText(self.s_r_obj.sub(self.s_r_func, unicode(wt.text())))
            except re.error as e:
                self.s_r_error = e
                self.s_r_set_colors()
                break

    def do_search_replace(self):
        field = unicode(self.search_field.currentText())
        if not field or not self.s_r_obj:
            return

        fm = self.db.field_metadata[field]

        def apply_pattern(val):
            try:
                return self.s_r_obj.sub(self.s_r_func, val)
            except:
                return val

        for id in self.ids:
            val = self.db.get_property(id, index_is_id=True,
                                       loc=fm['rec_index'])
            if val is None:
                continue
            if fm['is_multiple']:
                res = []
                for val in [t.strip() for t in val.split(fm['is_multiple'])]:
                    v = apply_pattern(val).strip()
                    if v:
                        res.append(v)
                val = res
                if fm['is_custom']:
                    # The standard tags and authors values want to be lists.
                    # All custom columns are to be strings
                    val = fm['is_multiple'].join(val)
                elif field == 'authors':
                    val = [v.replace('|', ',') for v in val]
            else:
                val = apply_pattern(val)

            if fm['is_custom']:
                extra = self.db.get_custom_extra(id, label=fm['label'], index_is_id=True)
                self.db.set_custom(id, val, label=fm['label'], extra=extra,
                                   commit=False)
            else:
                if field == 'comments':
                    setter = self.db.set_comment
                else:
                    setter = getattr(self.db, 'set_'+field)
                setter(id, val, notify=False, commit=False)
        self.db.commit()

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

        if self.s_r_error is not None:
            error_dialog(self, _('Search/replace invalid'),
                    _('Search pattern is invalid: %s')%self.s_r_error.message,
                    show=True)
            return False
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

        self.do_search_replace()

        self.db.clean()
        return QDialog.accept(self)


    def series_changed(self, *args):
        self.write_series = True

