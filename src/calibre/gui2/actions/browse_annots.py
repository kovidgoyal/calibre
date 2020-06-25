#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals


from calibre.gui2.actions import InterfaceAction


class BrowseAnnotationsAction(InterfaceAction):

    name = 'Browse Annotations'
    action_spec = (_('Browse annotations'), 'polish.png',
                   _('Browse highlights and bookmarks from all books in the library'), _('B'))
    dont_add_to = frozenset(('context-menu-device',))
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.show_browser)
        self._browser = None

    @property
    def browser(self):
        if self._browser is None:
            from calibre.gui2.library.annotations import AnnotationsBrowser
            self._browser = AnnotationsBrowser(self.gui)
        return self._browser

    def show_browser(self):
        self.browser.show_dialog()
