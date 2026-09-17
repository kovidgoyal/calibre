#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

# Exporting the story of a game as an EPUB 3 book, so that the player can
# read it in the calibre viewer or on their reader rather than in the game
# window. The book is built with the same container machinery the editor and
# the polish tools use: an empty EPUB is created, upgraded from EPUB 2 to
# EPUB 3, and its chapters, pictures and navigation are then added to the
# container, see story_to_epub(). The book opens with a generated cover, see
# add_cover(), then a prologue holding the description of the world, followed
# by a dramatis personae listing the character the player plays and everybody
# they share the world with, and then one file per chapter, laid out so that
# it reads well on screens of widely differing sizes, see EPUB_CSS. This
# module must not import any GUI code, so that it can be used and tested
# headless; asking the player where the book should go is the job of the read
# the story dialog, see calibre.gui2.cyoa.read.

import os
from base64 import standard_b64decode
from collections.abc import Iterator, Mapping
from contextlib import suppress
from html import escape
from typing import TYPE_CHECKING

from calibre import force_unicode
from calibre.ai.cyoa import PROTAGONIST_ID, CharacterState, GameState
from calibre.ai.utils import ContentType, response_to_html
from calibre.constants import filesystem_encoding, iswindows
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.oeb.polish.container import EpubContainer, get_container
from calibre.ebooks.oeb.polish.create import create_book
from calibre.ebooks.oeb.polish.pretty import pretty_html_tree
from calibre.ebooks.oeb.polish.toc import TOC, commit_nav_toc
from calibre.ebooks.oeb.polish.upgrade import upgrade_book
from calibre.utils.localization import _, canonicalize_lang, get_lang, lang_as_iso639_1
from calibre.utils.logging import DevNull
from calibre.utils.resources import get_image_path

if TYPE_CHECKING:
    from unittest.suite import TestSuite
else:
    TestSuite = object

# The names the skeleton created by create_book() uses. The start page it
# writes is only a placeholder for a book the user is going to write
# themselves, so it is removed once the real chapters have been added.
OPF_NAME = 'metadata.opf'
PLACEHOLDER_NAME = 'start.xhtml'
CSS_NAME = 'styles/story.css'
PROLOGUE_NAME = 'text/prologue.xhtml'
CAST_NAME = 'text/dramatis-personae.xhtml'
DIVIDER_NAME = 'images/divider.png'
COVER_NAME = 'images/cover.jpg'
XHTML_MIME = 'application/xhtml+xml'

# The tag every exported story is given, so that the stories a player has
# exported are one click away from each other in their library. It is the
# name of the genre rather than a word of prose, so it is not translated: a
# library is often shared between machines running calibre in different
# languages and the books in it have to stay grouped.
CYOA_TAG = 'CYOA'

# The picture of a scene is capped by the height of the screen as well as by
# its width: a portrait picture scaled to the full width of a phone screen
# would otherwise push the prose it illustrates off the bottom of it, while
# on a desktop screen the same picture would be blown up far past the size it
# was generated at. The portraits of the characters stack above their
# description on a narrow screen and sit beside it on a screen with room for
# both. No colors are set anywhere, so that readers that invert the page for
# night reading keep the book legible.
EPUB_CSS = '''\
@namespace "http://www.w3.org/1999/xhtml";

body {
    margin: 0 5%;
    line-height: 1.5;
    text-align: justify;
    hyphens: auto;
    -epub-hyphens: auto;
}

h1 {
    font-size: 1.5em;
    font-weight: normal;
    text-align: center;
    margin: 1em 0 1.2em;
    page-break-after: avoid;
    break-after: avoid;
}

h2 {
    font-size: 1.1em;
    margin: 0 0 0.3em;
    page-break-after: avoid;
    break-after: avoid;
}

p {
    margin: 0;
    text-indent: 1.4em;
    orphans: 2;
    widows: 2;
}

/* The first line of a passage is not indented, only the lines that continue
   one already begun. */
h1 + p, h2 + p, .action + p, .scene + p, .divider + p, .portrait + p {
    text-indent: 0;
}

/* What the player typed or chose before the passage that answers it. */
.action {
    text-indent: 0;
    text-align: center;
    font-style: italic;
    margin: 1.4em auto 1em;
    max-width: 85%;
}

.scene, .divider {
    margin: 1.5em 0;
    text-align: center;
    page-break-inside: avoid;
    break-inside: avoid;
}

.scene img {
    width: auto;
    height: auto;
    max-width: 100%;
    max-height: 80vh;
}

.divider img {
    width: 35%;
    max-width: 12em;
}

.character {
    margin: 0 0 2em;
}

/* The portrait floats beside the description only when the screen is wide
   enough for the text next to it not to be a column of single words. */
.portrait {
    text-indent: 0;
    text-align: center;
    margin: 0 0 0.6em;
}

.portrait img {
    max-width: 60%;
    max-height: 45vh;
}

@media (min-width: 35em) {
    .portrait {
        float: left;
        width: 30%;
        margin: 0.2em 1.2em 0.6em 0;
    }

    .portrait img {
        max-width: 100%;
        max-height: none;
    }
}

/* So that the description of one character never wraps around the portrait
   of the next. */
.character:after {
    content: "";
    display: block;
    clear: both;
}

.role {
    text-indent: 0;
    font-style: italic;
    margin: 0 0 0.5em;
}
'''

