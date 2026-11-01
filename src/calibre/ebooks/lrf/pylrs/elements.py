"""elements.py -- replacements and helpers for ElementTree"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from xml.etree.ElementTree import Element

    from _typeshed import SupportsWrite


class ElementWriter:
    def __init__(
        self,
        e: Element,
        header: bool = False,
        sourceEncoding: str = 'ascii',
        spaceBeforeClose: bool = True,
        outputEncodingName: str = 'UTF-16',
    ) -> None:
        self.header = header
        self.e = e
        self.sourceEncoding = sourceEncoding
        self.spaceBeforeClose = spaceBeforeClose
        self.outputEncodingName = outputEncodingName

    def _encodeCdata(self, rawText: str | bytes) -> str:
        if isinstance(rawText, bytes):
            rawText = rawText.decode(self.sourceEncoding)

        text = rawText.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        return text

    def _writeAttribute(self, f: SupportsWrite[str], name: str, value: object) -> None:
        f.write(f' {name!s}="')
        if not isinstance(value, (str, bytes)):
            value = str(value)
        value = self._encodeCdata(value)
        value = value.replace('"', '&quot;')
        f.write(value)
        f.write('"')

    def _writeText(self, f: SupportsWrite[str], rawText: str | bytes) -> None:
        text = self._encodeCdata(rawText)
        f.write(text)

    def _write(self, f: SupportsWrite[str], e: Element) -> None:
        f.write('<' + str(e.tag))

        attributes = sorted(e.items())
        for name, value in attributes:
            self._writeAttribute(f, name, value)

        if e.text is not None or len(e) > 0:
            f.write('>')

            if e.text:
                self._writeText(f, e.text)

            for e2 in e:
                self._write(f, e2)

            f.write(f'</{e.tag}>')
        else:
            if self.spaceBeforeClose:
                f.write(' ')
            f.write('/>')

        if e.tail is not None:
            self._writeText(f, e.tail)

    def toString(self) -> str:
        class x:
            write: Callable[[str], None]

        buffer: list[str] = []
        x.write = buffer.append
        self.write(x)
        return ''.join(buffer)

    def write(self, f: SupportsWrite[str]) -> None:
        if self.header:
            f.write(f'<?xml version="1.0" encoding="{self.outputEncodingName}"?>\n')

        self._write(f, self.e)
