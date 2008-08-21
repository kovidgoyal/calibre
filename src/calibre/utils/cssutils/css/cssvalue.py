"""CSSValue related classes

- CSSValue implements DOM Level 2 CSS CSSValue
- CSSPrimitiveValue implements DOM Level 2 CSS CSSPrimitiveValue
- CSSValueList implements DOM Level 2 CSS CSSValueList

"""
__all__ = ['CSSValue', 'CSSPrimitiveValue', 'CSSValueList']
__docformat__ = 'restructuredtext'
__version__ = '$Id: cssvalue.py 1228 2008-05-19 19:59:50Z cthedot $'

import re
import xml.dom
import cssutils
import cssproperties

class CSSValue(cssutils.util.Base):
    """
    The CSSValue interface represents a simple or a complex value.
    A CSSValue object only occurs in a context of a CSS property

    Properties
    ==========
    cssText
        A string representation of the current value.
    cssValueType
        A (readonly) code defining the type of the value.

    seq: a list (cssutils)
        All parts of this style declaration including CSSComments
    valid: boolean
        if the value is valid at all, False for e.g. color: #1
    wellformed
        if this Property is syntactically ok

    _value (INTERNAL!)
        value without any comments, used to validate
    """

    CSS_INHERIT = 0
    """
    The value is inherited and the cssText contains "inherit".
    """
    CSS_PRIMITIVE_VALUE = 1
    """
    The value is a primitive value and an instance of the
    CSSPrimitiveValue interface can be obtained by using binding-specific
    casting methods on this instance of the CSSValue interface.
    """
    CSS_VALUE_LIST = 2
    """
    The value is a CSSValue list and an instance of the CSSValueList
    interface can be obtained by using binding-specific casting
    methods on this instance of the CSSValue interface.
    """
    CSS_CUSTOM = 3
    """
    The value is a custom value.
    """
    _typestrings = ['CSS_INHERIT' , 'CSS_PRIMITIVE_VALUE', 'CSS_VALUE_LIST',
                     'CSS_CUSTOM']

    def __init__(self, cssText=None, readonly=False, _propertyName=None):
        """
        inits a new CSS Value

        cssText
            the parsable cssText of the value
        readonly
            defaults to False
        property
            used to validate this value in the context of a property
        """
        super(CSSValue, self).__init__()

        self.seq = []
        self.valid = False
        self.wellformed = False
        self._valueValue = u''
        self._linetoken = None # used for line report only
        self._propertyName = _propertyName

        if cssText is not None: # may be 0
            if type(cssText) in (int, float):
                cssText = unicode(cssText) # if it is a number
            self.cssText = cssText

        self._readonly = readonly

    def _getValue(self):
        v = []
        for x in self.seq:
            if isinstance(x, cssutils.css.CSSComment):
                continue
            elif isinstance(x, basestring):
                v.append(x)
            else: # maybe CSSPrimitiveValue
                v.append(x.cssText)
        if v and u'' == v[-1].strip():
            # simple strip of joined string does not work for escaped spaces
            del v[-1]
        return u''.join(v)

    def _setValue(self, value):
        "overwritten by CSSValueList!"
        self._valueValue = value

    _value = property(_getValue, _setValue,
                doc="Actual cssText value of this CSSValue.")

    def _getCssText(self):
        return cssutils.ser.do_css_CSSValue(self)

    def _setCssText(self, cssText):
        """
        Format
        ======
        ::
        
            unary_operator
              : '-' | '+'
              ;
            operator
              : '/' S* | ',' S* | /* empty */
              ;
            expr
              : term [ operator term ]*
              ;
            term
              : unary_operator?
                [ NUMBER S* | PERCENTAGE S* | LENGTH S* | EMS S* | EXS S* | ANGLE S* |
                  TIME S* | FREQ S* ]
              | STRING S* | IDENT S* | URI S* | hexcolor | function
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

        DOMException on setting

        - SYNTAX_ERR: (self)
          Raised if the specified CSS string value has a syntax error
          (according to the attached property) or is unparsable.
        - TODO: INVALID_MODIFICATION_ERR:
          Raised if the specified CSS string value represents a different
          type of values than the values allowed by the CSS property.
        - NO_MODIFICATION_ALLOWED_ERR: (self)
          Raised if this value is readonly.
        """
        self._checkReadonly()

        # for closures: must be a mutable
        new = {'values': [], 
               'commas': 0, 
               'valid': True,
               'wellformed': True }

        def _S(expected, seq, token, tokenizer=None):
            val = self._tokenvalue(token)
            if expected.endswith('operator'):
                seq.append(u' ')
                return 'term or operator'
            elif expected.endswith('S'):
                return 'term or S'
            else:
                return expected

        def _char(expected, seq, token, tokenizer=None):
            val = self._tokenvalue(token)
            if 'funcend' == expected and u')' == val:
                # end of FUNCTION
                seq[-1] += val
                new['values'].append(seq[-1])
                return 'operator'

            elif expected in (')', ']', '}') and expected == val:
                # end of any block: (), [], {}
                seq[-1] += val
                return 'operator'

            elif expected in ('funcend', ')', ']', '}'):
                # content of func or block: (), [], {}
                seq[-1] += val
                return expected

            elif expected.endswith('operator') and ',' == val:
                # term , term
                new['commas'] += 1
                if seq and seq[-1] == u' ':
                    seq[-1] = val
                else:
                    seq.append(val)
                return 'term or S'

            elif expected.endswith('operator') and '/' == val:
                # term / term
                if seq and seq[-1] == u' ':
                    seq[-1] = val
                else:
                    seq.append(val)
                return 'term or S'

            elif expected.startswith('term') and u'(' == val:
                # start of ( any* ) block
                seq.append(val)
                return ')'
            elif expected.startswith('term') and u'[' == val:
                # start of [ any* ] block
                seq.append(val)
                return ']'
            elif expected.startswith('term') and u'{' == val:
                # start of { any* } block
                seq.append(val)
                return '}'
            elif expected.startswith('term') and u'-' == val or u'+' == 'val':
                # unary operator
                seq.append(val)
                new['values'].append(val)
                return 'number percentage dimension'
            elif expected.startswith('term') and u'/' == val:
                # font-size/line-height separator
                seq.append(val)
                new['values'].append(val)
                return 'number percentage dimension'
            else:
                new['wellformed'] = False
                self._log.error(u'CSSValue: Unexpected char.', token)
                return expected

        def _number_percentage_dimension(expected, seq, token, tokenizer=None):
            # NUMBER PERCENTAGE DIMENSION after -/+ or operator
            if expected.startswith('term') or expected == 'number percentage dimension':
                # normal value
                val = self._tokenvalue(token)
                if new['values'] and new['values'][-1] in (u'-', u'+'):
                    new['values'][-1] += val
                else:
                    new['values'].append(val)
                seq.append(val)
                return 'operator'
            elif 'operator' == expected:
                # expected S but token which is ok
                val = self._tokenvalue(token)
                if new['values'] and new['values'][-1] in (u'-', u'+'):
                    new['values'][-1] += val
                else:
                    new['values'].append(u' ')
                    seq.append(u' ')
                    new['values'].append(val)
                seq.append(val)
                return 'operator'
            elif expected in ('funcend', ')', ']', '}'):
                # a block
                seq[-1] += self._tokenvalue(token)
                return expected
            else:
                new['wellformed'] = False
                self._log.error(u'CSSValue: Unexpected token.', token)
                return expected

        def _string_ident_uri_hexcolor(expected, seq, token, tokenizer=None):
            # STRING IDENT URI HASH
            if expected.startswith('term'):
                # normal value
                
                # TODO: use actual values, probably needs Base2 for this                
                typ = self._type(token)
                if self._prods.STRING == typ:
                    val = u'"%s"' % self._stringtokenvalue(token)
