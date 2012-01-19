import codecs
import re
import types
import sys

from constants import EOF, spaceCharacters, asciiLetters, asciiUppercase
from constants import encodings, ReparseException

#Non-unicode versions of constants for use in the pre-parser
spaceCharactersBytes = frozenset([str(item) for item in spaceCharacters])
asciiLettersBytes = frozenset([str(item) for item in asciiLetters])
asciiUppercaseBytes = frozenset([str(item) for item in asciiUppercase])
spacesAngleBrackets = spaceCharactersBytes | frozenset([">", "<"])

invalid_unicode_re = re.compile(u"[\u0001-\u0008\u000B\u000E-\u001F\u007F-\u009F\uD800-\uDFFF\uFDD0-\uFDEF\uFFFE\uFFFF\U0001FFFE\U0001FFFF\U0002FFFE\U0002FFFF\U0003FFFE\U0003FFFF\U0004FFFE\U0004FFFF\U0005FFFE\U0005FFFF\U0006FFFE\U0006FFFF\U0007FFFE\U0007FFFF\U0008FFFE\U0008FFFF\U0009FFFE\U0009FFFF\U000AFFFE\U000AFFFF\U000BFFFE\U000BFFFF\U000CFFFE\U000CFFFF\U000DFFFE\U000DFFFF\U000EFFFE\U000EFFFF\U000FFFFE\U000FFFFF\U0010FFFE\U0010FFFF]")

non_bmp_invalid_codepoints = set([0x1FFFE, 0x1FFFF, 0x2FFFE, 0x2FFFF, 0x3FFFE,
                                  0x3FFFF, 0x4FFFE, 0x4FFFF, 0x5FFFE, 0x5FFFF,
                                  0x6FFFE, 0x6FFFF, 0x7FFFE, 0x7FFFF, 0x8FFFE,
                                  0x8FFFF, 0x9FFFE, 0x9FFFF, 0xAFFFE, 0xAFFFF,
                                  0xBFFFE, 0xBFFFF, 0xCFFFE, 0xCFFFF, 0xDFFFE,
                                  0xDFFFF, 0xEFFFE, 0xEFFFF, 0xFFFFE, 0xFFFFF,
                                  0x10FFFE, 0x10FFFF])

ascii_punctuation_re = re.compile(ur"[\u0009-\u000D\u0020-\u002F\u003A-\u0040\u005B-\u0060\u007B-\u007E]")

# Cache for charsUntil()
charsUntilRegEx = {}
        
class BufferedStream:
    """Buffering for streams that do not have buffering of their own

    The buffer is implemented as a list of chunks on the assumption that 
    joining many strings will be slow since it is O(n**2)
    """
    
    def __init__(self, stream):
        self.stream = stream
        self.buffer = []
        self.position = [-1,0] #chunk number, offset

    def tell(self):
        pos = 0
        for chunk in self.buffer[:self.position[0]]:
            pos += len(chunk)
        pos += self.position[1]
        return pos

    def seek(self, pos):
        assert pos < self._bufferedBytes()
        offset = pos
        i = 0
        while len(self.buffer[i]) < offset:
            offset -= pos
            i += 1
        self.position = [i, offset]

    def read(self, bytes):
        if not self.buffer:
            return self._readStream(bytes)
        elif (self.position[0] == len(self.buffer) and
              self.position[1] == len(self.buffer[-1])):
            return self._readStream(bytes)
        else:
            return self._readFromBuffer(bytes)
    
    def _bufferedBytes(self):
        return sum([len(item) for item in self.buffer])

    def _readStream(self, bytes):
        data = self.stream.read(bytes)
        self.buffer.append(data)
        self.position[0] += 1
        self.position[1] = len(data)
        return data

    def _readFromBuffer(self, bytes):
        remainingBytes = bytes
        rv = []
        bufferIndex = self.position[0]
        bufferOffset = self.position[1]
        while bufferIndex < len(self.buffer) and remainingBytes != 0:
            assert remainingBytes > 0
            bufferedData = self.buffer[bufferIndex]
            
            if remainingBytes <= len(bufferedData) - bufferOffset:
                bytesToRead = remainingBytes
                self.position = [bufferIndex, bufferOffset + bytesToRead]
            else:
                bytesToRead = len(bufferedData) - bufferOffset
                self.position = [bufferIndex, len(bufferedData)]
                bufferIndex += 1
            data = rv.append(bufferedData[bufferOffset: 
                                          bufferOffset + bytesToRead])
            remainingBytes -= bytesToRead

            bufferOffset = 0

        if remainingBytes:
            rv.append(self._readStream(remainingBytes))
        
        return "".join(rv)
        


