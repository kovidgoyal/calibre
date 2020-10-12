#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

class SelectorError(ValueError):

    """Common parent for SelectorSyntaxError and ExpressionError"""

class SelectorSyntaxError(SelectorError):

    """Parsing a selector that does not match the grammar."""

class ExpressionError(SelectorError):

    """Unknown or unsupported selector (eg. pseudo-class)."""
