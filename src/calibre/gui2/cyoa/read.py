#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# The dialog that lets the player re-read the story of the game so far as a
# book. The chapters it is made of are listed on the left, the prose of the
# selected chapter is shown on the right, rendered by the same widget the
# game renders its turns with, so that it follows the text display settings
# and zooms along with the game. The pictures of the scenes of the turns are
# shown as the illustrations of the chapter, each after the prose it
# illustrates, and can be shown full size by clicking them. The story can
# also be exported from here as an EPUB book, to be read outside the game,
# see export_epub() and calibre.gui2.cyoa.epub.

import os
import shutil
import tempfile
from collections.abc import Mapping

from qt.core import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QEvent,
    QHBoxLayout,
    QIcon,
    QKeyEvent,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QObject,
    QPixmap,
    QPushButton,
    QResizeEvent,
    QSize,
    QSplitter,
    Qt,
    QTextCursor,
    QTimer,
    QUrl,
    QVBoxLayout,
    QWidget,
    pyqtSignal,
)

from calibre.ai.cyoa import GameState
from calibre.gui2 import choose_save_file, error_dialog, info_dialog, safe_open_url
from calibre.gui2.cyoa import data
from calibre.gui2.cyoa.story_widgets import (
    SCENE_DIVIDER_WIDTH,
    SCENE_IMAGE_SCHEME,
    StoryView,
    add_scene_divider_resource,
    add_scene_image_resources,
    render_chapter,
    scene_divider_image,
    story_text_width,
)
from calibre.gui2.image_popup import ImagePopup
from calibre.gui2.widgets import BusyCursor
from calibre.gui2.widgets2 import Dialog
from calibre.ptempfile import get_default_tempdir
from calibre.utils.localization import _, ngettext

# How long to wait after the width available for the story changes before
# rendering the chapter again with the illustrations scaled to the new width,
# so that dragging the splitter or the window edge does not re-render on
# every pixel of movement.
RELAYOUT_DELAY = 300  # milliseconds
# The width has to change by at least this fraction for the illustrations to
# be worth scaling again.
MIN_RELAYOUT_CHANGE = 0.05


class ReadStoryView(StoryView):
    # The illustrations are scaled for the width of the text column, which
    # changes both when the view is resized and when the text display
    # settings, such as the font size or the maximum line length, change.
    relayout_needed = pyqtSignal()

    def apply_text_display_settings(self) -> None:
        super().apply_text_display_settings()
        self.relayout_needed.emit()

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        super().resizeEvent(a0)
        self.relayout_needed.emit()


class ExportDestination(Dialog):
    # Asks what should be done with a book that has just been exported. There
    # are three answers to that and not two, which is why this is a dialog of
    # its own rather than a question_dialog(): on a question there is no way
    # to say "neither", so dismissing it with Esc or the window close button
    # counted as the answer no and quietly went on to save a book the player
    # had changed their mind about. Here only the two buttons choose a
    # destination and everything else abandons the export.

    def __init__(self, parent: QWidget | None = None) -> None:
        self.add_to_library = False
        super().__init__(_('Where should the book go?'), 'cyoa-export-epub-destination', parent, default_buttons=QDialogButtonBox.StandardButton.Cancel)

    def setup_ui(self) -> None:
        l = QVBoxLayout(self)
        self.msg = la = QLabel(
            _('The story so far has been made into an EPUB book. It can be added to your calibre library or saved to a file of your choosing.'), self
        )
        la.setWordWrap(True)
        la.setMinimumWidth(400)
        l.addWidget(la)
        l.addWidget(self.bb)

        self.add_button = b = self.bb.addButton(_('&Add to calibre'), QDialogButtonBox.ButtonRole.ActionRole)
        assert b is not None
        b.setIcon(QIcon.ic('add_book.png'))
        b.setToolTip('<p>' + _('Add the book to your calibre library, starting calibre if it is not already running'))
        b.clicked.connect(self.add_to_calibre_requested)
        # Adding to the library is both the more common choice and the
        # reversible one, so it is what Enter does.
        b.setDefault(True)
        b.setFocus(Qt.FocusReason.OtherFocusReason)

        self.save_button = b = self.bb.addButton(_('&Save to a file'), QDialogButtonBox.ButtonRole.ActionRole)
        assert b is not None
        b.setIcon(QIcon.ic('save.png'))
        b.setToolTip('<p>' + _('Save the book as an EPUB file of your choosing, to read outside calibre'))
        b.clicked.connect(self.save_to_disk_requested)

    def add_to_calibre_requested(self) -> None:
        self.add_to_library = True
        self.accept()

    def save_to_disk_requested(self) -> None:
        self.add_to_library = False
        self.accept()