class HTMLInputStream:
    """Provides a unicode stream of characters to the HTMLTokenizer.

    This class takes care of character encoding and removing or replacing
    incorrect byte-sequences and also provides column and line tracking.

    """

    _defaultChunkSize = 10240

    def __init__(self, source, encoding=None, parseMeta=True, chardet=True):
        """Initialises the HTMLInputStream.

        HTMLInputStream(source, [encoding]) -> Normalized stream from source
        for use by html5lib.

        source can be either a file-object, local filename or a string.

        The optional encoding parameter must be a string that indicates
        the encoding.  If specified, that encoding will be used,
        regardless of any BOM or later declaration (such as in a meta
        element)
        
        parseMeta - Look for a <meta> element containing encoding information

        """

        #Craziness
        if len(u"\U0010FFFF") == 1:
            self.reportCharacterErrors = self.characterErrorsUCS4
        else:
            self.reportCharacterErrors = self.characterErrorsUCS2

        # List of where new lines occur
        self.newLines = [0]

        self.charEncoding = (codecName(encoding), "certain")

        # Raw Stream - for unicode objects this will encode to utf-8 and set
        #              self.charEncoding as appropriate
        self.rawStream = self.openStream(source)

        # Encoding Information
        #Number of bytes to use when looking for a meta element with
        #encoding information
        self.numBytesMeta = 512
        #Number of bytes to use when using detecting encoding using chardet
        self.numBytesChardet = 100
        #Encoding to use if no other information can be found
        self.defaultEncoding = "windows-1252"
        
        #Detect encoding iff no explicit "transport level" encoding is supplied
        if (self.charEncoding[0] is None):
            self.charEncoding = self.detectEncoding(parseMeta, chardet)


        self.reset()

    def reset(self):
        self.dataStream = codecs.getreader(self.charEncoding[0])(self.rawStream,
                                                                 'replace')

        self.chunk = u""
        self.chunkSize = 0
        self.chunkOffset = 0
        self.errors = []

        # number of (complete) lines in previous chunks
        self.prevNumLines = 0
        # number of columns in the last line of the previous chunk
        self.prevNumCols = 0
        
        #Flag to indicate we may have a CR LF broken across a data chunk
        self._lastChunkEndsWithCR = False

    def openStream(self, source):
        """Produces a file object from source.

        source can be either a file object, local filename or a string.

        """
        # Already a file object
        if hasattr(source, 'read'):
            stream = source
        else:
            # Otherwise treat source as a string and convert to a file object
            if isinstance(source, unicode):
                source = source.encode('utf-8')
                self.charEncoding = ("utf-8", "certain")
            import cStringIO
            stream = cStringIO.StringIO(str(source))

        if (not(hasattr(stream, "tell") and hasattr(stream, "seek")) or
            stream is sys.stdin):
            stream = BufferedStream(stream)

        return stream

    def detectEncoding(self, parseMeta=True, chardet=True):
        #First look for a BOM
        #This will also read past the BOM if present
        encoding = self.detectBOM()
        confidence = "certain"
        #If there is no BOM need to look for meta elements with encoding 
        #information
        if encoding is None and parseMeta:
            encoding = self.detectEncodingMeta()
            confidence = "tentative"
        #Guess with chardet, if avaliable
        if encoding is None and chardet:
            confidence = "tentative"
            try:
                from chardet.universaldetector import UniversalDetector
                buffers = []
                detector = UniversalDetector()
                while not detector.done:
                    buffer = self.rawStream.read(self.numBytesChardet)
                    if not buffer:
                        break
                    buffers.append(buffer)
                    detector.feed(buffer)
                detector.close()
                encoding = detector.result['encoding']
                self.rawStream.seek(0)
            except ImportError:
                pass
        # If all else fails use the default encoding
        if encoding is None:
            confidence="tentative"
            encoding = self.defaultEncoding
        
        #Substitute for equivalent encodings:
        encodingSub = {"iso-8859-1":"windows-1252"}

        if encoding.lower() in encodingSub:
            encoding = encodingSub[encoding.lower()]

        return encoding, confidence

    def changeEncoding(self, newEncoding):
        newEncoding = codecName(newEncoding)
        if newEncoding in ("utf-16", "utf-16-be", "utf-16-le"):
            newEncoding = "utf-8"
        if newEncoding is None:
            return
        elif newEncoding == self.charEncoding[0]:
            self.charEncoding = (self.charEncoding[0], "certain")
        else:
            self.rawStream.seek(0)
            self.reset()
            self.charEncoding = (newEncoding, "certain")
            raise ReparseException, "Encoding changed from %s to %s"%(self.charEncoding[0], newEncoding)
            
    def detectBOM(self):
        """Attempts to detect at BOM at the start of the stream. If
        an encoding can be determined from the BOM return the name of the
        encoding otherwise return None"""
        bomDict = {
            codecs.BOM_UTF8: 'utf-8',
            codecs.BOM_UTF16_LE: 'utf-16-le', codecs.BOM_UTF16_BE: 'utf-16-be',
            codecs.BOM_UTF32_LE: 'utf-32-le', codecs.BOM_UTF32_BE: 'utf-32-be'
        }

        # Go to beginning of file and read in 4 bytes
        string = self.rawStream.read(4)

        # Try detecting the BOM using bytes from the string
        encoding = bomDict.get(string[:3])         # UTF-8
        seek = 3
        if not encoding:
            # Need to detect UTF-32 before UTF-16
            encoding = bomDict.get(string)         # UTF-32
            seek = 4
            if not encoding:
                encoding = bomDict.get(string[:2]) # UTF-16
                seek = 2

        # Set the read position past the BOM if one was found, otherwise
        # set it to the start of the stream
        self.rawStream.seek(encoding and seek or 0)

        return encoding

    def detectEncodingMeta(self):
        """Report the encoding declared by the meta element
        """
        buffer = self.rawStream.read(self.numBytesMeta)
        parser = EncodingParser(buffer)
        self.rawStream.seek(0)
        encoding = parser.getEncoding()
        
        if encoding in ("utf-16", "utf-16-be", "utf-16-le"):
            encoding = "utf-8"

        return encoding

    def _position(self, offset):
        chunk = self.chunk
        nLines = chunk.count(u'\n', 0, offset)
        positionLine = self.prevNumLines + nLines
        lastLinePos = chunk.rfind(u'\n', 0, offset)
        if lastLinePos == -1:
            positionColumn = self.prevNumCols + offset
        else:
            positionColumn = offset - (lastLinePos + 1)
        return (positionLine, positionColumn)

    def position(self):
        """Returns (line, col) of the current position in the stream."""
        line, col = self._position(self.chunkOffset)
        return (line+1, col)

    def char(self):
        """ Read one character from the stream or queue if available. Return
            EOF when EOF is reached.
        """
        # Read a new chunk from the input stream if necessary
        if self.chunkOffset >= self.chunkSize:
            if not self.readChunk():
                return EOF

        chunkOffset = self.chunkOffset
        char = self.chunk[chunkOffset]
        self.chunkOffset = chunkOffset + 1

        return char

    def readChunk(self, chunkSize=None):
        if chunkSize is None:
            chunkSize = self._defaultChunkSize

        self.prevNumLines, self.prevNumCols = self._position(self.chunkSize)

        self.chunk = u""
        self.chunkSize = 0
        self.chunkOffset = 0

        data = self.dataStream.read(chunkSize)

        if not data:
            return False
        
        self.reportCharacterErrors(data)

        data = data.replace(u"\u0000", u"\ufffd")
        #Check for CR LF broken across chunks
        if (self._lastChunkEndsWithCR and data[0] == u"\n"):
            data = data[1:]
            # Stop if the chunk is now empty
            if not data:
                return False
        self._lastChunkEndsWithCR = data[-1] == u"\r"
        data = data.replace(u"\r\n", u"\n")
        data = data.replace(u"\r", u"\n")

        self.chunk = data
        self.chunkSize = len(data)

        return True

    def characterErrorsUCS4(self, data):
        for i in xrange(data.count(u"\u0000")):
            self.errors.append("null-character")
        for i in xrange(len(invalid_unicode_re.findall(data))):
            self.errors.append("invalid-codepoint")

    def characterErrorsUCS2(self, data):
        #Someone picked the wrong compile option
        #You lose
        for i in xrange(data.count(u"\u0000")):
            self.errors.append("null-character")
        skip = False
        import sys
        for match in invalid_unicode_re.finditer(data):
            if skip:
                continue
            codepoint = ord(match.group())
            pos = match.start()
            #Pretty sure there should be endianness issues here
            if (codepoint >= 0xD800 and codepoint <= 0xDBFF and
                pos < len(data) - 1 and
                ord(data[pos + 1]) >= 0xDC00 and
                ord(data[pos + 1]) <= 0xDFFF):
                #We have a surrogate pair!
                #From a perl manpage
                char_val = (0x10000 + (codepoint - 0xD800) * 0x400 + 
                            (ord(data[pos + 1]) - 0xDC00))
                if char_val in non_bmp_invalid_codepoints:
                    self.errors.append("invalid-codepoint")
                skip = True
            elif (codepoint >= 0xD800 and codepoint <= 0xDFFF and
                  pos == len(data) - 1):
                self.errors.append("invalid-codepoint")
            else:
                skip = False
                self.errors.append("invalid-codepoint")
        #This is still wrong if it is possible for a surrogate pair to break a
        #chunk boundary

    def charsUntil(self, characters, opposite = False):
        """ Returns a string of characters from the stream up to but not
        including any character in 'characters' or EOF. 'characters' must be
        a container that supports the 'in' method and iteration over its
        characters.
        """

        # Use a cache of regexps to find the required characters
        try:
            chars = charsUntilRegEx[(characters, opposite)]
        except KeyError:
            if __debug__:
                for c in characters: 
                    assert(ord(c) < 128)
            regex = u"".join([u"\\x%02x" % ord(c) for c in characters])
            if not opposite:
                regex = u"^%s" % regex
            chars = charsUntilRegEx[(characters, opposite)] = re.compile(u"[%s]+" % regex)

        rv = []

        while True:
            # Find the longest matching prefix
            m = chars.match(self.chunk, self.chunkOffset)
            if m is None:
                # If nothing matched, and it wasn't because we ran out of chunk,
                # then stop
                if self.chunkOffset != self.chunkSize:
                    break
            else:
                end = m.end()
                # If not the whole chunk matched, return everything
                # up to the part that didn't match
                if end != self.chunkSize:
                    rv.append(self.chunk[self.chunkOffset:end])
                    self.chunkOffset = end
                    break
            # If the whole remainder of the chunk matched,
            # use it all and read the next chunk
            rv.append(self.chunk[self.chunkOffset:])
            if not self.readChunk():
                # Reached EOF
                break

        r = u"".join(rv)
        return r

    def charsUntilEOF(self):
        """ Returns a string of characters from the stream up to EOF."""

        rv = []

        while True:
            rv.append(self.chunk[self.chunkOffset:])
            if not self.readChunk():
                # Reached EOF
                break

        r = u"".join(rv)
        return r

    def unget(self, char):
        # Only one character is allowed to be ungotten at once - it must
        # be consumed again before any further call to unget

        if char is not None:
            if self.chunkOffset == 0:
                # unget is called quite rarely, so it's a good idea to do
                # more work here if it saves a bit of work in the frequently
                # called char and charsUntil.
                # So, just prepend the ungotten character onto the current
                # chunk:
                self.chunk = char + self.chunk
                self.chunkSize += 1
            else:
                self.chunkOffset -= 1
                assert self.chunk[self.chunkOffset] == char

