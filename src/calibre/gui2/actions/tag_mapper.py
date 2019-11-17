#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>


from polyglot.builtins import iteritems, map, range

from calibre.gui2 import gprefs
from calibre.gui2.actions import InterfaceAction


class TagMapAction(InterfaceAction):

    name = 'Tag Mapper'
    action_spec = (_('Tag mapper'), 'tags.png', _('Filter/transform the tags for books in the library'), None)
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
        from calibre.ebooks.metadata.tag_mapper import map_tags
        from calibre.gui2.tag_mapper import RulesDialog
        from calibre.gui2.device import BusyCursor
        d = RulesDialog(self.gui)
        d.setWindowTitle(ngettext(
            'Map tags for one book in the library',
            'Map tags for {} books in the library', len(book_ids)).format(len(book_ids)))
        d.rules = gprefs.get('library-tag-mapper-ruleset', ())
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
            gprefs.set('library-tag-mapper-ruleset', rules)
            db = self.gui.current_db.new_api
            tag_map = db.all_field_for('tags', book_ids)
            changed_tag_map = {}
            for book_id, tags in iteritems(tag_map):
                tags = list(tags)
                new_tags = map_tags(tags, rules)
                if tags != new_tags:
                    changed_tag_map[book_id] = new_tags
            if changed_tag_map:
                db.set_field('tags', changed_tag_map)
                self.gui.library_view.model().refresh_ids(tuple(changed_tag_map), current_row=self.gui.library_view.currentIndex().row())
                self.gui.tags_view.recount()
