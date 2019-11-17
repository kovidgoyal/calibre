#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2017, Kovid Goyal <kovid at kovidgoyal.net>



import sys

from calibre.constants import iswindows, preferred_encoding, ispy3


if ispy3:
    from getpass import getpass
    getpass
else:
    def getpass(prompt):
        if iswindows:
            # getpass is broken on windows with python 2.x and unicode, the
            # below implementation is from the python 3 source code
            import msvcrt
            for c in prompt:
                msvcrt.putwch(c)
            pw = ""
            while 1:
                c = msvcrt.getwch()
                if c == '\r' or c == '\n':
                    break
                if c == '\003':
                    raise KeyboardInterrupt
                if c == '\b':
                    pw = pw[:-1]
                else:
                    pw = pw + c
            msvcrt.putwch('\r')
            msvcrt.putwch('\n')
            return pw
        else:
            enc = getattr(sys.stdin, 'encoding', preferred_encoding) or preferred_encoding
            from getpass import getpass
            return getpass(prompt).decode(enc)