class EncodingBytes(str):
    """String-like object with an associated position and various extra methods
    If the position is ever greater than the string length then an exception is
    raised"""
    def __new__(self, value):
        return str.__new__(self, value.lower())

    def __init__(self, value):
        self._position=-1
    
    def __iter__(self):
        return self
    
    def next(self):
        p = self._position = self._position + 1
        if p >= len(self):
            raise StopIteration
        elif p < 0:
            raise TypeError
        return self[p]

    def previous(self):
        p = self._position
        if p >= len(self):
            raise StopIteration
        elif p < 0:
            raise TypeError
        self._position = p = p - 1
        return self[p]
    
    def setPosition(self, position):
        if self._position >= len(self):
            raise StopIteration
        self._position = position
    
    def getPosition(self):
        if self._position >= len(self):
            raise StopIteration
        if self._position >= 0:
            return self._position
        else:
            return None
    
    position = property(getPosition, setPosition)

    def getCurrentByte(self):
        return self[self.position]
    
    currentByte = property(getCurrentByte)

    def skip(self, chars=spaceCharactersBytes):
        """Skip past a list of characters"""
        p = self.position               # use property for the error-checking
        while p < len(self):
            c = self[p]
            if c not in chars:
                self._position = p
                return c
            p += 1
        self._position = p
        return None

    def skipUntil(self, chars):
        p = self.position
        while p < len(self):
            c = self[p]
            if c in chars:
                self._position = p
                return c
            p += 1
        self._position = p
        return None

    def matchBytes(self, bytes):
        """Look for a sequence of bytes at the start of a string. If the bytes 
        are found return True and advance the position to the byte after the 
        match. Otherwise return False and leave the position alone"""
        p = self.position
        data = self[p:p+len(bytes)]
        rv = data.startswith(bytes)
        if rv:
            self.position += len(bytes)
        return rv
    
    def jumpTo(self, bytes):
        """Look for the next sequence of bytes matching a given sequence. If
        a match is found advance the position to the last byte of the match"""
        newPosition = self[self.position:].find(bytes)
        if newPosition > -1:
            # XXX: This is ugly, but I can't see a nicer way to fix this.
            if self._position == -1:
                self._position = 0
            self._position += (newPosition + len(bytes)-1)
            return True
        else:
            raise StopIteration

