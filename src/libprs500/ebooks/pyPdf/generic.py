# vim: sw=4:expandtab:foldmethod=marker
#
# Copyright (c) 2006, Mathieu Fenniak
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
# * Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
# * The name of the author may not be used to endorse or promote products
# derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.


"""
Implementation of generic PDF objects (dictionary, number, string, and so on)
"""
__author__ = "Mathieu Fenniak"
__author_email__ = "mfenniak@pobox.com"

import re
from utils import readNonWhitespace, RC4_encrypt
import filters

def readObject(stream, pdf):
    tok = stream.read(1)
    stream.seek(-1, 1) # reset to start
    if tok == 't' or tok == 'f':
        # boolean object
        return BooleanObject.readFromStream(stream)
    elif tok == '(':
        # string object
        return StringObject.readFromStream(stream)
    elif tok == '/':
        # name object
        return NameObject.readFromStream(stream)
    elif tok == '[':
        # array object
        return ArrayObject.readFromStream(stream, pdf)
    elif tok == 'n':
        # null object
        return NullObject.readFromStream(stream)
    elif tok == '<':
        # hexadecimal string OR dictionary
        peek = stream.read(2)
        stream.seek(-2, 1) # reset to start
        if peek == '<<':
            return DictionaryObject.readFromStream(stream, pdf)
        else:
            return StringObject.readHexStringFromStream(stream)
    elif tok == '%':
        # comment
        while tok not in ('\r', '\n'):
            tok = stream.read(1)
        tok = readNonWhitespace(stream)
        stream.seek(-1, 1)
        return readObject(stream, pdf)
    else:
        # number object OR indirect reference
        if tok == '+' or tok == '-':
            # number
            return NumberObject.readFromStream(stream)
        peek = stream.read(20)
        stream.seek(-len(peek), 1) # reset to start
        if re.match(r"(\d+)\s(\d+)\sR[^a-zA-Z]", peek) != None:
            return IndirectObject.readFromStream(stream, pdf)
        else:
            return NumberObject.readFromStream(stream)

class PdfObject(object):
    def getObject(self):
        """Resolves indirect references."""
        return self


class NullObject(PdfObject):
    def writeToStream(self, stream, encryption_key):
        stream.write("null")

    def readFromStream(stream):
        assert stream.read(4) == "null"
        return NullObject()
    readFromStream = staticmethod(readFromStream)


class BooleanObject(PdfObject):
    def __init__(self, value):
        self.value = value

    def writeToStream(self, stream, encryption_key):
        if self.value:
            stream.write("true")
        else:
            stream.write("false")

    def readFromStream(stream):
        word = stream.read(4)
        if word == "true":
            return BooleanObject(True)
        elif word == "fals":
            stream.read(1)
            return BooleanObject(False)
        assert False
    readFromStream = staticmethod(readFromStream)


class ArrayObject(list, PdfObject):
    def writeToStream(self, stream, encryption_key):
        stream.write("[")
        for data in self:
            stream.write(" ")
            data.writeToStream(stream, encryption_key)
        stream.write(" ]")

    def readFromStream(stream, pdf):
        arr = ArrayObject()
        assert stream.read(1) == "["
        while True:
            # skip leading whitespace
            tok = stream.read(1)
            while tok.isspace():
                tok = stream.read(1)
            stream.seek(-1, 1)
            # check for array ending
            peekahead = stream.read(1)
            if peekahead == "]":
                break
            stream.seek(-1, 1)
            # read and append obj
            arr.append(readObject(stream, pdf))
        return arr
    readFromStream = staticmethod(readFromStream)


class IndirectObject(PdfObject):
    def __init__(self, idnum, generation, pdf):
        self.idnum = idnum
        self.generation = generation
        self.pdf = pdf

    def getObject(self):
        return self.pdf.getObject(self).getObject()

    def __repr__(self):
        return "IndirectObject(%r, %r)" % (self.idnum, self.generation)

    def __eq__(self, other):
        return (
            other != None and
            isinstance(other, IndirectObject) and
            self.idnum == other.idnum and
            self.generation == other.generation and
            self.pdf is other.pdf
            )

    def __ne__(self, other):
        return not self.__eq__(other)

    def writeToStream(self, stream, encryption_key):
        stream.write("%s %s R" % (self.idnum, self.generation))

    def readFromStream(stream, pdf):
        idnum = ""
        while True:
            tok = stream.read(1)
            if tok.isspace():
                break
            idnum += tok
        generation = ""
        while True:
            tok = stream.read(1)
            if tok.isspace():
                break
            generation += tok
        r = stream.read(1)
        #if r != "R":
        #    stream.seek(-20, 1)
        #    print idnum, generation
        #    print repr(stream.read(40))
        assert r == "R"
        return IndirectObject(int(idnum), int(generation), pdf)
    readFromStream = staticmethod(readFromStream)


