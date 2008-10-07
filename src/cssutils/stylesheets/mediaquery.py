"""
MediaQuery, see http://www.w3.org/TR/css3-mediaqueries/

A cssutils own implementation, not defined in official DOM

TODO:
    add possibility to

part of a media_query_list: <media_query> [, <media_query> ]*
see stylesheets.MediaList
"""
__all__ = ['MediaQuery']
__docformat__ = 'restructuredtext'
__version__ = '$Id: mediaquery.py 1363 2008-07-13 18:14:26Z cthedot $'

import re
import xml.dom
import cssutils

class MediaQuery(cssutils.util.Base):
    """
    A Media Query consists of a media type and one or more
    expressions involving media features.

    Properties
    ==========
    mediaText: of type DOMString
        The parsable textual representation of this MediaQuery
    mediaType: of type DOMString
        one of MEDIA_TYPES like e.g. 'print'
    seq: a list (cssutils)
        All parts of this MediaQuery including CSSComments
    wellformed:
        if this query is wellformed

    Format
    ======
    ::
    
        media_query: [[only | not]? <media_type> [ and <expression> ]*]
          | <expression> [ and <expression> ]*
        expression: ( <media_feature> [: <value>]? )
        media_type: all | aural | braille | handheld | print |
          projection | screen | tty | tv | embossed
        media_feature: width | min-width | max-width
          | height | min-height | max-height
          | device-width | min-device-width | max-device-width
          | device-height | min-device-height | max-device-height
          | device-aspect-ratio | min-device-aspect-ratio | max-device-aspect-ratio
          | color | min-color | max-color
          | color-index | min-color-index | max-color-index
          | monochrome | min-monochrome | max-monochrome
          | resolution | min-resolution | max-resolution
          | scan | grid
          
    """
    MEDIA_TYPES = [u'all', u'aural', u'braille', u'embossed', u'handheld',
        u'print', u'projection', u'screen', u'tty', u'tv']

    # From the HTML spec (see MediaQuery):
    # "[...] character that isn't a US ASCII letter [a-zA-Z] (Unicode
    # decimal 65-90, 97-122), digit [0-9] (Unicode hex 30-39), or hyphen (45)."
    # so the following is a valid mediaType
    __mediaTypeMatch = re.compile(ur'^[-a-zA-Z0-9]+$', re.U).match

    def __init__(self, mediaText=None, readonly=False):
        """
        mediaText
            unicodestring of parsable media
        """
        super(MediaQuery, self).__init__()

        self.seq = []
        self._mediaType = u''
        if mediaText:
            self.mediaText = mediaText # sets self._mediaType too

        self._readonly = readonly

    def _getMediaText(self):
        """
        returns serialized property mediaText
        """
        return cssutils.ser.do_stylesheets_mediaquery(self)

    def _setMediaText(self, mediaText):
        """
        mediaText
            a single media query string, e.g. "print and (min-width: 25cm)"

        DOMException

        - SYNTAX_ERR: (self)
          Raised if the specified string value has a syntax error and is
          unparsable.
        - INVALID_CHARACTER_ERR: (self)
          Raised if the given mediaType is unknown.
        - NO_MODIFICATION_ALLOWED_ERR: (self)
          Raised if this media query is readonly.
        """
        self._checkReadonly()
        tokenizer = self._tokenize2(mediaText)
        if not tokenizer:
            self._log.error(u'MediaQuery: No MediaText given.')
        else:
            # for closures: must be a mutable
            new = {'mediatype': None,
                   'wellformed': True }

            def _ident_or_dim(expected, seq, token, tokenizer=None):
                # only|not or mediatype or and
                val = self._tokenvalue(token)
                nval = self._normalize(val)
                if expected.endswith('mediatype'):
                    if nval in (u'only', u'not'):
                        # only or not
                        seq.append(val)
                        return 'mediatype'
                    else:
                        # mediatype
                        new['mediatype'] = val
                        seq.append(val)
                        return 'and'
                elif 'and' == nval and expected.startswith('and'):
                    seq.append(u'and')
                    return 'feature'
                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'MediaQuery: Unexpected syntax.', token=token)
                    return expected

            def _char(expected, seq, token, tokenizer=None):
                # starting a feature which basically is a CSS Property
                # but may simply be a property name too
                val = self._tokenvalue(token)
                if val == u'(' and expected == 'feature':
                    proptokens = self._tokensupto2(
                        tokenizer, funcendonly=True)
                    if proptokens and u')' == self._tokenvalue(proptokens[-1]):
                        proptokens.pop()
                    property = cssutils.css.Property(_mediaQuery=True)
                    property.cssText = proptokens
                    seq.append(property)
                    return 'and or EOF'
                else:
                    new['wellformed'] = False
                    self._log.error(
                        u'MediaQuery: Unexpected syntax, expected "and" but found "%s".' %
                        val, token)
                    return expected

            # expected: only|not or mediatype, mediatype, feature, and
            newseq = []
            wellformed, expected = self._parse(expected='only|not or mediatype',
                seq=newseq, tokenizer=tokenizer,
                productions={'IDENT': _ident_or_dim, # e.g. "print"
                             'DIMENSION': _ident_or_dim, # e.g. "3d"
                             'CHAR': _char})
            wellformed = wellformed and new['wellformed']

            # post conditions
            if not new['mediatype']:
                wellformed = False
                self._log.error(u'MediaQuery: No mediatype found: %s' %
                    self._valuestr(mediaText))

            if wellformed:
                # set
                self.mediaType = new['mediatype']
                self.seq = newseq

    mediaText = property(_getMediaText, _setMediaText,
        doc="""(DOM) The parsable textual representation of the media list.
            This is a comma-separated list of media.""")

    def _getMediaType(self):
        """
        returns serialized property mediaText
        """
        return self._mediaType

    def _setMediaType(self, mediaType):
        """
        mediaType
            one of MEDIA_TYPES

        DOMException

        - SYNTAX_ERR: (self)
          Raised if the specified string value has a syntax error and is
          unparsable.
        - INVALID_CHARACTER_ERR: (self)
          Raised if the given mediaType is unknown.
        - NO_MODIFICATION_ALLOWED_ERR: (self)
          Raised if this media query is readonly.
        """
        self._checkReadonly()
        nmediaType = self._normalize(mediaType)

        if not MediaQuery.__mediaTypeMatch(nmediaType):
            self._log.error(
                u'MediaQuery: Syntax Error in media type "%s".' % mediaType,
                error=xml.dom.SyntaxErr)
        else:
            if nmediaType not in MediaQuery.MEDIA_TYPES:
                self._log.warn(
                    u'MediaQuery: Unknown media type "%s".' % mediaType,
                    error=xml.dom.InvalidCharacterErr)
                return

            # set
            self._mediaType = mediaType

            # update seq
            for i, x in enumerate(self.seq):
                if isinstance(x, basestring):
                    if self._normalize(x) in (u'only', u'not'):
                        continue
                    else:
                        self.seq[i] = mediaType
                        break
            else:
                self.seq.insert(0, mediaType)

    mediaType = property(_getMediaType, _setMediaType,
        doc="""(DOM) media type (one of MediaQuery.MEDIA_TYPES) of this MediaQuery.""")

    wellformed = property(lambda self: bool(len(self.seq)))

    def __repr__(self):
        return "cssutils.stylesheets.%s(mediaText=%r)" % (
                self.__class__.__name__, self.mediaText)

    def __str__(self):
        return "<cssutils.stylesheets.%s object mediaText=%r at 0x%x>" % (
                self.__class__.__name__, self.mediaText, id(self))
