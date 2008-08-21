"""CSSRule implements DOM Level 2 CSS CSSRule."""
__all__ = ['CSSRule']
__docformat__ = 'restructuredtext'
__version__ = '$Id: cssrule.py 1177 2008-03-20 17:47:23Z cthedot $'

import xml.dom
import cssutils

class CSSRule(cssutils.util.Base2):
    """
    Abstract base interface for any type of CSS statement. This includes
    both rule sets and at-rules. An implementation is expected to preserve
    all rules specified in a CSS style sheet, even if the rule is not
    recognized by the parser. Unrecognized rules are represented using the
    CSSUnknownRule interface.

    Properties
    ==========
    cssText: of type DOMString
        The parsable textual representation of the rule. This reflects the
        current state of the rule and not its initial value.
    parentRule: of type CSSRule, readonly
        If this rule is contained inside another rule (e.g. a style rule
        inside an @media block), this is the containing rule. If this rule
        is not nested inside any other rules, this returns None.
    parentStyleSheet: of type CSSStyleSheet, readonly
        The style sheet that contains this rule.
    type: of type unsigned short, readonly
        The type of the rule, as defined above. The expectation is that
        binding-specific casting methods can be used to cast down from an
        instance of the CSSRule interface to the specific derived interface
        implied by the type.

    cssutils only
    -------------
    seq (READONLY):
        contains sequence of parts of the rule including comments but
        excluding @KEYWORD and braces
    typeString: string
        A string name of the type of this rule, e.g. 'STYLE_RULE'. Mainly
        useful for debugging
    wellformed:
        if a rule is valid 
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

    _typestrings = ['UNKNOWN_RULE', 'STYLE_RULE', 'CHARSET_RULE', 'IMPORT_RULE',
                     'MEDIA_RULE', 'FONT_FACE_RULE', 'PAGE_RULE', 'NAMESPACE_RULE',
                     'COMMENT']

    type = UNKNOWN_RULE
    """
    The type of this rule, as defined by a CSSRule type constant.
    Overwritten in derived classes.

    The expectation is that binding-specific casting methods can be used to
    cast down from an instance of the CSSRule interface to the specific
    derived interface implied by the type.
    (Casting not for this Python implementation I guess...)
    """

    def __init__(self, parentRule=None, parentStyleSheet=None, readonly=False):
        """
        set common attributes for all rules
        """
        super(CSSRule, self).__init__()
        self._parentRule = parentRule
        self._parentStyleSheet = parentStyleSheet
        self._setSeq(self._tempSeq())
        # must be set after initialization of #inheriting rule is done
        self._readonly = False

    def _setCssText(self, cssText):
        """
        DOMException on setting

        - SYNTAX_ERR:
          Raised if the specified CSS string value has a syntax error and
          is unparsable.
        - INVALID_MODIFICATION_ERR:
          Raised if the specified CSS string value represents a different
          type of rule than the current one.
        - HIERARCHY_REQUEST_ERR:
          Raised if the rule cannot be inserted at this point in the
          style sheet.
        - NO_MODIFICATION_ALLOWED_ERR: (self)
          Raised if the rule is readonly.
        """
        self._checkReadonly()

    cssText = property(lambda self: u'', _setCssText,
        doc="""(DOM) The parsable textual representation of the rule. This
        reflects the current state of the rule and not its initial value.
        The initial value is saved, but this may be removed in a future
        version!
        MUST BE OVERWRITTEN IN SUBCLASS TO WORK!""")

    def _setAtkeyword(self, akw):
        """checks if new keyword is normalized same as old"""
        if not self.atkeyword or (self._normalize(akw) == 
                                  self._normalize(self.atkeyword)):
            self._atkeyword = akw
        else:
            self._log.error(u'%s: Invalid atkeyword for this rule: %r' % 
                            (self._normalize(self.atkeyword), akw), 
                            error=xml.dom.InvalidModificationErr)

    atkeyword = property(lambda self: self._atkeyword, _setAtkeyword,
                          doc=u"@keyword for @rules")

    parentRule = property(lambda self: self._parentRule,
                          doc=u"READONLY")

    parentStyleSheet = property(lambda self: self._parentStyleSheet,
                                doc=u"READONLY")

    wellformed = property(lambda self: False, 
                          doc=u"READONLY")

    typeString = property(lambda self: CSSRule._typestrings[self.type], 
                          doc="Name of this rules type.")
