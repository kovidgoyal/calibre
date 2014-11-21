#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from functools import partial

from PyQt5.Qt import QTextBlockUserData
from pygments.lexer import _TokenType, Text, Error

from calibre.gui2.tweak_book.editor.syntax.base import SyntaxHighlighter
from calibre.gui2.tweak_book.editor.syntax.utils import format_for_pygments_token, NULL_FMT

NORMAL = 0

def create_lexer(base_class):
    '''
    Subclass the pygments RegexLexer to store state on the lexer itself,
    allowing for efficient integration into Qt
    '''

    def get_tokens_unprocessed(self, text, stack=('root',)):
        # Method is overriden to store state on the lexer itself
        pos = 0
        tokendefs = self._tokens
        statestack = self.saved_state_stack = list(stack if self.saved_state_stack is None else self.saved_state_stack)
        statetokens = tokendefs[statestack[-1]]
        while 1:
            for rexmatch, action, new_state in statetokens:
                m = rexmatch(text, pos)
                if m:
                    if action is not None:
                        if type(action) is _TokenType:
                            yield pos, action, m.group()
                        else:
                            for item in action(self, m):
                                yield item
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
                        elif isinstance(new_state, int):
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
                        statestack = ['root']
                        statetokens = tokendefs['root']
                        yield pos, Text, u'\n'
                        pos += 1
                        continue
                    yield pos, Error, text[pos]
                    pos += 1
                except IndexError:
                    break

    def lex_a_line(self, state, text, i, formats_map, user_data):
        ' Get formats for a single block (line) '
        self.saved_state_stack = state.pygments_stack

        # Lex the text using Pygments
        formats = []
        if i > 0:
            text = text[i:]
        for token, txt in self.get_tokens(text):
            if txt:
                formats.append((len(txt), formats_map(token)))

        ss = self.saved_state_stack
        if ss is not None:
            state.pygments_stack = ss
            # Clean up the lexer so that it can be re-used
            self.saved_state_stack = None
        return formats

    return type(str('Qt'+base_class.__name__), (base_class,), {
        'saved_state_stack': None,
        'get_tokens_unprocessed': get_tokens_unprocessed,
        'lex_a_line':lex_a_line,
    })

class State(object):

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
    return type(str(name), (SyntaxHighlighter,), {
        'state_map': {NORMAL:create_lexer(lexer_class)().lex_a_line},
        'create_formats_func': create_formats,
        'user_data_factory': PygmentsUserData,
    })
