"""CSSStyleDeclaration implements DOM Level 2 CSS CSSStyleDeclaration and
extends CSS2Properties

see
    http://www.w3.org/TR/1998/REC-CSS2-19980512/syndata.html#parsing-errors

Unknown properties
------------------
User agents must ignore a declaration with an unknown property.
For example, if the style sheet is::

    H1 { color: red; rotation: 70minutes }

the user agent will treat this as if the style sheet had been::

    H1 { color: red }

Cssutils gives a message about any unknown properties but
keeps any property (if syntactically correct).

Illegal values
--------------
User agents must ignore a declaration with an illegal value. For example::

    IMG { float: left }       /* correct CSS2 */
    IMG { float: left here }  /* "here" is not a value of 'float' */
    IMG { background: "red" } /* keywords cannot be quoted in CSS2 */
    IMG { border-width: 3 }   /* a unit must be specified for length values */

A CSS2 parser would honor the first rule and ignore the rest, as if the
style sheet had been::

    IMG { float: left }
    IMG { }
    IMG { }
    IMG { }

Cssutils again will issue a message (WARNING in this case) about invalid 
CSS2 property values.

TODO:
    This interface is also used to provide a read-only access to the
    computed values of an element. See also the ViewCSS interface.

    - return computed values and not literal values
    - simplify unit pairs/triples/quadruples
      2px 2px 2px 2px -> 2px for border/padding...
    - normalize compound properties like:
      background: no-repeat left url()  #fff
      -> background: #fff url() no-repeat left
"""
__all__ = ['CSSStyleDeclaration', 'Property']
__docformat__ = 'restructuredtext'
__version__ = '$Id: cssstyledeclaration.py 1879 2009-11-17 20:35:04Z cthedot $'

from cssproperties import CSS2Properties
from property import Property
import cssutils
import xml.dom