XHTML_TEMPLATE = '''\
<?xml version='1.0' encoding='utf-8'?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{lang}" xml:lang="{lang}">
<head>
<meta charset="utf-8"/>
<title>{title}</title>
<link rel="stylesheet" type="text/css" href="{css}"/>
</head>
<body epub:type="{etype}">
{body}
</body>
</html>
'''


def username() -> str:
    # The name of the person playing, as the operating system knows them,
    # used as the author of the exported book. Same sources, in the same
    # order, as the name the single instance sockets are named after, see
    # calibre.utils.ipc.socket_address().
    ans = ''
    if iswindows:
        from calibre.constants import get_windows_username

        with suppress(Exception):
            ans = get_windows_username()
    ans = ans or os.environ.get('USER') or os.environ.get('USERNAME') or os.path.basename(os.path.expanduser('~'))
    return force_unicode(ans, filesystem_encoding).strip() or _('Unknown')


def markdown_to_html(text: str) -> str:
    # The prose the AI writes is markdown, as it is in the game window, see
    # calibre.gui2.cyoa.story_widgets.render_chapter().
    return response_to_html(text.strip(), ContentType.markdown) if text.strip() else ''


def image_for_epub(raw: bytes) -> tuple[bytes, str]:
    """Return (data, file extension) for raw, converted if needed.

    The pictures of the scenes are WebP, which is not one of the core media
    types every EPUB 3 reader must understand, so anything that is not
    already a core type is re-encoded: to PNG when it has transparency to
    preserve, which the portraits of the characters can have, and to JPEG
    otherwise, as the pictures are photographic and PNG would bloat the book.
    """
    from calibre.utils.imghdr import what

    fmt = (what(None, raw) or '').lower()
    if fmt in ('jpeg', 'jpg'):
        return raw, 'jpg'
    if fmt in ('png', 'gif'):
        return raw, fmt
    from calibre.utils.img import image_from_data, image_to_data

    img = image_from_data(raw)
    if img.hasAlphaChannel():
        return image_to_data(img, fmt='PNG'), 'png'
    return image_to_data(img, fmt='JPEG', compression_quality=90), 'jpg'


