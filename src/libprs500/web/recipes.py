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
Contains recipes for various common news sources and websites.
'''
import re
from libprs500.web.feeds.news import BasicNewsRecipe

_basic_recipes = (BasicNewsRecipe,)
_basic_recipe_names = (i.__name__ for i in _basic_recipes)

def compile_recipe(src):
    '''
    Compile the code in src and return the first object that is
    '''
    locals = {}
    exec src in globals(), locals
    for obj in locals.values():
        if type(obj) is type and obj.__name__ not in _basic_recipe_names:
            for base in obj.__bases__:
                if base in _basic_recipes:
                    return obj
    
    return None


def get_feed(title):
    '''
    Return a builtin recipe class whoose title == C{title} or None if no such
    recipe exists.
    
    @type title: string
    @rtype: class or None
    '''
    if isinstance(_feeds[0], basestring):
        for i, val in enumerate(_feeds):
            recipe = compile_recipe(val)
            if recipe is None:
                raise RuntimeError('The builtin Recipe #%d is invalid.'%i)
            _feeds[i] = recipe
    
    for recipe in _feeds:
        if recipe.title == title:
            return recipe
        
    return None
    

#: Recipes to be used with feeds2disk
_feeds = ['class Temp(BasicNewsRecipe):\n\ttitle="temp"']