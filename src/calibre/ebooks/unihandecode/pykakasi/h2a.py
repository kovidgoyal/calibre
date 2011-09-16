# -*- coding: utf-8 -*-
#  h2a.py
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
# */

class H2a (object):

    H2a_table = {
        u"\u3041":"a", u"\u3042":"a",
        u"\u3043":"i", u"\u3044":"i",
        u"\u3045":"u", u"\u3046":"u",
        u"\u3046\u309b":"vu", u"\u3046\u309b\u3041":"va",
        u"\u3046\u309b\u3043":"vi", u"\u3046\u309b\u3047":"ve",
        u"\u3046\u309b\u3049":"vo",
        u"\u3047":"e", u"\u3048":"e",
        u"\u3049":"o", u"\u304a":"o",

        u"\u304b":"ka", u"\u304c":"ga",
        u"\u304d":"ki", u"\u304d\u3041":"kya",
        u"\u304d\u3045":"kyu", u"\u304d\u3049":"kyo",
        u"\u304e":"gi", u"\u3050\u3083":"gya",
        u"\u304e\u3045":"gyu", u"\u304e\u3087":"gyo",
        u"\u304f":"ku", u"\u3050":"gu",
        u"\u3051":"ke", u"\u3052":"ge",
        u"\u3053":"ko", u"\u3054":"go",

        u"\u3055":"sa", u"\u3056":"za",
        u"\u3057":"shi", u"\u3057\u3083":"sha",
        u"\u3057\u3085":"shu", u"\u3057\u3087":"sho",
        u"\u3058":"ji", u"\u3058\u3083":"ja",
        u"\u3058\u3085":"ju", u"\u3058\u3087":"jo",
        u"\u3059":"su", u"\u305a":"zu",
        u"\u305b":"se", u"\u305c":"ze",
        u"\u305d":"so", u"\u305e":"zo",

        u"\u305f":"ta", u"\u3060":"da",
        u"\u3061":"chi", u"\u3061\u3047":"che", u"\u3061\u3083":"cha",
        u"\u3061\u3085":"chu", u"\u3061\u3087":"cho",
        u"\u3062":"ji", u"\u3062\u3083":"ja",
        u"\u3062\u3085":"ju", u"\u3062\u3087":"jo",

        u"\u3063":"tsu",
        u"\u3063\u3046\u309b":"vvu",
        u"\u3063\u3046\u309b\u3041":"vva",
        u"\u3063\u3046\u309b\u3043":"vvi",
        u"\u3063\u3046\u309b\u3047":"vve",
        u"\u3063\u3046\u309b\u3049":"vvo",
        u"\u3063\u304b":"kka", u"\u3063\u304c":"gga",
        u"\u3063\u304d":"kki", u"\u3063\u304d\u3083":"kkya",
        u"\u3063\u304d\u3085":"kkyu", u"\u3063\u304d\u3087":"kkyo",
        u"\u3063\u304e":"ggi", u"\u3063\u304e\u3083":"ggya",
        u"\u3063\u304e\u3085":"ggyu", u"\u3063\u304e\u3087":"ggyo",
        u"\u3063\u304f":"kku", u"\u3063\u3050":"ggu",
        u"\u3063\u3051":"kke", u"\u3063\u3052":"gge",
        u"\u3063\u3053":"kko", u"\u3063\u3054":"ggo",
        u"\u3063\u3055":"ssa", u"\u3063\u3056":"zza",
        u"\u3063\u3057":"sshi", u"\u3063\u3057\u3083":"ssha",
        u"\u3063\u3057\u3085":"sshu", u"\u3063\u3057\u3087":"ssho",
        u"\u3063\u3058":"jji", u"\u3063\u3058\u3083":"jja",
        u"\u3063\u3058\u3085":"jju", u"\u3063\u3058\u3087":"jjo",
        u"\u3063\u3059":"ssu", u"\u3063\u305a":"zzu",
        u"\u3063\u305b":"sse", u"\u3063\u305e":"zze",
        u"\u3063\u305d":"sso", u"\u3063\u305e":"zzo",
        u"\u3063\u305f":"tta", u"\u3063\u3060":"dda",
        u"\u3063\u3061":"tchi", u"\u3063\u3061\u3083":"tcha",
        u"\u3063\u3061\u3085":"tchu", u"\u3063\u3061\u3087":"tcho",
        u"\u3063\u3062":"jji", u"\u3063\u3062\u3083":"jjya",
        u"\u3063\u3062\u3085":"jjyu", u"\u3063\u3062\u3087":"jjyo",
        u"\u3063\u3064":"ttsu", u"\u3063\u3065":"zzu",
        u"\u3063\u3066":"tte", u"\u3063\u3067":"dde",
        u"\u3063\u3068":"tto", u"\u3063\u3069":"ddo",
        u"\u3063\u306f":"hha", u"\u3063\u3070":"bba",
        u"\u3063\u3071":"ppa",
        u"\u3063\u3072":"hhi", u"\u3063\u3072\u3083":"hhya",
        u"\u3063\u3072\u3085":"hhyu", u"\u3063\u3072\u3087":"hhyo",
        u"\u3063\u3073":"bbi", u"\u3063\u3073\u3083":"bbya",
        u"\u3063\u3073\u3085":"bbyu", u"\u3063\u3073\u3087":"bbyo",
        u"\u3063\u3074":"ppi", u"\u3063\u3074\u3083":"ppya",
        u"\u3063\u3074\u3085":"ppyu", u"\u3063\u3074\u3087":"ppyo",
        u"\u3063\u3075":"ffu", u"\u3063\u3075\u3041":"ffa",
        u"\u3063\u3075\u3043":"ffi", u"\u3063\u3075\u3047":"ffe",
        u"\u3063\u3075\u3049":"ffo",
        u"\u3063\u3076":"bbu", u"\u3063\u3077":"ppu",
        u"\u3063\u3078":"hhe", u"\u3063\u3079":"bbe",
        u"\u3063\u307a":"ppe",
        u"\u3063\u307b":"hho", u"\u3063\u307c":"bbo",
        u"\u3063\u307d":"ppo",
        u"\u3063\u3084":"yya", u"\u3063\u3086":"yyu",
        u"\u3063\u3088":"yyo",
        u"\u3063\u3089":"rra", u"\u3063\u308a":"rri",
        u"\u3063\u308a\u3083":"rrya", u"\u3063\u308a\u3085":"rryu",
        u"\u3063\u308a\u3087":"rryo",
        u"\u3063\u308b":"rru", u"\u3063\u308c":"rre",
        u"\u3063\u308d":"rro",

        u"\u3064":"tsu", u"\u3065":"zu",
        u"\u3066":"te", u"\u3067":"de", u"\u3067\u3043":"di",
        u"\u3068":"to", u"\u3069":"do",

        u"\u306a":"na",
        u"\u306b":"ni", u"\u306b\u3083":"nya",
        u"\u306b\u3085":"nyu", u"\u306b\u3087":"nyo",
        u"\u306c":"nu", u"\u306d":"ne", u"\u306e":"no",

        u"\u306f":"ha", u"\u3070":"ba", u"\u3071":"pa",
        u"\u3072":"hi", u"\u3072\u3083":"hya",
        u"\u3072\u3085":"hyu", u"\u3072\u3087":"hyo",
        u"\u3073":"bi", u"\u3073\u3083":"bya",
        u"\u3073\u3085":"byu", u"\u3073\u3087":"byo",
        u"\u3074":"pi", u"\u3074\u3083":"pya",
        u"\u3074\u3085":"pyu", u"\u3074\u3087":"pyo",
        u"\u3075":"fu", u"\u3075\u3041":"fa",
        u"\u3075\u3043":"fi", u"\u3075\u3047":"fe",
        u"\u3075\u3049":"fo",
        u"\u3076":"bu", u"\u3077":"pu",
        u"\u3078":"he", u"\u3079":"be", u"\u307a":"pe",
        u"\u307b":"ho", u"\u307c":"bo", u"\u307d":"po",

        u"\u307e":"ma",
        u"\u307f":"mi", u"\u307f\u3083":"mya",
        u"\u307f\u3085":"myu", u"\u307f\u3087":"myo",
        u"\u3080":"mu", u"\u3081":"me", u"\u3082":"mo",

        u"\u3083":"ya", u"\u3084":"ya",
        u"\u3085":"yu", u"\u3086":"yu",
        u"\u3087":"yo", u"\u3088":"yo",

        u"\u3089":"ra",
        u"\u308a":"ri", u"\u308a\u3083":"rya",
        u"\u308a\u3085":"ryu", u"\u308a\u3087":"ryo",
        u"\u308b":"ru", u"\u308c":"re", u"\u308d":"ro",

        u"\u308e":"wa", u"\u308f":"wa",
        u"\u3090":"i", u"\u3091":"e",
        u"\u3092":"wo", u"\u3093":"n",

        u"\u3093\u3042":"n'a", u"\u3093\u3044":"n'i",
        u"\u3093\u3046":"n'u", u"\u3093\u3048":"n'e",
        u"\u3093\u304a":"n'o",
    }

# this class is Borg
    _shared_state = {}

    def __new__(cls, *p, **k):
        self = object.__new__(cls, *p, **k)
        self.__dict__ = cls._shared_state
        return self

    def isHiragana(self, char):
        return ( 0x3040 < ord(char) and ord(char) < 0x3094)

    def convert(self, text):
        Hstr = ""
        max_len = -1
        r = min(4, len(text)+1)
        for x in xrange(r):
            if text[:x] in self.H2a_table:
                if max_len < x:
                    max_len = x
                    Hstr = self.H2a_table[text[:x]]
        return (Hstr, max_len)