class ReadStoryDialog(Dialog):
    def __init__(
        self,
        state: GameState,
        images: Mapping[int, data.SceneImage] | None = None,
        parent: QWidget | None = None,
        portraits: Mapping[str, Mapping[str, str]] | None = None,
    ) -> None:
        # images maps one based turn number to the picture of that turn's
        # scene and portraits maps the stable id of a character to their
        # portrait, both as GameWidget keeps them. The portraits are not used
        # by the view, only by the dramatis personae of an exported book.
        self.state = state
        self.images: dict[int, bytes] = {k: v.data for k, v in (images or {}).items() if v.data}
        self.portraits: dict[str, Mapping[str, str]] = dict(portraits or {})
        self.displayed_image_turns: frozenset[int] = frozenset()
        self.rendered_width = 0
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

        self.story_view = sv = ReadStoryView(sp)
        # Links in the prose are opened in the browser rather than followed
        # in this view, which would replace the chapter being read.
        sv.setOpenLinks(False)
        sv.anchorClicked.connect(self.on_link_clicked)
        sp.addWidget(sv)
        sp.setStretchFactor(0, 1)
        sp.setStretchFactor(1, 3)
        l.addWidget(sp, stretch=10)

        bl = QHBoxLayout()
        self.show_images = si = QCheckBox(_('Show &pictures'), self)
        si.setToolTip('<p>' + _('Show the pictures of the scenes of the story as illustrations. Click an illustration to see it full size.'))
        si.setChecked(data.read_story_show_images())
        si.setVisible(bool(self.images))
        si.toggled.connect(self.toggle_images)
        self.export_button = eb = QPushButton(QIcon.ic('save.png'), _('Export as &EPUB'), self)
        eb.setToolTip('<p>' + _('Turn the story so far into an EPUB book, to read outside the game or add to your calibre library'))
        eb.clicked.connect(self.export_epub)
        bl.addWidget(si), bl.addStretch(10), bl.addWidget(eb), bl.addWidget(self.bb)
        l.addLayout(bl)

        self.image_popup = ImagePopup(self)
        # Scaling the illustrations for a width that is still changing as
        # the window or the splitter is dragged would be wasted work.
        self.relayout_timer = rt = QTimer(self)
        rt.setSingleShot(True)
        rt.setInterval(RELAYOUT_DELAY)
        rt.timeout.connect(self.relayout_images)
        sv.relayout_needed.connect(rt.start)

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
        sv.installEventFilter(self)
        sv.setFocus()

    def sizeHint(self) -> QSize:
        return QSize(900, 700)

    def show_chapter(self, chapter: int, preserve_scroll: bool = False) -> None:
        sv = self.story_view
        vsb = sv.verticalScrollBar()
        # When the chapter is rendered again only because the illustrations
        # need scaling for a new width, the player must not lose their place
        # in it. The place is remembered as a fraction of the chapter as the
        # text is about to be laid out afresh.
        fraction = 0.0
        if preserve_scroll and vsb is not None and vsb.maximum() > vsb.minimum():
            fraction = (vsb.value() - vsb.minimum()) / (vsb.maximum() - vsb.minimum())
        sv.stopMomentumScroll()
        sv.clear()
        add_scene_divider_resource(sv, self.scene_divider)  # clear() discards document resources
        sv.apply_max_line_width()  # as does the margin limiting the line length
        self.rendered_width = story_text_width(sv)
        self.displayed_image_turns = self.register_images(chapter)
        c = sv.textCursor()
        c.movePosition(QTextCursor.MoveOperation.End)
        render_chapter(c, self.state, chapter, self.displayed_image_turns)
        # Inserting the text leaves the view scrolled to the end of the
        # chapter, but a chapter is meant to be read from its start.
        if vsb is not None:
            vsb.setValue(vsb.minimum() + round(fraction * (vsb.maximum() - vsb.minimum())))

    def register_images(self, chapter: int) -> frozenset[int]:
        # Make the pictures of the turns of this chapter available to the
        # text layout, scaled for the current width of the text column. Only
        # the chapter being read is rendered, so only its pictures are
        # decoded and scaled.
        if not self.images or not self.show_images.isChecked():
            return frozenset()
        of_chapter = {i + 1: self.images[i + 1] for i, t in enumerate(self.state.turns) if t.chapter == chapter and i + 1 in self.images}
        return add_scene_image_resources(self.story_view, of_chapter, self.rendered_width)

    def relayout_images(self) -> None:
        # The illustrations are scaled for the width of the text column, so
        # a change to it means they have to be scaled and inserted again.
        if not self.displayed_image_turns:
            return
        width = story_text_width(self.story_view)
        if not width or abs(width - self.rendered_width) < MIN_RELAYOUT_CHANGE * max(1, self.rendered_width):
            return
        self.show_chapter(self.chapters_list.currentRow(), preserve_scroll=True)

    def toggle_images(self) -> None:
        data.set_read_story_show_images(self.show_images.isChecked())
        self.show_chapter(self.chapters_list.currentRow(), preserve_scroll=True)

    def show_scene_image(self, turn_number: int) -> None:
        # The picture of a scene at its full size, as double clicking the
        # picture of the current scene does while playing.
        pm = QPixmap()
        if (raw := self.images.get(turn_number)) and pm.loadFromData(raw):
            self.image_popup.current_img = pm
            self.image_popup.current_url = QUrl(data.image_file_name(turn_number))
            self.image_popup()

    # Exporting the story as a book {{{

    def export_epub(self) -> None:
        from calibre.gui2.cyoa.epub import story_to_epub

        # The book has to be able to outlive this process: when it is handed
        # to calibre to add, the game could easily be closed before the GUI
        # it just launched has copied the book into the library, and
        # calibre's own temporary folder is deleted the moment the game
        # exits. So it goes into a folder of the system temporary folder
        # instead, which is removed again here in every case except that
        # one, in which calibre removes it, see add_book_to_calibre().
        tdir = tempfile.mkdtemp(prefix='calibre-cyoa-', dir=get_default_tempdir())
        path = os.path.join(tdir, data.save_name_for_title(self.state.world.title) + '.epub')
        try:
            with BusyCursor():
                story_to_epub(self.state, path, self.images, self.portraits)
        except Exception:
            import traceback

            shutil.rmtree(tdir, ignore_errors=True)
            error_dialog(
                self,
                _('Failed to create the book'),
                _('Failed to turn this story into an EPUB book. Click "Show details" for more information.'),
                det_msg=traceback.format_exc(),
                show=True,
            )
            return
        d = ExportDestination(self)
        if d.exec() != QDialog.DialogCode.Accepted:
            shutil.rmtree(tdir, ignore_errors=True)
            return
        if d.add_to_library:
            self.add_book_to_calibre(path, tdir)
        else:
            self.save_book_to_disk(path, tdir)

    def add_book_to_calibre(self, path: str, tdir: str) -> None:
        # Adding to the library is the calibre GUI's job, and starting it with
        # the book as the argument of --add-and-delete is what asks it to do
        # it, whether or not one is already running. calibre takes ownership
        # of the book file, deleting both it and the folder it is in once it
        # has been added, so tdir must not be removed here.
        from calibre.startup import launch_calibre_gui

        try:
            launch_calibre_gui(('--add-and-delete', path))
        except Exception:
            import traceback

            shutil.rmtree(tdir, ignore_errors=True)
            error_dialog(
                self,
                _('Failed to start calibre'),
                _('Failed to start calibre to add the book to your library. Click "Show details" for more information.'),
                det_msg=traceback.format_exc(),
                show=True,
            )
            return
        info_dialog(
            self,
            _('Adding the book to calibre'),
            _('The book is being added to your calibre library. The calibre main window will open if it is not already running.'),
            show=True,
        )

    def save_book_to_disk(self, path: str, tdir: str) -> None:
        try:
            dest = choose_save_file(
                self, 'cyoa-export-epub', _('Save the story as'), filters=[(_('EPUB books'), ['epub'])], initial_filename=os.path.basename(path)
            )
            if not dest:
                return
            if not dest.lower().endswith('.epub'):
                dest += '.epub'
            try:
                shutil.move(path, dest)
            except Exception:
                import traceback

                error_dialog(
                    self,
                    _('Failed to save the book'),
                    _('Failed to save the book to {}. Click "Show details" for more information.').format(dest),
                    det_msg=traceback.format_exc(),
                    show=True,
                )
        finally:
            shutil.rmtree(tdir, ignore_errors=True)

    # }}}

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if a0 is self.story_view and a1 is not None and a1.type() == QEvent.Type.KeyPress:
            assert isinstance(a1, QKeyEvent)
            if self._handle_story_key(a1):
                return True
        return super().eventFilter(a0, a1)

    def _handle_story_key(self, event: QKeyEvent) -> bool:
        key = event.key()
        mods = event.modifiers()
        no_mods = mods == Qt.KeyboardModifier.NoModifier
        ctrl = mods == Qt.KeyboardModifier.ControlModifier
        sv = self.story_view
        cl = self.chapters_list
        vsb = sv.verticalScrollBar()
        if vsb is None:
            return False

        if ctrl and key == Qt.Key.Key_Home:
            cl.setCurrentRow(0)
            vsb.setValue(vsb.minimum())
            return True

        if ctrl and key == Qt.Key.Key_End:
            cl.setCurrentRow(cl.count() - 1)
            vsb.setValue(vsb.maximum())
            return True

        if no_mods and key in (Qt.Key.Key_Up, Qt.Key.Key_PageUp):
            if vsb.value() <= vsb.minimum():
                row = cl.currentRow()
                if row > 0:
                    cl.setCurrentRow(row - 1)
                    vsb.setValue(vsb.maximum())
                return True
            return False

        if no_mods and key in (Qt.Key.Key_Down, Qt.Key.Key_PageDown, Qt.Key.Key_Space):
            if vsb.value() >= vsb.maximum():
                row = cl.currentRow()
                if row < cl.count() - 1:
                    cl.setCurrentRow(row + 1)
                return True
            if key == Qt.Key.Key_Space:
                vsb.setValue(min(vsb.value() + vsb.pageStep(), vsb.maximum()))
                return True
            return False

        return False

    def on_link_clicked(self, url: QUrl) -> None:
        if url.scheme() != SCENE_IMAGE_SCHEME:
            safe_open_url(url)
            return
        try:
            turn_number = int(url.path())
        except ValueError:
            return
        self.show_scene_image(turn_number)


