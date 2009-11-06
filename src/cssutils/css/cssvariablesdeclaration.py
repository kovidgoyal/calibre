"""CSSVariablesDeclaration
http://disruptive-innovations.com/zoo/cssvariables/#mozTocId496530
"""
__all__ = ['CSSVariablesDeclaration']
__docformat__ = 'restructuredtext'
__version__ = '$Id: cssstyledeclaration.py 1819 2009-08-01 20:52:43Z cthedot $'

from cssutils.prodparser import *
from cssvalue import CSSValue
import cssutils
import itertools
import xml.dom

class CSSVariablesDeclaration(cssutils.util._NewBase):
    """The CSSVariablesDeclaration interface represents a single block of
    variable declarations. 
    """
    def __init__(self, cssText=u'', parentRule=None, readonly=False):
        """
        :param cssText:
            Shortcut, sets CSSVariablesDeclaration.cssText
        :param parentRule:
            The CSS rule that contains this declaration block or
            None if this CSSVariablesDeclaration is not attached to a CSSRule.
        :param readonly:
            defaults to False
        """
        super(CSSVariablesDeclaration, self).__init__()
        self._parentRule = parentRule
        self._vars = {}
        if cssText:
            self.cssText = cssText
            
        self._readonly = readonly

    def __repr__(self):
        return "cssutils.css.%s(cssText=%r)" % (
                self.__class__.__name__, self.cssText)

    def __str__(self):
        return "<cssutils.css.%s object length=%r at 0x%x>" % (
                self.__class__.__name__, self.length, id(self))
        
    def __contains__(self, variableName):
        """Check if a variable is in variable declaration block.
        
        :param variableName:
            a string
        """
        return variableName.lower() in self.keys()
    
    def __getitem__(self, variableName):
        """Retrieve the value of variable ``variableName`` from this 
        declaration.
        """
        return self.getVariableValue(variableName.lower())
    
    def __setitem__(self, variableName, value):
        self.setVariable(variableName.lower(), value)

    def __delitem__(self, variableName):
        return self.removeVariable(variableName.lower())

    def __iter__(self):
        """Iterator of names of set variables."""
        for name in self.keys():
            yield name

    def _absorb(self, other):
        """Replace all own data with data from other object."""
        self._parentRule = other._parentRule
        self.seq.absorb(other.seq)
        self._readonly = other._readonly
        
    def keys(self):
        """Analoguous to standard dict returns variable names which are set in
        this declaration."""
        return self._vars.keys()
    
    def _getCssText(self):
        """Return serialized property cssText."""
        return cssutils.ser.do_css_CSSVariablesDeclaration(self)

    def _setCssText(self, cssText):
        """Setting this attribute will result in the parsing of the new value
        and resetting of all the properties in the declaration block
        including the removal or addition of properties.

        :exceptions:
            - :exc:`~xml.dom.NoModificationAllowedErr`:
              Raised if this declaration is readonly or a property is readonly.
            - :exc:`~xml.dom.SyntaxErr`:
              Raised if the specified CSS string value has a syntax error and
              is unparsable.

        Format::
        
            variableset
            : vardeclaration [ ';' S* vardeclaration ]*
            ;
            
            vardeclaration
            : varname ':' S* term
            ;
            
            varname
            : IDENT S*
            ;
            
            expr
            : [ VARCALL | term ] [ operator [ VARCALL | term ] ]*
            ;

        """
        self._checkReadonly()

        vardeclaration = Sequence(
            PreDef.ident(),
            PreDef.char(u':', u':', toSeq=False),
            #PreDef.S(toSeq=False, optional=True),
            Prod(name=u'term', match=lambda t, v: True,
                 toSeq=lambda t, tokens: (u'value', 
                                          CSSValue(itertools.chain([t], 
                                                                   tokens))
                 )
            ),
            PreDef.char(u';', u';', toSeq=False, optional=True),
        )
        prods = Sequence(vardeclaration, minmax=lambda: (0, None))
        # parse
        wellformed, seq, store, notused = \
            ProdParser().parse(cssText, 
                               u'CSSVariableDeclaration',
                               prods)
        if wellformed:
            newseq = self._tempSeq()

            # seq contains only name: value pairs plus comments etc
            lastname = None
            for item in seq:
                if u'IDENT' == item.type:
                    lastname = item
                    self._vars[lastname.value.lower()] = None
                elif u'value' == item.type:
                    self._vars[lastname.value.lower()] = item.value
                    newseq.append((lastname.value, item.value), 
                                  'var',
                                  lastname.line, lastname.col)
                else:
                    newseq.appendItem(item)

            self._setSeq(newseq)
            self.wellformed = True

                    
    cssText = property(_getCssText, _setCssText,
        doc="(DOM) A parsable textual representation of the declaration\
        block excluding the surrounding curly braces.")

    def _setParentRule(self, parentRule):
        self._parentRule = parentRule
    
    parentRule = property(lambda self: self._parentRule, _setParentRule,
                          doc="(DOM) The CSS rule that contains this"
                              " declaration block or None if this block"
                              " is not attached to a CSSRule.")

    def getVariableValue(self, variableName):
        """Used to retrieve the value of a variable if it has been explicitly
        set within this variable declaration block.
         
        :param variableName:
            The name of the variable.
        :returns:
            the value of the variable if it has been explicitly set in this
            variable declaration block. Returns the empty string if the
            variable has not been set.
        """
        try:
            return self._vars[variableName.lower()].cssText
        except KeyError, e:
            return u''

    def removeVariable(self, variableName):
        """Used to remove a variable if it has been explicitly set within this
        variable declaration block.

        :param variableName:
            The name of the variable.
        :returns:
            the value of the variable if it has been explicitly set for this
            variable declaration block. Returns the empty string if the
            variable has not been set.

        :exceptions:
            - :exc:`~xml.dom.NoModificationAllowedErr`:
              Raised if this declaration is readonly is readonly.
        """
        try:
            r = self._vars[variableName.lower()]
        except KeyError, e:
            return u''
        else: 
            self.seq._readonly = False
            if variableName in self._vars:
                for i, x in enumerate(self.seq):
                    if x.value[0] == variableName:
                        del self.seq[i]
            self.seq._readonly = True
            del self._vars[variableName.lower()]

        return r.cssText

    def setVariable(self, variableName, value):
        """Used to set a variable value within this variable declaration block.

        :param variableName:
            The name of the CSS variable. 
        :param value:
            The new value of the variable, may also be a CSSValue object.

        :exceptions:
            - :exc:`~xml.dom.SyntaxErr`:
              Raised if the specified value has a syntax error and is
              unparsable.
            - :exc:`~xml.dom.NoModificationAllowedErr`:
              Raised if this declaration is readonly or the property is
              readonly.
        """
        self._checkReadonly()
                
        # check name
        wellformed, seq, store, unused = ProdParser().parse(variableName.lower(),
                                                            u'variableName',
                                                            Sequence(PreDef.ident()
                                                                     ))
        if not wellformed:
            self._log.error(u'Invalid variableName: %r: %r'
                    % (variableName, value))
        else:
            # check value
            if isinstance(value, CSSValue):
                v = value 
            else:
                v = CSSValue(cssText=value)
                                
            if not v.wellformed:
                self._log.error(u'Invalid variable value: %r: %r'
                        % (variableName, value))
            else:
                # update seq
                self.seq._readonly = False
                if variableName in self._vars:
                    for i, x in enumerate(self.seq):
                        if x.value[0] == variableName:
                            x.replace(i, 
                                      [variableName, v], 
                                      x.type, 
                                      x.line,
                                      x.col)
                            break
                else:
                    self.seq.append([variableName, v], 'var')                
                self.seq._readonly = True
                self._vars[variableName] = v
                
                    

    def item(self, index):
        """Used to retrieve the variables that have been explicitly set in
        this variable declaration block. The order of the variables
        retrieved using this method does not have to be the order in which
        they were set. This method can be used to iterate over all variables
        in this variable declaration block.

        :param index:
            of the variable name to retrieve, negative values behave like
            negative indexes on Python lists, so -1 is the last element

        :returns:
            The name of the variable at this ordinal position. The empty
            string if no variable exists at this position.
        """
        try:
            return self.keys()[index]
        except IndexError:
            return u''

    length = property(lambda self: len(self._vars),
        doc="The number of variables that have been explicitly set in this"
            " variable declaration block. The range of valid indices is 0"
            " to length-1 inclusive.")
