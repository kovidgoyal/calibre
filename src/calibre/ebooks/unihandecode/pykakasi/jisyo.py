# -*- coding: utf-8 -*-
#  jisyo.py
#
# Copyright 2011 Hiroshi Miura <miurahr@linux.com>
from cPickle import load
import anydbm,marshal
from zlib import decompress
import os

class jisyo (object):
    kanwadict = None
    itaijidict = None
    jisyo_table = {}

    def __init__(self):
        if self.kanwadict is None:
            dictpath = os.path.join('unihandecode','pykakasi','kanwadict2.db')
            self.kanwadict = anydbm.open(dictpath,'r')
        if self.itaijidict is  None:
            itaijipath = os.path.join('unihandecode','pykakasi','itaijidict2.pickle')
            itaiji_pkl = open(itaijipath, 'rb')
            self.itaijidict = load(itaiji_pkl)

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

