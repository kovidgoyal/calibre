#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

import calibre
from calibre.utils.resources import compiled_coffeescript, load_hyphenator_dicts


class JavaScriptLoader(object):

    JS = {x:('viewer/%s.js'%x if y is None else y) for x, y in {

            'bookmarks':None,
            'referencing':None,
            'hyphenation':None,
            'jquery':'viewer/jquery.js',
            'jquery_scrollTo':None,
            'hyphenator':'viewer/hyphenate/Hyphenator.js',
            'images':None

        }.iteritems()}

    CS = {
            'cfi':'ebooks.oeb.display.cfi',
            'indexing':'ebooks.oeb.display.indexing',
            'paged':'ebooks.oeb.display.paged',
            'utils':'ebooks.oeb.display.utils',
            'fs':'ebooks.oeb.display.full_screen',
            'math': 'ebooks.oeb.display.mathjax',
            'extract': 'ebooks.oeb.display.extract',
        }

    ORDER = ('jquery', 'jquery_scrollTo', 'bookmarks', 'referencing', 'images',
            'hyphenation', 'hyphenator', 'utils', 'cfi', 'indexing', 'paged',
            'fs', 'math', 'extract')

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
                dynamic = self._dynamic_coffeescript and calibre.__file__ and not calibre.__file__.endswith('.pyo') and os.path.exists(calibre.__file__)
                ans = compiled_coffeescript(src, dynamic=dynamic).decode('utf-8')
            self._cache[name] = ans

        return ans

    def __call__(self, evaljs, lang, default_lang):
        for x in self.ORDER:
            src = self.get(x)
            evaljs(src)

        js, lang = load_hyphenator_dicts(self._hp_cache, lang, default_lang)
        evaljs(js)
        return lang
