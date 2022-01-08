#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import numbers
from functools import partial

from qt.core import QTextBlockUserData
from pygments.lexer import _TokenType, Error

from calibre.gui2.tweak_book.editor.syntax.base import SyntaxHighlighter
from calibre.gui2.tweak_book.editor.syntax.utils import format_for_pygments_token, NULL_FMT

NORMAL = 0


def create_lexer(base_class):
    '''
    Subclass the pygments RegexLexer to lex line by line instead of lexing full
    text. The statestack at the end of each line is stored in the Qt block state.
    '''

    def get_tokens_unprocessed(self, text, statestack):
        pos = 0
        tokendefs = self._tokens
        statetokens = tokendefs[statestack[-1]]
        while True:
            for rexmatch, action, new_state in statetokens:
                m = rexmatch(text, pos)
                if m is not None:
                    if action is not None:
                        if type(action) is _TokenType:
                            yield pos, action, m.group()
                        else:
                            yield from action(self, m)
                    pos = m.end()
                    if new_state is not None:
                        # state transition
                        if isinstance(new_state, tuple):
                            for state in new_state:
                                if state == '#pop':
                                    statestack.pop()
                                elif state == '#push':
                                    statestack.append(statestack[-1])
                                else:
                                    statestack.append(state)
                        elif isinstance(new_state, numbers.Integral):
                            # pop
                            del statestack[new_state:]
                        elif new_state == '#push':
                            statestack.append(statestack[-1])
                        else:
                            assert False, "wrong state def: %r" % new_state
                        statetokens = tokendefs[statestack[-1]]
                    break
            else:
                try:
                    if text[pos] == '\n':
                        # at EOL, reset state to "root"
                        statestack[:] = ['root']
                        break
                    yield pos, Error, text[pos]
                    pos += 1
                except IndexError:
                    break

    def lex_a_line(self, state, text, i, formats_map, user_data):
        ' Get formats for a single block (line) '
        statestack = list(state.pygments_stack) if state.pygments_stack is not None else ['root']

        # Lex the text using Pygments
        formats = []
        if i > 0:
            # This should never happen
            state.pygments_stack = None
            return [(len(text) - i, formats_map(Error))]
        try:
            # Pygments lexers expect newlines at the end of the line
            for pos, token, txt in self.get_tokens_unprocessed(text + '\n', statestack):
                if txt not in ('\n', ''):
                    formats.append((len(txt), formats_map(token)))
        except Exception:
            import traceback
            traceback.print_exc()
            state.pygments_stack = None
            return [(len(text) - i, formats_map(Error))]

        state.pygments_stack = statestack
        return formats

    name_type = type(base_class.__name__)

    return type(name_type('Qt'+base_class.__name__), (base_class,), {
        'get_tokens_unprocessed': get_tokens_unprocessed,
        'lex_a_line':lex_a_line,
    })


class State:

    __slots__ = ('parse', 'pygments_stack')

    def __init__(self):
        self.parse = NORMAL
        self.pygments_stack = None

    def copy(self):
        s = State()
        s.pygments_stack = None if self.pygments_stack is None else list(self.pygments_stack)
        return s

    def __eq__(self, other):
        return self.parse == getattr(other, 'parse', -1) and \
            self.pygments_stack == getattr(other, 'pygments_stack', False)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "PythonState(%r)" % self.pygments_stack
    __str__ = __repr__


class PygmentsUserData(QTextBlockUserData):

    def __init__(self):
        QTextBlockUserData.__init__(self)
        self.state = State()
        self.doc_name = None

    def clear(self, state=None, doc_name=None):
        self.state = State() if state is None else state
        self.doc_name = doc_name


def create_formats(highlighter):
    cache = {}
    theme = highlighter.theme.copy()
    theme[None] = NULL_FMT
    return partial(format_for_pygments_token, theme, cache)


def create_highlighter(name, lexer_class):
    name_type = type(lexer_class.__name__)
    return type(name_type(name), (SyntaxHighlighter,), {
        'state_map': {NORMAL:create_lexer(lexer_class)().lex_a_line},
        'create_formats_func': create_formats,
        'user_data_factory': PygmentsUserData,
    })
