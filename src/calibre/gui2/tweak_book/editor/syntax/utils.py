#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from qt.core import QTextCharFormat

NULL_FMT = QTextCharFormat()

_pyg_map = None


def pygments_map():
    global _pyg_map
    if _pyg_map is None:
        from pygments.token import Token
        _pyg_map = {
            Token: None,
            Token.Comment: 'Comment', Token.Comment.Preproc: 'PreProc',
            Token.String: 'String',
            Token.Number: 'Number',
            Token.Keyword.Type: 'Type',
            Token.Keyword: 'Keyword',
            Token.Name.Builtin: 'Identifier',
            Token.Operator: 'Statement',
            Token.Name.Function: 'Function',
            Token.Literal: 'Constant',
            Token.Error: 'Error',
        }
    return _pyg_map


def format_for_pygments_token(theme, cache, token):
    try:
        return cache[token]
    except KeyError:
        pass
    pmap = pygments_map()
    while token is not None:
        try:
            name = pmap[token]
        except KeyError:
            token = token.parent
            continue
        cache[token] = ans = theme[name]
        return ans
    cache[token] = ans = NULL_FMT
    return ans