class FloatObject(float, PdfObject):
    def writeToStream(self, stream, encryption_key):
        stream.write(repr(self))


class NumberObject(int, PdfObject):
    def __init__(self, value):
        int.__init__(self, value)

    def writeToStream(self, stream, encryption_key):
        stream.write(repr(self))

    def readFromStream(stream):
        name = ""
        while True:
            tok = stream.read(1)
            if tok != '+' and tok != '-' and tok != '.' and not tok.isdigit():
                stream.seek(-1, 1)
                break
            name += tok
        if name.find(".") != -1:
            return FloatObject(name)
        else:
            return NumberObject(name)
    readFromStream = staticmethod(readFromStream)


class StringObject(str, PdfObject):
    def writeToStream(self, stream, encryption_key):
        string = self
        if encryption_key:
            string = RC4_encrypt(encryption_key, string)
        stream.write("(")
        for c in string:
            if not c.isalnum() and not c.isspace():
                stream.write("\\%03o" % ord(c))
            else:
                stream.write(c)
        stream.write(")")

    def readHexStringFromStream(stream):
        stream.read(1)
        txt = ""
        x = ""
        while True:
            tok = readNonWhitespace(stream)
            if tok == ">":
                break
            x += tok
            if len(x) == 2:
                txt += chr(int(x, base=16))
                x = ""
        if len(x) == 1:
            x += "0"
        if len(x) == 2:
            txt += chr(int(x, base=16))
        return StringObject(txt)
    readHexStringFromStream = staticmethod(readHexStringFromStream)

    def readFromStream(stream):
        tok = stream.read(1)
        parens = 1
        txt = ""
        while True:
            tok = stream.read(1)
            if tok == "(":
                parens += 1
            elif tok == ")":
                parens -= 1
                if parens == 0:
                    break
            elif tok == "\\":
                tok = stream.read(1)
                if tok == "n":
                    tok = "\n"
                elif tok == "r":
                    tok = "\r"
                elif tok == "t":
                    tok = "\t"
                elif tok == "b":
                    tok == "\b"
                elif tok == "f":
                    tok = "\f"
                elif tok == "(":
                    tok = "("
                elif tok == ")":
                    tok = ")"
                elif tok == "\\":
                    tok = "\\"
                elif tok.isdigit():
                    tok += stream.read(2)
                    tok = chr(int(tok, base=8))
            txt += tok
        return StringObject(txt)
    readFromStream = staticmethod(readFromStream)


class NameObject(str, PdfObject):
    delimiterCharacters = "(", ")", "<", ">", "[", "]", "{", "}", "/", "%"

    def __init__(self, data):
        str.__init__(self, data)

    def writeToStream(self, stream, encryption_key):
        stream.write(self)

    def readFromStream(stream):
        name = stream.read(1)
        assert name == "/"
        while True:
            tok = stream.read(1)
            if tok.isspace() or tok in NameObject.delimiterCharacters:
                stream.seek(-1, 1)
                break
            name += tok
        return NameObject(name)
    readFromStream = staticmethod(readFromStream)


class DictionaryObject(dict, PdfObject):
    def __init__(self):
        pass

    def writeToStream(self, stream, encryption_key):
        stream.write("<<\n")
        for key, value in self.items():
            key.writeToStream(stream, encryption_key)
            stream.write(" ")
            value.writeToStream(stream, encryption_key)
            stream.write("\n")
        stream.write(">>")

    def readFromStream(stream, pdf):
        assert stream.read(2) == "<<"
        data = {}
        while True:
            tok = readNonWhitespace(stream)
            if tok == ">":
                stream.read(1)
                break
            stream.seek(-1, 1)
            key = readObject(stream, pdf)
            tok = readNonWhitespace(stream)
            stream.seek(-1, 1)
            value = readObject(stream, pdf)
            if data.has_key(key):
                # multiple definitions of key not permitted
                assert False
            data[key] = value
        pos = stream.tell()
        s = readNonWhitespace(stream)
        if s == 's' and stream.read(5) == 'tream':
            eol = stream.read(1)
            # odd PDF file output has spaces after 'stream' keyword but before EOL.
            # patch provided by Danial Sandler
            while eol == ' ':
                eol = stream.read(1)
            assert eol in ("\n", "\r")
            if eol == "\r":
                # read \n after
                stream.read(1)
            # this is a stream object, not a dictionary
            assert data.has_key("/Length")
            length = data["/Length"]
            if isinstance(length, IndirectObject):
                t = stream.tell()
                length = pdf.getObject(length)
                stream.seek(t, 0)
            data["__streamdata__"] = stream.read(length)
            e = readNonWhitespace(stream)
            ndstream = stream.read(8)
            if (e + ndstream) != "endstream":
                # (sigh) - the odd PDF file has a length that is too long, so
                # we need to read backwards to find the "endstream" ending.
                # ReportLab (unknown version) generates files with this bug,
                # and Python users into PDF files tend to be our audience.
                # we need to do this to correct the streamdata and chop off
                # an extra character.
                pos = stream.tell()
                stream.seek(-10, 1)
                end = stream.read(9)
                if end == "endstream":
                    # we found it by looking back one character further.
                    data["__streamdata__"] = data["__streamdata__"][:-1]
                else:
                    stream.seek(pos, 0)
                    raise "Unable to find 'endstream' marker after stream."
        else:
            stream.seek(pos, 0)
        if data.has_key("__streamdata__"):
            return StreamObject.initializeFromDictionary(data)
        else:
            retval = DictionaryObject()
            retval.update(data)
            return retval
    readFromStream = staticmethod(readFromStream)


