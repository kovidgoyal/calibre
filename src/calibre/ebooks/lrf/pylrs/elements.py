""" elements.py -- replacements and helpers for ElementTree """


class ElementWriter(object):

    def __init__(self, e, header=False, sourceEncoding="ascii",
                 spaceBeforeClose=True, outputEncodingName="UTF-16"):
        self.header = header
        self.e = e
        self.sourceEncoding=sourceEncoding
        self.spaceBeforeClose = spaceBeforeClose
        self.outputEncodingName = outputEncodingName

    def _encodeCdata(self, rawText):
        if type(rawText) is str:
            rawText = rawText.decode(self.sourceEncoding)

        text = rawText.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        return text

    def _writeAttribute(self, f, name, value):
        f.write(u' %s="' % unicode(name))
        if not isinstance(value, basestring):
            value = unicode(value)
        value = self._encodeCdata(value)
        value = value.replace('"', '&quot;')
        f.write(value)
        f.write(u'"')

    def _writeText(self, f, rawText):
        text = self._encodeCdata(rawText)
        f.write(text)

    def _write(self, f, e):
        f.write(u'<' + unicode(e.tag))

        attributes = e.items()
        attributes.sort()
        for name, value in attributes:
            self._writeAttribute(f, name, value)

        if e.text is not None or len(e) > 0:
            f.write(u'>')

            if e.text:
                self._writeText(f, e.text)

            for e2 in e:
                self._write(f, e2)

            f.write(u'</%s>' % e.tag)
        else:
            if self.spaceBeforeClose:
                f.write(' ')
            f.write(u'/>')

        if e.tail is not None:
            self._writeText(f, e.tail)

    def toString(self):
        class x:
            pass
        buffer = []
        x.write = buffer.append
        self.write(x)
        return u''.join(buffer)

    def write(self, f):
        if self.header:
            f.write(u'<?xml version="1.0" encoding="%s"?>\n' % self.outputEncodingName)

        self._write(f, self.e)



