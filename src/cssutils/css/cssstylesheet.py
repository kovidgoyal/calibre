"""CSSStyleSheet implements DOM Level 2 CSS CSSStyleSheet.

Partly also:
    - http://dev.w3.org/csswg/cssom/#the-cssstylesheet
    - http://www.w3.org/TR/2006/WD-css3-namespace-20060828/

TODO:
    - ownerRule and ownerNode
"""
__all__ = ['CSSStyleSheet']
__docformat__ = 'restructuredtext'
__version__ = '$Id: cssstylesheet.py 1857 2009-10-10 21:49:33Z cthedot $'

from cssutils.helper import Deprecated
from cssutils.util import _Namespaces, _SimpleNamespaces, _readUrl
from cssrule import CSSRule
import cssutils.stylesheets
import xml.dom

class CSSStyleSheet(cssutils.stylesheets.StyleSheet):
    """CSSStyleSheet represents a CSS style sheet.

    Format::
    
        stylesheet
          : [ CHARSET_SYM S* STRING S* ';' ]?
            [S|CDO|CDC]* [ import [S|CDO|CDC]* ]*
            [ namespace [S|CDO|CDC]* ]* # according to @namespace WD
            [ [ ruleset | media | page ] [S|CDO|CDC]* ]*

    ``cssRules``
        All Rules in this style sheet, a :class:`~cssutils.css.CSSRuleList`.
    """
    def __init__(self, href=None, media=None, title=u'', disabled=None,
                 ownerNode=None, parentStyleSheet=None, readonly=False,
                 ownerRule=None):
        """
        For parameters see :class:`~cssutils.stylesheets.StyleSheet`
        """
        super(CSSStyleSheet, self).__init__(
                'text/css', href, media, title, disabled,
                ownerNode, parentStyleSheet)

        self._ownerRule = ownerRule
        self.cssRules = cssutils.css.CSSRuleList()
        self._namespaces = _Namespaces(parentStyleSheet=self, log=self._log)
        self._readonly = readonly

        # used only during setting cssText by parse*()
        self.__encodingOverride = None
        self._fetcher = None

    def __iter__(self):
        "Generator which iterates over cssRules."
        for rule in self._cssRules:
            yield rule

    def __repr__(self):
        if self.media:
            mediaText = self.media.mediaText
        else:
            mediaText = None
        return "cssutils.css.%s(href=%r, media=%r, title=%r)" % (
                self.__class__.__name__,
                self.href, mediaText, self.title)

    def __str__(self):
        if self.media:
            mediaText = self.media.mediaText
        else:
            mediaText = None
        return "<cssutils.css.%s object encoding=%r href=%r "\
               "media=%r title=%r namespaces=%r at 0x%x>" % (
                self.__class__.__name__, self.encoding, self.href,
                mediaText, self.title, self.namespaces.namespaces,
                id(self))

    def _cleanNamespaces(self):
        "Remove all namespace rules with same namespaceURI but last one set."
        rules = self._cssRules
        namespaceitems = self.namespaces.items()
        i = 0
        while i < len(rules):
            rule = rules[i]
            if rule.type == rule.NAMESPACE_RULE and \
               (rule.prefix, rule.namespaceURI) not in namespaceitems:
                self.deleteRule(i)
            else:
                i += 1

    def _getUsedURIs(self):
        "Return set of URIs used in the sheet."
        useduris = set()
        for r1 in self:
            if r1.STYLE_RULE == r1.type:
                useduris.update(r1.selectorList._getUsedUris())
            elif r1.MEDIA_RULE == r1.type:
                for r2 in r1:
                    if r2.type == r2.STYLE_RULE:
                        useduris.update(r2.selectorList._getUsedUris())
        return useduris

    def _setCssRules(self, cssRules):
        "Set new cssRules and update contained rules refs."
        cssRules.append = self.insertRule
        cssRules.extend = self.insertRule
        cssRules.__delitem__ == self.deleteRule
        for rule in cssRules:
            rule._parentStyleSheet = self
        self._cssRules = cssRules

    cssRules = property(lambda self: self._cssRules, _setCssRules,
            "All Rules in this style sheet, a "
            ":class:`~cssutils.css.CSSRuleList`.")

    def _getCssText(self):
        "Textual representation of the stylesheet (a byte string)."
        return cssutils.ser.do_CSSStyleSheet(self)

    def _setCssText(self, cssText):
        """Parse `cssText` and overwrites the whole stylesheet.

        :param cssText:
            a parseable string or a tuple of (cssText, dict-of-namespaces)
        :exceptions:
            - :exc:`~xml.dom.NamespaceErr`:
              If a namespace prefix is found which is not declared.
            - :exc:`~xml.dom.NoModificationAllowedErr`:
              Raised if the rule is readonly.
            - :exc:`~xml.dom.SyntaxErr`:
              Raised if the specified CSS string value has a syntax error and
              is unparsable.
        """
        self._checkReadonly()

        cssText, namespaces = self._splitNamespacesOff(cssText)
        if not namespaces:
            namespaces = _SimpleNamespaces(log=self._log)

        tokenizer = self._tokenize2(cssText)
        newseq = [] #cssutils.css.CSSRuleList()

        # for closures: must be a mutable
        new = {'encoding': None, # needed for setting encoding of @import rules
               'namespaces': namespaces}
        def S(expected, seq, token, tokenizer=None):
            # @charset must be at absolute beginning of style sheet
            if expected == 0:
                return 1
            else:
                return expected

        def COMMENT(expected, seq, token, tokenizer=None):
            "special: sets parent*"
            comment = cssutils.css.CSSComment([token],
                                parentStyleSheet=self.parentStyleSheet)
            seq.append(comment)
            return expected

        def charsetrule(expected, seq, token, tokenizer):
            rule = cssutils.css.CSSCharsetRule(parentStyleSheet=self)
            rule.cssText = self._tokensupto2(tokenizer, token)
            if expected > 0 or len(seq) > 0:
                self._log.error(
                    u'CSSStylesheet: CSSCharsetRule only allowed at beginning of stylesheet.',
                    token, xml.dom.HierarchyRequestErr)
            else:
                if rule.wellformed:
                    seq.append(rule)
                    new['encoding'] = rule.encoding
            return 1

        def importrule(expected, seq, token, tokenizer):
            if new['encoding']:
                # set temporarily as used by _resolveImport
                # save newEncoding which have been set by resolveImport
                self.__newEncoding = new['encoding']

            rule = cssutils.css.CSSImportRule(parentStyleSheet=self)
            rule.cssText = self._tokensupto2(tokenizer, token)
            if expected > 1:
                self._log.error(
                    u'CSSStylesheet: CSSImportRule not allowed here.',
                    token, xml.dom.HierarchyRequestErr)
            else:
                if rule.wellformed:
                    #del rule._parentEncoding # remove as later it is read from this sheet!
                    seq.append(rule)

            try:
                # remove as only used temporarily but may not be set at all
                del self.__newEncoding
            except AttributeError, e:
                pass

            return 1

        def namespacerule(expected, seq, token, tokenizer):
            rule = cssutils.css.CSSNamespaceRule(
                                cssText=self._tokensupto2(tokenizer, token),
                                parentStyleSheet=self)
            if expected > 2:
                self._log.error(
                    u'CSSStylesheet: CSSNamespaceRule not allowed here.',
                    token, xml.dom.HierarchyRequestErr)
            else:
                if rule.wellformed:
                    for i, r in enumerate(seq):
                        if r.type == r.NAMESPACE_RULE and r.prefix == rule.prefix:
                            # replace as doubled:
                            seq[i] = rule
                            self._log.info(
                                u'CSSStylesheet: CSSNamespaceRule with same prefix found, replacing: %r'
                                % r.cssText,
                                token, neverraise=True)
                    seq.append(rule)
                    # temporary namespaces given to CSSStyleRule and @media
                    new['namespaces'][rule.prefix] = rule.namespaceURI
            return 2

        def variablesrule(expected, seq, token, tokenizer):
            rule = cssutils.css.CSSVariablesRule(parentStyleSheet=self)
            rule.cssText = self._tokensupto2(tokenizer, token)
            if rule.wellformed:
                seq.append(rule)
            return 2

        def fontfacerule(expected, seq, token, tokenizer):
            rule = cssutils.css.CSSFontFaceRule(parentStyleSheet=self)
            rule.cssText = self._tokensupto2(tokenizer, token)
            if rule.wellformed:
                seq.append(rule)
            return 3

        def mediarule(expected, seq, token, tokenizer):
            rule = cssutils.css.CSSMediaRule()
            rule.cssText = (self._tokensupto2(tokenizer, token),
                            new['namespaces'])
            if rule.wellformed:
                rule._parentStyleSheet=self
                for r in rule:
                    r._parentStyleSheet=self
                seq.append(rule)
            return 3

        def pagerule(expected, seq, token, tokenizer):
            rule = cssutils.css.CSSPageRule(parentStyleSheet=self)
            rule.cssText = self._tokensupto2(tokenizer, token)
            if rule.wellformed:
                seq.append(rule)
            return 3

        def unknownrule(expected, seq, token, tokenizer):
            self._log.warn(
                    u'CSSStylesheet: Unknown @rule found.',
                    token, neverraise=True)
            rule = cssutils.css.CSSUnknownRule(parentStyleSheet=self)
            rule.cssText = self._tokensupto2(tokenizer, token)
            if rule.wellformed:
                seq.append(rule)
            return expected

        def ruleset(expected, seq, token, tokenizer):
            rule = cssutils.css.CSSStyleRule()
            rule.cssText = (self._tokensupto2(tokenizer, token),
                            new['namespaces'])
            if rule.wellformed:
                rule._parentStyleSheet=self
                seq.append(rule)
            return 3

        # expected:
        # ['CHARSET', 'IMPORT', 'NAMESPACE', ('PAGE', 'MEDIA', ruleset)]
        wellformed, expected = self._parse(0, newseq, tokenizer,
            {'S': S,
             'COMMENT': COMMENT,
             'CDO': lambda *ignored: None,
             'CDC': lambda *ignored: None,
             'CHARSET_SYM': charsetrule,
             'FONT_FACE_SYM': fontfacerule,
             'IMPORT_SYM': importrule,
             'NAMESPACE_SYM': namespacerule,
             'PAGE_SYM': pagerule,
             'MEDIA_SYM': mediarule,
             'VARIABLES_SYM': variablesrule,
             'ATKEYWORD': unknownrule
             },
             default=ruleset)

        if wellformed:
            del self._cssRules[:]
            for rule in newseq:
                self.insertRule(rule, _clean=False)
            self._cleanNamespaces()

    cssText = property(_getCssText, _setCssText,
            "Textual representation of the stylesheet (a byte string)")

    def _resolveImport(self, url):
        """Read (encoding, enctype, decodedContent) from `url` for @import
        sheets."""
        try:
            # only available during parse of a complete sheet
            selfAsParentEncoding = self.__newEncoding
        except AttributeError:
            try:
                # explicit @charset
                selfAsParentEncoding = self._cssRules[0].encoding
            except (IndexError, AttributeError):
                # default not UTF-8 but None!
                selfAsParentEncoding = None

        return _readUrl(url, fetcher=self._fetcher,
                        overrideEncoding=self.__encodingOverride,
                        parentEncoding=selfAsParentEncoding)

    def _setCssTextWithEncodingOverride(self, cssText, encodingOverride=None,
                                        encoding=None):
        """Set `cssText` but use `encodingOverride` to overwrite detected
        encoding. This is used by parse and @import during setting of cssText.

        If `encoding` is given use this but do not save it as `encodingOverride`."""
        if encodingOverride:
            # encoding during resolving of @import
            self.__encodingOverride = encodingOverride

        self.__newEncoding = encoding # save for nested @import
        self.cssText = cssText

        if encodingOverride:
            # set encodingOverride explicit again!
            self.encoding = self.__encodingOverride
            # remove?
            self.__encodingOverride = None
        elif encoding:
            # may e.g. be httpEncoding
            self.encoding = encoding

    def _setFetcher(self, fetcher=None):
        """Set @import URL loader, if None the default is used."""
        self._fetcher = fetcher

    def _getEncoding(self):
        """Encoding set in :class:`~cssutils.css.CSSCharsetRule` or if ``None``
        resulting in default ``utf-8`` encoding being used."""
        try:
            return self._cssRules[0].encoding
        except (IndexError, AttributeError):
            return 'utf-8'

    def _setEncoding(self, encoding):
        """Set `encoding` of charset rule if present in sheet or insert a new
        :class:`~cssutils.css.CSSCharsetRule` with given `encoding`. 
        If `encoding` is None removes charsetrule if present resulting in 
        default encoding of utf-8.
        """
        try:
            rule = self._cssRules[0]
        except IndexError:
            rule = None
        if rule and rule.CHARSET_RULE == rule.type:
            if encoding:
                rule.encoding = encoding
            else:
                self.deleteRule(0)
        elif encoding:
            self.insertRule(cssutils.css.CSSCharsetRule(encoding=encoding), 0)

    encoding = property(_getEncoding, _setEncoding,
            "(cssutils) Reflect encoding of an @charset rule or 'utf-8' "
            "(default) if set to ``None``")

    namespaces = property(lambda self: self._namespaces,
                          doc="All Namespaces used in this CSSStyleSheet.")

    def add(self, rule):
        """Add `rule` to style sheet at appropriate position.
        Same as ``insertRule(rule, inOrder=True)``.
        """
        return self.insertRule(rule, index=None, inOrder=True)

    def deleteRule(self, index):
        """Delete rule at `index` from the style sheet.

        :param index:
            The `index` of the rule to be removed from the StyleSheet's rule
            list. For an `index` < 0 **no** :exc:`~xml.dom.IndexSizeErr` is
            raised but rules for normal Python lists are used. E.g. 
            ``deleteRule(-1)`` removes the last rule in cssRules.
            
            `index` may also be a CSSRule object which will then be removed
            from the StyleSheet.
            
        :exceptions:
            - :exc:`~xml.dom.IndexSizeErr`:
              Raised if the specified index does not correspond to a rule in
              the style sheet's rule list.
            - :exc:`~xml.dom.NamespaceErr`:
              Raised if removing this rule would result in an invalid StyleSheet
            - :exc:`~xml.dom.NoModificationAllowedErr`:
              Raised if this style sheet is readonly.
        """
        self._checkReadonly()

        if isinstance(index, CSSRule):
            for i, r in enumerate(self.cssRules):
                if index == r:
                    index = i
                    break
            else:
                raise xml.dom.IndexSizeErr(u"CSSStyleSheet: Not a rule in"
                                           " this sheets'a cssRules list: %s"
                                           % index)

        try:
            rule = self._cssRules[index]
        except IndexError:
            raise xml.dom.IndexSizeErr(
                u'CSSStyleSheet: %s is not a valid index in the rulelist of length %i' % (
                index, self._cssRules.length))
        else:
            if rule.type == rule.NAMESPACE_RULE:
                # check all namespacerules if used
                uris = [r.namespaceURI for r in self if r.type == r.NAMESPACE_RULE]
                useduris = self._getUsedURIs()
                if rule.namespaceURI in useduris and\
                   uris.count(rule.namespaceURI) == 1:
                    raise xml.dom.NoModificationAllowedErr(
                        u'CSSStyleSheet: NamespaceURI defined in this rule is used, cannot remove.')
                    return

            rule._parentStyleSheet = None # detach
            del self._cssRules[index] # delete from StyleSheet

    def insertRule(self, rule, index=None, inOrder=False, _clean=True):
        """
        Used to insert a new rule into the style sheet. The new rule now
        becomes part of the cascade.

        :param rule:
            a parsable DOMString, in cssutils also a 
            :class:`~cssutils.css.CSSRule` or :class:`~cssutils.css.CSSRuleList`
        :param index:
            of the rule before the new rule will be inserted.
            If the specified `index` is equal to the length of the
            StyleSheet's rule collection, the rule will be added to the end
            of the style sheet.
            If `index` is not given or ``None`` rule will be appended to rule
            list.
        :param inOrder:
            if ``True`` the rule will be put to a proper location while
            ignoring `index` and without raising :exc:`~xml.dom.HierarchyRequestErr`.
            The resulting index is returned nevertheless.
        :returns: The index within the style sheet's rule collection
        :Exceptions:
            - :exc:`~xml.dom.HierarchyRequestErr`:
              Raised if the rule cannot be inserted at the specified `index`
              e.g. if an @import rule is inserted after a standard rule set
              or other at-rule.
            - :exc:`~xml.dom.IndexSizeErr`:
              Raised if the specified `index` is not a valid insertion point.
            - :exc:`~xml.dom.NoModificationAllowedErr`:
              Raised if this style sheet is readonly.
            - :exc:`~xml.dom.SyntaxErr`:
              Raised if the specified rule has a syntax error and is
              unparsable.
        """
        self._checkReadonly()

        # check position
        if index is None:
            index = len(self._cssRules)
        elif index < 0 or index > self._cssRules.length:
            raise xml.dom.IndexSizeErr(
                u'CSSStyleSheet: Invalid index %s for CSSRuleList with a length of %s.' % (
                    index, self._cssRules.length))
            return

        if isinstance(rule, basestring):
            # init a temp sheet which has the same properties as self
            tempsheet = CSSStyleSheet(href=self.href,
                                      media=self.media,
                                      title=self.title,
                                      parentStyleSheet=self.parentStyleSheet,
                                      ownerRule=self.ownerRule)
            tempsheet._ownerNode = self.ownerNode
            tempsheet._fetcher = self._fetcher

            # prepend encoding if in this sheet to be able to use it in
            # @import rules encoding resolution
            # do not add if new rule startswith "@charset" (which is exact!)
            if not rule.startswith(u'@charset') and (self._cssRules and
                self._cssRules[0].type == self._cssRules[0].CHARSET_RULE):
                # rule 0 is @charset!
                newrulescount, newruleindex = 2, 1
                rule = self._cssRules[0].cssText + rule
            else:
                newrulescount, newruleindex = 1, 0

            # parse the new rule(s)
            tempsheet.cssText = (rule, self._namespaces)

            if len(tempsheet.cssRules) != newrulescount or (not isinstance(
               tempsheet.cssRules[newruleindex], cssutils.css.CSSRule)):
                self._log.error(u'CSSStyleSheet: Not a CSSRule: %s' % rule)
                return
            rule = tempsheet.cssRules[newruleindex]
            rule._parentStyleSheet = None # done later?

            # TODO:
            #tempsheet._namespaces = self._namespaces

        elif isinstance(rule, cssutils.css.CSSRuleList):
            # insert all rules
            for i, r in enumerate(rule):
                self.insertRule(r, index + i)
            return index

        if not rule.wellformed:
            self._log.error(u'CSSStyleSheet: Invalid rules cannot be added.')
            return

        # CHECK HIERARCHY
        # @charset
        if rule.type == rule.CHARSET_RULE:
            if inOrder:
                index = 0
                # always first and only
                if (self._cssRules
                    and self._cssRules[0].type == rule.CHARSET_RULE):
                    self._cssRules[0].encoding = rule.encoding
                else:
                    self._cssRules.insert(0, rule)
            elif index != 0 or (self._cssRules and
                              self._cssRules[0].type == rule.CHARSET_RULE):
                self._log.error(
                    u'CSSStylesheet: @charset only allowed once at the'
                    ' beginning of a stylesheet.',
                    error=xml.dom.HierarchyRequestErr)
                return
            else:
                self._cssRules.insert(index, rule)

        # @unknown or comment
        elif rule.type in (rule.UNKNOWN_RULE, rule.COMMENT) and not inOrder:
            if index == 0 and self._cssRules and\
               self._cssRules[0].type == rule.CHARSET_RULE:
                self._log.error(
                    u'CSSStylesheet: @charset must be the first rule.',
                    error=xml.dom.HierarchyRequestErr)
                return
            else:
                self._cssRules.insert(index, rule)

        # @import
        elif rule.type == rule.IMPORT_RULE:
            if inOrder:
                # automatic order
                if rule.type in (r.type for r in self):
                    # find last of this type
                    for i, r in enumerate(reversed(self._cssRules)):
                        if r.type == rule.type:
                            index = len(self._cssRules) - i
                            break
                else:
                    # find first point to insert
                    if self._cssRules and self._cssRules[0].type in (rule.CHARSET_RULE,
                                                                     rule.COMMENT):
                        index = 1
                    else:
                        index = 0
            else:
                # after @charset
                if index == 0 and self._cssRules and\
                   self._cssRules[0].type == rule.CHARSET_RULE:
                    self._log.error(
                        u'CSSStylesheet: Found @charset at index 0.',
                        error=xml.dom.HierarchyRequestErr)
                    return
                # before @namespace @variables @page @font-face @media stylerule
                for r in self._cssRules[:index]:
                    if r.type in (r.NAMESPACE_RULE, 
                                  r.VARIABLES_RULE, 
                                  r.MEDIA_RULE, 
                                  r.PAGE_RULE,
                                  r.STYLE_RULE, 
                                  r.FONT_FACE_RULE):
                        self._log.error(
                            u'CSSStylesheet: Cannot insert @import here,'
                             ' found @namespace, @variables, @media, @page or'
                             ' CSSStyleRule before index %s.' %
                            index,
                            error=xml.dom.HierarchyRequestErr)
                        return
            self._cssRules.insert(index, rule)

        # @namespace
        elif rule.type == rule.NAMESPACE_RULE:
            if inOrder:
                if rule.type in (r.type for r in self):
                    # find last of this type
                    for i, r in enumerate(reversed(self._cssRules)):
                        if r.type == rule.type:
                            index = len(self._cssRules) - i
                            break
                else:
                    # find first point to insert
                    for i, r in enumerate(self._cssRules):
                        if r.type in (r.VARIABLES_RULE, r.MEDIA_RULE, 
                                      r.PAGE_RULE, r.STYLE_RULE,
                                      r.FONT_FACE_RULE, r.UNKNOWN_RULE, 
                                      r.COMMENT):
                            index = i # before these
                            break
            else:
                # after @charset and @import
                for r in self._cssRules[index:]:
                    if r.type in (r.CHARSET_RULE, r.IMPORT_RULE):
                        self._log.error(
                            u'CSSStylesheet: Cannot insert @namespace here,'
                            ' found @charset or @import after index %s.' %
                            index,
                            error=xml.dom.HierarchyRequestErr)
                        return
                # before @variables @media @page @font-face and stylerule
                for r in self._cssRules[:index]:
                    if r.type in (r.VARIABLES_RULE, 
                                  r.MEDIA_RULE, 
                                  r.PAGE_RULE, 
                                  r.STYLE_RULE, 
                                  r.FONT_FACE_RULE):
                        self._log.error(
                            u'CSSStylesheet: Cannot insert @namespace here,'
                            ' found @variables, @media, @page or CSSStyleRule'
                            ' before index %s.' %
                            index,
                            error=xml.dom.HierarchyRequestErr)
                        return

            if not (rule.prefix in self.namespaces and
               self.namespaces[rule.prefix] == rule.namespaceURI):
                # no doublettes
                self._cssRules.insert(index, rule)
                if _clean:
                    self._cleanNamespaces()


        # @variables
        elif rule.type == rule.VARIABLES_RULE:
            if inOrder:
                if rule.type in (r.type for r in self):
                    # find last of this type
                    for i, r in enumerate(reversed(self._cssRules)):
                        if r.type == rule.type:
                            index = len(self._cssRules) - i
                            break
                else:
                    # find first point to insert
                    for i, r in enumerate(self._cssRules):
                        if r.type in (r.MEDIA_RULE, 
                                      r.PAGE_RULE, 
                                      r.STYLE_RULE,
                                      r.FONT_FACE_RULE, 
                                      r.UNKNOWN_RULE, 
                                      r.COMMENT):
                            index = i # before these
                            break
            else:
                # after @charset @import @namespace
                for r in self._cssRules[index:]:
                    if r.type in (r.CHARSET_RULE, 
                                  r.IMPORT_RULE, 
                                  r.NAMESPACE_RULE):
                        self._log.error(
                            u'CSSStylesheet: Cannot insert @variables here,'
                            ' found @charset, @import or @namespace after'
                            ' index %s.' %
                            index,
                            error=xml.dom.HierarchyRequestErr)
                        return
                # before @media @page @font-face and stylerule
                for r in self._cssRules[:index]:
                    if r.type in (r.MEDIA_RULE, 
                                  r.PAGE_RULE, 
                                  r.STYLE_RULE, 
                                  r.FONT_FACE_RULE):
                        self._log.error(
                            u'CSSStylesheet: Cannot insert @variables here,'
                            ' found @media, @page or CSSStyleRule'
                            ' before index %s.' %
                            index,
                            error=xml.dom.HierarchyRequestErr)
                        return

            self._cssRules.insert(index, rule)

        # all other where order is not important
        else:
            if inOrder:
                # simply add to end as no specific order
                self._cssRules.append(rule)
                index = len(self._cssRules) - 1
            else:
                for r in self._cssRules[index:]:
                    if r.type in (r.CHARSET_RULE, r.IMPORT_RULE, r.NAMESPACE_RULE):
                        self._log.error(
                            u'CSSStylesheet: Cannot insert rule here, found @charset, @import or @namespace before index %s.' %
                            index,
                            error=xml.dom.HierarchyRequestErr)
                        return
                self._cssRules.insert(index, rule)

        # post settings, TODO: for other rules which contain @rules
        rule._parentStyleSheet = self
        if rule.MEDIA_RULE == rule.type:
            for r in rule:
                r._parentStyleSheet = self
        # ?
        elif rule.IMPORT_RULE == rule.type:
            rule.href = rule.href # try to reload stylesheet

        return index

    ownerRule = property(lambda self: self._ownerRule,
                         doc="A ref to an @import rule if it is imported, else ``None``.")

    def setSerializer(self, cssserializer):
        """Set the cssutils global Serializer used for all output."""
        if isinstance(cssserializer, cssutils.CSSSerializer):
            cssutils.ser = cssserializer
        else:
            raise ValueError(u'Serializer must be an instance of cssutils.CSSSerializer.')

    def setSerializerPref(self, pref, value):
        """Set a Preference of CSSSerializer used for output.
        See :class:`cssutils.serialize.Preferences` for possible
        preferences to be set.
        """
        cssutils.ser.prefs.__setattr__(pref, value)
