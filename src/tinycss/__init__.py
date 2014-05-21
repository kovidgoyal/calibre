# coding: utf8
"""
    tinycss
    -------

    A CSS parser, and nothing else.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""

import sys

from .version import VERSION
__version__ = VERSION

from .css21 import CSS21Parser
from .page3 import CSSPage3Parser


PARSER_MODULES = {
    'page3': CSSPage3Parser,
}


def make_parser(*features, **kwargs):
    """Make a parser object with the chosen features.

    :param features:
        Positional arguments are base classes the new parser class will extend.
        The string ``'page3'`` is accepted as short for
        :class:`~page3.CSSPage3Parser`.
    :param kwargs:
        Keyword arguments are passed to the parser’s constructor.
    :returns:
        An instance of a new subclass of :class:`CSS21Parser`

    """
    if features:
        bases = tuple(PARSER_MODULES.get(f, f) for f in features)
        parser_class = type('CustomCSSParser', bases + (CSS21Parser,), {})
    else:
        parser_class = CSS21Parser
    return parser_class(**kwargs)
