"""CSSStyleRule implements DOM Level 2 CSS CSSStyleRule."""
__all__ = ['CSSStyleRule']
__docformat__ = 'restructuredtext'
__version__ = '$Id: cssstylerule.py 1868 2009-10-17 19:36:54Z cthedot $'

from cssstyledeclaration import CSSStyleDeclaration
from selectorlist import SelectorList
import cssrule
import cssutils
import xml.dom

class CSSStyleRule(cssrule.CSSRule):
    """The CSSStyleRule object represents a ruleset specified (if any) in a CSS
    style sheet. It provides access to a declaration block as well as to the
    associated group of selectors.
    
    Format::
    
        : selector [ COMMA S* selector ]*
        LBRACE S* declaration [ ';' S* declaration ]* '}' S*
        ;
    """
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

    def _getCssText(self):
        """Return serialized property cssText."""
        return cssutils.ser.do_CSSStyleRule(self)

    def _setCssText(self, cssText):
        """
        :param cssText:
            a parseable string or a tuple of (cssText, dict-of-namespaces)
        :exceptions:
            - :exc:`~xml.dom.NamespaceErr`:
              Raised if the specified selector uses an unknown namespace
              prefix.
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
            # save if parse goes wrong
            oldstyle = CSSStyleDeclaration()
            oldstyle._absorb(self.style)
            oldselector = SelectorList()
            oldselector._absorb(self.selectorList)

            ok = True
            
            bracetoken = selectortokens.pop()
            if self._tokenvalue(bracetoken) != u'{':
                ok = False
                self._log.error(
                    u'CSSStyleRule: No start { of style declaration found: %r' %
                    self._valuestr(cssText), bracetoken)
            elif not selectortokens:
                ok = False
                self._log.error(u'CSSStyleRule: No selector found: %r.' %
                            self._valuestr(cssText), bracetoken)
            # SET
            self.selectorList.selectorText = (selectortokens, 
                                              namespaces)
            if not styletokens:
                ok = False
                self._log.error(
                    u'CSSStyleRule: No style declaration or "}" found: %r' %
                    self._valuestr(cssText))
            else:
                braceorEOFtoken = styletokens.pop()
                val, typ = self._tokenvalue(braceorEOFtoken), self._type(braceorEOFtoken)
                if val != u'}' and typ != 'EOF':
                    ok = False
                    self._log.error(
                        u'CSSStyleRule: No "}" after style declaration found: %r' %
                        self._valuestr(cssText))
                else:
                    if 'EOF' == typ:
                        # add again as style needs it
                        styletokens.append(braceorEOFtoken)
                    
                    # SET
                    try:
                        self.style.cssText = styletokens
                    except:
                        # reset in case of error
                        self.selectorList._absorb(oldselector)
                        raise

            if not ok or not self.wellformed:
                # reset as not ok
                self.selectorList._absorb(oldselector)
                self.style._absorb(oldstyle)

    cssText = property(_getCssText, _setCssText,
        doc="(DOM) The parsable textual representation of this rule.")


    def __getNamespaces(self):
        "Uses children namespaces if not attached to a sheet, else the sheet's ones."
        try:
            return self.parentStyleSheet.namespaces
        except AttributeError:
            return self.selectorList._namespaces
            
    _namespaces = property(__getNamespaces, 
                           doc="If this Rule is attached to a CSSStyleSheet "
                               "the namespaces of that sheet are mirrored "
                               "here. While the Rule is not attached the "
                               "namespaces of selectorList are used.""")

    def _setSelectorList(self, selectorList):
        """
        :param selectorList: A SelectorList which replaces the current 
            selectorList object
        """
        self._checkReadonly()
        selectorList._parentRule = self
        self._selectorList = selectorList
            
    selectorList = property(lambda self: self._selectorList, _setSelectorList,
        doc="The SelectorList of this rule.")

    def _setSelectorText(self, selectorText):
        """
        wrapper for cssutils SelectorList object

        :param selectorText: 
            of type string, might also be a comma separated list
            of selectors
        :exceptions:
            - :exc:`~xml.dom.NamespaceErr`:
              Raised if the specified selector uses an unknown namespace
              prefix.
            - :exc:`~xml.dom.SyntaxErr`:
              Raised if the specified CSS string value has a syntax error
              and is unparsable.
            - :exc:`~xml.dom.NoModificationAllowedErr`:
              Raised if this rule is readonly.
        """
        self._checkReadonly()
        self._selectorList.selectorText = selectorText

    selectorText = property(lambda self: self._selectorList.selectorText, 
                            _setSelectorText,
                            doc="(DOM) The textual representation of the "
                                "selector for the rule set.")

    def _setStyle(self, style):
        """
        :param style: A string or CSSStyleDeclaration which replaces the 
            current style object.
        """
        self._checkReadonly()
        if isinstance(style, basestring):
            self._style.cssText = style
        else:
            style._parentRule = self
            self._style = style

    style = property(lambda self: self._style, _setStyle,
                     doc="(DOM) The declaration-block of this rule set.")

    type = property(lambda self: self.STYLE_RULE, 
                    doc="The type of this rule, as defined by a CSSRule "
                        "type constant.")

    wellformed = property(lambda self: self.selectorList.wellformed)
