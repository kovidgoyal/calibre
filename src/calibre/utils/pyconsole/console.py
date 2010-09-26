#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, textwrap, traceback, StringIO
from functools import partial
from codeop import CommandCompiler

from PyQt4.Qt import QTextEdit, Qt, QTextFrameFormat, pyqtSignal, \
    QApplication, QColor, QPalette, QMenu, QActionGroup, QTimer

from pygments.lexers import PythonLexer, PythonTracebackLexer
from pygments.styles import get_all_styles

from calibre.utils.pyconsole.formatter import Formatter
from calibre.utils.pyconsole.controller import Controller
from calibre.utils.pyconsole.history import History
from calibre.utils.pyconsole import prints, prefs, __appname__, \
        __version__, error_dialog, dynamic

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

class ThemeMenu(QMenu): # {{{

    def __init__(self, parent):
        QMenu.__init__(self, _('Choose theme (needs restart)'))
        parent.addMenu(self)
        self.group = QActionGroup(self)
        current = prefs['theme']
        alls = list(sorted(get_all_styles()))
        if current not in alls:
            current = prefs['theme'] = 'default'
        self.actions = []
        for style in alls:
            ac = self.group.addAction(style)
            ac.setCheckable(True)
            if current == style:
                ac.setChecked(True)
            self.actions.append(ac)
            ac.triggered.connect(partial(self.set_theme, style))
            self.addAction(ac)

    def set_theme(self, style, *args):
        prefs['theme'] = style

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
        self.shutting_down = False
        self.compiler = CommandCompiler()
        self.buf = self.old_buf = []
        self.history = History([''], dynamic.get('console_history', []))
        self.prompt_frame = None
        self.allow_output = False
        self.prompt_frame_format = QTextFrameFormat()
        self.prompt_frame_format.setBorder(1)
        self.prompt_frame_format.setBorderStyle(QTextFrameFormat.BorderStyle_Solid)
        self.prompt_len = len(prompt)

        self.doc.setMaximumBlockCount(int(prefs['scrollback']))
        self.lexer = PythonLexer(ensurenl=False)
        self.tb_lexer = PythonTracebackLexer()

        self.context_menu = cm = QMenu(self) # {{{
        cm.theme = ThemeMenu(cm)
        # }}}

        self.formatter = Formatter(prompt, continuation, style=prefs['theme'])
        p = QPalette()
        p.setColor(p.Base, QColor(self.formatter.background_color))
        p.setColor(p.Text, QColor(self.formatter.color))
        self.setPalette(p)

        self.key_dispatcher = { # {{{
                Qt.Key_Enter : self.enter_pressed,
                Qt.Key_Return : self.enter_pressed,
                Qt.Key_Up : self.up_pressed,
                Qt.Key_Down : self.down_pressed,
                Qt.Key_Home : self.home_pressed,
                Qt.Key_End : self.end_pressed,
                Qt.Key_Left : self.left_pressed,
                Qt.Key_Right : self.right_pressed,
                Qt.Key_Backspace : self.backspace_pressed,
                Qt.Key_Delete : self.delete_pressed,
        } # }}}

        motd = textwrap.dedent('''\
        # Python {0}
        # {1} {2}
        '''.format(sys.version.splitlines()[0], __appname__,
            __version__))

        sys.excepthook = self.unhandled_exception

        self.controllers = []
        QTimer.singleShot(0, self.launch_controller)


        with EditBlock(self.cursor):
            self.render_block(motd)

    def shutdown(self):
        dynamic.set('console_history', self.history.serialize())
        self.shutting_down = True
        for c in self.controllers:
            c.kill()

    def contextMenuEvent(self, event):
        self.context_menu.popup(event.globalPos())
        event.accept()

    # Controller management {{{
    @property
    def controller(self):
        return self.controllers[-1]

    def no_controller_error(self):
        error_dialog(self, _('No interpreter'),
                _('No active interpreter found. Try restarting the'
                    ' console'), show=True)

    def launch_controller(self, *args):
        c = Controller(self)
        c.write_output.connect(self.show_output, type=Qt.QueuedConnection)
        c.show_error.connect(self.show_error, type=Qt.QueuedConnection)
        c.interpreter_died.connect(self.interpreter_died,
                type=Qt.QueuedConnection)
        c.interpreter_done.connect(self.execution_done)
        self.controllers.append(c)

    def interpreter_died(self, controller, returncode):
        if not self.shutting_down and controller.current_command is not None:
            error_dialog(self, _('Interpreter died'),
                    _('Interpreter dies while excuting a command. To see '
                        'the command, click Show details'),
                    det_msg=controller.current_command, show=True)

    def execute(self, prompt_lines):
        c = self.root_frame.lastCursorPosition()
        self.setTextCursor(c)
        self.old_prompt_frame = self.prompt_frame
        self.prompt_frame = None
        self.old_buf = self.buf
        self.buf = []
        self.running.emit()
        self.controller.runsource('\n'.join(prompt_lines))

    def execution_done(self, controller, ret):
        if controller is self.controller:
            self.running_done.emit()
            if ret: # Incomplete command
                self.buf = self.old_buf
                self.prompt_frame = self.old_prompt_frame
                c = self.prompt_frame.lastCursorPosition()
                c.insertBlock()
                self.setTextCursor(c)
            else: # Command completed
                try:
                    self.old_prompt_frame.setFrameFormat(QTextFrameFormat())
                except RuntimeError:
                    # Happens if enough lines of output that the old
                    # frame was deleted
                    pass

            self.render_current_prompt()

    # }}}

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

    def move_cursor_to_prompt(self):
        if self.prompt_frame is not None and self.cursor_pos[0] < 0:
            c = self.prompt_frame.lastCursorPosition()
            self.setTextCursor(c)

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

    def show_error(self, is_syntax_err, tb, controller=None):
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
        QApplication.processEvents()

    def show_output(self, raw, which='stdout', controller=None):
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
        QApplication.processEvents()

    # }}}

    # Keyboard management {{{

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

    def up_pressed(self):
        lineno, pos = self.cursor_pos
        if lineno < 0: return
        if lineno == 0:
            b = self.history.back()
            if b is not None:
                self.set_prompt(b)
        else:
            c = self.cursor
            c.movePosition(c.Up)
            self.setTextCursor(c)
        self.ensureCursorVisible()


    def backspace_pressed(self):
        lineno, pos = self.cursor_pos
        if lineno < 0: return
        if pos > self.prompt_len:
            self.cursor.deletePreviousChar()
        elif lineno > 0:
            c = self.cursor
            c.movePosition(c.Up)
            c.movePosition(c.EndOfLine)
            self.setTextCursor(c)
        self.ensureCursorVisible()

    def delete_pressed(self):
        self.cursor.deleteChar()
        self.ensureCursorVisible()

    def right_pressed(self):
        lineno, pos = self.cursor_pos
        if lineno < 0: return
        c = self.cursor
        cp = list(self.prompt(False))
        if pos < len(cp[lineno]):
            c.movePosition(c.NextCharacter)
        elif lineno < len(cp)-1:
            c.movePosition(c.NextCharacter, n=1+self.prompt_len)
        self.setTextCursor(c)
        self.ensureCursorVisible()

    def down_pressed(self):
        lineno, pos = self.cursor_pos
        if lineno < 0: return
        c = self.cursor
        cp = list(self.prompt(False))
        if lineno >= len(cp) - 1:
            b = self.history.forward()
            if b is not None:
                self.set_prompt(b)
        else:
            c = self.cursor
            c.movePosition(c.Down)
            self.setTextCursor(c)
        self.ensureCursorVisible()


    def home_pressed(self):
        if self.prompt_frame is not None:
            mods = QApplication.keyboardModifiers()
            ctrl = bool(int(mods & Qt.CTRL))
            if ctrl:
                self.cursor_pos = (0, self.prompt_len)
            else:
                c = self.cursor
                c.movePosition(c.StartOfLine)
                c.movePosition(c.NextCharacter, n=self.prompt_len)
                self.setTextCursor(c)
            self.ensureCursorVisible()

    def end_pressed(self):
        if self.prompt_frame is not None:
            mods = QApplication.keyboardModifiers()
            ctrl = bool(int(mods & Qt.CTRL))
            if ctrl:
                self.cursor_pos = (len(list(self.prompt()))-1, self.prompt_len)
            c = self.cursor
            c.movePosition(c.EndOfLine)
            self.setTextCursor(c)
            self.ensureCursorVisible()

    def enter_pressed(self):
        if self.prompt_frame is None:
            return
        if not self.controller.is_alive:
            return self.no_controller_error()
        cp = list(self.prompt())
        if cp[0]:
            try:
                ret = self.compiler('\n'.join(cp))
            except:
                pass
            else:
                if ret is None:
                    c = self.prompt_frame.lastCursorPosition()
                    c.insertBlock()
                    self.setTextCursor(c)
                    self.render_current_prompt()
                    return
                else:
                    self.history.enter(cp)
            self.execute(cp)

    def text_typed(self, text):
        if self.prompt_frame is not None:
            self.move_cursor_to_prompt()
            self.cursor.insertText(text)
            self.render_current_prompt(restore_cursor=True)
            self.history.current = list(self.prompt())

    # }}}


