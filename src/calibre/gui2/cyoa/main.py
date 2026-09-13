#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# The main window for the "Create Your Own Adventure" game. It shows the
# welcome screen until the AI used to generate the story is configured, then
# either the world creation flow or, when a game is already in progress, the
# game itself. Like the E-book viewer and the editor, the game is a program
# of its own: it is normally started as a separate process, either from the
# command line or by the calibre GUI via
# job_manager.launch_gui_app('cyoa'), and keeps running after the calibre
# GUI that launched it is closed.
# Run with: calibre-debug -c 'from calibre.gui2.cyoa.main import main; main()'

import os
import sys
from collections.abc import Sequence
from contextlib import closing

from qt.core import QFont, QIcon, QSize, QStackedWidget, Qt

from calibre.ai.cyoa import PROTAGONIST_ID, GeneratedWorld, StoryStyle, start_game
from calibre.constants import CYOA_APP_UID, islinux
from calibre.gui2 import Application, error_dialog, gprefs, setup_gui_option_parser
from calibre.gui2.cyoa import data
from calibre.gui2.cyoa.game import GameWidget
from calibre.gui2.cyoa.welcome import WelcomeWidget
from calibre.gui2.cyoa.world import CreateWorldWidget
from calibre.gui2.listener import Listener, send_message_in_process
from calibre.gui2.main_window import MainWindow
from calibre.ptempfile import reset_base_dir
from calibre.utils.config import OptionParser
from calibre.utils.ipc import cyoa_socket_address
from calibre.utils.localization import _
from calibre.utils.lock import SingleInstance

# Only one process can play at a time, as two of them would overwrite each
# other's auto-saved game, see main().
SINGLE_INSTANCE_NAME = 'calibre_cyoa'


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
        cw.saved_game_load_requested.connect(self.resume_saved_game)
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

    def start_new_game(self, world: GeneratedWorld, character_index: int, brief: str, style: StoryStyle, portrait: dict[str, str] | None) -> None:
        # The portrait of the chosen character comes from the world it was
        # generated in, but from now on the game owns its own copy of it.
        state = start_game(brief, world, character_index, style)
        portraits = {PROTAGONIST_ID: portrait} if portrait else {}
        game_id = data.new_game_id()
        data.save_game(game_id, state, portraits=portraits)
        data.set_current_game(game_id)
        self.game.load_game(game_id, state, portraits=portraits)
        self.stack.setCurrentWidget(self.game)

    def resume_saved_game(self, save_name: str) -> None:
        # The save itself is left untouched: it is copied into a new current
        # game, so that playing on from it does not overwrite it.
        try:
            state, images, portraits = data.load_game(save_name, base=data.saves_dir())
        except Exception as e:
            error_dialog(self, _('Failed to load game'), _('Failed to load the saved game "{0}": {1}').format(save_name, e), show=True)
            return
        game_id = data.new_game_id()
        data.save_game(game_id, state, images, portraits=portraits)
        data.set_current_game(game_id)
        self.game.load_game(game_id, state, images, portraits, save_name=save_name)
        self.stack.setCurrentWidget(self.game)

    def abandon_game(self) -> None:
        data.set_current_game('')
        self.show_appropriate_page()

    def message_from_other_instance(self, msg: bytes) -> None:
        # Another process was started to play the game. Since there can be
        # only one, it asks this one to come to the front instead, see
        # main().
        self.raise_and_focus()


def option_parser() -> OptionParser:
    from calibre.gui2.main_window import option_parser as base_option_parser

    parser = base_option_parser(
        _(
            '''\
%prog [options]

Play a "Create Your Own Adventure" game, in which the story is written by an AI as you play it.
'''
        )
    )
    setup_gui_option_parser(parser)
    return parser


def run_gui(app: Application, listener: Listener | None = None) -> None:
    w = CYOAMainWindow()
    w.set_exception_handler()
    app.shutdown_signal_received.connect(w.close)
    if listener is not None:
        listener.message_received.connect(w.message_from_other_instance, type=Qt.ConnectionType.QueuedConnection)
    w.show()
    app.exec()
    del w


def main(args: Sequence[str] = sys.argv) -> None:
    # Ensure the game can continue to be played if the calibre GUI that
    # launched it is closed, which would otherwise take its temporary
    # directory away.
    os.environ.pop('CALIBRE_WORKER_TEMP_DIR', None)
    reset_base_dir()
    args = list(args)
    override = 'calibre-cyoa' if islinux else None
    app = Application(args, override_program_name=override, windows_app_uid=CYOA_APP_UID)
    option_parser().parse_args(args)
    fi = gprefs['font']
    if fi is not None:
        font = QFont(*(fi[:4]))
        s = gprefs.get('font_stretch', None)
        if s is not None:
            font.setStretch(s)
        app.setFont(font)
    app.setWindowIcon(QIcon.ic('ai.png'))
    # Two processes playing at the same time would overwrite each other's
    # auto-saved game, so a second launch asks the one already running to
    # come to the front and exits.
    with SingleInstance(SINGLE_INSTANCE_NAME) as si:
        if not si:
            try:
                send_message_in_process(b'raise-window', address=cyoa_socket_address())
            except Exception as err:
                error_dialog(
                    None,
                    _('Failed to connect'),
                    _('Could not connect to the already running game window, try restarting it.'),
                    det_msg=str(err),
                    show=True,
                )
                raise SystemExit(1)
        else:
            try:
                listener = Listener(address=cyoa_socket_address(), parent=app)
                listener.start_listening()
            except Exception as err:
                error_dialog(
                    None,
                    _('Failed to start listener'),
                    _('Could not start the listener used to ensure only one game is played at a time. Try rebooting your computer.'),
                    det_msg=str(err),
                    show=True,
                )
                run_gui(app)
            else:
                with closing(listener):
                    run_gui(app, listener)
    del app


if __name__ == '__main__':
    main()
