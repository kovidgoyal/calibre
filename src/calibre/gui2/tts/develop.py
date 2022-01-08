#!/usr/bin/env python
# License: GPL v3 Copyright: 2020, Kovid Goyal <kovid at kovidgoyal.net>


import re
from itertools import count
from qt.core import (
    QDialogButtonBox, QLabel, QMainWindow, Qt, QTimer, QVBoxLayout, QWidget,
    pyqtSignal
)

from calibre.gui2 import Application

from .common import EventType
from .implementation import Client


def add_markup(text):
    buf = []
    first = True
    counter = count()
    pos_map = {}
    last = None
    bm = Client.mark_template
    for m in re.finditer(r'\w+', text):
        start, end = m.start(), m.end()
        if first:
            first = False
            if start:
                buf.append(Client.escape_marked_text(text[:start]))
        elif start > last:
            buf.append(Client.escape_marked_text(text[last:start]))
        num = next(counter)
        buf.append(bm.format(num))
        pos_map[num] = start, end
        buf.append(Client.escape_marked_text(m.group()))
        last = end
    if last is None:
        buf.append(Client.escape_marked_text(text))
    else:
        buf.append(Client.escape_marked_text(text[last:]))
    return ''.join(buf), pos_map


class TTSWidget(QWidget):

    dispatch_on_main_thread_signal = pyqtSignal(object)
    mark_changed = pyqtSignal(object)
    show_message = pyqtSignal(object)
    show_status = pyqtSignal(object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.mark_changed.connect(self.on_mark_change)
        self.dispatch_on_main_thread_signal.connect(self.dispatch_on_main_thread, type=Qt.ConnectionType.QueuedConnection)
        self.tts = Client({}, self.dispatch_on_main_thread_signal.emit)
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(self)
        la.setTextFormat(Qt.TextFormat.RichText)
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
        l.addWidget(bb)
        self.play_button = b = bb.addButton('Play', QDialogButtonBox.ButtonRole.ActionRole)
        b.clicked.connect(self.play_clicked)
        self.pause_button = b = bb.addButton('Pause', QDialogButtonBox.ButtonRole.ActionRole)
        b.clicked.connect(self.pause_clicked)
        self.resume_button = b = bb.addButton('Resume', QDialogButtonBox.ButtonRole.ActionRole)
        b.clicked.connect(self.resume_clicked)
        self.stop_button = b = bb.addButton('Stop', QDialogButtonBox.ButtonRole.ActionRole)
        b.clicked.connect(self.stop_clicked)
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

    def pause_clicked(self):
        self.tts.pause()

    def resume_clicked(self):
        self.tts.resume()

    def stop_clicked(self):
        self.tts.stop()

    def dispatch_on_main_thread(self, func):
        try:
            func()
        except Exception:
            import traceback
            traceback.print_exc()

    def handle_event(self, event):
        status = str(self.tts.status)
        self.show_status.emit(str(status))
        if event.type is EventType.mark:
            try:
                mark = int(event.data)
            except Exception:
                return
            self.mark_changed.emit(mark)
        else:
            self.show_message.emit(f'Got event: {event.type.name}')

    def on_mark_change(self, mark):
        self.current_mark = mark
        self.render_text()


def main():
    app = Application([])
    w = QMainWindow()
    sb = w.statusBar()
    la = QLabel(sb)
    sb.addPermanentWidget(la)
    tts = TTSWidget(w)
    tts.show_message.connect(sb.showMessage)
    tts.show_status.connect(la.setText)
    w.setCentralWidget(tts)
    w.show()
    app.exec()
    tts.dispatch_on_main_thread_signal.disconnect()
    tts.mark_changed.disconnect()
    tts.tts.shutdown()


def headless():
    app = Application([])
    c = Client()
    text = '[[sync 0x123456]]very [[sync 0x80]]good [[sync 0x81]]indeed'

    def callback():
        for ev in c.get_events():
            if ev.type is EventType.mark:
                print('mark:', hex(ev.data))
            if ev.type in (EventType.end, EventType.cancel):
                print(ev.type)
                app.quit()

    def run():
        c.speak_marked_text(text, callback)
    QTimer.singleShot(10, run)
    QTimer.singleShot(5000, app.quit)
    app.exec()


if __name__ == '__main__':
    main()
