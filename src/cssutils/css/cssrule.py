"""CSSRule implements DOM Level 2 CSS CSSRule."""
__all__ = ['CSSRule']
__docformat__ = 'restructuredtext'
__version__ = '$Id: cssrule.py 1855 2009-10-07 17:03:19Z cthedot $'

import cssutils
import xml.dom

class CSSRule(cssutils.util.Base2):
    """Abstract base interface for any type of CSS statement. This includes
    both rule sets and at-rules. An implementation is expected to preserve
    all rules specified in a CSS style sheet, even if the rule is not
    recognized by the parser. Unrecognized rules are represented using the
    :class:`CSSUnknownRule` interface.
    """

    """
    CSSRule type constants.
    An integer indicating which type of rule this is.
    """
    COMMENT = -1 # cssutils only
    UNKNOWN_RULE = 0 #u
    STYLE_RULE = 1 #s
    CHARSET_RULE = 2 #c
    IMPORT_RULE = 3 #i
    MEDIA_RULE = 4 #m
    FONT_FACE_RULE = 5 #f
    PAGE_RULE = 6 #p
    NAMESPACE_RULE = 7 # CSSOM
    VARIABLES_RULE = 8 # CSS Variables

    _typestrings = ['UNKNOWN_RULE', 'STYLE_RULE', 'CHARSET_RULE', 'IMPORT_RULE',
                     'MEDIA_RULE', 'FONT_FACE_RULE', 'PAGE_RULE', 'NAMESPACE_RULE',
                     'VARIABLES_RULE',
                     'COMMENT']

    def __init__(self, parentRule=None, parentStyleSheet=None, readonly=False):
        """Set common attributes for all rules."""
        super(CSSRule, self).__init__()
        self._parent = parentRule
        self._parentRule = parentRule
        self._parentStyleSheet = parentStyleSheet
        self._setSeq(self._tempSeq())
        # must be set after initialization of #inheriting rule is done
        self._readonly = False

    def _setAtkeyword(self, akw):
        """Check if new keyword fits the rule it is used for."""
        if not self.atkeyword or (self._normalize(akw) == 
                                  self._normalize(self.atkeyword)):
            self._atkeyword = akw
        else:
            self._log.error(u'%s: Invalid atkeyword for this rule: %r' % 
                            (self._normalize(self.atkeyword), akw), 
                            error=xml.dom.InvalidModificationErr)

    atkeyword = property(lambda self: self._atkeyword, _setAtkeyword,
                         doc=u"Literal keyword of an @rule (e.g. ``@IMport``).")

    def _setCssText(self, cssText):
        """
        :param cssText:
            A parsable DOMString.
        :exceptions:
            - :exc:`~xml.dom.SyntaxErr`:
              Raised if the specified CSS string value has a syntax error and
              is unparsable.
            - :exc:`~xml.dom.InvalidModificationErr`:
              Raised if the specified CSS string value represents a different
              type of rule than the current one.
            - :exc:`~xml.dom.HierarchyRequestErr`:
              Raised if the rule cannot be inserted at this point in the
              style sheet.
            - :exc:`~xml.dom.NoModificationAllowedErr`:
              Raised if the rule is readonly.
        """
        self._checkReadonly()

    cssText = property(lambda self: u'', _setCssText,
                       doc="(DOM) The parsable textual representation of the "
                           "rule. This reflects the current state of the rule "
                           "and not its initial value.")

    parent = property(lambda self: self._parent,
                      doc="The Parent Node of this CSSRule (currently if a "
                          "CSSStyleDeclaration only!) or None.")    
    
    parentRule = property(lambda self: self._parentRule,
                                doc="If this rule is contained inside "
                                    "another rule (e.g. a style rule inside "
                                    "an @media block), this is the containing "
                                    "rule. If this rule is not nested inside "
                                    "any other rules, this returns None.")

    parentStyleSheet = property(lambda self: self._parentStyleSheet,
                          doc="The style sheet that contains this rule.")

    type = property(lambda self: self.UNKNOWN_RULE, 
                    doc="The type of this rule, as defined by a CSSRule "
                        "type constant.")

    typeString = property(lambda self: CSSRule._typestrings[self.type], 
                          doc="Descriptive name of this rule's type.")

    wellformed = property(lambda self: False, 
                          doc=u"If the rule is wellformed.")
