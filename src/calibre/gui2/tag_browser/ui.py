#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import copy, textwrap
from functools import partial

from qt.core import (
    Qt, QIcon, QWidget, QHBoxLayout, QVBoxLayout, QToolButton, QLabel, QFrame, QDialog, QComboBox, QLineEdit,
    QTimer, QMenu, QActionGroup, QAction, QSizePolicy, pyqtSignal)

from calibre.gui2 import error_dialog, question_dialog, gprefs, config
from calibre.gui2.widgets import HistoryLineEdit
from calibre.library.field_metadata import category_icon_map
from calibre.utils.icu import sort_key
from calibre.gui2.tag_browser.view import TagsView
from calibre.ebooks.metadata import title_sort
from calibre.gui2.dialogs.tag_categories import TagCategories
from calibre.gui2.dialogs.tag_list_editor import TagListEditor
from calibre.gui2.dialogs.edit_authors_dialog import EditAuthorsDialog
from polyglot.builtins import iteritems


class TagBrowserMixin:  # {{{

    def __init__(self, *args, **kwargs):
        pass

    def populate_tb_manage_menu(self, db):
        self.populate_manage_categories_menu(db, self.alter_tb.manage_menu)

    def populate_manage_categories_menu(self, db, menu):
        from calibre.db.categories import find_categories
        m = menu
        m.clear()
        for text, func, args, cat_name in (
             (_('Authors'),
                        self.do_author_sort_edit, (self, None), 'authors'),
             (ngettext('Series', 'Series', 2),
                        self.do_tags_list_edit, (None, 'series'), 'series'),
             (_('Publishers'),
                        self.do_tags_list_edit, (None, 'publisher'), 'publisher'),
             (_('Tags'),
                        self.do_tags_list_edit, (None, 'tags'), 'tags'),
             (_('User categories'),
                        self.do_edit_user_categories, (None,), 'user:'),
             (_('Saved searches'),
                        self.do_saved_search_edit, (None,), 'search')
            ):
            m.addAction(QIcon.ic(category_icon_map[cat_name]), text,
                    partial(func, *args))
        fm = db.new_api.field_metadata
        categories = [x[0] for x in find_categories(fm) if fm.is_custom_field(x[0])]
        if categories:
            if len(categories) > 5:
                m = m.addMenu(_('Custom columns'))
            else:
                m.addSeparator()

            def cat_key(x):
                try:
                    return fm[x]['name']
                except Exception:
                    return ''
            for cat in sorted(categories, key=cat_key):
                name = cat_key(cat)
                if name:
                    m.addAction(name, partial(self.do_tags_list_edit, None, cat))

    def init_tag_browser_mixin(self, db):
        self.library_view.model().count_changed_signal.connect(self.tags_view.recount_with_position_based_index)
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
                                                 type=Qt.ConnectionType.QueuedConnection)
        self.tags_view.tag_item_delete.connect(self.do_tag_item_delete)
        self.tags_view.tag_identifier_delete.connect(self.delete_identifier)
        self.tags_view.apply_tag_to_selected.connect(self.apply_tag_to_selected)
        self.populate_tb_manage_menu(db)
        self.tags_view.model().user_categories_edited.connect(self.user_categories_edited,
                type=Qt.ConnectionType.QueuedConnection)
        self.tags_view.model().user_category_added.connect(self.user_categories_edited,
                type=Qt.ConnectionType.QueuedConnection)
        self.tags_view.edit_enum_values.connect(self.edit_enum_values)
        self.tags_view.model().research_required.connect(self.do_gui_research, type=Qt.ConnectionType.QueuedConnection)

    def do_gui_research(self):
        self.library_view.model().research()
        # The count can change if the current search uses in_tag_browser, perhaps in a VL
        self.library_view.model().count_changed()

    def user_categories_edited(self):
        self.library_view.model().refresh()

    def do_restriction_error(self, e):
        error_dialog(self.tags_view, _('Invalid search restriction'),
                         _('The current search restriction is invalid'),
                         det_msg=str(e) if e else '', show=True)

    def do_add_subcategory(self, on_category_key, new_category_name=None):
        '''
        Add a subcategory to the category 'on_category'. If new_category_name is
        None, then a default name is shown and the user is offered the
        opportunity to edit the name.
        '''
        db = self.library_view.model().db
        user_cats = db.new_api.pref('user_categories', {})

        # Ensure that the temporary name we will use is not already there
        i = 0
        if new_category_name is not None:
            new_name = new_category_name.replace('.', '')
        else:
            new_name = _('New category').replace('.', '')
        n = new_name
        while True:
            new_cat = on_category_key[1:] + '.' + n
            if new_cat not in user_cats:
                break
            i += 1
            n = new_name + str(i)
        # Add the new category
        user_cats[new_cat] = []
        db.new_api.set_pref('user_categories', user_cats)
        self.tags_view.recount()
        db.new_api.clear_search_caches()
        m = self.tags_view.model()
        idx = m.index_for_path(m.find_category_node('@' + new_cat))
        self.tags_view.show_item_at_index(idx)
        # Open the editor on the new item to rename it
        if new_category_name is None:
            item = m.get_node(idx)
            item.use_vl = False
            item.ignore_vl = True
            self.tags_view.edit(idx)

    def do_edit_user_categories(self, on_category=None):
        '''
        Open the User categories editor.
        '''
        db = self.library_view.model().db
        d = TagCategories(self, db, on_category,
                          book_ids=self.tags_view.model().get_book_ids_to_use())
        if d.exec() == QDialog.DialogCode.Accepted:
            # Order is important. The categories must be removed before setting
            # the preference because setting the pref recomputes the dynamic categories
            db.field_metadata.remove_user_categories()
            db.new_api.set_pref('user_categories', d.categories)
            db.new_api.refresh_search_locations()
            self.tags_view.recount()
            db.new_api.clear_search_caches()
            self.user_categories_edited()

    def do_delete_user_category(self, category_name):
        '''
        Delete the User category named category_name. Any leading '@' is removed
        '''
        if category_name.startswith('@'):
            category_name = category_name[1:]
        db = self.library_view.model().db
        user_cats = db.new_api.pref('user_categories', {})
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
            return error_dialog(self.tags_view, _('Delete User category'),
                         _('%s is not a User category')%category_name, show=True)
        if has_children:
            if not question_dialog(self.tags_view, _('Delete User category'),
                                   _('%s contains items. Do you really '
                                     'want to delete it?')%category_name):
                return
        for k in cat_keys:
            if k == category_name:
                del user_cats[k]
            elif k.startswith(category_name + '.'):
                del user_cats[k]
        db.new_api.set_pref('user_categories', user_cats)
        self.tags_view.recount()
        db.new_api.clear_search_caches()
        self.user_categories_edited()

    def do_del_item_from_user_cat(self, user_cat, item_name, item_category):
        '''
        Delete the item (item_name, item_category) from the User category with
        key user_cat. Any leading '@' characters are removed
        '''
        if user_cat.startswith('@'):
            user_cat = user_cat[1:]
        db = self.library_view.model().db
        user_cats = db.new_api.pref('user_categories', {})
        if user_cat not in user_cats:
            error_dialog(self.tags_view, _('Remove category'),
                         _('User category %s does not exist')%user_cat,
                         show=True)
            return
        self.tags_view.model().delete_item_from_user_category(user_cat,
                                                      item_name, item_category)
        self.tags_view.recount()
        db.new_api.clear_search_caches()
        self.user_categories_edited()

    def do_add_item_to_user_cat(self, dest_category, src_name, src_category):
        '''
        Add the item src_name in src_category to the User category
        dest_category. Any leading '@' is removed
        '''
        db = self.library_view.model().db
        user_cats = db.new_api.pref('user_categories', {})

        if dest_category and dest_category.startswith('@'):
            dest_category = dest_category[1:]

        if dest_category not in user_cats:
            return error_dialog(self.tags_view, _('Add to User category'),
                    _('A User category %s does not exist')%dest_category, show=True)

        # Now add the item to the destination User category
        add_it = True
        if src_category == 'news':
            src_category = 'tags'
        for tup in user_cats[dest_category]:
            if src_name == tup[0] and src_category == tup[1]:
                add_it = False
        if add_it:
            user_cats[dest_category].append([src_name, src_category, 0])
        db.new_api.set_pref('user_categories', user_cats)
        self.tags_view.recount()
        db.new_api.clear_search_caches()
        self.user_categories_edited()

    def get_book_ids(self, use_virtual_library, db, category):
        book_ids = None if not use_virtual_library else self.tags_view.model().get_book_ids_to_use()
        data = db.new_api.get_categories(book_ids=book_ids)
        if category in data:
            result = [(t.id, t.original_name, t.count) for t in data[category] if t.count > 0]
        else:
            result = None
        return result

    def do_tags_list_edit(self, tag, category, is_first_letter=False):
        '''
        Open the 'manage_X' dialog where X == category. If tag is not None, the
        dialog will position the editor on that item.
        '''

        db = self.current_db
        if category == 'series':
            key = lambda x:sort_key(title_sort(x))
        else:
            key = sort_key

        d = TagListEditor(self, category=category,
                          cat_name=db.field_metadata[category]['name'],
                          tag_to_match=tag,
                          get_book_ids=partial(self.get_book_ids, db=db, category=category),
                          sorter=key, ttm_is_first_letter=is_first_letter,
                          fm=db.field_metadata[category])
        d.exec()
        if d.result() == QDialog.DialogCode.Accepted:
            to_rename = d.to_rename  # dict of old id to new name
            to_delete = d.to_delete  # list of ids
            orig_name = d.original_names  # dict of id: name

            if (category in ['tags', 'series', 'publisher'] or
                    db.new_api.field_metadata.is_custom_field(category)):
                m = self.tags_view.model()
                for item in to_delete:
                    m.delete_item_from_all_user_categories(orig_name[item], category)
                for old_id in to_rename:
                    m.rename_item_in_all_user_categories(orig_name[old_id],
                                            category, str(to_rename[old_id]))

                db.new_api.remove_items(category, to_delete)
                db.new_api.rename_items(category, to_rename, change_index=False)

                # Clean up the library view
                self.do_tag_item_renamed()
                self.tags_view.recount()

    def do_tag_item_delete(self, category, item_id, orig_name,
                           restrict_to_book_ids=None, children=[]):
        '''
        Delete an item from some category.
        '''
        tag_names = []
        for child in children:
            if child.tag.is_editable:
                tag_names.append(child.tag.original_name)
        n = '\n   '.join(tag_names)
        if n:
            n = '%s:\n   %s\n%s:\n   %s'%(_('Item'), orig_name, _('Children'), n)
        if n:
            # Use a new "see this again" name to force the dialog to appear at
            # least once, thus announcing the new feature.
            skip_dialog_name = 'tag_item_delete_hierarchical'
            if restrict_to_book_ids:
                msg = _('%s and its children will be deleted from books '
                        'in the Virtual library. Are you sure?')%orig_name
            else:
                msg = _('%s and its children will be deleted from all books. '
                        'Are you sure?')%orig_name
        else:
            skip_dialog_name='tag_item_delete'
            if restrict_to_book_ids:
                msg = _('%s will be deleted from books in the Virtual library. Are you sure?')%orig_name
            else:
                msg = _('%s will be deleted from all books. Are you sure?')%orig_name
        if not question_dialog(self.tags_view,
                    title=_('Delete item'),
                    msg='<p>'+ msg,
                    det_msg=n,
                    skip_dialog_name=skip_dialog_name,
                    skip_dialog_msg=_('Show this confirmation again')):
            return
        ids_to_remove = []
        if item_id is not None:
            ids_to_remove.append(item_id)
        for child in children:
            if child.tag.is_editable:
                ids_to_remove.append(child.tag.id)

        self.current_db.new_api.remove_items(category, ids_to_remove,
                                             restrict_to_book_ids=restrict_to_book_ids)
        if restrict_to_book_ids is None:
            m = self.tags_view.model()
            m.delete_item_from_all_user_categories(orig_name, category)

        # Clean up the library view
        self.do_tag_item_renamed()
        self.tags_view.recount()

    def apply_tag_to_selected(self, field_name, item_name, remove):
        db = self.current_db.new_api
        fm = db.field_metadata.get(field_name)
        if fm is None:
            return
        book_ids = self.library_view.get_selected_ids()
        if not book_ids:
            return error_dialog(self.library_view, _('No books selected'), _(
                'You must select some books to apply {} to').format(item_name), show=True)
        existing_values = db.all_field_for(field_name, book_ids)
        series_index_field = None
        if fm['datatype'] == 'series':
            series_index_field = field_name + '_index'
        changes = {}
        for book_id, existing in iteritems(existing_values):
            if isinstance(existing, tuple):
                existing = list(existing)
                if remove:
                    try:
                        existing.remove(item_name)
                    except ValueError:
                        continue
                    changes[book_id] = existing
                else:
                    if item_name not in existing:
                        changes[book_id] = existing + [item_name]
            else:
                if remove:
                    if existing == item_name:
                        changes[book_id] = None
                else:
                    if existing != item_name:
                        changes[book_id] = item_name
        if changes:
            db.set_field(field_name, changes)
            if series_index_field is not None:
                for book_id in changes:
                    si = db.get_next_series_num_for(item_name, field=field_name)
                    db.set_field(series_index_field, {book_id: si})
            self.library_view.model().refresh_ids(set(changes), current_row=self.library_view.currentIndex().row())
            self.tags_view.recount_with_position_based_index()

    def delete_identifier(self, name, in_vl):
        d = self.current_db.new_api
        changed = False
        books_to_use = self.tags_view.model().get_book_ids_to_use() if in_vl else d.all_book_ids()
        ids = d.all_field_for('identifiers', books_to_use)
        new_ids = {}
        for id_ in ids:
            for identifier_type in ids[id_]:
                if identifier_type == name:
                    new_ids[id_] = copy.copy(ids[id_])
                    new_ids[id_].pop(name)
                    changed = True
        if changed:
            if in_vl:
                msg = _('The identifier %s will be deleted from books in the '
                        'current virtual library. Are you sure?')%name
            else:
                msg= _('The identifier %s will be deleted from all books. Are you sure?')%name
            if not question_dialog(self,
                title=_('Delete identifier'),
                msg=msg,
                skip_dialog_name='tag_browser_delete_identifiers',
                skip_dialog_msg=_('Show this confirmation again')):
                return
            d.set_field('identifiers', new_ids)
            self.tags_view.recount_with_position_based_index()

    def edit_enum_values(self, parent, db, key):
        from calibre.gui2.dialogs.enum_values_edit import EnumValuesEdit
        d = EnumValuesEdit(parent, db, key)
        d.exec()

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

    def do_author_sort_edit(self, parent, id_, select_sort=True,
                            select_link=False, is_first_letter=False,
                            lookup_author=False):
        '''
        Open the manage authors dialog
        '''

        db = self.library_view.model().db
        get_authors_func = partial(self.get_book_ids, db=db, category='authors')
        if lookup_author:
            for t in get_authors_func(use_virtual_library=False):
                if t[1] == id_:
                    id_ = t[0]
                    break
        editor = EditAuthorsDialog(parent, db, id_, select_sort, select_link,
                                   get_authors_func, is_first_letter)
        if editor.exec() == QDialog.DialogCode.Accepted:
            # Save and restore the current selections. Note that some changes
            # will cause sort orders to change, so don't bother with attempting
            # to restore the position. Restoring the state has the side effect
            # of refreshing book details.
            with self.library_view.preserve_state(preserve_hpos=False, preserve_vpos=False):
                affected_books, id_map = set(), {}
                db = db.new_api
                rename_map = {author_id:new_author for author_id, old_author, new_author, new_sort, new_link in editor.result if old_author != new_author}
                if rename_map:
                    affected_books, id_map = db.rename_items('authors', rename_map)
                link_map = {id_map.get(author_id, author_id):new_link for author_id, old_author, new_author, new_sort, new_link in editor.result}
                affected_books |= db.set_link_for_authors(link_map)
                sort_map = {id_map.get(author_id, author_id):new_sort for author_id, old_author, new_author, new_sort, new_link in editor.result}
                affected_books |= db.set_sort_for_authors(sort_map)
                self.library_view.model().refresh_ids(affected_books, current_row=self.library_view.currentIndex().row())
                self.tags_view.recount()

    def drag_drop_finished(self, ids):
        self.library_view.model().refresh_ids(ids)

    def tb_category_visibility(self, category, operation):
        '''
        Hide or show categories in the tag browser. 'category' is the lookup key.
        Operation can be:
        - 'show' to show the category in the tag browser
        - 'hide' to hide the category
        - 'toggle' to invert its visibility
        - 'is_visible' returns True if the category is currently visible, False otherwise
        '''
        if category not in self.tags_view.model().categories:
            raise ValueError(_('change_tb_category_visibility: category %s does not exist') % category)
        cats = self.tags_view.hidden_categories
        if operation == 'hide':
            cats.add(category)
        elif operation == 'show':
            cats.discard(category)
        elif operation == 'toggle':
            if category in cats:
                cats.remove(category)
            else:
                cats.add(category)
        elif operation == 'is_visible':
            return category not in cats
        else:
            raise ValueError(_('change_tb_category_visibility: invalid operation %s') % operation)
        self.library_view.model().db.new_api.set_pref('tag_browser_hidden_categories', list(cats))
        self.tags_view.recount()

