# -*- coding: utf-8 -*-
#  jisyo.py
#
# Copyright 2011 Hiroshi Miura <miurahr@linux.com>
import six.moves.cPickle, marshal
from zlib import decompress


class jisyo (object):
    kanwadict = None
    itaijidict = None
    kanadict = None
    jisyo_table = {}

# this class is Borg
    _shared_state = {}

    def __new__(cls, *p, **k):
        self = object.__new__(cls, *p, **k)
        self.__dict__ = cls._shared_state
        return self

    def __init__(self):
        if self.kanwadict is None:
            self.kanwadict = six.moves.cPickle.loads(
                P('localization/pykakasi/kanwadict2.pickle', data=True))
        if self.itaijidict is None:
            self.itaijidict = six.moves.cPickle.loads(
                P('localization/pykakasi/itaijidict2.pickle', data=True))
        if self.kanadict is None:
            self.kanadict = six.moves.cPickle.loads(
                P('localization/pykakasi/kanadict2.pickle', data=True))

    def load_jisyo(self, char):
        try:  # python2
            key = "%04x"%ord(unicode(char))
        except:  # python3
            key = "%04x"%ord(char)

        try:  # already exist?
            table = self.jisyo_table[key]
        except:
            try:
                table = self.jisyo_table[key]  = marshal.loads(decompress(self.kanwadict[key]))
            except:
                return None
        return table

