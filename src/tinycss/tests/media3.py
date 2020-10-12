#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from tinycss.media3 import CSSMedia3Parser, MediaQuery as MQ
from tinycss.tests import BaseTest, jsonify

def jsonify_expr(e):
    if e is None:
        return None
    return next(jsonify([e]))

def jsonify_expressions(mqlist):
    for mq in mqlist:
        mq.expressions = tuple(
            (k, jsonify_expr(e)) for k, e in mq.expressions)
    return mqlist

class TestFonts3(BaseTest):

    def test_media_queries(self):
        'Test parsing of media queries from the CSS 3 media module'
        for css, media_query_list, expected_errors in [
                # CSS 2.1 (simple media queries)
                ('@media {}', [MQ()], []),
                ('@media all {}', [MQ()], []),
                ('@media screen {}', [MQ('screen')], []),
                ('@media , screen {}', [MQ(), MQ('screen')], []),
                ('@media screen, {}', [MQ('screen'), MQ()], []),

                # Examples from the CSS 3 specs
                ('@media screen and (color) {}', [MQ('screen', (('color', None),))], []),
                ('@media all and (min-width:500px) {}', [
                    MQ('all', (('min-width', ('DIMENSION', 500)),))], []),
                ('@media (min-width:500px) {}', [
                    MQ('all', (('min-width', ('DIMENSION', 500)),))], []),
                ('@media (orientation: portrait) {}', [
                    MQ('all', (('orientation', ('IDENT', 'portrait')),))], []),
                ('@media screen and (color), projection and (color) {}', [
                    MQ('screen', (('color', None),)), MQ('projection', (('color', None),)),], []),
                ('@media not screen and (color) {}', [
                    MQ('screen', (('color', None),), True)], []),
                ('@media only screen and (color) {}', [
                    MQ('screen', (('color', None),))], []),
                ('@media aural and (device-aspect-ratio: 16/9) {}', [
                    MQ('aural', (('device-aspect-ratio', ('RATIO', (16, 9))),))], []),
                ('@media (resolution: 166dpi) {}', [
                    MQ('all', (('resolution', ('DIMENSION', 166)),))], []),
                ('@media (min-resolution: 166DPCM) {}', [
                    MQ('all', (('min-resolution', ('DIMENSION', 166)),))], []),

                # Malformed media queries
                ('@media (example, all,), speech {}', [MQ(negated=True), MQ('speech')], ['expected a :']),
                ('@media &test, screen {}', [MQ(negated=True), MQ('screen')], ['expected a media expression not a DELIM']),

        ]:
            stylesheet = CSSMedia3Parser().parse_stylesheet(css)
            self.assert_errors(stylesheet.errors, expected_errors)
            self.ae(len(stylesheet.rules), 1)
            rule = stylesheet.rules[0]
            self.ae(jsonify_expressions(rule.media), media_query_list)

