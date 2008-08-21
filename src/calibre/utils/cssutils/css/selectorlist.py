"""SelectorList is a list of CSS Selector objects.

TODO
    - remove duplicate Selectors. -> CSSOM canonicalize

    - ??? CSS2 gives a special meaning to the comma (,) in selectors.
        However, since it is not known if the comma may acquire other
        meanings in future versions of CSS, the whole statement should be
        ignored if there is an error anywhere in the selector, even though
        the rest of the selector may look reasonable in CSS2.

        Illegal example(s):

        For example, since the "&" is not a valid token in a CSS2 selector,
        a CSS2 user agent must ignore the whole second line, and not set
        the color of H3 to red:
"""
__all__ = ['SelectorList']
__docformat__ = 'restructuredtext'
__version__ = '$Id: selectorlist.py 1174 2008-03-20 17:43:07Z cthedot $'

import xml.dom
import cssutils
from selector import Selector

class SelectorList(cssutils.util.Base, cssutils.util.ListSeq):
    """
    (cssutils) a list of Selectors of a CSSStyleRule

    Properties
    ==========
    length: of type unsigned long, readonly
        The number of Selector elements in the list.
    parentRule: of type CSSRule, readonly
        The CSS rule that contains this selector list or None if this
        list is not attached to a CSSRule.
    selectorText: of type DOMString
        The textual representation of the selector for the rule set. The
        implementation may have stripped out insignificant whitespace while
        parsing the selector.
    seq: (internal use!)
        A list of Selector objects
    wellformed
        if this selectorlist is wellformed regarding the Selector spec
    """
    def __init__(self, selectorText=None, parentRule=None,
                 readonly=False):
        """
        initializes SelectorList with optional selectorText

        :Parameters:
            selectorText
                parsable list of Selectors
            parentRule
                the parent CSSRule if available
        """
        super(SelectorList, self).__init__()

        self._parentRule = parentRule

        if selectorText:
            self.selectorText = selectorText

        self._readonly = readonly

    def __prepareset(self, newSelector, namespaces=None):
        "used by appendSelector and __setitem__"
        if not namespaces:
            namespaces = {}
        self._checkReadonly()
        if not isinstance(newSelector, Selector):
            newSelector = Selector((newSelector, namespaces),
                                   parentList=self)
        if newSelector.wellformed:
            newSelector._parent = self # maybe set twice but must be!
            return newSelector

    def __setitem__(self, index, newSelector):
        """
        overwrites ListSeq.__setitem__

        Any duplicate Selectors are **not** removed.
        """
        newSelector = self.__prepareset(newSelector)
        if newSelector:
            self.seq[index] = newSelector

    def append(self, newSelector):
        "same as appendSelector(newSelector)"
        self.appendSelector(newSelector)

    length = property(lambda self: len(self),
        doc="The number of Selector elements in the list.")


    def __getNamespaces(self):
        "uses children namespaces if not attached to a sheet, else the sheet's ones"
        try:
            return self.parentRule.parentStyleSheet.namespaces
        except AttributeError:
            namespaces = {}
            for selector in self.seq:
                namespaces.update(selector._namespaces)
            return namespaces

    _namespaces = property(__getNamespaces, doc="""if this SelectorList is
        attached to a CSSStyleSheet the namespaces of that sheet are mirrored
        here. While the SelectorList (or parentRule(s) are
        not attached the namespaces of all children Selectors are used.""")

    parentRule = property(lambda self: self._parentRule,
        doc="(DOM) The CSS rule that contains this SelectorList or\
        None if this SelectorList is not attached to a CSSRule.")

    def _getSelectorText(self):
        "returns serialized format"
        return cssutils.ser.do_css_SelectorList(self)

    def _setSelectorText(self, selectorText):
        """
        :param selectorText:
            comma-separated list of selectors or a tuple of
            (selectorText, dict-of-namespaces)
        :Exceptions:
            - `NAMESPACE_ERR`: (Selector)
              Raised if the specified selector uses an unknown namespace
              prefix.
            - `SYNTAX_ERR`: (self)
              Raised if the specified CSS string value has a syntax error
              and is unparsable.
            - `NO_MODIFICATION_ALLOWED_ERR`: (self)
              Raised if this rule is readonly.
        """
        self._checkReadonly()

        # might be (selectorText, namespaces)
        selectorText, namespaces = self._splitNamespacesOff(selectorText)
        try:
            # use parent's only if available
            namespaces = self.parentRule.parentStyleSheet.namespaces
        except AttributeError:
            pass

        wellformed = True
        tokenizer = self._tokenize2(selectorText)
        newseq = []

        expected = True
        while True:
            # find all upto and including next ",", EOF or nothing
            selectortokens = self._tokensupto2(tokenizer, listseponly=True)
            if selectortokens:
                if self._tokenvalue(selectortokens[-1]) == ',':
                    expected = selectortokens.pop()
                else:
                    expected = None

                selector = Selector((selectortokens, namespaces),
                                    parentList=self)
                if selector.wellformed:
                    newseq.append(selector)
                else:
                    wellformed = False
                    self._log.error(u'SelectorList: Invalid Selector: %s' %
                                    self._valuestr(selectortokens))
            else:
                break

        # post condition
        if u',' == expected:
            wellformed = False
            self._log.error(u'SelectorList: Cannot end with ",": %r' %
                            self._valuestr(selectorText))
        elif expected:
            wellformed = False
            self._log.error(u'SelectorList: Unknown Syntax: %r' %
                            self._valuestr(selectorText))
        if wellformed:
            self.seq = newseq