# }}}


class FindBox(HistoryLineEdit):  # {{{

    def keyPressEvent(self, event):
        k = event.key()
        if k not in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            return HistoryLineEdit.keyPressEvent(self, event)
        self.blockSignals(True)
        if k == Qt.Key.Key_Down and self.currentIndex() == 0 and not self.lineEdit().text():
            self.setCurrentIndex(1), self.setCurrentIndex(0)
            event.accept()
        else:
            HistoryLineEdit.keyPressEvent(self, event)
        self.blockSignals(False)
# }}}


class TagBrowserBar(QWidget):  # {{{

    clear_find = pyqtSignal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        parent = parent.parent()
        self.l = l = QHBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.alter_tb = parent.alter_tb = b = QToolButton(self)
        b.setAutoRaise(True)
        b.setText(_('Configure')), b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        b.setToolTip(textwrap.fill(_(
            'Change how the Tag browser works, such as,'
            ' how it is sorted, what happens when you click'
            ' items, etc.'
        )))
        b.setIcon(QIcon.ic('config.png'))
        b.m = QMenu(b)
        b.setMenu(b.m)

        self.item_search = FindBox(parent)
        self.item_search.setMinimumContentsLength(5)
        self.item_search.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.item_search.initialize('tag_browser_search')
        self.item_search.completer().setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)
        self.item_search.setToolTip(
            '<p>' +_(
                'Search for items. If the text begins with equals (=) the search is '
                'exact match, otherwise it is "contains" finding items containing '
                'the text anywhere in the item name. Both exact and contains '
                'searches ignore case. You can limit the search to particular '
                'categories using syntax similar to search. For example, '
                'tags:foo will find foo in any tag, but not in authors etc. Entering '
                '*foo will collapse all categories then showing only those categories '
                'with items containing the text "foo"') + '</p>')
        ac = QAction(parent)
        parent.addAction(ac)
        parent.keyboard.register_shortcut('tag browser find box',
                _('Find in the Tag browser'), default_keys=(),
                action=ac, group=_('Tag browser'))
        ac.triggered.connect(self.set_focus_to_find_box)

        self.search_button = QToolButton()
        self.search_button.setAutoRaise(True)
        self.search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_button.setIcon(QIcon.ic('search.png'))
        self.search_button.setToolTip(_('Find the first/next matching item'))
        ac = QAction(parent)
        parent.addAction(ac)
        parent.keyboard.register_shortcut('tag browser find button',
                _('Find next match'), default_keys=(),
                action=ac, group=_('Tag browser'))
        ac.triggered.connect(self.search_button.click)

        self.toggle_search_button = b = QToolButton(self)
        le = self.item_search.lineEdit()
        le.addAction(QIcon.ic('window-close.png'), QLineEdit.ActionPosition.LeadingPosition).triggered.connect(self.close_find_box)
        b.setText(_('Find')), b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setIcon(QIcon.ic('search.png'))
        b.setCheckable(True)
        b.setChecked(gprefs.get('tag browser search box visible', False))
        b.setToolTip(_('Find item in the Tag browser'))
        b.setAutoRaise(True)
        b.toggled.connect(self.update_searchbar_state)
        self.update_searchbar_state()

    def close_find_box(self):
        self.item_search.setCurrentIndex(0)
        self.item_search.setCurrentText('')
        self.toggle_search_button.click()
        self.clear_find.emit()

    def set_focus_to_find_box(self):
        self.toggle_search_button.setChecked(True)
        self.item_search.setFocus()
        self.item_search.lineEdit().selectAll()

    def update_searchbar_state(self):
        find_shown = self.toggle_search_button.isChecked()
        self.toggle_search_button.setVisible(not find_shown)
        l = self.layout()
        while l.count():
            l.takeAt(0)
        if find_shown:
            l.addWidget(self.alter_tb)
            self.alter_tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            l.addWidget(self.item_search, 10)
            l.addWidget(self.search_button)
            self.item_search.setFocus(Qt.FocusReason.OtherFocusReason)
            self.toggle_search_button.setVisible(False)
            self.search_button.setVisible(True)
            self.item_search.setVisible(True)
        else:
            l.addWidget(self.alter_tb)
            self.alter_tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            l.addStretch(10)
            l.addStretch(10)
            l.addWidget(self.toggle_search_button)
            self.toggle_search_button.setVisible(True)
            self.search_button.setVisible(False)
            self.item_search.setVisible(False)