class BookBuilder:
    # Collects the pieces of the book as they are generated and puts them
    # into the container. The links between the files are all resolved by the
    # container, so that the layout of the book is described in exactly one
    # place, by the name constants at the top of this module.

    def __init__(self, container: EpubContainer, lang: str) -> None:
        self.container = container
        self.lang = lang
        self.spine: list[str] = []
        self.toc = TOC()
        self.image_names: dict[str, str] = {}  # cache key -> name in the container

    def href(self, target: str, base: str) -> str:
        return self.container.name_to_href(target, base)

    def add_page(self, name: str, title: str, body: str, etype: str = 'bodymatter') -> None:
        # The markdown converter and the fragments built here emit HTML, not
        # XHTML, so every page is parsed by the container's HTML 5 parser and
        # written back out by it, which is what makes the result well formed
        # XML rather than merely well intentioned.
        html = XHTML_TEMPLATE.format(lang=escape(self.lang, True), title=escape(title), css=escape(self.href(CSS_NAME, name), True), etype=etype, body=body)
        self.container.add_file(name, html.encode('utf-8'), media_type=XHTML_MIME)
        root = self.container.parsed(name)
        pretty_html_tree(self.container, root)
        self.container.dirty(name)
        self.spine.append(name)
        self.toc.add(title, name)

    def add_image(self, key: str, raw: bytes, name_stem: str) -> str:
        """The name of the picture raw in the container, adding it if needed.

        key identifies the picture for the caller, so that the same picture
        used twice is stored once. Returns the empty string when the data is
        not an image calibre can read, as a picture that cannot be decoded
        must not cost the player the whole book.
        """
        if (existing := self.image_names.get(key)) is not None:
            return existing
        try:
            data, ext = image_for_epub(raw)
        except Exception:
            self.image_names[key] = ''
            return ''
        name = self.container.add_file(f'{name_stem}.{ext}', data, modify_name_if_needed=True)
        self.image_names[key] = name
        return name

    def divider_name(self) -> str:
        # The ornament drawn between the turns of a chapter, the same one the
        # game window draws, put into the book the first time it is needed.
        if (existing := self.image_names.get('divider')) is not None:
            return existing
        with suppress(OSError):
            with open(get_image_path('scene-divider.png'), 'rb') as f:
                return self.add_image('divider', f.read(), DIVIDER_NAME.rpartition('.')[0])
        self.image_names['divider'] = ''
        return ''

    def img_tag(self, image_name: str, base: str, alt: str, cls: str) -> str:
        return f'<div class="{cls}"><img src="{escape(self.href(image_name, base), True)}" alt="{escape(alt, True)}"/></div>'


def cast_of(state: GameState) -> Iterator[tuple[CharacterState, bool]]:
    # Everybody in the story, as (character, is the player), the played
    # character first. The cast comes from the running summary rather than
    # from the world so that characters the AI introduced as the story went
    # on are in it too, and because the summary keys them by the stable ids
    # their portraits are stored under. For a game in which no turn has been
    # played yet the summary is the one the game starts from, which holds the
    # played character and the characters generated with the world.
    characters = state.current_summary.characters
    for c in characters:
        if c.id == PROTAGONIST_ID:
            yield c, True
    for c in characters:
        if c.id != PROTAGONIST_ID:
            yield c, False


def prologue_body(state: GameState) -> str:
    return f'<h1>{escape(_("Prologue"))}</h1>\n{markdown_to_html(state.world.world_description)}'


def cast_body(b: BookBuilder, state: GameState, portraits: Mapping[str, Mapping[str, str]]) -> str:
    # The empty string when the story has nobody in it, so that the book does
    # not get a dramatis personae with nobody on the bill.
    from calibre import sanitize_file_name

    parts: list[str] = []
    for character, is_player in cast_of(state):
        if not character.name.strip():
            continue
        parts.append('<div class="character">')
        parts.append(f'<h2>{escape(character.name)}</h2>')
        if is_player:
            parts.append(f'<p class="role">{escape(_("The character you play"))}</p>')
        # The portrait has to come before the description in the source for
        # it to float beside it, see EPUB_CSS.
        if (portrait := portraits.get(character.id)) is not None:
            with suppress(Exception):
                raw = standard_b64decode(portrait['data'])
                # The ids are invented by the AI, so they are not necessarily
                # usable as a file name as they stand.
                stem = sanitize_file_name(character.id) or 'unknown'
                if name := b.add_image(f'portrait:{character.id}', raw, f'images/portrait-{stem}'):
                    parts.append(b.img_tag(name, CAST_NAME, _('Portrait of {}').format(character.name), 'portrait'))
        parts.append(markdown_to_html(character.description))
        parts.append('</div>')
    if not parts:
        return ''
    return f'<h1>{escape(_("Dramatis personae"))}</h1>\n' + '\n'.join(parts)


def chapter_body(b: BookBuilder, state: GameState, chapter: int, name: str, images: Mapping[int, bytes]) -> str:
    parts = [f'<h1>{escape(state.chapter_titles[chapter])}</h1>']
    turns = [(i + 1, t) for i, t in enumerate(state.turns) if t.chapter == chapter]
    # The divider is only worth putting into the book at all when the chapter
    # has more than one turn for it to separate.
    divider = b.divider_name() if len(turns) > 1 else ''
    for pos, (turn_number, t) in enumerate(turns):
        if pos and divider:
            parts.append(b.img_tag(divider, name, '', 'divider'))
        if t.player_input:
            parts.append(f'<p class="action">➤ {escape(t.player_input)}</p>')
        parts.append(markdown_to_html(t.turn.narrative))
        if raw := images.get(turn_number):
            if image_name := b.add_image(f'scene:{turn_number}', raw, f'images/scene-{turn_number:03d}'):
                # The description of the scene is what the picture was drawn
                # from, which makes it exactly the alternate text for it.
                parts.append(b.img_tag(image_name, name, t.turn.scene_description, 'scene'))
    return '\n'.join(parts)


