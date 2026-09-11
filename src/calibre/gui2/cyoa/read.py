#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# The dialog that lets the player re-read the story of the game so far as a
# book. The chapters it is made of are listed on the left, the prose of the
# selected chapter is shown on the right, rendered by the same widget the
# game renders its turns with, so that it follows the text display settings
# and zooms along with the game.

from qt.core import QDialogButtonBox, QLabel, QListWidget, QListWidgetItem, QSize, QSplitter, QTextCursor, QUrl, QVBoxLayout, QWidget

from calibre.ai.cyoa import GameState
from calibre.gui2 import safe_open_url
from calibre.gui2.cyoa.story_widgets import SCENE_DIVIDER_WIDTH, StoryView, add_scene_divider_resource, render_chapter, scene_divider_image
from calibre.gui2.widgets2 import Dialog
from calibre.utils.localization import _, ngettext


class ReadStoryDialog(Dialog):
    def __init__(self, state: GameState, parent: QWidget | None = None) -> None:
        self.state = state
        super().__init__(_('Read the story so far'), 'cyoa-read-story', parent, default_buttons=QDialogButtonBox.StandardButton.Close)

    def setup_ui(self) -> None:
        l = QVBoxLayout(self)
        # Named splitter so that Dialog saves and restores its position
        self.splitter = sp = QSplitter(self)
        sp.setChildrenCollapsible(False)

        left = QWidget(sp)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.chapters_label = la = QLabel(_('&Chapters:'), left)
        self.chapters_list = cl = QListWidget(left)
        la.setBuddy(cl)
        ll.addWidget(la), ll.addWidget(cl)
        sp.addWidget(left)

        self.story_view = sv = StoryView(sp)
        # Links in the prose are opened in the browser rather than followed
        # in this view, which would replace the chapter being read.
        sv.setOpenLinks(False)
        sv.anchorClicked.connect(self.on_link_clicked)
        sp.addWidget(sv)
        sp.setStretchFactor(0, 1)
        sp.setStretchFactor(1, 3)
        l.addWidget(sp, stretch=10)
        l.addWidget(self.bb)

        self.scene_divider = scene_divider_image(SCENE_DIVIDER_WIDTH, self.devicePixelRatioF())
        for i, title in enumerate(self.state.chapter_titles):
            item = QListWidgetItem(title, cl)
            num = sum(1 for t in self.state.turns if t.chapter == i)
            item.setToolTip(ngettext('{} turn', '{} turns', num).format(num))
        # The chapter being played is the one the player is most likely to
        # want to look back at first. The list is populated and positioned
        # before connecting, so that the chapter is rendered exactly once.
        cl.setCurrentRow(self.state.current_chapter)
        cl.currentRowChanged.connect(self.show_chapter)
        self.show_chapter(cl.currentRow())

    def sizeHint(self) -> QSize:
        return QSize(900, 700)

    def show_chapter(self, chapter: int) -> None:
        sv = self.story_view
        sv.stopMomentumScroll()
        sv.clear()
        add_scene_divider_resource(sv, self.scene_divider)  # clear() discards document resources
        sv.apply_max_line_width()  # as does the margin limiting the line length
        c = sv.textCursor()
        c.movePosition(QTextCursor.MoveOperation.End)
        render_chapter(c, self.state, chapter)
        # Inserting the text leaves the view scrolled to the end of the
        # chapter, but a chapter is meant to be read from its start.
        if (vsb := sv.verticalScrollBar()) is not None:
            vsb.setValue(vsb.minimum())

    def on_link_clicked(self, url: QUrl) -> None:
        safe_open_url(url)


if __name__ == '__main__':
    from calibre.ai.cyoa import GeneratedWorld, PlayerCharacter, StoryTurn, SummaryUpdate, TurnRecord, initial_summary, start_game
    from calibre.gui2 import Application

    app = Application([])
    pc = PlayerCharacter('Ada', 'a stubborn engineer', 'She built the mist engines.')
    world = GeneratedWorld(title='Mist City', world_description='A city lost in *perpetual* mist.', characters=(pc,))
    state = start_game('a foggy city', world)
    for i in range(9):
        new_chapter = bool(i) and i % 3 == 0
        turn = StoryTurn(
            narrative=f'**Turn {i + 1}**: The mist *swirls* around you as something stirs in the distance.' + ' The fog thickens with every breath.' * 3,
            quick_actions=(),
            scene_description='A foggy city street at night.',
            summary_update=SummaryUpdate(current_situation='In the mist.', character_updates=(), new_major_events=(), upcoming_events=()),
            starts_new_chapter=new_chapter,
            chapter_title=f'Chapter starting at turn {i + 1}' if new_chapter else None,
        )
        state.turns.append(
            TurnRecord(
                player_input=f'Take step {i + 1}' if i else '',
                raw_response='',
                turn=turn,
                summary=initial_summary(world, pc),
                chapter=i // 3,
            )
        )
    ReadStoryDialog(state).exec()
    del app
