# -*- coding: utf-8 -*-
#  j2h.py
#
# Copyright 2011 Hiroshi Miura <miurahr@linux.com>
#
#  Original Copyright:
# * KAKASI (Kanji Kana Simple inversion program)
# * $Id: jj2.c,v 1.7 2001-04-12 05:57:34 rug Exp $
# * Copyright (C) 1992
# * Hironobu Takahashi (takahasi@tiny.or.jp)
# *
# * This program is free software; you can redistribute it and/or modify
# * it under the terms of the GNU General Public License as published by
# * the Free Software Foundation; either versions 2, or (at your option)
# * any later version.
# *
# * This program is distributed in the hope that it will be useful
# * but WITHOUT ANY WARRANTY; without even the implied warranty of
# * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# * GNU General Public License for more details.
# *
# */


import re

from calibre.ebooks.unihandecode.pykakasi.jisyo import jisyo
from polyglot.builtins import iteritems


class J2H (object):

    kanwa = None

    cl_table = [
        "","aiueow", "aiueow", "aiueow", "aiueow", "aiueow", "aiueow", "aiueow",
        "aiueow", "aiueow", "aiueow", "k", "g", "k", "g", "k", "g", "k", "g", "k",
        "g", "s", "zj", "s", "zj", "s", "zj", "s", "zj", "s", "zj", "t", "d", "tc",
        "d", "aiueokstchgzjfdbpw", "t", "d", "t", "d", "t", "d", "n", "n", "n", "n",
        "n", "h", "b", "p", "h", "b", "p", "hf", "b", "p", "h", "b", "p", "h", "b",
        "p", "m", "m", "m", "m", "m", "y", "y", "y", "y", "y", "y", "rl", "rl",
        "rl", "rl", "rl", "wiueo", "wiueo", "wiueo", "wiueo", "w", "n", "v", "k",
        "k", "", "", "", "", "", "", "", "", ""]

    def __init__(self):
        self.kanwa = jisyo()

    def isKanji(self, c):
        return (0x3400 <= ord(c) and ord(c) < 0xfa2e)

    def isCletter(self, l, c):
        if (ord("ぁ") <= ord(c) and ord(c) <= 0x309f) and (l in self.cl_table[ord(c) - ord("ぁ")-1]):
            return True
        return False

    def itaiji_conv(self, text):
        r = []
        for c in text:
            if c in self.kanwa.itaijidict:
                r.append(c)
        for c in r:
            text = re.sub(c, self.kanwa.itaijidict[c], text)
        return text

    def convert(self, text):
        max_len = 0
        Hstr = ""
        table = self.kanwa.load_jisyo(text[0])
        if table is None:
            return ("", 0)
        for (k,v) in iteritems(table):
            length = len(k)
            if len(text) >= length:
                if text.startswith(k):
                    for (yomi, tail) in v:
                        if tail == '':
                            if max_len < length:
                                Hstr = yomi
                                max_len = length
                        elif max_len < length+1 and len(text) > length and self.isCletter(tail, text[length]):
                            Hstr=''.join([yomi,text[length]])
                            max_len = length+1
        return (Hstr, max_len)