class StreamObject(DictionaryObject):
    def __init__(self):
        self._data = None
        self.decodedSelf = None

    def writeToStream(self, stream, encryption_key):
        self[NameObject("/Length")] = NumberObject(len(self._data))
        DictionaryObject.writeToStream(self, stream, encryption_key)
        del self["/Length"]
        stream.write("\nstream\n")
        data = self._data
        if encryption_key:
            data = RC4_encrypt(encryption_key, data)
        stream.write(data)
        stream.write("\nendstream")

    def initializeFromDictionary(data):
        if data.has_key("/Filter"):
            retval = EncodedStreamObject()
        else:
            retval = DecodedStreamObject()
        retval._data = data["__streamdata__"]
        del data["__streamdata__"]
        del data["/Length"]
        retval.update(data)
        return retval
    initializeFromDictionary = staticmethod(initializeFromDictionary)

    def flateEncode(self):
        if self.has_key("/Filter"):
            f = self["/Filter"]
            if isinstance(f, ArrayObject):
                f.insert(0, NameObject("/FlateDecode"))
            else:
                newf = ArrayObject()
                newf.append(NameObject("/FlateDecode"))
                newf.append(f)
                f = newf
        else:
            f = NameObject("/FlateDecode")
        retval = EncodedStreamObject()
        retval[NameObject("/Filter")] = f
        retval._data = filters.FlateDecode.encode(self._data)
        return retval


class DecodedStreamObject(StreamObject):
    def getData(self):
        return self._data

    def setData(self, data):
        self._data = data


class EncodedStreamObject(StreamObject):
    def __init__(self):
        self.decodedSelf = None

    def getData(self):
        if self.decodedSelf:
            # cached version of decoded object
            return self.decodedSelf.getData()
        else:
            # create decoded object
            decoded = StreamObject()
            decoded._data = filters.decodeStreamData(self)
            for key, value in self.items():
                if not key in ("/Length", "/Filter", "/DecodeParms"):
                    decoded[key] = value
            self.decodedSelf = decoded
            return decoded._data

    def setData(self, data):
        raise "Creating EncodedStreamObject is not currently supported"


class RectangleObject(ArrayObject):
    def __init__(self, arr):
        # must have four points
        assert len(arr) == 4
        # automatically convert arr[x] into NumberObject(arr[x]) if necessary
        ArrayObject.__init__(self, [self.ensureIsNumber(x) for x in arr])

    def ensureIsNumber(self, value):
        if not isinstance(value, NumberObject):
            value = NumberObject(value)
        return value

    def __repr__(self):
        return "RectangleObject(%s)" % repr(list(self))

    def getLowerLeft_x(self):
        return self[0]

    def getLowerLeft_y(self):
        return self[1]

    def getUpperRight_x(self):
        return self[2]

    def getUpperRight_y(self):
        return self[3]

    def getUpperLeft_x(self):
        return self.getLowerLeft_x()
    
    def getUpperLeft_y(self):
        return self.getUpperRight_y()

    def getLowerRight_x(self):
        return self.getUpperRight_x()

    def getLowerRight_y(self):
        return self.getLowerLeft_y()

    def getLowerLeft(self):
        return self.getLowerLeft_x(), self.getLowerLeft_y()

    def getLowerRight(self):
        return self.getLowerRight_x(), self.getLowerRight_y()

    def getUpperLeft(self):
        return self.getUpperLeft_x(), self.getUpperLeft_y()

    def getUpperRight(self):
        return self.getUpperRight_x(), self.getUpperRight_y()

    def setLowerLeft(self, value):
        self[0], self[1] = [self.ensureIsNumber(x) for x in value]

    def setLowerRight(self, value):
        self[2], self[1] = [self.ensureIsNumber(x) for x in value]

    def setUpperLeft(self, value):
        self[0], self[3] = [self.ensureIsNumber(x) for x in value]

    def setUpperRight(self, value):
        self[2], self[3] = [self.ensureIsNumber(x) for x in value]

    lowerLeft = property(getLowerLeft, setLowerLeft, None, None)
    lowerRight = property(getLowerRight, setLowerRight, None, None)
    upperLeft = property(getUpperLeft, setUpperLeft, None, None)
    upperRight = property(getUpperRight, setUpperRight, None, None)

