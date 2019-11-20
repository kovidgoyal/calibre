#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>


from calibre.gui2 import gprefs
from calibre.gui2.actions import InterfaceAction
from polyglot.builtins import iteritems, map, range


class AuthorMapAction(InterfaceAction):

    name = 'Author Mapper'
    action_spec = (_('Author mapper'), 'user_profile.png', _('Transform the authors for books in the library'), None)
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.start_map)

    def start_map(self):
        rows = self.gui.library_view.selectionModel().selectedRows()
        selected = True
        if not rows or len(rows) < 2:
            selected = False
            rows = range(self.gui.library_view.model().rowCount(None))
        ids = set(map(self.gui.library_view.model().id, rows))
        self.do_map(ids, selected)

    def do_map(self, book_ids, selected):
        from calibre.ebooks.metadata.author_mapper import map_authors, compile_rules
        from calibre.gui2.author_mapper import RulesDialog
        from calibre.gui2.device import BusyCursor
        d = RulesDialog(self.gui)
        d.setWindowTitle(ngettext(
            'Map authors for one book in the library',
            'Map authors for {} books in the library', len(book_ids)).format(len(book_ids)))
        d.rules = gprefs.get('library-author-mapper-ruleset', ())
        txt = ngettext(
            'The changes will be applied to the <b>selected book</b>',
            'The changes will be applied to the <b>{} selected books</b>', len(book_ids)) if selected else ngettext(
            'The changes will be applied to <b>one book in the library</b>',
            'The changes will be applied to <b>{} books in the library</b>', len(book_ids))
        d.edit_widget.msg_label.setText(d.edit_widget.msg_label.text() + '<p>' + txt.format(len(book_ids)))
        if d.exec_() != d.Accepted:
            return
        with BusyCursor():
            rules = d.rules
            gprefs.set('library-author-mapper-ruleset', rules)
            rules = compile_rules(rules)
            db = self.gui.current_db.new_api
            author_map = db.all_field_for('authors', book_ids)
            changed_author_map = {}
            changed_author_sort_map = {}
            for book_id, authors in iteritems(author_map):
                authors = list(authors)
                new_authors = map_authors(authors, rules)
                if authors != new_authors:
                    changed_author_map[book_id] = new_authors
                    changed_author_sort_map[book_id] = db.author_sort_from_authors(new_authors)
            if changed_author_map:
                db.set_field('authors', changed_author_map)
                db.set_field('author_sort', changed_author_sort_map)
                self.gui.library_view.model().refresh_ids(tuple(changed_author_map), current_row=self.gui.library_view.currentIndex().row())
