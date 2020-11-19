#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>


import re
from itertools import count
from PyQt5.Qt import (
    QDialogButtonBox, QLabel, QMainWindow, Qt, QVBoxLayout, QWidget, pyqtSignal
)

from calibre import prepare_string_for_xml
from calibre.gui2 import Application

from .common import EventType
from .implementation import Client


def add_markup(text):
    buf = []
    first = True
    counter = count()
    pos_map = {}
    last = None
    for m in re.finditer(r'\w+', text):
        start, end = m.start(), m.end()
        if first:
            first = False
            if start:
                buf.append(prepare_string_for_xml(text[:start]))
        num = next(counter)
        buf.append(f'<mark name="{num}"/>')
        pos_map[num] = start, end
        buf.append(prepare_string_for_xml(m.group()))
        last = end
    if last is None:
        buf.append(prepare_string_for_xml(text))
    else:
        buf.append(prepare_string_for_xml(text[last:]))
    return ''.join(buf), pos_map


class TTS(QWidget):

    mark_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.mark_changed.connect(self.on_mark_change)
        self.tts = Client()
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(self)
        la.setTextFormat(Qt.RichText)
        la.setWordWrap(True)
        self.text = '''\
In their duty through weakness of will, which is the
same as saying through shrinking from toil and pain. These cases are
perfectly simple and easy to distinguish. In a free hour, when our
power of choice is untrammelled and when nothing prevents our being
able to do what we like best, every pleasure is to be welcomed and
every pain avoided.

But in certain circumstances and owing to the claims of duty or the obligations
of business it will frequently occur that pleasures have to be repudiated and
annoyances accepted. The wise man therefore always holds in these matters to
this.

Born and I will give you a complete account of the system, and expound the
actual teachings of the great explorer of the truth, the master-builder of
human happiness. No one rejects, dislikes, or avoids pleasure itself, because
it is pleasure, but because those who do not know how to pursue pleasure
rationally encounter consequences that are extremely painful.

Nor again is there anyone who loves or pursues or desires to obtain pain of
itself, because it is pain, but because occasionally circumstances occur in
which toil and pain can procure him some great pleasure. To take a trivial
example, which of.
'''
        self.ssml, self.pos_map = add_markup(self.text)
        self.current_mark = None
        l.addWidget(la)
        self.bb = bb = QDialogButtonBox(self)
        self.play_button = b = bb.addButton('Play', bb.ActionRole)
        l.addWidget(bb)
        b.clicked.connect(self.play_clicked)
        self.render_text()

    def render_text(self):
        text = self.text
        if self.current_mark is not None:
            start, end = self.pos_map[self.current_mark]
            text = text[:end] + '</b>' + text[end:]
            text = text[:start] + '<b>' + text[start:]
        lines = ['<p>']
        for line in text.splitlines():
            if not line.strip():
                lines.append('<p>')
            else:
                lines.append(line)
        self.la.setText('\n'.join(lines))

    def play_clicked(self):
        self.tts.speak_marked_text(self.ssml, self.handle_event)

    def handle_event(self, event):
        if event.type is EventType.mark:
            try:
                mark = int(event.data)
            except Exception:
                return
            self.mark_changed.emit(mark)

    def on_mark_change(self, mark):
        self.current_mark = mark
        self.render_text()


def main():
    app = Application([])
    w = QMainWindow()
    tts = TTS(w)
    w.setCentralWidget(tts)
    w.show()
    app.exec_()
    del tts.tts


if __name__ == '__main__':
    main()
