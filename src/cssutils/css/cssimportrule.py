"""CSSImportRule implements DOM Level 2 CSS CSSImportRule plus the 
``name`` property from http://www.w3.org/TR/css3-cascade/#cascading."""
__all__ = ['CSSImportRule']
__docformat__ = 'restructuredtext'
__version__ = '$Id: cssimportrule.py 1871 2009-10-17 19:57:37Z cthedot $'

import cssrule
import cssutils
import os
import urllib
import urlparse
import xml.dom

class CSSImportRule(cssrule.CSSRule):
    """
    Represents an @import rule within a CSS style sheet.  The @import rule
    is used to import style rules from other style sheets.

    Format::

        import
          : IMPORT_SYM S*
          [STRING|URI] S* [ medium [ COMMA S* medium]* ]? S* STRING? S* ';' S*
          ;
    """
    def __init__(self, href=None, mediaText=u'all', name=None,
                 parentRule=None, parentStyleSheet=None, readonly=False):
        """
        if readonly allows setting of properties in constructor only

        Do not use as positional but as keyword attributes only!

        href
            location of the style sheet to be imported.
        mediaText
            A list of media types for which this style sheet may be used
            as a string
        """
        super(CSSImportRule, self).__init__(parentRule=parentRule,
                                            parentStyleSheet=parentStyleSheet)
        self._atkeyword = u'@import'
        self.hreftype = None
        self._styleSheet = None

        self._href = None
        self.href = href

        self._media = cssutils.stylesheets.MediaList()
        if mediaText:
            self._media.mediaText = mediaText

        self._name = name

        seq = self._tempSeq()
        seq.append(self.href, 'href')
        seq.append(self.media, 'media')
        seq.append(self.name, 'name')            
        self._setSeq(seq)
        self._readonly = readonly

    def __repr__(self):
        if self._usemedia:
            mediaText = self.media.mediaText
        else:
            mediaText = None
        return "cssutils.css.%s(href=%r, mediaText=%r, name=%r)" % (
                self.__class__.__name__,
                self.href, self.media.mediaText, self.name)

    def __str__(self):
        if self._usemedia:
            mediaText = self.media.mediaText
        else:
            mediaText = None
        return "<cssutils.css.%s object href=%r mediaText=%r name=%r at 0x%x>" % (
                self.__class__.__name__, self.href, mediaText, self.name, id(self))

    _usemedia = property(lambda self: self.media.mediaText not in (u'', u'all'),
                         doc="if self._media is used (or simply empty)")

    def _getCssText(self):
        """Return serialized property cssText."""
        return cssutils.ser.do_CSSImportRule(self)

    def _setCssText(self, cssText):
        """
        :exceptions:    
            - :exc:`~xml.dom.HierarchyRequestErr`:
              Raised if the rule cannot be inserted at this point in the
              style sheet.
            - :exc:`~xml.dom.InvalidModificationErr`:
              Raised if the specified CSS string value represents a different
              type of rule than the current one.
            - :exc:`~xml.dom.NoModificationAllowedErr`:
              Raised if the rule is readonly.
            - :exc:`~xml.dom.SyntaxErr`:
              Raised if the specified CSS string value has a syntax error and
              is unparsable.
        """
        super(CSSImportRule, self)._setCssText(cssText)
        tokenizer = self._tokenize2(cssText)
        attoken = self._nexttoken(tokenizer, None)
        if self._type(attoken) != self._prods.IMPORT_SYM:
            self._log.error(u'CSSImportRule: No CSSImportRule found: %s' %
                self._valuestr(cssText),
                error=xml.dom.InvalidModificationErr)
        else:
            # save if parse goes wrong
            oldmedia = cssutils.stylesheets.MediaList()
            oldmedia._absorb(self.media)
            
            # for closures: must be a mutable
            new = {'keyword': self._tokenvalue(attoken),
                   'href': None,
                   'hreftype': None,
                   'media': None,
                   'name': None,
                   'wellformed': True
                   }

            def __doname(seq, token):
                # called by _string or _ident
                new['name'] = self._stringtokenvalue(token)
                seq.append(new['name'], 'name')
                return ';'

            def _string(expected, seq, token, tokenizer=None):
                if 'href' == expected:
                    # href
                    new['href'] = self._stringtokenvalue(token)
                    new['hreftype'] = 'string'
                    seq.append(new['href'], 'href')
                    return 'media name ;'
                elif 'name' in expected:
                    # name
                    return __doname(seq, token)
                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'CSSImportRule: Unexpected string.', token)
                    return expected

            def _uri(expected, seq, token, tokenizer=None):
                # href
                if 'href' == expected:
                    uri = self._uritokenvalue(token)
                    new['hreftype'] = 'uri'
                    new['href'] = uri
                    seq.append(new['href'], 'href')
                    return 'media name ;'
                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'CSSImportRule: Unexpected URI.', token)
                    return expected

            def _ident(expected, seq, token, tokenizer=None):
                # medialist ending with ; which is checked upon too
                if expected.startswith('media'):
                    mediatokens = self._tokensupto2(
                        tokenizer, importmediaqueryendonly=True)
                    mediatokens.insert(0, token) # push found token

                    last = mediatokens.pop() # retrieve ;
                    lastval, lasttyp = self._tokenvalue(last), self._type(last)
                    if lastval != u';' and lasttyp not in ('EOF', self._prods.STRING):
                        new['wellformed'] = False
                        self._log.error(u'CSSImportRule: No ";" found: %s' %
                                        self._valuestr(cssText), token=token)

                    #media = cssutils.stylesheets.MediaList()
                    self.media.mediaText = mediatokens
                    if self.media.wellformed:
                        new['media'] = self.media
                        seq.append(self.media, 'media')
                    else:
                        # RESET
                        self.media._absorb(oldmedia)
                        new['wellformed'] = False
                        self._log.error(u'CSSImportRule: Invalid MediaList: %s' %
                                        self._valuestr(cssText), token=token)

                    if lasttyp == self._prods.STRING:
                        # name
                        return __doname(seq, last)
                    else:
                        return 'EOF' # ';' is token "last"
                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'CSSImportRule: Unexpected ident.', token)
                    return expected

            def _char(expected, seq, token, tokenizer=None):
                # final ;
                val = self._tokenvalue(token)
                if expected.endswith(';') and u';' == val:
                    return 'EOF'
                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'CSSImportRule: Unexpected char.', token)
                    return expected

            # import : IMPORT_SYM S* [STRING|URI]
            #            S* [ medium [ ',' S* medium]* ]? ';' S*
            #         STRING? # see http://www.w3.org/TR/css3-cascade/#cascading
            #        ;
            newseq = self._tempSeq()
            wellformed, expected = self._parse(expected='href',
                seq=newseq, tokenizer=tokenizer,
                productions={'STRING': _string,
                             'URI': _uri,
                             'IDENT': _ident,
                             'CHAR': _char},
                new=new)

            # wellformed set by parse
            wellformed = wellformed and new['wellformed']

            # post conditions
            if not new['href']:
                wellformed = False
                self._log.error(u'CSSImportRule: No href found: %s' %
                    self._valuestr(cssText))

            if expected != 'EOF':
                wellformed = False
                self._log.error(u'CSSImportRule: No ";" found: %s' %
                    self._valuestr(cssText))

            # set all
            if wellformed:
                self.atkeyword = new['keyword']
                self.hreftype = new['hreftype']
                if not new['media']:
                	# reset media to base media 
                    self.media.mediaText = u'all'
                    newseq.append(self.media, 'media')
                self.name = new['name']
                self._setSeq(newseq)
                self.href = new['href']

                if self.styleSheet:
                    # title is set by href
                    #self.styleSheet._href = self.href
                    self.styleSheet._parentStyleSheet = self.parentStyleSheet

    cssText = property(fget=_getCssText, fset=_setCssText,
        doc="(DOM) The parsable textual representation of this rule.")

    def _setHref(self, href):
        # update seq
        for i, item in enumerate(self.seq):
            val, typ = item.value, item.type
            if 'href' == typ:
                self._seq[i] = (href, typ, item.line, item.col)
                break
        else:
            seq = self._tempSeq()
            seq.append(self.href, 'href')
            self._setSeq(seq)
        # set new href
        self._href = href
        if not self.styleSheet:
            # set only if not set before
            self.__setStyleSheet()

    href = property(lambda self: self._href, _setHref,
                    doc="Location of the style sheet to be imported.")

    media = property(lambda self: self._media,
                     doc="(DOM readonly) A list of media types for this rule "
                         "of type :class:`~cssutils.stylesheets.MediaList`.")

    def _setName(self, name):
        """Raises xml.dom.SyntaxErr if name is not a string."""
        if isinstance(name, basestring) or name is None:
            # "" or ''
            if not name:
                name = None
            # update seq
            for i, item in enumerate(self.seq):
                val, typ = item.value, item.type
                if 'name' == typ:
                    self._seq[i] = (name, typ, item.line, item.col)
                    break
            else:
                # append
                seq = self._tempSeq()
                for item in self.seq:
                    # copy current seq
                    seq.append(item.value, item.type, item.line, item.col)
                seq.append(name, 'name')
                self._setSeq(seq)
            self._name = name
            # set title of referred sheet
            if self.styleSheet:
                self.styleSheet.title = name
        else:
            self._log.error(u'CSSImportRule: Not a valid name: %s' % name)

    name = property(lambda self: self._name, _setName,
                    doc=u"An optional name for the imported sheet.")

    def __setStyleSheet(self):
        """Read new CSSStyleSheet cssText from href using parentStyleSheet.href

        Indirectly called if setting ``href``. In case of any error styleSheet 
        is set to ``None``.
        """
        # should simply fail so all errors are catched!
        if self.parentStyleSheet and self.href:
            # relative href
            parentHref = self.parentStyleSheet.href
            if parentHref is None:
                # use cwd instead
                #parentHref = u'file:' + urllib.pathname2url(os.getcwd()) + '/'
                parentHref = cssutils.helper.path2url(os.getcwd()) + '/'
            href = urlparse.urljoin(parentHref, self.href)

            # all possible exceptions are ignored (styleSheet is None then)
            try:
                usedEncoding, enctype, cssText = self.parentStyleSheet._resolveImport(href)
                if cssText is None:
                    # catched in next except below!
                    raise IOError('Cannot read Stylesheet.')
                styleSheet = cssutils.css.CSSStyleSheet(href=href,
                                                      media=self.media,
                                                      ownerRule=self,
                                                      title=self.name)
                # inherit fetcher for @imports in styleSheet
                styleSheet._setFetcher(self.parentStyleSheet._fetcher)
                # contentEncoding with parentStyleSheet.overrideEncoding,
                # HTTP or parent
                encodingOverride, encoding = None, None
                if enctype == 0:
                    encodingOverride = usedEncoding
                elif 5 > enctype > 0:
                    encoding = usedEncoding
                
                styleSheet._setCssTextWithEncodingOverride(cssText, 
                                                         encodingOverride=encodingOverride,
                                                         encoding=encoding)

            except (OSError, IOError, ValueError), e:
                self._log.warn(u'CSSImportRule: While processing imported style sheet href=%r: %r'
                               % (self.href, e), neverraise=True)
            else:
                self._styleSheet = styleSheet

    styleSheet = property(lambda self: self._styleSheet,
                          doc="(readonly) The style sheet referred to by this rule.")

    type = property(lambda self: self.IMPORT_RULE, 
                    doc="The type of this rule, as defined by a CSSRule "
                        "type constant.")

    def _getWellformed(self):
        "Depending if media is used at all."
        if self._usemedia:
            return bool(self.href and self.media.wellformed)
        else:
            return bool(self.href)

    wellformed = property(_getWellformed)