if __name__ == '__main__':
    from base64 import standard_b64encode

    from qt.core import QBuffer, QColor, QImage, QIODeviceBase, QPainter

    from calibre.ai.cyoa import PROTAGONIST_ID, GeneratedWorld, PlayerCharacter, StoryTurn, SummaryUpdate, TurnRecord, initial_summary, start_game
    from calibre.gui2 import Application

    def demo_image(turn_number: int) -> data.SceneImage:
        img = QImage(1024, 768, QImage.Format.Format_RGB32)
        img.fill(QColor.fromHsv((turn_number * 37) % 360, 120, 160))
        p = QPainter(img)
        f = p.font()
        f.setPointSize(72)
        p.setFont(f)
        p.setPen(QColor('white'))
        p.drawText(img.rect(), int(Qt.AlignmentFlag.AlignCenter), f'Scene {turn_number}')
        p.end()
        buf = QBuffer()
        buf.open(QIODeviceBase.OpenModeFlag.WriteOnly)
        img.save(buf, 'PNG')
        return data.SceneImage(data=bytes(buf.data()))

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
            summary_update=SummaryUpdate(current_situation='In the mist.', character_updates=(), new_major_events=()),
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
    # Only some of the turns have a picture, as in a game in which image
    # generation was turned on part way through or failed for a turn.
    images = {i: demo_image(i) for i in range(1, len(state.turns) + 1) if i % 3 != 2}
    portraits = {PROTAGONIST_ID: {'mime': 'image/png', 'data': standard_b64encode(demo_image(99).data).decode('ascii')}}
    ReadStoryDialog(state, images, portraits=portraits).exec()
    del app
