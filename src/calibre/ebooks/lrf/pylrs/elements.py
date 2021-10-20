""" elements.py -- replacements and helpers for ElementTree """

from polyglot.builtins import string_or_bytes


class ElementWriter:

    def __init__(self, e, header=False, sourceEncoding="ascii",
                 spaceBeforeClose=True, outputEncodingName="UTF-16"):
        self.header = header
        self.e = e
        self.sourceEncoding=sourceEncoding
        self.spaceBeforeClose = spaceBeforeClose
        self.outputEncodingName = outputEncodingName

    def _encodeCdata(self, rawText):
        if isinstance(rawText, bytes):
            rawText = rawText.decode(self.sourceEncoding)

        text = rawText.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        return text

    def _writeAttribute(self, f, name, value):
        f.write(' %s="' % str(name))
        if not isinstance(value, string_or_bytes):
            value = str(value)
        value = self._encodeCdata(value)
        value = value.replace('"', '&quot;')
        f.write(value)
        f.write('"')

    def _writeText(self, f, rawText):
        text = self._encodeCdata(rawText)
        f.write(text)

    def _write(self, f, e):
        f.write('<' + str(e.tag))

        attributes = e.items()
        attributes.sort()
        for name, value in attributes:
            self._writeAttribute(f, name, value)

        if e.text is not None or len(e) > 0:
            f.write('>')

            if e.text:
                self._writeText(f, e.text)

            for e2 in e:
                self._write(f, e2)

            f.write('</%s>' % e.tag)
        else:
            if self.spaceBeforeClose:
                f.write(' ')
            f.write('/>')

        if e.tail is not None:
            self._writeText(f, e.tail)

    def toString(self):
        class x:
            pass
        buffer = []
        x.write = buffer.append
        self.write(x)
        return ''.join(buffer)

    def write(self, f):
        if self.header:
            f.write('<?xml version="1.0" encoding="%s"?>\n' % self.outputEncodingName)

        self._write(f, self.e)