class EncodingParser(object):
    """Mini parser for detecting character encoding from meta elements"""

    def __init__(self, data):
        """string - the data to work on for encoding detection"""
        self.data = EncodingBytes(data)
        self.encoding = None

    def getEncoding(self):
        methodDispatch = (
            ("<!--",self.handleComment),
            ("<meta",self.handleMeta),
            ("</",self.handlePossibleEndTag),
            ("<!",self.handleOther),
            ("<?",self.handleOther),
            ("<",self.handlePossibleStartTag))
        for byte in self.data:
            keepParsing = True
            for key, method in methodDispatch:
                if self.data.matchBytes(key):
                    try:
                        keepParsing = method()    
                        break
                    except StopIteration:
                        keepParsing=False
                        break
            if not keepParsing:
                break
        
        return self.encoding

    def handleComment(self):
        """Skip over comments"""
        return self.data.jumpTo("-->")

    def handleMeta(self):
        if self.data.currentByte not in spaceCharactersBytes:
            #if we have <meta not followed by a space so just keep going
            return True
        #We have a valid meta element we want to search for attributes
        while True:
            #Try to find the next attribute after the current position
            attr = self.getAttribute()
            if attr is None:
                return True
            else:
                if attr[0] == "charset":
                    tentativeEncoding = attr[1]
                    codec = codecName(tentativeEncoding)
                    if codec is not None:
                        self.encoding = codec
                        return False
                elif attr[0] == "content":
                    contentParser = ContentAttrParser(EncodingBytes(attr[1]))
                    tentativeEncoding = contentParser.parse()
                    codec = codecName(tentativeEncoding)
                    if codec is not None:
                        self.encoding = codec
                        return False

    def handlePossibleStartTag(self):
        return self.handlePossibleTag(False)

    def handlePossibleEndTag(self):
        self.data.next()
        return self.handlePossibleTag(True)

    def handlePossibleTag(self, endTag):
        data = self.data
        if data.currentByte not in asciiLettersBytes:
            #If the next byte is not an ascii letter either ignore this
            #fragment (possible start tag case) or treat it according to 
            #handleOther
            if endTag:
                data.previous()
                self.handleOther()
            return True
        
        c = data.skipUntil(spacesAngleBrackets)
        if c == "<":
            #return to the first step in the overall "two step" algorithm
            #reprocessing the < byte
            data.previous()
        else:
            #Read all attributes
            attr = self.getAttribute()
            while attr is not None:
                attr = self.getAttribute()
        return True

    def handleOther(self):
        return self.data.jumpTo(">")

    def getAttribute(self):
        """Return a name,value pair for the next attribute in the stream, 
        if one is found, or None"""
        data = self.data
        # Step 1 (skip chars)
        c = data.skip(spaceCharactersBytes | frozenset("/"))
        # Step 2
        if c in (">", None):
            return None
        # Step 3
        attrName = []
        attrValue = []
        #Step 4 attribute name
        while True:
            if c == "=" and attrName:   
                break
            elif c in spaceCharactersBytes:
                #Step 6!
                c = data.skip()
                c = data.next()
                break
            elif c in ("/", ">"):
                return "".join(attrName), ""
            elif c in asciiUppercaseBytes:
                attrName.append(c.lower())
            elif c == None:
                return None
            else:
                attrName.append(c)
            #Step 5
            c = data.next()
        #Step 7
        if c != "=":
            data.previous()
            return "".join(attrName), ""
        #Step 8
        data.next()
        #Step 9
        c = data.skip()
        #Step 10
        if c in ("'", '"'):
            #10.1
            quoteChar = c
            while True:
                #10.2
                c = data.next()
                #10.3
                if c == quoteChar:
                    data.next()
                    return "".join(attrName), "".join(attrValue)
                #10.4
                elif c in asciiUppercaseBytes:
                    attrValue.append(c.lower())
                #10.5
                else:
                    attrValue.append(c)
        elif c == ">":
            return "".join(attrName), ""
        elif c in asciiUppercaseBytes:
            attrValue.append(c.lower())
        elif c is None:
            return None
        else:
            attrValue.append(c)
        # Step 11
        while True:
            c = data.next()
            if c in spacesAngleBrackets:
                return "".join(attrName), "".join(attrValue)
            elif c in asciiUppercaseBytes:
                attrValue.append(c.lower())
            elif c is None:
                return None
            else:
                attrValue.append(c)


