#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt4.Qt import (Qt, QIcon, QWidget, QHBoxLayout, QVBoxLayout, QShortcut,
        QKeySequence, QToolButton, QString, QLabel, QFrame, QTimer,
        QMenu, QPushButton, QActionGroup)

from calibre.gui2 import error_dialog, question_dialog
from calibre.gui2.widgets import HistoryLineEdit
from calibre.library.field_metadata import category_icon_map
from calibre.utils.icu import sort_key
from calibre.gui2.tag_browser.view import TagsView
from calibre.ebooks.metadata import title_sort
from calibre.gui2.dialogs.tag_categories import TagCategories
from calibre.gui2.dialogs.tag_list_editor import TagListEditor
from calibre.gui2.dialogs.edit_authors_dialog import EditAuthorsDialog

class TagBrowserMixin(object):  # {{{

    def __init__(self, db):
        self.library_view.model().count_changed_signal.connect(self.tags_view.recount)
        self.tags_view.set_database(db, self.alter_tb)
        self.tags_view.tags_marked.connect(self.search.set_search_string)
        self.tags_view.tags_list_edit.connect(self.do_tags_list_edit)
        self.tags_view.edit_user_category.connect(self.do_edit_user_categories)
        self.tags_view.delete_user_category.connect(self.do_delete_user_category)
        self.tags_view.del_item_from_user_cat.connect(self.do_del_item_from_user_cat)
        self.tags_view.add_subcategory.connect(self.do_add_subcategory)
        self.tags_view.add_item_to_user_cat.connect(self.do_add_item_to_user_cat)
        self.tags_view.saved_search_edit.connect(self.do_saved_search_edit)
        self.tags_view.rebuild_saved_searches.connect(self.do_rebuild_saved_searches)
        self.tags_view.author_sort_edit.connect(self.do_author_sort_edit)
        self.tags_view.tag_item_renamed.connect(self.do_tag_item_renamed)
        self.tags_view.search_item_renamed.connect(self.saved_searches_changed)
        self.tags_view.drag_drop_finished.connect(self.drag_drop_finished)
        self.tags_view.restriction_error.connect(self.do_restriction_error,
                                                 type=Qt.QueuedConnection)
        self.tags_view.tag_item_delete.connect(self.do_tag_item_delete)

        for text, func, args, cat_name in (
             (_('Manage Authors'),
                        self.do_author_sort_edit, (self, None), 'authors'),
             (_('Manage Series'),
                        self.do_tags_list_edit, (None, 'series'), 'series'),
             (_('Manage Publishers'),
                        self.do_tags_list_edit, (None, 'publisher'), 'publisher'),
             (_('Manage Tags'),
                        self.do_tags_list_edit, (None, 'tags'), 'tags'),
             (_('Manage User Categories'),
                        self.do_edit_user_categories, (None,), 'user:'),
             (_('Manage Saved Searches'),
                        self.do_saved_search_edit, (None,), 'search')
            ):
            m = self.alter_tb.manage_menu
            m.addAction(QIcon(I(category_icon_map[cat_name])), text,
                    partial(func, *args))

    def do_restriction_error(self):
        error_dialog(self.tags_view, _('Invalid search restriction'),
                         _('The current search restriction is invalid'), show=True)

    def do_add_subcategory(self, on_category_key, new_category_name=None):
        '''
        Add a subcategory to the category 'on_category'. If new_category_name is
        None, then a default name is shown and the user is offered the
        opportunity to edit the name.
        '''
        db = self.library_view.model().db
        user_cats = db.prefs.get('user_categories', {})

        # Ensure that the temporary name we will use is not already there
        i = 0
        if new_category_name is not None:
            new_name = new_category_name.replace('.', '')
        else:
            new_name = _('New Category').replace('.', '')
        n = new_name
        while True:
            new_cat = on_category_key[1:] + '.' + n
            if new_cat not in user_cats:
                break
            i += 1
            n = new_name + unicode(i)
        # Add the new category
        user_cats[new_cat] = []
        db.prefs.set('user_categories', user_cats)
        self.tags_view.recount()
        m = self.tags_view.model()
        idx = m.index_for_path(m.find_category_node('@' + new_cat))
        self.tags_view.show_item_at_index(idx)
        # Open the editor on the new item to rename it
        if new_category_name is None:
            self.tags_view.edit(idx)

    def do_edit_user_categories(self, on_category=None):
        '''
        Open the user categories editor.
        '''
        db = self.library_view.model().db
        d = TagCategories(self, db, on_category)
        if d.exec_() == d.Accepted:
            db.prefs.set('user_categories', d.categories)
            db.field_metadata.remove_user_categories()
            for k in d.categories:
                db.field_metadata.add_user_category('@' + k, k)
            db.data.change_search_locations(db.field_metadata.get_search_terms())
            self.tags_view.recount()

    def do_delete_user_category(self, category_name):
        '''
        Delete the user category named category_name. Any leading '@' is removed
        '''
        if category_name.startswith('@'):
            category_name = category_name[1:]
        db = self.library_view.model().db
        user_cats = db.prefs.get('user_categories', {})
        cat_keys = sorted(user_cats.keys(), key=sort_key)
        has_children = False
        found = False
        for k in cat_keys:
            if k == category_name:
                found = True
                has_children = len(user_cats[k])
            elif k.startswith(category_name + '.'):
                has_children = True
        if not found:
            return error_dialog(self.tags_view, _('Delete user category'),
                         _('%s is not a user category')%category_name, show=True)
        if has_children:
            if not question_dialog(self.tags_view, _('Delete user category'),
                                   _('%s contains items. Do you really '
                                     'want to delete it?')%category_name):
                return
        for k in cat_keys:
            if k == category_name:
                del user_cats[k]
            elif k.startswith(category_name + '.'):
                del user_cats[k]
        db.prefs.set('user_categories', user_cats)
        self.tags_view.recount()

    def do_del_item_from_user_cat(self, user_cat, item_name, item_category):
        '''
        Delete the item (item_name, item_category) from the user category with
        key user_cat. Any leading '@' characters are removed
        '''
        if user_cat.startswith('@'):
            user_cat = user_cat[1:]
        db = self.library_view.model().db
        user_cats = db.prefs.get('user_categories', {})
        if user_cat not in user_cats:
            error_dialog(self.tags_view, _('Remove category'),
                         _('User category %s does not exist')%user_cat,
                         show=True)
            return
        self.tags_view.model().delete_item_from_user_category(user_cat,
                                                      item_name, item_category)
        self.tags_view.recount()

    def do_add_item_to_user_cat(self, dest_category, src_name, src_category):
        '''
        Add the item src_name in src_category to the user category
        dest_category. Any leading '@' is removed
        '''
        db = self.library_view.model().db
        user_cats = db.prefs.get('user_categories', {})

        if dest_category and dest_category.startswith('@'):
            dest_category = dest_category[1:]

        if dest_category not in user_cats:
            return error_dialog(self.tags_view, _('Add to user category'),
                    _('A user category %s does not exist')%dest_category, show=True)

        # Now add the item to the destination user category
        add_it = True
        if src_category == 'news':
            src_category = 'tags'
        for tup in user_cats[dest_category]:
            if src_name == tup[0] and src_category == tup[1]:
                add_it = False
        if add_it:
            user_cats[dest_category].append([src_name, src_category, 0])
        db.prefs.set('user_categories', user_cats)
        self.tags_view.recount()

    def do_tags_list_edit(self, tag, category):
        '''
        Open the 'manage_X' dialog where X == category. If tag is not None, the
        dialog will position the editor on that item.
        '''

        tags_model = self.tags_view.model()
        result = tags_model.get_category_editor_data(category)
        if result is None:
            return

        if category == 'series':
            key = lambda x:sort_key(title_sort(x))
        else:
            key = sort_key

        db=self.library_view.model().db
        d = TagListEditor(self, cat_name=db.field_metadata[category]['name'],
                          tag_to_match=tag, data=result, sorter=key)
        d.exec_()
        if d.result() == d.Accepted:
            to_rename = d.to_rename  # dict of old id to new name
            to_delete = d.to_delete  # list of ids
            orig_name = d.original_names  # dict of id: name

            rename_func = None
            if category == 'tags':
                rename_func = db.rename_tag
                delete_func = db.delete_tag_using_id
            elif category == 'series':
                rename_func = db.rename_series
                delete_func = db.delete_series_using_id
            elif category == 'publisher':
                rename_func = db.rename_publisher
                delete_func = db.delete_publisher_using_id
            else:  # must be custom
                cc_label = db.field_metadata[category]['label']
                rename_func = partial(db.rename_custom_item, label=cc_label)
                delete_func = partial(db.delete_custom_item_using_id, label=cc_label)
            m = self.tags_view.model()
            if rename_func:
                for item in to_delete:
                    delete_func(item)
                    m.delete_item_from_all_user_categories(orig_name[item], category)
                for old_id in to_rename:
                    rename_func(old_id, new_name=unicode(to_rename[old_id]))
                    m.rename_item_in_all_user_categories(orig_name[old_id],
                                            category, unicode(to_rename[old_id]))

            # Clean up the library view
            self.do_tag_item_renamed()
            self.tags_view.recount()

    def do_tag_item_delete(self, category, item_id, orig_name):
        '''
        Delete an item from some category.
        '''
        if not question_dialog(self.tags_view,
                    title=_('Delete item'),
                    msg='<p>'+
                    _('%s will be deleted from all books. Are you sure?')
                                %orig_name,
                    skip_dialog_name='tag_item_delete',
                    skip_dialog_msg=_('Show this confirmation again')):
            return
        db = self.current_db

        if category == 'tags':
            delete_func = db.delete_tag_using_id
        elif category == 'series':
            delete_func = db.delete_series_using_id
        elif category == 'publisher':
            delete_func = db.delete_publisher_using_id
        else:  # must be custom
            cc_label = db.field_metadata[category]['label']
            delete_func = partial(db.delete_custom_item_using_id, label=cc_label)
        m = self.tags_view.model()
        if delete_func:
            delete_func(item_id)
            m.delete_item_from_all_user_categories(orig_name, category)

        # Clean up the library view
        self.do_tag_item_renamed()
        self.tags_view.recount()

    def do_tag_item_renamed(self):
        # Clean up library view and search
        # get information to redo the selection
        rows = [r.row() for r in
                self.library_view.selectionModel().selectedRows()]
        m = self.library_view.model()
        ids = [m.id(r) for r in rows]

        m.refresh(reset=False)
        m.research()
        self.library_view.select_rows(ids)
        # refreshing the tags view happens at the emit()/call() site

    def do_author_sort_edit(self, parent, id_, select_sort=True, select_link=False):
        '''
        Open the manage authors dialog
        '''

        db = self.library_view.model().db
        editor = EditAuthorsDialog(parent, db, id_, select_sort, select_link)
        d = editor.exec_()
        if d:
            # Save and restore the current selections. Note that some changes
            # will cause sort orders to change, so don't bother with attempting
            # to restore the position. Restoring the state has the side effect
            # of refreshing book details.
            with self.library_view.preserve_state(preserve_hpos=False, preserve_vpos=False):
                for (id2, old_author, new_author, new_sort, new_link) in editor.result:
                    if old_author != new_author:
                        # The id might change if the new author already exists
                        id2 = db.rename_author(id2, new_author)
                    db.set_sort_field_for_author(id2, unicode(new_sort),
                                                 commit=False, notify=False)
                    db.set_link_field_for_author(id2, unicode(new_link),
                                                 commit=False, notify=False)
                db.commit()
                self.library_view.model().refresh()
                self.tags_view.recount()

    def drag_drop_finished(self, ids):
        self.library_view.model().refresh_ids(ids)

