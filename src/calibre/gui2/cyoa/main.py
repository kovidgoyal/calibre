#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# The main window for the "Create Your Own Adventure" game. It shows the
# welcome screen until the AI used to generate the story is configured, then
# either the world creation flow or, when a game is already in progress, the
# game itself.
# Run with: calibre-debug -c 'from calibre.gui2.cyoa.main import main; main()'

from qt.core import QIcon, QSize, QStackedWidget

from calibre.ai.cyoa import PROTAGONIST_ID, GeneratedWorld, start_game
from calibre.constants import CYOA_APP_UID, islinux
from calibre.gui2 import Application, error_dialog
from calibre.gui2.cyoa import data
from calibre.gui2.cyoa.game import GameWidget
from calibre.gui2.cyoa.welcome import WelcomeWidget
from calibre.gui2.cyoa.world import CreateWorldWidget
from calibre.gui2.main_window import MainWindow
from calibre.utils.localization import _


class CYOAMainWindow(MainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(_('Create Your Own Adventure'))
        self.setWindowIcon(QIcon.ic('ai.png'))
        self.stack = s = QStackedWidget(self)
        self.setCentralWidget(s)
        self.welcome = w = WelcomeWidget(self)
        w.configured.connect(self.show_appropriate_page)
        s.addWidget(w)
        self.world = cw = CreateWorldWidget(self)
        cw.game_start_requested.connect(self.start_new_game)
        s.addWidget(cw)
        self.game = g = GameWidget(self)
        g.game_abandoned.connect(self.abandon_game)
        s.addWidget(g)
        self.show_appropriate_page()

    def sizeHint(self) -> QSize:
        return QSize(1000, 720)

    def show_appropriate_page(self) -> None:
        self.setWindowTitle(_('Create Your Own Adventure'))
        if not data.is_ready('text'):
            self.welcome.show_intro_page()
            self.stack.setCurrentWidget(self.welcome)
            return
        if game_id := data.current_game_id():
            try:
                state, images, portraits = data.load_game(game_id)
            except Exception as e:
                error_dialog(self, _('Failed to load game'), _('Failed to load the current game: {}').format(e), show=True)
                data.set_current_game('')
            else:
                self.game.load_game(game_id, state, images, portraits)
                self.stack.setCurrentWidget(self.game)
                return
        self.world.reset()
        self.stack.setCurrentWidget(self.world)

    def start_new_game(self, world: GeneratedWorld, character_index: int, brief: str, art_style: str, portrait: dict[str, str] | None) -> None:
        # The portrait of the chosen character comes from the world it was
        # generated in, but from now on the game owns its own copy of it.
        state = start_game(brief, world, character_index, art_style)
        portraits = {PROTAGONIST_ID: portrait} if portrait else {}
        game_id = data.new_game_id()
        data.save_game(game_id, state, portraits=portraits)
        data.set_current_game(game_id)
        self.game.load_game(game_id, state, portraits=portraits)
        self.stack.setCurrentWidget(self.game)

    def abandon_game(self) -> None:
        data.set_current_game('')
        self.show_appropriate_page()


def main() -> None:
    override = 'calibre-ebook-viewer' if islinux else None
    app = Application([], override_program_name=override, windows_app_uid=CYOA_APP_UID)
    w = CYOAMainWindow()
    w.set_exception_handler()
    w.show()
    app.exec()
    del w
    del app


if __name__ == '__main__':
    main()
