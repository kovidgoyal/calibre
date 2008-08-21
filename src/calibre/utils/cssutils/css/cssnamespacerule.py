"""CSSNamespaceRule currently implements
http://dev.w3.org/csswg/css3-namespace/

(until 0.9.5a2: http://www.w3.org/TR/2006/WD-css3-namespace-20060828/)
"""
__all__ = ['CSSNamespaceRule']
__docformat__ = 'restructuredtext'
__version__ = '$Id: cssnamespacerule.py 1305 2008-06-22 18:42:51Z cthedot $'

import xml.dom
import cssrule
import cssutils
from cssutils.helper import Deprecated

class CSSNamespaceRule(cssrule.CSSRule):
    """
    Represents an @namespace rule within a CSS style sheet.

    The @namespace at-rule declares a namespace prefix and associates
    it with a given namespace (a string). This namespace prefix can then be
    used in namespace-qualified names such as those described in the
    Selectors Module [SELECT] or the Values and Units module [CSS3VAL].

    Properties
    ==========
    atkeyword (cssutils only)
        the literal keyword used
    cssText: of type DOMString
        The parsable textual representation of this rule
    namespaceURI: of type DOMString
        The namespace URI (a simple string!) which is bound to the given
        prefix. If no prefix is set (``CSSNamespaceRule.prefix==''``)
        the namespace defined by ``namespaceURI`` is set as the default 
        namespace.
    prefix: of type DOMString
        The prefix used in the stylesheet for the given
        ``CSSNamespaceRule.nsuri``. If prefix is empty namespaceURI sets a 
        default namespace for the stylesheet.

    Inherits properties from CSSRule

    Format
    ======
    namespace
      : NAMESPACE_SYM S* [namespace_prefix S*]? [STRING|URI] S* ';' S*
      ;
    namespace_prefix
      : IDENT
      ;
    """
    type = property(lambda self: cssrule.CSSRule.NAMESPACE_RULE)

    def __init__(self, namespaceURI=None, prefix=None, cssText=None, 
                 parentRule=None, parentStyleSheet=None, readonly=False):
        """
        :Parameters:
            namespaceURI
                The namespace URI (a simple string!) which is bound to the
                given prefix. If no prefix is set
                (``CSSNamespaceRule.prefix==''``) the namespace defined by
                namespaceURI is set as the default namespace
            prefix
                The prefix used in the stylesheet for the given
                ``CSSNamespaceRule.uri``.
            cssText
                if no namespaceURI is given cssText must be given to set
                a namespaceURI as this is readonly later on
            parentStyleSheet
                sheet where this rule belongs to

        Do not use as positional but as keyword parameters only!

        If readonly allows setting of properties in constructor only

        format namespace::

            namespace
              : NAMESPACE_SYM S* [namespace_prefix S*]? [STRING|URI] S* ';' S*
              ;
            namespace_prefix
              : IDENT
              ;
        """
        super(CSSNamespaceRule, self).__init__(parentRule=parentRule, 
                                               parentStyleSheet=parentStyleSheet)
        self._atkeyword = u'@namespace'
        self._prefix = u''
        self._namespaceURI = None
        
        if namespaceURI:
            self.namespaceURI = namespaceURI
            self.prefix = prefix
            tempseq = self._tempSeq()
            tempseq.append(self.prefix, 'prefix')
            tempseq.append(self.namespaceURI, 'namespaceURI')
            self._setSeq(tempseq)
        elif cssText is not None:
            self.cssText = cssText

        if parentStyleSheet:
            self._parentStyleSheet = parentStyleSheet

        self._readonly = readonly

    def _getCssText(self):
        """
        returns serialized property cssText
        """
        return cssutils.ser.do_CSSNamespaceRule(self)

    def _setCssText(self, cssText):
        """
        DOMException on setting

        :param cssText: initial value for this rules cssText which is parsed
        :Exceptions:
            - `HIERARCHY_REQUEST_ERR`: (CSSStylesheet)
              Raised if the rule cannot be inserted at this point in the
              style sheet.
            - `INVALID_MODIFICATION_ERR`: (self)
              Raised if the specified CSS string value represents a different
              type of rule than the current one.
            - `NO_MODIFICATION_ALLOWED_ERR`: (CSSRule)
              Raised if the rule is readonly.
            - `SYNTAX_ERR`: (self)
              Raised if the specified CSS string value has a syntax error and
              is unparsable.
        """
        super(CSSNamespaceRule, self)._setCssText(cssText)
        tokenizer = self._tokenize2(cssText)
        attoken = self._nexttoken(tokenizer, None)
        if self._type(attoken) != self._prods.NAMESPACE_SYM:
            self._log.error(u'CSSNamespaceRule: No CSSNamespaceRule found: %s' %
                self._valuestr(cssText),
                error=xml.dom.InvalidModificationErr)
        else:
            # for closures: must be a mutable
            new = {'keyword': self._tokenvalue(attoken),
                   'prefix': u'',
                   'uri': None,
                   'wellformed': True
                   }

            def _ident(expected, seq, token, tokenizer=None):
                # the namespace prefix, optional
                if 'prefix or uri' == expected:
                    new['prefix'] = self._tokenvalue(token)
                    seq.append(new['prefix'], 'prefix')
                    return 'uri'
                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'CSSNamespaceRule: Unexpected ident.', token)
                    return expected

            def _string(expected, seq, token, tokenizer=None):
                # the namespace URI as a STRING
                if expected.endswith('uri'):
                    new['uri'] = self._stringtokenvalue(token)
                    seq.append(new['uri'], 'namespaceURI')
                    return ';'

                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'CSSNamespaceRule: Unexpected string.', token)
                    return expected

            def _uri(expected, seq, token, tokenizer=None):
                # the namespace URI as URI which is DEPRECATED
                if expected.endswith('uri'):
                    uri = self._uritokenvalue(token)
                    new['uri'] = uri
                    seq.append(new['uri'], 'namespaceURI')
                    return ';'
                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'CSSNamespaceRule: Unexpected URI.', token)
                    return expected

            def _char(expected, seq, token, tokenizer=None):
                # final ;
                val = self._tokenvalue(token)
                if ';' == expected and u';' == val:
                    return 'EOF'
                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'CSSNamespaceRule: Unexpected char.', token)
                    return expected

            # "NAMESPACE_SYM S* [namespace_prefix S*]? [STRING|URI] S* ';' S*"
            newseq = self._tempSeq()
            wellformed, expected = self._parse(expected='prefix or uri',
                seq=newseq, tokenizer=tokenizer,
                productions={'IDENT': _ident,
                             'STRING': _string,
                             'URI': _uri,
                             'CHAR': _char},
                new=new)

            # wellformed set by parse
            wellformed = wellformed and new['wellformed']

            # post conditions
            if new['uri'] is None:
                wellformed = False
                self._log.error(u'CSSNamespaceRule: No namespace URI found: %s' %
                    self._valuestr(cssText))

            if expected != 'EOF':
                wellformed = False
                self._log.error(u'CSSNamespaceRule: No ";" found: %s' %
                    self._valuestr(cssText))

            # set all
            if wellformed:
                self.atkeyword = new['keyword']
                self._prefix = new['prefix']
                self.namespaceURI = new['uri']
                self._setSeq(newseq)

    cssText = property(fget=_getCssText, fset=_setCssText,
        doc="(DOM attribute) The parsable textual representation.")

    def _setNamespaceURI(self, namespaceURI):
        """
        DOMException on setting
    
        :param namespaceURI: the initial value for this rules namespaceURI
        :Exceptions:
            - `NO_MODIFICATION_ALLOWED_ERR`: 
              (CSSRule) Raised if this rule is readonly or a namespaceURI is 
              already set in this rule.
        """
        self._checkReadonly()
        if not self._namespaceURI:
            # initial setting
            self._namespaceURI = namespaceURI
            tempseq = self._tempSeq()
            tempseq.append(namespaceURI, 'namespaceURI')
            self._setSeq(tempseq) # makes seq readonly!
        elif self._namespaceURI != namespaceURI:
            self._log.error(u'CSSNamespaceRule: namespaceURI is readonly.',
                            error=xml.dom.NoModificationAllowedErr)

    namespaceURI = property(lambda self: self._namespaceURI, _setNamespaceURI,
        doc="URI (string!) of the defined namespace.")

    def _setPrefix(self, prefix=None):
        """
        DOMException on setting
        
        :param prefix: the new prefix 
        :Exceptions:
            - `SYNTAX_ERR`: (TODO)
              Raised if the specified CSS string value has a syntax error and
              is unparsable.
            - `NO_MODIFICATION_ALLOWED_ERR`: CSSRule)
              Raised if this rule is readonly.
        """
        self._checkReadonly()
        if not prefix:
            prefix = u''
        else:        
            tokenizer = self._tokenize2(prefix)
            prefixtoken = self._nexttoken(tokenizer, None)
            if not prefixtoken or self._type(prefixtoken) != self._prods.IDENT:
                self._log.error(u'CSSNamespaceRule: No valid prefix "%s".' %
                    self._valuestr(prefix),
                    error=xml.dom.SyntaxErr)
                return
            else:
                prefix = self._tokenvalue(prefixtoken)
        # update seg
        for i, x in enumerate(self._seq):
            if x == self._prefix:
                self._seq[i] = (prefix, 'prefix', None, None)
                break
        else:
            # put prefix at the beginning!
            self._seq[0] = (prefix, 'prefix', None, None) 

        # set new prefix
        self._prefix = prefix

    prefix = property(lambda self: self._prefix, _setPrefix,
        doc="Prefix used for the defined namespace.")

#    def _setParentStyleSheet(self, parentStyleSheet):
#        self._parentStyleSheet = parentStyleSheet
#
#    parentStyleSheet = property(lambda self: self._parentStyleSheet, 
#                                _setParentStyleSheet,
#                                doc=u"Containing CSSStyleSheet.")

    wellformed = property(lambda self: self.namespaceURI is not None)

    def __repr__(self):
        return "cssutils.css.%s(namespaceURI=%r, prefix=%r)" % (
                self.__class__.__name__, self.namespaceURI, self.prefix)

    def __str__(self):
        return "<cssutils.css.%s object namespaceURI=%r prefix=%r at 0x%x>" % (
                self.__class__.__name__, self.namespaceURI, self.prefix, id(self))
