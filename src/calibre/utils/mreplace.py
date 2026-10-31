# License: GPLv3 Copyright: 2010, sengian <sengian1 @ gmail.com>

# multiple replace from dictionary : http://code.activestate.com/recipes/81330/

import re
from collections import UserDict
from collections.abc import Mapping


class MReplace(UserDict):
    def __init__(self, data: Mapping[str, str] | Mapping[bytes, bytes] | None = None, case_sensitive: bool = True) -> None:
        UserDict.__init__(self, data)
        self.re = None
        self.regex = None
        self.case_sensitive = case_sensitive
        self.compile_regex()

    def compile_regex(self) -> None:
        if len(self.data) > 0:
            keys = sorted(self.data, key=len, reverse=True)
            if isinstance(keys[0], bytes):
                tmp = b'(%s)' % b'|'.join(map(re.escape, keys))
            else:
                tmp = '({})'.format('|'.join(map(re.escape, keys)))
            if self.re != tmp:
                self.re = tmp
                if self.case_sensitive:
                    self.regex = re.compile(self.re)
                else:
                    self.regex = re.compile(self.re, re.I)

    def __call__(self, mo: re.Match[str] | re.Match[bytes]) -> str | bytes:
        return self[mo.string[mo.start() : mo.end()]]

    def mreplace[T: (str, bytes)](self, text: T) -> T:
        # Replace without regex compile
        if len(self.data) < 1 or self.re is None:
            return text
        assert self.regex is not None
        return self.regex.sub(self, text)  # ty: ignore[no-matching-overload]
