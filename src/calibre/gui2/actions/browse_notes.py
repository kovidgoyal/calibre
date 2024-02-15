#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>


from calibre.gui2.actions import InterfaceAction


class BrowseNotesAction(InterfaceAction):

    name = 'Browse Notes'
    action_spec = (_('Browse notes'), 'notes.png',
                   _('Browse notes for authors, tags, etc. in the library'), _('Ctrl+Shift+N'))
    dont_add_to = frozenset(('context-menu-device',))
    action_type = 'current'

    def genesis(self):
        self.d = None
        self.qaction.triggered.connect(self.show_browser)

    def show_browser(self):
        if self.d is not None and self.d.isVisible():
            self.d.raise_and_focus()
        else:
            from calibre.gui2.library.notes import NotesBrowser
            self.d = NotesBrowser(self.gui)
            self.d.show()
