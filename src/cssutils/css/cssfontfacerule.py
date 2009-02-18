"""CSSFontFaceRule implements DOM Level 2 CSS CSSFontFaceRule.
"""
__all__ = ['CSSFontFaceRule']
__docformat__ = 'restructuredtext'
__version__ = '$Id: cssfontfacerule.py 1638 2009-01-13 20:39:33Z cthedot $'

from cssstyledeclaration import CSSStyleDeclaration
import cssrule
import cssutils
import xml.dom

class CSSFontFaceRule(cssrule.CSSRule):
    """
    The CSSFontFaceRule interface represents a @font-face rule in a CSS
    style sheet. The @font-face rule is used to hold a set of font 
    descriptions.

    Format::

        font_face
          : FONT_FACE_SYM S*
            '{' S* declaration [ ';' S* declaration ]* '}' S*
          ;
    """
    def __init__(self, style=None, parentRule=None, 
                 parentStyleSheet=None, readonly=False):
        """
        If readonly allows setting of properties in constructor only.

        :param style:
            CSSStyleDeclaration for this CSSStyleRule
        """
        super(CSSFontFaceRule, self).__init__(parentRule=parentRule, 
                                              parentStyleSheet=parentStyleSheet)
        self._atkeyword = u'@font-face'
        if style:
            self.style = style
        else:
            self._style = CSSStyleDeclaration(parentRule=self)
        
        self._readonly = readonly

    def __repr__(self):
        return "cssutils.css.%s(style=%r)" % (
                self.__class__.__name__, self.style.cssText)

    def __str__(self):
        return "<cssutils.css.%s object style=%r at 0x%x>" % (
                self.__class__.__name__, self.style.cssText, id(self))

    def _getCssText(self):
        """Return serialized property cssText."""
        return cssutils.ser.do_CSSFontFaceRule(self)

    def _setCssText(self, cssText):
        """
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
        super(CSSFontFaceRule, self)._setCssText(cssText)
        
        tokenizer = self._tokenize2(cssText)
        attoken = self._nexttoken(tokenizer, None)
        if self._type(attoken) != self._prods.FONT_FACE_SYM:
            self._log.error(u'CSSFontFaceRule: No CSSFontFaceRule found: %s' %
                self._valuestr(cssText),
                error=xml.dom.InvalidModificationErr)
        else:
            wellformed = True
            beforetokens, brace = self._tokensupto2(tokenizer, 
                                                    blockstartonly=True,
                                                    separateEnd=True)            
            if self._tokenvalue(brace) != u'{':
                wellformed = False
                self._log.error(
                    u'CSSFontFaceRule: No start { of style declaration found: %r' %
                    self._valuestr(cssText), brace)
            
            # parse stuff before { which should be comments and S only
            new = {'wellformed': True}
            newseq = self._tempSeq()#[]
            
            beforewellformed, expected = self._parse(expected=':',
                seq=newseq, tokenizer=self._tokenize2(beforetokens),
                productions={})
            wellformed = wellformed and beforewellformed and new['wellformed']
    
            styletokens, braceorEOFtoken = self._tokensupto2(tokenizer, 
                                                             blockendonly=True,
                                                             separateEnd=True)

            val, typ = self._tokenvalue(braceorEOFtoken), self._type(braceorEOFtoken)
            if val != u'}' and typ != 'EOF':
                wellformed = False
                self._log.error(
                    u'CSSFontFaceRule: No "}" after style declaration found: %r' %
                    self._valuestr(cssText))
                
            nonetoken = self._nexttoken(tokenizer)
            if nonetoken:
                wellformed = False
                self._log.error(u'CSSFontFaceRule: Trailing content found.',
                                token=nonetoken)

            newstyle = CSSStyleDeclaration()
            if 'EOF' == typ:
                # add again as style needs it
                styletokens.append(braceorEOFtoken)
            newstyle.cssText = styletokens

            if wellformed:
                self.style = newstyle
                self._setSeq(newseq) # contains (probably comments) upto { only

    cssText = property(_getCssText, _setCssText,
        doc="(DOM) The parsable textual representation of this rule.")

    def _setStyle(self, style):
        """
        :param style:
            a CSSStyleDeclaration or string
        """
        self._checkReadonly()
        if isinstance(style, basestring):
            self._style = CSSStyleDeclaration(parentRule=self, cssText=style)
        else:
            self._style._seq = style.seq

    style = property(lambda self: self._style, _setStyle,
                     doc="(DOM) The declaration-block of this rule set, "
                         "a :class:`~cssutils.css.CSSStyleDeclaration`.")

    type = property(lambda self: self.FONT_FACE_RULE, 
                    doc="The type of this rule, as defined by a CSSRule "
                        "type constant.")

    # constant but needed:
    wellformed = property(lambda self: True)
