#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, zipfile

import calibre
from calibre.utils.localization import lang_as_iso639_1
from calibre.utils.resources import compiled_coffeescript

class JavaScriptLoader(object):

    JS = {x:('viewer/%s.js'%x if y is None else y) for x, y in {

            'bookmarks':None,
            'referencing':None,
            'hyphenation':None,
            'jquery':'content_server/jquery.js',
            'jquery_scrollTo':None,
            'hyphenator':'viewer/hyphenate/Hyphenator.js',
            'images':None

        }.iteritems()}

    CS = {
            'cfi':'ebooks.oeb.display.cfi',
            'indexing':'ebooks.oeb.display.indexing',
        }

    ORDER = ('jquery', 'jquery_scrollTo', 'bookmarks', 'referencing', 'images',
            'hyphenation', 'hyphenator', 'cfi', 'indexing',)


    def __init__(self, dynamic_coffeescript=False):
        self._dynamic_coffeescript = dynamic_coffeescript
        if self._dynamic_coffeescript:
            try:
                from calibre.utils.serve_coffee import compile_coffeescript
                compile_coffeescript
            except:
                self._dynamic_coffeescript = False
                print ('WARNING: Failed to load serve_coffee, not compiling '
                        'coffeescript dynamically.')

        self._cache = {}
        self._hp_cache = {}

    def get(self, name):
        ans = self._cache.get(name, None)
        if ans is None:
            src = self.CS.get(name, None)
            if src is None:
                src = self.JS.get(name, None)
                if src is None:
                    raise KeyError('No such resource: %s'%name)
                ans = P(src, data=True,
                        allow_user_override=False).decode('utf-8')
            else:
                dynamic = (self._dynamic_coffeescript and
                        os.path.exists(calibre.__file__))
                ans = compiled_coffeescript(src, dynamic=dynamic).decode('utf-8')
            self._cache[name] = ans

        return ans

    def __call__(self, evaljs, lang, default_lang):
        for x in self.ORDER:
            src = self.get(x)
            evaljs(src)

        if not lang:
            lang = 'en'

        def lang_name(l):
            l = l.lower()
            l = lang_as_iso639_1(l)
            if not l:
                l = 'en'
            l = {'en':'en-us', 'nb':'nb-no', 'el':'el-monoton'}.get(l, l)
            return l.lower().replace('_', '-')

        if not self._hp_cache:
            with zipfile.ZipFile(P('viewer/hyphenate/patterns.zip',
                allow_user_override=False), 'r') as zf:
                for pat in zf.namelist():
                    raw = zf.read(pat).decode('utf-8')
                    self._hp_cache[pat.partition('.')[0]] = raw

        if lang_name(lang) not in self._hp_cache:
            lang = lang_name(default_lang)

        lang = lang_name(lang)

        evaljs('\n\n'.join(self._hp_cache.itervalues()))

        return lang

