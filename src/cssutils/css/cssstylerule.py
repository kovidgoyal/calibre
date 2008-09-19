"""CSSStyleRule implements DOM Level 2 CSS CSSStyleRule.
"""
__all__ = ['CSSStyleRule']
__docformat__ = 'restructuredtext'
__version__ = '$Id: cssstylerule.py 1284 2008-06-05 16:29:17Z cthedot $'

import xml.dom
import cssrule
import cssutils
from selectorlist import SelectorList
from cssstyledeclaration import CSSStyleDeclaration

class CSSStyleRule(cssrule.CSSRule):
    """
    The CSSStyleRule object represents a ruleset specified (if any) in a CSS
    style sheet. It provides access to a declaration block as well as to the
    associated group of selectors.
    
    Properties
    ==========
    selectorList: of type SelectorList (cssutils only)
        A list of all Selector elements for the rule set.
    selectorText: of type DOMString
        The textual representation of the selector for the rule set. The
        implementation may have stripped out insignificant whitespace while
        parsing the selector.
    style: of type CSSStyleDeclaration, (DOM)
        The declaration-block of this rule set.
    type
        the type of this rule, constant cssutils.CSSRule.STYLE_RULE
        
    inherited properties:
        - cssText
        - parentRule
        - parentStyleSheet

    Format
    ======
    ruleset::
    
        : selector [ COMMA S* selector ]*
        LBRACE S* declaration [ ';' S* declaration ]* '}' S*
        ;
    """
    type = property(lambda self: cssrule.CSSRule.STYLE_RULE)

    def __init__(self, selectorText=None, style=None, parentRule=None, 
                 parentStyleSheet=None, readonly=False):
        """
        :Parameters:
            selectorText
                string parsed into selectorList
            style
                string parsed into CSSStyleDeclaration for this CSSStyleRule
            readonly
                if True allows setting of properties in constructor only
        """
        super(CSSStyleRule, self).__init__(parentRule=parentRule, 
                                           parentStyleSheet=parentStyleSheet)

        self._selectorList = SelectorList(parentRule=self)
        self._style = CSSStyleDeclaration(parentRule=self)
        if selectorText:
            self.selectorText = selectorText            
        if style:
            self.style = style

        self._readonly = readonly


    def _getCssText(self):
        """
        returns serialized property cssText
        """
        return cssutils.ser.do_CSSStyleRule(self)

    def _setCssText(self, cssText):
        """
        :param cssText:
            a parseable string or a tuple of (cssText, dict-of-namespaces)
        :Exceptions:
            - `NAMESPACE_ERR`: (Selector)
              Raised if the specified selector uses an unknown namespace
              prefix.
            - `SYNTAX_ERR`: (self, StyleDeclaration, etc)
              Raised if the specified CSS string value has a syntax error and
              is unparsable.
            - `INVALID_MODIFICATION_ERR`: (self)
              Raised if the specified CSS string value represents a different
              type of rule than the current one.
            - `HIERARCHY_REQUEST_ERR`: (CSSStylesheet)
              Raised if the rule cannot be inserted at this point in the
              style sheet.
            - `NO_MODIFICATION_ALLOWED_ERR`: (CSSRule)
              Raised if the rule is readonly.
        """
        super(CSSStyleRule, self)._setCssText(cssText)
        
        # might be (cssText, namespaces)
        cssText, namespaces = self._splitNamespacesOff(cssText)
        try:
            # use parent style sheet ones if available
            namespaces = self.parentStyleSheet.namespaces
        except AttributeError:
            pass

        tokenizer = self._tokenize2(cssText)
        selectortokens = self._tokensupto2(tokenizer, blockstartonly=True)
        styletokens = self._tokensupto2(tokenizer, blockendonly=True)
        trail = self._nexttoken(tokenizer)
        if trail:
            self._log.error(u'CSSStyleRule: Trailing content: %s' % 
                            self._valuestr(cssText), token=trail)
        elif not selectortokens:
            self._log.error(u'CSSStyleRule: No selector found: %r' % 
                            self._valuestr(cssText))
        elif self._tokenvalue(selectortokens[0]).startswith(u'@'):
            self._log.error(u'CSSStyleRule: No style rule: %r' %
                            self._valuestr(cssText),
                            error=xml.dom.InvalidModificationErr)
        else:
            wellformed = True
            
            bracetoken = selectortokens.pop()
            if self._tokenvalue(bracetoken) != u'{':
                wellformed = False
                self._log.error(
                    u'CSSStyleRule: No start { of style declaration found: %r' %
                    self._valuestr(cssText), bracetoken)
            elif not selectortokens:
                wellformed = False
                self._log.error(u'CSSStyleRule: No selector found: %r.' %
                            self._valuestr(cssText), bracetoken)
            newselectorlist = SelectorList(selectorText=(selectortokens, 
                                                         namespaces),
                                           parentRule=self)

            newstyle = CSSStyleDeclaration()
            if not styletokens:
                wellformed = False
                self._log.error(
                    u'CSSStyleRule: No style declaration or "}" found: %r' %
                    self._valuestr(cssText))
            else:
                braceorEOFtoken = styletokens.pop()
                val, typ = self._tokenvalue(braceorEOFtoken), self._type(braceorEOFtoken)
                if val != u'}' and typ != 'EOF':
                    wellformed = False
                    self._log.error(
                        u'CSSStyleRule: No "}" after style declaration found: %r' %
                        self._valuestr(cssText))
                else:
                    if 'EOF' == typ:
                        # add again as style needs it
                        styletokens.append(braceorEOFtoken)
                    newstyle.cssText = styletokens

            if wellformed:
                self._selectorList = newselectorlist
                self.style = newstyle

    cssText = property(_getCssText, _setCssText,
        doc="(DOM) The parsable textual representation of the rule.")


    def __getNamespaces(self):
        "uses children namespaces if not attached to a sheet, else the sheet's ones"
        try:
            return self.parentStyleSheet.namespaces
        except AttributeError:
            return self.selectorList._namespaces
            
    _namespaces = property(__getNamespaces, doc=u"""if this Rule is 
        attached to a CSSStyleSheet the namespaces of that sheet are mirrored
        here. While the Rule is not attached the namespaces of selectorList
        are used.""")

    def _setSelectorList(self, selectorList):
        """
        :param selectorList: selectorList, only content is used, not the actual
            object
        """
        self._checkReadonly()
        self.selectorText = selectorList.selectorText
            
    selectorList = property(lambda self: self._selectorList, _setSelectorList,
        doc="The SelectorList of this rule.")

    def _setSelectorText(self, selectorText):
        """
        wrapper for cssutils SelectorList object

        :param selectorText: of type string, might also be a comma separated list
            of selectors
        :Exceptions:
            - `NAMESPACE_ERR`: (Selector)
              Raised if the specified selector uses an unknown namespace
              prefix.
            - `SYNTAX_ERR`: (SelectorList, Selector)
              Raised if the specified CSS string value has a syntax error
              and is unparsable.
            - `NO_MODIFICATION_ALLOWED_ERR`: (self)
              Raised if this rule is readonly.
        """
        self._checkReadonly()
        self._selectorList.selectorText = selectorText

    selectorText = property(lambda self: self._selectorList.selectorText, 
                            _setSelectorText,
        doc="""(DOM) The textual representation of the selector for the
            rule set.""")

    def _setStyle(self, style):
        """
        :param style: CSSStyleDeclaration or string, only the cssText of a 
            declaration is used, not the actual object
        """
        self._checkReadonly()
        if isinstance(style, basestring):
            self._style.cssText = style
        else:
            # cssText would be serialized with optional preferences
            # so use _seq!
            self._style._seq = style._seq 

    style = property(lambda self: self._style, _setStyle,
        doc="(DOM) The declaration-block of this rule set.")

    wellformed = property(lambda self: self.selectorList.wellformed)

    def __repr__(self):
        if self._namespaces:
            st = (self.selectorText, self._namespaces)
        else:
            st = self.selectorText 
        return "cssutils.css.%s(selectorText=%r, style=%r)" % (
                self.__class__.__name__, st, self.style.cssText)

    def __str__(self):
        return "<cssutils.css.%s object selector=%r style=%r _namespaces=%r at 0x%x>" % (
                self.__class__.__name__, self.selectorText, self.style.cssText,
                self._namespaces, id(self))