# }}}


class TagBrowserWidget(QFrame):  # {{{

    def __init__(self, parent):
        QFrame.__init__(self, parent)
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self._parent = parent
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0,0,0,0)

        # Set up the find box & button
        self.tb_bar = tbb = TagBrowserBar(self)
        tbb.clear_find.connect(self.reset_find)
        self.alter_tb, self.item_search, self.search_button = tbb.alter_tb, tbb.item_search, tbb.search_button
        self.toggle_search_button = tbb.toggle_search_button
        self._layout.addWidget(tbb)

        self.current_find_position = None
        self.search_button.clicked.connect(self.find)
        self.item_search.lineEdit().textEdited.connect(self.find_text_changed)
        self.item_search.textActivated.connect(self.do_find)

        # The tags view
        parent.tags_view = TagsView(parent)
        self.tags_view = parent.tags_view
        self._layout.insertWidget(0, parent.tags_view)

        # Now the floating 'not found' box
        l = QLabel(self.tags_view)
        self.not_found_label = l
        l.setFrameStyle(QFrame.Shape.StyledPanel)
        l.setAutoFillBackground(True)
        l.setText('<p><b>'+_('No more matches.</b><p> Click Find again to go to first match'))
        l.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        l.setWordWrap(True)
        l.resize(l.sizeHint())
        l.move(10,20)
        l.setVisible(False)
        self.not_found_label_timer = QTimer()
        self.not_found_label_timer.setSingleShot(True)
        self.not_found_label_timer.timeout.connect(self.not_found_label_timer_event,
                                                   type=Qt.ConnectionType.QueuedConnection)
        self.collapse_all_action = ac = QAction(parent)
        parent.addAction(ac)
        parent.keyboard.register_shortcut('tag browser collapse all',
                _('Collapse all'), default_keys=(),
                action=ac, group=_('Tag browser'))
        connect_lambda(ac.triggered, self, lambda self: self.tags_view.collapseAll())

        # The Configure Tag Browser button
        l = self.alter_tb
        ac = QAction(parent)
        parent.addAction(ac)
        parent.keyboard.register_shortcut('tag browser alter',
                _('Configure Tag browser'), default_keys=(),
                action=ac, group=_('Tag browser'))
        ac.triggered.connect(l.showMenu)

        l.m.aboutToShow.connect(self.about_to_show_configure_menu)
        l.m.show_counts_action = ac = l.m.addAction('counts')
        ac.triggered.connect(self.toggle_counts)
        l.m.show_avg_rating_action = ac = l.m.addAction(QIcon.ic('rating.png'), 'avg rating')
        ac.triggered.connect(self.toggle_avg_rating)
        sb = l.m.addAction(QIcon.ic('sort.png'), _('Sort by'))
        sb.m = l.sort_menu = QMenu(l.m)
        sb.setMenu(sb.m)
        sb.bg = QActionGroup(sb)

        # Must be in the same order as db2.CATEGORY_SORTS
        for i, x in enumerate((_('Name'), _('Number of books'),
                  _('Average rating'))):
            a = sb.m.addAction(x)
            sb.bg.addAction(a)
            a.setCheckable(True)
            if i == 0:
                a.setChecked(True)
        sb.setToolTip(
                _('Set the sort order for entries in the Tag browser'))
        sb.setStatusTip(sb.toolTip())

        ma = l.m.addAction(QIcon.ic('search.png'), _('Search type when selecting multiple items'))
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
                _('When selecting multiple entries in the Tag browser '
                    'match any or all of them'))
        ma.setStatusTip(ma.toolTip())

        mt = l.m.addAction(_('Manage authors, tags, etc.'))
        mt.setToolTip(_('All of these category managers are available by right-clicking '
                       'on items in the Tag browser above'))
        mt.m = l.manage_menu = QMenu(l.m)
        mt.setMenu(mt.m)

        l.m.filter_action = ac = l.m.addAction(QIcon.ic('filter.png'), _('Show only books that have visible categories'))
        # Give it a (complicated) shortcut so people can discover a shortcut
        # is possible, I hope without creating collisions.
        parent.keyboard.register_shortcut('tag browser filter booklist',
                _('Filter book list'), default_keys=('Ctrl+Alt+Shift+F',),
                action=ac, group=_('Tag browser'))
        ac.triggered.connect(self.filter_book_list)

        ac = QAction(parent)
        parent.addAction(ac)
        parent.keyboard.register_shortcut('tag browser toggle item',
                _("'Click' found item"), default_keys=(),
                action=ac, group=_('Tag browser'))
        ac.triggered.connect(self.toggle_item)

        ac = QAction(parent)
        parent.addAction(ac)
        parent.keyboard.register_shortcut('tag browser set focus',
                _("Give the Tag browser keyboard focus"), default_keys=(),
                action=ac, group=_('Tag browser'))
        ac.triggered.connect(self.give_tb_focus)

        # self.leak_test_timer = QTimer(self)
        # self.leak_test_timer.timeout.connect(self.test_for_leak)
        # self.leak_test_timer.start(5000)

    def about_to_show_configure_menu(self):
        ac = self.alter_tb.m.show_counts_action
        ac.setText(_('Hide counts') if gprefs['tag_browser_show_counts'] else _('Show counts'))
        ac.setIcon(QIcon.ic('minus.png') if gprefs['tag_browser_show_counts'] else QIcon.ic('plus.png'))
        ac = self.alter_tb.m.show_avg_rating_action
        ac.setText(_('Hide average rating') if config['show_avg_rating'] else _('Show average rating'))
        ac.setIcon(QIcon.ic('minus.png' if config['show_avg_rating'] else 'plus.png'))

    def filter_book_list(self):
        self.tags_view.model().set_in_tag_browser()
        self._parent.search.set_search_string('in_tag_browser:true')

    def toggle_counts(self):
        gprefs['tag_browser_show_counts'] ^= True

    def toggle_avg_rating(self):
        config['show_avg_rating'] ^= True

    def save_state(self):
        gprefs.set('tag browser search box visible', self.toggle_search_button.isChecked())

    def toggle_item(self):
        self.tags_view.toggle_current_index()

    def give_tb_focus(self, *args):
        if gprefs['tag_browser_allow_keyboard_focus']:
            tb = self.tags_view
            if tb.hasFocus():
                self._parent.shift_esc()
            elif self._parent.current_view() == self._parent.library_view:
                tb.setFocus()
                idx = tb.currentIndex()
                if not idx.isValid():
                    idx = tb.model().createIndex(0, 0)
                    tb.setCurrentIndex(idx)

    def set_pane_is_visible(self, to_what):
        self.tags_view.set_pane_is_visible(to_what)
        if not to_what:
            self._parent.shift_esc()

    def find_text_changed(self, str_):
        self.current_find_position = None

    def set_focus_to_find_box(self):
        self.tb_bar.set_focus_to_find_box()

    def do_find(self, str_=None):
        self.current_find_position = None
        self.find()

    @property
    def find_text(self):
        return str(self.item_search.currentText()).strip()

    def reset_find(self):
        model = self.tags_view.model()
        model.clear_boxed()
        if model.get_categories_filter():
            model.set_categories_filter(None)
            self.tags_view.recount()
            self.current_find_position = None

    def find(self):
        model = self.tags_view.model()
        model.clear_boxed()

        # When a key is specified don't use the auto-collapsing search.
        # A colon separates the lookup key from the search string.
        # A leading colon says not to use autocollapsing search but search all keys
        txt = self.find_text
        colon = txt.find(':')
        if colon >= 0:
            key = self._parent.library_view.model().db.\
                        field_metadata.search_term_to_field_key(txt[:colon])
            if key in self._parent.library_view.model().db.field_metadata:
                txt = txt[colon+1:]
            else:
                key = ''
                txt = txt[1:] if colon == 0 else txt
        else:
            key = None

        # key is None indicates that no colon was found.
        # key == '' means either a leading : was found or the key is invalid

        # At this point the txt might have a leading =, in which case do an
        # exact match search

        if (gprefs.get('tag_browser_always_autocollapse', False) and
                key is None and not txt.startswith('*')):
            txt = '*' + txt
        if txt.startswith('*'):
            self.tags_view.collapseAll()
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
        self.search_button.setFocus(Qt.FocusReason.OtherFocusReason)
        self.item_search.lineEdit().blockSignals(False)

        if txt.startswith('='):
            equals_match = True
            txt = txt[1:]
        else:
            equals_match = False
        self.current_find_position = \
            model.find_item_node(key, txt, self.current_find_position,
                                 equals_match=equals_match)

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

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return) and self.item_search.hasFocus():
            self.find()
            ev.accept()
            return
        return QFrame.keyPressEvent(self, ev)


# }}}
