#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>


from io import StringIO, BytesIO


class PolyglotStringIO(StringIO):

    def __init__(self, initial_data=None, encoding='utf-8', errors='strict'):
        StringIO.__init__(self)
        self._encoding_for_bytes = encoding
        self._errors = errors
        if initial_data is not None:
            self.write(initial_data)

    def write(self, x):
        if isinstance(x, bytes):
            x = x.decode(self._encoding_for_bytes, errors=self._errors)
        StringIO.write(self, x)


class PolyglotBytesIO(BytesIO):

    def __init__(self, initial_data=None, encoding='utf-8', errors='strict'):
        BytesIO.__init__(self)
        self._encoding_for_bytes = encoding
        self._errors = errors
        if initial_data is not None:
            self.write(initial_data)

    def write(self, x):
        if not isinstance(x, bytes):
            x = x.encode(self._encoding_for_bytes, errors=self._errors)
        BytesIO.write(self, x)
