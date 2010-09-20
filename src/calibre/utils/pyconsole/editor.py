#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, textwrap

from PyQt4.Qt import QTextEdit, Qt, QTextFrameFormat

from pygments.lexers import PythonLexer, PythonTracebackLexer

from calibre.constants import __appname__, __version__
from calibre.utils.pyconsole.formatter import Formatter
from calibre.utils.pyconsole.repl import Interpreter, DummyFile
from calibre.utils.pyconsole import prints

class EditBlock(object): # {{{

    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        self.cursor.beginEditBlock()
        return self.cursor

    def __exit__(self, *args):
        self.cursor.endEditBlock()
# }}}

class Editor(QTextEdit):

    @property
    def doc(self):
        return self.document()

    @property
    def cursor(self):
        return self.textCursor()

    @property
    def root_frame(self):
        return self.doc.rootFrame()

    @property
    def cursor_pos(self):
        pass
        #pos = self.cursor.position() - self.prompt_frame.firstPosition()
        #i = 0
        #for line in self.current_prompt:
        #    i += self.prompt_len

    def __init__(self,
            prompt='>>> ',
            continuation='... ',
            parent=None):
        QTextEdit.__init__(self, parent)
        self.buf = ''
        self.prompt_frame = None
        self.current_prompt = ['']
        self.allow_output = False
        self.prompt_frame_format = QTextFrameFormat()
        self.prompt_frame_format.setBorder(1)
        self.prompt_frame_format.setBorderStyle(QTextFrameFormat.BorderStyle_Solid)
        self.prompt_len = len(prompt)

        self.doc.setMaximumBlockCount(10000)
        self.lexer = PythonLexer(ensurenl=False)
        self.tb_lexer = PythonTracebackLexer()
        self.formatter = Formatter(prompt, continuation)

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

        #it = self.prompt_frame.begin()
        #while not it.atEnd():
        #    bl = it.currentBlock()
        #    prints(repr(bl.text()))
        #    it += 1


    # Rendering {{{

    def render_block(self, text, restore_prompt=True):
        self.formatter.render(self.lexer.get_tokens(text), self.cursor)
        self.cursor.insertBlock()
        self.cursor.movePosition(self.cursor.End)
        if restore_prompt:
            self.render_current_prompt()

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

    def render_current_prompt(self):
        self.clear_current_prompt()

        for i, line in enumerate(self.current_prompt):
            start = i == 0
            end = i == len(self.current_prompt) - 1
            self.formatter.render_prompt(not start, self.cursor)
            self.formatter.render(self.lexer.get_tokens(line), self.cursor)
            if not end:
                self.cursor.insertText('\n')

    def show_error(self, is_syntax_err, tb):
        if self.prompt_frame is not None:
            # At a prompt, so redirect output
            return prints(tb)
        try:
            self.buf += tb
            if is_syntax_err:
                self.formatter.render_syntax_error(tb, self.cursor)
            else:
                self.formatter.render(self.tb_lexer.get_tokens(tb), self.cursor)
        except:
            prints(tb)

    def show_output(self, raw):
        if self.prompt_frame is not None:
            # At a prompt, so redirect output
            return prints(raw)
        try:
            self.current_prompt_range = None
            self.buf += raw
            self.formatter.render_raw(raw, self.cursor)
        except:
            prints(raw)

    # }}}

    # Keyboard handling {{{

    def keyPressEvent(self, ev):
        text = unicode(ev.text())
        key = ev.key()
        if key in (Qt.Key_Enter, Qt.Key_Return):
            self.enter_pressed()
        elif key == Qt.Key_Home:
             self.home_pressed()
        elif key == Qt.Key_End:
            self.end_pressed()
        elif key == Qt.Key_Left:
            self.left_pressed()
        elif key == Qt.Key_Right:
            self.right_pressed()
        elif text:
            self.text_typed(text)
        else:
            QTextEdit.keyPressEvent(self, ev)

    def left_pressed(self):
        pass

    def right_pressed(self):
        if self.prompt_frame is not None:
            c = self.cursor
            c.movePosition(c.NextCharacter)
            self.setTextCursor(c)

    def home_pressed(self):
        if self.prompt_frame is not None:
            c = self.cursor
            c.movePosition(c.StartOfLine)
            c.movePosition(c.NextCharacter, n=self.prompt_len)
            self.setTextCursor(c)

    def end_pressed(self):
        if self.prompt_frame is not None:
            c = self.cursor
            c.movePosition(c.EndOfLine)
            self.setTextCursor(c)

    def enter_pressed(self):
        if self.prompt_frame is None:
            return
        if self.current_prompt[0]:
            c = self.root_frame.lastCursorPosition()
            self.setTextCursor(c)
            old_pf = self.prompt_frame
            self.prompt_frame = None
            oldbuf = self.buf
            self.buf = ''
            ret = self.interpreter.runsource('\n'.join(self.current_prompt))
            if ret: # Incomplete command
                self.buf = oldbuf
                self.prompt_frame = old_pf
                self.current_prompt.append('')
            else: # Command completed
                self.current_prompt = ['']
                old_pf.setFrameFormat(QTextFrameFormat())
            self.render_current_prompt()

    def text_typed(self, text):
        if not self.current_prompt[0]:
            self.cursor.beginEditBlock()
        else:
            self.cursor.joinPreviousEditBlock()
        self.current_prompt[-1] += text
        self.render_current_prompt()
        self.cursor.endEditBlock()


    # }}}


