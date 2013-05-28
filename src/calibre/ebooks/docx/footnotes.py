#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from collections import OrderedDict

from calibre.ebooks.docx.names import get, XPath, descendants

class Note(object):

    def __init__(self, parent):
        self.type = get(parent, 'w:type', 'normal')
        self.parent = parent

    def __iter__(self):
        for p in descendants(self.parent, 'w:p', 'w:tbl'):
            yield p

class Footnotes(object):

    def __init__(self):
        self.footnotes = {}
        self.endnotes = {}
        self.counter = 0
        self.notes = OrderedDict()

    def __call__(self, footnotes, endnotes):
        if footnotes is not None:
            for footnote in XPath('./w:footnote[@w:id]')(footnotes):
                fid = get(footnote, 'w:id')
                if fid:
                    self.footnotes[fid] = Note(footnote)

        if endnotes is not None:
            for endnote in XPath('./w:endnote[@w:id]')(endnotes):
                fid = get(endnote, 'w:id')
                if fid:
                    self.endnotes[fid] = Note(endnote)

    def get_ref(self, ref):
        fid = get(ref, 'w:id')
        notes = self.footnotes if ref.tag.endswith('}footnoteReference') else self.endnotes
        note = notes.get(fid, None)
        if note is not None and note.type == 'normal':
            self.counter += 1
            anchor = 'note_%d' % self.counter
            self.notes[anchor] = (type('')(self.counter), note)
            return anchor, type('')(self.counter)
        return None, None

    def __iter__(self):
        for anchor, (counter, note) in self.notes.iteritems():
            yield anchor, counter, note

    @property
    def has_notes(self):
        return bool(self.notes)

