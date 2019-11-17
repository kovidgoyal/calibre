# coding: utf8
"""
    tinycss.page3
    ------------------

    Support for CSS 3 Paged Media syntax:
    http://dev.w3.org/csswg/css3-page/

    Adds support for named page selectors and margin rules.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.
"""


from .css21 import CSS21Parser, ParseError


class MarginRule(object):
    """A parsed at-rule for margin box.

    .. attribute:: at_keyword

        One of the 16 following strings:

        * ``@top-left-corner``
        * ``@top-left``
        * ``@top-center``
        * ``@top-right``
        * ``@top-right-corner``
        * ``@bottom-left-corner``
        * ``@bottom-left``
        * ``@bottom-center``
        * ``@bottom-right``
        * ``@bottom-right-corner``
        * ``@left-top``
        * ``@left-middle``
        * ``@left-bottom``
        * ``@right-top``
        * ``@right-middle``
        * ``@right-bottom``

    .. attribute:: declarations

        A list of :class:`~.css21.Declaration` objects.

    .. attribute:: line

        Source line where this was read.

    .. attribute:: column

        Source column where this was read.

    """

    __slots__ = 'at_keyword', 'declarations', 'line', 'column'

    def __init__(self, at_keyword, declarations, line, column):
        self.at_keyword = at_keyword
        self.declarations = declarations
        self.line = line
        self.column = column


class CSSPage3Parser(CSS21Parser):
    """Extend :class:`~.css21.CSS21Parser` for `CSS 3 Paged Media`_ syntax.

    .. _CSS 3 Paged Media: http://dev.w3.org/csswg/css3-page/

    Compared to CSS 2.1, the ``at_rules`` and ``selector`` attributes of
    :class:`~.css21.PageRule` objects are modified:

    * ``at_rules`` is not always empty, it is a list of :class:`MarginRule`
      objects.

    * ``selector``, instead of a single string, is a tuple of the page name
      and the pseudo class. Each of these may be a ``None`` or a string.

    +--------------------------+------------------------+
    | CSS                      | Parsed selectors       |
    +==========================+========================+
    | .. code-block:: css      | .. code-block:: python |
    |                          |                        |
    |     @page {}             |     (None, None)       |
    |     @page :first {}      |     (None, 'first')    |
    |     @page chapter {}     |     ('chapter', None)  |
    |     @page table:right {} |     ('table', 'right') |
    +--------------------------+------------------------+

    """

    PAGE_MARGIN_AT_KEYWORDS = (
        '@top-left-corner',
        '@top-left',
        '@top-center',
        '@top-right',
        '@top-right-corner',
        '@bottom-left-corner',
        '@bottom-left',
        '@bottom-center',
        '@bottom-right',
        '@bottom-right-corner',
        '@left-top',
        '@left-middle',
        '@left-bottom',
        '@right-top',
        '@right-middle',
        '@right-bottom',
    )

    def __init__(self):
        super(CSSPage3Parser, self).__init__()
        for x in self.PAGE_MARGIN_AT_KEYWORDS:
            self.at_parsers[x] = self.parse_page_margin_rule

    def parse_page_margin_rule(self, rule, previous_rules, errors, context):
        if context != '@page':
            raise ParseError(rule,
                '%s rule not allowed in %s' % (rule.at_keyword, context))
        if rule.head:
            raise ParseError(rule.head[0],
                'unexpected %s token in %s rule header'
                % (rule.head[0].type, rule.at_keyword))
        declarations, body_errors = self.parse_declaration_list(rule.body)
        errors.extend(body_errors)
        return MarginRule(rule.at_keyword, declarations,
                            rule.line, rule.column)

    def parse_page_selector(self, head):
        """Parse an @page selector.

        :param head:
            The ``head`` attribute of an unparsed :class:`AtRule`.
        :returns:
            A page selector. For CSS 2.1, this is 'first', 'left', 'right'
            or None. 'blank' is added by GCPM.
        :raises:
            :class`~parsing.ParseError` on invalid selectors

        """
        if not head:
            return (None, None), (0, 0, 0)
        if head[0].type == 'IDENT':
            name = head.pop(0).value
            while head and head[0].type == 'S':
                head.pop(0)
            if not head:
                return (name, None), (1, 0, 0)
            name_specificity = (1,)
        else:
            name = None
            name_specificity = (0,)
        if (len(head) == 2 and head[0].type == ':'
                and head[1].type == 'IDENT'):
            pseudo_class = head[1].value
            specificity = {
                'first': (1, 0), 'blank': (1, 0),
                'left': (0, 1), 'right': (0, 1),
            }.get(pseudo_class)
            if specificity:
                return (name, pseudo_class), (name_specificity + specificity)
        raise ParseError(head[0], 'invalid @page selector')
