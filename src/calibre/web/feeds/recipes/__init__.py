#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Builtin recipes.
'''
import re, imp, inspect, time, os
from calibre.web.feeds.news import BasicNewsRecipe, CustomIndexRecipe, \
    AutomaticNewsRecipe, CalibrePeriodical
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre import __appname__, english_sort
from calibre.utils.config import JSONConfig

BeautifulSoup, time, english_sort

basic_recipes = (BasicNewsRecipe, AutomaticNewsRecipe, CustomIndexRecipe,
        CalibrePeriodical)
_tdir = None
_crep = 0

custom_recipes = JSONConfig('custom_recipes/index.json')

def custom_recipe_filename(id_, title):
    from calibre.utils.filenames import ascii_filename
    return ascii_filename(title[:50]) + \
                        ('_%s.recipe'%id_)

def compile_recipe(src):
    '''
    Compile the code in src and return the first object that is a recipe or profile.
    @param src: Python source code
    @type src: string
    @return: Recipe class or None, if no such class was found in C{src}
    '''
    global _tdir, _crep
    if _tdir is None or not os.path.exists(_tdir):
        _tdir = PersistentTemporaryDirectory('_recipes')
    temp = os.path.join(_tdir, 'recipe%d.py'%_crep)
    _crep += 1
    if not isinstance(src, unicode):
        match = re.search(r'coding[:=]\s*([-\w.]+)', src[:200])
        enc = match.group(1) if match else 'utf-8'
        src = src.decode(enc)
    src = re.sub(r'from __future__.*', '', src)
    f = open(temp, 'wb')
    src = 'from %s.web.feeds.news import BasicNewsRecipe, AutomaticNewsRecipe\n'%__appname__ + src
    src = '# coding: utf-8\n' + src
    src = 'from __future__ import with_statement\n' + src

    src = src.replace('from libprs500', 'from calibre').encode('utf-8')
    f.write(src)
    f.close()
    module = imp.find_module(os.path.splitext(os.path.basename(temp))[0],
        [os.path.dirname(temp)])
    module = imp.load_module(os.path.splitext(os.path.basename(temp))[0], *module)
    classes = inspect.getmembers(module,
            lambda x : inspect.isclass(x) and \
                issubclass(x, (BasicNewsRecipe,)) and \
                x not in basic_recipes)
    if not classes:
        return None

    return classes[0][1]


