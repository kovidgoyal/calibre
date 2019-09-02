# coding: utf8
"""
    tinycss
    -------

    A CSS parser, and nothing else.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""

from .version import VERSION
__version__ = VERSION

from tinycss.css21 import CSS21Parser
from tinycss.page3 import CSSPage3Parser
from tinycss.fonts3 import CSSFonts3Parser
from tinycss.media3 import CSSMedia3Parser


PARSER_MODULES = {
    'page3': CSSPage3Parser,
    'fonts3': CSSFonts3Parser,
    'media3': CSSMedia3Parser,
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


def make_full_parser(**kwargs):
    ''' A parser that parses all supported CSS 3 modules in addition to CSS 2.1 '''
    features = tuple(PARSER_MODULES)
    return make_parser(*features, **kwargs)