class ContentAttrParser(object):
    def __init__(self, data):
        self.data = data
    def parse(self):
        try:
            #Check if the attr name is charset 
            #otherwise return
            self.data.jumpTo("charset")
            self.data.position += 1
            self.data.skip()
            if not self.data.currentByte == "=":
                #If there is no = sign keep looking for attrs
                return None
            self.data.position += 1
            self.data.skip()
            #Look for an encoding between matching quote marks
            if self.data.currentByte in ('"', "'"):
                quoteMark = self.data.currentByte
                self.data.position += 1
                oldPosition = self.data.position
                if self.data.jumpTo(quoteMark):
                    return self.data[oldPosition:self.data.position]
                else:
                    return None
            else:
                #Unquoted value
                oldPosition = self.data.position
                try:
                    self.data.skipUntil(spaceCharactersBytes)
                    return self.data[oldPosition:self.data.position]
                except StopIteration:
                    #Return the whole remaining value
                    return self.data[oldPosition:]
        except StopIteration:
            return None


def codecName(encoding):
    """Return the python codec name corresponding to an encoding or None if the
    string doesn't correspond to a valid encoding."""
    if (encoding is not None and type(encoding) in types.StringTypes):
        canonicalName = ascii_punctuation_re.sub("", encoding).lower()
        return encodings.get(canonicalName, None)
    else:
        return None