#                elif 'URI' == typ:
#                    val = u'url(%s)' % self._uritokenvalue(token)
                else:
                    val = self._tokenvalue(token)
                
                new['values'].append(val)
                seq.append(val)
                return 'operator'
            elif 'operator' == expected:
                # expected S but still ok
                
                # TODO: use actual values, probably needs Base2 for this                
                typ = self._type(token)
                if self._prods.STRING == typ:
                    val = u'"%s"' % self._stringtokenvalue(token)
#                elif 'URI' == typ:
#                    val = u'url(%s)' % self._uritokenvalue(token)
                else:
                    val = self._tokenvalue(token)
                new['values'].append(u' ')
                new['values'].append(val)
                seq.append(u' ')
                seq.append(val)
                return 'operator'
            elif expected in ('funcend', ')', ']', '}'):
                # a block
                seq[-1] += self._tokenvalue(token)
                return expected
            else:
                new['wellformed'] = False
                self._log.error(u'CSSValue: Unexpected token.', token)
                return expected

        def _function(expected, seq, token, tokenizer=None):
            # FUNCTION
            if expected.startswith('term'):
                # normal value but add if funcend if found
                seq.append(self._tokenvalue(token))
                return 'funcend'
            elif 'operator' == expected:
                # normal value but add if funcend if found
                seq.append(u' ')
                seq.append(self._tokenvalue(token))
                return 'funcend'
            elif expected in ('funcend', ')', ']', '}'):
                # a block
                seq[-1] += self._tokenvalue(token)
                return expected
            else:
                new['wellformed'] = False
                self._log.error(u'CSSValue: Unexpected token.', token)
                return expected

        tokenizer = self._tokenize2(cssText)

        linetoken = self._nexttoken(tokenizer)
        if not linetoken:
            self._log.error(u'CSSValue: Unknown syntax or no value: %r.' %
                self._valuestr(cssText))
        else:
            # TODO: not very efficient tokenizing twice!
            tokenizer = self._tokenize2(cssText)
            newseq = []
            wellformed, expected = self._parse(expected='term',
                seq=newseq, tokenizer=tokenizer,
                productions={'S': _S,
                             'CHAR': _char,

                             'NUMBER': _number_percentage_dimension,
                             'PERCENTAGE': _number_percentage_dimension,
                             'DIMENSION': _number_percentage_dimension,

                             'STRING': _string_ident_uri_hexcolor,
                             'IDENT': _string_ident_uri_hexcolor,
                             'URI': _string_ident_uri_hexcolor,
                             'HASH': _string_ident_uri_hexcolor,
                             'UNICODE-RANGE': _string_ident_uri_hexcolor, #?

                             'FUNCTION': _function
                              })

            wellformed = wellformed and new['wellformed']

            # post conditions
            if expected.startswith('term') and newseq and newseq[-1] != u' '  or (
               expected in ('funcend', ')', ']', '}')):
                wellformed = False
                self._log.error(u'CSSValue: Incomplete value: %r.' %
                self._valuestr(cssText))

            if not new['values']:
                wellformed = False
                self._log.error(u'CSSValue: Unknown syntax or no value: %r.' %
                self._valuestr(cssText))

            else:
                self._linetoken = linetoken # used for line report
                self.seq = newseq
                self.valid = False

                self._validate()

                if len(new['values']) == 1 and new['values'][0] == u'inherit':
                    self._value = u'inherit'
                    self._cssValueType = CSSValue.CSS_INHERIT
                    self.__class__ = CSSValue # reset
                elif len(new['values']) == 1:
                    self.__class__ = CSSPrimitiveValue
                    self._init() #inits CSSPrimitiveValue
                elif len(new['values']) > 1 and\
                     len(new['values']) == new['commas'] + 1:
                    # e.g. value for font-family: a, b
                    self.__class__ = CSSPrimitiveValue
                    self._init() #inits CSSPrimitiveValue
                elif len(new['values']) > 1:
                    # separated by S
                    self.__class__ = CSSValueList
                    self._init() # inits CSSValueList
                else:
                    self._cssValueType = CSSValue.CSS_CUSTOM
                    self.__class__ = CSSValue # reset
                    
            self.wellformed = wellformed

    cssText = property(_getCssText, _setCssText,
        doc="A string representation of the current value.")

    def _getCssValueType(self):
        if hasattr(self, '_cssValueType'):
            return self._cssValueType

    cssValueType = property(_getCssValueType,
        doc="A (readonly) code defining the type of the value as defined above.")

    def _getCssValueTypeString(self):
        t = self.cssValueType
        if t is not None: # may be 0!
            return CSSValue._typestrings[t]
        else:
            return None

    cssValueTypeString = property(_getCssValueTypeString,
        doc="cssutils: Name of cssValueType of this CSSValue (readonly).")

    def _validate(self):
        """
        validates value against _propertyName context if given
        """
        if self._value:
            if self._propertyName in cssproperties.cssvalues:
                if cssproperties.cssvalues[self._propertyName](self._value):
                    self.valid = True
                else:
                    self.valid = False
                    self._log.warn(
                        u'CSSValue: Invalid value for CSS2 property %r: %r' %
                        (self._propertyName, self._value), neverraise=True)
            else:
                self._log.debug(
                    u'CSSValue: Unable to validate as no or unknown property context set for this value: %r'
                    % self._value, neverraise=True)

    def _get_propertyName(self):
        return self.__propertyName

    def _set_propertyName(self, _propertyName):
        self.__propertyName = _propertyName
        self._validate()
    
    _propertyName = property(_get_propertyName, _set_propertyName,
        doc="cssutils: Property this values is validated against") 

    def __repr__(self):
        return "cssutils.css.%s(%r, _propertyName=%r)" % (
                self.__class__.__name__, self.cssText, self._propertyName)

    def __str__(self):
        return "<cssutils.css.%s object cssValueType=%r cssText=%r propname=%r valid=%r at 0x%x>" % (
                self.__class__.__name__, self.cssValueTypeString,
                self.cssText, self._propertyName, self.valid, id(self))


