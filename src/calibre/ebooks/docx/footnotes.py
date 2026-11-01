#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

from collections import OrderedDict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from lxml.etree import _Element

    from calibre.ebooks.docx.container import Relationships
    from calibre.ebooks.docx.names import DOCXNamespace


class Note:
    def __init__(self, namespace: DOCXNamespace, parent: _Element, rels: Relationships) -> None:
        self.type = namespace.get(parent, 'w:type', 'normal')
        self.parent = parent
        self.rels = rels
        self.namespace = namespace

    def __iter__(self) -> Iterator[_Element]:
        yield from self.namespace.descendants(self.parent, 'w:p', 'w:tbl')


class Footnotes:
    def __init__(self, namespace: DOCXNamespace) -> None:
        self.namespace = namespace
        self.footnotes: dict[str, Note] = {}
        self.endnotes: dict[str, Note] = {}
        self.counter = 0
        self.notes: OrderedDict[str, tuple[str, Note]] = OrderedDict()

    def __call__(self, footnotes: _Element | None, footnotes_rels: Relationships, endnotes: _Element | None, endnotes_rels: Relationships) -> None:
        XPath, get = self.namespace.XPath, self.namespace.get
        if footnotes is not None:
            for footnote in XPath('./w:footnote[@w:id]')(footnotes):
                fid = get(footnote, 'w:id')
                if fid:
                    self.footnotes[fid] = Note(self.namespace, footnote, footnotes_rels)

        if endnotes is not None:
            for endnote in XPath('./w:endnote[@w:id]')(endnotes):
                fid = get(endnote, 'w:id')
                if fid:
                    self.endnotes[fid] = Note(self.namespace, endnote, endnotes_rels)

    def get_ref(self, ref: _Element) -> tuple[str, str] | tuple[None, None]:
        fid = self.namespace.get(ref, 'w:id')
        tag = ref.tag
        assert isinstance(tag, str)  # ref is a w:footnoteReference or w:endnoteReference element
        notes = self.footnotes if tag.endswith('}footnoteReference') else self.endnotes
        note = notes.get(fid, None)
        if note is not None and note.type == 'normal':
            self.counter += 1
            anchor = f'note_{self.counter}'
            self.notes[anchor] = (str(self.counter), note)
            return anchor, str(self.counter)
        return None, None

    def __iter__(self) -> Iterator[tuple[str, str, Note]]:
        for anchor, (counter, note) in self.notes.items():
            yield anchor, counter, note

    @property
    def has_notes(self) -> bool:
        return bool(self.notes)