# }}}

class TagBrowserWidget(QWidget):  # {{{

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.parent = parent
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._layout.setContentsMargins(0,0,0,0)

        # Set up the find box & button
        search_layout = QHBoxLayout()
        self._layout.addLayout(search_layout)
        self.item_search = HistoryLineEdit(parent)
        self.item_search.setMinimumContentsLength(10)
        self.item_search.setSizeAdjustPolicy(self.item_search.AdjustToMinimumContentsLengthWithIcon)
        try:
            self.item_search.lineEdit().setPlaceholderText(
                                                _('Find item in tag browser'))
        except:
            pass             # Using Qt < 4.7
        self.item_search.setToolTip(_(
        'Search for items. This is a "contains" search; items containing the\n'
        'text anywhere in the name will be found. You can limit the search\n'
        'to particular categories using syntax similar to search. For example,\n'
        'tags:foo will find foo in any tag, but not in authors etc. Entering\n'
        '*foo will filter all categories at once, showing only those items\n'
        'containing the text "foo"'))
        search_layout.addWidget(self.item_search)
        # Not sure if the shortcut should be translatable ...
        sc = QShortcut(QKeySequence(_('ALT+f')), parent)
        sc.activated.connect(self.set_focus_to_find_box)

        self.search_button = QToolButton()
        self.search_button.setText(_('F&ind'))
        self.search_button.setToolTip(_('Find the first/next matching item'))
        search_layout.addWidget(self.search_button)

        self.expand_button = QToolButton()
        self.expand_button.setText('-')
        self.expand_button.setToolTip(_('Collapse all categories'))
        search_layout.addWidget(self.expand_button)
        search_layout.setStretch(0, 10)
        search_layout.setStretch(1, 1)
        search_layout.setStretch(2, 1)

        self.current_find_position = None
        self.search_button.clicked.connect(self.find)
        self.item_search.initialize('tag_browser_search')
        self.item_search.lineEdit().returnPressed.connect(self.do_find)
        self.item_search.lineEdit().textEdited.connect(self.find_text_changed)
        self.item_search.activated[QString].connect(self.do_find)
        self.item_search.completer().setCaseSensitivity(Qt.CaseSensitive)

        parent.tags_view = TagsView(parent)
        self.tags_view = parent.tags_view
        self.expand_button.clicked.connect(self.tags_view.collapseAll)
        self._layout.addWidget(parent.tags_view)

        # Now the floating 'not found' box
        l = QLabel(self.tags_view)
        self.not_found_label = l
        l.setFrameStyle(QFrame.StyledPanel)
        l.setAutoFillBackground(True)
        l.setText('<p><b>'+_('No More Matches.</b><p> Click Find again to go to first match'))
        l.setAlignment(Qt.AlignVCenter)
        l.setWordWrap(True)
        l.resize(l.sizeHint())
        l.move(10,20)
        l.setVisible(False)
        self.not_found_label_timer = QTimer()
        self.not_found_label_timer.setSingleShot(True)
        self.not_found_label_timer.timeout.connect(self.not_found_label_timer_event,
                                                   type=Qt.QueuedConnection)

        parent.alter_tb = l = QPushButton(parent)
        l.setText(_('Alter Tag Browser'))
        l.setIcon(QIcon(I('tags.png')))
        l.m = QMenu()
        l.setMenu(l.m)
        self._layout.addWidget(l)

        sb = l.m.addAction(_('Sort by'))
        sb.m = l.sort_menu = QMenu(l.m)
        sb.setMenu(sb.m)
        sb.bg = QActionGroup(sb)

        # Must be in the same order as db2.CATEGORY_SORTS
        for i, x in enumerate((_('Sort by name'), _('Sort by popularity'),
                  _('Sort by average rating'))):
            a = sb.m.addAction(x)
            sb.bg.addAction(a)
            a.setCheckable(True)
            if i == 0:
                a.setChecked(True)
        sb.setToolTip(
                _('Set the sort order for entries in the Tag Browser'))
        sb.setStatusTip(sb.toolTip())

        ma = l.m.addAction(_('Search type when selecting multiple items'))
        ma.m = l.match_menu = QMenu(l.m)
        ma.setMenu(ma.m)
        ma.ag = QActionGroup(ma)

        # Must be in the same order as db2.MATCH_TYPE
        for i, x in enumerate((_('Match any of the items'), _('Match all of the items'))):
            a = ma.m.addAction(x)
            ma.ag.addAction(a)
            a.setCheckable(True)
            if i == 0:
                a.setChecked(True)
        ma.setToolTip(
                _('When selecting multiple entries in the Tag Browser '
                    'match any or all of them'))
        ma.setStatusTip(ma.toolTip())

        mt = l.m.addAction(_('Manage authors, tags, etc'))
        mt.setToolTip(_('All of these category_managers are available by right-clicking '
                       'on items in the tag browser above'))
        mt.m = l.manage_menu = QMenu(l.m)
        mt.setMenu(mt.m)

        # self.leak_test_timer = QTimer(self)
        # self.leak_test_timer.timeout.connect(self.test_for_leak)
        # self.leak_test_timer.start(5000)

    def set_pane_is_visible(self, to_what):
        self.tags_view.set_pane_is_visible(to_what)

    def find_text_changed(self, str):
        self.current_find_position = None

    def set_focus_to_find_box(self):
        self.item_search.setFocus()
        self.item_search.lineEdit().selectAll()

    def do_find(self, str=None):
        self.current_find_position = None
        self.find()

    def find(self):
        model = self.tags_view.model()
        model.clear_boxed()
        txt = unicode(self.item_search.currentText()).strip()

        if txt.startswith('*'):
            model.set_categories_filter(txt[1:])
            self.tags_view.recount()
            self.current_find_position = None
            return
        if model.get_categories_filter():
            model.set_categories_filter(None)
            self.tags_view.recount()
            self.current_find_position = None

        if not txt:
            return

        self.item_search.lineEdit().blockSignals(True)
        self.search_button.setFocus(True)
        self.item_search.lineEdit().blockSignals(False)

        key = None
        colon = txt.rfind(':') if len(txt) > 2 else 0
        if colon > 0:
            key = self.parent.library_view.model().db.\
                        field_metadata.search_term_to_field_key(txt[:colon])
            txt = txt[colon+1:]

        self.current_find_position = \
            model.find_item_node(key, txt, self.current_find_position)

        if self.current_find_position:
            self.tags_view.show_item_at_path(self.current_find_position, box=True)
        elif self.item_search.text():
            self.not_found_label.setVisible(True)
            if self.tags_view.verticalScrollBar().isVisible():
                sbw = self.tags_view.verticalScrollBar().width()
            else:
                sbw = 0
            width = self.width() - 8 - sbw
            height = self.not_found_label.heightForWidth(width) + 20
            self.not_found_label.resize(width, height)
            self.not_found_label.move(4, 10)
            self.not_found_label_timer.start(2000)

    def not_found_label_timer_event(self):
        self.not_found_label.setVisible(False)

# }}}

