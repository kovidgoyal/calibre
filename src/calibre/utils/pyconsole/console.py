#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, textwrap, traceback, StringIO

from PyQt4.Qt import QTextEdit, Qt, QTextFrameFormat, pyqtSignal, \
    QCoreApplication

from pygments.lexers import PythonLexer, PythonTracebackLexer

from calibre.constants import __appname__, __version__
from calibre.utils.pyconsole.formatter import Formatter
from calibre.utils.pyconsole.repl import Interpreter, DummyFile
from calibre.utils.pyconsole import prints
from calibre.gui2 import error_dialog

class EditBlock(object): # {{{

    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        self.cursor.beginEditBlock()
        return self.cursor

    def __exit__(self, *args):
        self.cursor.endEditBlock()
# }}}

class Prepender(object): # {{{
    'Helper class to insert output before the current prompt'
    def __init__(self, console):
        self.console = console

    def __enter__(self):
        c = self.console
        self.opos = c.cursor_pos
        cur = c.prompt_frame.firstCursorPosition()
        cur.movePosition(cur.PreviousCharacter)
        c.setTextCursor(cur)

    def __exit__(self, *args):
        self.console.cursor_pos = self.opos
# }}}


class Console(QTextEdit):

    running = pyqtSignal()
    running_done = pyqtSignal()

    @property
    def doc(self):
        return self.document()

    @property
    def cursor(self):
        return self.textCursor()

    @property
    def root_frame(self):
        return self.doc.rootFrame()

    def unhandled_exception(self, type, value, tb):
        if type == KeyboardInterrupt:
            return
        try:
            sio = StringIO.StringIO()
            traceback.print_exception(type, value, tb, file=sio)
            fe = sio.getvalue()
            prints(fe)
            try:
                val = unicode(value)
            except:
                val = repr(value)
            msg = '<b>%s</b>:'%type.__name__ + val
            error_dialog(self, _('ERROR: Unhandled exception'), msg,
                    det_msg=fe, show=True)
        except BaseException:
            pass

    def __init__(self,
            prompt='>>> ',
            continuation='... ',
            parent=None):
        QTextEdit.__init__(self, parent)
        self.buf = []
        self.prompt_frame = None
        self.allow_output = False
        self.prompt_frame_format = QTextFrameFormat()
        self.prompt_frame_format.setBorder(1)
        self.prompt_frame_format.setBorderStyle(QTextFrameFormat.BorderStyle_Solid)
        self.prompt_len = len(prompt)

        self.doc.setMaximumBlockCount(10000)
        self.lexer = PythonLexer(ensurenl=False)
        self.tb_lexer = PythonTracebackLexer()
        self.formatter = Formatter(prompt, continuation, style='default')
        self.setStyleSheet(self.formatter.stylesheet)

        self.key_dispatcher = { # {{{
                Qt.Key_Enter : self.enter_pressed,
                Qt.Key_Return : self.enter_pressed,
                Qt.Key_Home : self.home_pressed,
                Qt.Key_End : self.end_pressed,
                Qt.Key_Left : self.left_pressed,
                Qt.Key_Right : self.right_pressed,
        } # }}}

        motd = textwrap.dedent('''\
        # Python {0}
        # {1} {2}
        '''.format(sys.version.splitlines()[0], __appname__,
            __version__))

        with EditBlock(self.cursor):
            self.render_block(motd)

        sys.stdout = sys.stderr = DummyFile(parent=self)
        sys.stdout.write_output.connect(self.show_output)
        self.interpreter = Interpreter(parent=self)
        self.interpreter.show_error.connect(self.show_error)

        sys.excepthook = self.unhandled_exception


    # Prompt management {{{

    @dynamic_property
    def cursor_pos(self):
        doc = '''
        The cursor position in the prompt has the form (row, col).
        row starts at 0 for the first line
        col is 0 if the cursor is at the start of the line, 1 if it is after
        the first character, n if it is after the nth char.
        '''

        def fget(self):
            if self.prompt_frame is not None:
                pos = self.cursor.position()
                it = self.prompt_frame.begin()
                lineno = 0
                while not it.atEnd():
                    bl = it.currentBlock()
                    if bl.contains(pos):
                        return (lineno, pos - bl.position())
                    it += 1
                    lineno += 1
            return (-1, -1)

        def fset(self, val):
            row, col = val
            if self.prompt_frame is not None:
                it = self.prompt_frame.begin()
                lineno = 0
                while not it.atEnd():
                    if lineno == row:
                        c = self.cursor
                        c.setPosition(it.currentBlock().position())
                        c.movePosition(c.NextCharacter, n=col)
                        self.setTextCursor(c)
                        break
                    it += 1
                    lineno += 1

        return property(fget=fget, fset=fset, doc=doc)

    def prompt(self, strip_prompt_strings=True):
        if not self.prompt_frame:
            yield u'' if strip_prompt_strings else self.formatter.prompt
        else:
            it = self.prompt_frame.begin()
            while not it.atEnd():
                bl = it.currentBlock()
                t = unicode(bl.text())
                if strip_prompt_strings:
                    t = t[self.prompt_len:]
                yield t
                it += 1

    def set_prompt(self, lines):
        self.render_current_prompt(lines)

    def clear_current_prompt(self):
        if self.prompt_frame is None:
            c = self.root_frame.lastCursorPosition()
            self.prompt_frame = c.insertFrame(self.prompt_frame_format)
            self.setTextCursor(c)
        else:
            c = self.prompt_frame.firstCursorPosition()
            self.setTextCursor(c)
            c.setPosition(self.prompt_frame.lastPosition(), c.KeepAnchor)
            c.removeSelectedText()
            c.setPosition(self.prompt_frame.firstPosition())

    def render_current_prompt(self, lines=None, restore_cursor=False):
        row, col = self.cursor_pos
        cp = list(self.prompt()) if lines is None else lines
        self.clear_current_prompt()

        for i, line in enumerate(cp):
            start = i == 0
            end = i == len(cp) - 1
            self.formatter.render_prompt(not start, self.cursor)
            self.formatter.render(self.lexer.get_tokens(line), self.cursor)
            if not end:
                self.cursor.insertBlock()

        if row > -1 and restore_cursor:
            self.cursor_pos = (row, col)

        self.ensureCursorVisible()

    # }}}

    # Non-prompt Rendering {{{

    def render_block(self, text, restore_prompt=True):
        self.formatter.render(self.lexer.get_tokens(text), self.cursor)
        self.cursor.insertBlock()
        self.cursor.movePosition(self.cursor.End)
        if restore_prompt:
            self.render_current_prompt()

    def show_error(self, is_syntax_err, tb):
        if self.prompt_frame is not None:
            # At a prompt, so redirect output
            return prints(tb, end='')
        try:
            self.buf.append(tb)
            if is_syntax_err:
                self.formatter.render_syntax_error(tb, self.cursor)
            else:
                self.formatter.render(self.tb_lexer.get_tokens(tb), self.cursor)
        except:
            prints(tb, end='')
        self.ensureCursorVisible()
        QCoreApplication.processEvents()

    def show_output(self, raw):
        def do_show():
            try:
                self.buf.append(raw)
                self.formatter.render_raw(raw, self.cursor)
            except:
                import traceback
                prints(traceback.format_exc())
                prints(raw, end='')

        if self.prompt_frame is not None:
            with Prepender(self):
                do_show()
        else:
            do_show()
        self.ensureCursorVisible()
        QCoreApplication.processEvents()

    # }}}

    # Keyboard handling {{{

    def keyPressEvent(self, ev):
        text = unicode(ev.text())
        key = ev.key()
        action = self.key_dispatcher.get(key, None)
        if callable(action):
            action()
        elif key in (Qt.Key_Escape,):
            QTextEdit.keyPressEvent(self, ev)
        elif text:
            self.text_typed(text)
        else:
            QTextEdit.keyPressEvent(self, ev)

    def left_pressed(self):
        lineno, pos = self.cursor_pos
        if lineno < 0: return
        if pos > self.prompt_len:
            c = self.cursor
            c.movePosition(c.PreviousCharacter)
            self.setTextCursor(c)
        elif lineno > 0:
            c = self.cursor
            c.movePosition(c.Up)
            c.movePosition(c.EndOfLine)
            self.setTextCursor(c)
        self.ensureCursorVisible()

    def right_pressed(self):
        lineno, pos = self.cursor_pos
        if lineno < 0: return
        c = self.cursor
        lineno, pos = self.cursor_pos
        cp = list(self.prompt(False))
        if pos < len(cp[lineno]):
            c.movePosition(c.NextCharacter)
        elif lineno < len(cp)-1:
            c.movePosition(c.NextCharacter, n=1+self.prompt_len)
        self.setTextCursor(c)
        self.ensureCursorVisible()

    def home_pressed(self):
        if self.prompt_frame is not None:
            c = self.cursor
            c.movePosition(c.StartOfLine)
            c.movePosition(c.NextCharacter, n=self.prompt_len)
            self.setTextCursor(c)
            self.ensureCursorVisible()

    def end_pressed(self):
        if self.prompt_frame is not None:
            c = self.cursor
            c.movePosition(c.EndOfLine)
            self.setTextCursor(c)
            self.ensureCursorVisible()

    def enter_pressed(self):
        if self.prompt_frame is None:
            return
        cp = list(self.prompt())
        if cp[0]:
            c = self.root_frame.lastCursorPosition()
            self.setTextCursor(c)
            old_pf = self.prompt_frame
            self.prompt_frame = None
            oldbuf = self.buf
            self.buf = []
            self.running.emit()
            try:
                ret = self.interpreter.runsource('\n'.join(cp))
            except SystemExit:
                ret = False
                self.show_output('Raising SystemExit not allowed\n')
            self.running_done.emit()
            if ret: # Incomplete command
                self.buf = oldbuf
                self.prompt_frame = old_pf
                c = old_pf.lastCursorPosition()
                c.insertBlock()
                self.setTextCursor(c)
            else: # Command completed
                try:
                    old_pf.setFrameFormat(QTextFrameFormat())
                except RuntimeError:
                    # Happens if enough lines of output that the old
                    # frame was deleted
                    pass

            self.render_current_prompt()

    def text_typed(self, text):
        if self.prompt_frame is not None:
            self.cursor.insertText(text)
            self.render_current_prompt(restore_cursor=True)

    # }}}


