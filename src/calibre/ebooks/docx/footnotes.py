#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import OrderedDict
from polyglot.builtins import iteritems


class Note:

    def __init__(self, namespace, parent, rels):
        self.type = namespace.get(parent, 'w:type', 'normal')
        self.parent = parent
        self.rels = rels
        self.namespace = namespace

    def __iter__(self):
        yield from self.namespace.descendants(self.parent, 'w:p', 'w:tbl')


class Footnotes:

    def __init__(self, namespace):
        self.namespace = namespace
        self.footnotes = {}
        self.endnotes = {}
        self.counter = 0
        self.notes = OrderedDict()

    def __call__(self, footnotes, footnotes_rels, endnotes, endnotes_rels):
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

    def get_ref(self, ref):
        fid = self.namespace.get(ref, 'w:id')
        notes = self.footnotes if ref.tag.endswith('}footnoteReference') else self.endnotes
        note = notes.get(fid, None)
        if note is not None and note.type == 'normal':
            self.counter += 1
            anchor = 'note_%d' % self.counter
            self.notes[anchor] = (str(self.counter), note)
            return anchor, str(self.counter)
        return None, None

    def __iter__(self):
        for anchor, (counter, note) in iteritems(self.notes):
            yield anchor, counter, note

    @property
    def has_notes(self):
        return bool(self.notes)