def book_metadata(state: GameState) -> tuple[Metadata, str]:
    # Returns the metadata of the book and the language its files are tagged
    # with, which is the language calibre is running in: the AI is asked to
    # write in it, see calibre.ai.cyoa.prose_contract().
    lang = canonicalize_lang(get_lang()) or 'eng'
    author = username()
    mi = Metadata(state.world.title.strip() or _('An adventure'), authors=[author])
    mi.author_sort = author
    mi.comments = state.world.world_description
    mi.languages = [lang]
    mi.tags = [CYOA_TAG]
    return mi, lang_as_iso639_1(lang) or lang


def add_cover(container: EpubContainer, mi: Metadata) -> None:
    # A book with no cover is a grey rectangle in every library and on every
    # reader, so one is drawn from the title and the author with the same
    # machinery as the "Generate cover" command in the library and the
    # editor, which means it follows whatever cover style the player has
    # chosen there. The imports are deferred because calibre.ebooks.covers
    # needs Qt and pulls in calibre.gui2 for it, which this module must not
    # do at import time, see the note at the top.
    from calibre.ebooks.covers import generate_cover
    from calibre.ebooks.oeb.polish.cover import set_cover

    name = container.add_file(COVER_NAME, generate_cover(mi), modify_name_if_needed=True)
    # As well as marking the picture as the cover of the book, for the
    # library and the reader to show, this wraps it in a title page and puts
    # that at the start of the spine, so that the cover is also the first
    # page of the book when it is opened. The aspect ratio of the picture is
    # preserved, as a generated cover stretched to the shape of the screen
    # would have its lettering distorted.
    set_cover(container, name, options={'existing_image': True, 'keep_aspect': True})


def story_to_epub(
    state: GameState,
    path: str,
    images: Mapping[int, bytes] | None = None,
    portraits: Mapping[str, Mapping[str, str]] | None = None,
) -> str:
    """Write the story of state to path as an EPUB 3 book and return path.

    images maps the one based number of a turn to the picture of its scene
    and portraits maps the stable id of a character to their portrait in the
    form games store them in, see calibre.gui2.cyoa.data.save_game().
    """
    images = images or {}
    portraits = portraits or {}
    mi, lang = book_metadata(state)
    # There is no code to create an EPUB 3 from nothing, so the book starts
    # life as the EPUB 2 skeleton the "Add an empty book" and editor commands
    # use and is upgraded in place, which also gives it its nav document.
    create_book(mi, path, fmt='epub', opf_name=OPF_NAME, html_name=PLACEHOLDER_NAME)
    container = get_container(path, log=DevNull())
    assert isinstance(container, EpubContainer)
    upgrade_book(container, lambda *a: None)

    container.add_file(CSS_NAME, EPUB_CSS.encode('utf-8'), media_type='text/css')
    b = BookBuilder(container, lang)
    b.add_page(PROLOGUE_NAME, _('Prologue'), prologue_body(state), etype='prologue')
    if body := cast_body(b, state, portraits):
        b.add_page(CAST_NAME, _('Dramatis personae'), body, etype='frontmatter')
    first_chapter = ''
    for chapter, title in enumerate(state.chapter_titles):
        name = f'text/chapter-{chapter + 1:03d}.xhtml'
        b.add_page(name, title, chapter_body(b, state, chapter, name, images), etype='chapter')
        first_chapter = first_chapter or name

    container.remove_item(PLACEHOLDER_NAME)
    container.set_spine([(name, True) for name in b.spine])
    # The cover is added after the spine has been set, as setting the spine
    # replaces it wholesale and would throw away the title page.
    add_cover(container, mi)
    # The prologue is where the book begins and the first chapter is where
    # the story proper does, which is where a reader offering to jump to the
    # start of the book should land.
    landmarks = [{'type': 'frontmatter', 'dest': PROLOGUE_NAME, 'frag': '', 'title': _('Prologue')}]
    if first_chapter:
        landmarks.append({'type': 'bodymatter', 'dest': first_chapter, 'frag': '', 'title': _('Start of the story')})
    commit_nav_toc(container, b.toc, lang=lang, landmarks=landmarks)
    container.commit(path)
    return path


