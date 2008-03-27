#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Builtin recipes.
'''
recipes = [
           'newsweek', 'atlantic', 'economist', 'dilbert', 'portfolio', 
           'nytimes', 'usatoday', 'outlook_india', 'bbc', 'greader', 'wsj',
           'wired',
          ]

import re, imp, inspect, time
from libprs500.web.feeds.news import BasicNewsRecipe, CustomIndexRecipe, AutomaticNewsRecipe
from libprs500.ebooks.lrf.web.profiles import DefaultProfile, FullContentProfile
from libprs500.ebooks.lrf.web import builtin_profiles
from libprs500.ebooks.BeautifulSoup import BeautifulSoup
from libprs500.path import path
from libprs500.ptempfile import PersistentTemporaryDirectory
from libprs500 import __appname__, english_sort

basic_recipes = (BasicNewsRecipe, AutomaticNewsRecipe, CustomIndexRecipe, DefaultProfile, FullContentProfile)
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

_tdir = None
def compile_recipe(src):
    '''
    Compile the code in src and return the first object that is a recipe or profile.
    @param src: Python source code
    @type src: string
    @return: Recipe/Profile class or None, if no such class was found in C{src} 
    '''
    global _tdir
    if _tdir is None:
        _tdir = path(PersistentTemporaryDirectory('_recipes'))
    temp = _tdir/('recipe%d.py'%time.time())
    f = open(temp, 'wb')
    src = 'from %s.web.feeds.news import BasicNewsRecipe, AutomaticNewsRecipe\n'%__appname__ + src
    src = 'from %s.ebooks.lrf.web.profiles import DefaultProfile, FullContentProfile\n'%__appname__ + src
    f.write(src)
    f.close()
    module = imp.find_module(temp.namebase, [temp.dirname()])
    module = imp.load_module(temp.namebase, *module)
    classes = inspect.getmembers(module, 
            lambda x : inspect.isclass(x) and \
                issubclass(x, (DefaultProfile, BasicNewsRecipe)) and \
                x not in basic_recipes)
    if not classes:
        return None
    
    return classes[0][1]


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
_titles.sort(cmp=english_sort)
titles = _titles

def migrate_automatic_profile_to_automatic_recipe(profile):
    oprofile = profile
    profile = compile_recipe(profile)
    if 'BasicUserProfile' not in profile.__name__:
        return oprofile
    return '''\
class BasicUserRecipe%d(AutomaticNewsRecipe):

    title = %s
    oldest_article = %d
    max_articles_per_feed = %d
    summary_length = %d
    
    feeds = %s
    
'''%(int(time.time()), repr(profile.title), profile.oldest_article, 
    profile.max_articles_per_feed, profile.summary_length, repr(profile.feeds))
    