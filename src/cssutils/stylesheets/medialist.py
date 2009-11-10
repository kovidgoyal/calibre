"""MediaList implements DOM Level 2 Style Sheets MediaList.

TODO:
    - delete: maybe if deleting from all, replace *all* with all others?
    - is unknown media an exception?
"""
__all__ = ['MediaList']
__docformat__ = 'restructuredtext'
__version__ = '$Id: medialist.py 1871 2009-10-17 19:57:37Z cthedot $'

from cssutils.css import csscomment
from mediaquery import MediaQuery
import cssutils
import xml.dom

class MediaList(cssutils.util.Base, cssutils.util.ListSeq):
    """Provides the abstraction of an ordered collection of media,
    without defining or constraining how this collection is
    implemented.

    A single media in the list is an instance of :class:`MediaQuery`. 
    An empty list is the same as a list that contains the medium "all".

    Format from CSS2.1::

        medium [ COMMA S* medium ]*

    New format with :class:`MediaQuery`::

        <media_query> [, <media_query> ]*
    """
    def __init__(self, mediaText=None, readonly=False):
        """
        :param mediaText:
            Unicodestring of parsable comma separared media
            or a (Python) list of media.
        :param readonly:
            Not used yet.
        """
        super(MediaList, self).__init__()
        self._wellformed = False

        if isinstance(mediaText, list):
            mediaText = u','.join(mediaText)

        if mediaText:
            self.mediaText = mediaText

        self._readonly = readonly

    def __repr__(self):
        return "cssutils.stylesheets.%s(mediaText=%r)" % (
                self.__class__.__name__, self.mediaText)

    def __str__(self):
        return "<cssutils.stylesheets.%s object mediaText=%r at 0x%x>" % (
                self.__class__.__name__, self.mediaText, id(self))

    def _absorb(self, other):
        """Replace all own data with data from other object."""
        #self._parentRule = other._parentRule
        self.seq[:] = other.seq[:]
        self._readonly = other._readonly


    length = property(lambda self: len(self),
        doc="The number of media in the list (DOM readonly).")

    def _getMediaText(self):
        return cssutils.ser.do_stylesheets_medialist(self)

    def _setMediaText(self, mediaText):
        """
        :param mediaText:
            simple value or comma-separated list of media

        :exceptions:
            - - :exc:`~xml.dom.SyntaxErr`:
              Raised if the specified string value has a syntax error and is
              unparsable.
            - - :exc:`~xml.dom.NoModificationAllowedErr`:
              Raised if this media list is readonly.
        """
        self._checkReadonly()
        wellformed = True
        tokenizer = self._tokenize2(mediaText)
        newseq = []

        expected = None
        while True:
            # find all upto and including next ",", EOF or nothing
            mqtokens = self._tokensupto2(tokenizer, listseponly=True)
            if mqtokens:
                if self._tokenvalue(mqtokens[-1]) == ',':
                    expected = mqtokens.pop()
                else:
                    expected = None

                mq = MediaQuery(mqtokens)
                if mq.wellformed:
                    newseq.append(mq)
                else:
                    wellformed = False
                    self._log.error(u'MediaList: Invalid MediaQuery: %s' %
                                    self._valuestr(mqtokens))
            else:
                break

        # post condition
        if expected:
            wellformed = False
            self._log.error(u'MediaList: Cannot end with ",".')

        if wellformed:
            del self[:]
            for mq in newseq:
                self.appendMedium(mq)
            self._wellformed = True

    mediaText = property(_getMediaText, _setMediaText,
        doc="The parsable textual representation of the media list.")

    def __prepareset(self, newMedium):
        # used by appendSelector and __setitem__
        self._checkReadonly()

        if not isinstance(newMedium, MediaQuery):
            newMedium = MediaQuery(newMedium)

        if newMedium.wellformed:
            return newMedium

    def __setitem__(self, index, newMedium):
        """Overwriting ListSeq.__setitem__

        Any duplicate items are **not yet** removed.
        """
        newMedium = self.__prepareset(newMedium)
        if newMedium:
            self.seq[index] = newMedium
        # TODO: remove duplicates?

    def appendMedium(self, newMedium):
        """Add the `newMedium` to the end of the list. 
        If the `newMedium` is already used, it is first removed.
        
        :param newMedium:
            a string or a :class:`~cssutils.stylesheets.MediaQuery`
        :returns: Wellformedness of `newMedium`.
        :exceptions:
            - :exc:`~xml.dom.InvalidCharacterErr`:
              If the medium contains characters that are invalid in the
              underlying style language.
            - :exc:`~xml.dom.InvalidModificationErr`:
              If mediaText is "all" and a new medium is tried to be added.
              Exception is "handheld" which is set in any case (Opera does handle
              "all, handheld" special, this special case might be removed in the
              future).
            - :exc:`~xml.dom.NoModificationAllowedErr`:
              Raised if this list is readonly.
        """
        newMedium = self.__prepareset(newMedium)

        if newMedium:
            mts = [self._normalize(mq.mediaType) for mq in self]
            newmt = self._normalize(newMedium.mediaType)

            if newmt in mts:
                self.deleteMedium(newmt)
                self.seq.append(newMedium)
            elif u'all' == newmt:
                # remove all except handheld (Opera)
                h = None
                for mq in self:
                    if mq.mediaType == u'handheld':
                        h = mq
                del self[:]
                self.seq.append(newMedium)
                if h:
                    self.append(h)
            elif u'all' in mts:
                if u'handheld' == newmt:
                    self.seq.append(newMedium)
                    self._log.warn(u'MediaList: Already specified "all" but still setting new medium: %r' %
                                   newMedium, error=xml.dom.InvalidModificationErr, neverraise=True)
                else:
                    self._log.warn(u'MediaList: Ignoring new medium %r as already specified "all" (set ``mediaText`` instead).' %
                                   newMedium, error=xml.dom.InvalidModificationErr)
            else:
                self.seq.append(newMedium)

            return True

        else:
            return False

    def append(self, newMedium):
        "Same as :meth:`appendMedium`."
        self.appendMedium(newMedium)

    def deleteMedium(self, oldMedium):
        """Delete a medium from the list.

        :param oldMedium:
            delete this medium from the list.
        :exceptions:
            - :exc:`~xml.dom.NotFoundErr`:
              Raised if `oldMedium` is not in the list.
            - :exc:`~xml.dom.NoModificationAllowedErr`:
              Raised if this list is readonly.
        """
        self._checkReadonly()
        oldMedium = self._normalize(oldMedium)

        for i, mq in enumerate(self):
            if self._normalize(mq.mediaType) == oldMedium:
                del self[i]
                break
        else:
            self._log.error(u'"%s" not in this MediaList' % oldMedium,
                            error=xml.dom.NotFoundErr)

    def item(self, index):
        """Return the mediaType of the `index`'th element in the list.
        If `index` is greater than or equal to the number of media in the
        list, returns ``None``.
        """
        try:
            return self[index].mediaType
        except IndexError:
            return None

    wellformed = property(lambda self: self._wellformed)
