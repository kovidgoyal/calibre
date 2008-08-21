#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""serializer classes for CSS classes

"""
__all__ = ['CSSSerializer', 'Preferences']
__docformat__ = 'restructuredtext'
__version__ = '$Id: serialize.py 1419 2008-08-09 19:28:06Z cthedot $'
import codecs
import re
import cssutils

def _escapecss(e):
    """
    Escapes characters not allowed in the current encoding the CSS way
    with a backslash followed by a uppercase hex code point
    
    E.g. the german umlaut 'ä' is escaped as \E4
    """
    s = e.object[e.start:e.end]
    return u''.join([ur'\%s ' % str(hex(ord(x)))[2:] # remove 0x from hex
                     .upper() for x in s]), e.end

codecs.register_error('escapecss', _escapecss)               


class Preferences(object):
    """
    controls output of CSSSerializer

    defaultAtKeyword = True
        Should the literal @keyword from src CSS be used or the default
        form, e.g. if ``True``: ``@import`` else: ``@i\mport``
    defaultPropertyName = True
        Should the normalized propertyname be used or the one given in
        the src file, e.g. if ``True``: ``color`` else: ``c\olor``

        Only used if ``keepAllProperties==False``.
        
    defaultPropertyPriority = True
        Should the normalized or literal priority be used, e.g. '!important'
        or u'!Im\portant'

    importHrefFormat = None
        Uses hreftype if ``None`` or explicit ``'string'`` or ``'uri'``
    indent = 4 * ' '
        Indentation of e.g Properties inside a CSSStyleDeclaration
    indentSpecificities = False
        Indent rules with subset of Selectors and higher Specitivity
        
    keepAllProperties = True
        If ``True`` all properties set in the original CSSStylesheet 
        are kept meaning even properties set twice with the exact same
        same name are kept!
    keepComments = True
        If ``False`` removes all CSSComments
    keepEmptyRules = False
        defines if empty rules like e.g. ``a {}`` are kept in the resulting
        serialized sheet
    keepUsedNamespaceRulesOnly = False
        if True only namespace rules which are actually used are kept
        
    lineNumbers = False
        Only used if a complete CSSStyleSheet is serialized.
    lineSeparator = u'\\n'
        How to end a line. This may be set to e.g. u'' for serializing of 
        CSSStyleDeclarations usable in HTML style attribute.
    listItemSpacer = u' '
        string which is used in ``css.SelectorList``, ``css.CSSValue`` and
        ``stylesheets.MediaList`` after the comma
    omitLastSemicolon = True
        If ``True`` omits ; after last property of CSSStyleDeclaration
    paranthesisSpacer = u' '
        string which is used before an opening paranthesis like in a 
        ``css.CSSMediaRule`` or ``css.CSSStyleRule``
    propertyNameSpacer = u' '
        string which is used after a Property name colon
    selectorCombinatorSpacer = u' '
        string which is used before and after a Selector combinator like +, > or ~.
        CSSOM defines a single space for this which is also the default in cssutils.
    spacer = u' '
        general spacer, used e.g. by CSSUnknownRule
    
    validOnly = False **DO NOT CHANGE YET**
        if True only valid (currently Properties) are kept
        
        A Property is valid if it is a known Property with a valid value.
        Currently CSS 2.1 values as defined in cssproperties.py would be
        valid.
        
    """
    def __init__(self, **initials):
        """
        Always use named instead of positional parameters
        """
        self.useDefaults()
        
        for key, value in initials.items():
            if value:
                self.__setattr__(key, value)

    def useDefaults(self):
        "reset all preference options to the default value"
        self.defaultAtKeyword = True
        self.defaultPropertyName = True
        self.defaultPropertyPriority = True
        self.importHrefFormat = None
        self.indent = 4 * u' '
        self.indentSpecificities = False
        self.keepAllProperties = True
        self.keepComments = True
        self.keepEmptyRules = False
        self.keepUsedNamespaceRulesOnly = False
        self.lineNumbers = False
        self.lineSeparator = u'\n'
        self.listItemSpacer = u' '
        self.omitLastSemicolon = True
        self.paranthesisSpacer = u' '
        self.propertyNameSpacer = u' '
        self.selectorCombinatorSpacer = u' '
        self.spacer = u' '
        self.validOnly = False # should not be changed currently!!!
        
    def useMinified(self):
        """
        sets options to achive a minified stylesheet
        
        you may want to set preferences with this convenience method
        and set settings you want adjusted afterwards
        """
        self.importHrefFormat = 'string'
        self.indent = u''
        self.keepComments = False
        self.keepEmptyRules = False
        self.keepUsedNamespaceRulesOnly = True
        self.lineNumbers = False
        self.lineSeparator = u''
        self.listItemSpacer = u''
        self.omitLastSemicolon = True
        self.paranthesisSpacer = u''
        self.propertyNameSpacer = u''
        self.selectorCombinatorSpacer = u''
        self.spacer = u''
        self.validOnly = False

    def __repr__(self):
        return u"cssutils.css.%s(%s)" % (self.__class__.__name__, 
            u', '.join(['\n    %s=%r' % (p, self.__getattribute__(p)) for p in self.__dict__]
                ))

    def __str__(self):
        return u"<cssutils.css.%s object %s at 0x%x" % (self.__class__.__name__, 
            u' '.join(['%s=%r' % (p, self.__getattribute__(p)) for p in self.__dict__]
                ),
                id(self))


class Out(object):
    """
    a simple class which makes appended items available as a combined string
    """
    def __init__(self, ser):
        self.ser = ser
        self.out = []
    
    def _remove_last_if_S(self):
        if self.out and not self.out[-1].strip():
            # remove trailing S
            del self.out[-1]
    
    def append(self, val, typ=None, space=True, keepS=False, indent=False, 
               lineSeparator=False):
        """Appends val. Adds a single S after each token except as follows:
        
        - typ COMMENT
            uses cssText depending on self.ser.prefs.keepComments
        - typ "Property", cssutils.css.CSSRule.UNKNOWN_RULE
            uses cssText
        - typ STRING
            escapes ser._string
        - typ S
            ignored except ``keepS=True``
        - typ URI
            calls ser_uri
        - val ``{``
            adds LF after
        - val ``;``
            removes S before and adds LF after
        - val ``, :``
            removes S before
        - val ``+ > ~``
            encloses in prefs.selectorCombinatorSpacer
        - some other vals
            add ``*spacer`` except ``space=False``
        """
        if val or 'STRING' == typ:
            # PRE
            if 'COMMENT' == typ:
                if self.ser.prefs.keepComments:
                    val = val.cssText
                else: 
                    return
            elif typ in ('Property', cssutils.css.CSSRule.UNKNOWN_RULE):
                val = val.cssText
            elif 'S' == typ and not keepS:
                return
            elif 'STRING' == typ:
                # may be empty but MUST not be None
                if val is None: 
                    return
                val = self.ser._string(val)                
            elif 'URI' == typ:
                val = self.ser._uri(val)
            elif val in u'+>~,:{;)]':
                self._remove_last_if_S()
                
            # APPEND
            if indent:
                self.out.append(self.ser._indentblock(val, self.ser._level+1))
            else:
                self.out.append(val)
            # POST
            if lineSeparator:
                # Property , ...
                pass
            elif val in u'+>~': # enclose selector combinator
                self.out.insert(-1, self.ser.prefs.selectorCombinatorSpacer)
                self.out.append(self.ser.prefs.selectorCombinatorSpacer)
            elif u',' == val: # list
                self.out.append(self.ser.prefs.listItemSpacer)
            elif u':' == val: # prop
                self.out.append(self.ser.prefs.propertyNameSpacer)
            elif u'{' == val: # block start
                self.out.insert(-1, self.ser.prefs.paranthesisSpacer)
                self.out.append(self.ser.prefs.lineSeparator)
            elif u';' == val: # end or prop or block
                self.out.append(self.ser.prefs.lineSeparator)
            elif val not in u'}[]()' and space:
                self.out.append(self.ser.prefs.spacer)
        
    def value(self, delim=u'', end=None):
        "returns all items joined by delim"
        self._remove_last_if_S()
        if end:
            self.out.append(end)
        return delim.join(self.out)
    

class CSSSerializer(object):
    """
    Methods to serialize a CSSStylesheet and its parts

    To use your own serializing method the easiest is to subclass CSS
    Serializer and overwrite the methods you like to customize.
    """
    # chars not in URI without quotes around
    __forbidden_in_uri_matcher = re.compile(ur'''.*?[\)\s\;]''', re.U).match

    def __init__(self, prefs=None):
        """
        prefs
            instance of Preferences
        """
        if not prefs:
            prefs = Preferences()
        self.prefs = prefs
        self._level = 0 # current nesting level
        
        # TODO:
        self._selectors = [] # holds SelectorList
        self._selectorlevel = 0 # current specificity nesting level

    def _atkeyword(self, rule, default):
        "returns default or source atkeyword depending on prefs"
        if self.prefs.defaultAtKeyword:
            return default
        else:
            return rule.atkeyword

    def _indentblock(self, text, level):
        """
        indent a block like a CSSStyleDeclaration to the given level
        which may be higher than self._level (e.g. for CSSStyleDeclaration)
        """
        if not self.prefs.lineSeparator:
            return text
        return self.prefs.lineSeparator.join(
            [u'%s%s' % (level * self.prefs.indent, line)
                for line in text.split(self.prefs.lineSeparator)]
        )

    def _propertyname(self, property, actual):
        """
        used by all styledeclarations to get the propertyname used
        dependent on prefs setting defaultPropertyName and
        keepAllProperties
        """
        if self.prefs.defaultPropertyName and not self.prefs.keepAllProperties:
            return property.name
        else:
            return actual

    def _linenumnbers(self, text):
        if self.prefs.lineNumbers:
            pad = len(str(text.count(self.prefs.lineSeparator)+1))
            out = []
            for i, line in enumerate(text.split(self.prefs.lineSeparator)):
                out.append((u'%*i: %s') % (pad, i+1, line))
            text = self.prefs.lineSeparator.join(out)
        return text

    def _string(self, s):
        """
        returns s encloded between "..." and escaped delim charater ", 
        escape line breaks \\n \\r and \\f
        """
        # \n = 0xa, \r = 0xd, \f = 0xc
        s = s.replace('\n', '\\a ').replace(
                      '\r', '\\d ').replace(
                      '\f', '\\c ')
        return u'"%s"' % s.replace('"', u'\\"')

    def _uri(self, uri):
        """returns uri enclosed in url() and "..." if necessary"""
        if CSSSerializer.__forbidden_in_uri_matcher(uri):
            return 'url(%s)' % self._string(uri)
        else:
            return 'url(%s)' % uri

    def _valid(self, x):
        "checks items valid property and prefs.validOnly"
        return not self.prefs.validOnly or (self.prefs.validOnly and 
                                            x.valid)
    
    def do_CSSStyleSheet(self, stylesheet):
        """serializes a complete CSSStyleSheet"""
        useduris = stylesheet._getUsedURIs()
        out = []
        for rule in stylesheet.cssRules:
            if self.prefs.keepUsedNamespaceRulesOnly and\
               rule.NAMESPACE_RULE == rule.type and\
               rule.namespaceURI not in useduris and (
                    rule.prefix or None not in useduris):
                continue 

            cssText = rule.cssText
            if cssText:
                out.append(cssText)
        text = self._linenumnbers(self.prefs.lineSeparator.join(out))
        
        # get encoding of sheet, defaults to UTF-8
        try:
            encoding = stylesheet.cssRules[0].encoding
        except (IndexError, AttributeError):
            encoding = 'UTF-8'
        
        return text.encode(encoding, 'escapecss')

    def do_CSSComment(self, rule):
        """
        serializes CSSComment which consists only of commentText
        """
        if rule._cssText and self.prefs.keepComments:
            return rule._cssText
        else:
            return u''

    def do_CSSCharsetRule(self, rule):
        """
        serializes CSSCharsetRule
        encoding: string

        always @charset "encoding";
        no comments or other things allowed!
        """
        if rule.wellformed:
            return u'@charset %s;' % self._string(rule.encoding)
        else:
            return u''

    def do_CSSFontFaceRule(self, rule):
        """
        serializes CSSFontFaceRule

        style
            CSSStyleDeclaration

        + CSSComments
        """
        styleText = self.do_css_CSSStyleDeclaration(rule.style)

        if styleText and rule.wellformed:
            out = Out(self)
            out.append(self._atkeyword(rule, u'@font-face'))   
            for item in rule.seq:
                # assume comments {
                out.append(item.value, item.type)            
            out.append(u'{')
            out.append(u'%s%s}' % (styleText, self.prefs.lineSeparator),
                       indent=1)            
            return out.value()            
        else:
            return u''

    def do_CSSImportRule(self, rule):
        """
        serializes CSSImportRule

        href
            string
        media
            optional cssutils.stylesheets.medialist.MediaList
        name
            optional string 

        + CSSComments
        """
        if rule.wellformed:
            out = Out(self)
            out.append(self._atkeyword(rule, u'@import'))
            
            for item in rule.seq:
                typ, val = item.type, item.value
                if 'href' == typ:
                    # "href" or url(href)
                    if self.prefs.importHrefFormat == 'string' or (
                             self.prefs.importHrefFormat != 'uri' and
                             rule.hreftype == 'string'):
                        out.append(val, 'STRING')
                    else:
                        if not len(self.prefs.spacer):
                            out.append(u' ')   
                        out.append(val, 'URI')
                elif 'media' == typ:
                    # media
                    mediaText = self.do_stylesheets_medialist(val)
                    if mediaText and mediaText != u'all':
                        out.append(mediaText)                
                elif 'name' == typ:
                    out.append(val, 'STRING')
                else:
                    out.append(val, typ)

            return out.value(end=u';')
        else:
            return u''

    def do_CSSNamespaceRule(self, rule):
        """
        serializes CSSNamespaceRule

        uri
            string
        prefix
            string

        + CSSComments
        """
        if rule.wellformed:
            out = Out(self)
            out.append(self._atkeyword(rule, u'@namespace'))
            if not len(self.prefs.spacer):
                out.append(u' ')   
            
            for item in rule.seq:
                typ, val = item.type, item.value
                if 'namespaceURI' == typ:
                    out.append(val, 'STRING')
                else:
                    out.append(val, typ)
                    
            return out.value(end=u';')
        else:
            return u''
        
    def do_CSSMediaRule(self, rule):
        """
        serializes CSSMediaRule

        + CSSComments
        """
        # TODO: use Out()?

        # mediaquery
        if not rule.media.wellformed:
            return u''

        # @media
        out = [self._atkeyword(rule, u'@media')] 
        if not len(self.prefs.spacer):
            # for now always with space as only webkit supports @mediaall?
            out.append(u' ')
        else: 
            out.append(self.prefs.spacer) # might be empty
        
        out.append(self.do_stylesheets_medialist(rule.media))
        
        # name, seq contains content after name only (Comments)
        if rule.name:
            out.append(self.prefs.spacer)
            nameout = Out(self)
            nameout.append(self._string(rule.name))
            for item in rule.seq:
                nameout.append(item.value, item.type)
            out.append(nameout.value())
            
        #  {
        out.append(self.prefs.paranthesisSpacer)
        out.append(u'{')                      
        out.append(self.prefs.lineSeparator)
        
        # rules
        rulesout = []
        for r in rule.cssRules:
            rtext = r.cssText
            if rtext:
                # indent each line of cssText
                rulesout.append(self._indentblock(rtext, self._level + 1))
                rulesout.append(self.prefs.lineSeparator)
        if not self.prefs.keepEmptyRules and not u''.join(rulesout).strip():
            return u''           
        out.extend(rulesout)
        
        #     }
        out.append(u'%s}' % ((self._level + 1) * self.prefs.indent))
        
        return u''.join(out)

    def do_CSSPageRule(self, rule):
        """
        serializes CSSPageRule

        selectorText
            string
        style
            CSSStyleDeclaration

        + CSSComments
        """
        styleText = self.do_css_CSSStyleDeclaration(rule.style)

        if styleText and rule.wellformed:
            out = Out(self)
            out.append(self._atkeyword(rule, u'@page'))
            if not len(self.prefs.spacer):
                out.append(u' ')
                        
            for item in rule.seq:
                out.append(item.value, item.type)
                            
            out.append(u'{')            
            out.append(u'%s%s}' % (styleText, self.prefs.lineSeparator),
                       indent=1)
            return out.value()            
        else:
            return u''
        
    def do_CSSUnknownRule(self, rule):
        """
        serializes CSSUnknownRule
        anything until ";" or "{...}"
        + CSSComments
        """
        if rule.wellformed:
            out = Out(self)
            out.append(rule.atkeyword)  
            if not len(self.prefs.spacer):
                out.append(u' ')
                         
            stacks = []
            for item in rule.seq:
                typ, val = item.type, item.value
                # PRE
                if u'}' == val:
                    # close last open item on stack
                    stackblock = stacks.pop().value()
                    if stackblock:
                        val = self._indentblock(
                               stackblock + self.prefs.lineSeparator + val, 
                               min(1, len(stacks)+1))
                    else:
                        val = self._indentblock(val, min(1, len(stacks)+1))
                # APPEND
                if stacks:
                    stacks[-1].append(val, typ)
                else:
                    out.append(val, typ)
                    
                # POST
                if u'{' == val:
                    # new stack level
                    stacks.append(Out(self))
            
            return out.value()
        else:
            return u''

    def do_CSSStyleRule(self, rule):
        """
        serializes CSSStyleRule

        selectorList
        style

        + CSSComments
        """
        # TODO: use Out()

        # prepare for element nested rules
        # TODO: sort selectors!
        if self.prefs.indentSpecificities:
            # subselectorlist?
            elements = set([s.element for s in rule.selectorList])
            specitivities = [s.specificity for s in rule.selectorList]
            for selector in self._selectors:
                lastelements = set([s.element for s in selector])
                if elements.issubset(lastelements):
                    # higher specificity?
                    lastspecitivities = [s.specificity for s in selector]
                    if specitivities > lastspecitivities:
                        self._selectorlevel += 1
                        break
                elif self._selectorlevel > 0:
                    self._selectorlevel -= 1
            else:
                # save new reference                
                self._selectors.append(rule.selectorList)
                self._selectorlevel = 0
        
        # TODO ^ RESOLVE!!!!
        
        selectorText = self.do_css_SelectorList(rule.selectorList)
        if not selectorText or not rule.wellformed:
            return u''
        self._level += 1
        styleText = u''
        try:
            styleText = self.do_css_CSSStyleDeclaration(rule.style)
        finally:
            self._level -= 1
        if not styleText:
                if self.prefs.keepEmptyRules:
                    return u'%s%s{}' % (selectorText,
                                        self.prefs.paranthesisSpacer)
        else:
            return self._indentblock(
                u'%s%s{%s%s%s%s}' % (
                    selectorText,
                    self.prefs.paranthesisSpacer,
                    self.prefs.lineSeparator,
                    self._indentblock(styleText, self._level + 1),
                    self.prefs.lineSeparator,
                    (self._level + 1) * self.prefs.indent),
                self._selectorlevel)

    def do_css_SelectorList(self, selectorlist):
        "comma-separated list of Selectors"
        # does not need Out() as it is too simple
        if selectorlist.wellformed:
            out = [] 
            for part in selectorlist.seq:
                if isinstance(part, cssutils.css.Selector):
                    out.append(part.selectorText)
                else:
                    out.append(part) # should not happen
            sep = u',%s' % self.prefs.listItemSpacer
            return sep.join(out)
        else:
            return u''
                  
    def do_css_Selector(self, selector):
        """
        a single Selector including comments
        
        an element has syntax (namespaceURI, name) where namespaceURI may be:
        
        - cssutils._ANYNS => ``*|name``
        - None => ``name``
        - u'' => ``|name``
        - any other value: => ``prefix|name``
        """
        if selector.wellformed:
            out = Out(self)
            
            DEFAULTURI = selector._namespaces.get('', None)           
            for item in selector.seq:
                typ, val = item.type, item.value
                if type(val) == tuple:
                    # namespaceURI|name (element or attribute)
                    namespaceURI, name = val
                    if DEFAULTURI == namespaceURI or (not DEFAULTURI and 
                                                      namespaceURI is None):
                        out.append(name, typ, space=False)
                    else:
                        if namespaceURI == cssutils._ANYNS:
                            prefix = u'*'
                        else:
                            try:
                                prefix = selector._namespaces.prefixForNamespaceURI(
                                                    namespaceURI)
                            except IndexError:
                                prefix = u''
                        
                        out.append(u'%s|%s' % (prefix, name), typ, space=False)
                else:
                    out.append(val, typ, space=False, keepS=True)
            
            return out.value()
        else: 
            return u''

    def do_css_CSSStyleDeclaration(self, style, separator=None):
        """
        Style declaration of CSSStyleRule
        """
#        # TODO: use Out()
        
        # may be comments only       
        if len(style.seq) > 0:
            if separator is None:
                separator = self.prefs.lineSeparator

            if self.prefs.keepAllProperties:
                # all
                seq = style.seq
            else:
                # only effective ones
                _effective = style.getProperties()
                seq = [item for item in style.seq 
                         if (isinstance(item.value, cssutils.css.Property) 
                             and item.value in _effective)
                         or not isinstance(item.value, cssutils.css.Property)]

            out = []
            for i, item in enumerate(seq):
                typ, val = item.type, item.value
                if isinstance(val, cssutils.css.CSSComment):
                    # CSSComment
                    if self.prefs.keepComments:
                        out.append(val.cssText)
                        out.append(separator)
                elif isinstance(val, cssutils.css.Property):
                    # PropertySimilarNameList
                    out.append(self.do_Property(val))
                    if not (self.prefs.omitLastSemicolon and i==len(seq)-1):
                        out.append(u';')
                    out.append(separator)
                elif isinstance(val, cssutils.css.CSSUnknownRule):
                    # @rule
                    out.append(val.cssText)
                    out.append(separator)
                else:
                    # ?
                    out.append(val)
                    out.append(separator)

            if out and out[-1] == separator:
                del out[-1]

            return u''.join(out)

        else:
            return u''

    def do_Property(self, property):
        """
        Style declaration of CSSStyleRule

        Property has a seqs attribute which contains seq lists for             
        name, a CSSvalue and a seq list for priority
        """
        # TODO: use Out()
        
        out = []
        if property.seqs[0] and property.wellformed and self._valid(property):
            nameseq, cssvalue, priorityseq = property.seqs

            #name
            for part in nameseq:
                if hasattr(part, 'cssText'):
                    out.append(part.cssText)
                elif property.literalname == part:
                    out.append(self._propertyname(property, part))
                else:
                    out.append(part)

            if out and (not property._mediaQuery or
                        property._mediaQuery and cssvalue.cssText):
                # MediaQuery may consist of name only
                out.append(u':')
                out.append(self.prefs.propertyNameSpacer)

            # value
            out.append(cssvalue.cssText)

            # priority
            if out and priorityseq:
                out.append(u' ')
                for part in priorityseq:
                    if hasattr(part, 'cssText'): # comments
                        out.append(part.cssText)
                    else:
                        if part == property.literalpriority and\
                           self.prefs.defaultPropertyPriority:
                            out.append(property.priority)
                        else:
                            out.append(part)

        return u''.join(out)

    def do_Property_priority(self, priorityseq):
        """
        a Properties priority "!" S* "important"
        """
        # TODO: use Out()
        
        out = []
        for part in priorityseq:
            if hasattr(part, 'cssText'): # comments
                out.append(u' ')
                out.append(part.cssText)
                out.append(u' ')
            else:
                out.append(part)
        return u''.join(out).strip()

    def do_css_CSSValue(self, cssvalue):
        """
        serializes a CSSValue
        """
        # TODO: use Out()
        # TODO: use self._valid(cssvalue)?
        
        if not cssvalue:
            return u''
        else:
            sep = u',%s' % self.prefs.listItemSpacer
            out = []
            for part in cssvalue.seq:
                if hasattr(part, 'cssText'):
                    # comments or CSSValue if a CSSValueList
                    out.append(part.cssText)
                elif isinstance(part, basestring) and part == u',':
                    out.append(sep)
                else:
                    # TODO: escape func parameter if STRING!
                    if part and part[0] == part[-1] and part[0] in '\'"':
                        # string has " " around it in CSSValue!
                        part = self._string(part[1:-1])
                    out.append(part)
            return (u''.join(out)).strip()

    def do_stylesheets_medialist(self, medialist):
        """
        comma-separated list of media, default is 'all'

        If "all" is in the list, every other media *except* "handheld" will
        be stripped. This is because how Opera handles CSS for PDAs.
        """
        if len(medialist) == 0:
            return u'all'
        else:
            sep = u',%s' % self.prefs.listItemSpacer
            return sep.join((mq.mediaText for mq in medialist))

    def do_stylesheets_mediaquery(self, mediaquery):
        """
        a single media used in medialist
        """
        if mediaquery.wellformed:
            out = []
            for part in mediaquery.seq:
                if isinstance(part, cssutils.css.Property): # Property
                    out.append(u'(%s)' % part.cssText)
                elif hasattr(part, 'cssText'): # comments
                    out.append(part.cssText)
                else:
                    # TODO: media queries!
                    out.append(part)
            return u' '.join(out)
        else:
            return u''