class CSSPrimitiveValue(CSSValue):
    """
    represents a single CSS Value.  May be used to determine the value of a
    specific style property currently set in a block or to set a specific
    style property explicitly within the block. Might be obtained from the
    getPropertyCSSValue method of CSSStyleDeclaration.

    Conversions are allowed between absolute values (from millimeters to
    centimeters, from degrees to radians, and so on) but not between
    relative values. (For example, a pixel value cannot be converted to a
    centimeter value.) Percentage values can't be converted since they are
    relative to the parent value (or another property value). There is one
    exception for color percentage values: since a color percentage value
    is relative to the range 0-255, a color percentage value can be
    converted to a number; (see also the RGBColor interface).
    """
    # constant: type of this CSSValue class
    cssValueType = CSSValue.CSS_PRIMITIVE_VALUE

    # An integer indicating which type of unit applies to the value.
    CSS_UNKNOWN = 0 # only obtainable via cssText
    CSS_NUMBER = 1
    CSS_PERCENTAGE = 2
    CSS_EMS = 3
    CSS_EXS = 4
    CSS_PX = 5
    CSS_CM = 6
    CSS_MM = 7
    CSS_IN = 8
    CSS_PT = 9
    CSS_PC = 10
    CSS_DEG = 11
    CSS_RAD = 12
    CSS_GRAD = 13
    CSS_MS = 14
    CSS_S = 15
    CSS_HZ = 16
    CSS_KHZ = 17
    CSS_DIMENSION = 18
    CSS_STRING = 19
    CSS_URI = 20
    CSS_IDENT = 21
    CSS_ATTR = 22
    CSS_COUNTER = 23
    CSS_RECT = 24
    CSS_RGBCOLOR = 25
    # NOT OFFICIAL:
    CSS_RGBACOLOR = 26

    _floattypes = [CSS_NUMBER, CSS_PERCENTAGE, CSS_EMS, CSS_EXS,
                   CSS_PX, CSS_CM, CSS_MM, CSS_IN, CSS_PT, CSS_PC,
                   CSS_DEG, CSS_RAD, CSS_GRAD, CSS_MS, CSS_S,
                   CSS_HZ, CSS_KHZ, CSS_DIMENSION
                   ]
    _stringtypes = [CSS_ATTR, CSS_IDENT, CSS_STRING, CSS_URI]
    _countertypes = [CSS_COUNTER]
    _recttypes = [CSS_RECT]
    _rbgtypes = [CSS_RGBCOLOR, CSS_RGBACOLOR]

    _reNumDim = re.compile(ur'^(.*?)([a-z]+|%)$', re.I| re.U|re.X)

    # oldtype: newType: converterfunc
    _converter = {
        # cm <-> mm <-> in, 1 inch is equal to 2.54 centimeters.
        # pt <-> pc, the points used by CSS 2.1 are equal to 1/72nd of an inch.
        # pc: picas - 1 pica is equal to 12 points
        (CSS_CM, CSS_MM): lambda x: x * 10,
        (CSS_MM, CSS_CM): lambda x: x / 10,

        (CSS_PT, CSS_PC): lambda x: x * 12,
        (CSS_PC, CSS_PT): lambda x: x / 12,

        (CSS_CM, CSS_IN): lambda x: x / 2.54,
        (CSS_IN, CSS_CM): lambda x: x * 2.54,
        (CSS_MM, CSS_IN): lambda x: x / 25.4,
        (CSS_IN, CSS_MM): lambda x: x * 25.4,

        (CSS_IN, CSS_PT): lambda x: x / 72,
        (CSS_PT, CSS_IN): lambda x: x * 72,
        (CSS_CM, CSS_PT): lambda x: x / 2.54 / 72,
        (CSS_PT, CSS_CM): lambda x: x * 72 * 2.54,
        (CSS_MM, CSS_PT): lambda x: x / 25.4 / 72,
        (CSS_PT, CSS_MM): lambda x: x * 72 * 25.4,

        (CSS_IN, CSS_PC): lambda x: x / 72 / 12,
        (CSS_PC, CSS_IN): lambda x: x * 12 * 72,
        (CSS_CM, CSS_PC): lambda x: x / 2.54 / 72 / 12,
        (CSS_PC, CSS_CM): lambda x: x * 12 * 72 * 2.54,
        (CSS_MM, CSS_PC): lambda x: x / 25.4 / 72 / 12,
        (CSS_PC, CSS_MM): lambda x: x * 12 * 72 * 25.4,

        # hz <-> khz
        (CSS_KHZ, CSS_HZ): lambda x: x * 1000,
        (CSS_HZ, CSS_KHZ): lambda x: x / 1000,
        # s <-> ms
        (CSS_S, CSS_MS): lambda x: x * 1000,
        (CSS_MS, CSS_S): lambda x: x / 1000

        # TODO: convert deg <-> rad <-> grad
    }

    def __init__(self, cssText=None, readonly=False, _propertyName=None):
        """
        see CSSPrimitiveValue.__init__()
        """
        super(CSSPrimitiveValue, self).__init__(cssText=cssText,
                                       readonly=readonly,
                                       _propertyName=_propertyName)

        #(String representation for unit types, token type of unit type, detail)
        # used to detect primitiveType and for __repr__
        self._init()

    def _init(self):
        # _unitinfos must be set here as self._prods is not known before
        self._unitinfos = [
            ('CSS_UNKNOWN', None, None),
            ('CSS_NUMBER', self._prods.NUMBER, None),
            ('CSS_PERCENTAGE', self._prods.PERCENTAGE, None),
            ('CSS_EMS', self._prods.DIMENSION, 'em'),
            ('CSS_EXS', self._prods.DIMENSION, 'ex'),
            ('CSS_PX', self._prods.DIMENSION, 'px'),
            ('CSS_CM', self._prods.DIMENSION, 'cm'),
            ('CSS_MM', self._prods.DIMENSION, 'mm'),
            ('CSS_IN', self._prods.DIMENSION, 'in'),
            ('CSS_PT', self._prods.DIMENSION, 'pt'),
            ('CSS_PC', self._prods.DIMENSION, 'pc'),
            ('CSS_DEG', self._prods.DIMENSION, 'deg'),
            ('CSS_RAD', self._prods.DIMENSION, 'rad'),
            ('CSS_GRAD', self._prods.DIMENSION, 'grad'),
            ('CSS_MS', self._prods.DIMENSION, 'ms'),
            ('CSS_S', self._prods.DIMENSION, 's'),
            ('CSS_HZ', self._prods.DIMENSION, 'hz'),
            ('CSS_KHZ', self._prods.DIMENSION, 'khz'),
            ('CSS_DIMENSION', self._prods.DIMENSION, None),
            ('CSS_STRING', self._prods.STRING, None),
            ('CSS_URI', self._prods.URI, None),
            ('CSS_IDENT', self._prods.IDENT, None),
            ('CSS_ATTR', self._prods.FUNCTION, 'attr('),
            ('CSS_COUNTER', self._prods.FUNCTION, 'counter('),
            ('CSS_RECT', self._prods.FUNCTION, 'rect('),
            ('CSS_RGBCOLOR', self._prods.FUNCTION, 'rgb('),
            ('CSS_RGBACOLOR', self._prods.FUNCTION, 'rgba('),
            ]

    def __set_primitiveType(self):
        """
        primitiveType is readonly but is set lazy if accessed
        no value is given as self._value is used
        """
        primitiveType = self.CSS_UNKNOWN
        _floatType = False # if unary expect NUMBER DIMENSION or PERCENTAGE
        tokenizer = self._tokenize2(self._value)
        t = self._nexttoken(tokenizer)
        if not t:
            self._log.error(u'CSSPrimitiveValue: No value.')

        # unary operator:
        if self._tokenvalue(t) in (u'-', u'+'):
            t = self._nexttoken(tokenizer)
            if not t:
                self._log.error(u'CSSPrimitiveValue: No value.')

            _floatType = True

        # check for font1, "font2" etc which is treated as ONE string
        fontstring = 0 # should be at leayst 2
        expected = 'ident or string'
        tokenizer = self._tokenize2(self._value) # add used tokens again
        for token in tokenizer:
            val, typ = self._tokenvalue(token, normalize=True), self._type(token)
            if expected == 'ident or string' and typ in (
                        self._prods.IDENT, self._prods.STRING):
                expected = 'comma'
                fontstring += 1
            elif expected == 'comma' and val == ',':
                expected = 'ident or string'
                fontstring += 1
            elif typ in (self._prods.S, self._prods.COMMENT):
                continue
            else:
                fontstring = False
                break

        if fontstring > 2:
            # special case: e.g. for font-family: a, b; only COMMA IDENT and STRING
            primitiveType = CSSPrimitiveValue.CSS_STRING
        elif self._type(t) == self._prods.HASH:
            # special case, maybe should be converted to rgb in any case?
            primitiveType = CSSPrimitiveValue.CSS_RGBCOLOR
        else:
            for i, (name, tokentype, search) in enumerate(self._unitinfos):
                val, typ = self._tokenvalue(t, normalize=True), self._type(t)
                if typ == tokentype:
                    if typ == self._prods.DIMENSION:
                        if not search:
                            primitiveType = i
                            break
                        elif re.match(ur'^[^a-z]*(%s)$' % search, val):
                            primitiveType = i
                            break
                    elif typ == self._prods.FUNCTION:
                        if not search:
                            primitiveType = i
                            break
                        elif val.startswith(search):
                            primitiveType = i
                            break
                    else:
                        primitiveType = i
                        break

        if _floatType and primitiveType not in self._floattypes:
            # - or + only expected before floattype
            primitiveType = self.CSS_UNKNOWN

        self._primitiveType = primitiveType

    def _getPrimitiveType(self):
        if not hasattr(self, '_primitivetype'):
            self.__set_primitiveType()
        return self._primitiveType

    primitiveType = property(_getPrimitiveType,
        doc="READONLY: The type of the value as defined by the constants specified above.")

    def _getPrimitiveTypeString(self):
        return self._unitinfos[self.primitiveType][0]

    primitiveTypeString = property(_getPrimitiveTypeString,
                                   doc="Name of primitive type of this value.")

    def _getCSSPrimitiveTypeString(self, type):
        "get TypeString by given type which may be unknown, used by setters"
        try:
            return self._unitinfos[type][0]
        except (IndexError, TypeError):
            return u'%r (UNKNOWN TYPE)' % type

    def __getValDim(self):
        "splits self._value in numerical and dimension part"
        try:
            val, dim = self._reNumDim.findall(self._value)[0]
        except IndexError:
            val, dim = self._value, u''
        try:
            val = float(val)
        except ValueError:
            raise xml.dom.InvalidAccessErr(
                u'CSSPrimitiveValue: No float value %r'
                % (self._value))

        return val, dim

    def getFloatValue(self, unitType):
        """
        (DOM method) This method is used to get a float value in a
        specified unit. If this CSS value doesn't contain a float value
        or can't be converted into the specified unit, a DOMException
        is raised.

        unitType
            to get the float value. The unit code can only be a float unit type
            (i.e. CSS_NUMBER, CSS_PERCENTAGE, CSS_EMS, CSS_EXS, CSS_PX, CSS_CM,
            CSS_MM, CSS_IN, CSS_PT, CSS_PC, CSS_DEG, CSS_RAD, CSS_GRAD, CSS_MS,
            CSS_S, CSS_HZ, CSS_KHZ, CSS_DIMENSION).

        returns not necessarily a float but some cases just an int
        e.g. if the value is ``1px`` it return ``1`` and **not** ``1.0``

        conversions might return strange values like 1.000000000001
        """
        if unitType not in self._floattypes:
            raise xml.dom.InvalidAccessErr(
                u'unitType Parameter is not a float type')

        val, dim = self.__getValDim()

        if self.primitiveType != unitType:
            try:
                val = self._converter[self.primitiveType, unitType](val)
            except KeyError:
                raise xml.dom.InvalidAccessErr(
                u'CSSPrimitiveValue: Cannot coerce primitiveType %r to %r'
                % (self.primitiveTypeString,
                   self._getCSSPrimitiveTypeString(unitType)))

        if val == int(val):
            val = int(val)

        return val

    def setFloatValue(self, unitType, floatValue):
        """
        (DOM method) A method to set the float value with a specified unit.
        If the property attached with this value can not accept the
        specified unit or the float value, the value will be unchanged and
        a DOMException will be raised.

        unitType
            a unit code as defined above. The unit code can only be a float
            unit type
        floatValue
            the new float value which does not have to be a float value but
            may simple be an int e.g. if setting::

                setFloatValue(CSS_PX, 1)

        raises DOMException
            - INVALID_ACCESS_ERR: Raised if the attached property doesn't
                support the float value or the unit type.
            - NO_MODIFICATION_ALLOWED_ERR: Raised if this property is readonly.
        """
        self._checkReadonly()
        if unitType not in self._floattypes:
            raise xml.dom.InvalidAccessErr(
               u'CSSPrimitiveValue: unitType %r is not a float type' %
               self._getCSSPrimitiveTypeString(unitType))
        try:
            val = float(floatValue)
        except ValueError, e:
            raise xml.dom.InvalidAccessErr(
               u'CSSPrimitiveValue: floatValue %r is not a float' %
               floatValue)

        oldval, dim = self.__getValDim()

        if self.primitiveType != unitType:
            # convert if possible
            try:
                val = self._converter[
                    unitType, self.primitiveType](val)
            except KeyError:
                raise xml.dom.InvalidAccessErr(
                u'CSSPrimitiveValue: Cannot coerce primitiveType %r to %r'
                % (self.primitiveTypeString,
                   self._getCSSPrimitiveTypeString(unitType)))

        if val == int(val):
            val = int(val)

        self.cssText = '%s%s' % (val, dim)

    def getStringValue(self):
        """
        (DOM method) This method is used to get the string value. If the
        CSS value doesn't contain a string value, a DOMException is raised.

        Some properties (like 'font-family' or 'voice-family')
        convert a whitespace separated list of idents to a string.

        Only the actual value is returned so e.g. all the following return the
        actual value ``a``: url(a), attr(a), "a", 'a'
        """
        if self.primitiveType not in self._stringtypes:
            raise xml.dom.InvalidAccessErr(
                u'CSSPrimitiveValue %r is not a string type'
                % self.primitiveTypeString)

        if CSSPrimitiveValue.CSS_STRING == self.primitiveType:
            # _stringtokenvalue expects tuple with at least 2
            return self._stringtokenvalue((None,self._value))
        elif CSSPrimitiveValue.CSS_URI == self.primitiveType:
            # _uritokenvalue expects tuple with at least 2
            return self._uritokenvalue((None, self._value)) 
        elif CSSPrimitiveValue.CSS_ATTR == self.primitiveType:
            return self._value[5:-1]
        else:
            return self._value

    def setStringValue(self, stringType, stringValue):
        """
        (DOM method) A method to set the string value with the specified
        unit. If the property attached to this value can't accept the
        specified unit or the string value, the value will be unchanged and
        a DOMException will be raised.

        stringType
            a string code as defined above. The string code can only be a
            string unit type (i.e. CSS_STRING, CSS_URI, CSS_IDENT, and
            CSS_ATTR).
        stringValue
            the new string value
            Only the actual value is expected so for (CSS_URI, "a") the
            new value will be ``url(a)``. For (CSS_STRING, "'a'")
            the new value will be ``"\\'a\\'"`` as the surrounding ``'`` are
            not part of the string value

        raises
            DOMException
            
            - INVALID_ACCESS_ERR: Raised if the CSS value doesn't contain a 
              string value or if the string value can't be converted into
              the specified unit.
              
            - NO_MODIFICATION_ALLOWED_ERR: Raised if this property is readonly.
        """
        self._checkReadonly()
        # self not stringType
        if self.primitiveType not in self._stringtypes:
            raise xml.dom.InvalidAccessErr(
                u'CSSPrimitiveValue %r is not a string type'
                % self.primitiveTypeString)
        # given stringType is no StringType
        if stringType not in self._stringtypes:
            raise xml.dom.InvalidAccessErr(
                u'CSSPrimitiveValue: stringType %s is not a string type'
                % self._getCSSPrimitiveTypeString(stringType))

        if self._primitiveType != stringType:
            raise xml.dom.InvalidAccessErr(
                u'CSSPrimitiveValue: Cannot coerce primitiveType %r to %r'
                % (self.primitiveTypeString,
                   self._getCSSPrimitiveTypeString(stringType)))

        if CSSPrimitiveValue.CSS_STRING == self._primitiveType:
            self.cssText = u'"%s"' % stringValue.replace(u'"', ur'\\"')
        elif CSSPrimitiveValue.CSS_URI == self._primitiveType:
            # Some characters appearing in an unquoted URI, such as
            # parentheses, commas, whitespace characters, single quotes
            # (') and double quotes ("), must be escaped with a backslash
            # so that the resulting URI value is a URI token:
            # '\(', '\)', '\,'.
            #
            # Here the URI is set in quotes alltogether!
            if u'(' in stringValue or\
               u')' in stringValue or\
               u',' in stringValue or\
               u'"' in stringValue or\
               u'\'' in stringValue or\
               u'\n' in stringValue or\
               u'\t' in stringValue or\
               u'\r' in stringValue or\
               u'\f' in stringValue or\
               u' ' in stringValue:
                stringValue = '"%s"' % stringValue.replace(u'"', ur'\"')
            self.cssText = u'url(%s)' % stringValue
        elif CSSPrimitiveValue.CSS_ATTR == self._primitiveType:
            self.cssText = u'attr(%s)' % stringValue
        else:
            self.cssText = stringValue
        self._primitiveType = stringType

    def getCounterValue(self):
        """
        (DOM method) This method is used to get the Counter value. If
        this CSS value doesn't contain a counter value, a DOMException
        is raised. Modification to the corresponding style property
        can be achieved using the Counter interface.
        """
        if not self.CSS_COUNTER == self.primitiveType:
            raise xml.dom.InvalidAccessErr(u'Value is not a counter type')
        # TODO: use Counter class
        raise NotImplementedError()

    def getRGBColorValue(self):
        """
        (DOM method) This method is used to get the RGB color. If this
        CSS value doesn't contain a RGB color value, a DOMException
        is raised. Modification to the corresponding style property
        can be achieved using the RGBColor interface.
        """
        # TODO: what about coercing #000 to RGBColor?
        if self.primitiveType not in self._rbgtypes:
            raise xml.dom.InvalidAccessErr(u'Value is not a RGB value')
        # TODO: use RGBColor class
        raise NotImplementedError()

    def getRectValue(self):
        """
        (DOM method) This method is used to get the Rect value. If this CSS
        value doesn't contain a rect value, a DOMException is raised.
        Modification to the corresponding style property can be achieved
        using the Rect interface.
        """
        if self.primitiveType not in self._recttypes:
            raise xml.dom.InvalidAccessErr(u'value is not a Rect value')
        # TODO: use Rect class
        raise NotImplementedError()

    def __str__(self):
        return "<cssutils.css.%s object primitiveType=%s cssText=%r _propertyName=%r valid=%r at 0x%x>" % (
                self.__class__.__name__, self.primitiveTypeString,
                self.cssText, self._propertyName, self.valid, id(self))


