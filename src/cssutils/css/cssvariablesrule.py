"""CSSVariables implements (and only partly) experimental 
`CSS Variables <http://disruptive-innovations.com/zoo/cssvariables/>`_
"""
__all__ = ['CSSVariablesRule']
__docformat__ = 'restructuredtext'
__version__ = '$Id: cssfontfacerule.py 1818 2009-07-30 21:39:00Z cthedot $'

from cssvariablesdeclaration import CSSVariablesDeclaration
import cssrule
import cssutils
import xml.dom

class CSSVariablesRule(cssrule.CSSRule):
    """
    The CSSVariablesRule interface represents a @variables rule within a CSS
    style sheet. The @variables rule is used to specify variables.

    cssutils uses a :class:`~cssutils.css.CSSVariablesDeclaration`  to
    represent the variables.
    """
    def __init__(self, mediaText=None, variables=None, parentRule=None, 
                 parentStyleSheet=None, readonly=False):
        """
        If readonly allows setting of properties in constructor only.
        """
        super(CSSVariablesRule, self).__init__(parentRule=parentRule, 
                                              parentStyleSheet=parentStyleSheet)
        self._atkeyword = u'@variables'
        self._media = cssutils.stylesheets.MediaList(mediaText, 
                                                     readonly=readonly)
        self._variables = CSSVariablesDeclaration(parentRule=self)
        if variables:
            self.variables = variables

        self._readonly = readonly
        
    def __repr__(self):
        return "cssutils.css.%s(mediaText=%r, variables=%r)" % (
                self.__class__.__name__, 
                self._media.mediaText, self.variables.cssText)

    def __str__(self):
        return "<cssutils.css.%s object mediaText=%r variables=%r valid=%r at 0x%x>" % (
                self.__class__.__name__, self._media.mediaText, 
                self.variables.cssText, self.valid, id(self))

    def _getCssText(self):
        """Return serialized property cssText."""
        return cssutils.ser.do_CSSVariablesRule(self)

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
              
        Format::
        
            variables
            : VARIABLES_SYM S* medium [ COMMA S* medium ]* LBRACE S* variableset* '}' S*
            ;
            
            variableset
            : LBRACE S* vardeclaration [ ';' S* vardeclaration ]* '}' S*
            ;
        """
        super(CSSVariablesRule, self)._setCssText(cssText)

        tokenizer = self._tokenize2(cssText)
        attoken = self._nexttoken(tokenizer, None)
        if self._type(attoken) != self._prods.VARIABLES_SYM:
            self._log.error(u'CSSVariablesRule: No CSSVariablesRule found: %s' %
                self._valuestr(cssText),
                error=xml.dom.InvalidModificationErr)
        else:
            # save if parse goes wrong
            oldvariables = CSSVariablesDeclaration()
            oldvariables._absorb(self.variables)
            
            ok = True
            beforetokens, brace = self._tokensupto2(tokenizer, 
                                                    blockstartonly=True,
                                                    separateEnd=True)            
            if self._tokenvalue(brace) != u'{':
                ok = False
                self._log.error(
                    u'CSSVariablesRule: No start { of variable declaration found: %r' %
                    self._valuestr(cssText), brace)
            
            # parse stuff before { which should be comments and S only
            new = {'wellformed': True}
            newseq = self._tempSeq()#[]
            
            beforewellformed, expected = self._parse(expected=':',
                seq=newseq, tokenizer=self._tokenize2(beforetokens),
                productions={})
            ok = ok and beforewellformed and new['wellformed']
    
            variablestokens, braceorEOFtoken = self._tokensupto2(tokenizer, 
                                                             blockendonly=True,
                                                             separateEnd=True)

            val, typ = self._tokenvalue(braceorEOFtoken), self._type(braceorEOFtoken)
            if val != u'}' and typ != 'EOF':
                ok = False
                self._log.error(
                    u'CSSVariablesRule: No "}" after variables declaration found: %r' %
                    self._valuestr(cssText))
                
            nonetoken = self._nexttoken(tokenizer)
            if nonetoken:
                ok = False
                self._log.error(u'CSSVariablesRule: Trailing content found.',
                                token=nonetoken)

            if 'EOF' == typ:
                # add again as variables needs it
                variablestokens.append(braceorEOFtoken)
            # may raise:
            self.variables.cssText = variablestokens

            if ok:
                # contains probably comments only upto {
                self._setSeq(newseq)
            else:
                # RESET
                self.variables._absorb(oldvariables)                

    cssText = property(_getCssText, _setCssText,
        doc="(DOM) The parsable textual representation of this rule.")

    def _setVariables(self, variables):
        """
        :param variables:
            a CSSVariablesDeclaration or string
        """
        self._checkReadonly()
        if isinstance(variables, basestring):
            self._variables.cssText = variables
        else:
            self._variables = variables
            self._variables.parentRule = self

    variables = property(lambda self: self._variables, _setVariables,
                     doc="(DOM) The variables of this rule set, "
                         "a :class:`~cssutils.css.CSSVariablesDeclaration`.")

    type = property(lambda self: self.VARIABLES_RULE, 
                    doc="The type of this rule, as defined by a CSSRule "
                        "type constant.")

    valid = property(lambda self: True, doc='TODO')
    
    # constant but needed:
    wellformed = property(lambda self: True)
