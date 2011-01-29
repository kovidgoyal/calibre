# -*- coding: utf-8 -*-
#  k2a.py
#
# Copyright 2011 Hiroshi Miura <miurahr@linux.com>
#
# Original copyright:
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
# * You should have received a copy of the GNU General Public License
# * along with KAKASI, see the file COPYING.  If not, write to the Free
# * Software Foundation Inc., 59 Temple Place - Suite 330, Boston, MA
# * 02111-1307, USA.
# */

from calibre.ebooks.unihandecode.pykakasi.jisyo import jisyo

class K2a (object):

    K2a_table = {
        u"\u30a1":"a", u"\u30a2":"a",
        u"\u30a3":"i", u"\u30a4":"i",
        u"\u30a5":"u", u"\u30a6":"u",
        u"\u30a6\u309b":"vu", u"\u30a6\u309b\u30a1":"va",
        u"\u30a6\u309b\u30a3":"vi", u"\u30a6\u309b\u30a7":"ve",
        u"\u30a6\u309b\u30a9":"vo",
        u"\u30a7":"e", u"\u30a8":"e",
        u"\u30a9":"o", u"\u30aa":"o",

        u"\u30ab":"ka", u"\u30ac":"ga",
        u"\u30ad":"ki", u"\u30ad\u30a1":"kya",
        u"\u30ad\u30a5":"kyu", u"\u30ad\u30a9":"kyo",
        u"\u30ae":"gi", u"\u30b0\u30e3":"gya",
        u"\u30ae\u30a5":"gyu", u"\u30ae\u30e7":"gyo",
        u"\u30af":"ku", u"\u30b0":"gu",
        u"\u30b1":"ke", u"\u30b2":"ge",
        u"\u30b3":"ko", u"\u30b4":"go",

        u"\u30b5":"sa", u"\u30b6":"za",
        u"\u30b7":"shi", u"\u30b7\u30e3":"sha",
        u"\u30b7\u30e5":"shu", u"\u30b7\u30e7":"sho",
        u"\u30b8":"ji", u"\u30b8\u30e3":"ja",
        u"\u30b8\u30e5":"ju", u"\u30b8\u30e7":"jo",
        u"\u30b9":"su", u"\u30ba":"zu",
        u"\u30bb":"se", u"\u30bc":"ze",
        u"\u30bd":"so", u"\u30be":"zo",

        u"\u30bf":"ta", u"\u30c0":"da",
        u"\u30c1":"chi", u"\u30c1\u30a7":"che", u"\u30c1\u30e3":"cha",
        u"\u30c1\u30e5":"chu", u"\u30c1\u30e7":"cho",
        u"\u30c2":"ji", u"\u30c2\u30e3":"ja",
        u"\u30c2\u30e5":"ju", u"\u30c2\u30e7":"jo",

        u"\u30c3":"tsu",
        u"\u30c3\u30a6\u309b":"vvu",
        u"\u30c3\u30a6\u309b\u30a1":"vva",
        u"\u30c3\u30a6\u309b\u30a3":"vvi",
        u"\u30c3\u30a6\u309b\u30a7":"vve",
        u"\u30c3\u30a6\u309b\u30a9":"vvo",
        u"\u30c3\u30ab":"kka", u"\u30c3\u30ac":"gga",
        u"\u30c3\u30ad":"kki", u"\u30c3\u30ad\u30e3":"kkya",
        u"\u30c3\u30ad\u30e5":"kkyu", u"\u30c3\u30ad\u30e7":"kkyo",
        u"\u30c3\u30ae":"ggi", u"\u30c3\u30ae\u30e3":"ggya",
        u"\u30c3\u30ae\u30e5":"ggyu", u"\u30c3\u30ae\u30e7":"ggyo",
        u"\u30c3\u30af":"kku", u"\u30c3\u30b0":"ggu",
        u"\u30c3\u30b1":"kke", u"\u30c3\u30b2":"gge",
        u"\u30c3\u30b3":"kko", u"\u30c3\u30b4":"ggo",
        u"\u30c3\u30b5":"ssa", u"\u30c3\u30b6":"zza",
        u"\u30c3\u30b7":"sshi", u"\u30c3\u30b7\u30e3":"ssha",
        u"\u30c3\u30b7\u30e5":"sshu", u"\u30c3\u30b7\u30e7":"ssho",
        u"\u30c3\u30b8":"jji", u"\u30c3\u30b8\u30e3":"jja",
        u"\u30c3\u30b8\u30e5":"jju", u"\u30c3\u30b8\u30e7":"jjo",
        u"\u30c3\u30b9":"ssu", u"\u30c3\u30ba":"zzu",
        u"\u30c3\u30bb":"sse", u"\u30c3\u30be":"zze",
        u"\u30c3\u30bd":"sso", u"\u30c3\u30be":"zzo",
        u"\u30c3\u30bf":"tta", u"\u30c3\u30c0":"dda",
        u"\u30c3\u30c1":"tchi", u"\u30c3\u30c1\u30e3":"tcha",
        u"\u30c3\u30c1\u30e5":"tchu", u"\u30c3\u30c1\u30e7":"tcho",
        u"\u30c3\u30c2":"jji", u"\u30c3\u30c2\u30e3":"jjya",
        u"\u30c3\u30c2\u30e5":"jjyu", u"\u30c3\u30c2\u30e7":"jjyo",
        u"\u30c3\u30c4":"ttsu", u"\u30c3\u30c5":"zzu",
        u"\u30c3\u30c6":"tte", u"\u30c3\u30c7":"dde",
        u"\u30c3\u30c8":"tto", u"\u30c3\u30c9":"ddo",
        u"\u30c3\u30cf":"hha", u"\u30c3\u30d0":"bba",
        u"\u30c3\u30d1":"ppa",
        u"\u30c3\u30d2":"hhi", u"\u30c3\u30d2\u30e3":"hhya",
        u"\u30c3\u30d2\u30e5":"hhyu", u"\u30c3\u30d2\u30e7":"hhyo",
        u"\u30c3\u30d3":"bbi", u"\u30c3\u30d3\u30e3":"bbya",
        u"\u30c3\u30d3\u30e5":"bbyu", u"\u30c3\u30d3\u30e7":"bbyo",
        u"\u30c3\u30d4":"ppi", u"\u30c3\u30d4\u30e3":"ppya",
        u"\u30c3\u30d4\u30e5":"ppyu", u"\u30c3\u30d4\u30e7":"ppyo",
        u"\u30c3\u30d5":"ffu", u"\u30c3\u30d5\u30a1":"ffa",
        u"\u30c3\u30d5\u30a3":"ffi", u"\u30c3\u30d5\u30a7":"ffe",
        u"\u30c3\u30d5\u30a9":"ffo",
        u"\u30c3\u30d6":"bbu", u"\u30c3\u30d7":"ppu",
        u"\u30c3\u30d8":"hhe", u"\u30c3\u30d9":"bbe",
        u"\u30c3\u30da":"ppe",
        u"\u30c3\u30db":"hho", u"\u30c3\u30dc":"bbo",
        u"\u30c3\u30dd":"ppo",
        u"\u30c3\u30e4":"yya", u"\u30c3\u30e6":"yyu",
        u"\u30c3\u30e8":"yyo",
        u"\u30c3\u30e9":"rra", u"\u30c3\u30ea":"rri",
        u"\u30c3\u30ea\u30e3":"rrya", u"\u30c3\u30ea\u30e5":"rryu",
        u"\u30c3\u30ea\u30e7":"rryo",
        u"\u30c3\u30eb":"rru", u"\u30c3\u30ec":"rre",
        u"\u30c3\u30ed":"rro",

        u"\u30c4":"tsu", u"\u30c5":"zu",
        u"\u30c6":"te", u"\u30c7":"de", u"\u30c7\u30a3":"di",
        u"\u30c8":"to", u"\u30c9":"do",

        u"\u30ca":"na",
        u"\u30cb":"ni", u"\u30cb\u30e3":"nya",
        u"\u30cb\u30e5":"nyu", u"\u30cb\u30e7":"nyo",
        u"\u30cc":"nu", u"\u30cd":"ne", u"\u30ce":"no",

        u"\u30cf":"ha", u"\u30d0":"ba", u"\u30d1":"pa",
        u"\u30d2":"hi", u"\u30d2\u30e3":"hya",
        u"\u30d2\u30e5":"hyu", u"\u30d2\u30e7":"hyo",
        u"\u30d3":"bi", u"\u30d3\u30e3":"bya",
        u"\u30d3\u30e5":"byu", u"\u30d3\u30e7":"byo",
        u"\u30d4":"pi", u"\u30d4\u30e3":"pya",
        u"\u30d4\u30e5":"pyu", u"\u30d4\u30e7":"pyo",
        u"\u30d5":"fu", u"\u30d5\u30a1":"fa",
        u"\u30d5\u30a3":"fi", u"\u30d5\u30a7":"fe",
        u"\u30d5\u30a9":"fo",
        u"\u30d6":"bu", u"\u30d7":"pu",
        u"\u30d8":"he", u"\u30d9":"be", u"\u30da":"pe",
        u"\u30db":"ho", u"\u30dc":"bo", u"\u30dd":"po",

        u"\u30de":"ma",
        u"\u30df":"mi", u"\u30df\u30e3":"mya",
        u"\u30df\u30e5":"myu", u"\u30df\u30e7":"myo",
        u"\u30e0":"mu", u"\u30e1":"me", u"\u30e2":"mo",

        u"\u30e3":"ya", u"\u30e4":"ya",
        u"\u30e5":"yu", u"\u30e6":"yu",
        u"\u30e7":"yo", u"\u30e8":"yo",

        u"\u30e9":"ra",
        u"\u30ea":"ri", u"\u30ea\u30e3":"rya",
        u"\u30ea\u30e5":"ryu", u"\u30ea\u30e7":"ryo",
        u"\u30eb":"ru", u"\u30ec":"re", u"\u30ed":"ro",

        u"\u30ee":"wa", u"\u30ef":"wa",
        u"\u30f0":"i", u"\u30f1":"e", 
        u"\u30f2":"wo", u"\u30f3":"n",

        u"\u30f3\u30a2":"n'a", u"\u30f3\u30a4":"n'i",
        u"\u30f3\u30a6":"n'u", u"\u30f3\u30a8":"n'e",
        u"\u30f3\u30aa":"n'o",

        u"\u30f4":"vu", u"\u30f5":"ka",
        u"\u30f6":"ke",
    }

    def isKatakana(self, char):
        return ( 0x30a0 < ord(char) and ord(char) < 0x30f7)

    def convert(self, text):
        Hstr = ""
        max_len = -1
        r = min(4, len(text)+1)
        for x in xrange(r):
            if text[:x] in self.K2a_table:
                if max_len < x:
                    max_len = x
                    Hstr = self.K2a_table[text[:x]]
        return (Hstr, max_len) 