#            for selector in newseq:
#                 self.appendSelector(selector)

    selectorText = property(_getSelectorText, _setSelectorText,
        doc="""(cssutils) The textual representation of the selector for
            a rule set.""")

    wellformed = property(lambda self: bool(len(self.seq)))

    def appendSelector(self, newSelector):
        """
        Append newSelector (a string will be converted to a new
        Selector).

        :param newSelector:
            comma-separated list of selectors or a tuple of
            (selectorText, dict-of-namespaces)
        :returns: New Selector or None if newSelector is not wellformed.
        :Exceptions:
            - `NAMESPACE_ERR`: (self)
              Raised if the specified selector uses an unknown namespace
              prefix.
            - `SYNTAX_ERR`: (self)
              Raised if the specified CSS string value has a syntax error
              and is unparsable.
            - `NO_MODIFICATION_ALLOWED_ERR`: (self)
              Raised if this rule is readonly.
        """
        self._checkReadonly()

        # might be (selectorText, namespaces)
        newSelector, namespaces = self._splitNamespacesOff(newSelector)
        try:
            # use parent's only if available
            namespaces = self.parentRule.parentStyleSheet.namespaces
        except AttributeError:
            # use already present namespaces plus new given ones
            _namespaces = self._namespaces
            _namespaces.update(namespaces)
            namespaces = _namespaces

        newSelector = self.__prepareset(newSelector, namespaces)
        if newSelector:
            seq = self.seq[:]
            del self.seq[:]
            for s in seq:
                if s.selectorText != newSelector.selectorText:
                    self.seq.append(s)
            self.seq.append(newSelector)
            return newSelector

    def __repr__(self):
        if self._namespaces:
            st = (self.selectorText, self._namespaces)
        else:
            st = self.selectorText
        return "cssutils.css.%s(selectorText=%r)" % (
                self.__class__.__name__, st)

    def __str__(self):
        return "<cssutils.css.%s object selectorText=%r _namespaces=%r at 0x%x>" % (
                self.__class__.__name__, self.selectorText, self._namespaces,
                id(self))

    def _getUsedUris(self):
        "used by CSSStyleSheet to check if @namespace rules are needed"
        uris = set()
        for s in self:
            uris.update(s._getUsedUris())
        return uris
