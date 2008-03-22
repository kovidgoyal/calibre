#!/usr/bin/env  python

##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
'''
Builtin recipes.
'''
recipes = ['newsweek', 'atlantic', 'economist', 'dilbert', 'portfolio', 
           'nytimes', 'usatoday']

import re, time 
from libprs500.web.feeds.news import BasicNewsRecipe, CustomIndexRecipe
from libprs500.ebooks.lrf.web.profiles import DefaultProfile, FullContentProfile
from libprs500.ebooks.lrf.web import builtin_profiles
from libprs500.ebooks.BeautifulSoup import BeautifulSoup

basic_recipes = (BasicNewsRecipe, CustomIndexRecipe, DefaultProfile, FullContentProfile)
basic_recipe_names = (i.__name__ for i in basic_recipes)


#: Compiled builtin recipe/profile classes
def load_recipe(module, package='libprs500.web.feeds.recipes'):
    module = __import__(package+'.'+module, fromlist=[''])
    for attr in dir(module):
        obj = getattr(module, attr)
        if type(obj) is not type:
            continue
        recipe = False
        for b in obj.__bases__:
            if b in basic_recipes:
                recipe = True
                break
        if not recipe:
            continue
        if obj not in basic_recipes:
            return obj


recipes = [load_recipe(i) for i in recipes]
    
def compile_recipe(src):
    '''
    Compile the code in src and return the first object that is a recipe or profile.
    @param src: Python source code
    @type src: string
    @return: Recipe/Profile class or None, if no such class was found in C{src} 
    '''
    locals = {}
    exec src in globals(), locals
    for obj in locals.values():
        if type(obj) is type and obj.__name__ not in basic_recipe_names:
            for base in obj.__bases__:
                if base in basic_recipes:
                    return obj
    
    return None


def get_builtin_recipe(title):
    '''
    Return a builtin recipe/profile class whoose title == C{title} or None if no such
    recipe exists. Also returns a flag that is True iff the found recipe is really
    an old-style Profile.
    
    @type title: string
    @rtype: class or None, boolean
    '''
    for r in recipes:
        if r.title == title:
            return r, False
    for p in builtin_profiles:
        if p.title == title:
            return p, True
    return None, False

_titles = list(frozenset([r.title for r in recipes] + [p.title for p in builtin_profiles]))
_titles.sort()
titles = _titles