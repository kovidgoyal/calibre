"""CSSComment is not defined in DOM Level 2 at all but a cssutils defined
class only.
Implements CSSRule which is also extended for a CSSComment rule type
"""
__all__ = ['CSSComment']
__docformat__ = 'restructuredtext'
__version__ = '$Id: csscomment.py 1170 2008-03-20 17:42:07Z cthedot $'

import xml.dom
import cssrule
import cssutils

class CSSComment(cssrule.CSSRule):
    """
    (cssutils) a CSS comment

    Properties
    ==========
    cssText: of type DOMString
        The comment text including comment delimiters

    Inherits properties from CSSRule

    Format
    ======
    ::

        /*...*/
    """
    type = property(lambda self: cssrule.CSSRule.COMMENT) # value = -1
    # constant but needed:
    wellformed = True 

    def __init__(self, cssText=None, parentRule=None, 
                 parentStyleSheet=None, readonly=False):
        super(CSSComment, self).__init__(parentRule=parentRule, 
                                         parentStyleSheet=parentStyleSheet)

        self._cssText = None
        if cssText:
            self._setCssText(cssText)

        self._readonly = readonly

    def _getCssText(self):
        """returns serialized property cssText"""
        return cssutils.ser.do_CSSComment(self)

    def _setCssText(self, cssText):
        """
        cssText
            textual text to set or tokenlist which is not tokenized
            anymore. May also be a single token for this rule
        parser
            if called from cssparser directly this is Parser instance

        DOMException on setting

        - SYNTAX_ERR: (self)
          Raised if the specified CSS string value has a syntax error and
          is unparsable.
        - INVALID_MODIFICATION_ERR: (self)
          Raised if the specified CSS string value represents a different
          type of rule than the current one.
        - NO_MODIFICATION_ALLOWED_ERR: (CSSRule)
          Raised if the rule is readonly.
        """
        super(CSSComment, self)._setCssText(cssText)
        tokenizer = self._tokenize2(cssText)

        commenttoken = self._nexttoken(tokenizer)
        unexpected = self._nexttoken(tokenizer)

        if not commenttoken or\
           self._type(commenttoken) != self._prods.COMMENT or\
           unexpected:
            self._log.error(u'CSSComment: Not a CSSComment: %r' %
                self._valuestr(cssText),
                error=xml.dom.InvalidModificationErr)
        else:
            self._cssText = self._tokenvalue(commenttoken)

    cssText = property(_getCssText, _setCssText,
        doc=u"(cssutils) Textual representation of this comment")

    def __repr__(self):
        return "cssutils.css.%s(cssText=%r)" % (
                self.__class__.__name__, self.cssText)

    def __str__(self):
        return "<cssutils.css.%s object cssText=%r at 0x%x>" % (
                self.__class__.__name__, self.cssText, id(self))
