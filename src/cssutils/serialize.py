#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""cssutils serializer"""
__all__ = ['CSSSerializer', 'Preferences']
__docformat__ = 'restructuredtext'
__version__ = '$Id: serialize.py 1872 2009-10-17 21:00:40Z cthedot $'

import codecs
import cssutils
import helper
import re
import xml.dom

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
    """Control output of CSSSerializer.

    defaultAtKeyword = True
        Should the literal @keyword from src CSS be used or the default
        form, e.g. if ``True``: ``@import`` else: ``@i\mport``
    defaultPropertyName = True
        Should the normalized propertyname be used or the one given in
        the src file, e.g. if ``True``: ``color`` else: ``c\olor``

        Only used if ``keepAllProperties==False``.
        
    defaultPropertyPriority = True
        Should the normalized or literal priority be used, e.g. ``!important``
        or ``!Im\portant``

    importHrefFormat = None
        Uses hreftype if ``None`` or format ``"URI"`` if ``'string'`` or
        format ``url(URI)`` if ``'uri'``
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
    keepUnkownAtRules = True
        defines if unknown @rules like e.g. ``@three-dee {}`` are kept in the 
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
    
    validOnly = False
        if True only valid (Properties) are output
        
        A Property is valid if it is a known Property with a valid value.
    """
    def __init__(self, **initials):
        """Always use named instead of positional parameters."""
        self.useDefaults()
        for key, value in initials.items():
            if value:
                self.__setattr__(key, value)

    def __repr__(self):
        return u"cssutils.css.%s(%s)" % (self.__class__.__name__, 
            u', '.join(['\n    %s=%r' % (p, self.__getattribute__(p)) for p in self.__dict__]
                ))

    def __str__(self):
        return u"<cssutils.css.%s object %s at 0x%x" % (self.__class__.__name__, 
            u' '.join(['%s=%r' % (p, self.__getattribute__(p)) for p in self.__dict__]
                ),
                id(self))

    def useDefaults(self):
        "Reset all preference options to their default value."
        self.defaultAtKeyword = True
        self.defaultPropertyName = True
        self.defaultPropertyPriority = True
        self.importHrefFormat = None
        self.indent = 4 * u' '
        self.indentSpecificities = False
        self.keepAllProperties = True
        self.keepComments = True
        self.keepEmptyRules = False
        self.keepUnkownAtRules = True
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
        """Set options resulting in a minified stylesheet.
        
        You may want to set preferences with this convenience method
        and set settings you want adjusted afterwards.
        """
        self.importHrefFormat = 'string'
        self.indent = u''
        self.keepComments = False
        self.keepEmptyRules = False
        self.keepUnkownAtRules = False
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


class Out(object):
    """A simple class which makes appended items available as a combined string"""
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
            escapes helper.string
        - typ S
            ignored except ``keepS=True``
        - typ URI
            calls helper.uri
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
        prefspace = self.ser.prefs.spacer
        
        if val or typ in ('STRING', 'URI'):
            # PRE
            if 'COMMENT' == typ:
                if self.ser.prefs.keepComments:
                    val = val.cssText
                else: 
                    return
            elif hasattr(val, 'cssText'):
                val = val.cssText
#            elif typ in ('Property', cssutils.css.CSSRule.UNKNOWN_RULE):
#                val = val.cssText
            elif 'S' == typ and not keepS:
                return
            elif 'S' == typ and keepS:
                val = u' '
            elif typ in ('NUMBER', 'DIMENSION', 'PERCENTAGE') and val == '0':
                # remove sign + or - if value is zero
                # TODO: only for lenghts!
                if self.out and self.out[-1] in u'+-':
                    del self.out[-1]
            elif 'STRING' == typ:
                # may be empty but MUST not be None
                if val is None: 
                    return
                val = helper.string(val) 
                if not prefspace:
                    self._remove_last_if_S()
            elif 'URI' == typ:
                val = helper.uri(val)
            elif 'HASH' == typ:
                val = self.ser._hash(val)
            elif val in u'+>~,:{;)]/':
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
            elif val not in u'}[]()/' and typ != 'FUNCTION' and space:
                self.out.append(self.ser.prefs.spacer)
                if typ != 'STRING' and not self.ser.prefs.spacer and \
                   self.out and not self.out[-1].endswith(u' '):
                    self.out.append(u' ')
        
    def value(self, delim=u'', end=None, keepS=False):
        "returns all items joined by delim"
        if not keepS:
            self._remove_last_if_S()
        if end:
            self.out.append(end)
        return delim.join(self.out)
    

