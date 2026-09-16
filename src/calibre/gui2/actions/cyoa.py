#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

from calibre.gui2.actions import InterfaceAction
from calibre.utils.localization import _


class CYOAAction(InterfaceAction):
    name = 'Create your own adventure'
    action_spec = (
        _('Create your own adventure'),
        'cyoa.png',
        _('Play a "Create your own Adventure" game, in which the story is written by an AI as you play it'),
        (),
    )
    action_type = 'global'
    # The game has nothing to do with the books in the library, so it makes no
    # sense in the context menus for books.
    dont_add_to = frozenset({'context-menu', 'context-menu-device', 'context-menu-cover-browser', 'context-menu-split'})

    def genesis(self) -> None:
        self.qaction.triggered.connect(self.play_game)

    def play_game(self) -> None:
        # The game is a program of its own, run in a separate process that
        # keeps running even after this calibre instance is closed. Starting a
        # second one simply raises the window of the one already running, see
        # calibre.gui2.cyoa.main.main()
        from calibre.gui2.widgets import BusyCursor

        with BusyCursor():
            self.gui.job_manager.launch_gui_app('cyoa', kwargs={'args': ['calibre-cyoa']})