def find_tests() -> TestSuite:  # {{{
    import tempfile
    import unittest

    from calibre.ai.cyoa import GeneratedWorld, NonPlayerCharacter, PlayerCharacter, StoryTurn, SummaryUpdate, TurnRecord, initial_summary, start_game

    def make_state(num_turns: int = 5) -> GameState:
        pc = PlayerCharacter('Ada', 'a *stubborn* engineer', 'She built the mist engines.')
        world = GeneratedWorld(
            title='Mist City',
            world_description='A city lost in **perpetual** mist.',
            characters=(pc,),
            npcs=(NonPlayerCharacter('Marlo', 'a mist-runner', 'He grew up in the tunnels.', 'wary of Ada'),),
        )
        state = start_game('a foggy city', world)
        for i in range(num_turns):
            new_chapter = bool(i) and i % 3 == 0
            turn = StoryTurn(
                narrative=f'Turn {i + 1}: the mist *swirls*.',
                quick_actions=(),
                scene_description='A foggy city street at night.',
                summary_update=SummaryUpdate(current_situation='In the mist.', character_updates=(), new_major_events=()),
                starts_new_chapter=new_chapter,
                chapter_title=f'Chapter about turn {i + 1}' if new_chapter else None,
            )
            state.turns.append(
                TurnRecord(player_input=f'Take step {i + 1}' if i else '', raw_response='', turn=turn, summary=initial_summary(world, pc), chapter=i // 3)
            )
        return state

    def make_image(fmt: str = 'WEBP') -> bytes:
        from qt.core import QColor, QImage

        from calibre.utils.img import image_to_data

        img = QImage(64, 48, QImage.Format.Format_RGB32)
        img.fill(QColor('red'))
        return image_to_data(img, fmt=fmt)

    # The name of the page wrapping the cover picture is chosen by
    # set_cover(), not by this module, so it is spelled out only here.
    TITLEPAGE_NAME = 'text/titlepage.xhtml'

    class TestCYOAEpub(unittest.TestCase):
        ae = unittest.TestCase.assertEqual

        def export(self, state: GameState, tdir: str, **kw: object) -> EpubContainer:
            path = os.path.join(tdir, 'book.epub')
            story_to_epub(state, path, **kw)  # ty: ignore[invalid-argument-type]
            ans = get_container(path, log=DevNull())
            assert isinstance(ans, EpubContainer)
            return ans

        def test_cyoa_epub_structure(self) -> None:
            state = make_state()
            with tempfile.TemporaryDirectory() as tdir:
                c = self.export(state, tdir)
                # An EPUB 3 with a nav document and no leftover EPUB 2 bits
                self.ae('3.0', c.opf_version)
                self.ae(1, len(tuple(c.manifest_items_with_property('nav'))))
                self.assertFalse([n for n in c.name_path_map if n.endswith('.ncx')])
                self.assertFalse(c.exists(PLACEHOLDER_NAME))
                # One file per chapter, after the cover, the prologue and the cast
                self.ae(2, len(state.chapter_titles))
                self.ae([TITLEPAGE_NAME, PROLOGUE_NAME, CAST_NAME, 'text/chapter-001.xhtml', 'text/chapter-002.xhtml'], [n for n, linear in c.spine_names])
                # Every spine item is in the table of contents, in order
                nav = c.raw_data([n for n in c.name_path_map if n.endswith('nav.xhtml')][0])
                for title in (_('Prologue'), _('Dramatis personae'), *state.chapter_titles):
                    self.assertIn(escape(title), nav)

        def test_cyoa_epub_landmarks(self) -> None:
            from calibre.ebooks.oeb.polish.toc import get_landmarks

            state = make_state()
            with tempfile.TemporaryDirectory() as tdir:
                c = self.export(state, tdir)
                self.ae(
                    [
                        {'dest': PROLOGUE_NAME, 'frag': '', 'type': 'frontmatter', 'title': _('Prologue')},
                        {'dest': 'text/chapter-001.xhtml', 'frag': '', 'type': 'bodymatter', 'title': _('Start of the story')},
                    ],
                    get_landmarks(c),
                )

        def test_cyoa_epub_content(self) -> None:
            state = make_state()
            with tempfile.TemporaryDirectory() as tdir:
                c = self.export(state, tdir)
                prologue = c.raw_data(PROLOGUE_NAME)
                self.assertIn('<b>perpetual</b>', prologue.replace('<strong>', '<b>').replace('</strong>', '</b>'))
                cast = c.raw_data(CAST_NAME)
                for name in ('Ada', 'Marlo'):
                    self.assertIn(name, cast)
                self.assertIn(_('The character you play'), cast)
                chapter = c.raw_data('text/chapter-001.xhtml')
                self.assertIn('Turn 1: the mist', chapter)
                self.assertIn('Take step 2', chapter)  # the action that led to the second turn
                # The divider separates the turns of a chapter, so a chapter
                # of three turns has two of them
                self.ae(2, chapter.count('class="divider"'))

        def test_cyoa_epub_images(self) -> None:
            state = make_state()
            webp, png = make_image(), make_image('PNG')
            with tempfile.TemporaryDirectory() as tdir:
                c = self.export(state, tdir, images={1: webp, 3: webp}, portraits={PROTAGONIST_ID: {'mime': 'image/png', 'data': 'not base64 at all'}})
                # WebP is not an EPUB 3 core media type, so it is converted
                self.assertFalse([n for n in c.name_path_map if n.endswith('.webp')])
                self.ae(['images/scene-001.jpg', 'images/scene-003.jpg'], sorted(n for n in c.name_path_map if n.startswith('images/scene-')))
                self.assertIn('images/scene-001.jpg', c.raw_data('text/chapter-001.xhtml'))
                # An unusable portrait costs its picture, not the book
                self.assertFalse([n for n in c.name_path_map if n.startswith('images/portrait-')])
            with tempfile.TemporaryDirectory() as tdir:
                from base64 import standard_b64encode

                portraits = {PROTAGONIST_ID: {'mime': 'image/png', 'data': standard_b64encode(png).decode('ascii')}}
                c = self.export(state, tdir, portraits=portraits)
                self.ae(['images/portrait-protagonist.png'], [n for n in c.name_path_map if n.startswith('images/portrait-')])
                self.assertIn('images/portrait-protagonist.png', c.raw_data(CAST_NAME))

        def test_cyoa_epub_metadata(self) -> None:
            state = make_state()
            with tempfile.TemporaryDirectory() as tdir:
                c = self.export(state, tdir)
                mi = c.mi
                self.ae('Mist City', mi.title)
                self.ae([username()], list(mi.authors))
                self.ae(state.world.world_description, mi.comments)
                self.ae([CYOA_TAG], list(mi.tags))

        def test_cyoa_epub_cover(self) -> None:
            from calibre.ebooks.oeb.polish.cover import find_cover_image, find_cover_page

            state = make_state()
            with tempfile.TemporaryDirectory() as tdir:
                c = self.export(state, tdir)
                # The generated cover is in the book, marked as its cover and
                # wrapped in the page the book opens with
                self.ae(COVER_NAME, find_cover_image(c, strict=True))
                self.ae(TITLEPAGE_NAME, find_cover_page(c))
                self.assertIn(COVER_NAME, c.raw_data(TITLEPAGE_NAME))
                self.assertTrue(c.raw_data(COVER_NAME, decode=False))

        def test_cyoa_epub_no_turns(self) -> None:
            # A game the player has not yet played a turn of still makes a
            # book: the world and the cast it starts with
            state = make_state(0)
            with tempfile.TemporaryDirectory() as tdir:
                c = self.export(state, tdir)
                self.ae([TITLEPAGE_NAME, PROLOGUE_NAME, CAST_NAME], [n for n, linear in c.spine_names])
                self.assertIn('Marlo', c.raw_data(CAST_NAME))

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestCYOAEpub)


# }}}


if __name__ == '__main__':
    import sys

    from calibre.gui2.cyoa import data

    game_id = sys.argv[1] if len(sys.argv) > 1 else data.current_game_id()
    state, images, portraits = data.load_game(game_id)
    out = story_to_epub(state, os.path.abspath('cyoa.epub'), {k: v.data for k, v in images.items() if v.data}, portraits)
    print('Wrote', out)
