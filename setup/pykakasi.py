#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2011, Hiroshi Miura <miurahr@linux.com>'
__docformat__ = 'restructuredtext en'

import os,re
from cPickle import dump
from marshal import dumps
import anydbm
from zlib import compress

from setup import Command, basenames, __appname__

class Pykakasi(Command):

    records = {}

    PATH = os.path.join(Command.SRC,  __appname__, 'ebooks', 'unihandecode', 'pykakasi')

    def run(self,opts):

        src = self.j(self.PATH, 'kakasidict.utf8')
        dest = self.j(self.RESOURCES, 'localization',
                'pykakasi','kanwadict2.db')
        base = os.path.dirname(dest)
        if not os.path.exists(base):
            os.makedirs(base)

        if not self.newer(dest, src):
            self.info('kanwadict is up to date')
        else:
            self.info('Generating Kanwadict to', dest)

            for line in open(src, "r"):
                self.parsekdict(line)
            self.kanwaout(dest)

        src = self.j(self.PATH, 'itaijidict.utf8')
        dest = self.j(self.RESOURCES, 'localization',
                'pykakasi','itaijidict2.pickle')

        if not self.newer(dest, src):
            self.info('itaijidict is up to date')
        else:
            self.info('Generating Itaijidict to', dest)
            self.mkitaiji(src, dest)

        src = self.j(self.PATH, 'kanadict.utf8')
        dest = self.j(self.RESOURCES, 'localization',
                'pykakasi','kanadict2.pickle')

        if not self.newer(dest, src):
            self.info('kanadict is up to date')
        else:
            self.info('Generating kanadict to', dest)
            self.mkkanadict(src, dest)

        return


    def mkitaiji(self, src, dst):
        dic = {}
        for line in open(src, "r"):
            line = line.decode("utf-8").strip()
            if line.startswith(';;'): # skip comment
                continue
            if re.match(r"^$",line):
                continue
            pair = re.sub(r'\\u([0-9a-fA-F]{4})', lambda x:unichr(int(x.group(1),16)), line)
            dic[pair[0]] = pair[1]
        dump(dic, open(dst, 'w'), protocol=2) #pickle

    def mkkanadict(self, src, dst):
        dic = {}
        for line in open(src, "r"):
            line = line.decode("utf-8").strip()
            if line.startswith(';;'): # skip comment
                continue
            if re.match(r"^$",line):
                continue
            (alpha, kana) = line.split(' ')
            dic[kana] = alpha
        dump(dic, open(dst, 'w'), protocol=2) #pickle

    def parsekdict(self, line):
        line = line.decode("utf-8").strip()
        if line.startswith(';;'): # skip comment
            return
        (yomi, kanji) = line.split(' ')
        if ord(yomi[-1:]) <= ord('z'): 
            tail = yomi[-1:]
            yomi = yomi[:-1]
        else:
            tail = ''
        self.updaterec(kanji, yomi, tail)

    def updaterec(self, kanji, yomi, tail):
            key = "%04x"%ord(kanji[0]) 
            if key in self.records:
                if kanji in self.records[key]:
                    rec = self.records[key][kanji]
                    rec.append((yomi,tail))
                    self.records[key].update( {kanji: rec} )
                else:
                    self.records[key][kanji]=[(yomi, tail)]
            else:
                self.records[key] = {}
                self.records[key][kanji]=[(yomi, tail)]

    def kanwaout(self, out):
        dic = anydbm.open(out, 'c')
        for (k, v) in self.records.iteritems():
            dic[k] = compress(dumps(v))
        dic.close()

