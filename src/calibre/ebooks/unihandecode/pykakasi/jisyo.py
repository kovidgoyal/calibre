# -*- coding: utf-8 -*-
#  jisyo.py
#
# Copyright 2011 Hiroshi Miura <miurahr@linux.com>
from cPickle import load
import anydbm,marshal
from zlib import decompress
import os

import calibre.utils.resources as resources

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
            dictpath = resources.get_path(os.path.join('localization','pykakasi','kanwadict2.db'))
            self.kanwadict = anydbm.open(dictpath,'r')
        if self.itaijidict is  None:
            itaijipath = resources.get_path(os.path.join('localization','pykakasi','itaijidict2.pickle'))
            itaiji_pkl = open(itaijipath, 'rb')
            self.itaijidict = load(itaiji_pkl)
        if self.kanadict is None:
            kanadictpath = resources.get_path(os.path.join('localization','pykakasi','kanadict2.pickle'))
            kanadict_pkl = open(kanadictpath, 'rb')
            self.kanadict = load(kanadict_pkl)

    def load_jisyo(self, char):
        try:#python2
            key = "%04x"%ord(unicode(char))
        except:#python3
            key = "%04x"%ord(char)

        try: #already exist?
            table = self.jisyo_table[key]
        except:
            try:
                table = self.jisyo_table[key]  = marshal.loads(decompress(self.kanwadict[key]))
            except:
                return None
        return table