class CSSStyleDeclaration(CSS2Properties, cssutils.util.Base2):
    """The CSSStyleDeclaration class represents a single CSS declaration
    block. This class may be used to determine the style properties
    currently set in a block or to set style properties explicitly
    within the block.

    While an implementation may not recognize all CSS properties within
    a CSS declaration block, it is expected to provide access to all
    specified properties in the style sheet through the
    CSSStyleDeclaration interface.
    Furthermore, implementations that support a specific level of CSS
    should correctly handle CSS shorthand properties for that level. For
    a further discussion of shorthand properties, see the CSS2Properties
    interface.

    Additionally the CSS2Properties interface is implemented.

    $css2propertyname
        All properties defined in the CSS2Properties class are available
        as direct properties of CSSStyleDeclaration with their respective
        DOM name, so e.g. ``fontStyle`` for property 'font-style'.

        These may be used as::

            >>> style = CSSStyleDeclaration(cssText='color: red')
            >>> style.color = 'green'
            >>> print style.color
            green
            >>> del style.color
            >>> print style.color
            <BLANKLINE>

    Format::
    
        [Property: Value Priority?;]* [Property: Value Priority?]?
    """
    def __init__(self, cssText=u'', parentRule=None, readonly=False):
        """
        :param cssText:
            Shortcut, sets CSSStyleDeclaration.cssText
        :param parentRule:
            The CSS rule that contains this declaration block or
            None if this CSSStyleDeclaration is not attached to a CSSRule.
        :param readonly:
            defaults to False
        """
        super(CSSStyleDeclaration, self).__init__()
        self._parentRule = parentRule
        self.cssText = cssText
        self._readonly = readonly

    def __contains__(self, nameOrProperty):
        """Check if a property (or a property with given name) is in style.
        
        :param name:
            a string or Property, uses normalized name and not literalname
        """
        if isinstance(nameOrProperty, Property):
            name = nameOrProperty.name
        else:
            name = self._normalize(nameOrProperty)
        return name in self.__nnames()
    
    def __iter__(self):
        """Iterator of set Property objects with different normalized names."""
        def properties():
            for name in self.__nnames():
                yield self.getProperty(name)
        return properties()

    def keys(self):
        """Analoguous to standard dict returns property names which are set in
        this declaration."""
        return list(self.__nnames())
    
    def __getitem__(self, CSSName):
        """Retrieve the value of property ``CSSName`` from this declaration.
        
        ``CSSName`` will be always normalized.
        """
        return self.getPropertyValue(CSSName)
    
    def __setitem__(self, CSSName, value):
        """Set value of property ``CSSName``. ``value`` may also be a tuple of 
        (value, priority), e.g. style['color'] = ('red', 'important')
        
        ``CSSName`` will be always normalized.
        """
        priority = None
        if type(value) == tuple:
            value, priority = value

        return self.setProperty(CSSName, value, priority)

    def __delitem__(self, CSSName):
        """Delete property ``CSSName`` from this declaration.
        If property is not in this declaration return u'' just like 
        removeProperty.
        
        ``CSSName`` will be always normalized.
        """
        return self.removeProperty(CSSName)

    def __setattr__(self, n, v):
        """Prevent setting of unknown properties on CSSStyleDeclaration
        which would not work anyway. For these
        ``CSSStyleDeclaration.setProperty`` MUST be called explicitly!

        TODO:
            implementation of known is not really nice, any alternative?
        """
        known = ['_tokenizer', '_log', '_ttypes',
                 '_seq', 'seq', 'parentRule', '_parentRule', 'cssText',
                 'valid', 'wellformed',
                 '_readonly', '_profiles']
        known.extend(CSS2Properties._properties)
        if n in known:
            super(CSSStyleDeclaration, self).__setattr__(n, v)
        else:
            raise AttributeError(
                'Unknown CSS Property, ``CSSStyleDeclaration.setProperty("%s", ...)`` MUST be used.'
                % n)

    def __repr__(self):
        return "cssutils.css.%s(cssText=%r)" % (
                self.__class__.__name__, self.getCssText(separator=u' '))

    def __str__(self):
        return "<cssutils.css.%s object length=%r (all: %r) at 0x%x>" % (
                self.__class__.__name__, self.length,
                len(self.getProperties(all=True)), id(self))

    def __nnames(self):
        """Return iterator for all different names in order as set
        if names are set twice the last one is used (double reverse!) 
        """
        names = []
        for item in reversed(self.seq):
            val = item.value
            if isinstance(val, Property) and not val.name in names:
                names.append(val.name)
        return reversed(names)    

    def _absorb(self, other):
        """Replace all own data with data from other object."""
        self._parentRule = other._parentRule
        self.seq.absorb(other.seq)
        self._readonly = other._readonly

    # overwritten accessor functions for CSS2Properties' properties
    def _getP(self, CSSName):
        """(DOM CSS2Properties) Overwritten here and effectively the same as
        ``self.getPropertyValue(CSSname)``.

        Parameter is in CSSname format ('font-style'), see CSS2Properties.

        Example::

            >>> style = CSSStyleDeclaration(cssText='font-style:italic;')
            >>> print style.fontStyle
            italic
        """
        return self.getPropertyValue(CSSName)

    def _setP(self, CSSName, value):
        """(DOM CSS2Properties) Overwritten here and effectively the same as
        ``self.setProperty(CSSname, value)``.

        Only known CSS2Properties may be set this way, otherwise an
        AttributeError is raised.
        For these unknown properties ``setPropertyValue(CSSname, value)``
        has to be called explicitly.
        Also setting the priority of properties needs to be done with a
        call like ``setPropertyValue(CSSname, value, priority)``.

        Example::

            >>> style = CSSStyleDeclaration()
            >>> style.fontStyle = 'italic'
            >>> # or
            >>> style.setProperty('font-style', 'italic', '!important')
            
        """
        self.setProperty(CSSName, value)
        # TODO: Shorthand ones

    def _delP(self, CSSName):
        """(cssutils only) Overwritten here and effectively the same as
        ``self.removeProperty(CSSname)``.

        Example::

            >>> style = CSSStyleDeclaration(cssText='font-style:italic;')
            >>> del style.fontStyle
            >>> print style.fontStyle
            <BLANKLINE>

        """
        self.removeProperty(CSSName)

    def children(self):
        """Generator yielding any known child in this declaration including
         *all* properties, comments or CSSUnknownrules.
        """
        for item in self._seq:
            yield item.value

    def _getCssText(self):
        """Return serialized property cssText."""
        return cssutils.ser.do_css_CSSStyleDeclaration(self)

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
        """
        self._checkReadonly()
        tokenizer = self._tokenize2(cssText)

        # for closures: must be a mutable
        new = {'wellformed': True} 
        def ident(expected, seq, token, tokenizer=None):
            # a property
            
            tokens = self._tokensupto2(tokenizer, starttoken=token,
                                       semicolon=True)
            if self._tokenvalue(tokens[-1]) == u';':
                tokens.pop()
            property = Property(parent=self)
            property.cssText = tokens
            if property.wellformed:
                seq.append(property, 'Property')                
            else:
                self._log.error(u'CSSStyleDeclaration: Syntax Error in Property: %s'
                                % self._valuestr(tokens))
            # does not matter in this case
            return expected 

        def unexpected(expected, seq, token, tokenizer=None):
            # error, find next ; or } to omit upto next property
            ignored = self._tokenvalue(token) + self._valuestr(
                                self._tokensupto2(tokenizer, propertyvalueendonly=True))
            self._log.error(u'CSSStyleDeclaration: Unexpected token, ignoring upto %r.' %
                            ignored,token)
            # does not matter in this case
            return expected

        # [Property: Value;]* Property: Value?
        newseq = self._tempSeq()
        wellformed, expected = self._parse(expected=None,
            seq=newseq, tokenizer=tokenizer,
            productions={'IDENT': ident},#, 'CHAR': char},
            default=unexpected)
        # wellformed set by parse

        for item in newseq:
            item.value._parent = self
         
        # do not check wellformed as invalid things are removed anyway            
        self._setSeq(newseq)
        
    cssText = property(_getCssText, _setCssText,
        doc="(DOM) A parsable textual representation of the declaration\
        block excluding the surrounding curly braces.")

    def getCssText(self, separator=None):
        """
        :returns: 
            serialized property cssText, each property separated by
            given `separator` which may e.g. be ``u''`` to be able to use
            cssText directly in an HTML style attribute. ``;`` is part of
            each property (except the last one) and **cannot** be set with
            separator!
        """
        return cssutils.ser.do_css_CSSStyleDeclaration(self, separator)

    def _setParentRule(self, parentRule):
        self._parentRule = parentRule
        for x in self.children():
            x.parent = self
            
    parentRule = property(lambda self: self._parentRule, _setParentRule,
        doc="(DOM) The CSS rule that contains this declaration block or "
            "None if this CSSStyleDeclaration is not attached to a CSSRule.")

    def getProperties(self, name=None, all=False):
        """
        :param name:
            optional `name` of properties which are requested.
            Only properties with this **always normalized** `name` are returned.
            If `name` is ``None`` all properties are returned (at least one for 
            each set name depending on parameter `all`).
        :param all:
            if ``False`` (DEFAULT) only the effective properties are returned. 
            If name is given a list with only one property is returned.

            if ``True`` all properties including properties set multiple times
            with different values or priorities for different UAs are returned.
            The order of the properties is fully kept as in the original 
            stylesheet.
        :returns: 
            a list of :class:`~cssutils.css.Property` objects set in 
            this declaration.
        """
        if name and not all:
            # single prop but list
            p = self.getProperty(name)
            if p:
                return [p]
            else: 
                return []
        elif not all:
            # effective Properties in name order
            return [self.getProperty(name)for name in self.__nnames()]
        else:    
            # all properties or all with this name    
            nname = self._normalize(name)
            properties = []
            for item in self.seq:
                val = item.value
                if isinstance(val, Property) and (
                   (bool(nname) == False) or (val.name == nname)):
                    properties.append(val)
            return properties

    def getProperty(self, name, normalize=True):
        """
        :param name:
            of the CSS property, always lowercase (even if not normalized)
        :param normalize:
            if ``True`` (DEFAULT) name will be normalized (lowercase, no simple
            escapes) so "color", "COLOR" or "C\olor" will all be equivalent

            If ``False`` may return **NOT** the effective value but the 
            effective for the unnormalized name.
        :returns:
            the effective :class:`~cssutils.css.Property` object.
        """
        nname = self._normalize(name)
        found = None
        for item in reversed(self.seq):
            val = item.value
            if isinstance(val, Property):
                if (normalize and nname == val.name) or name == val.literalname:
                    if val.priority:
                        return val
                    elif not found:
                        found = val
        return found

    def getPropertyCSSValue(self, name, normalize=True):
        """
        :param name:
            of the CSS property, always lowercase (even if not normalized)
        :param normalize:
            if ``True`` (DEFAULT) name will be normalized (lowercase, no simple
            escapes) so "color", "COLOR" or "C\olor" will all be equivalent

            If ``False`` may return **NOT** the effective value but the effective
            for the unnormalized name.
        :returns:
            :class:`~cssutils.css.CSSValue`, the value of the effective
            property if it has been explicitly set for this declaration block. 

        (DOM)
        Used to retrieve the object representation of the value of a CSS
        property if it has been explicitly set within this declaration
        block. Returns None if the property has not been set.
                
        (This method returns None if the property is a shorthand
        property. Shorthand property values can only be accessed and
        modified as strings, using the getPropertyValue and setProperty
        methods.)

        **cssutils currently always returns a CSSValue if the property is 
        set.**

        for more on shorthand properties see
            http://www.dustindiaz.com/css-shorthand/
        """
        nname = self._normalize(name)
        if nname in self._SHORTHANDPROPERTIES:
            self._log.info(
                u'CSSValue for shorthand property "%s" should be None, this may be implemented later.' %
                nname, neverraise=True)

        p = self.getProperty(name, normalize)
        if p:
            return p.cssValue
        else:
            return None
        
    def getPropertyValue(self, name, normalize=True):
        """
        :param name:
            of the CSS property, always lowercase (even if not normalized)
        :param normalize:
            if ``True`` (DEFAULT) name will be normalized (lowercase, no simple
            escapes) so "color", "COLOR" or "C\olor" will all be equivalent

            If ``False`` may return **NOT** the effective value but the
            effective for the unnormalized name.
        :returns:
            the value of the effective property if it has been explicitly set
            for this declaration block. Returns the empty string if the
            property has not been set.
        """
        p = self.getProperty(name, normalize)
        if p:
            return p.value
        else:
            return u''
        
    def getPropertyPriority(self, name, normalize=True):
        """
        :param name:
            of the CSS property, always lowercase (even if not normalized)
        :param normalize:
            if ``True`` (DEFAULT) name will be normalized (lowercase, no simple
            escapes) so "color", "COLOR" or "C\olor" will all be equivalent

            If ``False`` may return **NOT** the effective value but the
            effective for the unnormalized name.
        :returns:
            the priority of the effective CSS property (e.g. the
            "important" qualifier) if the property has been explicitly set in
            this declaration block. The empty string if none exists.
        """
        p = self.getProperty(name, normalize)
        if p:
            return p.priority
        else:
            return u''

    def removeProperty(self, name, normalize=True):
        """
        (DOM)
        Used to remove a CSS property if it has been explicitly set within
        this declaration block.

        :param name:
            of the CSS property
        :param normalize:
            if ``True`` (DEFAULT) name will be normalized (lowercase, no simple
            escapes) so "color", "COLOR" or "C\olor" will all be equivalent.
            The effective Property value is returned and *all* Properties
            with ``Property.name == name`` are removed.

            If ``False`` may return **NOT** the effective value but the 
            effective for the unnormalized `name` only. Also only the 
            Properties with the literal name `name` are removed.
        :returns:
            the value of the property if it has been explicitly set for
            this declaration block. Returns the empty string if the property
            has not been set or the property name does not correspond to a
            known CSS property


        :exceptions:
            - :exc:`~xml.dom.NoModificationAllowedErr`:
              Raised if this declaration is readonly or the property is
              readonly.
        """
        self._checkReadonly()
        r = self.getPropertyValue(name, normalize=normalize)
        newseq = self._tempSeq()
        if normalize:
            # remove all properties with name == nname
            nname = self._normalize(name)
            for item in self.seq:
                if not (isinstance(item.value, Property) and item.value.name == nname):
                    newseq.appendItem(item)
        else:
            # remove all properties with literalname == name
            for item in self.seq:
                if not (isinstance(item.value, Property) and item.value.literalname == name):
                    newseq.appendItem(item)
        self._setSeq(newseq)
        return r

    def setProperty(self, name, value=None, priority=u'', normalize=True):
        """(DOM) Set a property value and priority within this declaration
        block.

        :param name:
            of the CSS property to set (in W3C DOM the parameter is called
            "propertyName"), always lowercase (even if not normalized)

            If a property with this `name` is present it will be reset.
            
            cssutils also allowed `name` to be a 
            :class:`~cssutils.css.Property` object, all other
            parameter are ignored in this case
        
        :param value:
            the new value of the property, ignored if `name` is a Property.
        :param priority:
            the optional priority of the property (e.g. "important"),
            ignored if `name` is a Property.
        :param normalize:
            if True (DEFAULT) `name` will be normalized (lowercase, no simple
            escapes) so "color", "COLOR" or "C\olor" will all be equivalent

        :exceptions:
            - :exc:`~xml.dom.SyntaxErr`:
              Raised if the specified value has a syntax error and is
              unparsable.
            - :exc:`~xml.dom.NoModificationAllowedErr`:
              Raised if this declaration is readonly or the property is
              readonly.
        """
        self._checkReadonly()
        
        if isinstance(name, Property):
            newp = name 
            name = newp.literalname
        elif not value:
            # empty string or None effectively removed property
            return self.removeProperty(name)
        else:
            newp = Property(name, value, priority)
        if not newp.wellformed:
            self._log.warn(u'Invalid Property: %s: %s %s'
                    % (name, value, priority))
        else:
            nname = self._normalize(name)
            properties = self.getProperties(name, all=(not normalize))
            for property in reversed(properties):
                if normalize and property.name == nname:
                    property.cssValue = newp.cssValue.cssText
                    property.priority = newp.priority
                    break
                elif property.literalname == name:
                    property.cssValue = newp.cssValue.cssText
                    property.priority = newp.priority
                    break
            else:
                newp.parent = self
                self.seq._readonly = False
                self.seq.append(newp, 'Property')
                self.seq._readonly = True

    def item(self, index):
        """(DOM) Retrieve the properties that have been explicitly set in
        this declaration block. The order of the properties retrieved using
        this method does not have to be the order in which they were set.
        This method can be used to iterate over all properties in this
        declaration block.

        :param index:
            of the property to retrieve, negative values behave like
            negative indexes on Python lists, so -1 is the last element

        :returns:
            the name of the property at this ordinal position. The
            empty string if no property exists at this position.

        **ATTENTION:**
        Only properties with different names are counted. If two
        properties with the same name are present in this declaration
        only the effective one is included.

        :meth:`item` and :attr:`length` work on the same set here.
        """
        names = list(self.__nnames())
        try:
            return names[index]
        except IndexError:
            return u''

    length = property(lambda self: len(list(self.__nnames())),
        doc="(DOM) The number of distinct properties that have been explicitly "
            "in this declaration block. The range of valid indices is 0 to "
            "length-1 inclusive. These are properties with a different ``name`` "
            "only. :meth:`item` and :attr:`length` work on the same set here.")
