#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import unittest


def jsonify(tokens):
    """Turn tokens into "JSON-compatible" data structures."""
    for token in tokens:
        if token.type == 'FUNCTION':
            yield (token.type, token.function_name,
                   list(jsonify(token.content)))
        elif token.is_container:
            yield token.type, list(jsonify(token.content))
        else:
            yield token.type, token.value


class BaseTest(unittest.TestCase):

    longMessage = True
    maxDiff = None
    ae = unittest.TestCase.assertEqual

    def assert_errors(self, errors, expected_errors):
        """Test not complete error messages but only substrings."""
        self.ae(len(errors), len(expected_errors))
        for error, expected in zip(errors, expected_errors):
            self.assertIn(expected, type(u'')(error))

    def jsonify_declarations(self, rule):
        return [(decl.name, list(jsonify(decl.value)))
                for decl in rule.declarations]
