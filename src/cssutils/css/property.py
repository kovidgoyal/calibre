"""Property is a single CSS property in a CSSStyleDeclaration

Internal use only, may be removed in the future!
"""
__all__ = ['Property']
__docformat__ = 'restructuredtext'
__version__ = '$Id: property.py 1444 2008-08-31 18:45:35Z cthedot $'

import xml.dom
import cssutils
#import cssproperties
from cssutils.profiles import profiles
from cssvalue import CSSValue
from cssutils.helper import Deprecated

class Property(cssutils.util.Base):
    """
    (cssutils) a CSS property in a StyleDeclaration of a CSSStyleRule

    Properties
    ==========
    cssText
        a parsable textual representation of this property
    name
        normalized name of the property, e.g. "color" when name is "c\olor"
        (since 0.9.5)
    literalname (since 0.9.5)
        original name of the property in the source CSS which is not normalized
        e.g. "C\\OLor"
    cssValue
        the relevant CSSValue instance for this property
    value
        the string value of the property, same as cssValue.cssText
    priority
        of the property (currently only u"important" or None)
    literalpriority
        original priority of the property in the source CSS which is not
        normalized e.g. "IM\portant"
    seqs
        combination of a list for seq of name, a CSSValue object, and
        a list for seq of  priority (empty or [!important] currently)
    valid
        if this Property is valid
    wellformed
        if this Property is syntactically ok

    DEPRECATED normalname (since 0.9.5)
        normalized name of the property, e.g. "color" when name is "c\olor"

    Format
    ======
    ::

        property = name
          : IDENT S*
          ;

        expr = value
          : term [ operator term ]*
          ;
        term
          : unary_operator?
            [ NUMBER S* | PERCENTAGE S* | LENGTH S* | EMS S* | EXS S* | ANGLE S* |
              TIME S* | FREQ S* | function ]
          | STRING S* | IDENT S* | URI S* | hexcolor
          ;
        function
          : FUNCTION S* expr ')' S*
          ;
        /*
         * There is a constraint on the color that it must
         * have either 3 or 6 hex-digits (i.e., [0-9a-fA-F])
         * after the "#"; e.g., "#000" is OK, but "#abcd" is not.
         */
        hexcolor
          : HASH S*
          ;

        prio
          : IMPORTANT_SYM S*
          ;

    """
    def __init__(self, name=None, value=None, priority=u'', _mediaQuery=False):
        """
        inits property

        name
            a property name string (will be normalized)
        value
            a property value string
        priority
            an optional priority string which currently must be u'',
            u'!important' or u'important'
        _mediaQuery boolean
            if True value is optional as used by MediaQuery objects
        """
        super(Property, self).__init__()

        self.seqs = [[], None, []]
        self.valid = False
        self.wellformed = False
        self._mediaQuery = _mediaQuery

        if name:
            self.name = name
        else:
            self._name = u''
            self._literalname = u''
            self.__normalname = u'' # DEPRECATED

        if value:
            self.cssValue = value
        else:
            self.seqs[1] = CSSValue()

        if priority:
            self.priority = priority
        else:
            self._priority = u''
            self._literalpriority = u''

    def _getCssText(self):
        """
        returns serialized property cssText
        """
        return cssutils.ser.do_Property(self)

    def _setCssText(self, cssText):
        """
        DOMException on setting

        - NO_MODIFICATION_ALLOWED_ERR: (CSSRule)
          Raised if the rule is readonly.
        - SYNTAX_ERR: (self)
          Raised if the specified CSS string value has a syntax error and
          is unparsable.
        """
        # check and prepare tokenlists for setting
        tokenizer = self._tokenize2(cssText)
        nametokens = self._tokensupto2(tokenizer, propertynameendonly=True)
        if nametokens:
            wellformed = True

            valuetokens = self._tokensupto2(tokenizer,
                                            propertyvalueendonly=True)
            prioritytokens = self._tokensupto2(tokenizer,
                                               propertypriorityendonly=True)

            if self._mediaQuery and not valuetokens:
                # MediaQuery may consist of name only
                self.name = nametokens
                self.cssValue = None
                self.priority = None
                return

            # remove colon from nametokens
            colontoken = nametokens.pop()
            if self._tokenvalue(colontoken) != u':':
                wellformed = False
                self._log.error(u'Property: No ":" after name found: %r' %
                                self._valuestr(cssText), colontoken)
            elif not nametokens:
                wellformed = False
                self._log.error(u'Property: No property name found: %r.' %
                            self._valuestr(cssText), colontoken)

            if valuetokens:
                if self._tokenvalue(valuetokens[-1]) == u'!':
                    # priority given, move "!" to prioritytokens
                    prioritytokens.insert(0, valuetokens.pop(-1))
            else:
                wellformed = False
                self._log.error(u'Property: No property value found: %r.' %
                                self._valuestr(cssText), colontoken)

            if wellformed:
                self.wellformed = True
                self.name = nametokens
                self.cssValue = valuetokens
                self.priority = prioritytokens

        else:
            self._log.error(u'Property: No property name found: %r.' %
                            self._valuestr(cssText))

    cssText = property(fget=_getCssText, fset=_setCssText,
        doc="A parsable textual representation.")

    def _setName(self, name):
        """
        DOMException on setting

        - SYNTAX_ERR: (self)
          Raised if the specified name has a syntax error and is
          unparsable.
        """
        # for closures: must be a mutable
        new = {'literalname': None,
               'wellformed': True}

        def _ident(expected, seq, token, tokenizer=None):
            # name
            if 'name' == expected:
                new['literalname'] = self._tokenvalue(token).lower()
                seq.append(new['literalname'])
                return 'EOF'
            else:
                new['wellformed'] = False
                self._log.error(u'Property: Unexpected ident.', token)
                return expected

        newseq = []
        wellformed, expected = self._parse(expected='name',
                                           seq=newseq,
                                           tokenizer=self._tokenize2(name),
                                           productions={'IDENT': _ident})
        wellformed = wellformed and new['wellformed']

        # post conditions
        # define a token for error logging
        if isinstance(name, list):
            token = name[0]
        else:
            token = None

        if not new['literalname']:
            wellformed = False
            self._log.error(u'Property: No name found: %r' %
                self._valuestr(name), token=token)

        if wellformed:
            self.wellformed = True
            self._literalname = new['literalname']
            self._name = self._normalize(self._literalname)
            self.__normalname = self._name # DEPRECATED
            self.seqs[0] = newseq

            # validate
            if self._name not in profiles.propertiesByProfile():
                self.valid = False
                tokenizer=self._tokenize2(name)
                self._log.warn(u'Property: Unknown Property: %r.' %
                         new['literalname'], token=token, neverraise=True)
            else:
                self.valid = True
                if self.cssValue:
                    self.cssValue._propertyName = self._name
                    self.valid = self.cssValue.valid
        else:
            self.wellformed = False

    name = property(lambda self: self._name, _setName,
        doc="Name of this property")

    literalname = property(lambda self: self._literalname,
        doc="Readonly literal (not normalized) name of this property")

    def _getCSSValue(self):
        return self.seqs[1]

    def _setCSSValue(self, cssText):
        """
        see css.CSSValue

        DOMException on setting?

        - SYNTAX_ERR: (self)
          Raised if the specified CSS string value has a syntax error
          (according to the attached property) or is unparsable.
        - TODO: INVALID_MODIFICATION_ERR:
          Raised if the specified CSS string value represents a different
          type of values than the values allowed by the CSS property.
        """
        if self._mediaQuery and not cssText:
            self.seqs[1] = CSSValue()
        else:
            if not self.seqs[1]:
                self.seqs[1] = CSSValue()

            cssvalue = self.seqs[1]
            cssvalue._propertyName = self.name
            cssvalue.cssText = cssText
            if cssvalue._value and cssvalue.wellformed:
                self.seqs[1] = cssvalue
            self.valid = self.valid and cssvalue.valid
            self.wellformed = self.wellformed and cssvalue.wellformed

    cssValue = property(_getCSSValue, _setCSSValue,
        doc="(cssutils) CSSValue object of this property")

    def _getValue(self):
        if self.cssValue:
            return self.cssValue._value
        else:
            return u''

    def _setValue(self, value):
        self.cssValue.cssText = value
        self.valid = self.valid and self.cssValue.valid
        self.wellformed = self.wellformed and self.cssValue.wellformed

    value = property(_getValue, _setValue,
                     doc="The textual value of this Properties cssValue.")

    def _setPriority(self, priority):
        """
        priority
            a string, currently either u'', u'!important' or u'important'

        Format
        ======
        ::

            prio
              : IMPORTANT_SYM S*
              ;

            "!"{w}"important"   {return IMPORTANT_SYM;}

        DOMException on setting

        - SYNTAX_ERR: (self)
          Raised if the specified priority has a syntax error and is
          unparsable.
          In this case a priority not equal to None, "" or "!{w}important".
          As CSSOM defines CSSStyleDeclaration.getPropertyPriority resulting in
          u'important' this value is also allowed to set a Properties priority
        """
        if self._mediaQuery:
            self._priority = u''
            self._literalpriority = u''
            if priority:
                self._log.error(u'Property: No priority in a MediaQuery - ignored.')
            return

        if isinstance(priority, basestring) and\
           u'important' == self._normalize(priority):
            priority = u'!%s' % priority

        # for closures: must be a mutable
        new = {'literalpriority': u'',
               'wellformed': True}

        def _char(expected, seq, token, tokenizer=None):
            # "!"
            val = self._tokenvalue(token)
            if u'!' == expected == val:
                seq.append(val)
                return 'important'
            else:
                new['wellformed'] = False
                self._log.error(u'Property: Unexpected char.', token)
                return expected

        def _ident(expected, seq, token, tokenizer=None):
            # "important"
            val = self._tokenvalue(token)
            normalval = self._tokenvalue(token, normalize=True)
            if 'important' == expected == normalval:
                new['literalpriority'] = val
                seq.append(val)
                return 'EOF'
            else:
                new['wellformed'] = False
                self._log.error(u'Property: Unexpected ident.', token)
                return expected

        newseq = []
        wellformed, expected = self._parse(expected='!',
                                           seq=newseq,
                                           tokenizer=self._tokenize2(priority),
                                           productions={'CHAR': _char,
                                                        'IDENT': _ident})
        wellformed = wellformed and new['wellformed']

        # post conditions
        if priority and not new['literalpriority']:
            wellformed = False
            self._log.info(u'Property: Invalid priority: %r.' %
                    self._valuestr(priority))

        if wellformed:
            self.wellformed = self.wellformed and wellformed
            self._literalpriority = new['literalpriority']
            self._priority = self._normalize(self.literalpriority)
            self.seqs[2] = newseq

            # validate
            if self._priority not in (u'', u'important'):
                self.valid = False
                self._log.info(u'Property: No CSS2 priority value: %r.' %
                    self._priority, neverraise=True)

    priority = property(lambda self: self._priority, _setPriority,
        doc="(cssutils) Priority of this property")

    literalpriority = property(lambda self: self._literalpriority,
        doc="Readonly literal (not normalized) priority of this property")

    def __repr__(self):
        return "cssutils.css.%s(name=%r, value=%r, priority=%r)" % (
                self.__class__.__name__,
                self.literalname, self.cssValue.cssText, self.priority)

    def __str__(self):
        return "<%s.%s object name=%r value=%r priority=%r at 0x%x>" % (
                self.__class__.__module__, self.__class__.__name__,
                self.name, self.cssValue.cssText, self.priority, id(self))

    @Deprecated(u'Use property ``name`` instead (since cssutils 0.9.5).')
    def _getNormalname(self):
        return self.__normalname
    normalname = property(_getNormalname,
                          doc="DEPRECATED since 0.9.5, use name instead")