class CSSSerializer(object):
    """Serialize a CSSStylesheet and its parts.

    To use your own serializing method the easiest is to subclass CSS
    Serializer and overwrite the methods you like to customize.
    """
    def __init__(self, prefs=None):
        """
        :param prefs:
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

    def _hash(self, val, type_=None):
        """
        Short form of hash, e.g. #123 instead of #112233
        """
        # TODO: add pref for this!
        if len(val) == 7 and val[1] == val[2] and\
                             val[3] == val[4] and\
                             val[5] == val[6]:
            return u'#%s%s%s' % (val[1], val[3], val[5])
        else:
            return val

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
            return u'@charset %s;' % helper.string(rule.encoding)
        else:
            return u''

    def do_CSSVariablesRule(self, rule):
        """
        serializes CSSVariablesRule

        media
            TODO
        variables
            CSSStyleDeclaration

        + CSSComments
        """
        variablesText = rule.variables.cssText

        if variablesText and rule.wellformed:
            out = Out(self)
            out.append(self._atkeyword(rule, u'@variables'))   
            for item in rule.seq:
                # assume comments {
                out.append(item.value, item.type)            
            out.append(u'{')
            out.append(u'%s%s}' % (variablesText, self.prefs.lineSeparator),
                       indent=1)            
            return out.value()            
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
            nameout.append(helper.string(rule.name))
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
            out.append(rule.selectorText)                            
            out.append(u'{')            
            out.append(u'%s%s}' % (styleText, self.prefs.lineSeparator),
                       indent=1)
            return out.value()            
        else:
            return u''

    def do_CSSPageRuleSelector(self, seq):
        "Serialize selector of a CSSPageRule"
        out = Out(self)
        for item in seq:
            if item.type == 'IDENT':
                out.append(item.value, item.type, space=False)
            else:
                out.append(item.value, item.type)
        return out.value()
        
    def do_CSSUnknownRule(self, rule):
        """
        serializes CSSUnknownRule
        anything until ";" or "{...}"
        + CSSComments
        """
        if rule.wellformed and self.prefs.keepUnkownAtRules:
            out = Out(self)
            out.append(rule.atkeyword)  
                         
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

    def do_css_CSSVariablesDeclaration(self, variables):
        """Variables of CSSVariableRule."""
        if len(variables.seq) > 0:
            out = Out(self)
            
            lastitem = len(variables.seq) - 1
            for i, item in enumerate(variables.seq):
                type_, val = item.type, item.value
                if u'var' == type_:
                    name, cssvalue = val
                    out.append(name)
                    out.append(u':')
                    out.append(cssvalue.cssText)
                    if i < lastitem or not self.prefs.omitLastSemicolon:
                        out.append(u';')
                
                elif isinstance(val, cssutils.css.CSSComment):
                    # CSSComment
                    out.append(val, 'COMMENT')
                    out.append(self.prefs.lineSeparator)
                else:
                    out.append(val.cssText, type_)
                    out.append(self.prefs.lineSeparator)
            
            return out.value().strip() 

        else:
            return u''

    def do_css_CSSStyleDeclaration(self, style, separator=None):
        """
        Style declaration of CSSStyleRule
        """
        # TODO: use Out()
        
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
                    if val.cssText:
                        out.append(val.cssText)
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
        """Serializes a CSSValue"""
        if not cssvalue:
            return u''
        else:
            out = Out(self)
            for item in cssvalue.seq:
                type_, val = item.type, item.value
                if hasattr(val, 'cssText'):
                    # RGBColor or CSSValue if a CSSValueList
                    out.append(val.cssText, type_)
                else:
                    if val and val[0] == val[-1] and val[0] in '\'"':
                        val = helper.string(val[1:-1])
                    # S must be kept! in between values but no extra space
                    out.append(val, type_)

            return out.value() 
                        
    def do_css_CSSPrimitiveValue(self, cssvalue):
        """Serialize a CSSPrimitiveValue"""
        if not cssvalue:
            return u''
        else:
            out = Out(self)
            for item in cssvalue.seq:
                type_, val = item.type, item.value
                if type_ in ('DIMENSION', 'NUMBER', 'PERCENTAGE'):
                    n, d = cssvalue._getNumDim(val)
                    if 0 == n:
                        if cssvalue.primitiveType in cssvalue._lengthtypes:
                            # 0 if zero value
                            val = u'0'
                        else:
                            val = u'0' + d
                    else:
                        val = unicode(n) + d
                out.append(val, type_)
                
            return out.value() 

    def do_css_CSSVariable(self, variable):
        """Serializes a CSSVariable"""
        if not variable:
            return u''
        else:
            out = Out(self)
            for item in variable.seq:
                type_, val = item.type, item.value
                out.append(val, type_)

            return out.value()
          
    def do_css_RGBColor(self, cssvalue):
        """Serialize a RGBColor value"""
        if not cssvalue:
            return u''
        else:
            out = Out(self)
            unary = None
            for item in cssvalue.seq:
                type_, val = item.type, item.value
                    
                out.append(val, type_)
            
            return out.value() 

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


    def do_css_ExpressionValue(self, cssvalue):
        """Serialize an ExpressionValue (IE only), 
        should at least keep the original syntax"""
        if not cssvalue:
            return u''
        else:
            out = Out(self)
            for item in cssvalue.seq:
                type_, val = item.type, item.value
                if type_ in ('DIMENSION', 'NUMBER', 'PERCENTAGE'):
                    n, d = cssvalue._getNumDim(val)
                    if 0 == n:
                        if cssvalue.primitiveType in cssvalue._lengthtypes:
                            # 0 if zero value
                            val = u'0'
                        else:
                            val = u'0' + d
                    else:
                        val = unicode(n) + d
                # do no send type_ so no special cases!
                out.append(val, None, space=False)
                
            return out.value() 
            