#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import QApplication

from calibre.gui2.preferences import ConfigWidgetBase, test_widget, \
        CommaSeparatedList, AbortCommit
from calibre.gui2.preferences.search_ui import Ui_Form
from calibre.gui2 import config, error_dialog, gprefs
from calibre.utils.config import prefs
from calibre.utils.icu import sort_key
from calibre.library.caches import set_use_primary_find_in_search
from polyglot.builtins import iteritems, unicode_type


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        db = gui.library_view.model().db
        self.db = db

        r = self.register

        r('search_as_you_type', config)
        r('highlight_search_matches', config)
        r('show_highlight_toggle_button', gprefs)
        r('limit_search_columns', prefs)
        r('use_primary_find_in_search', prefs)
        r('case_sensitive', prefs)
        r('limit_search_columns_to', prefs, setting=CommaSeparatedList)
        fl = db.field_metadata.get_search_terms()
        self.opt_limit_search_columns_to.update_items_cache(fl)
        self.clear_history_button.clicked.connect(self.clear_histories)

        self.gst_explanation.setText('<p>' + _(
    "<b>Grouped search terms</b> are search names that permit a query to automatically "
    "search across more than one column. For example, if you create a grouped "
    "search term <code>allseries</code> with the value "
    "<code>series, #myseries, #myseries2</code>, then "
    "the query <code>allseries:adhoc</code> will find 'adhoc' in any of the "
    "columns <code>series</code>, <code>#myseries</code>, and "
    "<code>#myseries2</code>.<p> Enter the name of the "
    "grouped search term in the drop-down box, enter the list of columns "
    "to search in the value box, then push the Save button. "
    "<p>Note: Search terms are forced to lower case; <code>MySearch</code> "
    "and <code>mysearch</code> are the same term."
    "<p>You can have your grouped search term show up as User categories in "
    " the Tag browser. Just add the grouped search term names to the Make User "
    "categories from box. You can add multiple terms separated by commas. "
    "The new User category will be automatically "
    "populated with all the items in the categories included in the grouped "
    "search term. <p>Automatic User categories permit you to see easily "
    "all the category items that "
    "are in the columns contained in the grouped search term. Using the above "
    "<code>allseries</code> example, the automatically-generated User category "
    "will contain all the series mentioned in <code>series</code>, "
    "<code>#myseries</code>, and <code>#myseries2</code>. This "
    "can be useful to check for duplicates, to find which column contains "
    "a particular item, or to have hierarchical categories (categories "
    "that contain categories)."))
        self.gst = db.prefs.get('grouped_search_terms', {}).copy()
        self.orig_gst_keys = list(self.gst.keys())

        fl = []
        for f in db.all_field_keys():
            fm = db.metadata_for_field(f)
            if not fm['search_terms']:
                continue
            if not fm['is_category']:
                continue
            fl.append(f)
        self.gst_value.update_items_cache(fl)
        self.fill_gst_box(select=None)

        self.user_category_layout.setContentsMargins(0, 30, 0, 0)
        self.gst_names.lineEdit().setPlaceholderText(
                         _('Enter new or select existing name'))
        self.gst_value.lineEdit().setPlaceholderText(
                         _('Enter list of column lookup names to search'))

        self.category_fields = fl
        ml = [(_('Match any'), 'match_any'), (_('Match all'), 'match_all')]
        r('similar_authors_match_kind', db.prefs, choices=ml)
        r('similar_tags_match_kind', db.prefs, choices=ml)
        r('similar_series_match_kind', db.prefs, choices=ml)
        r('similar_publisher_match_kind', db.prefs, choices=ml)
        self.set_similar_fields(initial=True)
        self.similar_authors_search_key.currentIndexChanged[int].connect(self.something_changed)
        self.similar_tags_search_key.currentIndexChanged[int].connect(self.something_changed)
        self.similar_series_search_key.currentIndexChanged[int].connect(self.something_changed)
        self.similar_publisher_search_key.currentIndexChanged[int].connect(self.something_changed)

        self.gst_delete_button.setEnabled(False)
        self.gst_save_button.setEnabled(False)
        self.gst_names.currentIndexChanged[int].connect(self.gst_index_changed)
        self.gst_names.editTextChanged.connect(self.gst_text_changed)
        self.gst_value.textChanged.connect(self.gst_text_changed)
        self.gst_save_button.clicked.connect(self.gst_save_clicked)
        self.gst_delete_button.clicked.connect(self.gst_delete_clicked)
        self.gst_changed = False

        if db.prefs.get('grouped_search_make_user_categories', None) is None:
            db.new_api.set_pref('grouped_search_make_user_categories', [])
        r('grouped_search_make_user_categories', db.prefs, setting=CommaSeparatedList)
        self.muc_changed = False
        self.opt_grouped_search_make_user_categories.lineEdit().editingFinished.connect(
                                                        self.muc_box_changed)

    def set_similar_fields(self, initial=False):
        self.set_similar('similar_authors_search_key', initial=initial)
        self.set_similar('similar_tags_search_key', initial=initial)
        self.set_similar('similar_series_search_key', initial=initial)
        self.set_similar('similar_publisher_search_key', initial=initial)

    def set_similar(self, name, initial=False):
        field = getattr(self, name)
        if not initial:
            val = field.currentText()
        else:
            val = self.db.prefs[name]
        field.blockSignals(True)
        field.clear()
        choices = []
        choices.extend(self.category_fields)
        choices.extend(sorted(self.gst.keys(), key=sort_key))
        field.addItems(choices)
        dex = field.findText(val)
        if dex >= 0:
            field.setCurrentIndex(dex)
        else:
            field.setCurrentIndex(0)
        field.blockSignals(False)

    def something_changed(self, dex):
        self.changed_signal.emit()

    def muc_box_changed(self):
        self.muc_changed = True

    def gst_save_clicked(self):
        idx = self.gst_names.currentIndex()
        name = icu_lower(unicode_type(self.gst_names.currentText()))
        if not name:
            return error_dialog(self.gui, _('Grouped search terms'),
                                _('The search term cannot be blank'),
                                show=True)
        if idx != 0:
            orig_name = unicode_type(self.gst_names.itemData(idx) or '')
        else:
            orig_name = ''
        if name != orig_name:
            if name in self.db.field_metadata.get_search_terms() and \
                    name not in self.orig_gst_keys:
                return error_dialog(self.gui, _('Grouped search terms'),
                    _('That name is already used for a column or grouped search term'),
                    show=True)
            if name in [icu_lower(p) for p in self.db.prefs.get('user_categories', {})]:
                return error_dialog(self.gui, _('Grouped search terms'),
                    _('That name is already used for User category'),
                    show=True)

        val = [v.strip() for v in unicode_type(self.gst_value.text()).split(',') if v.strip()]
        if not val:
            return error_dialog(self.gui, _('Grouped search terms'),
                _('The value box cannot be empty'), show=True)

        if orig_name and name != orig_name:
            del self.gst[orig_name]
        self.gst_changed = True
        self.gst[name] = val
        self.fill_gst_box(select=name)
        self.set_similar_fields(initial=False)
        self.changed_signal.emit()

    def gst_delete_clicked(self):
        if self.gst_names.currentIndex() == 0:
            return error_dialog(self.gui, _('Grouped search terms'),
                _('The empty grouped search term cannot be deleted'), show=True)
        name = unicode_type(self.gst_names.currentText())
        if name in self.gst:
            del self.gst[name]
            self.fill_gst_box(select='')
            self.changed_signal.emit()
            self.gst_changed = True
            self.set_similar_fields(initial=False)

    def fill_gst_box(self, select=None):
        terms = sorted(self.gst.keys(), key=sort_key)
        self.opt_grouped_search_make_user_categories.update_items_cache(terms)
        self.gst_names.blockSignals(True)
        self.gst_names.clear()
        self.gst_names.addItem('', '')
        for t in terms:
            self.gst_names.addItem(t, t)
        self.gst_names.blockSignals(False)
        if select is not None:
            if select == '':
                self.gst_index_changed(0)
            elif select in terms:
                self.gst_names.setCurrentIndex(self.gst_names.findText(select))

    def gst_text_changed(self):
        t = self.gst_names.currentText()
        self.gst_delete_button.setEnabled(len(t) > 0 and t in self.gst)
        self.gst_save_button.setEnabled(True)

    def gst_index_changed(self, idx):
        self.gst_delete_button.setEnabled(idx != 0)
        self.gst_save_button.setEnabled(False)
        self.gst_value.blockSignals(True)
        if idx == 0:
            self.gst_value.setText('')
        else:
            name = unicode_type(self.gst_names.itemData(idx) or '')
            self.gst_value.setText(','.join(self.gst[name]))
        self.gst_value.blockSignals(False)

    def commit(self):
        if self.opt_case_sensitive.isChecked() and self.opt_use_primary_find_in_search.isChecked():
            error_dialog(self, _('Incompatible options'), _(
                'The option to have un-accented characters match accented characters has no effect'
                ' if you also turn on case-sensitive searching. So only turn on one of those options'), show=True)
            raise AbortCommit()
        if self.gst_changed:
            self.db.new_api.set_pref('grouped_search_terms', self.gst)
            self.db.field_metadata.add_grouped_search_terms(self.gst)
        self.db.new_api.set_pref('similar_authors_search_key',
                          unicode_type(self.similar_authors_search_key.currentText()))
        self.db.new_api.set_pref('similar_tags_search_key',
                          unicode_type(self.similar_tags_search_key.currentText()))
        self.db.new_api.set_pref('similar_series_search_key',
                          unicode_type(self.similar_series_search_key.currentText()))
        self.db.new_api.set_pref('similar_publisher_search_key',
                          unicode_type(self.similar_publisher_search_key.currentText()))
        return ConfigWidgetBase.commit(self)

    def refresh_gui(self, gui):
        gui.current_db.new_api.clear_caches()
        set_use_primary_find_in_search(prefs['use_primary_find_in_search'])
        gui.set_highlight_only_button_icon()
        if self.muc_changed:
            gui.tags_view.recount()
        gui.search.search_as_you_type(config['search_as_you_type'])
        gui.search.do_search()

    def clear_histories(self, *args):
        for key, val in iteritems(config.defaults):
            if key.endswith('_search_history') and isinstance(val, list):
                config[key] = []
        self.gui.search.clear_history()
        from calibre.gui2.widgets import history
        for key in 'bulk_edit_search_for bulk_edit_replace_with'.split():
            history.set('lineedit_history_' + key, [])


if __name__ == '__main__':
    app = QApplication([])
    test_widget('Interface', 'Search')