class CSSValueList(CSSValue):
    """
    The CSSValueList interface provides the abstraction of an ordered
    collection of CSS values.

    Some properties allow an empty list into their syntax. In that case,
    these properties take the none identifier. So, an empty list means
    that the property has the value none.

    The items in the CSSValueList are accessible via an integral index,
    starting from 0.
    """
    cssValueType = CSSValue.CSS_VALUE_LIST

    def __init__(self, cssText=None, readonly=False, _propertyName=None):
        """
        inits a new CSSValueList
        """
        super(CSSValueList, self).__init__(cssText=cssText,
                                       readonly=readonly,
                                       _propertyName=_propertyName)
        self._init()

    def _init(self):
        "called by CSSValue if newly identified as CSSValueList"
        # defines which values
        ivalueseq, valueseq = 0, self._SHORTHANDPROPERTIES.get(
                                                    self._propertyName, [])
        self._items = []
        newseq = []
        i, max = 0, len(self.seq)
        minus = None
        while i < max:            
            v = self.seq[i]

            if u'-' == v:
                if minus: # 2 "-" after another
                    self._log.error(
                        u'CSSValueList: Unknown syntax: %r.'
                            % u''.join(self.seq))
                else:
                    minus = v
                    
            elif isinstance(v, basestring) and not v.strip() == u'' and\
               not u'/' == v:
                if minus:
                    v = minus + v
                    minus = None
                # TODO: complete
                # if shorthand get new propname
                if ivalueseq < len(valueseq):
                    propname, mandatory = valueseq[ivalueseq]
                    if mandatory:
                        ivalueseq += 1
                    else:
                        propname = None
                        ivalueseq = len(valueseq) # end
                else:
                    propname = self._propertyName
                
                # TODO: more (do not check individual values for these props)
                if propname in self._SHORTHANDPROPERTIES:
                    propname = None
                
                if i+1 < max and self.seq[i+1] == u',':
                    # a comma separated list of values as ONE value
                    # e.g. font-family: a,b
                    fullvalue = [v]

                    expected = 'comma' # or 'value'
                    for j in range(i+1, max):
                        testv = self.seq[j]
                        if u' ' == testv: # a single value follows
                            break
                        elif testv in ('-', '+') and expected == 'value':
                            # unary modifier
                            fullvalue.append(testv)
                            expected = 'value'
                        elif u',' == testv and expected == 'comma':
                            fullvalue.append(testv)
                            expected = 'value'
                        elif u',' != testv and expected == 'value':
                            fullvalue.append(testv)
                            expected = 'comma'
                        else:
                            self._log.error(
                                u'CSSValueList: Unknown syntax: %r.'
                                % testv)
                            return
                    if expected == 'value':
                        self._log.error(
                            u'CSSValueList: Unknown syntax: %r.'
                            % u''.join(self.seq))
                        return
                    # setting _propertyName this way does not work
                    # for compound props like font!
                    i += len(fullvalue) - 1
                    o = CSSValue(cssText=u''.join(fullvalue),
                             _propertyName=propname)
                else:
                    # a single value, u' ' or nothing should be following
                    o = CSSValue(cssText=v, _propertyName=propname)

                self._items.append(o)
                newseq.append(o)

            else:
                # S (or TODO: comment?)
                newseq.append(v)

            i += 1

        self.seq = newseq

    length = property(lambda self: len(self._items),
                doc="(DOM attribute) The number of CSSValues in the list.")

    def item(self, index):
        """
        (DOM method) Used to retrieve a CSSValue by ordinal index. The
        order in this collection represents the order of the values in the
        CSS style property. If index is greater than or equal to the number
        of values in the list, this returns None.
        """
        try:
            return self._items[index]
        except IndexError:
            return None

    def __iter__(self):
        "CSSValueList is iterable"
        return CSSValueList.__items(self)

    def __items(self):
        "the iterator"
        for i in range (0, self.length):
            yield self.item(i)

    def __str_(self):
        return "<cssutils.css.%s object length=%s at 0x%x>" % (
                self.__class__.__name__, self.length, id(self))
