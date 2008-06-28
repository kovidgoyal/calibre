# -*- coding: utf-8 -*-
#
# Copyright (C) 2007-2008 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://genshi.edgewall.org/wiki/License.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://genshi.edgewall.org/log/.

"""String interpolation routines, i.e. the splitting up a given text into some
parts that are literal strings, and others that are Python expressions.
"""

from itertools import chain
import os
import re
from tokenize import PseudoToken

from calibre.utils.genshi.core import TEXT
from calibre.utils.genshi.template.base import TemplateSyntaxError, EXPR
from calibre.utils.genshi.template.eval import Expression

__all__ = ['interpolate']
__docformat__ = 'restructuredtext en'

NAMESTART = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'
NAMECHARS = NAMESTART + '.0123456789'
PREFIX = '$'

token_re = re.compile('%s|%s(?s)' % (
    r'[uU]?[rR]?("""|\'\'\')((?<!\\)\\\1|.)*?\1',
    PseudoToken
))

def interpolate(text, filepath=None, lineno=-1, offset=0, lookup='strict'):
    """Parse the given string and extract expressions.
    
    This function is a generator that yields `TEXT` events for literal strings,
    and `EXPR` events for expressions, depending on the results of parsing the
    string.
    
    >>> for kind, data, pos in interpolate("hey ${foo}bar"):
    ...     print kind, `data`
    TEXT u'hey '
    EXPR Expression('foo')
    TEXT u'bar'
    
    :param text: the text to parse
    :param filepath: absolute path to the file in which the text was found
                     (optional)
    :param lineno: the line number at which the text was found (optional)
    :param offset: the column number at which the text starts in the source
                   (optional)
    :param lookup: the variable lookup mechanism; either "lenient" (the
                   default), "strict", or a custom lookup class
    :return: a list of `TEXT` and `EXPR` events
    :raise TemplateSyntaxError: when a syntax error in an expression is
                                encountered
    """
    pos = [filepath, lineno, offset]

    textbuf = []
    textpos = None
    for is_expr, chunk in chain(lex(text, pos, filepath), [(True, '')]):
        if is_expr:
            if textbuf:
                yield TEXT, u''.join(textbuf), textpos
                del textbuf[:]
                textpos = None
            if chunk:
                try:
                    expr = Expression(chunk.strip(), pos[0], pos[1],
                                      lookup=lookup)
                    yield EXPR, expr, tuple(pos)
                except SyntaxError, err:
                    raise TemplateSyntaxError(err, filepath, pos[1],
                                              pos[2] + (err.offset or 0))
        else:
            textbuf.append(chunk)
            if textpos is None:
                textpos = tuple(pos)

        if '\n' in chunk:
            lines = chunk.splitlines()
            pos[1] += len(lines) - 1
            pos[2] += len(lines[-1])
        else:
            pos[2] += len(chunk)

def lex(text, textpos, filepath):
    offset = pos = 0
    end = len(text)
    escaped = False

    while 1:
        if escaped:
            offset = text.find(PREFIX, offset + 2)
            escaped = False
        else:
            offset = text.find(PREFIX, pos)
        if offset < 0 or offset == end - 1:
            break
        next = text[offset + 1]

        if next == '{':
            if offset > pos:
                yield False, text[pos:offset]
            pos = offset + 2
            level = 1
            while level:
                match = token_re.match(text, pos)
                if match is None:
                    raise TemplateSyntaxError('invalid syntax',  filepath,
                                              *textpos[1:])
                pos = match.end()
                tstart, tend = match.regs[3]
                token = text[tstart:tend]
                if token == '{':
                    level += 1
                elif token == '}':
                    level -= 1
            yield True, text[offset + 2:pos - 1]

        elif next in NAMESTART:
            if offset > pos:
                yield False, text[pos:offset]
                pos = offset
            pos += 1
            while pos < end:
                char = text[pos]
                if char not in NAMECHARS:
                    break
                pos += 1
            yield True, text[offset + 1:pos].strip()

        elif not escaped and next == PREFIX:
            if offset > pos:
                yield False, text[pos:offset]
            escaped = True
            pos = offset + 1

        else:
            yield False, text[pos:offset + 1]
            pos = offset + 1

    if pos < end:
        yield False, text[pos:]
