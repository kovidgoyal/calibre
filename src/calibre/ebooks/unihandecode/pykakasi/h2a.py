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


from polyglot.builtins import range


class H2a (object):

    H2a_table = {
        "\u3041":"a", "\u3042":"a",
        "\u3043":"i", "\u3044":"i",
        "\u3045":"u", "\u3046":"u",
        "\u3046\u309b":"vu", "\u3046\u309b\u3041":"va",
        "\u3046\u309b\u3043":"vi", "\u3046\u309b\u3047":"ve",
        "\u3046\u309b\u3049":"vo",
        "\u3047":"e", "\u3048":"e",
        "\u3049":"o", "\u304a":"o",

        "\u304b":"ka", "\u304c":"ga",
        "\u304d":"ki", "\u304d\u3041":"kya",
        "\u304d\u3045":"kyu", "\u304d\u3049":"kyo",
        "\u304e":"gi", "\u3050\u3083":"gya",
        "\u304e\u3045":"gyu", "\u304e\u3087":"gyo",
        "\u304f":"ku", "\u3050":"gu",
        "\u3051":"ke", "\u3052":"ge",
        "\u3053":"ko", "\u3054":"go",

        "\u3055":"sa", "\u3056":"za",
        "\u3057":"shi", "\u3057\u3083":"sha",
        "\u3057\u3085":"shu", "\u3057\u3087":"sho",
        "\u3058":"ji", "\u3058\u3083":"ja",
        "\u3058\u3085":"ju", "\u3058\u3087":"jo",
        "\u3059":"su", "\u305a":"zu",
        "\u305b":"se", "\u305c":"ze",
        "\u305d":"so", "\u305e":"zo",

        "\u305f":"ta", "\u3060":"da",
        "\u3061":"chi", "\u3061\u3047":"che", "\u3061\u3083":"cha",
        "\u3061\u3085":"chu", "\u3061\u3087":"cho",
        "\u3062":"ji", "\u3062\u3083":"ja",
        "\u3062\u3085":"ju", "\u3062\u3087":"jo",

        "\u3063":"tsu",
        "\u3063\u3046\u309b":"vvu",
        "\u3063\u3046\u309b\u3041":"vva",
        "\u3063\u3046\u309b\u3043":"vvi",
        "\u3063\u3046\u309b\u3047":"vve",
        "\u3063\u3046\u309b\u3049":"vvo",
        "\u3063\u304b":"kka", "\u3063\u304c":"gga",
        "\u3063\u304d":"kki", "\u3063\u304d\u3083":"kkya",
        "\u3063\u304d\u3085":"kkyu", "\u3063\u304d\u3087":"kkyo",
        "\u3063\u304e":"ggi", "\u3063\u304e\u3083":"ggya",
        "\u3063\u304e\u3085":"ggyu", "\u3063\u304e\u3087":"ggyo",
        "\u3063\u304f":"kku", "\u3063\u3050":"ggu",
        "\u3063\u3051":"kke", "\u3063\u3052":"gge",
        "\u3063\u3053":"kko", "\u3063\u3054":"ggo",
        "\u3063\u3055":"ssa", "\u3063\u3056":"zza",
        "\u3063\u3057":"sshi", "\u3063\u3057\u3083":"ssha",
        "\u3063\u3057\u3085":"sshu", "\u3063\u3057\u3087":"ssho",
        "\u3063\u3058":"jji", "\u3063\u3058\u3083":"jja",
        "\u3063\u3058\u3085":"jju", "\u3063\u3058\u3087":"jjo",
        "\u3063\u3059":"ssu", "\u3063\u305a":"zzu",
        "\u3063\u305b":"sse", "\u3063\u305e":"zze",
        "\u3063\u305d":"sso", "\u3063\u305c":"zzo",
        "\u3063\u305f":"tta", "\u3063\u3060":"dda",
        "\u3063\u3061":"tchi", "\u3063\u3061\u3083":"tcha",
        "\u3063\u3061\u3085":"tchu", "\u3063\u3061\u3087":"tcho",
        "\u3063\u3062":"jji", "\u3063\u3062\u3083":"jjya",
        "\u3063\u3062\u3085":"jjyu", "\u3063\u3062\u3087":"jjyo",
        "\u3063\u3064":"ttsu", "\u3063\u3065":"zzu",
        "\u3063\u3066":"tte", "\u3063\u3067":"dde",
        "\u3063\u3068":"tto", "\u3063\u3069":"ddo",
        "\u3063\u306f":"hha", "\u3063\u3070":"bba",
        "\u3063\u3071":"ppa",
        "\u3063\u3072":"hhi", "\u3063\u3072\u3083":"hhya",
        "\u3063\u3072\u3085":"hhyu", "\u3063\u3072\u3087":"hhyo",
        "\u3063\u3073":"bbi", "\u3063\u3073\u3083":"bbya",
        "\u3063\u3073\u3085":"bbyu", "\u3063\u3073\u3087":"bbyo",
        "\u3063\u3074":"ppi", "\u3063\u3074\u3083":"ppya",
        "\u3063\u3074\u3085":"ppyu", "\u3063\u3074\u3087":"ppyo",
        "\u3063\u3075":"ffu", "\u3063\u3075\u3041":"ffa",
        "\u3063\u3075\u3043":"ffi", "\u3063\u3075\u3047":"ffe",
        "\u3063\u3075\u3049":"ffo",
        "\u3063\u3076":"bbu", "\u3063\u3077":"ppu",
        "\u3063\u3078":"hhe", "\u3063\u3079":"bbe",
        "\u3063\u307a":"ppe",
        "\u3063\u307b":"hho", "\u3063\u307c":"bbo",
        "\u3063\u307d":"ppo",
        "\u3063\u3084":"yya", "\u3063\u3086":"yyu",
        "\u3063\u3088":"yyo",
        "\u3063\u3089":"rra", "\u3063\u308a":"rri",
        "\u3063\u308a\u3083":"rrya", "\u3063\u308a\u3085":"rryu",
        "\u3063\u308a\u3087":"rryo",
        "\u3063\u308b":"rru", "\u3063\u308c":"rre",
        "\u3063\u308d":"rro",

        "\u3064":"tsu", "\u3065":"zu",
        "\u3066":"te", "\u3067":"de", "\u3067\u3043":"di",
        "\u3068":"to", "\u3069":"do",

        "\u306a":"na",
        "\u306b":"ni", "\u306b\u3083":"nya",
        "\u306b\u3085":"nyu", "\u306b\u3087":"nyo",
        "\u306c":"nu", "\u306d":"ne", "\u306e":"no",

        "\u306f":"ha", "\u3070":"ba", "\u3071":"pa",
        "\u3072":"hi", "\u3072\u3083":"hya",
        "\u3072\u3085":"hyu", "\u3072\u3087":"hyo",
        "\u3073":"bi", "\u3073\u3083":"bya",
        "\u3073\u3085":"byu", "\u3073\u3087":"byo",
        "\u3074":"pi", "\u3074\u3083":"pya",
        "\u3074\u3085":"pyu", "\u3074\u3087":"pyo",
        "\u3075":"fu", "\u3075\u3041":"fa",
        "\u3075\u3043":"fi", "\u3075\u3047":"fe",
        "\u3075\u3049":"fo",
        "\u3076":"bu", "\u3077":"pu",
        "\u3078":"he", "\u3079":"be", "\u307a":"pe",
        "\u307b":"ho", "\u307c":"bo", "\u307d":"po",

        "\u307e":"ma",
        "\u307f":"mi", "\u307f\u3083":"mya",
        "\u307f\u3085":"myu", "\u307f\u3087":"myo",
        "\u3080":"mu", "\u3081":"me", "\u3082":"mo",

        "\u3083":"ya", "\u3084":"ya",
        "\u3085":"yu", "\u3086":"yu",
        "\u3087":"yo", "\u3088":"yo",

        "\u3089":"ra",
        "\u308a":"ri", "\u308a\u3083":"rya",
        "\u308a\u3085":"ryu", "\u308a\u3087":"ryo",
        "\u308b":"ru", "\u308c":"re", "\u308d":"ro",

        "\u308e":"wa", "\u308f":"wa",
        "\u3090":"i", "\u3091":"e",
        "\u3092":"wo", "\u3093":"n",

        "\u3093\u3042":"n'a", "\u3093\u3044":"n'i",
        "\u3093\u3046":"n'u", "\u3093\u3048":"n'e",
        "\u3093\u304a":"n'o",
    }

# this class is Borg
    _shared_state = {}

    def __new__(cls, *p, **k):
        self = object.__new__(cls, *p, **k)
        self.__dict__ = cls._shared_state
        return self

    def isHiragana(self, char):
        return (0x3040 < ord(char) and ord(char) < 0x3094)

    def convert(self, text):
        Hstr = ""
        max_len = -1
        r = min(4, len(text)+1)
        for x in range(r):
            if text[:x] in self.H2a_table:
                if max_len < x:
                    max_len = x
                    Hstr = self.H2a_table[text[:x]]
        return (Hstr, max_len)
