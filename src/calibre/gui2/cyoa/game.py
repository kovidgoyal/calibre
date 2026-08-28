#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Placeholder for the actual gameplay widget of the "Create Your Own
# Adventure" game.

from qt.core import QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout, QWidget, pyqtSignal

from calibre.ai.cyoa import GameState
from calibre.ai.utils import ContentType, response_to_html
from calibre.gui2 import question_dialog
from calibre.utils.localization import _


class GameWidget(QWidget):
    game_abandoned = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.game_id = ''
        l = QVBoxLayout(self)
        self.title_label = t = QLabel(self)
        f = t.font()
        f.setPointSizeF(f.pointSizeF() * 1.5)
        f.setBold(True)
        t.setFont(f)
        t.setWordWrap(True)
        l.addWidget(t)
        self.character_label = c = QLabel(self)
        c.setWordWrap(True)
        l.addWidget(c)
        self.world_view = w = QTextBrowser(self)
        w.setOpenExternalLinks(True)
        l.addWidget(w)
        self.construction_label = u = QLabel(_('Gameplay is under construction, check back soon.'))
        u.setWordWrap(True)
        l.addWidget(u)
        h = QHBoxLayout()
        self.abandon_button = b = QPushButton(_('&Abandon game'), self)
        b.clicked.connect(self.abandon_game)
        h.addWidget(b), h.addStretch()
        l.addLayout(h)

    def load_game(self, game_id: str, state: GameState) -> None:
        self.game_id = game_id
        self.title_label.setText(state.world.title)
        self.character_label.setText(_('Playing as {0}: {1}').format(state.character.name, state.character.description))
        html = response_to_html(state.world.world_description, ContentType.markdown)
        html += f'<hr><p><b>{_("Win condition")}</b></p>' + response_to_html(state.world.win_condition, ContentType.markdown)
        self.world_view.setHtml(html)

    def abandon_game(self) -> None:
        if question_dialog(
            self,
            _('Are you sure?'),
            _('Abandon the current game and create a new world? The abandoned game remains saved on disk.'),
        ):
            self.game_abandoned.emit()


if __name__ == '__main__':
    from calibre.ai.cyoa import GeneratedWorld, PlayerCharacter, start_game
    from calibre.gui2 import Application

    app = Application([])
    w = GameWidget()
    pc = PlayerCharacter('Ada', 'a stubborn engineer', 'She built the mist engines.')
    world = GeneratedWorld(title='Mist City', world_description='A city lost in *perpetual* mist.', characters=(pc,), win_condition='Escape the city.')
    w.load_game('test', start_game('a foggy city', world, pc))
    w.game_abandoned.connect(lambda: print('game abandoned'))
    w.show()
    app.exec()
    del w
    del app
