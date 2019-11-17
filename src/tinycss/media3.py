#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from tinycss.css21 import CSS21Parser
from tinycss.parsing import remove_whitespace, split_on_comma, ParseError
from polyglot.builtins import error_message


class MediaQuery(object):

    __slots__ = 'media_type', 'expressions', 'negated'

    def __init__(self, media_type='all', expressions=(), negated=False):
        self.media_type = media_type
        self.expressions = expressions
        self.negated = negated

    def __repr__(self):
        return '<MediaQuery type=%s negated=%s expressions=%s>' % (
            self.media_type, self.negated, self.expressions)

    def __eq__(self, other):
        return self.media_type == getattr(other, 'media_type', None) and \
            self.negated == getattr(other, 'negated', None) and \
            self.expressions == getattr(other, 'expressions', None)


class MalformedExpression(Exception):

    def __init__(self, tok, msg):
        Exception.__init__(self, msg)
        self.tok = tok


class CSSMedia3Parser(CSS21Parser):

    ''' Parse media queries as defined by the CSS 3 media module '''

    def parse_media(self, tokens, errors):
        if not tokens:
            return [MediaQuery('all')]
        queries = []

        for part in split_on_comma(remove_whitespace(tokens)):
            negated = False
            media_type = None
            expressions = []
            try:
                for i, tok in enumerate(part):
                    if i == 0 and tok.type == 'IDENT':
                        val = tok.value.lower()
                        if val == 'only':
                            continue  # ignore leading ONLY
                        if val == 'not':
                            negated = True
                            continue
                    if media_type is None and tok.type == 'IDENT':
                        media_type = tok.value
                        continue
                    elif media_type is None:
                        media_type = 'all'

                    if tok.type == 'IDENT' and tok.value.lower() == 'and':
                        continue
                    if not tok.is_container:
                        raise MalformedExpression(tok, 'expected a media expression not a %s' % tok.type)
                    if tok.type != '(':
                        raise MalformedExpression(tok, 'media expressions must be in parentheses not %s' % tok.type)
                    content = remove_whitespace(tok.content)
                    if len(content) == 0:
                        raise MalformedExpression(tok, 'media expressions cannot be empty')
                    if content[0].type != 'IDENT':
                        raise MalformedExpression(content[0], 'expected a media feature not a %s' % tok.type)
                    media_feature, expr = content[0].value, None
                    if len(content) > 1:
                        if len(content) < 3:
                            raise MalformedExpression(content[1], 'malformed media feature definition')
                        if content[1].type != ':':
                            raise MalformedExpression(content[1], 'expected a :')
                        expr = content[2:]
                        if len(expr) == 1:
                            expr = expr[0]
                        elif len(expr) == 3 and (expr[0].type, expr[1].type, expr[1].value, expr[2].type) == (
                            'INTEGER', 'DELIM', '/', 'INTEGER'):
                            # This should really be moved into token_data, but
                            # since RATIO is not part of CSS 2.1 and does not
                            # occur anywhere else, we special case it here.
                            r = expr[0]
                            r.value = (expr[0].value, expr[2].value)
                            r.type = 'RATIO'
                            r._as_css = expr[0]._as_css + expr[1]._as_css + expr[2]._as_css
                            expr = r
                        else:
                            raise MalformedExpression(expr[0], 'malformed media feature definition')

                    expressions.append((media_feature, expr))
            except MalformedExpression as err:
                errors.append(ParseError(err.tok, error_message(err)))
                media_type, negated, expressions = 'all', True, ()
            queries.append(MediaQuery(media_type or 'all', expressions=tuple(expressions), negated=negated))

        return queries
